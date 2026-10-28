"""History and motivation in the engine (G52): off by default; on, the drive reaches action selection."""

from __future__ import annotations

import pytest

from brain.systems.basal_ganglia import channel_terms
from core.config import EngineConfig
from core.engine import Engine


def test_off_by_default() -> None:
    for cfg in (EngineConfig.legacy(), EngineConfig.research()):
        assert not cfg.history.enabled and not cfg.motivation.enabled
    e = Engine(seed=1, config=EngineConfig.research())
    e.run(5)
    assert e.history is None and e.motivation is None and e.context.motivation == 1.0


def test_motivation_needs_the_visit_channel_and_history_needs_the_place_code() -> None:
    cfg = EngineConfig.research()
    cfg.motivation.enabled = True
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
    cfg = EngineConfig.legacy()
    cfg.history.enabled = True
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)


def test_an_agent_with_nothing_to_move_for_rests_and_the_terms_still_sum() -> None:
    cfg = EngineConfig.research()
    cfg.history.enabled = True
    cfg.motivation.enabled = True
    cfg.history.visit_familiarisation = 1.0  # everything familiar at once: curiosity never rises
    cfg.motivation.hunger_initial = 0.0  # and sated: hunger is no reason either (G53: hunger alone is one)
    e = Engine(seed=2, config=cfg)
    trace = e.run(300)
    rest = sum(t.action_name == "REST" for t in trace[100:]) / 200
    assert e.context.motivation < 0.05 and rest > 0.5
    ctx = e.context
    terms = channel_terms(ctx.observation, ctx.wm_novelty, ctx.trn_gate_value, ctx.microsleep_active, e.config.basal_ganglia,
                          ctx.neuromodulators, *ctx.value_signals, ctx.criticality_gain, ctx.freeze_habituation, 0.0,
                          ctx.previous_action, ctx.motivation, ctx.vigour)
    for ch, parts in terms.items():
        assert sum(parts.values()) == pytest.approx(ctx.action_scores[ch])
    assert terms["REST"]["idle"] > 0.9
    assert ctx.vigour == pytest.approx(0.5)  # nothing found: the floor of its vigour (G53)


def test_the_capped_step_never_passes_its_target_where_the_uncapped_one_diverges() -> None:
    import numpy as np

    from core.world import WorldObject
    from experiments import m3_part2 as p2

    def run(cap: bool) -> float:
        cfg = p2.track_config({})
        cfg.place.reward_step_cap = cap
        e = Engine(seed=31, config=cfg)
        e.world.add_object(WorldObject(9.0, 0.0, 0.5, "hidden"))
        with np.errstate(over="ignore", invalid="ignore"):
            e.run(1500)
        return float(np.max(np.abs(e.sr_weights)))

    assert run(True) <= 1.0 + 1e-9  # rewards are 0 and 1: a weight that never passes its target stays in [0, 1]
    assert not run(False) <= 1.0  # the 0.1 m track at the unlearning rate 4: the uncapped weights leave [0, 1]


def test_the_cap_is_the_research_default_and_pinned_off_before_g53() -> None:
    from core.config import PRE_G50, PRE_G53

    assert EngineConfig.research().place.reward_step_cap and not EngineConfig.legacy().place.reward_step_cap
    assert PRE_G53 == {"place.reward_step_cap": False} and PRE_G50["place.reward_step_cap"] is False


def test_a_fixed_schema_is_read_never_learned_and_r_keeps_its_own_rule() -> None:
    import numpy as np

    from core.world import WorldObject
    from experiments import m3_part2 as p2

    cfg = p2.track_config({})
    cfg.history.enabled = True
    cfg.history.schema = {"taste": (-1.0, 0.0, 0.0)}
    e = Engine(seed=31, config=cfg)
    e.world.add_object(WorldObject(9.0, 0.0, 0.5, "hidden"))
    e.run(1500)
    assert e.history.fixed and list(e.history.schema["taste"]) == [-1.0, 0.0, 0.0]  # given, and never moved
    assert float(np.min(e.sr_weights)) >= 0.0 and float(np.max(e.sr_weights)) <= 1.0 + 1e-9  # G36's rule, untouched
    assert e.history.reward_adjustment() is not None
    cfg.history.schema = {"taste": (-1.0, 0.0)}
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
    cfg.history.schema = {"sight": (0.0, 0.0, 0.0)}
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
