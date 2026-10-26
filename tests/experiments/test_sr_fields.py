"""The SR-fields experiment (experiments/sr_fields.py; docs/prereg/m2b_sr_fields.md).

Quick runs only (6 laps, 600 open-field ticks, two seeds): the protocol's placement leaves the egomotion alone, the
files and columns, the preregistered test rows, distinct walks per seed, identical tables across worker counts, and
the refusal of the committed directory. The numbers of a quick run mean nothing; the evaluation is in G35.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from brain.contracts import Action
from core.engine import Engine
from experiments import sr_fields as sf


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_the_track_protocol_places_the_body_without_moving_the_estimate_by_it() -> None:
    eng = Engine(seed=1, config=sf.m2b_config(sf.TRACK_BOUNDS))
    assert eng.world.bounds == (10.0, 0.5) and eng.place.size == 20
    eng.run(3, reset=True)
    sf._place(eng, -10.0, 0.0, 0.0, anchor=True)
    st = eng.spatial.state
    assert (st.grid_x, st.grid_y, st.hd_angle) == (-10.0, 0.0, 0.0)
    eng.last_action = Action(name="FORWARD", thrust=0.8, turn=0.0)
    td = eng.run(1)[0]
    assert eng.agent.pos == pytest.approx((-9.2, 0.0))
    assert abs(td.obs_forward_delta - 0.8) < 0.8 * 0.3  # the move, with odometry noise; the placement is not in it
    with pytest.raises(ValueError):
        sf.run_track("loop", 1, 1)


@pytest.fixture(scope="module")
def quick(tmp_path_factory):
    out = tmp_path_factory.mktemp("sr")
    return out, sf.main(["--quick", "--seeds", "2", "--workers", "2", "--out", str(out)])


def test_quick_run_writes_its_tables(quick) -> None:
    out, res = quick
    assert {p.name for p in out.iterdir()} == set(sf.OUTPUT_FILES)
    track = _read(out / "sr_track_per_seed.csv")
    assert list(track[0]) == list(sf.TRACK_PER_SEED_COLUMNS) and len(track) == 2 * 2
    assert all(r["laps"] == "6" and r["cells"] == "14" for r in track)
    one = [float(r["shift_mean"]) for r in track if r["mode"] == "one_way"]
    two = [float(r["shift_mean"]) for r in track if r["mode"] == "two_way"]
    assert all(s < 0 for s in one) and all(abs(s) < abs(o) for s, o in zip(two, one))
    assert len(_read(out / "sr_track_cells.csv")) == 2 * 20
    open_rows = _read(out / "sr_open_per_seed.csv")
    assert list(open_rows[0]) == list(sf.OPEN_PER_SEED_COLUMNS) and len(open_rows) == 2
    assert all(r["wall_cells"] == "72" and r["interior_cells"] == "196" and r["ticks"] == "600" for r in open_rows)
    cells = _read(out / "sr_open_cells.csv")
    assert len(cells) == 400 and {c["kind"] for c in cells} == {"wall", "interior", "other"}
    effects = _read(out / "sr_effects.csv")
    assert [e["test"] for e in effects[:3]] == ["t1_backward_shift", "t2_direction_specific", "t3_wall_elongation"]
    assert {e["test"] for e in effects[3:]} == {"reported"}
    assert res["guards"] == {"track/one_way": 2, "track/two_way": 2, "open_field": 2}
    m = json.loads((out / "sr_manifest.json").read_text())
    assert m["protocol"] == "sr_fields" and m["prereg"] == "docs/prereg/m2b_sr_fields.md" and m["learning_rate"] == 0.1 and m["discount"] == 0.95
    assert m["track"]["laps"] == 6 and m["open_field"]["ticks"] == 600 and m["quick"] is True


def test_quick_run_is_identical_across_workers_and_refuses_the_committed_directory(quick, tmp_path, monkeypatch) -> None:
    out, _ = quick
    again = tmp_path / "again"
    sf.main(["--quick", "--seeds", "2", "--workers", "1", "--out", str(again)])
    for name in sf.OUTPUT_FILES:
        if not name.endswith(".json"):
            assert (out / name).read_bytes() == (again / name).read_bytes(), name
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        sf.main(["--quick", "--seeds", "2"])
    assert not (tmp_path / "docs").exists()
