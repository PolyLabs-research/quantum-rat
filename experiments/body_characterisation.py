"""The body on the track and in the open field (M3 step 1, ``docs/prereg/m3_body.md``; decisions G44).

Each condition is a set of config overrides on ``EngineConfig.research()``: by default the three body presets of
``core.body.BODY_PRESETS`` (``discrete``, today's body; ``rodent_quiet``; ``rodent``, with RatInABox's noise). Each
runs on two worlds for every seed:

- **track**: bounds 10 x 0.5 units (2 m x 0.1 m, the plan's track). Laps are traversals between the two end zones
  (within 1 unit of either end); per run: laps, the median ticks per lap (3,000 when no lap completed), the FORWARD
  share, the wall-contact share (on any bound), the stall share (FORWARD ticks with displacement below 1e-6 units:
  Amendment 1), the late median estimate error (ticks 1,000-2,999).
- **open field**: bounds 10 x 10 units (2 m x 2 m). Mean and sd of speed (m/s), sd of angular velocity (rad/s), the
  share of ticks within 0.1 m of a wall, coverage (share of the 400 one-unit bins visited), the stall share, the
  late median estimate error, and the orbit share (``analysis.orbits``, the G40 definition).

T1 (the registered primary bound) per condition: the mean over seeds of the median ticks per lap at most 36 and of
the stall share below 0.05, each with its BCa 95% interval's upper end below the bound.

    python -m experiments.body_characterisation --workers 4 --prereg docs/prereg/m3_body.md --out docs/data/m3/body
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.engine import Engine  # noqa: I001  (core pins the BLAS thread counts before numpy: docs/determinism.md rule 2)

import numpy as np

from analysis.orbits import summarise as orbit_summary
from analysis.stats import bootstrap_ci, pseudo_replication_guard
from core.body import BODY_PRESETS
from core.config import EngineConfig
from metrics.manifest import build_manifest, finish_manifest, write_manifest

TRACK_BOUNDS = (10.0, 0.5)
OPEN_BOUNDS = (10.0, 10.0)
END_ZONE = 1.0
TICKS = 3000
LATE_FROM = 1000
DEFAULT_SEEDS: Tuple[int, ...] = tuple(range(1, 31))
QUICK_SEEDS: Tuple[int, ...] = (1, 2)
QUICK_TICKS = 300
STRAIGHT_RUN = 18  # ticks for a straight 2 m lap between the end zones at 1 unit per tick
T1_LAP_BOUND = 2 * STRAIGHT_RUN
T1_STALL_BOUND = 0.05
STALL_EPS = 1e-6
DEFAULT_CONDITIONS: Dict[str, Dict[str, Any]] = {name: dict(fields) for name, fields in BODY_PRESETS.items()}
PREREGS = {"docs/prereg/m3_body.md": {"seeds": DEFAULT_SEEDS, "conditions": tuple(DEFAULT_CONDITIONS), "out": Path("docs/data/m3/body")}}
OUTPUT_FILES = ("body_per_seed.csv", "body_summary.json", "manifest.json")
METRICS = {
    "track": ("laps", "ticks_per_lap", "forward_share", "wall_contact_share", "stall_share", "estimate_error_late"),
    "open": ("speed_mean", "speed_sd", "angular_velocity_sd", "wall_zone_share", "coverage", "stall_share",
             "estimate_error_late", "orbit_share"),
}


def condition_config(overrides: Mapping[str, Any], bounds: Tuple[float, float]) -> EngineConfig:
    cfg = EngineConfig.research()
    cfg.world.bounds = tuple(bounds)
    for key, value in overrides.items():
        cfg.set_field(key, value)
    return cfg


def run_world(world: str, overrides: Mapping[str, Any], seed: int, ticks: int) -> Dict[str, Any]:
    bounds = TRACK_BOUNDS if world == "track" else OPEN_BOUNDS
    cfg = condition_config(overrides, bounds)
    eng = Engine(seed=seed, config=cfg)
    eng.run(1, reset=True)
    units = cfg.units
    bx, by = bounds
    prev = eng.agent.pos
    prev_h = eng.agent.heading
    n = fwd = stall = wall = zone = 0
    speeds: List[float] = []
    omegas: List[float] = []
    errors: List[float] = []
    visited = set()
    laps: List[int] = []
    last_end: Optional[int] = None
    lap_start = 0
    records: List[Dict[str, Any]] = []
    for t in range(ticks):
        td = eng.run(1)[0]
        x, y = td.pos
        h = eng.agent.heading
        step = math.hypot(x - prev[0], y - prev[1])
        n += 1
        a = td.action_name
        fwd += a == "FORWARD"
        stall += a == "FORWARD" and step < STALL_EPS
        wall += abs(x) >= bx - 1e-9 or abs(y) >= by - 1e-9
        zone += abs(x) >= bx - 1.0 or abs(y) >= by - 1.0
        speeds.append(step * units.metres_per_unit / units.dt_s)
        omegas.append((h - prev_h) / units.dt_s)
        if t >= (LATE_FROM if ticks >= 2 * LATE_FROM else ticks // 3):  # a short (quick) run reads its last two thirds
            st = eng.spatial.state
            errors.append(math.hypot(st.grid_x - x, st.grid_y - y))
        visited.add((math.floor(x), math.floor(y)))
        if world == "track":
            end = -1 if x <= -bx + END_ZONE else (1 if x >= bx - END_ZONE else None)
            if end is not None and end != last_end:
                if last_end is not None:
                    laps.append(t - lap_start)
                last_end, lap_start = end, t
        else:
            records.append({"tick": td.tick, "episode": eng.episode, "x": x, "y": y, "heading": h, "action": a,
                            "target_contact": False, "reward": 0.0})
        prev, prev_h = (x, y), h
    out: Dict[str, Any] = {"stall_share": stall / n, "estimate_error_late": float(np.median(errors)) if errors else math.nan}
    if world == "track":
        out.update({"laps": len(laps), "ticks_per_lap": float(np.median(laps)) if laps else float(ticks),
                    "forward_share": fwd / n, "wall_contact_share": wall / n})
    else:
        bins = (2 * int(bx)) * (2 * int(by))
        out.update({"speed_mean": float(np.mean(speeds)), "speed_sd": float(np.std(speeds)),
                    "angular_velocity_sd": float(np.std(omegas)), "wall_zone_share": zone / n,
                    "coverage": len(visited) / bins, "orbit_share": orbit_summary(records)["orbit_fraction"]})
    return out


def run_one(job: Tuple[str, Dict[str, Any], int, int]) -> Dict[str, Any]:
    name, overrides, seed, ticks = job
    return {"condition": name, "seed": seed,
            "track": run_world("track", overrides, seed, ticks), "open": run_world("open", overrides, seed, ticks)}


def run_all(conditions: Mapping[str, Mapping[str, Any]], seeds: Sequence[int], ticks: int, workers: Optional[int]) -> List[Dict[str, Any]]:
    jobs = [(name, dict(overrides), seed, ticks) for name, overrides in conditions.items() for seed in seeds]
    if workers == 1 or len(jobs) == 1:
        return [run_one(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_one, jobs, chunksize=1))


def _ci(values: Sequence[float], n_boot: int) -> Dict[str, Any]:
    ci = bootstrap_ci(np.asarray(values, dtype=float), n_boot=n_boot)
    return {"mean": ci.estimate, "low": ci.low, "high": ci.high, "n": ci.n, "note": ci.note}


def summarise(results: Sequence[Mapping[str, Any]], conditions: Sequence[str], n_boot: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name in conditions:
        rows = [r for r in results if r["condition"] == name]
        entry: Dict[str, Any] = {}
        for world, metrics in METRICS.items():
            entry[world] = {m: _ci([r[world][m] for r in rows], n_boot) for m in metrics}
        lap, stall = entry["track"]["ticks_per_lap"], entry["track"]["stall_share"]
        entry["T1"] = {"ticks_per_lap_mean": lap["mean"], "ticks_per_lap_high": lap["high"], "lap_bound": T1_LAP_BOUND,
                       "stall_mean": stall["mean"], "stall_high": stall["high"], "stall_bound": T1_STALL_BOUND,
                       "passes": bool(lap["high"] < T1_LAP_BOUND and stall["high"] < T1_STALL_BOUND)}
        out[name] = entry
    return out


def write_per_seed(path: Path, results: Sequence[Mapping[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "task", "seed", "metric", "value"])
        for r in sorted(results, key=lambda r: (r["condition"], r["seed"])):
            for world, metrics in METRICS.items():
                for m in metrics:
                    w.writerow([r["condition"], world, r["seed"], m, r[world][m]])


def format_summary(summary: Mapping[str, Any]) -> str:
    lines = [f"{'condition':<14}{'lap ticks':>11}{'stalls':>9}{'FORWARD':>9}{'wall':>7}{'track err':>10}"
             f"{'speed m/s':>10}{'omega sd':>9}{'near wall':>10}{'coverage':>9}{'orbits':>8}{'field err':>10}  T1"]
    for name, e in summary.items():
        t, o = e["track"], e["open"]
        lines.append(f"{name:<14}{t['ticks_per_lap']['mean']:>11.1f}{t['stall_share']['mean']:>9.1%}{t['forward_share']['mean']:>9.0%}"
                     f"{t['wall_contact_share']['mean']:>7.0%}{t['estimate_error_late']['mean']:>10.2f}{o['speed_mean']['mean']:>10.3f}"
                     f"{o['angular_velocity_sd']['mean']:>9.2f}{o['wall_zone_share']['mean']:>10.0%}{o['coverage']['mean']:>9.0%}"
                     f"{o['orbit_share']['mean']:>8.0%}{o['estimate_error_late']['mean']:>10.2f}  "
                     f"{'PASS' if e['T1']['passes'] else 'fail'} (laps [{t['ticks_per_lap']['low']:.1f}, {t['ticks_per_lap']['high']:.1f}],"
                     f" stalls [{t['stall_share']['low']:.1%}, {t['stall_share']['high']:.1%}])")
    return "\n".join(lines)


def parse_set(items: Sequence[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in items or ():
        key, _, value = item.partition("=")
        try:
            out[key.strip()] = json.loads(value)
        except json.JSONDecodeError:
            out[key.strip()] = value
    return out


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", default=None, help="e.g. 1-30 (default 1-30; --quick: 1,2)")
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--conditions", default=None, help="comma-separated body presets (default: all three)")
    parser.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE",
                        help="an override applied to every condition (repeatable); a run with any is exploratory")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=10_000)
    parser.add_argument("--prereg", default=None, help="the preregistration this run answers to (recorded; a run away from its settings is marked exploratory)")
    parser.add_argument("--quick", action="store_true", help=f"{len(QUICK_SEEDS)} seeds x {QUICK_TICKS} ticks; needs --out")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.seeds:
        a, _, b = args.seeds.partition("-")
        seeds: Tuple[int, ...] = tuple(range(int(a), int(b) + 1)) if b else tuple(int(s) for s in args.seeds.split(","))
    else:
        seeds = QUICK_SEEDS if args.quick else DEFAULT_SEEDS
    ticks = args.ticks or (QUICK_TICKS if args.quick else TICKS)
    names = tuple(args.conditions.split(",")) if args.conditions else tuple(DEFAULT_CONDITIONS)
    shared = parse_set(args.set)
    conditions = {name: {**DEFAULT_CONDITIONS[name], **shared} for name in names}
    spec = PREREGS.get(args.prereg) if args.prereg else None
    full = bool(spec and seeds == spec["seeds"] and names == spec["conditions"] and not shared and not args.quick
                and ticks == TICKS and args.n_boot >= 1000)
    for committed in (p["out"] for p in PREREGS.values()):
        if args.out.resolve() == committed.resolve() and not full:
            parser.error(f"a partial or exploratory run must not overwrite the committed tables in {committed}: give another --out")
    started = time.perf_counter()
    results = run_all(conditions, seeds, ticks, args.workers)
    guard = {name: pseudo_replication_guard([r["track"]["estimate_error_late"] + r["open"]["speed_mean"] for r in results
                                             if r["condition"] == name], allow=True) for name in names}
    summary = summarise(results, names, min(args.n_boot, 200) if args.quick else args.n_boot)
    wall = time.perf_counter() - started
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_per_seed(out / OUTPUT_FILES[0], results)
    payload = {"conditions": conditions, "seeds": list(seeds), "ticks": ticks, "prereg": args.prereg, "exploratory": not full,
               "guard": guard, "t1_bounds": {"ticks_per_lap": T1_LAP_BOUND, "stall_share": T1_STALL_BOUND},
               "summary": summary, "wall_seconds": round(wall, 1)}
    (out / OUTPUT_FILES[1]).write_text(json.dumps(payload, indent=1, sort_keys=True, default=float))
    manifest = build_manifest(condition_config(conditions[names[0]], TRACK_BOUNDS), protocol="body_characterisation",
                              seeds=list(seeds), ticks_requested=ticks * len(seeds) * len(names) * 2,
                              extra={"conditions": conditions, "prereg": args.prereg, "exploratory": not full,
                                     "worlds": {"track": list(TRACK_BOUNDS), "open": list(OPEN_BOUNDS)},
                                     "experiment": "experiments.body_characterisation"})
    finish_manifest(manifest, ticks_run=ticks * len(seeds) * len(names) * 2, wall_seconds=wall)
    write_manifest(out / OUTPUT_FILES[2], manifest)
    print(format_summary(summary))
    print(f"{'' if full else 'EXPLORATORY: not the preregistered settings. '}wrote {out} ({wall:.0f} s)")
    return payload


if __name__ == "__main__":
    main()
