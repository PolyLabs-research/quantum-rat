"""The corrected-estimate experiment (experiments/estimate_correction.py; docs/prereg/m2b_estimate.md).

Quick runs only (300 ticks, two seeds): the cells and their configs, the files and their columns, the preregistered
test rows, the same body walk in every cell of a seed, byte-identical tables across worker counts, and the refusal
of the committed directory. The numbers of a quick run mean nothing; the evaluation is in G33.
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import pytest

from core.config import EngineConfig
from experiments import estimate_correction as ec


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_the_cells_are_the_preregistered_ones() -> None:
    assert list(ec.CONDITIONS) == ["integrated", "integrated_reset", "oracle", "oracle_reset"]
    assert ec.ORACLE_NOISE == 0.05 and ec.SENSITIVITY_NOISES == (0.0, 0.02, 0.1, 0.2) and ec.TICKS == 3000
    assert [r.label for r in ec.runs()] == ["integrated", "integrated_reset", "oracle", "oracle_reset", "oracle_reset@0",
                                            "oracle_reset@0.02", "oracle_reset@0.1", "oracle_reset@0.2"]
    research = EngineConfig.research()
    for condition, spec in ec.CONDITIONS.items():
        cfg = ec.engine_config(condition)
        diff = {d[0] for d in research.diff(cfg)}
        expected = {"sensors.heading_oracle", "sensors.heading_oracle_noise", "sensors.wall_contact_sensing"}
        if spec["heading_source"] == "oracle":
            expected.add("spatial.heading_source")
        if spec["wall_reset"]:
            expected.add("spatial.wall_reset")
        assert diff == expected, condition
    with pytest.raises(ValueError):
        ec.engine_config("compass")


@pytest.fixture(scope="module")
def quick(tmp_path_factory):
    out = tmp_path_factory.mktemp("est")
    return out, ec.main(["--quick", "--seeds", "2", "--workers", "2", "--out", str(out)])


def test_quick_run_writes_its_tables(quick) -> None:
    out, res = quick
    assert {p.name for p in out.iterdir()} == set(ec.OUTPUT_FILES)
    rows = _read(out / "estimate_per_seed.csv")
    assert list(rows[0]) == list(ec.PER_SEED_COLUMNS) and len(rows) == 8 * 2
    assert all(r["ticks"] == "300" for r in rows)
    # The same body walk in every cell of a seed, and two distinct walks across the two seeds.
    assert res["same_walk"] and res["guard"] == 2
    for seed in ("1", "2"):
        assert len({r["walk_digest"] for r in rows if r["seed"] == seed}) == 1
    # No reset, no reset writes; with a reset at the oracle, no wrong wall in 300 ticks.
    assert all(r["reset_writes"] == "0" and r["wrong_wall_share"] == "nan" for r in rows if not r["condition"].endswith("_reset"))
    assert all(float(r["wrong_wall_share"]) == 0.0 for r in rows if r["label"] == "oracle_reset")
    curve = _read(out / "estimate_curve.csv")
    assert list(curve[0]) == list(ec.CURVE_COLUMNS) and len(curve) == 8 * (300 // 25)
    effects = _read(out / "estimate_effects.csv")
    assert list(effects[0]) == list(ec.EFFECT_COLUMNS)
    tests = {e["test"] for e in effects}
    assert {"t1_level", "t2_primary_vs_integrated", "t3_drop_at_contact", "t4_wrong_wall"} <= tests
    assert {e["test"] for e in effects if e["verdict"] in ("passes", "fails")} == {"t1_level", "t2_primary_vs_integrated", "t3_drop_at_contact", "t4_wrong_wall"}
    assert len([e for e in effects if e["test"] == "sensitivity"]) == 2 * 4
    contacts = list(csv.DictReader(gzip.open(out / "estimate_contacts.csv.gz", "rt", newline="")))
    assert contacts and list(contacts[0]) == list(ec.CONTACT_COLUMNS)
    # At a contact onset under a reset the normal error after the reset is 0 when the right wall is written.
    for c in contacts:
        if c["condition"] == "oracle_reset" and c["correct"] == "True":
            assert float(c["normal_error_after"]) < 1e-9
    m = json.loads((out / "estimate_manifest.json").read_text())
    assert m["protocol"] == "estimate_correction" and m["prereg"] == "docs/prereg/m2b_estimate.md" and m["quick"] is True
    assert m["guard"]["same_walk_across_cells"] is True and m["ticks"] == 300 and m["full_evaluation"] is False
    assert [c["label"] for c in m["cells"]] == [r.label for r in ec.runs()]


def test_quick_run_is_byte_identical_and_refuses_the_committed_directory(quick, tmp_path, monkeypatch) -> None:
    out, _ = quick
    again = tmp_path / "again"
    ec.main(["--quick", "--seeds", "2", "--workers", "1", "--out", str(again)])
    for name in ec.OUTPUT_FILES:
        if not name.endswith(".json"):
            assert (out / name).read_bytes() == (again / name).read_bytes(), name
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        ec.main(["--quick", "--seeds", "2"])
    with pytest.raises(SystemExit):
        ec.main(["--ticks", "10", "--out", str(tmp_path / "x")])
    assert not (tmp_path / "docs").exists()
