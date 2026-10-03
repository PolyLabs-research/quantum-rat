"""Physical units (core.config.UnitsConfig; docs/units.md; docs/research_plan.md section 5, M0b item 6).

The declaration is read by no engine constant, so what there is to test is the
arithmetic (round trips, the derived table to the last bit), that both profiles
declare the same units, that the whole EngineConfig round-trips through
to_dict / from_dict and JSON, and that the probe's realised speeds are bounded
by the nominal FORWARD speed the declaration implies.
"""

from __future__ import annotations

import json
import math

import pytest

from brain.systems.basal_ganglia import TURN_STEP, TURN_THRUST
from core.config import EngineConfig, UnitsConfig
from tools.probes import PROBES
from tools.probes import realised_speed
from ui.scenarios import MemoryMaze

UNITS = UnitsConfig()
RAT_TRACK_RUNNING_M_S = (0.2, 0.6)  # plan section 5 item 6, for comparison


# --- the declaration and its arithmetic ------------------------------------


def test_defaults_are_the_plans_declaration() -> None:
    assert (UNITS.dt_s, UNITS.metres_per_unit) == (0.2, 0.1)
    assert UNITS.ticks_per_second == 5.0  # 1 / 0.2 is exactly 5.0 in binary floating point


def test_derived_table_holds_to_the_last_bit() -> None:
    bounds = EngineConfig().world.bounds
    assert UNITS.metres(2 * bounds[0]) == 2.0 and UNITS.metres(2 * bounds[1]) == 2.0  # 2 m x 2 m open field
    assert UNITS.metres_per_second(1.0) == 0.5  # FORWARD, 1.0 unit per tick
    assert UNITS.metres_per_second(TURN_THRUST) == 0.15  # a TURN's forward component
    assert UNITS.radians_per_second(TURN_STEP) == 1.5  # a TURN's heading step (0.3 / 0.2 would read 1.4999999999999998)
    assert UNITS.seconds(MemoryMaze.TIMEOUT) == 60.0  # the maze's 300-tick timeout
    assert UNITS.ticks(60.0) == MemoryMaze.TIMEOUT == 300
    assert UNITS.units(2.0) == 20.0
    assert RAT_TRACK_RUNNING_M_S[0] <= UNITS.metres_per_second(1.0) <= RAT_TRACK_RUNNING_M_S[1]
    # Smaller quantities are equal up to rounding only.
    assert math.isclose(UNITS.metres(EngineConfig().spatial.bin_size), 0.05, rel_tol=1e-12)  # 5 cm bins
    assert math.isclose(UNITS.metres(EngineConfig().sensors.vision_range), 1.2, rel_tol=1e-12)


@pytest.mark.parametrize("x", [0.0, 0.3, 1.0, 2.5, 7.0, 10.0, 12.0, 22.8209, 1e3])
def test_metres_and_units_round_trip(x: float) -> None:
    assert math.isclose(UNITS.units(UNITS.metres(x)), x, rel_tol=1e-12, abs_tol=1e-15)
    assert math.isclose(UNITS.metres(UNITS.units(x)), x, rel_tol=1e-12, abs_tol=1e-15)


def test_seconds_and_ticks_round_trip_on_whole_ticks() -> None:
    for n in list(range(0, 400)) + [1000, 3000, 20000]:
        assert UNITS.ticks(UNITS.seconds(n)) == n
    assert UNITS.seconds(3000) == 600.0  # a 3000-tick run is ten minutes


def test_ticks_rounds_to_the_nearest_tick_halves_up() -> None:
    assert [UNITS.ticks(s) for s in (0.0, 0.09, 0.1, 0.11, 0.3, 0.4, 0.5, 2.0)] == [0, 0, 1, 1, 2, 2, 3, 10]


def test_rates_are_per_tick_times_ticks_per_second() -> None:
    assert UNITS.metres_per_second(0.088) == pytest.approx(0.044)  # the legacy mean step, in m/s
    assert UNITS.radians_per_second(0.0) == 0.0
    other = UnitsConfig(dt_s=0.1, metres_per_unit=0.2)
    assert other.metres_per_second(1.0) == pytest.approx(2.0)
    assert other.radians_per_second(TURN_STEP) == pytest.approx(3.0)
    assert other.seconds(300) == pytest.approx(30.0)


@pytest.mark.parametrize("kwargs", [{"dt_s": 0.0}, {"dt_s": -0.2}, {"metres_per_unit": 0.0}, {"metres_per_unit": -1.0}])
def test_non_positive_units_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        UnitsConfig(**kwargs)


# --- the profiles ------------------------------------------------------------


def test_units_are_identical_in_both_profiles_and_not_in_the_diff() -> None:
    assert EngineConfig.legacy().units == EngineConfig.research().units == EngineConfig().units == UnitsConfig()
    assert not any(name.startswith("units") for name, _, _ in EngineConfig.legacy().diff(EngineConfig.research()))
    assert ("units.dt_s", 0.2, 0.1) in EngineConfig.legacy().diff(EngineConfig(units=UnitsConfig(dt_s=0.1)))


# --- to_dict / from_dict ----------------------------------------------------


@pytest.mark.parametrize("make", [EngineConfig.legacy, EngineConfig.research], ids=["legacy", "research"])
def test_to_dict_from_dict_round_trip_exactly(make) -> None:
    cfg = make()
    d = cfg.to_dict()
    assert list(d)[:3] == ["profile", "units", "world"]
    assert d["profile"] == cfg.profile
    assert d["units"] == {"dt_s": 0.2, "metres_per_unit": 0.1}
    assert d["world"]["bounds"] == [10.0, 10.0] and isinstance(d["world"]["bounds"], list)
    assert all(isinstance(v, dict) for k, v in d.items() if k != "profile")
    assert EngineConfig.from_dict(d).diff(cfg) == []
    # Through JSON too: tuples come back as tuples and inf as inf.
    text = json.dumps(d)
    back = EngineConfig.from_dict(json.loads(text))
    assert back.diff(cfg) == []
    assert back.world.bounds == (10.0, 10.0) and isinstance(back.world.bounds, tuple)
    assert back.to_dict() == d
    if cfg.profile == "research":
        assert d["trn"]["narrow_above_kappa"] == math.inf and back.trn.narrow_above_kappa == math.inf
        assert back.diff(EngineConfig.legacy()) != []


def test_from_dict_rejects_unknown_keys_and_fills_missing_ones() -> None:
    with pytest.raises(ValueError, match="trn.nope"):
        EngineConfig.from_dict({"trn": {"nope": 1}})
    with pytest.raises(ValueError, match="bogus"):
        EngineConfig.from_dict({"bogus": {}})
    with pytest.raises(ValueError, match="units.dt"):
        EngineConfig.from_dict({"units": {"dt": 0.2}})
    with pytest.raises(ValueError):
        EngineConfig.from_dict({"units": 0.2})  # a section must be a mapping
    partial = EngineConfig.from_dict({"profile": "research", "units": {"dt_s": 0.1}})
    assert partial.profile == "research"
    assert partial.units == UnitsConfig(dt_s=0.1, metres_per_unit=0.1)
    assert partial.diff(EngineConfig()) == [("profile", "research", "legacy"), ("units.dt_s", 0.1, 0.2)]


def test_to_dict_does_not_alias_the_config() -> None:
    cfg = EngineConfig()
    d = cfg.to_dict()
    d["world"]["bounds"][0] = 99.0
    d["units"]["dt_s"] = 1.0
    assert cfg.world.bounds == (10.0, 10.0) and cfg.units.dt_s == 0.2


# --- the probe --------------------------------------------------------------


def test_realised_speed_probe_is_listed_and_bounded_by_the_nominal_speed() -> None:
    """tests/characterisation/test_probes_run.py runs it at a tiny budget; here: the
    numbers it reports are consistent with the declaration. Off a wall every research
    step is 0.3 (TURN) or 1.0 (FORWARD) units, so the moving-tick speed cannot exceed
    the nominal 0.5 m/s, and every turn is TURN_STEP, 1.5 rad/s."""
    assert "realised_speed" in PROBES
    out = realised_speed.run(0.05)  # 150 ticks x 4 seeds x 2 profiles
    for label in ("research", "legacy"):
        assert set(out[f"{label}_by_seed"]) == set(realised_speed.SEEDS)
    research = out["research_pooled"]
    assert 0.0 < research["mean_moving_speed_m_s"] <= UNITS.metres_per_second(1.0)
    assert research["mean_speed_all_ticks_m_s"] <= research["mean_moving_speed_m_s"]
    assert 0.0 <= research["frac_immobile"] <= 1.0 and 0.0 <= research["frac_at_wall"] <= 1.0
    # Heading differences carry floating-point rounding (0.29999999999999993 and the like),
    # so the mean turn rate is 1.5 rad/s up to that, and the probe's 6-decimal rounding
    # reports one distinct turn size.
    assert math.isclose(research["mean_turn_rad_s"], UNITS.radians_per_second(TURN_STEP), rel_tol=1e-12)
    assert research["distinct_abs_turns"] == 1 and research["abs_turn_min_max_rad"] == [TURN_STEP, TURN_STEP]
    legacy = out["legacy_pooled"]
    assert legacy["mean_moving_speed_m_s"] < research["mean_moving_speed_m_s"]  # the ATP throttle
    assert legacy["abs_turn_min_max_rad"][1] <= TURN_STEP + 1e-9
