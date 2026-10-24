"""Replay-event metrics by the plan's definitions (docs/research_plan.md section 2; docs/m2a_linear_track.md).

    python3 -m analysis.replay_metrics docs/data/m2a/track/track_replay_events.jsonl.gz --out docs/data/m2a/track

A replay in ``experiments.linear_track_replay`` is a list of TD backups made at
one pause; its record (``track_replay_events.jsonl.gz``) carries the start cell
of every backed-up transition in backup order. The plan defines a **replay
event** as "a sampled sequence of >= 4 distinct states spanning >= 0.3 m, with a
start state, direction (forward / reverse / neither, by the sign of the
position-time slope along the track) and a trigger", a **remote event** as one
whose start state is > 0.5 m from the agent, and the **rate** as events per
stop. This module reads events off the backup lists by those definitions, so
that a rule which replays scattered transitions is not credited with a
"reverse" or "forward" event on the strength of a slope sign over 20 unrelated
cells (what G26 found for the uniform and prioritised rules: a coin).

Extraction (``extract_events``): consecutive backups are *linked* when their
start cells are the same or adjacent on the track (|cell difference| <=
:data:`NEIGHBOUR_CELLS`, 1), whatever their heading or goal row: a sequence is
spatial, and a TURN in a replayed path keeps the cell. A maximal run of linked
backups is a *segment*; a segment is an event when it covers at least
:data:`MIN_DISTINCT_CELLS` (4) distinct cells and spans at least
:data:`MIN_SPAN_CELLS` (6 cells = 0.3 m at 0.05 m per cell, docs/units.md).
Each event gets the direction and signed correlation of
``brain.systems.replay_rules.sequence_direction`` over its own cells against
the travel direction of the lap its states belong to (their goal row: the
state carries the goal end, so a replayed transition is direction-selective
like a track place cell; a segment mixing rows takes the majority), its start
cell, and a remote flag when that start is more than :data:`REMOTE_CELLS` (10
cells = 0.5 m) from the agent's cell at the pause (the record's ``agent_cell``
when present, else the goal cell just reached). A reverse-trajectory replay of a lap
is one segment unless the sweep cycled (the wrap from the lap's first
transition back to its newest is a jump); a lap whose last 20 steps wandered
within fewer than 6 cells yields no event.

Aggregation keeps the seed as the unit: ``per_stop_rows`` gives one row per
pause, ``per_seed_rows`` pools a seed's pauses into events per stop, the share
of stops with an event, the direction and remote shares among its events and
the mean span and length, and ``summarise_by_condition`` hands the per-seed
values to ``analysis.stats`` for BCa intervals (a seed with no event has no
direction share and is left out of that metric's interval, with ``n`` saying
so). ``rate_by_lap`` is events per stop by lap index (the plan's familiarity
axis). Pure functions on plain records; the command line writes three tables.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy (analysis.stats) loads
import numpy as np

from analysis.stats import bootstrap_ci, summarise, tidy_table
from brain.systems.replay_rules import sequence_direction

MIN_DISTINCT_CELLS = 4
MIN_SPAN_CELLS = 6  # 0.3 m at 0.05 m per cell (docs/units.md)
REMOTE_CELLS = 10  # 0.5 m
NEIGHBOUR_CELLS = 1  # consecutive backups are linked when |cell difference| <= this
DEFAULT_N_BOOT = 10_000
OUTPUT_FILES = ("track_sequence_events.csv", "track_sequence_metrics.csv", "track_sequence_rate_by_lap.csv")


def link_segments(cells: Sequence[int], neighbour: int = NEIGHBOUR_CELLS) -> List[Tuple[int, int]]:
    """Maximal runs of consecutive backups whose cells are within ``neighbour`` of each other: (first, last) indices, inclusive."""
    if not cells:
        return []
    segments: List[Tuple[int, int]] = []
    start = 0
    for k in range(1, len(cells)):
        if abs(int(cells[k]) - int(cells[k - 1])) > neighbour:
            segments.append((start, k - 1))
            start = k
    segments.append((start, len(cells) - 1))
    return segments


def is_event(cells: Sequence[int], min_distinct: int = MIN_DISTINCT_CELLS, min_span: int = MIN_SPAN_CELLS) -> bool:
    """The plan's event test: at least ``min_distinct`` distinct cells spanning at least ``min_span`` cells."""
    if not cells:
        return False
    distinct = {int(c) for c in cells}
    return len(distinct) >= min_distinct and (max(distinct) - min(distinct)) >= min_span


@dataclass(frozen=True)
class SequenceEvent:
    """One replay event by the plan's definition, read off one replay's backup list."""

    condition: str
    seed: int
    lap: int
    trigger: str
    rule: str
    travel_sign: int
    start_index: int  # first backup of the segment within the replay
    end_index: int  # last backup, inclusive
    n_backups: int
    n_distinct_cells: int
    span_cells: int
    start_cell: int
    end_cell: int
    direction: str
    sequence_r: float
    agent_cell: int
    distance_from_agent: int  # |start_cell - agent_cell| in cells
    remote: bool


def travel_sign_for(record: Mapping[str, Any]) -> int:
    """+1 when the lap ran east (toward increasing cells), -1 when west."""
    goal = record["goal"]
    if goal == "east":
        return 1
    if goal == "west":
        return -1
    raise ValueError(f"unknown goal {goal!r}")


def agent_cell_for(record: Mapping[str, Any], n_bins: int) -> int:
    """Where the agent is at the pause: the record's ``agent_cell`` when it carries one (M2a step 2 writes it
    for both pauses), else the goal cell of the lap just run."""
    if "agent_cell" in record and record["agent_cell"] is not None:
        return int(record["agent_cell"])
    return n_bins - 1 if travel_sign_for(record) == 1 else 0


def goal_sign_of_row(row: int) -> int:
    """The travel direction of the lap a replayed state belongs to, from its learner row (``experiments
    .linear_track_replay.LinearTrack.position``): rows 0 and -1 are the goal-east laps (travel +1), rows 1 and 2
    the goal-west laps (travel -1)."""
    return 1 if int(row) in (0, -1) else -1


def segment_travel_sign(rows: Sequence[int]) -> int:
    """The majority travel direction of a segment's states (a tie goes to the first state): the direction a
    replayed sequence is read against, so a replay is forward when it runs the way the body ran on the lap
    those states belong to, whatever lap the agent is about to run (docs/prereg/rq1_track_tabular.md)."""
    signs = [goal_sign_of_row(r) for r in rows]
    east = sum(s == 1 for s in signs)
    west = len(signs) - east
    if east == west:
        return signs[0]
    return 1 if east > west else -1


def extract_events(
    record: Mapping[str, Any],
    n_bins: int,
    *,
    min_distinct: int = MIN_DISTINCT_CELLS,
    min_span: int = MIN_SPAN_CELLS,
    remote_cells: int = REMOTE_CELLS,
    neighbour: int = NEIGHBOUR_CELLS,
) -> List[SequenceEvent]:
    """The plan's events in one replay record (``ReplayEvent.to_dict`` plus the track's condition, seed, lap, goal)."""
    cells = [int(c[0]) for c in record["cells"]]
    rows = [int(c[1]) for c in record["cells"]]
    agent = agent_cell_for(record, n_bins)
    events: List[SequenceEvent] = []
    for first, last in link_segments(cells, neighbour):
        segment = cells[first : last + 1]
        if not is_event(segment, min_distinct, min_span):
            continue
        travel = segment_travel_sign(rows[first : last + 1])
        direction, r = sequence_direction([float(c) for c in segment], travel)
        distance = abs(segment[0] - agent)
        events.append(
            SequenceEvent(
                condition=str(record["condition"]), seed=int(record["seed"]), lap=int(record["lap"]),
                trigger=str(record["trigger"]), rule=str(record["rule"]), travel_sign=travel,
                start_index=first, end_index=last, n_backups=last - first + 1,
                n_distinct_cells=len(set(segment)), span_cells=max(segment) - min(segment),
                start_cell=segment[0], end_cell=segment[-1], direction=direction, sequence_r=r,
                agent_cell=agent, distance_from_agent=distance, remote=distance > remote_cells,
            )
        )
    return events


STOP_COLUMNS = ("condition", "seed", "lap", "trigger", "rule", "n_backups", "n_events", "n_reverse", "n_forward",
                "n_neither", "n_remote", "backups_in_events", "mean_span", "mean_length", "mean_abs_r")


def per_stop_rows(records: Iterable[Mapping[str, Any]], n_bins: int, **kwargs: Any) -> List[Dict[str, Any]]:
    """One row per replay (one pause): how many events it held and what they were."""
    rows: List[Dict[str, Any]] = []
    for record in records:
        events = extract_events(record, n_bins, **kwargs)
        n = len(events)
        rows.append({
            "condition": record["condition"], "seed": int(record["seed"]), "lap": int(record["lap"]),
            "trigger": record["trigger"], "rule": record["rule"], "n_backups": int(record["n_backups"]),
            "n_events": n,
            "n_reverse": sum(e.direction == "reverse" for e in events),
            "n_forward": sum(e.direction == "forward" for e in events),
            "n_neither": sum(e.direction == "neither" for e in events),
            "n_remote": sum(e.remote for e in events),
            "backups_in_events": sum(e.n_backups for e in events),
            "mean_span": (sum(e.span_cells for e in events) / n) if n else math.nan,
            "mean_length": (sum(e.n_backups for e in events) / n) if n else math.nan,
            "mean_abs_r": (sum(abs(e.sequence_r) for e in events) / n) if n else math.nan,
        })
    return rows


SEED_METRICS = ("events_per_stop", "stops_with_event", "reverse_share", "forward_share", "neither_share",
                "remote_share", "backups_in_events_share", "mean_span_cells", "mean_length_backups", "mean_abs_sequence_r")


def per_seed_rows(stop_rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Pool a seed's pauses: events per stop, the share of stops with an event, and shares among its events.

    A seed with no event has no direction, remote, span or length share: those read NaN and
    are left out of the intervals (``summarise_by_condition`` reports ``n`` per metric).
    """
    by: Dict[Tuple[str, int], List[Mapping[str, Any]]] = {}
    for row in stop_rows:
        by.setdefault((str(row["condition"]), int(row["seed"])), []).append(row)
    out: List[Dict[str, Any]] = []
    for (condition, seed), rows in sorted(by.items()):
        stops = len(rows)
        events = sum(r["n_events"] for r in rows)
        backups = sum(r["n_backups"] for r in rows)
        in_events = sum(r["backups_in_events"] for r in rows)
        spans = [r["mean_span"] * r["n_events"] for r in rows if r["n_events"]]
        lengths = [r["mean_length"] * r["n_events"] for r in rows if r["n_events"]]
        abs_r = [r["mean_abs_r"] * r["n_events"] for r in rows if r["n_events"]]
        out.append({
            "condition": condition, "seed": seed, "task": "linear_track",
            "events_per_stop": events / stops,
            "stops_with_event": sum(r["n_events"] > 0 for r in rows) / stops,
            "reverse_share": (sum(r["n_reverse"] for r in rows) / events) if events else math.nan,
            "forward_share": (sum(r["n_forward"] for r in rows) / events) if events else math.nan,
            "neither_share": (sum(r["n_neither"] for r in rows) / events) if events else math.nan,
            "remote_share": (sum(r["n_remote"] for r in rows) / events) if events else math.nan,
            "backups_in_events_share": in_events / backups if backups else math.nan,
            "mean_span_cells": (math.fsum(spans) / events) if events else math.nan,
            "mean_length_backups": (math.fsum(lengths) / events) if events else math.nan,
            "mean_abs_sequence_r": (math.fsum(abs_r) / events) if events else math.nan,
        })
    return out


def summarise_by_condition(seed_rows: Sequence[Mapping[str, Any]], n_boot: int = DEFAULT_N_BOOT, seed: int = 0):
    """``analysis.stats.summarise`` over the per-seed metrics, NaN values dropped per metric.

    Every (condition, metric) pair of :data:`SEED_METRICS` is a row: where no seed had a
    value (a condition that produced no event has no direction share) the row reads
    ``n`` 0 with NaN statistics, so an undefined share is visible as such rather than
    missing from the table.
    """
    import pandas as pd

    tidy = tidy_table([{k: v for k, v in r.items()} for r in seed_rows])
    tidy = tidy[~tidy["value"].isna()].reset_index(drop=True)
    table = summarise(tidy, by="condition", n_boot=n_boot, seed=seed)
    conditions = sorted({str(r["condition"]) for r in seed_rows})
    have = {(row.condition, row.metric) for row in table.itertuples(index=False)}
    missing = [
        {"condition": c, "metric": m, "n": 0, "mean": math.nan, "low": math.nan, "high": math.nan, "iqm": math.nan,
         "ci_method": "none"}
        for c in conditions for m in SEED_METRICS if (c, m) not in have
    ]
    if missing:
        table = pd.concat([table, pd.DataFrame(missing, columns=table.columns)], ignore_index=True)
        table = table.sort_values(["condition", "metric"], kind="mergesort").reset_index(drop=True)
    return table


def rate_by_lap(stop_rows: Sequence[Mapping[str, Any]], n_boot: int = DEFAULT_N_BOOT, seed: int = 0) -> List[Dict[str, Any]]:
    """Events per stop by lap index (familiarity), per condition: mean over seeds with a BCa interval."""
    by: Dict[Tuple[str, int], List[float]] = {}
    for row in stop_rows:
        by.setdefault((str(row["condition"]), int(row["lap"])), []).append(float(row["n_events"]))
    out: List[Dict[str, Any]] = []
    for (condition, lap), values in sorted(by.items()):
        arr = np.array(values, dtype=np.float64)
        ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=seed + 7919 * lap + sum(map(ord, condition)))
        out.append({"condition": condition, "lap": lap, "n": int(arr.size), "events_per_stop": ci.estimate,
                    "low": ci.low, "high": ci.high, "stops_with_event": float(np.mean(arr > 0))})
    return out


# --- i/o --------------------------------------------------------------------------------------


def read_events(path: Path) -> List[Dict[str, Any]]:
    import gzip

    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:  # type: ignore[operator]
        return [json.loads(line) for line in fh if line.strip()]


def _fmt(value: Any) -> Any:
    if isinstance(value, float):
        return "nan" if math.isnan(value) else f"{value:.6g}"
    return value


def write_csv(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row.get(k)) for k in columns})


EVENT_COLUMNS = tuple(SequenceEvent.__dataclass_fields__)
RATE_COLUMNS = ("condition", "lap", "n", "events_per_stop", "low", "high", "stops_with_event")


def n_bins_from_manifest(events_path: Path, default: int = 40) -> int:
    manifest = events_path.parent / "track_manifest.json"
    if manifest.exists():
        try:
            return int(json.loads(manifest.read_text())["config"]["n_bins"])
        except (KeyError, ValueError, TypeError):
            pass
    return default


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("events", type=Path, help="track_replay_events.jsonl(.gz) from experiments.linear_track_replay")
    parser.add_argument("--out", type=Path, default=None, help="output directory (default: the events file's directory)")
    parser.add_argument("--n-bins", type=int, default=None, help="track cells (default: the manifest beside the events, else 40)")
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--min-distinct", type=int, default=MIN_DISTINCT_CELLS)
    parser.add_argument("--min-span", type=int, default=MIN_SPAN_CELLS)
    parser.add_argument("--remote-cells", type=int, default=REMOTE_CELLS)
    parser.add_argument("--neighbour", type=int, default=NEIGHBOUR_CELLS, help="largest cell step that keeps two consecutive backups linked")
    args = parser.parse_args(argv)
    out = args.out if args.out is not None else args.events.parent
    n_bins = args.n_bins if args.n_bins is not None else n_bins_from_manifest(args.events)
    records = read_events(args.events)
    kwargs = {"min_distinct": args.min_distinct, "min_span": args.min_span, "remote_cells": args.remote_cells,
              "neighbour": args.neighbour}
    events = [e for r in records for e in extract_events(r, n_bins, **kwargs)]
    stops = per_stop_rows(records, n_bins, **kwargs)
    seeds = per_seed_rows(stops)
    summary = summarise_by_condition(seeds, n_boot=args.n_boot)
    rates = rate_by_lap(stops, n_boot=args.n_boot)
    write_csv(out / OUTPUT_FILES[0], EVENT_COLUMNS, (asdict(e) for e in events))
    write_csv(out / OUTPUT_FILES[1], list(summary.columns), [dict(zip(summary.columns, row)) for row in summary.itertuples(index=False)])
    write_csv(out / OUTPUT_FILES[2], RATE_COLUMNS, rates)
    print(f"{len(records)} replays, {len(events)} events (>= {args.min_distinct} distinct cells spanning >= {args.min_span}, "
          f"linked within {args.neighbour} cell{'s' if args.neighbour != 1 else ''})")
    for condition in sorted({r['condition'] for r in records}, key=lambda c: ["none", "uniform", "reverse_trajectory", "prioritised_td"].index(c) if c in ("none", "uniform", "reverse_trajectory", "prioritised_td") else 9):
        rows = summary[summary["condition"] == condition]
        line = ", ".join(f"{r.metric} {r.mean:.3g} [{r.low:.3g}, {r.high:.3g}] (n {r.n})" for r in rows.itertuples(index=False)
                         if r.metric in ("events_per_stop", "stops_with_event", "reverse_share", "remote_share"))
        print(f"  {condition:20s} {line}")
    print(f"wrote {', '.join(OUTPUT_FILES)} to {out}")
    return {"events": events, "stops": stops, "seeds": seeds, "summary": summary, "rates": rates}


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
