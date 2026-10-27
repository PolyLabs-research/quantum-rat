"""M3 step 2 Part 1 (docs/prereg/m3_step2.md): the smoke run writes its tables and refuses the committed ones."""

from __future__ import annotations

import csv

import pytest

from experiments import m3_reachable as m


def test_the_design() -> None:
    assert m.SEEDS == tuple(range(215, 245)) and not set(m.QUICK_SEEDS) & set(m.SEEDS)
    assert m._overrides("off") == {"sensors.lateral_odometry": True}
    assert m._overrides("on")["value_memory.reachable_probes"] and m._overrides("on")["sensors.free_space_sensing"]


def test_quick_run_writes_its_tables_and_refuses_the_committed_directory(tmp_path) -> None:
    m.main(["--quick", "--workers", "1", "--out", str(tmp_path)])
    groups = list(csv.DictReader((tmp_path / "gate" / "by_start_group.csv").open()))
    assert len(groups) == len(m.GATE) * len(m.PROBES) * 3 * 2 * len(m.QUICK_SEEDS) * len(m.GROUPS)
    reflex = list(csv.DictReader((tmp_path / "reflex.csv").open()))
    on = {(r["world"], r["seed"]): r for r in reflex if r["probes"] == "on"}
    for r in reflex:  # the reflex alone does not read value: identical with and without the probes
        if r["probes"] == "off":
            assert r == {**on[(r["world"], r["seed"])], "probes": "off"}
    with pytest.raises(SystemExit):
        m.main(["--quick", "--workers", "1"])
