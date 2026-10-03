"""Smoke test and unit checks for experiments/g23_remeasure.py (docs/decisions.md G23).

The smoke test runs the whole script with ``--seeds 2 --quick`` (300-tick budgets,
gains 0 and 1.5, 4 maze headings, 200 bootstrap replicates) through two worker
processes and checks the files it writes and the keys of its summary. Measured
on the 4-core development box: about 4 s for the run, and a second, identical
run that must give byte-identical CSVs. The numbers of a quick run mean nothing;
the full run (30 seeds, 10,000 replicates) is the one the entry reports.

The unit checks pin the pure helpers: the seed-bootstrap ratio of means, G16's
worst-scenario fraction, the contiguous band, and the three verdict rules. The
separation settings of the entry's section G (A_speed, A_turn, A_softmax: one of
A's elements each on top of sensor noise) are checked at the config level, and
each gets a tiny tagged ``--quick`` run of claim 3 at gain 1.5 (one seed, four
headings, under a second) that pins the ``--tag`` file names, the ``--maze-gains``
restriction and the guard's one-element list.

These tests pin the legacy profile (EngineConfig() defaults); see docs/decisions.md G22 and docs/profiles.md.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import pytest

from analysis.stats import CI, TIDY_COLUMNS
from experiments import g23_remeasure as g23

QUICK_ARGS = ["--seeds", "2", "--quick", "--workers", "2"]


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def quick_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("g23")
    res = g23.main(QUICK_ARGS + ["--out", str(out)])
    return out, res


def test_quick_run_writes_every_file(quick_run):
    out, _ = quick_run
    names = {"hidden_food.csv", "steering_band.csv", "maze_recall.csv", "maze_recall_by_heading.csv",
             "summary.csv", "guard.csv", "meta.json"}
    assert {p.name for p in out.iterdir()} == names
    meta = json.loads((out / "meta.json").read_text())
    assert meta["seeds"] == [1, 2] and meta["quick"] is True and meta["n_boot"] == g23.QUICK_N_BOOT
    assert set(meta["settings"]) == {"A", "B"} and meta["settings"]["B"] == []
    assert meta["jobs"] == (2 * 2 * 2 + 2 * 2 * 2) + 2 * 4 * 2 * 2 + 2 * 2 * 2 * 4
    assert set(meta["verdicts"]) == {"1", "2", "3"}
    for claim in meta["verdicts"].values():
        assert set(claim) == {"A", "B", "overall"}
        assert all(v in g23.VERDICTS for v in claim.values())


def test_tidy_tables_have_the_long_format(quick_run):
    out, _ = quick_run
    for name, tasks, metrics in (
        ("hidden_food.csv", {"hidden_food"}, {"score", "sites_found"}),
        ("steering_band.csv", set(g23.CLAIM2_SCENARIOS), {"score", "vrest", "attempted"}),
        ("maze_recall.csv", {"memory_maze_full_circle"},
         {"recalls", "attempted", "recall_rate", "headings_recalling"}),
    ):
        rows = _read(out / name)
        assert rows and list(rows[0]) == list(TIDY_COLUMNS), name
        assert {r["task"] for r in rows} == tasks, name
        assert {r["metric"] for r in rows} == metrics, name
        assert {r["seed"] for r in rows} == {"1", "2"}, name
        assert all(r["condition"].split("/")[0] in ("A", "B") for r in rows), name
        for r in rows:
            float(r["value"])  # every value is a number
    hidden = _read(out / "hidden_food.csv")
    assert {r["condition"] for r in hidden} == {f"{s}/{arm}" for s in "AB"
                                               for arm in ("memory_on", "memory_off", "moved_on", "moved_off")}
    band = _read(out / "steering_band.csv")
    assert {r["condition"] for r in band} == {f"{s}/gain={g:g}" for s in "AB" for g in g23.QUICK_GAINS}
    by_heading = _read(out / "maze_recall_by_heading.csv")
    assert list(by_heading[0]) == list(g23.BY_HEADING_COLUMNS)
    assert len(by_heading) == 2 * 2 * 2 * g23.QUICK_HEADINGS


def test_summary_has_the_statistics_the_entry_reports(quick_run):
    out, res = quick_run
    rows = _read(out / "summary.csv")
    assert list(rows[0]) == list(g23.SUMMARY_COLUMNS)
    stats = {(r["claim"], r["statistic"]) for r in rows}
    for name in ("mean", "vrest_mean", "on_vs_off_paired_diff", "on_vs_off_fraction_b_gt_a",
                 "on_vs_off_fraction_b_lt_a", "on_vs_off_cliffs_delta", "on_vs_off_ratio_of_means",
                 "benefit_factor", "verdict"):
        assert ("1", name) in stats, name
    for name in ("score_mean", "vrest_mean", "vrest_max", "vs_gain0_ratio_of_means", "vs_gain0_cliffs_delta",
                 "vs_gain0_fraction_seeds_within_a_fifth", "recall_rate_mean", "fraction_seeds_recall_ok",
                 "worst_fraction", "in_guard_band_ci", "in_g16_band_ci", "guard_band_ci", "guard_band_point",
                 "g16_band_ci", "g16_band_point", "maze_recall_ok_gains_ci", "verdict"):
        assert ("2", name) in stats, name
    for name in ("recall_rate_mean", "fraction_seeds_recall_ok", "headings_recalling_mean",
                 "fraction_seeds_all_headings", "fraction_runs_recalling", "fraction_seeds_recalling_heading",
                 "recall_rate_paired_diff", "recall_rate_cliffs_delta", "verdict"):
        assert ("3", name) in stats, name
    # Every interval brackets its estimate, and the methods are the module's.
    for r in rows:
        est, low, high = (float(r[k]) for k in ("estimate", "low", "high"))
        assert r["method"] in ("bca", "percentile", "none"), r
        if math.isfinite(low) and math.isfinite(high):
            assert low <= est <= high, r
    # The verdict rows carry one of the three verdicts, per claim and setting.
    verdicts = {(r["claim"], r["setting"]): r["label"] for r in rows if r["statistic"] == "verdict"}
    assert set(verdicts) == {(c, s) for c in "123" for s in "AB"}
    assert all(v in g23.VERDICTS for v in verdicts.values())
    assert res.verdicts == {c: {s: verdicts[(c, s)] for s in "AB"} for c in "123"}
    # Cliff's delta rows carry a magnitude label; the band rows carry a band.
    assert all(r["label"] in ("negligible", "small", "medium", "large")
               for r in rows if r["statistic"].endswith("cliffs_delta"))
    band_rows = {"guard_band_ci", "guard_band_point", "g16_band_ci", "g16_band_point", "maze_recall_ok_gains_ci"}
    assert all(r["label"] for r in rows if r["statistic"] in band_rows)
    assert {r["statistic"] for r in rows if r["statistic"] in band_rows} == band_rows
    guard = _read(out / "guard.csv")
    assert list(guard[0]) == list(g23.GUARD_COLUMNS)
    assert all(int(r["n"]) == 2 and 1 <= int(r["distinct_rows"]) <= 2 for r in guard)
    assert all("sensors.noise=0.03" in r["stochastic_elements"] for r in guard)
    assert all("odometry_speed_noise" in r["stochastic_elements"] for r in guard if r["setting"] == "A")
    assert all("odometry" not in r["stochastic_elements"] for r in guard if r["setting"] == "B")


def test_quick_run_is_byte_identical(quick_run, tmp_path):
    out, _ = quick_run
    again = tmp_path / "again"
    g23.main(QUICK_ARGS + ["--out", str(again)])
    for path in sorted(out.iterdir()):
        if path.name == "meta.json":
            continue  # the one file with the wall-clock runtime in it
        assert (again / path.name).read_bytes() == path.read_bytes(), path.name


def test_ratio_of_means_resamples_seeds_together():
    off = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    ci = g23.ratio_of_means_ci(2.0 * off, off, n_boot=200, seed=1)
    # on = 2 * off seed by seed, so every replicate's ratio is exactly 2: the interval collapses.
    assert ci.estimate == 2.0 and ci.low == 2.0 and ci.high == 2.0
    assert "collapsed" in ci.note
    on = np.array([3.0, 3.0, 9.0, 7.0, 11.0, 15.0])
    ci = g23.ratio_of_means_ci(on, off, n_boot=500, seed=1)
    assert ci.estimate == pytest.approx(on.mean() / off.mean())
    assert ci.low < ci.estimate < ci.high and ci.method == "bca"
    assert g23.ratio_of_means_ci(on, np.zeros(6), 100, 1).note.startswith("undefined")


def test_worst_fraction_matches_the_harness_definition():
    # (scenarios, gains, seeds): scenario 0 is best at gain 1, scenario 1 at gain 0.
    scores = np.array([
        [[10.0, 10.0, 10.0], [20.0, 20.0, 20.0]],
        [[8.0, 8.0, 8.0], [4.0, 4.0, 4.0]],
    ])
    assert g23.worst_fraction_ci(scores, 0, 100, 1).estimate == pytest.approx(0.5)  # scenario 0: 10 / 20
    assert g23.worst_fraction_ci(scores, 1, 100, 1).estimate == pytest.approx(0.5)  # scenario 1: 4 / 8
    never = np.zeros((1, 2, 3))
    assert g23.worst_fraction_ci(np.concatenate([scores, never]), 1, 100, 1).estimate == 0.0


def test_contiguous_band_and_its_text():
    ok = {0.4: True, 0.6: True, 0.8: False, 1.0: True, 1.2: True, 1.5: True, 2.0: False}
    assert g23.contiguous_band(ok) == [1.0, 1.2, 1.5]
    assert g23.contiguous_band({0.4: True, 0.6: True, 0.8: False, 1.0: True, 1.2: True}) == [0.4, 0.6]
    assert g23.contiguous_band({0.4: False}) == []
    assert g23.band_text([0.4, 3.0]) == "0.4-3" and g23.band_text([]) == "none"


def _ci(estimate, low, high):
    return CI(estimate, low, high, "bca", 30, 100, 0.05)


def test_verdict_rules():
    assert g23.verdict_hidden_food(_ci(3.0, 2.5, 3.6), 0.0)[0] == "survives"
    assert g23.verdict_hidden_food(_ci(3.0, 2.5, 3.6), 0.1)[0] == "weakened"
    assert g23.verdict_hidden_food(_ci(2.0, 1.5, 2.6), 0.0)[0] == "weakened"
    assert g23.verdict_hidden_food(_ci(1.5, 0.9, 2.6), 0.0)[0] == "does not survive"
    assert g23.verdict_band([0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0], [0.4, 3.0])[0] == "survives"
    assert g23.verdict_band([0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0], [0.4, 3.0])[0] == "weakened"
    assert g23.verdict_band([], [])[0] == "does not survive"
    rates = {0.8: _ci(0.98, 0.95, 1.0), 1.5: _ci(0.99, 0.97, 1.0)}
    heads = {0.8: _ci(15.8, 15.3, 16.0), 1.5: _ci(15.9, 15.6, 16.0)}
    assert g23.verdict_maze(rates, heads, 16)[0] == "survives"
    assert g23.verdict_maze(rates, {0.8: _ci(14.0, 13.0, 15.0), 1.5: heads[1.5]}, 16)[0] == "weakened"
    assert g23.verdict_maze({0.8: _ci(0.9, 0.85, 0.95), 1.5: rates[1.5]},
                            {0.8: _ci(14.0, 13.0, 15.0), 1.5: heads[1.5]}, 16)[0] == "does not survive"
    assert g23.weaker(["survives", "weakened"]) == "weakened"
    assert g23.weaker(["survives", "does not survive", "weakened"]) == "does not survive"


SEPARATION = [
    ("A_speed", "sensors.odometry_speed_noise=0.05"),
    ("A_turn", "sensors.odometry_turn_noise=0.01"),
    ("A_softmax", "basal_ganglia.softmax_temperature=0.05"),
]


def test_separation_settings_split_a_and_leave_a_and_b_alone():
    assert g23.SEPARATION_ORDER == ("A_speed", "A_turn", "A_softmax")
    assert g23.SETTING_GROUPS == {"both": ("A", "B"), "separation": g23.SEPARATION_ORDER}
    assert g23.SETTINGS["A"] == (("sensors.odometry_speed_noise", 0.05), ("sensors.odometry_turn_noise", 0.01),
                                 ("basal_ganglia.softmax_temperature", 0.05))
    assert g23.SETTINGS["B"] == ()
    assert all(len(g23.SETTINGS[s]) == 1 for s in g23.SEPARATION_ORDER)
    assert tuple(g23.SETTINGS[s][0] for s in g23.SEPARATION_ORDER) == g23.SETTINGS["A"]


@pytest.mark.parametrize("setting, element", SEPARATION)
def test_separation_setting_quick_run_reaches_one_element(setting, element, tmp_path):
    from ui.scenarios import make_scenario

    assert g23.elements_of(setting, make_scenario("memory_maze").config()) == [f"sensors.noise={g23.NOISE}", element]
    out = tmp_path / setting
    res = g23.main(["--seeds", "1", "--quick", "--workers", "1", "--claims", "3", "--setting", setting,
                    "--maze-gains", "1.5", "--tag", setting, "--out", str(out)])
    # Tagged file names, and no tidy table for the claims that did not run.
    assert {p.name for p in out.iterdir()} == {f"maze_recall_{setting}.csv", f"maze_recall_by_heading_{setting}.csv",
                                               f"summary_{setting}.csv", f"guard_{setting}.csv", f"meta_{setting}.json"}
    meta = json.loads((out / f"meta_{setting}.json").read_text())
    assert meta["gains_claim3"] == [1.5] and meta["tag"] == setting and meta["claims"] == ["3"]
    assert meta["settings"] == {setting: [list(g23.SETTINGS[setting][0])]}
    assert meta["jobs"] == 1 * 1 * g23.QUICK_HEADINGS
    assert res.verdicts == {"3": {setting: meta["verdicts"]["3"][setting]}}
    rows = _read(out / f"summary_{setting}.csv")
    assert {r["setting"] for r in rows} == {setting}
    assert {r["condition"] for r in rows if r["condition"]} >= {f"{setting}/gain=1.5"}
    assert all(r["condition"].startswith(f"{setting}/gain=1.5") for r in rows if r["condition"])
    stats = {r["statistic"] for r in rows}
    assert {"recall_rate_mean", "headings_recalling_mean", "fraction_runs_recalling", "verdict"} <= stats
    assert not any(s.startswith("recall_rate_paired") or s.endswith("cliffs_delta") for s in stats)  # one gain: no pair
    guard = _read(out / f"guard_{setting}.csv")
    assert [r["stochastic_elements"] for r in guard] == [f"sensors.noise={g23.NOISE} {element}"]
    by_heading = _read(out / f"maze_recall_by_heading_{setting}.csv")
    assert {(r["setting"], r["gain"]) for r in by_heading} == {(setting, "1.5")}
    assert len(by_heading) == g23.QUICK_HEADINGS


def test_moved_sites_jumps_stay_in_the_band_and_repeat():
    from core.rng import RNG

    first = RNG(seed=g23.SITE_JUMP_SEED).stream(g23.SITE_JUMP_STREAM)
    second = RNG(seed=g23.SITE_JUMP_SEED).stream(g23.SITE_JUMP_STREAM)
    points = [g23.band_point(first) for _ in range(50)]
    assert points == [g23.band_point(second) for _ in range(50)]
    assert all(2.0 <= 10.0 - max(abs(x), abs(y)) <= 3.0 for x, y in points)
