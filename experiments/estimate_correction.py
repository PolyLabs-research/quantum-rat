"""M2b step 1: the corrected position estimate, characterised (docs/prereg/m2b_estimate.md).

    python3 -m experiments.estimate_correction --workers 4               # 30 seeds x 8 runs, writes docs/data/m2b/estimate
    python3 -m experiments.estimate_correction --quick --seeds 2 --out /tmp/est   # the smoke test's run

The research profile in the default 2 m box (bounds 10 x 10 units), no objects, 3,000 ticks (10 min) per run, with the
declared heading oracle and wall-contact sensing on in every run (so every run's Observation stream, and so its body
walk, is the same for a seed; only the estimate differs). Four conditions cross the heading source with the
wall-contact reset: ``integrated`` (the research estimate so far: the summed egomotion turn, no reset),
``integrated_reset``, ``oracle`` (the oracle's heading, no reset) and ``oracle_reset`` (the M2b estimate), all at the
oracle error ``ORACLE_NOISE``; ``oracle_reset`` is also run at each of ``SENSITIVITY_NOISES``.

Tables (``--out``): estimate_per_seed.csv (per run: the error levels, the heading error, contacts and resets, the
wrong-wall share, the drop at contact, and a digest of the body walk), estimate_curve.csv (mean error every 25 ticks
per condition with BCa intervals), estimate_effects.csv (paired comparisons and the preregistered tests),
estimate_contacts.csv.gz (one row per contact onset: the walls touched and reset, the error before and after) and
estimate_manifest.json. A partial run refuses the committed directory: give ``--out``.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from analysis.stats import bootstrap_ci, cliffs_delta, paired_effect, pseudo_replication_guard
from brain.systems.spatial import wrap_angle
from core.config import EngineConfig
from core.engine import Engine
from experiments.linear_track_replay import _dependency_versions, _stat_seed, write_csv
from experiments.linear_track_rq1 import write_csv_gz
from metrics.manifest import build_manifest, finish_manifest, write_manifest

CONDITIONS: Dict[str, Dict[str, Any]] = {
    "integrated": {"heading_source": "integrated", "wall_reset": False},
    "integrated_reset": {"heading_source": "integrated", "wall_reset": True},
    "oracle": {"heading_source": "oracle", "wall_reset": False},
    "oracle_reset": {"heading_source": "oracle", "wall_reset": True},
}
ORACLE_NOISE = 0.05  # radians, sd of the oracle's per-tick heading error (preregistered)
SENSITIVITY_NOISES: Tuple[float, ...] = (0.0, 0.02, 0.1, 0.2)  # oracle_reset only
TICKS = 3000  # 600 s at dt 0.2 s
LATE_FROM = 1001  # the late window: ticks 1001-3000 (the second and third thirds)
SAMPLE_EVERY = 25
BOUND_UNITS = 2.0  # 0.2 m: RQ4(a)'s arrival bound, here read on the open-field estimate
DELTA_BOUND = 0.3
WRONG_WALL_BOUND = 0.01
DEFAULT_SEEDS: Tuple[int, ...] = tuple(range(1, 31))
DEFAULT_OUT = Path("docs/data/m2b/estimate")
DEFAULT_N_BOOT = 10_000
QUICK_TICKS = 300


@dataclass(frozen=True)
class Run:
    """One (condition, oracle noise) cell: the label the tables carry."""

    condition: str
    oracle_noise: float

    @property
    def label(self) -> str:
        return self.condition if self.oracle_noise == ORACLE_NOISE else f"{self.condition}@{self.oracle_noise:g}"


def runs() -> List[Run]:
    """The preregistered cells: the four conditions at ORACLE_NOISE, then oracle_reset at each sensitivity noise."""
    return [Run(c, ORACLE_NOISE) for c in CONDITIONS] + [Run("oracle_reset", n) for n in SENSITIVITY_NOISES]


def engine_config(condition: str, oracle_noise: float = ORACLE_NOISE) -> EngineConfig:
    """The research profile with the heading oracle and wall-contact sensing on and the condition's estimate."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}; one of {tuple(CONDITIONS)}")
    cfg = EngineConfig.research()
    cfg.sensors.heading_oracle = True
    cfg.sensors.heading_oracle_noise = float(oracle_noise)
    cfg.sensors.wall_contact_sensing = True
    cfg.spatial.heading_source = CONDITIONS[condition]["heading_source"]
    cfg.spatial.wall_reset = CONDITIONS[condition]["wall_reset"]
    return cfg


def _walls_touched(pos: Tuple[float, float], bounds: Tuple[float, float]) -> Tuple[str, ...]:
    x, y = pos
    out = []
    if x >= bounds[0] - 1e-9:
        out.append("+x")
    elif x <= -bounds[0] + 1e-9:
        out.append("-x")
    if y >= bounds[1] - 1e-9:
        out.append("+y")
    elif y <= -bounds[1] + 1e-9:
        out.append("-y")
    return tuple(out)


@dataclass
class SeedResult:
    label: str
    condition: str
    oracle_noise: float
    seed: int
    errors: List[float]  # |estimate - body| per tick (units)
    heading_errors: List[float]  # wrapped estimate - body heading per tick (radians)
    contacts: List[Dict[str, Any]] = field(default_factory=list)
    reset_writes: int = 0
    wrong_writes: int = 0
    ticks_at_wall: int = 0
    walk_digest: str = ""


def run_seed(run: Run, seed: int, ticks: int = TICKS) -> SeedResult:
    """One seed of one cell, stepped tick by tick so the reset's writes can be scored against the walls touched."""
    cfg = engine_config(run.condition, run.oracle_noise)
    eng = Engine(seed=seed, config=cfg)
    bounds = tuple(eng.world.bounds)
    result = SeedResult(run.label, run.condition, run.oracle_noise, seed, [], [])
    digest = hashlib.sha256()
    prev_walls: Tuple[str, ...] = ()
    prev_err = 0.0
    prev_normal: Dict[str, float] = {}
    for i in range(ticks):
        td = eng.run(1, reset=(i == 0))[0]
        x, y = eng.agent.pos
        st = eng.spatial.state
        err = math.hypot(st.grid_x - x, st.grid_y - y)
        result.errors.append(err)
        result.heading_errors.append(wrap_angle(st.hd_angle - eng.agent.heading))
        digest.update(f"{x:.12f},{y:.12f},{eng.agent.heading:.12f};".encode())
        walls = _walls_touched((x, y), bounds)
        result.ticks_at_wall += bool(walls)
        writes = tuple(st.resets)
        result.reset_writes += len(writes)
        result.wrong_writes += sum(w not in walls for w in writes)
        normal = {"x": abs(st.grid_x - x), "y": abs(st.grid_y - y)}
        if walls and not prev_walls and i > 0:  # a contact onset: the first tick of a bout at a wall
            axis = walls[0][1]
            result.contacts.append({
                "label": run.label, "condition": run.condition, "oracle_noise": run.oracle_noise, "seed": seed,
                "tick": td.tick, "walls_touched": "|".join(walls), "walls_reset": "|".join(writes),
                "correct": all(w in walls for w in writes) if writes else "",
                "error_before": prev_err, "error_after": err,
                "normal_error_before": prev_normal[axis], "normal_error_after": normal[axis],
            })
        prev_walls, prev_err, prev_normal = walls, err, normal
    result.walk_digest = digest.hexdigest()[:16]
    return result


def _job(args: Tuple[Run, int, int]) -> SeedResult:
    run, seed, ticks = args
    return run_seed(run, seed, ticks)


def run_all(cells: Sequence[Run], seeds: Sequence[int], ticks: int, workers: Optional[int] = None) -> List[SeedResult]:
    jobs = [(r, s, ticks) for r in cells for s in seeds]
    if workers == 1 or len(jobs) == 1:
        return [_job(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_job, jobs, chunksize=1))


# --- per seed ---------------------------------------------------------------------------------------


PER_SEED_COLUMNS = ("label", "condition", "oracle_noise", "seed", "ticks", "error_mean_late", "error_median_late",
                    "error_p90_late", "error_final", "error_median_all", "share_late_below_bound", "heading_rms_late",
                    "heading_abs_max", "ticks_at_wall_share", "contact_onsets", "reset_writes", "wrong_wall_share",
                    "drop_at_contact", "normal_drop_at_contact", "walk_digest")


def per_seed_row(r: SeedResult, late_from: int) -> Dict[str, Any]:
    n = len(r.errors)
    late = np.array(r.errors[late_from - 1:], dtype=np.float64)
    head = np.array(r.heading_errors[late_from - 1:], dtype=np.float64)
    drops = [c["error_after"] - c["error_before"] for c in r.contacts]
    ndrops = [c["normal_error_after"] - c["normal_error_before"] for c in r.contacts]
    return {
        "label": r.label, "condition": r.condition, "oracle_noise": r.oracle_noise, "seed": r.seed, "ticks": n,
        "error_mean_late": float(late.mean()), "error_median_late": float(np.median(late)),
        "error_p90_late": float(np.quantile(late, 0.9)), "error_final": r.errors[-1],
        "error_median_all": float(np.median(r.errors)), "share_late_below_bound": float(np.mean(late < BOUND_UNITS)),
        "heading_rms_late": float(np.sqrt(np.mean(head ** 2))), "heading_abs_max": float(np.max(np.abs(r.heading_errors))),
        "ticks_at_wall_share": r.ticks_at_wall / n, "contact_onsets": len(r.contacts), "reset_writes": r.reset_writes,
        "wrong_wall_share": (r.wrong_writes / r.reset_writes) if r.reset_writes else math.nan,
        "drop_at_contact": float(np.mean(drops)) if drops else math.nan,
        "normal_drop_at_contact": float(np.mean(ndrops)) if ndrops else math.nan,
        "walk_digest": r.walk_digest,
    }


CURVE_COLUMNS = ("label", "tick", "n", "mean_error", "low", "high", "median_error")


def curve_rows(results: Sequence[SeedResult], n_boot: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    labels = list(dict.fromkeys(r.label for r in results))
    for label in labels:
        group = [r for r in results if r.label == label]
        n = len(group[0].errors)
        for t in range(SAMPLE_EVERY, n + 1, SAMPLE_EVERY):
            arr = np.array([g.errors[t - 1] for g in group], dtype=np.float64)
            ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed("curve", label, t))
            out.append({"label": label, "tick": t, "n": int(arr.size), "mean_error": ci.estimate, "low": ci.low,
                        "high": ci.high, "median_error": float(np.median(arr))})
    return out


EFFECT_COLUMNS = ("test", "statistic", "a", "b", "n", "mean_a", "mean_b", "estimate", "low", "high", "cliffs_delta",
                  "cliffs_low", "cliffs_high", "fraction_b_lt_a", "bound", "verdict", "note")

# The paired comparisons (b against a, paired by seed): the M2b estimate against today's, and each mechanism alone.
COMPARISONS: Tuple[Tuple[str, str, str], ...] = (
    ("primary_vs_integrated", "integrated", "oracle_reset"),
    ("reset_under_oracle", "oracle", "oracle_reset"),
    ("reset_under_integration", "integrated", "integrated_reset"),
    ("oracle_without_reset", "integrated", "oracle"),
    ("oracle_under_reset", "integrated_reset", "oracle_reset"),
)


def effect_rows(rows: Sequence[Mapping[str, Any]], n_boot: int) -> List[Dict[str, Any]]:
    by: Dict[str, Dict[int, Mapping[str, Any]]] = {}
    for r in rows:
        by.setdefault(str(r["label"]), {})[int(r["seed"])] = r
    out: List[Dict[str, Any]] = []
    base = {k: "" for k in EFFECT_COLUMNS}

    def ci_row(test: str, statistic: str, label: str, values: Sequence[float], bound: str, verdict_fn) -> Dict[str, Any]:
        arr = np.array([v for v in values if not math.isnan(v)], dtype=np.float64)
        if arr.size == 0:
            return {**base, "test": test, "statistic": statistic, "b": label, "n": 0, "estimate": math.nan, "low": math.nan,
                    "high": math.nan, "bound": bound, "verdict": "undefined"}
        ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed("effect", test, statistic, label))
        return {**base, "test": test, "statistic": statistic, "b": label, "n": int(arr.size), "mean_b": ci.estimate,
                "estimate": ci.estimate, "low": ci.low, "high": ci.high, "bound": bound, "verdict": verdict_fn(ci), "note": ci.note}

    # (1) The M2b estimate's level: per-seed median error over the late window, mean over seeds, below 0.2 m.
    if "oracle_reset" in by:
        p = by["oracle_reset"]
        out.append(ci_row("t1_level", "error_median_late", "oracle_reset", [p[s]["error_median_late"] for s in sorted(p)],
                          f"< {BOUND_UNITS} units, interval below", lambda ci: "passes" if ci.high < BOUND_UNITS else "fails"))
        # (3) The drop at contact: error after the reset minus before, per-seed mean over contact onsets, below 0.
        out.append(ci_row("t3_drop_at_contact", "drop_at_contact", "oracle_reset", [p[s]["drop_at_contact"] for s in sorted(p)],
                          "< 0, interval below", lambda ci: "passes" if ci.high < 0.0 else "fails"))
        # (4) Wrong-wall resets: below 1% of reset writes.
        out.append(ci_row("t4_wrong_wall", "wrong_wall_share", "oracle_reset", [p[s]["wrong_wall_share"] for s in sorted(p)],
                          f"< {WRONG_WALL_BOUND}", lambda ci: "passes" if ci.estimate < WRONG_WALL_BOUND else "fails"))
    for label in ("integrated_reset",):
        if label in by:
            q = by[label]
            out.append(ci_row("reported_wrong_wall", "wrong_wall_share", label, [q[s]["wrong_wall_share"] for s in sorted(q)],
                              "reported", lambda ci: "reported"))
            out.append(ci_row("reported_drop_at_contact", "drop_at_contact", label, [q[s]["drop_at_contact"] for s in sorted(q)],
                              "reported", lambda ci: "reported"))
    # (2) and the mechanism comparisons: paired by seed on the late mean error.
    for test, a, b in COMPARISONS:
        if a not in by or b not in by:
            continue
        seeds = sorted(set(by[a]) & set(by[b]))
        va = np.array([by[a][s]["error_mean_late"] for s in seeds], dtype=np.float64)
        vb = np.array([by[b][s]["error_mean_late"] for s in seeds], dtype=np.float64)
        eff = paired_effect(va, vb, n_boot=n_boot, seed=_stat_seed("paired", test))
        d = cliffs_delta(va, vb, n_boot=n_boot, seed=_stat_seed("cliff", test))
        primary = test == "primary_vs_integrated"
        verdict = ("passes" if (d["delta"] <= -DELTA_BOUND and eff["high"] < 0.0) else "fails") if primary else "reported"
        out.append({**base, "test": "t2_" + test if primary else test, "statistic": "error_mean_late", "a": a, "b": b,
                    "n": len(seeds), "mean_a": eff["mean_a"], "mean_b": eff["mean_b"], "estimate": eff["mean_diff"],
                    "low": eff["low"], "high": eff["high"], "cliffs_delta": d["delta"], "cliffs_low": d["low"],
                    "cliffs_high": d["high"], "fraction_b_lt_a": float(np.mean(vb < va)),
                    "bound": f"b < a: delta <= -{DELTA_BOUND}, interval below 0" if primary else "reported", "verdict": verdict,
                    "note": "; ".join(n for n in (eff["note"], d["note"]) if n)})
    # Sensitivity: the M2b estimate's level at each oracle noise.
    for label in [lab for lab in by if lab.startswith("oracle_reset@")]:
        q = by[label]
        out.append(ci_row("sensitivity", "error_median_late", label, [q[s]["error_median_late"] for s in sorted(q)],
                          "reported", lambda ci: "reported"))
        out.append(ci_row("sensitivity", "wrong_wall_share", label, [q[s]["wrong_wall_share"] for s in sorted(q)],
                          "reported", lambda ci: "reported"))
    return out


CONTACT_COLUMNS = ("label", "condition", "oracle_noise", "seed", "tick", "walls_touched", "walls_reset", "correct",
                   "error_before", "error_after", "normal_error_before", "normal_error_after")
OUTPUT_FILES = ("estimate_per_seed.csv", "estimate_curve.csv", "estimate_effects.csv", "estimate_contacts.csv.gz",
                "estimate_manifest.json")


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEEDS[0])
    parser.add_argument("--ticks", type=int, default=None, help=f"ticks per run (default {TICKS}; {QUICK_TICKS} with --quick)")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--quick", action="store_true", help=f"{QUICK_TICKS} ticks, 200 replicates; needs --out")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    ticks = args.ticks if args.ticks is not None else (QUICK_TICKS if args.quick else TICKS)
    if ticks < 2 * SAMPLE_EVERY:
        parser.error(f"--ticks must be at least {2 * SAMPLE_EVERY}")
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    full = tuple(seeds) == DEFAULT_SEEDS and ticks == TICKS and not args.quick and n_boot >= 1000
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a partial run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    late_from = LATE_FROM if ticks == TICKS else ticks // 3 + 1
    cells = runs()
    started = time.perf_counter()
    results = run_all(cells, seeds, ticks, args.workers)
    rows = [per_seed_row(r, late_from) for r in results]
    # Guards: seeds are samples (distinct walks), and within a seed every cell walks the same body path.
    guard = pseudo_replication_guard([{"seed": r.seed, "walk": [r.walk_digest]} for r in results if r.label == cells[0].label],
                                     key="walk", allow=True)
    walks_by_seed: Dict[int, set] = {}
    for r in results:
        walks_by_seed.setdefault(r.seed, set()).add(r.walk_digest)
    same_walk = all(len(v) == 1 for v in walks_by_seed.values())
    curve = curve_rows(results, n_boot)
    effects = effect_rows(rows, n_boot)
    contacts = [c for r in results for c in r.contacts]
    cfg = engine_config("oracle_reset")
    manifest = build_manifest(
        cfg, protocol="estimate_correction", seeds=seeds, ticks_requested=ticks * len(cells) * len(seeds),
        extra={"cells": [{"label": c.label, "condition": c.condition, "oracle_noise": c.oracle_noise,
                          "config_diff_from_research": [list(map(str, d)) for d in EngineConfig.research().diff(engine_config(c.condition, c.oracle_noise))]}
                         for c in cells],
               "ticks": ticks, "late_from": late_from, "bound_units": BOUND_UNITS, "n_boot": n_boot, "full_evaluation": full,
               "quick": args.quick, "prereg": "docs/prereg/m2b_estimate.md", "dependencies": _dependency_versions(),
               "command": "python3 -m experiments.estimate_correction " + " ".join(list(argv) if argv is not None else sys.argv[1:])},
    )
    manifest["guard"] = {"distinct_walks": guard if isinstance(guard, int) else None, "message": guard if isinstance(guard, str) else "",
                         "same_walk_across_cells": same_walk}
    manifest["workers"] = args.workers if args.workers is not None else os.cpu_count()
    finish_manifest(manifest, ticks_run=ticks * len(results), wall_seconds=time.perf_counter() - started)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / OUTPUT_FILES[0], PER_SEED_COLUMNS, rows)
    write_csv(out / OUTPUT_FILES[1], CURVE_COLUMNS, curve)
    write_csv(out / OUTPUT_FILES[2], EFFECT_COLUMNS, effects)
    write_csv_gz(out / OUTPUT_FILES[3], CONTACT_COLUMNS, contacts)
    write_manifest(out / OUTPUT_FILES[4], manifest)
    print("preregistered tests and comparisons (docs/prereg/m2b_estimate.md):")
    for e in effects:
        est = "nan" if (isinstance(e["estimate"], float) and math.isnan(e["estimate"])) else f"{e['estimate']:.4g} [{e['low']:.4g}, {e['high']:.4g}]"
        extra = f" delta {e['cliffs_delta']:+.2f}" if e["cliffs_delta"] != "" else ""
        print(f"  {e['test']:28s} {e['statistic']:20s} {e['a'] or '':17s} {e['b']:20s} {est:34s}{extra} {e['verdict']}")
    print(f"guard: distinct walks {guard}; same walk across cells within a seed: {same_walk}")
    print(f"wrote {', '.join(OUTPUT_FILES)} to {out} in {manifest['timing']['wall_seconds']:.1f} s")
    return {"rows": rows, "curve": curve, "effects": effects, "contacts": contacts, "results": results,
            "guard": guard, "same_walk": same_walk}


if __name__ == "__main__":
    main()
