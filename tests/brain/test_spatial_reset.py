"""The spatial system's heading oracle and wall-contact reset (M2b step 1, docs/prereg/m2b_estimate.md)."""

from __future__ import annotations

import math

import pytest

from brain.contracts import Observation
from brain.systems.spatial import SpatialSystem, wall_of_normal
from core.config import EngineConfig
from core.engine import Engine


def _obs(forward=0.0, turn=0.0, heading=None, contacts=None) -> Observation:
    return Observation(vision_rays=(), whisker_hits=(False, False), pain_signal=0.0, forward_delta=forward,
                       turn_delta=turn, heading=heading, wall_contacts=contacts)


def test_the_oracle_heading_replaces_the_integrated_one() -> None:
    integ = SpatialSystem()
    oracle = SpatialSystem(heading_source="oracle")
    for s in (integ, oracle):
        s.step(_obs(forward=1.0, turn=0.3, heading=1.0))
    assert integ.state.hd_angle == pytest.approx(0.3) and oracle.state.hd_angle == pytest.approx(1.0)
    assert oracle.state.grid_x == pytest.approx(math.cos(1.0)) and oracle.state.grid_y == pytest.approx(math.sin(1.0))
    with pytest.raises(ValueError):
        oracle.step(_obs(forward=1.0))  # no heading reading
    with pytest.raises(ValueError):
        SpatialSystem(heading_source="compass")
    with pytest.raises(ValueError):
        SpatialSystem(wall_reset=True)  # no bounds


def test_the_reset_writes_the_touched_walls_coordinate_and_nothing_else() -> None:
    s = SpatialSystem(heading_source="oracle", wall_reset=True, reset_bounds=(10.0, 8.0))
    s.state.grid_x, s.state.grid_y = 7.0, 3.0
    s.step(_obs(heading=0.0, contacts=(0.0,)))  # facing +x and touching the wall ahead
    assert (s.state.grid_x, s.state.grid_y) == (10.0, 3.0) and s.state.resets == ("+x",)
    s.step(_obs(heading=math.pi / 2, contacts=(-math.pi / 2, 0.0)))  # the +x/+y corner
    assert (s.state.grid_x, s.state.grid_y) == (10.0, 8.0) and s.state.resets == ("+x", "+y")
    s.step(_obs(heading=0.0, contacts=()))
    assert s.state.resets == () and (s.state.grid_x, s.state.grid_y) == (10.0, 8.0)
    s.step(_obs(heading=0.0, contacts=(math.pi,)))  # -x wall behind
    assert s.state.grid_x == -10.0 and s.state.resets == ("-x",)
    s.step(_obs(heading=math.pi, contacts=(math.pi / 2,)))  # facing -x, wall on the left: the -y wall
    assert s.state.grid_y == -8.0 and s.state.resets == ("-y",)
    with pytest.raises(ValueError):
        s.step(_obs(heading=0.0))  # the reset needs the contact channel


def test_a_heading_error_past_45_degrees_resets_the_wrong_wall() -> None:
    """Wall identity comes from the heading estimate: an integrated heading that drifted 50 degrees snaps the
    touched +x wall's normal to +y, which is what the experiment's wrong-wall share measures."""
    s = SpatialSystem(wall_reset=True, reset_bounds=(10.0, 10.0))
    s.state.hd_angle = math.radians(50.0)  # the body faces +x (contact normal 0 egocentric), the estimate says 50 deg
    s.step(_obs(contacts=(0.0,)))
    assert s.state.resets == ("+y",) and s.state.grid_y == 10.0
    assert [wall_of_normal(a) for a in (0.0, math.pi, math.pi / 2, -math.pi / 2, math.pi / 4)] == ["+x", "-x", "+y", "-y", "+x"]


def test_the_engine_wires_the_oracle_and_the_reset_and_refuses_them_without_their_channels() -> None:
    # The research profile carries the oracle heading and the reset since M2b's exit (decisions G37); the engine
    # refuses each of them without its sensor channel.
    cfg = EngineConfig.research()
    cfg.sensors.heading_oracle_noise = 0.0
    cfg.sensors.heading_oracle = False  # heading_source is still "oracle"
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
    cfg = EngineConfig.research()
    cfg.sensors.wall_contact_sensing = False  # wall_reset is still on
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
    cfg = EngineConfig.research()
    cfg.sensors.heading_oracle_noise = 0.0
    eng = Engine(seed=1, config=cfg)
    assert eng.spatial.reset_bounds == (10.0, 10.0) and eng.spatial.heading_source == "oracle"
    eng.run(400, reset=True)
    # At sigma 0 the oracle heading is the body's; after a reset the touched coordinate equals the body's.
    assert eng.spatial.state.hd_angle == pytest.approx(math.remainder(eng.agent.heading, 2 * math.pi))
    # The sensing alone changes nothing the research body does: with the estimate integrated and no reset, the walk
    # is the same with the channels off and on.
    plain_cfg = EngineConfig.research()
    plain_cfg.spatial.heading_source = "integrated"
    plain_cfg.spatial.wall_reset = False
    plain_cfg.sensors.heading_oracle_noise = 0.0
    plain_cfg.sensors.heading_oracle = False
    plain_cfg.sensors.wall_contact_sensing = False
    plain = Engine(seed=4, config=plain_cfg)
    sensed_cfg = EngineConfig.research()
    sensed_cfg.spatial.heading_source = "integrated"
    sensed_cfg.spatial.wall_reset = False
    sensed = Engine(seed=4, config=sensed_cfg)
    a = [td.pos for td in plain.run(600, reset=True)]
    b = [td.pos for td in sensed.run(600, reset=True)]
    assert a == b
