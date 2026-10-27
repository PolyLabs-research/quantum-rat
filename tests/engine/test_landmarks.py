"""Distal cues and the learned cue map (decisions G48).

The agent sees each cue in its field of view as a name, a bearing and a distance (never a position); its spatial
system places each cue where its estimate says it is, and once a cue is learned, corrects the estimate toward where
the cues put it. Off by default: no cue is sensed, the map stays empty, and every earlier run reads as before.
"""

from __future__ import annotations

import math

import pytest

from brain.contracts import Observation
from brain.systems.spatial import SpatialSystem
from core.config import EngineConfig, SensorConfig, SpatialConfig
from core.determinism import observation_record
from core.engine import Engine
from core.entities import Agent
from core.rng import RNG
from core.sensors import gather_observation, observation_checksum
from core.world import Cue, World

CUES = (Cue(-15.0, 12.0, "A"), Cue(14.0, 15.0, "B"), Cue(16.0, -10.0, "C"), Cue(-13.0, -16.0, "D"))


def _world() -> World:
    world = World()
    world.cues.extend(CUES)
    return world


def test_a_cue_is_seen_as_a_bearing_and_a_distance_within_the_field_of_view() -> None:
    agent = Agent(id=0, pos=(0.0, 0.0), heading=0.0)
    exact = SensorConfig(landmark_sensing=True, landmark_bearing_noise=0.0, landmark_distance_noise=0.0)
    seen = {name: (b, d) for name, b, d in gather_observation(agent, _world(), config=exact).landmarks}
    assert seen["B"] == pytest.approx((math.atan2(15.0, 14.0), math.hypot(14.0, 15.0)))
    narrow = SensorConfig(landmark_sensing=True, landmark_fov=0.6 * math.pi, landmark_bearing_noise=0.0, landmark_distance_noise=0.0)
    assert {n for n, _, _ in gather_observation(agent, _world(), config=narrow).landmarks} == {"B", "C"}  # A and D behind


def test_the_errors_come_from_their_own_stream() -> None:
    agent = Agent(id=0, pos=(2.0, -1.0), heading=0.7)
    noisy = SensorConfig(landmark_sensing=True)
    a = gather_observation(agent, _world(), config=noisy, landmark_stream=RNG(seed=3).stream("sensors_landmarks"))
    b = gather_observation(agent, _world(), config=noisy, landmark_stream=RNG(seed=3).stream("sensors_landmarks"))
    exact = gather_observation(agent, _world(), config=noisy)  # no stream: no draw
    assert a.landmarks == b.landmarks and a.landmarks != exact.landmarks


def test_off_by_default_and_out_of_the_checksum_while_off() -> None:
    agent = Agent(id=0, pos=(0.0, 0.0), heading=0.0)
    off = gather_observation(agent, _world(), config=SensorConfig())
    assert off.landmarks is None and "landmarks" not in observation_record(0, off)
    on = gather_observation(agent, _world(), config=SensorConfig(landmark_sensing=True))
    assert observation_checksum(on) != observation_checksum(off)
    assert EngineConfig.research().spatial.landmark_gain == 0.0 and not EngineConfig.research().sensors.landmark_sensing


def _observe(spatial: SpatialSystem, true_pos, heading, config=None) -> None:
    config = config or SensorConfig(landmark_sensing=True, heading_oracle=True, landmark_bearing_noise=0.0,
                                    landmark_distance_noise=0.0)
    agent = Agent(id=0, pos=true_pos, heading=heading)
    obs = gather_observation(agent, _world(), config=config)
    zero = Observation(vision_rays=obs.vision_rays, whisker_hits=obs.whisker_hits, pain_signal=0.0, forward_delta=0.0,
                       turn_delta=0.0, heading=heading, landmarks=obs.landmarks)
    spatial.step(zero)


def test_a_cue_is_placed_where_the_estimate_puts_it() -> None:
    spatial = SpatialSystem(heading_source="oracle", landmark_gain=0.1, landmark_min_sightings=5)
    spatial.state.grid_x, spatial.state.grid_y = 1.0, 2.0
    for _ in range(3):
        _observe(spatial, (1.0, 2.0), 0.3)
    for cue in CUES:
        learned = spatial.cue_map[cue.name]
        assert (learned.x, learned.y) == pytest.approx((cue.x, cue.y)) and learned.sightings == 3


def test_a_learned_map_pulls_a_displaced_estimate_back() -> None:
    spatial = SpatialSystem(heading_source="oracle", landmark_gain=0.1, landmark_min_sightings=20)
    for _ in range(300):  # learn the map from a correct estimate at the centre (past the running mean: rate 0.01)
        _observe(spatial, (0.0, 0.0), 0.0)
    # The body is put down at (6, -4) and the estimate is not told: it still says the centre.
    errors = []
    for _ in range(60):
        _observe(spatial, (6.0, -4.0), 0.0)
        errors.append(math.hypot(spatial.state.grid_x - 6.0, spatial.state.grid_y + 4.0))
    assert errors[0] == pytest.approx(0.9 * math.hypot(6.0, 4.0), rel=0.02)  # one correction of 0.1
    # The map co-moves a little toward the displaced estimate (rate / (gain + rate) of it, about 9%) before the
    # estimate settles: the estimate recovers most of the way, not all of it.
    assert errors[-1] < 0.15 * math.hypot(6.0, 4.0)
    assert spatial.state.landmarks_used == 4 and spatial.state.landmark_correction > 0.0


def test_no_correction_until_a_cue_is_learned() -> None:
    spatial = SpatialSystem(heading_source="oracle", landmark_gain=0.1, landmark_min_sightings=20)
    for _ in range(19):
        _observe(spatial, (0.0, 0.0), 0.0)
    assert spatial.state.landmarks_used == 0


def test_off_the_map_stays_empty() -> None:
    spatial = SpatialSystem(heading_source="oracle")
    _observe(spatial, (0.0, 0.0), 0.0)
    assert spatial.cue_map == {} and spatial.state.landmark_correction == 0.0


def test_the_engine_refuses_a_gain_without_the_sense() -> None:
    cfg = EngineConfig.research()
    cfg.spatial.landmark_gain = 0.1
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
    with pytest.raises(ValueError):
        SpatialConfig(landmark_gain=1.5)


def test_in_the_engine_the_estimate_recovers_after_a_teleport() -> None:
    cfg = EngineConfig.research()
    cfg.sensors.landmark_sensing = True
    cfg.spatial.landmark_gain = 0.1
    engine = Engine(seed=4, config=cfg)
    engine.world.cues.extend(CUES)
    engine.run(400)  # learn the cues while the estimate is good
    x, y = engine.agent.pos
    engine.agent.pos = engine.agent.last_pos = (-7.0 if x > 0 else 7.0, -7.0 if y > 0 else 7.0)  # moved, not told
    engine.run(1)
    first = math.hypot(engine.spatial.state.grid_x - engine.agent.pos[0], engine.spatial.state.grid_y - engine.agent.pos[1])
    engine.run(40)
    later = math.hypot(engine.spatial.state.grid_x - engine.agent.pos[0], engine.spatial.state.grid_y - engine.agent.pos[1])
    assert first > 3.0 and later < 1.5


def test_lateral_odometry_reports_a_slide_and_the_estimate_follows_it() -> None:
    from core.world import Barrier

    cfg = EngineConfig.research()
    cfg.sensors.odometry_speed_noise = 0.0
    cfg.sensors.lateral_odometry = True
    engine = Engine(seed=2, config=cfg)
    engine.world.add_barrier(Barrier(1.0, -10.0, 1.5, 10.0))
    a = engine.agent
    a.pos = a.last_pos = (0.5, 0.0)
    a.heading = a.last_heading = math.pi / 4  # into the wall at 45 degrees: the body slides along it
    engine.spatial.state.grid_x, engine.spatial.state.grid_y = 0.5, 0.0
    engine.run(1)
    obs = engine.context.observation
    dx, dy = a.pos[0] - a.last_pos[0], a.pos[1] - a.last_pos[1]
    assert obs.lateral_delta == pytest.approx(-dx * math.sin(a.heading) + dy * math.cos(a.heading))
    off = EngineConfig.research()
    assert not off.sensors.lateral_odometry


def test_off_the_observation_has_no_lateral_field() -> None:
    agent = Agent(id=0, pos=(0.0, 0.0), heading=0.0)
    assert gather_observation(agent, _world(), config=SensorConfig()).lateral_delta is None
