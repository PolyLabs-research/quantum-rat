"""The RQ1 protocol runner and the dose-response script (experiments/linear_track_rq1.py,
experiments/linear_track_dose_response.py; docs/prereg/rq1_track_tabular.md, rq1_track_gain_need.md, rq1_track_step4.md,
rq1_track_mattar_daw.md).

Quick runs only (blocks of two laps, two seeds): they pin the protocol's shape in its four versions, the pause
table, the preregistered test table's rows and verdict vocabulary, the files and their columns, the pilot, and the
refusal of the committed directories. The numbers of a quick run mean nothing; the evaluations are reported in
docs/m2a_linear_track.md and decisions entries G28 to G31.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import re
from pathlib import Path

import pytest

from brain.systems.replay_events import RULE_NONE, TRIGGER_PRE_RUN, TRIGGER_REWARD
from experiments import linear_track_dose_response as ld
from experiments import linear_track_replay as lt
from experiments import linear_track_rq1 as rq


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_the_protocol_is_the_preregistered_one_in_every_version() -> None:
    # Step 2 (G28): one theta, the trajectory rule's "next" priority, four blocks in one session.
    cfg = rq.protocol_config("thresholded", version="step2")
    assert cfg.laps == 80 and cfg.blocks() == ((20, 1.0, 1.0), (20, 4.0, 1.0), (20, 1.0, 1.0), (20, 0.25, 1.0))
    assert cfg.pre_run_pause and cfg.budget_mode == "thresholded" and cfg.threshold == rq.THRESHOLD == 0.0035 and cfg.backup_cap == 100
    assert cfg.trajectory_priority == "next" and cfg.threshold_scale == "none"
    fixed = rq.protocol_config("fixed", version="step2")
    assert fixed.budget_mode == "fixed" and fixed.backups_per_trigger == 20 and fixed.lap_cap == 2000
    base = lt.TrackConfig().to_dict()
    changed = {k for k, v in fixed.to_dict().items() if v != base[k]}
    assert changed == {"laps", "reward_blocks", "pre_run_pause", "threshold"}  # theta is set for both modes; fixed mode ignores it
    # Step 3 (G29; docs/prereg/rq1_track_gain_need.md): theta per rule from the pilot, "remaining_max", the same blocks.
    step3 = rq.protocol_config("thresholded", version="step3", theta=rq.theta_for("gain_need", "step3"))
    assert step3.trajectory_priority == "remaining_max" and step3.threshold == pytest.approx(1.59024e-07) and step3.threshold_scale == "none"
    assert step3.blocks() == cfg.blocks()
    assert rq.theta_for("reverse_trajectory", "step3") == pytest.approx(0.137277)
    assert rq.theta_for("uniform", "step2") == 0.0035 and rq.theta_for("uniform", "step3", {"uniform": 0.5}) == 0.5
    assert set(rq.THRESHOLDS_STEP3) == set(rq.version_conditions("step3")) - {RULE_NONE} and all(v is not None for v in rq.THRESHOLDS_STEP3.values())
    # Step 4 (docs/prereg/rq1_track_step4.md): two sessions per seed, theta scaled by the value scale, the v learner.
    assert rq.SESSIONS["step4"] == rq.SESSIONS["step5"] == {
        "increase": ((20, 1.0, 1.0), (20, 4.0, 1.0)), "decrease": ((20, 1.0, 1.0), (20, 0.25, 1.0))}
    inc = rq.protocol_config("thresholded", version="step4", session="increase", theta=1.0)
    dec = rq.protocol_config("thresholded", version="step4", session="decrease", theta=1.0)
    assert inc.laps == dec.laps == 40 and inc.blocks() == ((20, 1.0, 1.0), (20, 4.0, 1.0)) and dec.blocks() == ((20, 1.0, 1.0), (20, 0.25, 1.0))
    assert inc.threshold_scale == "mean_abs_value" and inc.trajectory_priority == "remaining_max" and inc.pre_run_pause and inc.learner == "v"
    assert {k for k, v in inc.to_dict().items() if v != dec.to_dict()[k]} == {"reward_blocks"}
    with pytest.raises(ValueError):
        rq.protocol_config("fixed")  # steps 4 and 5 have two sessions: one must be named
    with pytest.raises(ValueError):
        rq.protocol_config("fixed", session="washout")
    with pytest.raises(ValueError):
        rq.protocol_config("fixed", version="step3", session="increase")
    assert rq.session_for("step3", None) == rq.FOUR_BLOCK and rq.session_for("step4", "decrease") == "decrease"
    assert set(rq.THRESHOLDS_STEP4) == set(rq.version_conditions("step4")) - {RULE_NONE} and all(v is not None for v in rq.THRESHOLDS_STEP4.values())
    assert rq.theta_for("need_only", "step4") == rq.THRESHOLDS_STEP4["need_only"]
    assert [rq.condition_is_value_scaled(c) for c in lt.ALL_CONDITIONS] == [False, True, True, True, True, True, False, True, True]
    # Step 5 (the default; docs/prereg/rq1_track_mattar_daw.md): step 4's protocol on the q learner, the floors and the Mattar & Daw rules.
    assert rq.DEFAULT_VERSION == "step5" and rq.version_conditions("step5") == (RULE_NONE, "uniform", "reverse_trajectory", "prioritised_td", "mattar_daw", "mattar_daw_1step")
    assert rq.version_conditions("step4") == rq.version_conditions("step3") == lt.CONDITIONS + lt.GAIN_NEED_CONDITIONS and rq.version_conditions("step2") == lt.CONDITIONS
    five = rq.protocol_config("thresholded", session="decrease", theta=rq.theta_for("mattar_daw", "step5"))
    assert five.learner == "q" and five.threshold_scale == "mean_abs_value" and five.blocks() == dec.blocks() and five.threshold == pytest.approx(3.90938e-05)
    assert {k for k, v in five.to_dict().items() if v != dec.to_dict()[k]} == {"learner", "threshold"}
    assert set(rq.THRESHOLDS_STEP5) == set(rq.version_conditions("step5")) - {RULE_NONE} and all(v is not None for v in rq.THRESHOLDS_STEP5.values())
    assert rq.LEARNERS_BY_VERSION == {"step2": "v", "step3": "v", "step4": "v", "step5": "q"}
    quick = rq.protocol_config("fixed", quick=True, session="increase")
    assert quick.laps == 4 and quick.blocks() == ((2, 1.0, 1.0), (2, 4.0, 1.0)) and quick.lap_cap == 2000
    with pytest.raises(ValueError):
        rq.protocol_config("poisson", session="increase")
    with pytest.raises(ValueError):
        rq.protocol_config("fixed", version="step9")
    assert rq.BLOCK_NAMES == ("baseline", "increase_x4", "washout", "decrease_x0.25")
    assert rq.SESSION_BLOCK_NAMES["decrease"] == ("baseline", "decrease_x0.25") and rq.cell_label("increase", 1) == "increase_block2"
    assert rq.cell_label(rq.FOUR_BLOCK, 3) == "block4"
    assert rq.DEFAULT_OUTS == {"step2": Path("docs/data/m2a/rq1"), "step3": Path("docs/data/m2a/rq1_step3"), "step4": Path("docs/data/m2a/rq1_step4"),
                               "step5": Path("docs/data/m2a/rq1_step5")}
    assert rq.PREREGS["step4"] == "docs/prereg/rq1_track_step4.md" and rq.PREREGS["step5"] == "docs/prereg/rq1_track_mattar_daw.md"


@pytest.fixture(scope="module")
def quick_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("rq1")
    res = rq.main(["--quick", "--seeds", "2", "--workers", "2", "--write-events", "--out", str(out)])
    return out, res


def test_quick_run_writes_the_pause_table_with_two_pauses_per_lap_in_both_sessions(quick_run) -> None:
    out, res = quick_run
    assert {p.name for p in out.iterdir()} == set(rq.OUTPUT_FILES) | {rq.EVENTS_FILE}
    pauses = rq.read_csv_gz(out / "rq1_pauses.csv.gz")
    assert list(pauses[0]) == list(rq.PAUSE_COLUMNS)
    conditions = rq.version_conditions("step5")
    assert {p["condition"] for p in pauses} == set(conditions) and {p["session"] for p in pauses} == {"increase", "decrease"}
    assert all(p["priority_before"] == "nan" and p["value_scale"] == "nan" for p in pauses if p["condition"] == RULE_NONE)
    for mode in ("fixed", "thresholded"):
        for session in ("increase", "decrease"):
            for c in conditions:
                rows = [p for p in pauses if p["mode"] == mode and p["session"] == session and p["condition"] == c]
                assert {int(p["lap"]) for p in rows} == set(range(1, 5))
                pre = [p for p in rows if p["trigger"] == TRIGGER_PRE_RUN]
                assert len(pre) == 2 * 4  # two seeds, four laps
                assert all(p["end"] in ("east", "west") for p in rows)
                for p in rows:  # a lap toward the east starts at the west end and ends at the east end
                    ends = {q["trigger"]: q["end"] for q in rows if q["seed"] == p["seed"] and q["lap"] == p["lap"]}
                    if TRIGGER_REWARD in ends:
                        assert ends[TRIGGER_REWARD] != ends[TRIGGER_PRE_RUN]
                if c == RULE_NONE:
                    assert all(int(p["n_backups"]) == 0 and int(p["n_events"]) == 0 for p in rows)
                elif mode == "fixed":
                    assert all(int(p["n_backups"]) == 20 for p in rows if p["trigger"] == TRIGGER_REWARD)
                    assert all(int(p["n_backups"]) in (0, 20) for p in pre)  # 0 only at the very first pause
                    assert all(float(p["value_scale"]) > 0.0 for p in rows if int(p["n_backups"]) > 0)
                else:
                    assert all(0 <= int(p["n_backups"]) <= 100 for p in rows)
                assert all(int(p["n_reverse"]) + int(p["n_forward"]) + int(p["n_neither"]) == int(p["n_events"]) for p in rows)
    # The two sessions run from the same seed: their baseline blocks are the same pauses, and they part at the change.
    strip = lambda p: {k: v for k, v in p.items() if k != "session"}  # noqa: E731
    for mode in ("fixed", "thresholded"):
        for c in conditions:
            inc = [strip(p) for p in pauses if p["mode"] == mode and p["session"] == "increase" and p["condition"] == c and p["block"] == "0"]
            dec = [strip(p) for p in pauses if p["mode"] == mode and p["session"] == "decrease" and p["condition"] == c and p["block"] == "0"]
            assert inc == dec and inc
    changed = [p for p in pauses if p["block"] == "1" and p["condition"] == "reverse_trajectory" and p["mode"] == "thresholded"]
    assert {p["session"]: p["block_name"] for p in changed} == {"increase": "increase_x4", "decrease": "decrease_x0.25"}
    blocks = _read(out / "rq1_seed_blocks.csv")
    assert list(blocks[0]) == list(rq.SEED_BLOCK_COLUMNS)
    assert {(r["session"], r["block_name"]) for r in blocks} == {("increase", "baseline"), ("increase", "increase_x4"), ("decrease", "baseline"), ("decrease", "decrease_x0.25")}
    events = [json.loads(l) for l in gzip.open(out / rq.EVENTS_FILE, "rt")]
    assert events and all("agent_cell" in e and e["trigger"] in (TRIGGER_REWARD, TRIGGER_PRE_RUN) and e["mode"] in ("fixed", "thresholded")
                          and e["session"] in ("increase", "decrease") for e in events)
    assert all(e["agent_cell"] in (0, 39) for e in events)
    assert res["guard"] and all(v["distinct"] == 2 for v in res["guard"].values()) and len(res["guard"]) == 2 * 2 * 6
    # The first lap is identical across the six conditions at every seed (Q = 0 gives the same softmax).
    first = {(r.condition, r.seed): r.first_lap_actions for r in res["runs_by_key"][("fixed", "increase")]}
    assert all(first[(c, s)] == first[(RULE_NONE, s)] for c in conditions for s in (1, 2))


def test_quick_run_writes_the_preregistered_test_table(quick_run) -> None:
    out, res = quick_run
    tests = _read(out / "rq1_tests.csv")
    assert list(tests[0]) == list(rq.TEST_COLUMNS)
    assert {t["test"] for t in tests} == {"a_direction", "a_direction_after_change", "d_remote", "b_rate_increase", "b_rate_decrease", "b_control_end",
                                          "b_rate_increase_vs_control", "b_rate_decrease_vs_control", "b_forward_unchanged", "c_familiarity", "c_after_change"}
    assert {t["condition"] for t in tests} == set(rq.version_conditions("step5")) - {RULE_NONE}
    assert all(t["mode"] in ("fixed", "thresholded") for t in tests)
    verdicts = {t["verdict"] for t in tests}
    allowed = {"passes", "fails", "undefined (no events)", "undefined", "equivalent (TOST)", "not shown equivalent (TOST)",
               "degenerate (every value identical)", "degenerate (baseline rate 0: relative TOST undefined)",
               "estimate above, interval not"}
    reaches = re.compile(r"^reaches 0 at \d+ of \d+ seeds$")  # the (c) first-lap-at-zero rows
    assert all(v in allowed or reaches.match(v) for v in verdicts), {v for v in verdicts if v not in allowed and not reaches.match(v)}
    assert all(reaches.match(t["verdict"]) for t in tests if t["statistic"].startswith("first_lap_with_zero_backups"))
    # The same rows for every replay condition, so the table reads across.
    per_condition = {c: sorted((t["test"], t["mode"], t["statistic"]) for t in tests if t["condition"] == c) for c in set(t["condition"] for t in tests)}
    assert len({tuple(v) for v in per_condition.values()}) == 1
    # (a) 2 + 2 after the change, (d) 2, (b) 3 metrics x 2 sessions x (2 ends + the east - west row), forward 2, (c) 3 cells x 3.
    assert len(tests) == 5 * (2 + 2 + 2 + 3 * 2 * 3 + 2 + 3 * 3)
    stats = {t["statistic"] for t in tests}
    assert {"reverse_share_reward_pauses_baseline", "forward_share_pre_run_pauses_baseline", "backups_per_stop_east_increase_block2_minus_block1",
            "events_per_stop_east_decrease_block2_minus_block1", "reverse_per_stop_west_decrease_block2_minus_block1",
            "forward_per_stop_east_increase_block2_minus_block1", "slope_of_n_backups_vs_lap_increase_block1",
            "slope_of_n_events_vs_lap_decrease_block2", "first_lap_with_zero_backups_increase_block2",
            "backups_per_stop_east_minus_west_change_increase", "events_per_stop_east_minus_west_change_decrease",
            "reverse_share_reward_pauses_changed_blocks", "forward_share_pre_run_pauses_changed_blocks"} <= stats
    assert {t["test"] for t in tests if "east_minus_west" in t["statistic"]} == {"b_rate_increase_vs_control", "b_rate_decrease_vs_control"}
    assert all(t["test"] == "b_rate_decrease_vs_control" for t in tests if t["statistic"].endswith("east_minus_west_change_decrease"))
    c_rows = [t for t in tests if t["statistic"].startswith(("slope_of", "first_lap"))]
    assert {t["test"] for t in c_rows if t["statistic"].endswith("_block1")} == {"c_familiarity"}
    assert {t["statistic"].split("_vs_lap_")[-1].split("backups_")[-1] for t in c_rows} == {"increase_block1", "increase_block2", "decrease_block2"}
    assert {t["test"] for t in tests if t["statistic"].startswith("slope") and t["statistic"].endswith("_block2")} == {"c_after_change"}
    assert all(t["test"] == "b_rate_decrease" for t in tests if "_east_decrease_" in t["statistic"] and not t["statistic"].startswith("forward"))
    assert all(t["test"] == "b_rate_increase" for t in tests if "_east_increase_" in t["statistic"] and not t["statistic"].startswith("forward"))
    assert not any("exploratory" in t["test"] for t in tests)
    learning = _read(out / "rq1_learning.csv")
    assert list(learning[0]) == list(rq.LEARNING_COLUMNS)
    assert {r["condition"] for r in learning} == set(rq.version_conditions("step5")) and {(r["mode"], r["session"]) for r in learning} == {
        (m, s) for m in ("fixed", "thresholded") for s in ("increase", "decrease")}
    assert all(r["vs"] in ("none", "prioritised_td", "") for r in learning)
    assert all(r["vs"] == "" for r in learning if r["condition"] == RULE_NONE)
    assert len([r for r in learning if r["condition"] == "mattar_daw" and r["mode"] == "fixed" and r["session"] == "decrease"]) == 2
    assert len(learning) == 4 * (1 + 4 * 2 + 1)  # none, prioritised vs none, four others vs none and vs prioritised
    adaptation = _read(out / "rq1_adaptation.csv")
    assert list(adaptation[0]) == list(rq.ADAPTATION_COLUMNS)
    assert {(r["session"], r["block"], r["lap_in_block"]) for r in adaptation} == {(s, str(b), str(k)) for s in ("increase", "decrease") for b in range(2) for k in (1, 2)}
    m = json.loads((out / "rq1_manifest.json").read_text())
    assert m["protocol"] == "linear_track_rq1" and m["prereg"] == "docs/prereg/rq1_track_mattar_daw.md" and m["version"] == "step5" and m["learner"] == "q"
    assert m["modes"] == ["fixed", "thresholded"] and m["sessions"] == ["increase", "decrease"] and m["threshold"] is None and m["backup_cap"] == 100
    assert m["thetas"] == {c: rq.THRESHOLDS_STEP5[c] for c in rq.version_conditions("step5") if c != RULE_NONE}
    assert m["threshold_scale"] == "mean_abs_value" and m["trajectory_priority"] == "remaining_max" and m["conditions"] == list(rq.version_conditions("step5"))
    assert m["session_blocks"] == {"increase": [[20, 1.0, 1.0], [20, 4.0, 1.0]], "decrease": [[20, 1.0, 1.0], [20, 0.25, 1.0]]}
    assert m["blocks"] == [[2, 1.0, 1.0], [2, 4.0, 1.0]] and m["block_names"] == ["baseline", "increase_x4"] and m["quick"] is True
    assert m["session_block_names"] == {"increase": ["baseline", "increase_x4"], "decrease": ["baseline", "decrease_x0.25"]}
    assert m["configs"]["thresholded/decrease/mattar_daw"]["budget_mode"] == "thresholded" and m["full_evaluation"] is False
    assert m["configs"]["thresholded/decrease/mattar_daw"]["threshold"] == pytest.approx(rq.THRESHOLDS_STEP5["mattar_daw"])
    assert m["configs"]["thresholded/decrease/mattar_daw"]["threshold_scale"] == "mean_abs_value" and m["configs"]["thresholded/decrease/mattar_daw"]["learner"] == "q"


def test_quick_run_is_byte_identical_and_refuses_the_committed_directories(quick_run, tmp_path, monkeypatch) -> None:
    out, _ = quick_run
    again = tmp_path / "again"
    rq.main(["--quick", "--seeds", "2", "--workers", "1", "--write-events", "--out", str(again)])
    for name in (*rq.OUTPUT_FILES, rq.EVENTS_FILE):
        if name.endswith("manifest.json"):
            continue
        assert (out / name).read_bytes() == (again / name).read_bytes(), name
    # Without the flag the events file is not written; one session alone runs.
    plain = tmp_path / "plain"
    res = rq.main(["--quick", "--seeds", "1", "--workers", "1", "--sessions", "decrease", "--out", str(plain)])
    assert {p.name for p in plain.iterdir()} == set(rq.OUTPUT_FILES) and set(res["runs_by_key"]) == {("fixed", "decrease"), ("thresholded", "decrease")}
    # The earlier versions reproduce their protocols' shape: four conditions and one theta in step 2, seven and theta
    # per rule in step 3, one four-block session and an unscaled theta in both.
    step2 = tmp_path / "step2"
    rq.main(["--version", "step2", "--quick", "--seeds", "1", "--workers", "1", "--out", str(step2)])
    m2 = json.loads((step2 / "rq1_manifest.json").read_text())
    assert m2["version"] == "step2" and m2["conditions"] == list(lt.CONDITIONS) and m2["threshold"] == 0.0035 and m2["sessions"] == [rq.FOUR_BLOCK]
    assert m2["prereg"] == "docs/prereg/rq1_track_tabular.md" and m2["trajectory_priority"] == "next" and m2["threshold_scale"] == "none"
    step3 = tmp_path / "step3"
    rq.main(["--version", "step3", "--quick", "--seeds", "1", "--workers", "1", "--out", str(step3)])
    m3 = json.loads((step3 / "rq1_manifest.json").read_text())
    assert m3["version"] == "step3" and m3["conditions"] == list(rq.version_conditions("step3")) and m3["sessions"] == [rq.FOUR_BLOCK]
    assert m3["thetas"] == {c: rq.THRESHOLDS_STEP3[c] for c in rq.version_conditions("step3") if c != RULE_NONE} and m3["threshold_scale"] == "none"
    assert m3["prereg"] == "docs/prereg/rq1_track_gain_need.md" and m3["blocks"] == [[2, 1.0, 1.0], [2, 4.0, 1.0], [2, 1.0, 1.0], [2, 0.25, 1.0]]
    tests3 = _read(step3 / "rq1_tests.csv")
    assert {t["test"] for t in tests3} == {"a_direction", "d_remote", "b_rate_increase", "b_rate_decrease", "b_rate_decrease_vs_baseline_exploratory",
                                           "b_control_end", "b_forward_unchanged", "c_familiarity"}
    assert len(tests3) == 6 * (2 + 2 + 3 * 5 + 1 + 2 * 3) and {t["statistic"] for t in tests3 if t["test"] == "c_familiarity"} >= {"slope_of_n_backups_vs_lap_block1", "slope_of_n_backups_vs_lap_block3"}
    assert {p["session"] for p in rq.read_csv_gz(step3 / "rq1_pauses.csv.gz")} == {rq.FOUR_BLOCK}
    step4 = tmp_path / "step4"
    rq.main(["--version", "step4", "--quick", "--seeds", "1", "--workers", "1", "--out", str(step4)])
    m4 = json.loads((step4 / "rq1_manifest.json").read_text())
    assert m4["version"] == "step4" and m4["conditions"] == list(rq.version_conditions("step4")) and m4["learner"] == "v" and m4["sessions"] == ["increase", "decrease"]
    assert m4["thetas"] == {c: rq.THRESHOLDS_STEP4[c] for c in rq.version_conditions("step4") if c != RULE_NONE} and m4["prereg"] == "docs/prereg/rq1_track_step4.md"
    tests4 = _read(step4 / "rq1_tests.csv")
    assert len(tests4) == 6 * (2 + 2 + 3 * 2 * 2 + 2 + 3 * 3) and not any("vs_control" in t["test"] or t["test"] == "a_direction_after_change" for t in tests4)
    # A theta override is recorded and makes the run partial.
    over = tmp_path / "over"
    rq.main(["--quick", "--seeds", "1", "--workers", "1", "--conditions", "none,uniform", "--theta", "uniform=0.5", "--out", str(over)])
    assert json.loads((over / "rq1_manifest.json").read_text())["thetas"] == {"uniform": 0.5}
    monkeypatch.chdir(tmp_path)
    for argv in (["--quick", "--seeds", "2"], ["--version", "step2", "--quick", "--seeds", "2"], ["--version", "step3", "--quick", "--seeds", "2"],
                 ["--version", "step4", "--quick", "--seeds", "2"],
                 ["--sessions", "increase", "--seeds", "2"], ["--modes", "poisson", "--seeds", "1", "--out", str(tmp_path / "x")],
                 ["--theta", "bogus=1", "--seeds", "1", "--out", str(tmp_path / "y")], ["--sessions", "washout", "--seeds", "1", "--out", str(tmp_path / "z")]):
        with pytest.raises(SystemExit):
            rq.main(argv)
    assert not (tmp_path / "docs").exists()


def test_the_pilot_sets_theta_from_the_normalised_priority_of_the_late_baseline(tmp_path) -> None:
    out = tmp_path / "pilot"
    res = rq.main(["--pilot", "--quick", "--seeds", "2", "--workers", "2", "--out", str(out)])
    rows = _read(out / rq.PILOT_FILE)
    assert {p.name for p in out.iterdir()} == {rq.PILOT_FILE} and list(rows[0]) == list(rq.PILOT_COLUMNS)
    assert [r["condition"] for r in rows] == [c for c in rq.version_conditions("step5") if c != RULE_NONE] and len(res["pilot"]) == 5
    assert all(r["version"] == "step5" and r["laps"] == "2-2" and r["seeds"] == "1,2" and r["n_pauses"] == "2" for r in rows)
    assert all(r["statistic"] == "priority / value_scale" for r in rows)
    rows4 = rq.pilot_rows("step4", seeds=(1,), workers=1, quick=True, conditions=("gain_need", "need_only"))
    assert [r["statistic"] for r in rows4] == ["priority / value_scale", "priority"]
    assert all(float(r["min"]) <= float(r["theta"]) <= float(r["max"]) for r in rows)
    # Step 3's pilot statistic is the raw priority for every rule; its window is laps 11-20 of 20 at the full budget.
    rows3 = rq.pilot_rows("step3", seeds=(1,), workers=1, quick=True, conditions=("uniform", "need_only"))
    assert [r["statistic"] for r in rows3] == ["priority", "priority"] and rows3[0]["laps"] == "2-2"
    baseline = rq.protocol_config("fixed", version="step4", session="increase").blocks()[0]
    assert baseline[0] // 2 + 1 == 11  # the full pilot's window starts at lap 11 of the 20-lap baseline block
    with pytest.raises(ValueError):
        rq.pilot_rows("step9")


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
