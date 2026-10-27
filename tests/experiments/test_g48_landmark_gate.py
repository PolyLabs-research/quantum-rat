"""The gate with distal cues (docs/prereg/g48_landmark_gate.md): the smoke run writes its tables and refuses the committed ones."""

from __future__ import annotations

import csv

import pytest

from experiments import g48_landmark_gate as g
from experiments import rq4a_gate as rg


def test_the_design() -> None:
    assert len(g.CONDITIONS) == 8 and g.CONDITIONS["L_carry_on"] == {"layout": "L", "start_estimate": "carry", "landmarks": True, "lateral_odometry": True}
    assert not set(g.QUICK_SEEDS) & set(g.PHASES["confirmatory"]["seeds"])
    assert set(g.PHASES["confirmatory"]["seeds"]) == set(range(185, 215))
    cfg = rg.gate_config("sr", "per_feature", landmarks=True)
    assert cfg.sensors.landmark_sensing and cfg.spatial.landmark_gain == rg.LANDMARK_GAIN
    assert all(abs(c.x) > 10 or abs(c.y) > 10 for c in rg.CUES)  # outside the arena


def test_quick_run_writes_its_tables_and_refuses_the_committed_directory(tmp_path) -> None:
    g.main(["--quick", "--workers", "1", "--out", str(tmp_path)])
    rows = list(csv.DictReader((tmp_path / "by_start_group.csv").open()))
    assert len(rows) == len(g.CONDITIONS) * 3 * 2 * len(g.QUICK_SEEDS) * len(g.GROUPS)
    assert all(float(r["estimate_error"]) >= 0.0 for r in rows)
    with pytest.raises(SystemExit):
        g.main(["--quick", "--workers", "1", "--phase", "confirmatory"])
