"""Fast checks of the odometry characterisation (experiments/odometry_characterisation.py; docs/odometry.md).

Short budgets only: four seeds and 400 units of travel per run (the full
characterisation is 30 seeds and 2,000 units, docs/data/m1), so the whole
module runs in a few seconds. The slope bands are the ones docs/odometry.md
justifies for the walk the research profile does in an open barren world, a
straight line: speed noise alone grows linearly (the forward clamp turns the
zero-mean error into a 0.02-per-unit shortfall), so its slope sits near 1.0,
and heading noise alone is the running sum of a heading random walk, so its
slope sits at 1.5 or above. The plan's 0.5-1.5 band is the one for a turning
walk, which the characterisation runs as a control; here the control only has
to show that it turns and that turning cancels part of the clamp bias.

These tests run the research profile (``EngineConfig.research()``) except
the ATP decorrelation, which is a legacy-profile measurement by design.
"""

from __future__ import annotations

import csv
import functools
import json
import math
from pathlib import Path

import pytest

from experiments import odometry_characterisation as oc

SEEDS = (1, 2, 3, 4)
DISTANCE = 400.0
FIT = (oc.FIT_LOW, DISTANCE)
BY_NAME = {c.name: c for c in oc.CONDITION_SETS["all"]}


@functools.lru_cache(maxsize=None)
def _runs(name: str):
    condition = BY_NAME[name]
    return condition, tuple(oc.run_seed(condition, seed, DISTANCE) for seed in SEEDS)


def _fit(name: str):
    condition, runs = _runs(name)
    return oc.fit_condition(condition, runs, FIT)


def test_log_log_slope_recovers_a_power_law():
    points = [(d, 3.0 * d**1.5) for d in (25.0, 50.0, 100.0, 400.0, 2000.0)]
    slope, intercept, r2 = oc.log_log_slope(points)
    assert slope == pytest.approx(1.5, abs=1e-12)
    assert intercept == pytest.approx(math.log(3.0), abs=1e-12)
    assert r2 == pytest.approx(1.0, abs=1e-12)
    # Non-positive errors are left out; fewer than two usable points is NaN.
    assert oc.log_log_slope([(25.0, 0.0), (50.0, 1.0), (100.0, 2.0)])[0] == pytest.approx(1.0)
    assert all(math.isnan(v) for v in oc.log_log_slope([(25.0, 1.0)]))
    assert all(math.isnan(v) for v in oc.log_log_slope([(25.0, 1.0), (25.0, 2.0)]))


def test_pearson():
    assert oc.pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)
    assert oc.pearson([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(-1.0)
    assert math.isnan(oc.pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]))
    assert math.isnan(oc.pearson([1.0], [2.0]))


def test_the_research_walk_in_an_open_box_is_straight():
    for name in ("speed_only", "turn_only", "both"):
        _, runs = _runs(name)
        for run in runs:
            assert not run.capped and run.distance >= DISTANCE
            assert run.forward_ticks >= 0.98 * run.ticks, (name, run.seed, run.forward_ticks, run.ticks)
            assert run.ticks <= 1.1 * DISTANCE  # one unit per FORWARD tick
            assert [c.distance for c in run.checkpoints] == [25.0 * k for k in range(1, 17)]
            assert run.net_displacement >= 0.9 * DISTANCE


def test_speed_noise_alone_grows_linearly_because_of_the_clamp():
    fit = _fit("speed_only")
    assert 0.8 <= fit["slope"] <= 1.2, fit
    assert fit["r2"] > 0.95
    _, runs = _runs("speed_only")
    for run in runs:
        # The clamp bias: the estimate falls short by about 0.05 / sqrt(2 pi) = 0.020 per unit on FORWARD ticks.
        assert -0.03 <= run.bias_per_unit <= -0.01, (run.seed, run.bias_per_unit)
        assert abs(run.final_hd_err) < 1e-12  # no heading noise: the heading estimate is exact (to wrap_angle's rounding)


def test_heading_noise_alone_is_the_running_sum_of_a_random_walk():
    fit = _fit("turn_only")
    assert 1.3 <= fit["slope"] <= 2.0, fit
    _, runs = _runs("turn_only")
    for run in runs:
        assert abs(run.bias_per_unit) < 1e-12  # no speed noise: the forward estimate is exact to the bit
        assert run.final_hd_err != 0.0


def test_both_noises_read_like_heading_noise_alone():
    both, turn, speed = _fit("both"), _fit("turn_only"), _fit("speed_only")
    assert 1.2 <= both["slope"] <= 2.0, both
    assert both["final_mean_err"] > speed["final_mean_err"]
    assert abs(both["slope"] - turn["slope"]) < abs(both["slope"] - speed["slope"])
    assert -0.03 <= both["bias_per_unit_mean"] <= -0.01


def test_the_turning_walk_turns_and_cancels_part_of_the_clamp_bias():
    fit = _fit("speed_only_turning")
    straight = _fit("speed_only")
    assert fit["walk"] == "turning" and fit["turn_share"] >= 0.3 and fit["forward_share"] >= 0.3, fit
    # The per-tick bias is the same shortfall along the heading of the moment ...
    assert -0.03 <= fit["bias_per_unit_mean"] < 0.0
    # ... but along a walk that turns, the bias vectors partly cancel, so the position error is smaller.
    assert fit["final_mean_err"] < straight["final_mean_err"]
    assert fit["net_displacement_mean"] < straight["net_displacement_mean"]


def test_atp_decorrelation_in_the_legacy_profile_at_seed_1():
    on = oc.atp_decorrelation(1, True)
    off = oc.atp_decorrelation(1, False)
    assert on["n_moving"] == off["n_moving"] > 1000  # the same body walk under both flags
    # With the gate scaling egomotion the per-tick odometry shortfall tracks ATP; with it off it cannot.
    assert on["r_step_error"] > 0.3, on
    assert abs(off["r_step_error"]) < 0.1, off
    # The error itself correlates with ATP under both flags through the shared initial trend ...
    assert off["r_error"] < -0.1 and on["r_error"] < -0.1
    # ... and not once the transient is dropped.
    assert abs(off["r_error_after_transient"]) < 0.1, off
    assert on["final_error"] > 10.0 * off["final_error"]
    assert on["frac_closed"] == off["frac_closed"] > 0.5


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_runner_writes_its_tables_byte_identically(tmp_path):
    args = ["--conditions", "named", "--seeds", "2", "--distance", "100", "--atp-seeds", "1", "--atp-ticks", "100",
            "--n-boot", "20", "--workers", "1"]
    first, second = tmp_path / "first", tmp_path / "second"
    oc.main(args + ["--out", str(first)])
    oc.main(args + ["--out", str(second)])
    assert {p.name for p in first.iterdir()} == set(oc.OUTPUT_FILES)
    for name in oc.OUTPUT_FILES:
        if name.endswith(".csv"):
            assert (first / name).read_bytes() == (second / name).read_bytes(), name
    curves = _read(first / "odometry_curves.csv")
    assert list(curves[0]) == list(oc.CURVE_COLUMNS)
    assert len(curves) == 3 * 4  # three conditions, checkpoints 25..100
    seeds = _read(first / "odometry_seeds.csv")
    assert list(seeds[0]) == list(oc.SEED_COLUMNS) and len(seeds) == 6
    slopes = _read(first / "odometry_slopes.csv")
    assert list(slopes[0]) == list(oc.SLOPE_COLUMNS)
    assert [r["condition"] for r in slopes] == ["speed_only", "turn_only", "both"]
    assert all(r["slope_low"] != "nan" and r["slope_high"] != "nan" for r in slopes)
    atp = _read(first / "odometry_atp.csv")
    assert list(atp[0]) == list(oc.ATP_COLUMNS) and [r["gate_scales_egomotion"] for r in atp] == ["True", "False"]
    meta = json.loads((first / "odometry_meta.json").read_text())
    assert meta["full"] is False and meta["seeds"] == [1, 2] and meta["n_boot"] == 20
    assert meta["fit_range"] == [50.0, 100.0]


def test_runner_refuses_the_committed_directory_for_a_partial_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the default is relative: docs/data/m1 under the cwd
    with pytest.raises(SystemExit):
        oc.main(["--conditions", "named", "--seeds", "2", "--distance", "100"])
    assert not (tmp_path / "docs").exists()
