"""Barriers: solid interior walls (decisions G47).

A barrier stops the body (which slides along it) and every ray and whisker, which see it as "wall"; the touch sense
does not report it, so the declared wall-contact reset never fires against it. With no barrier nothing changes (the
determinism baselines pin that).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from core.config import EngineConfig, SensorConfig
from core.engine import Engine
from core.entities import Agent
from core.sensors import gather_observation
from core.world import BARRIER_CLEARANCE, Barrier, World


def _wall() -> World:
    world = World()
    world.add_barrier(Barrier(2.0, -3.0, 2.5, 3.0))  # a vertical wall segment ahead of an agent at the origin facing +x
    return world


def test_a_barrier_needs_extent() -> None:
    with pytest.raises(ValueError):
        Barrier(1.0, 0.0, 1.0, 2.0)


def test_a_move_into_a_barrier_stops_at_its_face() -> None:
    assert _wall().constrain((0.0, 0.0), (5.0, 0.0)) == (2.0 - BARRIER_CLEARANCE, 0.0)
    assert _wall().constrain((4.0, 0.0), (-1.0, 0.0)) == (2.5 + BARRIER_CLEARANCE, 0.0)


def test_a_move_at_an_angle_slides_along_it() -> None:
    x, y = _wall().constrain((1.5, 0.0), (3.0, 1.0))
    assert x == 2.0 - BARRIER_CLEARANCE and y == 1.0


def test_a_move_past_its_end_is_free() -> None:
    assert _wall().constrain((0.0, 4.0), (5.0, 4.0)) == (5.0, 4.0)


def test_no_move_ends_inside_or_crosses_a_barrier() -> None:
    world = World()
    world.add_barrier(Barrier(-1.0, -1.0, 1.0, 1.0))
    world.add_barrier(Barrier(3.0, -5.0, 3.2, 5.0))
    rng = np.random.default_rng(0)
    for _ in range(5000):
        frm = tuple(rng.uniform(-8, 8, 2))
        if any(b.contains(*frm) for b in world.barriers):
            continue
        to = (frm[0] + rng.normal(0, 3), frm[1] + rng.normal(0, 3))
        x, y = world.constrain(frm, to)
        assert not any(b.contains(x, y) for b in world.barriers)
        # neither axis leg crosses a barrier: the x leg at the start's y, the y leg at the end's x
        for b in world.barriers:
            if b.y0 <= frm[1] <= b.y1:
                assert not (min(frm[0], x) < b.x0 and max(frm[0], x) > b.x1)
                assert not (min(frm[0], x) <= b.x0 <= max(frm[0], x) and frm[0] != x and (frm[0] < b.x0) != (x < b.x0))
            if b.x0 <= x <= b.x1:
                assert not (min(frm[1], y) < b.y0 and max(frm[1], y) > b.y1)


def test_a_ray_sees_a_barrier_as_a_wall() -> None:
    agent = Agent(id=0, pos=(0.0, 0.0), heading=0.0)
    obs = gather_observation(agent, _wall(), config=SensorConfig())
    centre = min(obs.vision_rays, key=lambda r: abs(r.angle))
    assert centre.obj_type == "wall" and centre.dist == pytest.approx(2.0 / SensorConfig().vision_range)
    behind = gather_observation(Agent(id=0, pos=(0.0, 0.0), heading=math.pi), _wall(), config=SensorConfig())
    assert min(behind.vision_rays, key=lambda r: abs(r.angle)).dist == pytest.approx(10.0 / SensorConfig().vision_range)


def test_whiskers_feel_a_barrier_but_the_touch_sense_does_not_report_it() -> None:
    world = World()
    world.add_barrier(Barrier(0.3, -2.0, 0.6, 2.0))
    agent = Agent(id=0, pos=(0.3 - BARRIER_CLEARANCE, 0.0), heading=0.0)
    obs = gather_observation(agent, world, config=SensorConfig(wall_contact_sensing=True))
    assert obs.whisker_hits == (True, True)
    assert obs.wall_contacts == ()


def test_the_engine_body_is_stopped_and_its_odometry_reads_the_true_displacement() -> None:
    cfg = EngineConfig.research()
    cfg.sensors.odometry_speed_noise = 0.0
    engine = Engine(seed=1, config=cfg)
    engine.world.add_barrier(Barrier(0.5, -10.0, 1.0, 10.0))  # a wall across the arena just ahead
    engine.agent.pos = engine.agent.last_pos = (0.0, 0.0)
    engine.agent.heading = engine.agent.last_heading = 0.0
    for _ in range(60):
        engine.run(1)
        a = engine.agent
        assert a.pos[0] < 0.5
        moved = (a.pos[0] - a.last_pos[0]) * math.cos(a.heading) + (a.pos[1] - a.last_pos[1]) * math.sin(a.heading)
        assert engine.context.observation.forward_delta == pytest.approx(moved)


def test_the_rodent_body_is_stopped_too() -> None:
    cfg = EngineConfig.research()
    cfg.set_field("body.model", "rodent")
    engine = Engine(seed=1, config=cfg)
    engine.world.add_barrier(Barrier(0.5, -10.0, 1.0, 10.0))
    engine.agent.pos = engine.agent.last_pos = (0.0, 0.0)
    engine.agent.heading = engine.agent.last_heading = 0.0
    assert max(td.pos[0] for td in engine.run(120)) < 0.5
