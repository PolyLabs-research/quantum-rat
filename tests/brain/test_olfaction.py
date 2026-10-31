"""Olfaction (G60; docs/prereg/whole_smell.md §1): odour from uneaten food, two nostrils, and its pull in selection."""

from __future__ import annotations

import math

import pytest

from brain.contracts import Observation, observation_fields
from brain.systems.basal_ganglia import _smell, channel_terms, select_action_with_scores
from core.config import BasalGangliaConfig, EngineConfig, SensorConfig
from core.engine import Engine
from core.entities import Agent
from core.sensors import gather_observation, odour_at
from core.world import World, WorldObject


def _world(kind="hidden"):
    w = World(bounds=(10.0, 10.0))
    w.add_object(WorldObject(3.0, 0.0, 0.75, kind))
    return w


def test_odour_falls_with_distance_from_the_edge_and_eaten_food_does_not_smell() -> None:
    w = _world()
    assert odour_at(w, 3.0, 0.0, 1.5) == 1.0 and odour_at(w, 3.75, 0.0, 1.5) == pytest.approx(1.0)  # inside or at the edge
    assert odour_at(w, 3.0 + 0.75 + 1.5, 0.0, 1.5) == pytest.approx(math.exp(-1.0))
    assert odour_at(w, -9.0, 0.0, 1.5) < 1e-3  # across the arena: nothing
    w.objects[0].kind = "collected"
    assert odour_at(w, 3.0, 0.0, 1.5) == 0.0


def test_the_nostrils_tell_the_side_and_the_observation_carries_it_only_when_on() -> None:
    w = _world()
    agent = Agent(id=0, pos=(0.0, 0.0))
    agent.heading = math.pi / 2  # facing +y: the food at +x is to the right
    obs = gather_observation(agent, w, config=SensorConfig(olfaction=True))
    left, right = obs.odour
    assert right > left > 0.0
    off = gather_observation(agent, w, config=SensorConfig())
    assert off.odour is None and "odour" not in observation_fields(off)  # every earlier observation reads as before
    with pytest.raises(ValueError):
        Observation(vision_rays=(), whisker_hits=(False, False), pain_signal=0.0, forward_delta=0.0, turn_delta=0.0,
                    odour=(1.5, 0.0)).validate()


def test_the_pull_turns_toward_the_stronger_side_and_runs_on_when_balanced() -> None:
    assert _smell(0.6, None) == (0.0, 0.0, 0.0) and _smell(0.0, (1.0, 1.0)) == (0.0, 0.0, 0.0)
    fwd, left, right = _smell(0.6, (0.5, 0.5))
    assert fwd == pytest.approx(0.3) and left == right == 0.0
    fwd, left, right = _smell(0.6, (0.6, 0.2))
    assert left > 0.0 and right == 0.0 and fwd + left == pytest.approx(0.6 * 0.4)
    obs = Observation(vision_rays=(), whisker_hits=(False, False), pain_signal=0.0, forward_delta=0.0, turn_delta=0.0,
                      odour=(0.6, 0.2))
    cfg = BasalGangliaConfig(smell_gain=0.6)
    _, scores = select_action_with_scores(obs, 0.0, 1.0, False, cfg, {}, target_gain=0.5)
    terms = channel_terms(obs, 0.0, 1.0, False, cfg, {}, target_gain=0.5)
    for ch, parts in terms.items():
        assert sum(parts.values()) == pytest.approx(scores[ch])
    assert terms["TURN_LEFT"]["smell"] == pytest.approx(0.5 * left)  # scaled by what food is worth now
    assert "smell" not in channel_terms(obs, 0.0, 1.0, False, BasalGangliaConfig(), {})["FORWARD"]  # off: no term


def test_off_on_both_profiles_and_the_engine_runs_with_it() -> None:
    for cfg in (EngineConfig.legacy(), EngineConfig.research()):
        assert not cfg.sensors.olfaction and cfg.basal_ganglia.smell_gain == 0.0
    cfg = EngineConfig.research()
    cfg.sensors.olfaction = True
    cfg.basal_ganglia.smell_gain = 0.6
    e = Engine(seed=1, config=cfg)
    e.world.add_object(WorldObject(2.0, 0.0, 0.75, "hidden"))
    e.run(30, reset=True)
    assert e.context.observation.odour is not None
