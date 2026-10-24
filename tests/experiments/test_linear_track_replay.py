"""The M2a linear-track experiment (experiments/linear_track_replay.py; docs/m2a_linear_track.md).

What these tests pin, each named for what it proves: the track's mechanics and the state
encoding, that the policy reads the learner and the learner receives the online backup of
every step and the consume, that the three replay conditions make exactly the budget of
backups per rewarded lap and ``none`` makes none, that the first lap is identical across
conditions at a seed (identical initial conditions), that replay randomness lives on its
own stream, that no replayed transition links two laps, that the direction and content
measures are what the rules imply, and that the runner's quick run writes every file,
byte-identically twice, with the manifest's provenance keys. The numbers of a quick run
mean nothing; the fixed evaluation is the one docs/m2a_linear_track.md reports.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from brain.systems.replay_events import RULE_NONE, RULE_PRIORITISED_TD, RULE_REVERSE_TRAJECTORY, RULE_UNIFORM
from core.rng import RNG
from experiments import linear_track_replay as lt

QUICK = lt.TrackConfig(laps=6, lap_cap=300)
SMALL = lt.TrackConfig(n_bins=8, laps=5, lap_cap=200, backups_per_trigger=6, memory_capacity=100)


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# --- the track and its state -------------------------------------------------------------------


def test_the_track_moves_blocks_turns_and_encodes_four_distinct_state_rows() -> None:
    cfg = lt.TrackConfig()
    track = lt.LinearTrack(cfg)
    start = track.start_state(lt.EAST)
    assert start == lt.State(cell=0, heading=lt.EAST, goal=lt.EAST)
    assert track.start_state(lt.WEST) == lt.State(cell=39, heading=lt.WEST, goal=lt.WEST)
    assert track.step(start, "FORWARD") == (lt.State(1, lt.EAST, lt.EAST), False)
    assert track.step(start, "TURN") == (lt.State(0, lt.WEST, lt.EAST), False)
    assert track.step(lt.State(0, lt.WEST, lt.EAST), "FORWARD") == (lt.State(0, lt.WEST, lt.EAST), True)  # the wall
    assert track.step(lt.State(39, lt.EAST, lt.WEST), "FORWARD") == (lt.State(39, lt.EAST, lt.WEST), True)
    assert track.at_goal(lt.State(39, lt.EAST, lt.EAST)) and not track.at_goal(lt.State(39, lt.EAST, lt.WEST))
    assert track.at_goal(lt.State(0, lt.WEST, lt.WEST))
    with pytest.raises(ValueError):
        track.step(start, "REST")
    # The learner's position: x the cell centre; the four (heading, goal) rows fall in four distinct y cells.
    learner = lt.TabularTD0(cfg.bin_size, cfg.learning_rate, cfg.discount)
    rows = {(h, g): learner.cell(*track.position(lt.State(5, h, g)))[1] for h in (lt.EAST, lt.WEST) for g in (lt.EAST, lt.WEST)}
    assert len(set(rows.values())) == 4 and all(learner.cell(*track.position(lt.State(5, h, g)))[0] == 5 for h, g in rows)
    assert len(track.states()) == 4 * cfg.n_bins == 160
    # The exact values: discount^(actions to the goal), one more when facing away; the goal state reads the reward.
    assert track.optimal_value(lt.State(39, lt.EAST, lt.EAST)) == 1.0
    assert track.optimal_value(lt.State(38, lt.EAST, lt.EAST)) == pytest.approx(0.95)
    assert track.optimal_value(lt.State(38, lt.WEST, lt.EAST)) == pytest.approx(0.95 ** 2)
    assert track.optimal_value(lt.State(0, lt.EAST, lt.EAST)) == pytest.approx(0.95 ** 39)
    assert track.optimal_value(lt.State(0, lt.WEST, lt.EAST)) == pytest.approx(0.95 ** 40)
    assert cfg.untrained_turn_probability() == pytest.approx(0.2)
    with pytest.raises(ValueError):
        lt.TrackConfig(n_bins=1)


def test_the_policy_reads_the_learner_and_the_learner_receives_every_online_backup() -> None:
    cfg = lt.TrackConfig()
    track = lt.LinearTrack(cfg)
    agent = lt.TrackAgent(cfg, track)
    state = lt.State(10, lt.EAST, lt.EAST)
    # Untrained: the scores are the prior alone, so TURN has probability 0.2.
    assert agent.scores(state) == {"FORWARD": pytest.approx(cfg.forward_prior), "TURN": 0.0}
    stream = RNG(1).stream(lt.ACTION_STREAM)
    draws = [agent.act(state, stream) for _ in range(4000)]
    assert 0.17 < draws.count("TURN") / 4000 < 0.23
    # Write a value one step ahead: FORWARD's score moves by value_gain times it, TURN's does not.
    x, y = track.position(lt.State(11, lt.EAST, lt.EAST))
    agent.learner.values[agent.learner.cell(x, y)] = 0.05
    assert agent.scores(state)["FORWARD"] == pytest.approx(cfg.forward_prior + 0.5)
    assert agent.scores(state)["TURN"] == 0.0
    # A value on the turned-to state makes TURN the likelier action: the decision follows the table.
    xt, yt = track.position(lt.State(10, lt.WEST, lt.EAST))
    agent.learner.values[agent.learner.cell(xt, yt)] = 0.2
    assert agent.scores(state)["TURN"] == pytest.approx(2.0)
    assert agent.scores(state)["TURN"] > agent.scores(state)["FORWARD"]
    stream = RNG(2).stream(lt.ACTION_STREAM)
    assert sum(agent.act(state, stream) == "TURN" for _ in range(2000)) > 1900
    # Online learning: every step of a lap is one backup (plus the consume), on the learner the policy reads.
    run = lt.run_seed(RULE_NONE, 1, SMALL)
    first = run.laps[0]
    assert first.online_updates == first.steps + 1 and first.rewarded
    assert all(lap.online_updates == lap.steps + (1 if lap.rewarded else 0) for lap in run.laps)
    assert sum(lap.replay_backups for lap in run.laps) == 0 and not any(lap.replay_event for lap in run.laps)


# --- the four conditions -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def runs():
    return {c: lt.run_seed(c, 7, SMALL) for c in lt.CONDITIONS}


def test_identical_first_lap_then_exactly_the_budget_of_backups_per_rewarded_lap(runs) -> None:
    first = {c: run.first_lap_actions for c, run in runs.items()}
    assert len(set(first.values())) == 1  # the same seed, the same first lap: no replay has happened yet
    assert all(run.laps[0].steps == runs[RULE_NONE].laps[0].steps for run in runs.values())
    for c, run in runs.items():
        for lap in run.laps:
            if c == RULE_NONE:
                assert lap.replay_backups == 0 and not lap.replay_event
            elif lap.rewarded:
                assert lap.replay_backups == SMALL.backups_per_trigger and lap.replay_event
            else:
                assert lap.replay_backups == 0 and not lap.replay_event  # a capped lap: no reward, no trigger
        summary = run.summary()
        rewarded = sum(lap.rewarded for lap in run.laps)
        expected = 0 if c == RULE_NONE else SMALL.backups_per_trigger * rewarded
        assert summary["replay_backups"] == expected and summary["replay_events"] == (0 if c == RULE_NONE else rewarded)
        assert summary["online_updates"] == sum(lap.steps + lap.rewarded for lap in run.laps)
        assert summary["replay_budget_fraction"] == pytest.approx(expected / summary["online_updates"])
    # The three replay conditions share the budget per trigger: event counts and backup counts agree exactly.
    replay_runs = [runs[c] for c in lt.CONDITIONS if c != RULE_NONE]
    assert len({r.summary()["replay_backups"] / max(r.summary()["replay_events"], 1) for r in replay_runs}) == 1


def test_replay_randomness_is_on_its_own_stream_and_never_links_two_laps(runs) -> None:
    # The action stream is consumed identically across conditions through the first lap (one draw per step),
    # and the replay stream is untouched by ``none`` and by the deterministic reverse sweep.
    cfg = SMALL
    for c in lt.CONDITIONS:
        action = RNG(7).stream(lt.ACTION_STREAM)
        for _ in range(runs[c].laps[0].steps):
            action.random()
        # Re-run the first lap by hand through the module's own objects to compare stream states.
        track = lt.LinearTrack(cfg)
        agent = lt.TrackAgent(cfg, track)
        stream = RNG(7).stream(lt.ACTION_STREAM)
        state = track.start_state(lt.EAST)
        steps = 0
        while not track.at_goal(state) and steps < cfg.lap_cap:
            nxt, _ = track.step(state, agent.act(state, stream))
            agent.store_and_learn(state, 0.0, nxt, False, 0, steps)
            state = nxt
            steps += 1
        assert steps == runs[c].laps[0].steps
        assert stream.getstate() == action.getstate()
    # Replayed transitions: each is one stored transition of a single lap with its own successor; the reverse
    # rule's events hold only the lap just completed, and no event's transitions straddle a lap boundary.
    for c in (RULE_UNIFORM, RULE_REVERSE_TRAJECTORY, RULE_PRIORITISED_TD):
        for event in runs[c].events:
            assert event["n_backups"] == SMALL.backups_per_trigger == len(event["cells"]) == len(event["episodes"]) == len(event["deltas"])
            assert all(1 <= e <= event["lap"] for e in event["episodes"])  # nothing from a lap not yet run
            if c == RULE_REVERSE_TRAJECTORY:
                assert set(event["episodes"]) == {event["lap"]}
    # The deterministic reverse sweep draws nothing from the replay stream; the sampling rules do.
    replay_untouched = RNG(7).stream(lt.REPLAY_STREAM).getstate()

    def replay_state_after(condition: str):
        track = lt.LinearTrack(cfg)
        agent = lt.TrackAgent(cfg, track)
        rng = RNG(7)
        action, rep = rng.stream(lt.ACTION_STREAM), rng.stream(lt.REPLAY_STREAM)
        state = track.start_state(lt.EAST)
        steps = 0
        while not track.at_goal(state):
            nxt, _ = track.step(state, agent.act(state, action))
            agent.store_and_learn(state, 0.0, nxt, False, 0, steps)
            state, steps = nxt, steps + 1
        agent.store_and_learn(state, 1.0, state, True, 0, steps)
        rule = lt._rule_for(condition, cfg)
        if rule is not None:
            lt.replay(rule, agent.memory, agent.learner, cfg.backups_per_trigger, 0, rep, tick=steps)
        return rep.getstate()

    assert replay_state_after(RULE_NONE) == replay_untouched
    assert replay_state_after(RULE_REVERSE_TRAJECTORY) == replay_untouched
    assert replay_state_after(RULE_UNIFORM) != replay_untouched
    assert replay_state_after(RULE_PRIORITISED_TD) != replay_untouched


def test_direction_and_content_measures_follow_the_rules(runs) -> None:
    reverse = runs[RULE_REVERSE_TRAJECTORY].summary()
    assert reverse["replay_from_this_lap"] == 1.0  # by construction: the lap just completed
    assert reverse["replay_reverse_share"] > 0.5 and reverse["replay_mean_sequence_r"] < 0.0
    for c in (RULE_UNIFORM, RULE_PRIORITISED_TD):
        s = runs[c].summary()
        assert 0.0 <= s["replay_from_this_lap"] <= 1.0 and 0.0 <= s["replay_remote_share"] <= 1.0
        assert abs(s["replay_reverse_share"] + s["replay_forward_share"] + s["replay_neither_share"] - 1.0) < 1e-12
        assert -1.0 <= s["replay_mean_sequence_r"] <= 1.0
    # The value table moves under every condition. The reverse sweep starts with the consume (TD error
    # 0.8 after its online backup) and the prioritised rule draws it first, so their tables already
    # differ from none's at the end of lap 1; a uniform draw of six zero-error transitions can leave the
    # table where it was, so uniform is only required to differ by the end of the run.
    none_rmse = [lap.value_rmse for lap in runs[RULE_NONE].laps]
    for c in lt.CONDITIONS:
        rmse = [lap.value_rmse for lap in runs[c].laps]
        assert all(math.isfinite(v) for v in rmse) and rmse[-1] < 1.0
        visited = [lap.value_rmse_visited for lap in runs[c].laps]
        assert all(math.isfinite(v) for v in visited) and visited[-1] < 1.0
        assert visited[-1] != rmse[-1]  # weighted by occupancy, so the unvisited states no longer dominate
    for c in (RULE_REVERSE_TRAJECTORY, RULE_PRIORITISED_TD):
        assert runs[c].laps[0].value_rmse != none_rmse[0]
    assert runs[RULE_UNIFORM].laps[-1].value_rmse != none_rmse[-1]


def test_a_rewarded_lap_flips_the_goal_and_a_capped_lap_retries_it() -> None:
    cfg = lt.TrackConfig(n_bins=6, laps=4, lap_cap=3, backups_per_trigger=2, memory_capacity=50)  # a cap too short to reach the goal
    run = lt.run_seed(RULE_REVERSE_TRAJECTORY, 3, cfg)
    assert [lap.rewarded for lap in run.laps] == [False] * 4 and [lap.goal for lap in run.laps] == ["east"] * 4
    assert all(lap.steps == 3 and lap.replay_backups == 0 and lap.reward == 0.0 for lap in run.laps)
    assert run.summary()["laps_capped"] == 4 and run.summary()["reward_total"] == 0.0 and run.events == []
    cfg = lt.TrackConfig(n_bins=4, laps=4, lap_cap=500, backups_per_trigger=3, memory_capacity=50)
    run = lt.run_seed(RULE_UNIFORM, 3, cfg)
    assert all(lap.rewarded for lap in run.laps) and [lap.goal for lap in run.laps] == ["east", "west", "east", "west"]
    assert run.summary()["reward_total"] == 4.0 and run.summary()["laps_rewarded"] == 4


def test_the_same_seed_gives_the_same_run_and_different_seeds_different_ones() -> None:
    a = lt.run_seed(RULE_PRIORITISED_TD, 11, SMALL)
    b = lt.run_seed(RULE_PRIORITISED_TD, 11, SMALL)
    assert [lap.steps for lap in a.laps] == [lap.steps for lap in b.laps] and a.events == b.events
    others = [lt.run_seed(RULE_PRIORITISED_TD, s, SMALL) for s in (12, 13)]
    assert len({tuple(lap.steps for lap in r.laps) for r in [a, *others]}) == 3
    result = lt.analyse([a, *others], n_boot=100)
    assert result["guard"][RULE_PRIORITISED_TD] == {"distinct": 3, "n": 3, "message": ""}
    # Two identical runs under the same condition are caught.
    result = lt.analyse([a, b], n_boot=100)
    assert result["guard"][RULE_PRIORITISED_TD]["distinct"] is None and "pseudo-replication" in result["guard"][RULE_PRIORITISED_TD]["message"]


# --- the runner ----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def quick_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("track")
    res = lt.main(["--seeds", "3", "--quick", "--workers", "2", "--out", str(out)])
    return out, res


def test_quick_run_writes_every_file_with_the_documented_columns(quick_run) -> None:
    out, res = quick_run
    assert {p.name for p in out.iterdir()} == set(lt.OUTPUT_FILES)
    laps = _read(out / "track_laps.csv")
    assert list(laps[0]) == list(lt.LAP_COLUMNS)
    assert len(laps) == 4 * 3 * 6  # four conditions, three seeds, six laps
    per_seed = _read(out / "track_per_seed.csv")
    assert list(per_seed[0]) == ["condition", "task", "seed", "metric", "value"]
    assert {r["task"] for r in per_seed} == {lt.TASK} and {r["seed"] for r in per_seed} == {"1", "2", "3"}
    summary = _read(out / "track_summary.csv")
    assert list(summary[0]) == ["condition", "metric", "n", "mean", "low", "high", "iqm", "ci_method"]
    assert {r["condition"] for r in summary} == set(lt.CONDITIONS)
    curve = _read(out / "track_learning_curve.csv")
    assert list(curve[0]) == list(lt.CURVE_COLUMNS) and len(curve) == 4 * 6
    effects = _read(out / "track_effects.csv")
    assert list(effects[0]) == list(lt.EFFECT_COLUMNS)
    assert len(effects) == len(lt.EFFECT_METRICS) * len(lt.COMPARISONS)
    assert {(r["a"], r["b"]) for r in effects} == set(lt.COMPARISONS)
    events = lt.read_events(out / lt.EVENTS_FILE)
    rewarded_replay_laps = sum(1 for r in laps if r["condition"] != RULE_NONE and r["rewarded"] == "True")
    assert len(events) == rewarded_replay_laps and all(e["trigger"] == "reward" for e in events)
    assert res["first_lap_identical"] is True
    assert all(v["distinct"] == 3 for v in res["guard"].values())


def test_quick_run_manifest_records_the_provenance_and_the_design_checks(quick_run) -> None:
    out, _ = quick_run
    m = json.loads((out / "track_manifest.json").read_text())
    assert m["protocol"] == "linear_track_replay" and m["seeds"] == [1, 2, 3] and m["task"] == lt.TASK
    assert m["conditions"] == list(lt.CONDITIONS) and m["full_evaluation"] is False
    assert m["config"]["laps"] == 6 and m["config"]["lap_cap"] == 300 and m["config"]["n_bins"] == 40
    assert m["learner"]["learner"] == "tabular_td0" and m["learner"]["discount"] == 0.95
    assert m["replay"]["backups_per_trigger"] == 20 and m["replay"]["trigger"] == "reward"
    assert m["replay"]["rules"] == [RULE_UNIFORM, RULE_REVERSE_TRAJECTORY, RULE_PRIORITISED_TD]
    assert m["policy"]["untrained_turn_probability"] == pytest.approx(0.2)
    assert m["rng_streams"] == {"action": lt.ACTION_STREAM, "replay": lt.REPLAY_STREAM, "environment": "none (deterministic track)"}
    assert set(m["dependencies"]) == {"python", "numpy", "pandas", "scipy", "threadpoolctl", "pyarrow"}
    assert m["first_lap_identical_across_conditions"] is True
    assert all(m["guard"][c]["distinct"] == 3 for c in lt.CONDITIONS)
    assert set(m["platform"]) >= {"blas_runtime_status", "blas_threads_verified", "numpy_loaded_before_pin"}
    assert m["git"]["sha"] != "unknown" and m["ticks_run"] > 0 and m["timing"]["wall_seconds"] >= 0
    assert "--quick" in m["command"]


def test_quick_run_is_byte_identical_whatever_the_worker_count(quick_run, tmp_path) -> None:
    out, _ = quick_run
    again = tmp_path / "again"
    lt.main(["--seeds", "3", "--quick", "--workers", "1", "--out", str(again)])
    for name in lt.OUTPUT_FILES:
        if name == "track_manifest.json":
            continue  # wall-clock provenance differs by design
        assert (out / name).read_bytes() == (again / name).read_bytes(), name


def test_a_partial_run_refuses_the_committed_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # the default is relative: docs/data/m2a/track under the cwd
    with pytest.raises(SystemExit):
        lt.main(["--seeds", "2", "--quick"])
    with pytest.raises(SystemExit):
        lt.main(["--conditions", "none,bogus", "--seeds", "1", "--out", str(tmp_path / "x")])
    assert not (tmp_path / "docs").exists()
