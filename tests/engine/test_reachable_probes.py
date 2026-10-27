"""Reachable value probes (M3 step 2, draft): a direction's value is read only as far as the agent sees it could go."""

from __future__ import annotations

import math

import pytest

from core.config import EngineConfig
from core.engine import Engine
from core.sensors import FREE_SPACE_ANGLES
from core.world import Barrier


def _engine(reach: bool) -> Engine:
    cfg = EngineConfig.research()
    cfg.sensors.free_space_sensing = reach
    cfg.value_memory.reachable_probes = reach
    engine = Engine(seed=1, config=cfg)
    engine.world.add_barrier(Barrier(0.5, -10.0, 0.9, 10.0))  # a wall 0.5 units ahead of the origin, facing +x
    engine.agent.pos = engine.agent.last_pos = (0.0, 0.0)
    engine.agent.heading = engine.agent.last_heading = 0.0
    engine.run(1, reset=True)
    return engine


def _probe_points(engine: Engine):
    seen = []
    real = engine._value_at
    engine._value_at = lambda x, y: (seen.append((x, y)), real(x, y))[1]
    engine._value_signals(engine.context)
    engine._value_at = real
    return seen[1:]  # the first read is the current place


def test_a_probe_stops_short_of_a_wall_it_sees() -> None:
    engine = _engine(True)
    ctx = engine.context
    ahead = _probe_points(engine)[0]
    free_ahead = ctx.observation.free_space[0]
    assert free_ahead < engine.config.value_memory.lookahead
    assert math.hypot(ahead[0] - ctx.grid_x, ahead[1] - ctx.grid_y) == pytest.approx(free_ahead - engine.PROBE_CLEARANCE)


def test_off_every_probe_reads_one_lookahead_away() -> None:
    engine = _engine(False)
    ctx = engine.context
    assert engine.context.observation.free_space is None
    for x, y in _probe_points(engine):
        assert math.hypot(x - ctx.grid_x, y - ctx.grid_y) == pytest.approx(engine.config.value_memory.lookahead)


def test_the_sensed_directions_are_the_value_fan_and_the_option_needs_the_sense() -> None:
    assert FREE_SPACE_ANGLES == (0.0, *Engine.VALUE_FAN_OFFSETS, *(-o for o in Engine.VALUE_FAN_OFFSETS))
    cfg = EngineConfig.research()
    cfg.value_memory.reachable_probes = True
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
