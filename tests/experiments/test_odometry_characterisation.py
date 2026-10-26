"""Fast checks of the odometry characterisation (experiments/odometry_characterisation.py; docs/odometry.md).

Short budgets only: four seeds and 400 units of travel per run (the full
characterisation is 30 seeds and 2,000 units, docs/data/m2a/odometry), so the
whole module runs in a few seconds. The slope bands are the ones docs/odometry.md
justifies for the walk the research profile does in an open barren world, a
straight line: speed noise alone is zero-mean under the research contract
(the forward range of 2.0, M2a), so its along-track error is a random walk
whose slope sits near 0.5 with a wide scatter at four seeds (it read near 1.0
under the legacy range, where the clamp turned the error into a shortfall of
0.02 per unit), and heading noise alone is the running sum of a heading random
walk, so its slope sits at 1.5 or above. The plan's 0.5-1.5 band is the one
for a turning walk, which the characterisation runs as a control; here the
control only has to show that it turns and that the along-track error stays
unbiased on it too.

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


def test_speed_noise_alone_is_a_zero_mean_random_walk_under_the_research_range():
    fit = _fit("speed_only")
    # A random walk's log-log slope is 0.5; four seeds over 400 units scatter around it
    # (measured 0.67 at these seeds), and nowhere near the clamped contract's 1.0 at r2 > 0.95.
    assert 0.3 <= fit["slope"] <= 0.95, fit
    _, runs = _runs("speed_only")
    for run in runs:
        # No clamp bias: the signed along-track error per unit is within sampling error of 0
        # (0.05 / sqrt(400) = 0.0025 per unit is one sd of the mean error over the run).
        assert abs(run.bias_per_unit) < 0.0075, (run.seed, run.bias_per_unit)
        assert abs(run.final_hd_err) < 1e-12  # no heading noise: the heading estimate is exact (to wrap_angle's rounding)
    assert any(run.bias_per_unit > 0.0 for run in runs) and any(run.bias_per_unit < 0.0 for run in runs)
    assert fit["final_mean_err"] < 3.0  # about 0.05 * sqrt(400) = 1.0 unit; the clamped contract gave about 8


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
    assert abs(both["bias_per_unit_mean"]) < 0.0075


def test_the_turning_walk_turns_and_its_along_track_error_is_unbiased_too():
    fit = _fit("speed_only_turning")
    straight = _fit("speed_only")
    # Measured at M2a: FORWARD on about 60% of ticks, a TURN on about 27%, REST on about 13%.
    assert fit["walk"] == "turning" and fit["turn_share"] >= 0.15 and 0.3 <= fit["forward_share"] <= 0.85, fit
    assert fit["net_displacement_mean"] < 0.8 * straight["net_displacement_mean"]
    # No clamp bias on either walk under the research range.
    assert abs(fit["bias_per_unit_mean"]) < 0.0075
    _, runs = _runs("speed_only_turning")
    assert all(abs(run.final_hd_err) < 1e-12 for run in runs)  # speed noise alone: the heading is exact


def test_atp_decorrelation_in_the_legacy_profile_at_seed_1():
    on = oc.atp_decorrelation(1, True)
    off = oc.atp_decorrelation(1, False)
    # The same body walk under both flags (the estimate is not fed back to the body in a barren box).
    assert on["body_walk"] == off["body_walk"] and on["n_moving"] == off["n_moving"] > 1000
    assert on["n_wall_moving"] == off["n_wall_moving"] > 0
    # With the gate scaling egomotion the per-tick odometry shortfall tracks ATP; with it off the gate
    # is out of the estimate and what remains is the wall-sliding under-read (the next test), not the gate.
    assert on["r_step_error"] > 0.3 and on["r_step_error_after_transient"] > 0.3, on
    assert abs(off["r_step_error"]) < 0.1, off
    assert -0.2 < off["r_step_error_after_transient"] < 0.0, off  # the wall ticks sit in ATP's first decay
    assert abs(off["r_step_error_off_wall"]) < 0.05, off  # the speed noise's own contribution
    # The error itself correlates with ATP under both flags through the shared initial trend ...
    assert off["r_error"] < -0.1 and on["r_error"] < -0.1
    # ... and not once the transient is dropped.
    assert abs(off["r_error_after_transient"]) < 0.1, off
    assert on["final_error"] > 10.0 * off["final_error"]
    assert on["frac_closed"] == off["frac_closed"] > 0.5


def test_the_flag_off_step_error_residual_is_wall_sliding_and_not_the_noise():
    # Zero-noise control: exact odometry, gate off. The step error is 0 wherever
    # the body's displacement is along its heading; it is not on the moving ticks
    # at which the box clamps the body against a wall (the body slides across its
    # heading, which the projection on the heading under-reads), and those ticks
    # carry the whole correlation. The body shares its first 1,637 ticks (and so
    # the 14 wall ticks, at 276 and 311-323) with the research-noise runs; exact
    # heading odometry flips one action at tick 1,638 (turn noise 1e-9 already
    # gives the noisy runs' body), hence the different body_walk digest.
    control = oc.atp_decorrelation(1, False, speed=0.0, turn=0.0)
    noisy = oc.atp_decorrelation(1, False)
    assert control["speed"] == control["turn"] == 0.0 and not control["gate_scales_egomotion"]
    assert control["n_wall_moving"] == noisy["n_wall_moving"] > 0 and control["body_walk"] != noisy["body_walk"]
    assert control["wall_step_error_mean"] < -0.2 and noisy["wall_step_error_mean"] < -0.2
    assert abs(control["r_step_error_off_wall"]) < 0.02  # exact odometry off the walls
    assert abs(control["r_step_error"]) < 0.1 and -0.25 < control["r_step_error_after_transient"] < -0.1
    assert abs(control["r_step_error"] - noisy["r_step_error"]) < 0.02  # the noise adds nothing to it
    assert control["final_error"] < noisy["final_error"] and control["final_error"] < 1.0  # the wall offsets only


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
    assert list(atp[0]) == list(oc.ATP_COLUMNS)
    assert [r["gate_scales_egomotion"] for r in atp] == ["True", "False", "False"]  # the zero-noise control last
    assert [(r["speed"], r["turn"]) for r in atp] == [("0.05", "0.01"), ("0.05", "0.01"), ("0", "0")]
    assert len({r["body_walk"] for r in atp[:2]}) == 1 and len(atp[2]["body_walk"]) == 16
    meta = json.loads((first / "odometry_meta.json").read_text())
    assert meta["full"] is False and meta["seeds"] == [1, 2] and meta["n_boot"] == 20
    assert meta["fit_range"] == [50.0, 100.0]


def test_runner_refuses_the_committed_directory_for_a_partial_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the default is relative: docs/data/m1 under the cwd
    with pytest.raises(SystemExit):
        oc.main(["--conditions", "named", "--seeds", "2", "--distance", "100"])
    assert not (tmp_path / "docs").exists()
