"""RQ1 on the tabular linear track, step 2 of the M2a remainder (docs/prereg/rq1_track_tabular.md).

    python3 -m experiments.linear_track_rq1 --workers 4                 # both modes x 4 conditions x seeds 1-30
    python3 -m experiments.linear_track_rq1 --quick --seeds 2 --out /tmp/rq1   # the smoke test's run

The protocol is the fixed evaluation's track and agent (``experiments.linear_track_replay``)
with the preregistered additions: four reward blocks of 20 laps (east 1.0 / 4.0 / 1.0 / 0.25,
west 1.0 throughout), a pre-run pause at the start of every lap beside the reward pause at its
end, and two budget modes, fixed (20 backups per pause) and thresholded (replay while the
rule's priority exceeds theta, at most 100 per pause; theta is 0.0035, set once by the
preregistered pilot rule from the preregistered 0.02). Replay events are read by the
plan's definition (``analysis.replay_metrics``: >= 4 distinct cells over >= 0.3 m, direction
against the travel of the lap the replayed states belong to, remote > 0.5 m from the agent).

Tables (``--out``, default docs/data/m2a/rq1): rq1_pauses.csv.gz (one row per pause: backups,
events, their directions, remote count), rq1_seed_blocks.csv (per condition, mode, seed, block,
end and pause kind: backups and events per stop and the shares), rq1_tests.csv (the
preregistered tests (a)-(d) with estimate, interval, bound and verdict), rq1_adaptation.csv
(steps per lap by block and condition) and rq1_manifest.json; ``--write-events`` adds
rq1_events.jsonl.gz, every replay with its cells (6 MB for the full run, not committed). A
partial run refuses the committed directory: give ``--out``.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from analysis.replay_metrics import extract_events
from analysis.stats import bootstrap_ci, cliffs_delta, paired_effect, pseudo_replication_guard, tost
from brain.systems.replay_events import RULE_NONE, TRIGGER_PRE_RUN, TRIGGER_REWARD
from experiments.linear_track_replay import (
    BUDGET_MODES,
    CONDITIONS,
    DEFAULT_N_BOOT,
    DEFAULT_SEEDS,
    SeedRun,
    TrackConfig,
    _dependency_versions,
    _stat_seed,
    run_all,
    write_csv,
)
from metrics.manifest import build_manifest, finish_manifest, write_manifest

DEFAULT_OUT = Path("docs/data/m2a/rq1")
BLOCKS: Tuple[Tuple[int, float, float], ...] = ((20, 1.0, 1.0), (20, 4.0, 1.0), (20, 1.0, 1.0), (20, 0.25, 1.0))
BLOCK_NAMES = ("baseline", "increase_x4", "washout", "decrease_x0.25")
# theta: 0.02 was the preregistered value; the preregistered pilot rule moved it once, to the median online |TD
# error| of laps 11-20 of the no-replay pilot (0.0035; docs/prereg/rq1_track_tabular.md, "Pilot outcome"; G28).
THRESHOLD = 0.0035
BACKUP_CAP = 100
ENDS = ("east", "west")
TRIGGERS = (TRIGGER_REWARD, TRIGGER_PRE_RUN)
DIRECTION_BOUND = 0.6
REMOTE_BOUND = 0.10
DELTA_BOUND = 0.3
TOST_RELATIVE = 0.2


def protocol_config(mode: str, quick: bool = False) -> TrackConfig:
    """The preregistered protocol in ``mode``; ``quick`` shrinks every block to 2 laps and the cap to 300 steps."""
    if mode not in BUDGET_MODES:
        raise ValueError(f"mode must be one of {BUDGET_MODES}, got {mode!r}")
    blocks = tuple((2, e, w) for _, e, w in BLOCKS) if quick else BLOCKS
    return TrackConfig(
        laps=sum(b[0] for b in blocks), reward_blocks=blocks, pre_run_pause=True, budget_mode=mode,
        threshold=THRESHOLD, backup_cap=BACKUP_CAP,
    )


# --- per pause ----------------------------------------------------------------------------------------


PAUSE_COLUMNS = ("condition", "mode", "seed", "lap", "block", "block_name", "end", "trigger", "lap_rewarded",
                 "n_backups", "n_events", "n_reverse", "n_forward", "n_neither", "n_remote", "backups_in_events")


def pause_rows(run: SeedRun, mode: str, cfg: TrackConfig) -> List[Dict[str, Any]]:
    """One row per pause of a seed's run: the pre-run pause that started each lap and the reward pause that ended it."""
    by_key: Dict[Tuple[str, int], List[Mapping[str, Any]]] = {}
    for event in run.events:
        by_key.setdefault((event["trigger"], int(event["lap"])), []).append(event)
    rows: List[Dict[str, Any]] = []
    for lap in run.laps:
        start_end = "west" if lap.goal == "east" else "east"  # the lap starts at the far end from its goal
        for trigger, end, backups in ((TRIGGER_PRE_RUN, start_end, lap.pre_run_backups), (TRIGGER_REWARD, lap.goal, lap.replay_backups)):
            if trigger == TRIGGER_REWARD and not lap.rewarded:
                continue  # a capped lap has no reward pause
            events = [e for record in by_key.get((trigger, lap.lap), []) for e in extract_events(record, cfg.n_bins)]
            rows.append({
                "condition": run.condition, "mode": mode, "seed": run.seed, "lap": lap.lap, "block": lap.block,
                "block_name": BLOCK_NAMES[lap.block] if lap.block < len(BLOCK_NAMES) else str(lap.block),
                "end": end, "trigger": trigger, "lap_rewarded": lap.rewarded, "n_backups": backups,
                "n_events": len(events), "n_reverse": sum(e.direction == "reverse" for e in events),
                "n_forward": sum(e.direction == "forward" for e in events),
                "n_neither": sum(e.direction == "neither" for e in events),
                "n_remote": sum(e.remote for e in events), "backups_in_events": sum(e.n_backups for e in events),
            })
    return rows


SEED_BLOCK_COLUMNS = ("condition", "mode", "seed", "block", "block_name", "end", "trigger", "stops", "backups_per_stop",
                      "events_per_stop", "reverse_per_stop", "forward_per_stop", "remote_per_stop", "reverse_share",
                      "forward_share", "remote_share")


def seed_block_rows(pauses: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by: Dict[Tuple[Any, ...], List[Mapping[str, Any]]] = {}
    for p in pauses:
        by.setdefault((p["condition"], p["mode"], int(p["seed"]), int(p["block"]), p["end"], p["trigger"]), []).append(p)
    out: List[Dict[str, Any]] = []
    for key, rows in sorted(by.items(), key=lambda kv: (CONDITIONS.index(kv[0][0]), kv[0][1:])):
        condition, mode, seed, block, end, trigger = key
        stops = len(rows)
        events = sum(r["n_events"] for r in rows)
        rev, fwd, rem = (sum(r[k] for r in rows) for k in ("n_reverse", "n_forward", "n_remote"))
        out.append({
            "condition": condition, "mode": mode, "seed": seed, "block": block, "block_name": rows[0]["block_name"],
            "end": end, "trigger": trigger, "stops": stops,
            "backups_per_stop": sum(r["n_backups"] for r in rows) / stops,
            "events_per_stop": events / stops, "reverse_per_stop": rev / stops, "forward_per_stop": fwd / stops,
            "remote_per_stop": rem / stops,
            "reverse_share": rev / events if events else math.nan,
            "forward_share": fwd / events if events else math.nan,
            "remote_share": rem / events if events else math.nan,
        })
    return out


# --- the preregistered tests --------------------------------------------------------------------------


TEST_COLUMNS = ("test", "condition", "mode", "statistic", "n", "estimate", "low", "high", "extra", "bound", "verdict", "note")


def _per_seed(rows: Sequence[Mapping[str, Any]], condition: str, mode: str, metric: str, *, blocks: Sequence[int],
              ends: Sequence[str], trigger: str, pooled: bool = True) -> Dict[int, float]:
    """Per seed, ``metric`` pooled (stop-weighted) over the given blocks, ends and pause kind; shares pool their counts."""
    out: Dict[int, float] = {}
    seeds = sorted({int(r["seed"]) for r in rows if r["condition"] == condition and r["mode"] == mode})
    for seed in seeds:
        sel = [r for r in rows if r["condition"] == condition and r["mode"] == mode and int(r["seed"]) == seed
               and int(r["block"]) in blocks and r["end"] in ends and r["trigger"] == trigger]
        if not sel:
            continue
        if metric.endswith("_share"):
            numer = metric.replace("_share", "_per_stop")
            events = math.fsum(r["events_per_stop"] * r["stops"] for r in sel)
            out[seed] = math.fsum(r[numer] * r["stops"] for r in sel) / events if events else math.nan
        else:
            stops = sum(r["stops"] for r in sel)
            out[seed] = math.fsum(r[metric] * r["stops"] for r in sel) / stops if stops else math.nan
    return out


def _ci_row(test: str, condition: str, mode: str, statistic: str, values: Mapping[int, float], n_boot: int,
            bound: str, verdict_fn, extra: str = "") -> Dict[str, Any]:
    arr = np.array([v for v in values.values() if not (isinstance(v, float) and math.isnan(v))], dtype=np.float64)
    if arr.size == 0:
        return {"test": test, "condition": condition, "mode": mode, "statistic": statistic, "n": 0, "estimate": math.nan,
                "low": math.nan, "high": math.nan, "extra": extra, "bound": bound, "verdict": "undefined (no events)", "note": ""}
    ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed(test, condition, mode, statistic))
    return {"test": test, "condition": condition, "mode": mode, "statistic": statistic, "n": int(arr.size),
            "estimate": ci.estimate, "low": ci.low, "high": ci.high, "extra": extra, "bound": bound,
            "verdict": verdict_fn(ci), "note": ci.note}


def _paired_row(test: str, condition: str, mode: str, statistic: str, a: Mapping[int, float], b: Mapping[int, float],
                n_boot: int, bound: str, expect: str) -> Dict[str, Any]:
    """``b - a`` paired by seed with Cliff's delta; ``expect`` is "up", "down" or "unchanged" (TOST)."""
    seeds = sorted(s for s in a if s in b and not math.isnan(a[s]) and not math.isnan(b[s]))
    va = np.array([a[s] for s in seeds], dtype=np.float64)
    vb = np.array([b[s] for s in seeds], dtype=np.float64)
    if len(seeds) < 2:
        return {"test": test, "condition": condition, "mode": mode, "statistic": statistic, "n": len(seeds), "estimate": math.nan,
                "low": math.nan, "high": math.nan, "extra": "", "bound": bound, "verdict": "undefined", "note": "fewer than two seeds"}
    eff = paired_effect(va, vb, n_boot=n_boot, seed=_stat_seed(test, condition, mode, statistic, "paired"))
    delta = cliffs_delta(va, vb, n_boot=n_boot, seed=_stat_seed(test, condition, mode, statistic, "cliff"))
    extra = f"delta {delta['delta']:+.3f} [{delta['low']:+.3f}, {delta['high']:+.3f}] ({delta['magnitude']}); mean_a {eff['mean_a']:.4g}, mean_b {eff['mean_b']:.4g}"
    notes = [n for n in (eff["note"], delta["note"]) if n]
    if expect == "up":
        verdict = "passes" if (delta["delta"] >= DELTA_BOUND and eff["low"] > 0.0) else "fails"
    elif expect == "down":
        verdict = "passes" if (delta["delta"] <= -DELTA_BOUND and eff["high"] < 0.0) else "fails"
    else:
        if np.all(va == va[0]) and np.all(vb == vb[0]) and va[0] == vb[0]:
            verdict, extra = "degenerate (every value identical)", extra + "; rates constant"
        else:
            eq = tost(va, vb, -TOST_RELATIVE, TOST_RELATIVE, relative=True, paired=True, n_boot=n_boot,
                      seed=_stat_seed(test, condition, mode, statistic, "tost"))
            verdict = "equivalent (TOST)" if eq["equivalent"] else "not shown equivalent (TOST)"
            extra += (f"; tost {eq['ci_level']:.0%} CI [{eq['ci_low']:.4g}, {eq['ci_high']:.4g}] against bounds "
                      f"[{eq['bound_low']:.4g}, {eq['bound_high']:.4g}]")
            if eq.get("note"):
                notes.append(str(eq["note"]))
    return {"test": test, "condition": condition, "mode": mode, "statistic": statistic, "n": len(seeds),
            "estimate": eff["mean_diff"], "low": eff["low"], "high": eff["high"], "extra": extra, "bound": bound,
            "verdict": verdict, "note": "; ".join(notes)}


def _slope_rows(pauses: Sequence[Mapping[str, Any]], condition: str, mode: str, metric: str, n_boot: int) -> Dict[str, Any]:
    """(c) per-seed slope of ``metric`` per stop against lap within block 1 (reward pauses, both ends)."""
    slopes: Dict[int, float] = {}
    seeds = sorted({int(p["seed"]) for p in pauses if p["condition"] == condition and p["mode"] == mode})
    for seed in seeds:
        sel = [p for p in pauses if p["condition"] == condition and p["mode"] == mode and int(p["seed"]) == seed
               and int(p["block"]) == 0 and p["trigger"] == TRIGGER_REWARD]
        xs = [float(p["lap"]) for p in sel]
        ys = [float(p[metric]) for p in sel]
        if len(xs) < 2:
            continue
        mx, my = math.fsum(xs) / len(xs), math.fsum(ys) / len(ys)
        sxx = math.fsum((x - mx) ** 2 for x in xs)
        slopes[seed] = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else math.nan
    return _ci_row("c_familiarity", condition, mode, f"slope_of_{metric}_vs_lap_block1", slopes, n_boot,
                   "slope < 0, interval excluding 0", lambda ci: "passes" if ci.high < 0.0 else "fails")


def rq1_tests(seed_blocks: Sequence[Mapping[str, Any]], pauses: Sequence[Mapping[str, Any]], conditions: Sequence[str],
              modes: Sequence[str], n_boot: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    gt = lambda bound: (lambda ci: "passes" if ci.low > bound else ("fails" if ci.estimate <= bound else "estimate above, interval not"))  # noqa: E731
    for condition in conditions:
        if condition == RULE_NONE:
            continue
        if "fixed" in modes:
            # (a) direction by window: blocks 1 and 3 (unchanged rewards), both ends.
            rev = _per_seed(seed_blocks, condition, "fixed", "reverse_share", blocks=(0, 2), ends=ENDS, trigger=TRIGGER_REWARD)
            rows.append(_ci_row("a_direction", condition, "fixed", "reverse_share_reward_pauses", rev, n_boot, f"> {DIRECTION_BOUND}", gt(DIRECTION_BOUND)))
            fwd = _per_seed(seed_blocks, condition, "fixed", "forward_share", blocks=(0, 2), ends=ENDS, trigger=TRIGGER_PRE_RUN)
            rows.append(_ci_row("a_direction", condition, "fixed", "forward_share_pre_run_pauses", fwd, n_boot, f"> {DIRECTION_BOUND}", gt(DIRECTION_BOUND)))
            # (d) remote events: all pauses, all blocks.
            rem_r = _per_seed(seed_blocks, condition, "fixed", "remote_share", blocks=(0, 1, 2, 3), ends=ENDS, trigger=TRIGGER_REWARD)
            rem_p = _per_seed(seed_blocks, condition, "fixed", "remote_share", blocks=(0, 1, 2, 3), ends=ENDS, trigger=TRIGGER_PRE_RUN)
            rows.append(_ci_row("d_remote", condition, "fixed", "remote_share_reward_pauses", rem_r, n_boot, f">= {REMOTE_BOUND}",
                                lambda ci: "passes" if ci.estimate >= REMOTE_BOUND else "fails"))
            rows.append(_ci_row("d_remote", condition, "fixed", "remote_share_pre_run_pauses", rem_p, n_boot, f">= {REMOTE_BOUND}",
                                lambda ci: "passes" if ci.estimate >= REMOTE_BOUND else "fails"))
        if "thresholded" in modes:
            # (b) rate and reward change at the east end (reward pauses), the west end as the control.
            for metric in ("reverse_per_stop", "backups_per_stop", "events_per_stop"):
                for end in ENDS:
                    pre = _per_seed(seed_blocks, condition, "thresholded", metric, blocks=(0,), ends=(end,), trigger=TRIGGER_REWARD)
                    inc = _per_seed(seed_blocks, condition, "thresholded", metric, blocks=(1,), ends=(end,), trigger=TRIGGER_REWARD)
                    wash = _per_seed(seed_blocks, condition, "thresholded", metric, blocks=(2,), ends=(end,), trigger=TRIGGER_REWARD)
                    dec = _per_seed(seed_blocks, condition, "thresholded", metric, blocks=(3,), ends=(end,), trigger=TRIGGER_REWARD)
                    if end == "east":
                        rows.append(_paired_row("b_rate_increase", condition, "thresholded", f"{metric}_east_block2_minus_block1", pre, inc, n_boot,
                                                f"up: delta >= {DELTA_BOUND}, interval > 0", "up"))
                        rows.append(_paired_row("b_rate_decrease", condition, "thresholded", f"{metric}_east_block4_minus_block3", wash, dec, n_boot,
                                                f"down: delta <= -{DELTA_BOUND}, interval < 0", "down"))
                    else:
                        rows.append(_paired_row("b_control_end", condition, "thresholded", f"{metric}_west_block2_minus_block1", pre, inc, n_boot,
                                                f"unchanged: TOST +-{TOST_RELATIVE:.0%}", "unchanged"))
                        rows.append(_paired_row("b_control_end", condition, "thresholded", f"{metric}_west_block4_minus_block3", wash, dec, n_boot,
                                                f"unchanged: TOST +-{TOST_RELATIVE:.0%}", "unchanged"))
            fpre = _per_seed(seed_blocks, condition, "thresholded", "forward_per_stop", blocks=(0,), ends=("east",), trigger=TRIGGER_REWARD)
            finc = _per_seed(seed_blocks, condition, "thresholded", "forward_per_stop", blocks=(1,), ends=("east",), trigger=TRIGGER_REWARD)
            rows.append(_paired_row("b_forward_unchanged", condition, "thresholded", "forward_per_stop_east_block2_minus_block1", fpre, finc, n_boot,
                                    f"unchanged: TOST +-{TOST_RELATIVE:.0%}", "unchanged"))
            # (c) familiarity within block 1.
            rows.append(_slope_rows(pauses, condition, "thresholded", "n_backups", n_boot))
            rows.append(_slope_rows(pauses, condition, "thresholded", "n_events", n_boot))
    return rows


ADAPTATION_COLUMNS = ("condition", "mode", "block", "block_name", "lap_in_block", "n", "mean_steps", "low", "high", "median_steps", "fraction_capped")


def adaptation_rows(runs: Sequence[SeedRun], mode: str, n_boot: int) -> List[Dict[str, Any]]:
    """Steps per lap by block and lap-in-block, per condition, for the runs of one ``mode``: how fast each re-learns a changed reward."""
    by: Dict[Tuple[str, str, int, int], List[Tuple[float, bool]]] = {}
    for run in runs:
        starts: Dict[int, int] = {}
        for lap in run.laps:
            starts.setdefault(lap.block, lap.lap)
            by.setdefault((run.condition, mode, lap.block, lap.lap - starts[lap.block] + 1), []).append((float(lap.steps), lap.rewarded))
    out: List[Dict[str, Any]] = []
    for (condition, mode, block, k), values in sorted(by.items(), key=lambda kv: (CONDITIONS.index(kv[0][0]), kv[0][1:])):
        arr = np.array([v for v, _ in values], dtype=np.float64)
        ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed("adapt", condition, mode, block, k))
        out.append({"condition": condition, "mode": mode, "block": block,
                    "block_name": BLOCK_NAMES[block] if block < len(BLOCK_NAMES) else str(block), "lap_in_block": k,
                    "n": int(arr.size), "mean_steps": ci.estimate, "low": ci.low, "high": ci.high,
                    "median_steps": float(np.median(arr)), "fraction_capped": float(np.mean([not r for _, r in values]))})
    return out


# --- the run --------------------------------------------------------------------------------------------


OUTPUT_FILES = ("rq1_pauses.csv.gz", "rq1_seed_blocks.csv", "rq1_tests.csv", "rq1_adaptation.csv", "rq1_manifest.json")
EVENTS_FILE = "rq1_events.jsonl.gz"  # written with --write-events only (6 MB for the full run; the pause table carries the counts)


def write_csv_gz(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    """``write_csv`` into a gzip file with a fixed header time, so two runs write identical bytes."""
    import csv
    import io

    from experiments.linear_track_replay import _fmt

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _fmt(row.get(k)) for k in columns})
    with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as fh:
        fh.write(buffer.getvalue().encode("utf-8"))


def read_csv_gz(path: Path) -> List[Dict[str, Any]]:
    import csv

    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_events(path: Path, events: Iterable[Mapping[str, Any]]) -> int:
    written = 0
    with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as fh:
        for event in events:
            fh.write((json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
            written += 1
    return written


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modes", default=",".join(BUDGET_MODES))
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEEDS[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--quick", action="store_true", help="blocks of 2 laps, 200 replicates; needs --out")
    parser.add_argument("--write-events", action="store_true", help=f"also write every replay with its cells to {EVENTS_FILE} (about 6 MB for the full run)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    conditions = tuple(c.strip() for c in args.conditions.split(",") if c.strip())
    for m in modes:
        if m not in BUDGET_MODES:
            parser.error(f"unknown mode {m!r}")
    for c in conditions:
        if c not in CONDITIONS:
            parser.error(f"unknown condition {c!r}")
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    full = (modes == BUDGET_MODES and conditions == CONDITIONS and tuple(seeds) == DEFAULT_SEEDS and not args.quick and n_boot >= 1000)
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a partial run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    started = time.perf_counter()
    runs_by_mode: Dict[str, List[SeedRun]] = {}
    pauses: List[Dict[str, Any]] = []
    events: List[Mapping[str, Any]] = []
    configs = {mode: protocol_config(mode, args.quick) for mode in modes}
    guard: Dict[str, Any] = {}
    for mode in modes:
        cfg = configs[mode]
        mode_runs = run_all(conditions, seeds, cfg, args.workers)
        runs_by_mode[mode] = mode_runs
        for run in mode_runs:
            pauses.extend(pause_rows(run, mode, cfg))
            events.extend({**e, "mode": mode} for e in run.events)
        for c in conditions:
            vectors = [{"seed": r.seed, "steps": [lap.steps for lap in r.laps]} for r in mode_runs if r.condition == c]
            verdict = pseudo_replication_guard(vectors, key="steps", allow=True)
            guard[f"{mode}/{c}"] = {"distinct": verdict if isinstance(verdict, int) else None, "n": len(vectors),
                                    "message": verdict if isinstance(verdict, str) else ""}
    runs: List[SeedRun] = [r for mode in modes for r in runs_by_mode[mode]]
    seed_blocks = seed_block_rows(pauses)
    tests = rq1_tests(seed_blocks, pauses, conditions, modes, n_boot)
    adaptation: List[Dict[str, Any]] = []
    for mode in modes:
        adaptation.extend(adaptation_rows(runs_by_mode[mode], mode, n_boot))
    manifest = build_manifest(
        configs[modes[0]], protocol="linear_track_rq1", seeds=seeds,
        ticks_requested=sum(configs[m].laps * configs[m].lap_cap * len(conditions) for m in modes),
        extra={"modes": list(modes), "configs": {m: configs[m].to_dict() for m in modes}, "conditions": list(conditions),
               "blocks": [list(b) for b in configs[modes[0]].blocks()], "block_names": list(BLOCK_NAMES),
               "threshold": THRESHOLD, "backup_cap": BACKUP_CAP, "n_boot": n_boot, "full_evaluation": full, "quick": args.quick,
               "prereg": "docs/prereg/rq1_track_tabular.md", "dependencies": _dependency_versions(),
               "command": "python3 -m experiments.linear_track_rq1 " + " ".join(list(argv) if argv is not None else sys.argv[1:])},
    )
    manifest["guard"] = guard
    manifest["workers"] = args.workers if args.workers is not None else os.cpu_count()
    finish_manifest(manifest, ticks_run=sum(lap.steps for r in runs for lap in r.laps), wall_seconds=time.perf_counter() - started)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_csv_gz(out / OUTPUT_FILES[0], PAUSE_COLUMNS, pauses)
    write_csv(out / OUTPUT_FILES[1], SEED_BLOCK_COLUMNS, seed_blocks)
    write_csv(out / OUTPUT_FILES[2], TEST_COLUMNS, tests)
    write_csv(out / OUTPUT_FILES[3], ADAPTATION_COLUMNS, adaptation)
    written = [out / name for name in OUTPUT_FILES]
    if args.write_events:
        write_events(out / EVENTS_FILE, events)
        written.append(out / EVENTS_FILE)
    write_manifest(out / OUTPUT_FILES[4], manifest)
    print("preregistered tests (docs/prereg/rq1_track_tabular.md):")
    for t in tests:
        est = "nan" if math.isnan(t["estimate"]) else f"{t['estimate']:.4g} [{t['low']:.4g}, {t['high']:.4g}]"
        print(f"  {t['test']:18s} {t['condition']:20s} {t['mode']:11s} {t['statistic']:46s} n {t['n']:>2} {est:34s} {t['verdict']}")
    print(f"guard: {guard}")
    print(f"wrote {', '.join(p.name for p in written)} to {out} in {manifest['timing']['wall_seconds']:.1f} s")
    return {"pauses": pauses, "seed_blocks": seed_blocks, "tests": tests, "adaptation": adaptation, "guard": guard,
            "runs_by_mode": runs_by_mode, "events": events}


if __name__ == "__main__":
    main()
