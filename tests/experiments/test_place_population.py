"""The place-population experiment (experiments/place_population.py; docs/prereg/m2b_place_population.md).

Quick runs only (300 ticks, two seeds): the populations, the files and their columns, the preregistered test rows,
the same walk across estimates, identical tables across worker counts (all but the wall-clock throughput), and the
refusal of the committed directory. The numbers of a quick run mean nothing; the evaluation is in G34.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from core.config import EngineConfig
from experiments import place_population as pp


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def quick(tmp_path_factory):
    out = tmp_path_factory.mktemp("place")
    return out, pp.main(["--quick", "--seeds", "2", "--workers", "2", "--out", str(out)])


def test_the_configs_are_step_ones_with_the_population(quick) -> None:
    assert pp.POPULATIONS == ("reference", "integrated", "m2b") and pp.ESTIMATES == {"integrated": "integrated", "m2b": "oracle_reset"}
    for name in pp.ESTIMATES:
        diff = {d[0] for d in EngineConfig.research().diff(pp.place_config(name))}
        assert "place.enabled" in diff and "sensors.heading_oracle" in diff
        assert ("spatial.wall_reset" in diff) == (name == "m2b")


def test_quick_run_writes_its_tables(quick) -> None:
    out, res = quick
    assert {p.name for p in out.iterdir()} == set(pp.OUTPUT_FILES)
    rows = _read(out / "place_per_seed.csv")
    assert list(rows[0]) == list(pp.PER_SEED_COLUMNS) and len(rows) == 3 * 2
    assert res["same_walk"] and res["guard"] == 2
    ref = [r for r in rows if r["population"] == "reference"]
    assert all(float(r["correlation_mean"]) == pytest.approx(1.0) and float(r["centroid_shift_mean"]) == pytest.approx(0.0, abs=1e-12) for r in ref)
    assert all(r["decode_vs_estimate_max"] == "nan" for r in ref)
    assert all(float(r["decode_vs_estimate_max"]) < 1e-6 and r["decode_undefined_ticks"] == "0" for r in rows if r["population"] != "reference")
    t2 = [e for e in _read(out / "place_effects.csv") if e["test"] == "t2_decoder"][0]
    assert t2["note"] == "undefined decodes: integrated 0, m2b 0"
    effects = _read(out / "place_effects.csv")
    assert list(effects[0]) == list(pp.EFFECT_COLUMNS)
    assert [e["test"] for e in effects[:4]] == ["t1_throughput", "t2_decoder", "t3_decoding_drop_at_contact", "t4_map_fidelity"]
    assert {e["test"] for e in effects[4:]} == {"reported"}
    cells = _read(out / "place_cells.csv")
    assert list(cells[0]) == list(pp.CELL_COLUMNS) and len(cells) == 3 * 400
    tp = _read(out / "place_throughput.csv")
    assert list(tp[0]) == list(pp.THROUGHPUT_COLUMNS) and {r["population"] for r in tp} == {"on", "off"}
    m = json.loads((out / "place_manifest.json").read_text())
    assert m["protocol"] == "place_population" and m["prereg"] == "docs/prereg/m2b_place_population.md" and m["quick"] is True
    assert m["population"]["n"] == 400 and m["guard"]["same_walk_across_estimates"] is True


def test_quick_run_is_identical_across_workers_and_refuses_the_committed_directory(quick, tmp_path, monkeypatch) -> None:
    out, _ = quick
    again = tmp_path / "again"
    pp.main(["--quick", "--seeds", "2", "--workers", "1", "--out", str(again)])
    for name in ("place_per_seed.csv", "place_cells.csv"):
        assert (out / name).read_bytes() == (again / name).read_bytes(), name
    a, b = _read(out / "place_effects.csv"), _read(again / "place_effects.csv")
    assert a[1:] == b[1:]  # every row but the wall-clock throughput
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        pp.main(["--quick", "--seeds", "2"])
    assert not (tmp_path / "docs").exists()
