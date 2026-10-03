"""Fast checks of the steering-sensitivity harness (short tick budgets only)."""

from __future__ import annotations

import inspect
import json
import math
from types import SimpleNamespace

import pytest

import ui.scenarios as scenarios_module
from experiments import steering_sensitivity as ss


def _without(row, *keys):
    return {k: v for k, v in row.items() if k not in keys}


def test_run_job_is_deterministic_and_order_independent():
    job = ss.Job("beacon", 1.5, 1, 0.03, 300)
    maze = ss.Job("memory_maze", 1.5, 2, 0.03, 200, (), 0.1)
    first = ss.run_job(job)
    first_maze = ss.run_job(maze)
    assert ss.run_job(job) == first  # also after another job ran in this process
    assert ss.run_job(maze) == first_maze
    assert first["ticks"] == 300 and first["heading"] is None and first["noise"] == 0.03


def test_headings_for_grid():
    assert ss.headings_for("beacon", None) == [None]
    assert ss.headings_for("memory_maze", None) == [None]
    assert ss.headings_for("foraging", 4) == [0.0, math.pi / 2, math.pi, 3 * math.pi / 2]
    # The maze uses the fixed memory-dependent set whatever N is.
    assert ss.headings_for("memory_maze", 8) == list(ss.MAZE_HEADINGS)
    assert ss.headings_for("memory_maze", 3) == [-0.2, -0.1, 0.0, 0.1, 0.2]
    with pytest.raises(ValueError):
        ss.headings_for("beacon", 0)


def test_maze_heading_sets():
    assert ss.maze_heading_set(None) == list(ss.MAZE_HEADINGS)
    assert ss.maze_heading_set("default") == list(ss.MAZE_HEADINGS)
    full = ss.maze_heading_set("full")
    assert len(full) == ss.FULL_CIRCLE_HEADINGS == 16
    assert full[4] == pytest.approx(math.pi / 2)
    assert ss.maze_heading_set("4") == ss.maze_heading_set(4) == [0.0, math.pi / 2, math.pi, 3 * math.pi / 2]
    for bad in ("half", 0, "-2"):
        with pytest.raises(ValueError):
            ss.maze_heading_set(bad)
    # --maze-headings alone varies only the maze; with --headings the open scenarios vary too.
    assert ss.headings_for("memory_maze", None, "full") == full
    assert ss.headings_for("beacon", None, "full") == [None]
    assert ss.headings_for("memory_maze", 8, "full") == full
    jobs = ss.make_jobs(["beacon", "memory_maze"], [1.5], [1], 0.0, maze_headings=4)
    assert [j.heading for j in jobs] == [None, 0.0, math.pi / 2, math.pi, 3 * math.pi / 2]


def test_maze_rows_report_training_and_timeouts():
    row = ss.run_job(ss.Job("memory_maze", 1.5, 1, 0.0, 400, (), math.pi))
    assert row["train_ticks"] is not None and row["train_ticks"] > 20  # a search: the goal starts out of view
    assert row["timeouts"] == row["attempted"] - row["score"]


def test_headings_change_outcomes_and_restore_start_pose():
    pose = scenarios_module.START_POSE
    beacon = ss.sweep(["beacon"], [1.5], [1], noise=0.0, ticks=300, workers=1, headings=4)
    maze = ss.sweep(["memory_maze"], [1.5], [1], noise=0.0, ticks=150, workers=1, headings=8)
    assert scenarios_module.START_POSE == pose  # the maze heading never leaks out of a run
    assert [r["heading"] for r in beacon] == ss.headings_for("beacon", 4)
    assert [r["heading"] for r in maze] == list(ss.MAZE_HEADINGS)
    for rows in (beacon, maze):
        outcomes = {json.dumps(_without(r, "heading"), sort_keys=True) for r in rows}
        assert len(outcomes) > 1, "start heading had no effect"


def test_vrest_share_and_maze_metrics():
    rows = ss.sweep(["foraging", "memory_maze"], [0.0, 1.5], [1], noise=0.0, ticks=200, workers=1)
    for row in rows:
        assert 0.0 <= row["vrest"] <= 1.0
        if row["value_gain"] == 0.0:
            assert row["vrest"] == 0.0  # no value term, no value-induced REST
    maze = [r for r in rows if r["scenario"] == "memory_maze"]
    for row in maze:
        assert {"first_hidden_ticks", "median_recall_ticks", "recall_rate", "attempted"} <= set(row)
        assert 0.0 <= row["recall_rate"] <= 1.0
    assert any(r["first_hidden_ticks"] is not None for r in maze)


def test_rows_carry_the_runs_trace_hash_and_outcome_fields_exclude_the_job():
    rows = ss.run_jobs([ss.Job("foraging", 1.5, seed, 0.03, 60) for seed in (1, 2)], workers=1)
    for row in rows:
        assert len(row["trace_hash"]) == 64 and int(row["trace_hash"], 16) >= 0
        assert set(ss.JOB_FIELDS) <= set(row)
        outcome = ss.outcome_fields(row)
        assert not set(ss.JOB_FIELDS) & set(outcome)
        assert {"score", "vrest", "trace_hash"} <= set(outcome)
    assert rows[0]["trace_hash"] != rows[1]["trace_hash"]  # two seeds, two runs (sensor noise on)
    again = ss.run_job(ss.Job("foraging", 1.5, 1, 0.03, 60))
    assert again["trace_hash"] == rows[0]["trace_hash"]  # the same job, the same trace


def _ctx(scores, signals, action=None):
    return SimpleNamespace(action_scores=scores, value_signals=signals, action_name=action)


def test_is_value_rest_counterfactual():
    # Value terms (all -1 at a local maximum) push every move below REST: value-induced REST.
    scores = {"FORWARD": -0.3, "TURN_LEFT": -0.4, "TURN_RIGHT": -0.6, "REST": 0.0}
    assert ss.is_value_rest(_ctx(scores, (-1.0, -1.0, -1.0), "REST"), 0.8)
    # Without the value terms REST would still win: pain-driven REST, not value-induced.
    pain = {"FORWARD": 0.1, "TURN_LEFT": 0.0, "TURN_RIGHT": 0.0, "REST": 0.5}
    assert not ss.is_value_rest(_ctx(pain, (0.0, 0.0, 0.0), "REST"), 0.8)
    # A move was chosen.
    assert not ss.is_value_rest(_ctx({**scores, "FORWARD": 0.2}, (-1.0, -1.0, -1.0), "FORWARD"), 0.8)
    # Microsleep and missing readouts never count.
    assert not ss.is_value_rest(_ctx({"REST": 1.0}, (-1.0, -1.0, -1.0), "REST"), 0.8)
    assert not ss.is_value_rest(SimpleNamespace(), 0.8)
    # Without action_name the winner is taken from the scores; ties break in ACTION_ORDER.
    tie = {"FORWARD": -0.5, "TURN_LEFT": -0.5, "TURN_RIGHT": -0.5, "REST": 0.0}
    assert ss.is_value_rest(_ctx(tie, (-0.5, -0.5, -0.5)), 1.0)
    assert not ss.is_value_rest(_ctx(tie, (-0.5, -0.5, -0.5)), 0.0)


def test_sweep_single_job_path_applies_ticks_override():
    by_scenario = ss.sweep(["beacon"], [0.8], [1], ticks={"beacon": 40})
    as_int = ss.sweep(["beacon"], [0.8], [1], ticks=40)
    direct = ss.run_job(ss.Job("beacon", 0.8, 1, 0.03, 40))
    assert by_scenario == as_int == [direct]
    assert direct["ticks"] == 40
    assert [j.ticks for j in ss.make_jobs(["beacon", "memory_maze"], [1.0], [1])] == [3000, 1500]


def test_pool_matches_in_process():
    kwargs = dict(scenarios=["beacon", "memory_maze"], gains=[1.5], seeds=[3], ticks=120)
    assert ss.sweep(workers=2, **kwargs) == ss.sweep(workers=1, **kwargs)


def _rows(table):
    """Synthetic rows from {scenario: {gain: [scores]}}."""
    return [
        {"scenario": scen, "value_gain": gain, "seed": i + 1, "score": score, "vrest": 0.1 * i}
        for scen, by_gain in table.items()
        for gain, scores in by_gain.items()
        for i, score in enumerate(scores)
    ]


def test_summary_worst_fraction_and_band():
    rows = _rows({
        "a": {0.0: [2, 4], 0.5: [9, 11], 1.0: [10, 10], 2.0: [9, 9], 3.0: [5, 5]},
        "b": {0.0: [20, 20], 0.5: [10, 10], 1.0: [19, 19], 2.0: [18, 18], 3.0: [20, 20]},
    })
    rows.append({"scenario": "memory_maze", "value_gain": 1.0, "seed": 1, "score": 3, "recall_rate": 0.75,
                 "first_hidden_ticks": 12, "median_recall_ticks": None, "vrest": 0.0})
    rows.append({"scenario": "memory_maze", "value_gain": 1.0, "seed": 2, "score": 4, "recall_rate": 1.0,
                 "first_hidden_ticks": None, "median_recall_ticks": 9, "vrest": 0.2})
    summary = ss.summarise(rows)
    assert summary["a"][0.0] == {"mean": 3, "min": 2, "max": 4, "n": 2, "vrest": pytest.approx(0.05)}
    maze = summary["memory_maze"][1.0]
    assert maze["recall_rate"] == pytest.approx(0.875)
    assert maze["first_hidden_ticks"] == 12 and maze["median_recall_ticks"] == 9
    assert maze["vrest"] == pytest.approx(0.1)

    del summary["memory_maze"]  # ran one gain only; worst_fraction needs a common grid
    worst = ss.worst_fraction(summary)
    assert worst == {0.0: pytest.approx(0.3), 0.5: pytest.approx(0.5), 1.0: pytest.approx(0.95),
                     2.0: pytest.approx(0.9), 3.0: pytest.approx(0.5)}
    assert ss.good_band(worst, 0.8) == [1.0, 2.0]
    assert ss.good_band(worst, 0.92) == [1.0]
    assert ss.good_band(worst, 0.99) == []
    # Longest contiguous run wins over a higher isolated value; equal runs go to the higher mean.
    assert ss.good_band({0: 0.9, 1: 0.1, 2: 0.81, 3: 0.82}, 0.8) == [2, 3]
    assert ss.good_band({0: 0.9, 1: 0.9, 2: 0.1, 3: 0.95, 4: 0.95}, 0.8) == [3, 4]

    robust = ss.robustness(summary)
    assert robust["a"] == {"best_mean": 10, "good_gains": [0.5, 1.0, 2.0], "n_gains": 5}
    assert robust["b"]["good_gains"] == [0.0, 1.0, 2.0, 3.0]
    # A scenario that never scores makes every gain bad.
    assert ss.worst_fraction(ss.summarise(_rows({"a": {1.0: [1]}, "z": {1.0: [0]}}))) == {1.0: 0.0}
    assert ss.worst_fraction({}) == {}


def test_by_noise_blocks_keep_order():
    rows = [{"noise": 0.03, "i": 0}, {"noise": 0.0, "i": 1}, {"noise": 0.03, "i": 2}]
    blocks = ss.by_noise(rows)
    assert list(blocks) == [0.03, 0.0]
    assert [r["i"] for r in blocks[0.03]] == [0, 2]


def test_main_noise_both_json_is_byte_identical(capsys):
    argv = ["--scenarios", "beacon,memory_maze", "--gains", "1.5", "--seeds", "2", "--seed-start", "9",
            "--noise-both", "--ticks", "60", "--workers", "2", "--json"]
    ss.main(argv)
    first = capsys.readouterr().out
    ss.main(argv)
    assert capsys.readouterr().out == first
    rows = json.loads(first)
    seeded = [r for r in rows if r["noise"] == 0.03]
    headed = [r for r in rows if r["noise"] == 0.0]
    assert sorted({r["seed"] for r in seeded}) == [9, 10]
    assert all(r["heading"] is None for r in seeded)
    assert {r["seed"] for r in headed} == {9}
    assert len([r for r in headed if r["scenario"] == "beacon"]) == 8
    assert [r["heading"] for r in headed if r["scenario"] == "memory_maze"] == list(ss.MAZE_HEADINGS)

    ss.main(argv[:-1])  # the table view prints one block per noise level
    out = capsys.readouterr().out
    assert "=== noise 0.03, seeds 9-10, start heading 0 ===" in out
    assert "=== noise 0, seed 9, 8 headings, maze 5 headings ===" in out
    assert out.count("good band (worst >= 0.80)") == 2


@pytest.mark.parametrize("scenario", ["hazard_field", "beacon"])
def test_is_value_rest_matches_the_engine_no_value_scores(monkeypatch, scenario):
    # Integration check against the real engine: the counterfactual in
    # is_value_rest (scores minus value_gain * ctx.value_signals on the three
    # moves, REST kept) must equal the engine's own channel scores recomputed
    # with every value input zeroed. This pins that ctx.value_signals are the
    # effective (cue-gated) signals fed to action selection and that the value
    # term is exactly value_gain * signal, with freeze habituation and pacing
    # living only in REST. hazard_field exercises pain freezing and pacing,
    # beacon exercises cue gating. Under the default split steering memory is
    # silent in beacon until about tick 1500 (the primary-only map has nothing
    # to steer by before the first few contacts), so beacon runs 2000 ticks.
    from brain.systems import basal_ganglia as bg
    from core.engine import Engine

    captured = {}
    original = bg._channel_scores

    def recording(*args, **kwargs):
        captured["args"], captured["kwargs"] = args, kwargs
        return original(*args, **kwargs)

    monkeypatch.setattr(bg, "_channel_scores", recording)
    sc = scenarios_module.make_scenario(scenario)
    config = sc.config()
    config.sensors.noise = 0.03
    config.basal_ganglia.value_gain = gain = 1.5
    engine = Engine(seed=1, config=config)
    sc.setup(engine)
    gated = paced = valued = rested = 0
    for _ in range(2000 if scenario == "beacon" else 1500):
        td = engine.run(1)[0]
        ctx = engine.context
        scores = ctx.action_scores
        if set(scores) != set(bg.ACTION_ORDER):
            sc.on_tick(engine, td.tick)
            continue  # microsleep
        bound = inspect.signature(original).bind(*captured["args"], **captured["kwargs"])
        inputs = bound.arguments
        assert (inputs["value_ahead"], inputs["value_left"], inputs["value_right"]) == tuple(ctx.value_signals)
        inputs.update(value_ahead=0.0, value_left=0.0, value_right=0.0)
        no_value = original(*bound.args, **bound.kwargs)
        ahead, left, right = ctx.value_signals
        expected = dict(scores)
        expected["FORWARD"] -= gain * ahead
        expected["TURN_LEFT"] -= gain * left
        expected["TURN_RIGHT"] -= gain * right
        for name in bg.ACTION_ORDER:
            assert expected[name] == pytest.approx(no_value[name], abs=1e-12)
        flagged = ss.is_value_rest(ctx, gain)
        assert flagged == (ctx.action_name == "REST" and ss._winner(no_value) != "REST")
        gated += ctx.cue_gate < 1.0
        paced += ctx.pacing_active
        valued += any(ctx.value_signals)
        rested += flagged
        sc.on_tick(engine, td.tick)
    assert valued and gated  # the value path and cue gating were exercised
    if scenario == "hazard_field":
        assert paced  # pacing put a REST drive in the scores
