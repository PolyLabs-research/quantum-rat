"""The action value and replay in the engine (M3 step 3): off by default; on, it learns, the steering reads it, the
agent pauses to eat and the rule's backups are one event per pause."""

from __future__ import annotations

import numpy as np
import pytest

from core.config import REPLAY_RULES, VALUE_SOURCES, EngineConfig
from core.engine import Engine
from experiments import m3_part2 as p2

AV = {"action_value.enabled": True, "value_memory.source": "action"}


def _cfg(**over):
    cfg = p2.track_config({})
    for k, v in {**AV, **over}.items():
        cfg.set_field(k, v)
    return cfg


def test_off_by_default_and_the_requirements() -> None:
    for cfg in (EngineConfig.legacy(), EngineConfig.research()):
        assert not cfg.action_value.enabled and cfg.replay.rule == "none"
    assert "action" in VALUE_SOURCES and REPLAY_RULES == ("none", "uniform", "reverse", "gain_need")
    e = Engine(seed=1, config=EngineConfig.research())
    e.run(3)
    assert e.action_learner is None and e.transition_memory is None and e.replay_rule is None and not e.context.consuming
    cfg = EngineConfig.research()
    cfg.replay.rule = "reverse"
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
    cfg = EngineConfig.research()
    cfg.value_memory.source = "action"
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
    with pytest.raises(ValueError):
        EngineConfig.research().replay.__class__(rule="dyna")
    assert "replay" in e.streams  # the uniform rule's stream, drawn only by it


def test_it_learns_on_the_track_the_steering_reads_it_and_each_meal_is_a_pause_with_one_event() -> None:
    rows = {rule: p2._track_job(("c", {**AV, "replay.rule": rule}, "learned", 31, 1500)) for rule in ("none", "reverse", "uniform")}
    for rule, row in rows.items():
        assert row["rewards"] >= 1, rule
        assert row["rest_share"] >= 5 * row["rewards"] / 1500 - 1e-9, rule  # the body rests five ticks at every meal
        assert row["replay_events"] == (0 if rule == "none" else row["rewards"]), rule  # one event per pause, none without a rule
    e = Engine(seed=31, config=_cfg())
    from core.world import WorldObject

    e.world.add_object(WorldObject(9.0, 0.0, 0.5, "hidden"))
    e.run(1, reset=True)
    e.run(600)
    assert e.action_learner.learner.updates > 0 and len(e.transition_memory) > 0
    assert any(abs(v) > 0.0 for v in e.context.action_values)  # the advantages the steering read this tick
    t = e.transition_memory.all()[-1]
    assert t.action in ("FORWARD", "TURN_LEFT", "TURN_RIGHT") and t.episode == e.episode


def test_begin_episode_cuts_the_chain_and_the_oracle_reads_the_true_position() -> None:
    e = Engine(seed=2, config=_cfg(**{"replay.rule": "reverse"}))
    e.run(50, reset=True)
    e._consume_remaining = 3
    e.begin_episode()
    assert e._av_prev is None and e._consume_remaining == 0 and all(not np.any(v) for v in e.action_learner.learner.e.values())
    o = Engine(seed=2, config=_cfg(**{"action_value.oracle_state": True}))
    o.run(20, reset=True)
    assert o._av_position(o.context) == (float(o.agent.pos[0]), float(o.agent.pos[1]))
    assert e._av_position(e.context) == (float(e.context.grid_x), float(e.context.grid_y))


def test_the_gain_need_rule_builds_over_the_place_code() -> None:
    from brain.systems.replay_place import PlaceQModel

    e = Engine(seed=3, config=_cfg(**{"replay.rule": "gain_need"}))
    e.run(30, reset=True)
    model = e.replay_rule.model
    assert isinstance(model, PlaceQModel) and model.acting_state() == int(np.argmax(e.place.rates(e.context.grid_x, e.context.grid_y)))
    policy = model.policy(model.action_scores({"FORWARD": 0.1, "TURN_LEFT": 0.0, "TURN_RIGHT": 0.0}))
    assert sum(policy.values()) == pytest.approx(1.0) and policy["FORWARD"] > policy["TURN_LEFT"]
    assert model.need(model.acting_state(), model.acting_state()) > 0.0
    with pytest.raises(RuntimeError):
        model.action_of(0.0, 0.0, 1.0, 0.0)
