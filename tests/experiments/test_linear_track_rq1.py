"""The RQ1 protocol runner and the dose-response script (experiments/linear_track_rq1.py,
experiments/linear_track_dose_response.py; docs/prereg/rq1_track_tabular.md).

Quick runs only (blocks of two laps, two seeds): they pin the protocol's shape, the pause table, the
preregistered test table's rows and verdict vocabulary, the files and their columns, and the refusal of
the committed directory. The numbers of a quick run mean nothing; the evaluation is reported in
docs/m2a_linear_track.md and decisions entry G28.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path

import pytest

from brain.systems.replay_events import RULE_NONE, TRIGGER_PRE_RUN, TRIGGER_REWARD
from experiments import linear_track_dose_response as ld
from experiments import linear_track_replay as lt
from experiments import linear_track_rq1 as rq


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_the_protocol_is_the_preregistered_one() -> None:
    cfg = rq.protocol_config("thresholded")
    assert cfg.laps == 80 and cfg.blocks() == ((20, 1.0, 1.0), (20, 4.0, 1.0), (20, 1.0, 1.0), (20, 0.25, 1.0))
    assert cfg.pre_run_pause and cfg.budget_mode == "thresholded" and cfg.threshold == rq.THRESHOLD == 0.0035 and cfg.backup_cap == 100
    fixed = rq.protocol_config("fixed")
    assert fixed.budget_mode == "fixed" and fixed.backups_per_trigger == 20 and fixed.lap_cap == 2000
    # Everything else is the fixed evaluation's.
    base = lt.TrackConfig().to_dict()
    changed = {k for k, v in fixed.to_dict().items() if v != base[k]}
    assert changed == {"laps", "reward_blocks", "pre_run_pause", "threshold"}  # theta is set for both modes; fixed mode ignores it
    quick = rq.protocol_config("fixed", quick=True)
    assert quick.laps == 8 and quick.blocks() == ((2, 1.0, 1.0), (2, 4.0, 1.0), (2, 1.0, 1.0), (2, 0.25, 1.0)) and quick.lap_cap == 2000
    with pytest.raises(ValueError):
        rq.protocol_config("poisson")
    assert rq.BLOCK_NAMES == ("baseline", "increase_x4", "washout", "decrease_x0.25")


@pytest.fixture(scope="module")
def quick_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("rq1")
    res = rq.main(["--quick", "--seeds", "2", "--workers", "2", "--write-events", "--out", str(out)])
    return out, res


def test_quick_run_writes_the_pause_table_with_two_pauses_per_lap(quick_run) -> None:
    out, res = quick_run
    assert {p.name for p in out.iterdir()} == set(rq.OUTPUT_FILES) | {rq.EVENTS_FILE}
    pauses = rq.read_csv_gz(out / "rq1_pauses.csv.gz")
    assert list(pauses[0]) == list(rq.PAUSE_COLUMNS)
    # Every lap has a pre-run pause row and, when rewarded, a reward pause row, in both modes for all four conditions.
    for mode in ("fixed", "thresholded"):
        for c in lt.CONDITIONS:
            rows = [p for p in pauses if p["mode"] == mode and p["condition"] == c]
            laps = {int(p["lap"]) for p in rows}
            assert laps == set(range(1, 9))
            pre = [p for p in rows if p["trigger"] == TRIGGER_PRE_RUN]
            assert len(pre) == 2 * 8  # two seeds, eight laps
            assert all(p["end"] in ("east", "west") for p in rows)
            # The pause ends: a lap toward the east starts at the west end and ends at the east end.
            for p in rows:
                lap_rows = [q for q in rows if q["seed"] == p["seed"] and q["lap"] == p["lap"]]
                ends = {q["trigger"]: q["end"] for q in lap_rows}
                if TRIGGER_REWARD in ends:
                    assert ends[TRIGGER_REWARD] != ends[TRIGGER_PRE_RUN]
            if c == RULE_NONE:
                assert all(int(p["n_backups"]) == 0 and int(p["n_events"]) == 0 for p in rows)
            elif mode == "fixed":
                rewarded = [p for p in rows if p["trigger"] == TRIGGER_REWARD]
                assert all(int(p["n_backups"]) == 20 for p in rewarded)
                assert all(int(p["n_backups"]) in (0, 20) for p in pre)  # 0 only at the very first pause
            else:
                assert all(0 <= int(p["n_backups"]) <= 100 for p in rows)
            assert all(int(p["n_reverse"]) + int(p["n_forward"]) + int(p["n_neither"]) == int(p["n_events"]) for p in rows)
    blocks = _read(out / "rq1_seed_blocks.csv")
    assert list(blocks[0]) == list(rq.SEED_BLOCK_COLUMNS)
    assert {r["block_name"] for r in blocks} == set(rq.BLOCK_NAMES)
    events = [json.loads(l) for l in gzip.open(out / rq.EVENTS_FILE, "rt")]
    assert events and all("agent_cell" in e and e["trigger"] in (TRIGGER_REWARD, TRIGGER_PRE_RUN) and e["mode"] in ("fixed", "thresholded") for e in events)
    assert all(e["agent_cell"] in (0, 39) for e in events)
    assert res["guard"] and all(v["distinct"] == 2 for v in res["guard"].values())


def test_quick_run_writes_the_preregistered_test_table(quick_run) -> None:
    out, res = quick_run
    tests = _read(out / "rq1_tests.csv")
    assert list(tests[0]) == list(rq.TEST_COLUMNS)
    names = {t["test"] for t in tests}
    assert names == {"a_direction", "d_remote", "b_rate_increase", "b_rate_decrease", "b_control_end", "b_forward_unchanged", "c_familiarity"}
    assert {t["condition"] for t in tests} == set(lt.CONDITIONS) - {RULE_NONE}
    assert all(t["mode"] in ("fixed", "thresholded") for t in tests)
    verdicts = {t["verdict"] for t in tests}
    allowed = {"passes", "fails", "undefined (no events)", "undefined", "equivalent (TOST)", "not shown equivalent (TOST)",
               "degenerate (every value identical)", "estimate above, interval not"}
    assert verdicts <= allowed, verdicts - allowed
    # The same rows for every replay condition, so the table reads across.
    per_condition = {c: sorted((t["test"], t["mode"], t["statistic"]) for t in tests if t["condition"] == c) for c in set(t["condition"] for t in tests)}
    assert len({tuple(v) for v in per_condition.values()}) == 1
    assert len(tests) == 3 * (2 + 2 + 3 * 4 + 1 + 2)  # (a) 2, (d) 2, (b) 3 metrics x 4 comparisons, forward 1, (c) 2
    adaptation = _read(out / "rq1_adaptation.csv")
    assert list(adaptation[0]) == list(rq.ADAPTATION_COLUMNS)
    assert {(r["block"], r["lap_in_block"]) for r in adaptation} == {(str(b), str(k)) for b in range(4) for k in (1, 2)}
    m = json.loads((out / "rq1_manifest.json").read_text())
    assert m["protocol"] == "linear_track_rq1" and m["prereg"] == "docs/prereg/rq1_track_tabular.md"
    assert m["modes"] == ["fixed", "thresholded"] and m["threshold"] == 0.0035 and m["backup_cap"] == 100
    assert m["blocks"] == [[2, 1.0, 1.0], [2, 4.0, 1.0], [2, 1.0, 1.0], [2, 0.25, 1.0]] and m["quick"] is True
    assert m["configs"]["thresholded"]["budget_mode"] == "thresholded" and m["full_evaluation"] is False


def test_quick_run_is_byte_identical_and_refuses_the_committed_directory(quick_run, tmp_path, monkeypatch) -> None:
    out, _ = quick_run
    again = tmp_path / "again"
    rq.main(["--quick", "--seeds", "2", "--workers", "1", "--write-events", "--out", str(again)])
    for name in (*rq.OUTPUT_FILES, rq.EVENTS_FILE):
        if name.endswith("manifest.json"):
            continue
        assert (out / name).read_bytes() == (again / name).read_bytes(), name
    # Without the flag the events file is not written.
    plain = tmp_path / "plain"
    rq.main(["--quick", "--seeds", "1", "--workers", "1", "--out", str(plain)])
    assert {p.name for p in plain.iterdir()} == set(rq.OUTPUT_FILES)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        rq.main(["--quick", "--seeds", "2"])
    with pytest.raises(SystemExit):
        rq.main(["--modes", "poisson", "--seeds", "1", "--out", str(tmp_path / "x")])
    assert not (tmp_path / "docs").exists()


def test_dose_response_quick_run_writes_its_tables_and_the_base_dose_is_the_fixed_evaluation(tmp_path, monkeypatch) -> None:
    out = tmp_path / "dose"
    res = ld.main(["--quick", "--seeds", "2", "--doses", "5,20", "--workers", "2", "--out", str(out)])
    assert {p.name for p in out.iterdir()} == set(ld.OUTPUT_FILES)
    effects = _read(out / "dose_response_effects.csv")
    assert list(effects[0]) == list(ld.EFFECT_COLUMNS)
    assert {r["dose"] for r in effects} == {"5", "20"} and {r["a"] for r in effects} == {RULE_NONE}
    assert len(effects) == 2 * 3  # per dose, each replay condition against none
    slopes = _read(out / "dose_response_slopes.csv")
    assert list(slopes[0]) == list(ld.SLOPE_COLUMNS) and [r["condition"] for r in slopes] == list(lt.CONDITIONS[1:])
    assert all(json.loads(r["doses"]) == [5, 20] and len(json.loads(r["mean_total_steps_by_dose"])) == 2 for r in slopes)
    m = json.loads((out / "dose_response_manifest.json").read_text())
    assert m["protocol"] == "linear_track_dose_response" and m["doses"] == [5, 20] and m["quick"] is True
    assert ld.DOSES == (5, 10, 20, 40) and ld.BASE == lt.TrackConfig()
    # The slope helper and the degenerate case.
    assert ld._slope([0.0, 1.0, 2.0], [1.0, 3.0, 5.0]) == pytest.approx(2.0)
    assert math.isnan(ld._slope([1.0, 1.0], [1.0, 2.0]))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        ld.main(["--quick", "--seeds", "2"])
    with pytest.raises(SystemExit):
        ld.main(["--doses", "5", "--seeds", "1", "--out", str(tmp_path / "x")])
    assert len(res["slopes"]) == 3
