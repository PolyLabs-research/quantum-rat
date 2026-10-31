"""The whole, part 2 (docs/prereg/whole_change.md): the layouts, the windows, the spark's scoring, a quick run."""

from __future__ import annotations

import math

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
