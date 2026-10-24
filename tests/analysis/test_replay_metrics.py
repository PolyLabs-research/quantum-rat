"""Replay events by the plan's definition (analysis/replay_metrics.py; docs/m2a_linear_track.md).

Each test is named for what it proves: how backups link into segments, the event
thresholds, the direction and remote reading of a reverse sweep, that scattered
draws give no event, the per-stop and per-seed pooling with NaN where a seed has no
event, and that the command line reads the committed M2a events and writes its three
tables byte-identically.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from analysis import replay_metrics as rm

ROOT = Path(__file__).resolve().parents[2]
COMMITTED = ROOT / "docs" / "data" / "m2a" / "track" / "track_replay_events.jsonl.gz"


def _record(cells, goal="east", condition="reverse_trajectory", seed=1, lap=3, rule=None):
    return {
        "condition": condition, "seed": seed, "lap": lap, "goal": goal, "trigger": "reward",
        "rule": rule or condition, "n_backups": len(cells), "cells": [[c, 0] for c in cells],
    }


def test_consecutive_backups_link_when_their_cells_are_the_same_or_adjacent() -> None:
    assert rm.link_segments([0, 1, 2, 3, 10, 11]) == [(0, 3), (4, 5)]
    assert rm.link_segments([5, 5, 5, 6, 6, 7]) == [(0, 5)]  # staying put (a TURN) keeps the link
    assert rm.link_segments([0, 2, 4]) == [(0, 0), (1, 1), (2, 2)]  # steps of two break it
    assert rm.link_segments([0, 2, 4], neighbour=2) == [(0, 2)]
    assert rm.link_segments([]) == [] and rm.link_segments([7]) == [(0, 0)]


def test_an_event_needs_four_distinct_cells_spanning_six() -> None:
    assert rm.is_event([0, 1, 2, 3, 4, 5, 6])
    assert rm.is_event([0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6])
    assert not rm.is_event([0, 1, 2, 3])  # four distinct, span 3
    assert not rm.is_event([0, 1, 2, 3, 4, 5])  # span 5
    assert rm.is_event([0, 1, 2, 3, 4, 5, 6], min_span=6) and not rm.is_event([0, 1, 2, 3, 4, 5, 6], min_span=7)
    assert not rm.is_event([3, 3, 3, 3, 3, 3, 3, 3])  # one cell
    assert not rm.is_event([])
    assert rm.MIN_DISTINCT_CELLS == 4 and rm.MIN_SPAN_CELLS == 6 and rm.REMOTE_CELLS == 10  # 0.3 m and 0.5 m at 5 cm per cell


def test_a_reverse_sweep_of_an_eastward_lap_is_one_reverse_event_starting_at_the_goal() -> None:
    cells = list(range(39, 19, -1))  # the lap's last 20 transitions, newest (the consume at the goal, cell 39) first
    events = rm.extract_events(_record(cells, goal="east"), n_bins=40)
    assert len(events) == 1
    e = events[0]
    assert (e.start_index, e.end_index, e.n_backups) == (0, 19, 20)
    assert e.n_distinct_cells == 20 and e.span_cells == 19
    assert e.direction == "reverse" and e.sequence_r == pytest.approx(-1.0)
    assert e.start_cell == 39 == e.agent_cell and e.distance_from_agent == 0 and not e.remote
    assert e.travel_sign == 1 and e.trigger == "reward" and e.condition == "reverse_trajectory"
    # The same cells on a westward lap (travel -1) read as a forward sequence.
    west = rm.extract_events(_record(cells, goal="west"), n_bins=40)
    assert len(west) == 1 and west[0].direction == "forward" and west[0].sequence_r == pytest.approx(1.0)
    assert west[0].agent_cell == 0 and west[0].distance_from_agent == 39 and west[0].remote


def test_a_cycling_sweep_breaks_at_the_wrap_and_a_short_tail_is_no_event() -> None:
    # A 7-transition lap tail replayed for 10 backups: the wrap from cell 33 back to 39 is a jump.
    cells = [39, 38, 37, 36, 35, 34, 33, 39, 38, 37]
    events = rm.extract_events(_record(cells), n_bins=40)
    assert [(e.start_index, e.end_index) for e in events] == [(0, 6)]  # the 3-backup remainder is no event
    # A lap whose last steps wandered within five cells: no event at all.
    assert rm.extract_events(_record([39, 38, 39, 38, 37, 36, 35, 36, 37, 38]), n_bins=40) == []
    # A lap with turns: the path stays linked (same cell repeats), the direction is read from the cells.
    cells = [39, 38, 38, 37, 36, 36, 36, 35, 34, 33]
    e, = rm.extract_events(_record(cells), n_bins=40)
    assert e.direction == "reverse" and -1.0 < e.sequence_r < -0.9 and e.n_distinct_cells == 7 and e.span_cells == 6


def test_scattered_draws_give_no_event_and_adjacent_chains_inside_them_do() -> None:
    scattered = [31, 36, 35, 4, 5, 35, 31, 3, 34, 2, 7, 7, 4, 7, 7, 35, 35, 33, 7, 36]  # a prioritised replay, seed 1 lap 12
    assert rm.extract_events(_record(scattered, condition="prioritised_td"), n_bins=40) == []
    chained = [31, 30, 29, 28, 27, 26, 25, 4, 5, 35, 20, 19, 18, 17, 16, 15, 14, 13, 2, 7]
    events = rm.extract_events(_record(chained, goal="west", condition="prioritised_td"), n_bins=40)
    assert [(e.start_cell, e.end_cell, e.direction) for e in events] == [(31, 25, "forward"), (20, 13, "forward")]
    assert [e.remote for e in events] == [True, True]  # the agent is at cell 0 after a westward lap
    # Thresholds are parameters: with a span of 3 and two distinct cells, the whole list is "events".
    assert len(rm.extract_events(_record(scattered), n_bins=40, min_distinct=1, min_span=0)) == len(rm.link_segments(scattered))


def test_per_stop_and_per_seed_pooling_and_nan_for_seeds_without_events() -> None:
    sweep = list(range(39, 19, -1))
    records = [
        _record(sweep, seed=1, lap=1), _record(sweep, goal="west", seed=1, lap=2),
        _record([39, 38, 39, 38, 37, 36, 35, 36, 37, 38], seed=1, lap=3),  # no event
        _record([31, 36, 35, 4, 5, 35, 31, 3, 34, 2], condition="uniform", seed=1, lap=1),
        _record([31, 36, 35, 4, 5, 35, 31, 3, 34, 2], condition="uniform", seed=2, lap=1),
        _record(sweep, condition="uniform", seed=2, lap=2),
    ]
    stops = rm.per_stop_rows(records, n_bins=40)
    assert [r["n_events"] for r in stops] == [1, 1, 0, 0, 0, 1]
    assert stops[1]["n_forward"] == 1 and stops[0]["n_reverse"] == 1 and math.isnan(stops[2]["mean_span"])
    seeds = rm.per_seed_rows(stops)
    assert [(r["condition"], r["seed"]) for r in seeds] == [("reverse_trajectory", 1), ("uniform", 1), ("uniform", 2)]
    rt = seeds[0]
    assert rt["events_per_stop"] == pytest.approx(2 / 3) and rt["stops_with_event"] == pytest.approx(2 / 3)
    assert rt["reverse_share"] == 0.5 and rt["forward_share"] == 0.5 and rt["remote_share"] == 0.5
    assert rt["backups_in_events_share"] == pytest.approx(40 / 50) and rt["mean_span_cells"] == 19 and rt["mean_length_backups"] == 20
    u1 = seeds[1]
    assert u1["events_per_stop"] == 0 and math.isnan(u1["reverse_share"]) and math.isnan(u1["mean_span_cells"])
    summary = rm.summarise_by_condition(seeds, n_boot=200)
    row = summary[(summary["condition"] == "uniform") & (summary["metric"] == "reverse_share")].iloc[0]
    assert row["n"] == 1  # the seed without events is left out of the share's interval
    row = summary[(summary["condition"] == "uniform") & (summary["metric"] == "events_per_stop")].iloc[0]
    assert row["n"] == 2 and row["mean"] == pytest.approx(0.25)
    rates = rm.rate_by_lap(stops, n_boot=200)
    assert [(r["condition"], r["lap"], r["n"], r["events_per_stop"]) for r in rates] == [
        ("reverse_trajectory", 1, 1, 1.0), ("reverse_trajectory", 2, 1, 1.0), ("reverse_trajectory", 3, 1, 0.0),
        ("uniform", 1, 2, 0.0), ("uniform", 2, 1, 1.0),
    ]
    with pytest.raises(ValueError):
        rm.travel_sign_for({"goal": "north"})


@pytest.mark.skipif(not COMMITTED.exists(), reason="the committed M2a events are not present")
def test_the_command_line_reads_the_committed_events_and_writes_its_tables_byte_identically(tmp_path) -> None:
    first = tmp_path / "a"
    result = rm.main([str(COMMITTED), "--out", str(first), "--n-boot", "200"])
    assert {p.name for p in first.iterdir()} == set(rm.OUTPUT_FILES)
    again = tmp_path / "b"
    rm.main([str(COMMITTED), "--out", str(again), "--n-boot", "200"])
    for name in rm.OUTPUT_FILES:
        assert (first / name).read_bytes() == (again / name).read_bytes(), name
    assert len(result["stops"]) == 3599  # one row per committed replay
    assert rm.n_bins_from_manifest(COMMITTED) == 40
    events = result["events"]
    assert events and all(e.n_distinct_cells >= 4 and e.span_cells >= 6 for e in events)
    assert all(e.n_backups <= 20 and 0 <= e.start_index <= e.end_index < 20 for e in events)
    with (first / "track_sequence_events.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0]) == list(rm.EVENT_COLUMNS) and len(rows) == len(events)
    seeds = {(r["condition"], r["seed"]): r for r in result["seeds"]}
    # Reverse replay sweeps the lap just run, so most stops hold an event; scattered draws rarely chain into one.
    rev = [seeds[("reverse_trajectory", s)]["events_per_stop"] for s in range(1, 31)]
    uni = [seeds[("uniform", s)]["events_per_stop"] for s in range(1, 31)]
    assert min(rev) > max(uni)
    assert all(seeds[("reverse_trajectory", s)]["reverse_share"] > 0.9 for s in range(1, 31))
