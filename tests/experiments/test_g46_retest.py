"""The retest after the audit (docs/prereg/g46_retest.md): the smoke run writes its tables and refuses the committed ones."""

from __future__ import annotations

import csv
import json

import pytest

from experiments import g46_retest as g


def test_the_registration() -> None:
    assert g.FOOD_SEEDS == tuple(range(17, 47)) and g.GATE_SEEDS == tuple(range(125, 155))
    assert not set(g.QUICK_FOOD_SEEDS) & set(g.FOOD_SEEDS) and not set(g.QUICK_GATE_SEEDS) & set(g.GATE_SEEDS)
    assert g.food_overrides("research", "pre_g46") == g.LEAKS and g.food_overrides("research", "g46") == {}
    assert g.food_overrides("legacy", "g46") == {"sensors.noise": 0.03, **g.FIXED}
    assert g.GATE_CONDITIONS["embodied"] == {"start_estimate": "carry", "estimate": "integrated"}


def test_quick_run_writes_its_tables_and_refuses_the_committed_directory(tmp_path) -> None:
    g.main(["--quick", "--workers", "1", "--out", str(tmp_path)])
    rows = list(csv.DictReader((tmp_path / "hidden_food" / "per_seed.csv").open()))
    assert len(rows) == len(g.QUICK_FOOD_SEEDS) * sum(len(g.FOOD_CONDITIONS[p]) * len(g.FOOD_ARMS[p]) for p in g.FOOD_CONDITIONS)
    for c in g.GATE_CONDITIONS:
        assert (tmp_path / "gate" / c / "gate_effects.csv").exists()
    assert json.loads((tmp_path / "summary.json").read_text())["full_evaluation"] is False
    with pytest.raises(SystemExit):
        g.main(["--quick", "--workers", "1"])
