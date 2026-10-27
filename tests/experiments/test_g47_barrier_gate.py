"""The gate with barriers (docs/prereg/g47_barrier_gate.md): the smoke run writes its tables and refuses the committed ones."""

from __future__ import annotations

import csv

import pytest

from experiments import g47_barrier_gate as g


def test_the_design() -> None:
    assert set(g.CONDITIONS) == {"open_anchor", "open_carry", "L_anchor", "L_carry"}
    assert g.GROUPS == {"blocked": (0, 2), "direct": (1, 3)}
    assert not set(g.QUICK_SEEDS) & set(g.PHASES["confirmatory"]["seeds"])
    assert set(g.PHASES["pilot"]["seeds"]) <= set(range(31, 61))  # spent (the confirmatory gate's)


def test_quick_run_writes_its_tables_and_refuses_the_committed_directory(tmp_path) -> None:
    g.main(["--quick", "--workers", "1", "--out", str(tmp_path)])
    groups = list(csv.DictReader((tmp_path / "by_start_group.csv").open()))
    assert len(groups) == len(g.CONDITIONS) * 3 * 2 * len(g.QUICK_SEEDS) * 2
    for c in g.CONDITIONS:
        assert (tmp_path / c / "gate_effects.csv").exists()
    with pytest.raises(SystemExit):
        g.main(["--quick", "--workers", "1", "--phase", "confirmatory"])
