"""M2b step 2: the place population over the corrected estimate (docs/prereg/m2b_place_population.md).

    python3 -m experiments.place_population --workers 4               # 30 seeds, writes docs/data/m2b/place
    python3 -m experiments.place_population --quick --seeds 2 --out /tmp/pl   # the smoke test's run

The research profile in the 2 m box, no objects, 3,000 ticks per run, the heading oracle (sigma 0.05) and wall-contact
sensing on in every run, and a 400-cell population (spacing 1 unit, width 1 unit) on in the engine. Two engines per
seed walk the same body path (checked by a digest): one with the research estimate (``integrated``), one with the M2b
estimate of step 1 (``m2b``: the oracle heading and the wall-contact reset). A third population, ``reference``, is
the same cells read at the body's true position on that walk: the place code a perfect estimate would give.

Every tick each engine population's rates are decoded (``PlacePopulation.decode``) and the decoded position compared
with the estimate (a check) and with the body (the decoding error); every population's rates enter a rate map over
1-unit bins of the true position. Per seed and population, each cell's map is compared with the reference map on
the same bins (``analysis.place_metrics.compare_maps``). After the runs, a throughput benchmark times the engine with
the population on and off.

Tables (``--out``): place_per_seed.csv, place_effects.csv (the preregistered tests and the reported comparisons),
place_cells.csv (per population and cell, means over seeds: correlation, centroid shift, information, wall
distance), place_throughput.csv and place_manifest.json. A partial run refuses the committed directory.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from analysis.place_metrics import RateMapAccumulator, compare_maps, wall_distance
from analysis.stats import bootstrap_ci, cliffs_delta, paired_effect, pseudo_replication_guard
from brain.systems.place_population import PlacePopulation
from core.config import EngineConfig
from core.engine import Engine
from experiments.estimate_correction import ORACLE_NOISE, engine_config
from experiments.linear_track_replay import _dependency_versions, _stat_seed, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

ESTIMATES: Dict[str, str] = {"integrated": "integrated", "m2b": "oracle_reset"}  # population label -> step-1 condition
POPULATIONS: Tuple[str, ...] = ("reference", "integrated", "m2b")
TICKS = 3000
LATE_FROM = 1001
WALL_CELL_DISTANCE = 2.0  # units: a cell whose centre lies within this of a wall is a "wall cell" (the outer two rings)
THROUGHPUT_BOUND = 1000.0  # ticks per second, the plan's row 2b
THROUGHPUT_REPEATS = 5
DECODE_TOLERANCE = 1e-6
DELTA_BOUND = 0.3
DEFAULT_SEEDS: Tuple[int, ...] = tuple(range(1, 31))
DEFAULT_OUT = Path("docs/data/m2b/place")
DEFAULT_N_BOOT = 10_000
QUICK_TICKS = 300


def place_config(estimate: str) -> EngineConfig:
    """Step 1's condition for ``estimate`` with the 400-cell population on."""
    cfg = engine_config(ESTIMATES[estimate], ORACLE_NOISE)
    cfg.place.enabled = True
    return cfg


def _walls_touched(pos: Tuple[float, float], bounds: Tuple[float, float]) -> bool:
    return abs(pos[0]) >= bounds[0] - 1e-9 or abs(pos[1]) >= bounds[1] - 1e-9


def run_seed(seed: int, ticks: int = TICKS) -> Dict[str, Any]:
    """Both engine populations and the reference on one seed's walk; per-population maps and decoding traces."""
    engines = {name: Engine(seed=seed, config=place_config(name)) for name in ESTIMATES}
    first = engines["m2b"]
    pop: PlacePopulation = first.place
    bounds = tuple(first.world.bounds)
    acc = {name: RateMapAccumulator(pop.size, bounds) for name in POPULATIONS}
    decode_err = {name: [] for name in ESTIMATES}
    decode_vs_est = {name: 0.0 for name in ESTIMATES}
    # Ticks at which the decoder returned no position: counted, never skipped (the first evaluation run's max() skipped
    # NaN and so read a failing decoder as exact; docs/prereg/m2b_place_population.md, post-run correction).
    undefined = {name: 0 for name in ESTIMATES}
    contacts: List[int] = []
    digests = {name: hashlib.sha256() for name in ESTIMATES}
    prev_wall = False
    for i in range(ticks):
        for name, eng in engines.items():
            eng.run(1, reset=(i == 0))
            x, y = eng.agent.pos
            digests[name].update(f"{x:.12f},{y:.12f},{eng.agent.heading:.12f};".encode())
            st = eng.spatial.state
            dx, dy = pop.decode(eng.place_rates)
            if math.isnan(dx) or math.isnan(dy):
                undefined[name] += 1
            else:
                decode_vs_est[name] = max(decode_vs_est[name], math.hypot(dx - st.grid_x, dy - st.grid_y))
            decode_err[name].append(math.hypot(dx - x, dy - y))  # NaN when undefined
            acc[name].add(x, y, eng.place_rates)
        x, y = first.agent.pos
        acc["reference"].add(x, y, pop.rates(x, y))
        wall = _walls_touched((x, y), bounds)
        if wall and not prev_wall and i > 0:
            contacts.append(i)
        prev_wall = wall
    walks = {name: d.hexdigest()[:16] for name, d in digests.items()}
    bins_x, bins_y = acc["reference"].bin_centres()
    ref_maps = acc["reference"].maps()
    counts = acc["reference"].counts
    cells = {}
    for name in POPULATIONS:
        cells[name] = compare_maps(acc[name].maps(), ref_maps, counts, pop.cx, pop.cy, bins_x, bins_y)
    return {"seed": seed, "ticks": ticks, "decode_err": decode_err, "decode_vs_est": decode_vs_est, "undefined": undefined,
            "contacts": contacts,
            "walks": walks, "cells": cells, "wall_distance": wall_distance(pop.cx, pop.cy, bounds),
            "bins_visited": int(np.sum(counts >= 5))}


def run_all(seeds: Sequence[int], ticks: int, workers: Optional[int]) -> List[Dict[str, Any]]:
    if workers == 1 or len(seeds) == 1:
        return [run_seed(s, ticks) for s in seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_seed, seeds, [ticks] * len(seeds), chunksize=1))


PER_SEED_COLUMNS = ("population", "seed", "ticks", "cells_compared", "correlation_mean", "correlation_wall", "correlation_interior",
                    "centroid_shift_mean", "centroid_shift_wall", "centroid_shift_interior", "info_ratio_mean",
                    "decode_vs_estimate_max", "decode_undefined_ticks", "decode_error_median_late", "decode_drop_at_contact", "contact_onsets",
                    "bins_visited", "walk_digest")


def _nanmean(a: np.ndarray) -> float:
    a = a[~np.isnan(a)]
    return float(np.sum(a)) / a.size if a.size else math.nan


def per_seed_rows(res: Mapping[str, Any], late_from: int) -> List[Dict[str, Any]]:
    out = []
    wall = res["wall_distance"] < WALL_CELL_DISTANCE
    for name in POPULATIONS:
        c = res["cells"][name]
        corr, shift = c["correlation"], c["centroid_shift"]
        ratio = c["info"] / c["info_reference"]
        row = {"population": name, "seed": res["seed"], "ticks": res["ticks"],
               "cells_compared": int(np.sum(~np.isnan(corr))), "correlation_mean": _nanmean(corr),
               "correlation_wall": _nanmean(corr[wall]), "correlation_interior": _nanmean(corr[~wall]),
               "centroid_shift_mean": _nanmean(shift), "centroid_shift_wall": _nanmean(shift[wall]),
               "centroid_shift_interior": _nanmean(shift[~wall]), "info_ratio_mean": _nanmean(ratio),
               "contact_onsets": len(res["contacts"]), "bins_visited": res["bins_visited"],
               "decode_vs_estimate_max": math.nan, "decode_undefined_ticks": "", "decode_error_median_late": math.nan,
               "decode_drop_at_contact": math.nan,
               "walk_digest": res["walks"].get(name, res["walks"]["m2b"])}
        if name in ESTIMATES:
            err = res["decode_err"][name]
            row["decode_vs_estimate_max"] = res["decode_vs_est"][name]
            row["decode_undefined_ticks"] = res["undefined"][name]
            late = np.array(err[late_from - 1:], dtype=np.float64)
            # The median over the ticks the decoder defined; with an undefined tick the column says how many.
            row["decode_error_median_late"] = float(np.median(late[~np.isnan(late)])) if np.any(~np.isnan(late)) else math.nan
            drops = [err[t] - err[t - 1] for t in res["contacts"] if not (math.isnan(err[t]) or math.isnan(err[t - 1]))]
            row["decode_drop_at_contact"] = float(np.mean(drops)) if drops else math.nan
        out.append(row)
    return out


CELL_COLUMNS = ("population", "cell", "centre_x", "centre_y", "wall_distance", "n_seeds", "correlation", "centroid_shift",
                "info", "info_reference")


def cell_rows(results: Sequence[Mapping[str, Any]], pop: PlacePopulation) -> List[Dict[str, Any]]:
    out = []
    wd = results[0]["wall_distance"]
    for name in POPULATIONS:
        stack = {k: np.vstack([r["cells"][name][k] for r in results]) for k in ("correlation", "centroid_shift", "info", "info_reference")}
        for j in range(pop.size):
            col = stack["correlation"][:, j]
            n = int(np.sum(~np.isnan(col)))
            out.append({"population": name, "cell": j, "centre_x": float(pop.cx[j]), "centre_y": float(pop.cy[j]),
                        "wall_distance": float(wd[j]), "n_seeds": n,
                        **{k: _nanmean(stack[k][:, j]) for k in ("correlation", "centroid_shift", "info", "info_reference")}})
    return out


EFFECT_COLUMNS = ("test", "statistic", "a", "b", "n", "mean_a", "mean_b", "estimate", "low", "high", "cliffs_delta",
                  "cliffs_low", "cliffs_high", "bound", "verdict", "note")


def effect_rows(rows: Sequence[Mapping[str, Any]], throughput: Mapping[str, Any], n_boot: int) -> List[Dict[str, Any]]:
    base = {k: "" for k in EFFECT_COLUMNS}
    by: Dict[str, Dict[int, Mapping[str, Any]]] = {}
    for r in rows:
        by.setdefault(str(r["population"]), {})[int(r["seed"])] = r
    out: List[Dict[str, Any]] = []

    def ci_row(test, statistic, label, values, bound, verdict_fn):
        arr = np.array([v for v in values if not math.isnan(v)], dtype=np.float64)
        if arr.size == 0:
            return {**base, "test": test, "statistic": statistic, "b": label, "n": 0, "estimate": math.nan, "low": math.nan,
                    "high": math.nan, "bound": bound, "verdict": "undefined"}
        ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed("place", test, statistic, label))
        return {**base, "test": test, "statistic": statistic, "b": label, "n": int(arr.size), "mean_b": ci.estimate,
                "estimate": ci.estimate, "low": ci.low, "high": ci.high, "bound": bound, "verdict": verdict_fn(ci), "note": ci.note}

    on = throughput["ticks_per_s_on"]
    out.append({**base, "test": "t1_throughput", "statistic": "ticks_per_s_median", "b": "m2b, 400 cells", "n": len(throughput["on"]),
                "estimate": on, "low": min(throughput["on"]), "high": max(throughput["on"]), "bound": f">= {THROUGHPUT_BOUND:g}",
                "verdict": "passes" if on >= THROUGHPUT_BOUND else "fails", "note": f"off: {throughput['ticks_per_s_off']:.0f}"})
    worst = max(float(r["decode_vs_estimate_max"]) for r in rows if r["population"] in ESTIMATES)
    undefined = {name: sum(int(by[name][s]["decode_undefined_ticks"]) for s in by[name]) for name in ESTIMATES}
    ok = worst < DECODE_TOLERANCE and not any(undefined.values())
    out.append({**base, "test": "t2_decoder", "statistic": "decode_vs_estimate_max", "b": "integrated, m2b", "n": len(by["m2b"]),
                "estimate": worst, "bound": f"< {DECODE_TOLERANCE:g} units at every tick (an undefined decode fails)",
                "verdict": "passes" if ok else "fails",
                "note": "undefined decodes: " + ", ".join(f"{k} {v}" for k, v in undefined.items())})
    m = by["m2b"]
    out.append(ci_row("t3_decoding_drop_at_contact", "decode_drop_at_contact", "m2b", [m[s]["decode_drop_at_contact"] for s in sorted(m)],
                      "< 0, interval below", lambda ci: "passes" if ci.high < 0.0 else "fails"))
    seeds = sorted(set(by["integrated"]) & set(by["m2b"]))
    va = np.array([by["integrated"][s]["correlation_mean"] for s in seeds], dtype=np.float64)
    vb = np.array([by["m2b"][s]["correlation_mean"] for s in seeds], dtype=np.float64)
    eff = paired_effect(va, vb, n_boot=n_boot, seed=_stat_seed("place", "t4"))
    d = cliffs_delta(va, vb, n_boot=n_boot, seed=_stat_seed("place", "t4", "cliff"))
    out.append({**base, "test": "t4_map_fidelity", "statistic": "correlation_mean", "a": "integrated", "b": "m2b", "n": len(seeds),
                "mean_a": eff["mean_a"], "mean_b": eff["mean_b"], "estimate": eff["mean_diff"], "low": eff["low"], "high": eff["high"],
                "cliffs_delta": d["delta"], "cliffs_low": d["low"], "cliffs_high": d["high"],
                "bound": f"b > a: delta >= {DELTA_BOUND}, interval above 0",
                "verdict": "passes" if (d["delta"] >= DELTA_BOUND and eff["low"] > 0.0) else "fails",
                "note": "; ".join(n for n in (eff["note"], d["note"]) if n)})
    for name in ("integrated", "m2b"):
        q = by[name]
        for stat in ("correlation_mean", "correlation_wall", "correlation_interior", "centroid_shift_mean", "centroid_shift_wall",
                     "centroid_shift_interior", "info_ratio_mean", "decode_error_median_late"):
            out.append(ci_row("reported", stat, name, [float(q[s][stat]) for s in sorted(q)], "reported", lambda ci: "reported"))
    return out


THROUGHPUT_COLUMNS = ("population", "repeat", "seed", "ticks", "seconds", "ticks_per_s")


def throughput(ticks: int, repeats: int) -> Dict[str, Any]:
    """Wall-clock ticks per second of one engine in this process, with the 400-cell population on and off (M2b estimate)."""
    rows, on, off = [], [], []
    for rep in range(repeats):
        for enabled in (True, False):
            cfg = place_config("m2b")
            cfg.value_memory.source = "tabular"  # the population's own cost: the SR source over it is step 4's (the profile's since G37)
            cfg.place.enabled = enabled
            eng = Engine(seed=rep + 1, config=cfg)
            t0 = time.perf_counter()
            eng.run(ticks, reset=True)
            secs = time.perf_counter() - t0
            (on if enabled else off).append(ticks / secs)
            rows.append({"population": "on" if enabled else "off", "repeat": rep + 1, "seed": rep + 1, "ticks": ticks,
                         "seconds": secs, "ticks_per_s": ticks / secs})
    return {"rows": rows, "on": on, "off": off, "ticks_per_s_on": float(np.median(on)), "ticks_per_s_off": float(np.median(off))}


OUTPUT_FILES = ("place_per_seed.csv", "place_effects.csv", "place_cells.csv", "place_throughput.csv", "place_manifest.json")


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEEDS[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--quick", action="store_true", help=f"{QUICK_TICKS} ticks, 200 replicates, 1 throughput repeat; needs --out")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    ticks = QUICK_TICKS if args.quick else TICKS
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    full = tuple(seeds) == DEFAULT_SEEDS and not args.quick and n_boot >= 1000
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a partial run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    late_from = LATE_FROM if ticks == TICKS else ticks // 3 + 1
    started = time.perf_counter()
    results = run_all(seeds, ticks, args.workers)
    rows = [row for res in results for row in per_seed_rows(res, late_from)]
    same_walk = all(len(set(res["walks"].values())) == 1 for res in results)
    guard = pseudo_replication_guard([{"seed": r["seed"], "walk": [r["walks"]["m2b"]]} for r in results], key="walk", allow=True)
    pop = Engine(seed=1, config=place_config("m2b")).place
    cells = cell_rows(results, pop)
    tp = throughput(ticks, 1 if args.quick else THROUGHPUT_REPEATS)
    effects = effect_rows(rows, tp, n_boot)
    cfg = place_config("m2b")
    manifest = build_manifest(
        cfg, protocol="place_population", seeds=seeds, ticks_requested=ticks * len(ESTIMATES) * len(seeds),
        extra={"populations": list(POPULATIONS), "estimates": dict(ESTIMATES), "population": pop.parameters(),
               "config_diff_from_research": {name: [list(map(str, d)) for d in EngineConfig.research().diff(place_config(name))] for name in ESTIMATES},
               "ticks": ticks, "late_from": late_from, "wall_cell_distance": WALL_CELL_DISTANCE, "n_boot": n_boot,
               "throughput_repeats": len(tp["on"]), "machine": platform.processor() or platform.machine(),
               "full_evaluation": full, "quick": args.quick, "prereg": "docs/prereg/m2b_place_population.md",
               "dependencies": _dependency_versions(),
               "command": "python3 -m experiments.place_population " + " ".join(list(argv) if argv is not None else sys.argv[1:])},
    )
    manifest["guard"] = {"distinct_walks": guard if isinstance(guard, int) else None, "message": guard if isinstance(guard, str) else "",
                         "same_walk_across_estimates": same_walk}
    manifest["workers"] = args.workers if args.workers is not None else os.cpu_count()
    finish_manifest(manifest, ticks_run=ticks * len(ESTIMATES) * len(seeds), wall_seconds=time.perf_counter() - started)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / OUTPUT_FILES[0], PER_SEED_COLUMNS, rows)
    write_csv(out / OUTPUT_FILES[1], EFFECT_COLUMNS, effects)
    write_csv(out / OUTPUT_FILES[2], CELL_COLUMNS, cells)
    write_csv(out / OUTPUT_FILES[3], THROUGHPUT_COLUMNS, tp["rows"])
    write_manifest(out / OUTPUT_FILES[4], manifest)
    print("preregistered tests and reported statistics (docs/prereg/m2b_place_population.md):")
    for e in effects:
        est = "nan" if (isinstance(e["estimate"], float) and math.isnan(e["estimate"])) else f"{e['estimate']:.4g}"
        rng = "" if e["low"] == "" else f" [{e['low']:.4g}, {e['high']:.4g}]"
        print(f"  {e['test']:28s} {e['statistic']:26s} {e['b']:16s} {est}{rng} {e['verdict']}")
    print(f"guard: distinct walks {guard}; same walk across estimates: {same_walk}")
    print(f"wrote {', '.join(OUTPUT_FILES)} to {out} in {manifest['timing']['wall_seconds']:.1f} s")
    return {"rows": rows, "effects": effects, "cells": cells, "throughput": tp, "results": results, "same_walk": same_walk, "guard": guard}


if __name__ == "__main__":
    main()
