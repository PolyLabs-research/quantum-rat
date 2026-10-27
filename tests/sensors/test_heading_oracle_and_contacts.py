"""The heading oracle and wall-contact sensing (M2b step 1, docs/prereg/m2b_estimate.md).

Pins the two optional Observation fields: absent (None) unless the sensor config turns them on, left out of the
checksum and the determinism record while absent (so no earlier hash moves), validated when present; the oracle's
reading and its error stream; the touch geometry at each wall and at a corner; and the config rules around them.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, replace

import pytest

from brain.contracts import OPTIONAL_OBSERVATION_FIELDS, Observation, observation_fields
from core.config import HEADING_SOURCES, EngineConfig, SensorConfig, SpatialConfig
from core.determinism import observation_record
from core.entities import Agent
from core.rng import RNG
from core.sensors import gather_observation, observation_checksum
from core.world import World


def _legacy_checksum(obs: Observation) -> str:
    """The checksum as it was before M2b: every field of asdict, sorted, repr'd."""
    def norm(obj):
        if isinstance(obj, dict):
            return {k: norm(obj[k]) for k in sorted(obj)}
        if isinstance(obj, list):
            return [norm(v) for v in obj]
        return obj
    data = asdict(obs)
    for name in OPTIONAL_OBSERVATION_FIELDS:
        data.pop(name)
    return hashlib.sha256(repr(norm(data)).encode("utf-8")).hexdigest()


def _obs(agent: Agent, config: SensorConfig, world: World = None, seed: int = 1):
    rng = RNG(seed=seed)
    return gather_observation(agent, world or World(), config=config, odometry_stream=rng.stream("sensors_odometry"),
                              heading_stream=rng.stream("sensors_heading"))


def test_absent_fields_leave_the_checksum_and_the_record_as_they_were() -> None:
    agent = Agent(id=0, pos=(1.0, 2.0), heading=0.3)
    obs = _obs(agent, SensorConfig())
    assert obs.heading is None and obs.wall_contacts is None and obs.landmarks is None
    assert OPTIONAL_OBSERVATION_FIELDS == ("heading", "wall_contacts", "landmarks", "lateral_delta")  # the last two: G48
    assert observation_checksum(obs) == _legacy_checksum(obs)
    assert set(observation_fields(obs)) == set(asdict(obs)) - set(OPTIONAL_OBSERVATION_FIELDS)
    assert "heading" not in observation_record(0, obs) and "wall_contacts" not in observation_record(0, obs)
    # Present fields enter both, and change the checksum.
    on = _obs(agent, SensorConfig(heading_oracle=True, wall_contact_sensing=True))
    assert on.heading == pytest.approx(0.3) and on.wall_contacts == ()
    rec = observation_record(0, on)
    assert rec["heading"] == pytest.approx(0.3) and rec["wall_contacts"] == []
    assert observation_checksum(on) != observation_checksum(obs)
    assert observation_fields(on)["wall_contacts"] == ()  # an empty tuple is present, not absent


def test_the_heading_oracle_reads_the_true_heading_with_its_own_error_stream() -> None:
    agent = Agent(id=0, pos=(0.0, 0.0), heading=3.1)
    exact = SensorConfig(heading_oracle=True)
    rng = RNG(seed=7)
    stream = rng.stream("sensors_heading")
    before = stream.getstate()
    obs = gather_observation(agent, World(), config=exact, heading_stream=stream)
    assert obs.heading == pytest.approx(3.1) and stream.getstate() == before  # no draw at sigma 0
    noisy = SensorConfig(heading_oracle=True, heading_oracle_noise=0.05)
    readings = [gather_observation(agent, World(), config=noisy, heading_stream=stream).heading for _ in range(2000)]
    errs = [math.remainder(h - 3.1, 2 * math.pi) for h in readings]
    assert abs(sum(errs) / len(errs)) < 0.005 and 0.045 < math.sqrt(sum(e * e for e in errs) / len(errs)) < 0.055
    assert all(-math.pi <= h <= math.pi for h in readings)  # wrapped (3.1 + error crosses pi)
    assert any(h < 0 for h in readings)
    # The odometry stream is untouched by the oracle: the egomotion draws are the same with it on or off.
    a = gather_observation(agent, World(), config=SensorConfig(odometry_turn_noise=0.01), odometry_stream=RNG(seed=3).stream("sensors_odometry"))
    b = gather_observation(agent, World(), config=SensorConfig(odometry_turn_noise=0.01, heading_oracle=True, heading_oracle_noise=0.05),
                           odometry_stream=RNG(seed=3).stream("sensors_odometry"), heading_stream=RNG(seed=3).stream("sensors_heading"))
    assert a.turn_delta == b.turn_delta and a.forward_delta == b.forward_delta


@pytest.mark.parametrize("pos,heading,expected", [
    ((10.0, 0.0), 0.0, (0.0,)),                       # facing the +x wall
    ((10.0, 3.0), math.pi / 2, (-math.pi / 2,)),      # +x wall on the right while facing +y
    ((-10.0, 0.0), 0.0, (-math.pi,)),                 # -x wall behind (wrapped to -pi)
    ((0.0, -10.0), 0.0, (-math.pi / 2,)),             # -y wall on the right
    ((10.0, 10.0), math.pi / 2, (-math.pi / 2, 0.0)),  # the +x/+y corner: x wall first
    ((9.999, 0.0), 0.0, ()),                          # a millimetre off the line: no touch
])
def test_wall_contacts_are_the_egocentric_normals_of_the_walls_touched(pos, heading, expected) -> None:
    obs = _obs(Agent(id=0, pos=pos, heading=heading), SensorConfig(wall_contact_sensing=True))
    assert len(obs.wall_contacts) == len(expected)
    for got, want in zip(obs.wall_contacts, expected):
        assert math.isclose(math.remainder(got - want, 2 * math.pi), 0.0, abs_tol=1e-12)


def test_validation_and_the_config_rules() -> None:
    base = Observation(vision_rays=(), whisker_hits=(False, False), pain_signal=0.0, forward_delta=0.0, turn_delta=0.0)
    base.validate()
    with pytest.raises(ValueError):
        replace(base, heading=4.0).validate()
    with pytest.raises(ValueError):
        replace(base, wall_contacts=(0.0, 1.0, 2.0)).validate()
    with pytest.raises(ValueError):
        replace(base, wall_contacts=(5.0,)).validate()
    with pytest.raises(ValueError):
        SensorConfig(heading_oracle_noise=0.1)  # noise without the oracle draws nothing
    with pytest.raises(ValueError):
        SensorConfig(heading_oracle=True, heading_oracle_noise=-1.0)
    with pytest.raises(ValueError):
        SpatialConfig(heading_source="compass")
    with pytest.raises(ValueError):
        SpatialConfig(reset_bounds=(10.0, -1.0))
    assert SpatialConfig(reset_bounds=[10, 5]).reset_bounds == (10.0, 5.0)
    from brain.systems.spatial import HEADING_SOURCES as SPATIAL_SOURCES
    assert HEADING_SOURCES == SPATIAL_SOURCES == ("integrated", "oracle")
    # The oracle's error counts as a stochastic element only while the oracle is on. The legacy profile has no oracle;
    # the research profile carries it, the wall-contact sensing and the reset since M2b's exit (decisions G37).
    cfg = EngineConfig.legacy()
    assert "sensors.heading_oracle_noise=0.05" not in cfg.stochastic_elements()
    cfg.sensors.heading_oracle = True
    cfg.sensors.heading_oracle_noise = 0.05
    assert cfg.stochastic_elements()[-1] == "sensors.heading_oracle_noise=0.05"
    cfg.spatial.reset_bounds = (10.0, 10.0)
    again = EngineConfig.from_dict(cfg.to_dict())
    assert again.spatial.reset_bounds == (10.0, 10.0) and again.sensors.heading_oracle and again.sensors.heading_oracle_noise == 0.05
    legacy = EngineConfig.legacy()
    assert not legacy.sensors.heading_oracle and not legacy.sensors.wall_contact_sensing
    assert legacy.spatial.heading_source == "integrated" and not legacy.spatial.wall_reset
    research = EngineConfig.research()
    assert research.sensors.heading_oracle and research.sensors.heading_oracle_noise == 0.05
    assert research.sensors.wall_contact_sensing and research.spatial.heading_source == "oracle"
    assert research.spatial.wall_reset and research.spatial.reset_bounds is None  # the arena's own bounds
    assert research.stochastic_elements()[-1] == "sensors.heading_oracle_noise=0.05"
