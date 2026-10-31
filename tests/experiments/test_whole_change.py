"""The whole, part 2 (docs/prereg/whole_change.md): the layouts, the windows, the spark's scoring, a quick run; and its
second design, by smell (docs/prereg/whole_smell.md): the parts, the validity checks, the feasibility rule."""

from __future__ import annotations

import math

import pytest

from experiments import whole_change as wc


def test_the_layouts_and_windows() -> None:
    assert len(wc.FIRST) == len(wc.SECOND) == 3
    for (x, y) in wc.SECOND:  # none of the new places within 3 units of an old one
        assert min(math.hypot(x - a, y - b) for (a, b) in wc.FIRST) >= 3.0
    assert abs(wc.CHANCE - 0.0942) < 1e-3
    w = wc.windows(18000)
    assert w["change"] == (9000, 9000) and w["before"] == (4500, 9000) and w["after"] == (13500, 18000)
    assert w["pre5"] == (7500, 9000) and w["post5"] == (9000, 10500)


def _rows(n=12, survived=True, before=3e-4, after=3e-4, zone=0.05):
    return [{"survived": survived, "intake_before": before, "intake_after": after, "old_zone_after": zone, "old_zone_post5": 0.2,
             "first_new_meal": 300, "coverage_pre5": 50, "coverage_post5": 80, "ne_pre5": 0.1, "ne_post5": 0.3,
             "efficiency_before": 6.0, "efficiency_after": 5.0, "sleep_share": 0.2, "meals": 30, "min_energy_after": 0.5}
            for _ in range(n)]


def test_the_spark() -> None:
    s = wc.score(_rows())
    assert s["spark"] and s["A1"] and s["A2"] and s["A3"] and s["recovery"] == 1.0
    assert not wc.score(_rows(after=2e-4))["A2"]  # recovered to two thirds only
    assert not wc.score(_rows(zone=0.2))["A3"]  # still near the old places
    assert not wc.score(_rows(survived=False))["A1"]
    assert not wc.score(_rows(n=5))["A3"]  # too few seeds alive in the last quarter-hour


def test_quick_run(tmp_path) -> None:
    summary = wc.main(["--phase", "pilot", "--quick", "--workers", "1", "--out", str(tmp_path)])
    assert len(summary["scores"]) == 27 and summary["windows"]["change"] == (600, 600)
    header = (tmp_path / "runs.csv").read_text().splitlines()[0]
    assert header == ",".join(wc.COLUMNS) and (tmp_path / "energy_trace.csv").exists()
    assert "validity" not in summary and "kind" not in summary  # the first design's summary, as G58 wrote it


# The second design (docs/prereg/whole_smell.md; G60)


def test_the_second_design_has_thirteen_parts_on_the_scale_and_29_configurations() -> None:
    parts = wc.smell_parts()
    assert list(parts)[-1] == "olfaction" and len(parts) == 13 and parts["olfaction"] == wc.OLFACTION
    assert parts["interoception"]["interoception.reward_scale"] == wc.wr.REWARD_SCALE == 9.7
    assert "interoception.reward_scale" not in wc.wr.PARTS["interoception"]  # part 1's parts are left as they were
    configs = wc.wr.configurations(parts)
    assert len(configs) == 29 and configs["whole"]["sensors.olfaction"] and "sensors.olfaction" not in configs["whole-olfaction"]
    assert configs["base+olfaction"] == {**wc.wr.BASE, **wc.OLFACTION}
    first, second = wc.layouts(True)
    assert first[-1] == wc.FOURTH[0] and second[-1] == wc.FOURTH[1] and wc.layouts(False) == (wc.FIRST, wc.SECOND)
    for (x, y) in second:  # amendment P1: with the fourth patch too, no new place within 3 units of an old one
        assert min(math.hypot(x - a, y - b) for (a, b) in first) >= 3.0
    assert wc.chance(first) == pytest.approx(4 * math.pi * 4 / 400) and wc.chance(wc.FIRST) == wc.CHANCE


def _validity_rows(n=12, intake=3e-4, pre=50, post=80):
    return [{"seed": s, "intake_before": intake, "coverage_pre5": pre + s % 3, "coverage_post5": post + s % 5} for s in range(1, n + 1)]


def test_validity_v1_memory_needed_and_v2_the_move_surprises() -> None:
    v = wc.validity(_validity_rows(intake=3e-4), _validity_rows(intake=2e-4))
    assert v["V1_memory_needed"] and v["V1_ratio"] == pytest.approx(1.5) and v["V2_move_surprises"]
    assert not wc.validity(_validity_rows(intake=3e-4), _validity_rows(intake=2.5e-4))["V1_memory_needed"]  # 1.2 < 1.25
    assert not wc.validity(_validity_rows(post=50), _validity_rows(intake=1e-4))["V2_move_surprises"]  # no more ground covered
    assert wc.validity(_validity_rows(), _validity_rows(intake=0.0))["V1_ratio"] == math.inf


def test_the_feasibility_rule_and_the_thirteen_part_verdict() -> None:
    rows = [{"seed": s, "meals_pre_move": m, "survived": True} for s, m in zip((2001, 2002, 2003, 2004), (5, 6, 7, 6))]
    rule = wc.design_rule(rows)
    assert rule["passes"] and rule["mean"] == 6 and rule["meals_pre_move"] == [5, 6, 7, 6]
    assert not wc.design_rule([dict(r, meals_pre_move=5) for r in rows])["passes"]
    parts = wc.smell_parts()
    spark = {"spark": True, "efficiency_before": 1.0, "efficiency_after": 1.0}
    scores = {"whole": spark, "whole_nomemory": spark, **{f"base+{p}": dict(spark, spark=False) for p in parts}}
    broken = list(parts)[:7]
    scores.update({f"whole-{p}": dict(spark, spark=p not in broken) for p in parts})
    v = wc.verdict(scores, parts, wc.SMELL_BREAKS_MIN)
    assert v["3_most_removals_break_it"] and v["removals_that_break_it"] == broken
    scores[f"whole-{broken[0]}"]["spark"] = True  # six of thirteen: not half
    assert not wc.verdict(scores, parts, wc.SMELL_BREAKS_MIN)["3_most_removals_break_it"]


def test_the_smell_run_waits_for_the_feasibility_rule(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(wc, "FOURTH_PATCH", None)
    with pytest.raises(SystemExit):
        wc.main(["--phase", "smell", "--workers", "1", "--out", str(tmp_path)])


def test_quick_design_and_smell_runs(tmp_path) -> None:
    design = wc.main(["--phase", "design", "--quick", "--workers", "1", "--out", str(tmp_path / "design")])
    assert list(design["configs"]) == ["whole"] and design["kind"] == "hidden" and "rule" in design and "scores" not in design
    row = (tmp_path / "design" / "runs.csv").read_text().splitlines()
    assert row[0] == ",".join(wc.DESIGN_COLUMNS) and len(row) == 2
    assert int(row[1].split(",")[3]) <= 600  # stopped at the move
    smell = wc.main(["--phase", "smell", "--quick", "--workers", "1", "--out", str(tmp_path / "smell")])
    assert len(smell["scores"]) == 29 and set(smell["validity"]) >= {"V1_memory_needed", "V2_move_surprises"}
    assert (tmp_path / "smell" / "runs.csv").read_text().splitlines()[0] == ",".join(wc.SMELL_COLUMNS)
