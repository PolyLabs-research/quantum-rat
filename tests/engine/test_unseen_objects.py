"""Nothing hidden is sensed on the research profile (the audit of 2026-10-27, docs/decisions.md G46).

A "hidden" goal and a "collected" (eaten) item are not seen: vision rays and whiskers pass through them, and approach
shaping reads visible targets only, while a hidden goal still rewards on contact. The legacy profile keeps the sensing
every result before G46 had (``sensors.unseen_block_rays``, ``reward.shape_hidden``), so its record regenerates.
"""

from __future__ import annotations

import pytest

from core.config import EngineConfig, SensorConfig
from core.engine import Engine
from core.entities import Agent
from core.sensors import UNSEEN_KINDS, gather_observation
from core.world import World, WorldObject


def _agent() -> Agent:
    """At the origin, facing +x."""
    return Agent(id=0, pos=(0.0, 0.0), heading=0.0)


def _facing_an_object(kind: str, unseen_block: bool):
    """An agent at the origin facing +x, an object of ``kind`` 3 units ahead on the centre ray."""
    world = World()
    world.add_object(WorldObject(3.0, 0.0, 0.5, kind))
    agent = _agent()
    return gather_observation(agent, world, config=SensorConfig(unseen_block_rays=unseen_block))


def _centre(obs):
    return min(obs.vision_rays, key=lambda r: abs(r.angle))


@pytest.mark.parametrize("kind", UNSEEN_KINDS)
def test_an_unseen_object_is_passed_through(kind: str) -> None:
    seen = _centre(_facing_an_object(kind, unseen_block=False))
    empty = _centre(gather_observation(_agent(), World(), config=SensorConfig()))
    assert seen.obj_type == "wall" and seen.dist == empty.dist  # what lies behind it, as if it were not there


@pytest.mark.parametrize("kind", UNSEEN_KINDS)
def test_before_g46_the_ray_stopped_at_it_and_named_it(kind: str) -> None:
    ray = _centre(_facing_an_object(kind, unseen_block=True))
    assert ray.obj_type == kind and ray.dist == pytest.approx(2.5 / SensorConfig().vision_range)


def test_a_visible_target_is_still_seen() -> None:
    ray = _centre(_facing_an_object("target", unseen_block=False))
    assert ray.obj_type == "target" and ray.dist == pytest.approx(2.5 / SensorConfig().vision_range)


def test_whiskers_do_not_feel_an_unseen_object() -> None:
    world = World()
    world.add_object(WorldObject(0.6, 0.6, 0.5, "hidden"))  # within whisker range, on the left whisker's line
    agent = _agent()
    assert gather_observation(agent, world, config=SensorConfig(unseen_block_rays=True)).whisker_hits[0]
    assert not gather_observation(agent, world, config=SensorConfig(unseen_block_rays=False)).whisker_hits[0]


def test_the_profiles() -> None:
    legacy, research = EngineConfig.legacy(), EngineConfig.research()
    assert legacy.sensors.unseen_block_rays and legacy.reward.shape_hidden
    assert not research.sensors.unseen_block_rays and not research.reward.shape_hidden


def _approach(kind: str, shape_hidden: bool):
    """The rewards of a few ticks walking straight at a goal of ``kind`` from 6 units away (legacy body, no noise)."""
    cfg = EngineConfig.legacy()
    cfg.reward.shape_hidden = shape_hidden
    engine = Engine(seed=3, config=cfg)
    engine.world.add_object(WorldObject(6.0, 0.0, 0.5, kind))
    return engine.run(6)


def test_shaping_reads_a_hidden_goal_only_before_g46() -> None:
    before = _approach("hidden", shape_hidden=True)
    after = _approach("hidden", shape_hidden=False)
    assert sum(t.reward for t in before[1:5]) > 1.0  # the hot/cold signal toward food it cannot see
    assert all(t.reward <= 0.0 for t in after[1:5])  # nothing until contact


def test_shaping_toward_a_visible_target_is_unchanged() -> None:
    a = _approach("target", shape_hidden=True)
    b = _approach("target", shape_hidden=False)
    assert [t.reward for t in a] == [t.reward for t in b]


def test_a_hidden_goal_still_rewards_on_contact() -> None:
    cfg = EngineConfig.research()
    engine = Engine(seed=1, config=cfg)
    engine.world.add_object(WorldObject(0.0, 0.0, 1.0, "hidden"))
    engine.agent.pos = engine.agent.last_pos = (0.0, 0.0)
    td = engine.run(1)[0]
    assert engine.context.target_contact and td.reward >= cfg.reward.contact_bonus - 1e-9
