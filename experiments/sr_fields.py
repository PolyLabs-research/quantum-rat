"""M2b step 3: successor features over the place code (docs/prereg/m2b_sr_fields.md).

    python3 -m experiments.sr_fields --workers 4                 # both parts, 30 seeds, writes docs/data/m2b/sr
    python3 -m experiments.sr_fields --quick --seeds 2 --out /tmp/sr   # the smoke test's run

Both parts use step 1's M2b estimate (heading oracle sigma 0.05, wall-contact reset) and step 2's place population,
whose rates, normalised to sum 1, are the features; the SR (``brain.systems.successor_features``) is learned by TD
from the agent's own transitions, one per tick, learning rate ``LR``, discount ``GAMMA``.

**Track** (the plan's "after 50 laps on the track, SR fields skew backward against the running direction"): a 2 m x
0.1 m corridor (world bounds 10 x 0.5 units), 20 cells along it. The protocol imposes the running: every tick the
body is driven FORWARD at a speed drawn uniformly from [0.5, 1.0] units per tick from a protocol stream (so seeds walk
different paths), heading along the track. ``one_way``: each lap runs east from the west wall to the east wall, then
the body is carried back to the west wall (an episode boundary for the SR, the estimate re-anchored to the start:
the rat is put back on the start platform). ``two_way``: at each wall the body turns round in place and runs back,
with no boundary. 50 laps. Per interior cell (centres at least 3.5 units from either end), the SR field along the
track and its centre-of-mass shift from the cell's own centre: negative is backward for eastward running.

**Open field** (the plan's "near walls, fields elongate along the wall"): the 2 m box, the research agent's own walk,
12,000 ticks (40 min). Per cell, the SR field over a 0.5-unit grid of the arena and, above half its maximum, its
variance along and across the nearest wall; the same for the raw place field (the SR before learning), whose region
the wall also truncates. Wall cells: centres 0.5 units from exactly one wall (72 cells); interior cells: at least
3.5 units from every wall (196 cells).

Tables (``--out``): sr_track_per_seed.csv, sr_track_cells.csv, sr_open_per_seed.csv, sr_open_cells.csv,
sr_effects.csv and sr_manifest.json. A partial run refuses the committed directory.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from analysis.stats import bootstrap_ci, cliffs_delta, paired_effect, pseudo_replication_guard
from brain.contracts import Action
from brain.systems.successor_features import SuccessorFeatures, normalised
from core.config import EngineConfig
from core.engine import Engine
from core.rng import RNG
from experiments.estimate_correction import ORACLE_NOISE, engine_config
from experiments.linear_track_replay import _dependency_versions, _stat_seed, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

LR = 0.1
GAMMA = 0.95
TRACK_BOUNDS = (10.0, 0.5)
TRACK_LAPS = 50
TRACK_SPEED = (0.5, 1.0)
TRACK_INTERIOR = 3.5  # a cell enters the skew statistic when its centre is at least this far from either end
TRACK_MODES: Tuple[str, ...] = ("one_way", "two_way")
TRACK_STREAM = "track_protocol"
OPEN_TICKS = 12_000
OPEN_GRID = 0.5
WALL_CELL = 0.5  # wall cells: centre this far from exactly one wall
INTERIOR_CELL = 3.5
DELTA_BOUND = 0.3
DEFAULT_SEEDS: Tuple[int, ...] = tuple(range(1, 31))
DEFAULT_OUT = Path("docs/data/m2b/sr")
DEFAULT_N_BOOT = 10_000
QUICK_LAPS = 6
QUICK_OPEN_TICKS = 600


def m2b_config(bounds: Tuple[float, float]) -> EngineConfig:
    """Step 1's M2b estimate with step 2's population, in a world of ``bounds``."""
    cfg = engine_config("oracle_reset", ORACLE_NOISE)
    cfg.world.bounds = tuple(bounds)
    cfg.place.enabled = True
    return cfg


def _place(eng: Engine, x: float, y: float, heading: float, *, anchor: bool) -> None:
    """Put the body at (x, y) facing ``heading`` between ticks (invisible to egomotion: the body remembers its pose at
    the start of each move); with ``anchor`` the estimate is re-anchored there too (the rat is put back on the start)."""
    a = eng.agent
    a.pos = a.last_pos = (x, y)
    a.heading = a.last_heading = heading
    if anchor:
        st = eng.spatial.state
        st.grid_x, st.grid_y, st.hd_angle = x, y, heading


# --- the track ----------------------------------------------------------------------------------------


def run_track(mode: str, seed: int, laps: int = TRACK_LAPS) -> Dict[str, Any]:
    if mode not in TRACK_MODES:
        raise ValueError(f"mode must be one of {TRACK_MODES}")
    eng = Engine(seed=seed, config=m2b_config(TRACK_BOUNDS))
    speed = RNG(seed=seed).stream(TRACK_STREAM)
    bx = TRACK_BOUNDS[0]
    sr = SuccessorFeatures(eng.place.size, LR, GAMMA)
    digest = hashlib.sha256()
    ticks = 0
    first = True
    direction = 1
    phi_prev: Optional[np.ndarray] = None
    errors: List[float] = []
    for lap in range(laps):
        if mode == "one_way" or lap == 0:
            _place(eng, -bx, 0.0, 0.0, anchor=True)
            direction = 1
            phi_prev = None  # the carry back is not a transition
        else:
            heading = 0.0 if direction > 0 else math.pi
            _place(eng, eng.agent.pos[0], 0.0, heading, anchor=False)  # turn round in place at the wall
        while True:
            eng.last_action = Action(name="FORWARD", thrust=speed.uniform(*TRACK_SPEED), turn=0.0)
            eng.run(1, reset=first)
            first = False
            ticks += 1
            x, y = eng.agent.pos
            digest.update(f"{x:.12f},{y:.12f};".encode())
            st = eng.spatial.state
            errors.append(math.hypot(st.grid_x - x, st.grid_y - y))
            phi = normalised(eng.place_rates)
            at_end = (direction > 0 and x >= bx - 1e-9) or (direction < 0 and x <= -bx + 1e-9)
            if phi_prev is not None:
                sr.update(phi_prev, phi, terminal=(at_end and mode == "one_way"))
            phi_prev = phi
            if at_end:
                break
        if mode == "two_way":
            direction = -direction
    pop = eng.place
    grid = np.arange(-bx, bx + 1e-9, 0.25)
    feats = np.stack([normalised(pop.rates(float(x), 0.0)) for x in grid])
    shifts, skews, peaks = [], [], []
    for j in range(pop.size):
        f = sr.field(j, feats)
        w = np.clip(f, 0.0, None)
        tot = float(np.sum(w))
        com = float(np.sum(w * grid)) / tot
        var = float(np.sum(w * (grid - com) ** 2)) / tot
        skew = float(np.sum(w * (grid - com) ** 3)) / tot / var ** 1.5 if var > 0 else math.nan
        shifts.append(com - float(pop.cx[j]))
        skews.append(skew)
        peaks.append(float(grid[int(np.argmax(f))]) - float(pop.cx[j]))
    return {"mode": mode, "seed": seed, "ticks": ticks, "laps": laps, "walk": digest.hexdigest()[:16],
            "centres": [float(c) for c in pop.cx], "shift": shifts, "skew": skews, "peak_shift": peaks,
            "estimate_error_mean": float(np.mean(errors)), "sr_updates": sr.updates}


# --- the open field -----------------------------------------------------------------------------------


def _region_moments(f: np.ndarray, gx: np.ndarray, gy: np.ndarray) -> Tuple[float, float, float]:
    """Variance along x and along y of a field above half its maximum (weighted by the field there), and the region's area."""
    top = float(np.max(f))
    keep = f >= 0.5 * top
    w = f[keep]
    tot = float(np.sum(w))
    mx, my = float(np.sum(w * gx[keep])) / tot, float(np.sum(w * gy[keep])) / tot
    return (float(np.sum(w * (gx[keep] - mx) ** 2)) / tot, float(np.sum(w * (gy[keep] - my) ** 2)) / tot,
            float(np.sum(keep)) * OPEN_GRID * OPEN_GRID)


def run_open(seed: int, ticks: int = OPEN_TICKS) -> Dict[str, Any]:
    bounds = (10.0, 10.0)
    eng = Engine(seed=seed, config=m2b_config(bounds))
    pop = eng.place
    sr = SuccessorFeatures(pop.size, LR, GAMMA)
    digest = hashlib.sha256()
    phi_prev = None
    errors = []
    at_wall = 0
    for i in range(ticks):
        eng.run(1, reset=(i == 0))
        x, y = eng.agent.pos
        digest.update(f"{x:.12f},{y:.12f};".encode())
        st = eng.spatial.state
        errors.append(math.hypot(st.grid_x - x, st.grid_y - y))
        at_wall += abs(x) >= bounds[0] - 1e-9 or abs(y) >= bounds[1] - 1e-9
        phi = normalised(eng.place_rates)
        if phi_prev is not None:
            sr.update(phi_prev, phi)
        phi_prev = phi
    axis = np.arange(-bounds[0] + OPEN_GRID / 2, bounds[0], OPEN_GRID)
    gx, gy = np.meshgrid(axis, axis)
    gx, gy = gx.reshape(-1), gy.reshape(-1)
    feats = np.stack([normalised(pop.rates(float(a), float(b))) for a, b in zip(gx, gy)])
    fields = sr.fields(feats)  # positions x cells
    cells = []
    for j in range(pop.size):
        cx, cy = float(pop.cx[j]), float(pop.cy[j])
        dist = {"x": bounds[0] - abs(cx), "y": bounds[1] - abs(cy)}
        vx, vy, area = _region_moments(fields[:, j], gx, gy)
        rx, ry, raw_area = _region_moments(feats[:, j], gx, gy)
        kind = ("wall" if (min(dist.values()) == WALL_CELL and max(dist.values()) > WALL_CELL) else
                "interior" if min(dist.values()) >= INTERIOR_CELL else "other")
        # Along and across the nearest wall: a wall at |x| = bound runs along y.
        if kind == "wall":
            along, across, ra, rc = (vy, vx, ry, rx) if dist["x"] < dist["y"] else (vx, vy, rx, ry)
            log_sr, log_raw = math.log(along / across), math.log(ra / rc)
        else:
            log_sr, log_raw = math.log(vx / vy), math.log(rx / ry)
        cells.append({"cell": j, "kind": kind, "centre_x": cx, "centre_y": cy, "log_ratio_sr": log_sr, "log_ratio_raw": log_raw,
                      "elongation": log_sr - log_raw, "area_sr": area, "area_raw": raw_area})
    return {"seed": seed, "ticks": ticks, "walk": digest.hexdigest()[:16], "cells": cells,
            "estimate_error_median": float(np.median(errors)), "at_wall_share": at_wall / ticks, "sr_updates": sr.updates}


def _track_job(args):
    return run_track(*args)


def _open_job(args):
    return run_open(*args)


def _pool(fn, jobs, workers):
    if workers == 1 or len(jobs) <= 1:
        return [fn(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, jobs, chunksize=1))


# --- tables -------------------------------------------------------------------------------------------


TRACK_PER_SEED_COLUMNS = ("mode", "seed", "ticks", "laps", "cells", "shift_mean", "skew_mean", "peak_shift_mean",
                          "estimate_error_mean", "walk_digest")
TRACK_CELL_COLUMNS = ("mode", "cell", "centre", "interior", "n", "shift", "skew", "peak_shift")
OPEN_PER_SEED_COLUMNS = ("seed", "ticks", "wall_cells", "interior_cells", "elongation_wall", "log_ratio_sr_wall", "log_ratio_raw_wall",
                         "log_ratio_sr_interior", "area_ratio_wall", "area_ratio_interior", "estimate_error_median", "at_wall_share",
                         "walk_digest")
OPEN_CELL_COLUMNS = ("cell", "kind", "centre_x", "centre_y", "n", "log_ratio_sr", "log_ratio_raw", "elongation", "area_sr", "area_raw")
EFFECT_COLUMNS = ("test", "statistic", "a", "b", "n", "mean_a", "mean_b", "estimate", "low", "high", "cliffs_delta", "cliffs_low",
                  "cliffs_high", "bound", "verdict", "note")


def _mean(xs: Sequence[float]) -> float:
    xs = [x for x in xs if not math.isnan(x)]
    return math.fsum(xs) / len(xs) if xs else math.nan


def track_tables(results: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    per_seed, cells = [], []
    for r in results:
        interior = [j for j, c in enumerate(r["centres"]) if TRACK_BOUNDS[0] - abs(c) >= TRACK_INTERIOR]
        per_seed.append({"mode": r["mode"], "seed": r["seed"], "ticks": r["ticks"], "laps": r["laps"], "cells": len(interior),
                         "shift_mean": _mean([r["shift"][j] for j in interior]), "skew_mean": _mean([r["skew"][j] for j in interior]),
                         "peak_shift_mean": _mean([r["peak_shift"][j] for j in interior]),
                         "estimate_error_mean": r["estimate_error_mean"], "walk_digest": r["walk"]})
    for mode in TRACK_MODES:
        group = [r for r in results if r["mode"] == mode]
        if not group:
            continue
        for j, c in enumerate(group[0]["centres"]):
            cells.append({"mode": mode, "cell": j, "centre": c, "interior": TRACK_BOUNDS[0] - abs(c) >= TRACK_INTERIOR, "n": len(group),
                          **{k: _mean([g[k][j] for g in group]) for k in ("shift", "skew", "peak_shift")}})
    return per_seed, cells


def open_tables(results: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    per_seed = []
    for r in results:
        wall = [c for c in r["cells"] if c["kind"] == "wall"]
        inner = [c for c in r["cells"] if c["kind"] == "interior"]
        per_seed.append({"seed": r["seed"], "ticks": r["ticks"], "wall_cells": len(wall), "interior_cells": len(inner),
                         "elongation_wall": _mean([c["elongation"] for c in wall]),
                         "log_ratio_sr_wall": _mean([c["log_ratio_sr"] for c in wall]),
                         "log_ratio_raw_wall": _mean([c["log_ratio_raw"] for c in wall]),
                         "log_ratio_sr_interior": _mean([c["log_ratio_sr"] for c in inner]),
                         "area_ratio_wall": _mean([c["area_sr"] / c["area_raw"] for c in wall]),
                         "area_ratio_interior": _mean([c["area_sr"] / c["area_raw"] for c in inner]),
                         "estimate_error_median": r["estimate_error_median"], "at_wall_share": r["at_wall_share"], "walk_digest": r["walk"]})
    cells = []
    n = len(results[0]["cells"]) if results else 0
    for j in range(n):
        group = [r["cells"][j] for r in results]
        cells.append({"cell": j, "kind": group[0]["kind"], "centre_x": group[0]["centre_x"], "centre_y": group[0]["centre_y"],
                      "n": len(group), **{k: _mean([g[k] for g in group]) for k in ("log_ratio_sr", "log_ratio_raw", "elongation", "area_sr", "area_raw")}})
    return per_seed, cells


def effect_rows(track: Sequence[Mapping[str, Any]], open_rows: Sequence[Mapping[str, Any]], n_boot: int) -> List[Dict[str, Any]]:
    base = {k: "" for k in EFFECT_COLUMNS}
    out: List[Dict[str, Any]] = []

    def ci_row(test, statistic, label, values, bound, verdict_fn):
        arr = np.array([v for v in values if not math.isnan(v)], dtype=np.float64)
        if arr.size == 0:
            return {**base, "test": test, "statistic": statistic, "b": label, "n": 0, "estimate": math.nan, "low": math.nan,
                    "high": math.nan, "bound": bound, "verdict": "undefined"}
        ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed("sr", test, statistic, label))
        return {**base, "test": test, "statistic": statistic, "b": label, "n": int(arr.size), "mean_b": ci.estimate, "estimate": ci.estimate,
                "low": ci.low, "high": ci.high, "bound": bound, "verdict": verdict_fn(ci), "note": ci.note}

    by = {m: {int(r["seed"]): r for r in track if r["mode"] == m} for m in TRACK_MODES}
    if by["one_way"]:
        ow = by["one_way"]
        out.append(ci_row("t1_backward_shift", "shift_mean", "one_way", [ow[s]["shift_mean"] for s in sorted(ow)],
                          "< 0, interval below", lambda ci: "passes" if ci.high < 0.0 else "fails"))
    if by["one_way"] and by["two_way"]:
        seeds = sorted(set(by["one_way"]) & set(by["two_way"]))
        va = np.array([by["two_way"][s]["shift_mean"] for s in seeds], dtype=np.float64)
        vb = np.array([by["one_way"][s]["shift_mean"] for s in seeds], dtype=np.float64)
        eff = paired_effect(va, vb, n_boot=n_boot, seed=_stat_seed("sr", "t2"))
        d = cliffs_delta(va, vb, n_boot=n_boot, seed=_stat_seed("sr", "t2", "cliff"))
        out.append({**base, "test": "t2_direction_specific", "statistic": "shift_mean", "a": "two_way", "b": "one_way", "n": len(seeds),
                    "mean_a": eff["mean_a"], "mean_b": eff["mean_b"], "estimate": eff["mean_diff"], "low": eff["low"], "high": eff["high"],
                    "cliffs_delta": d["delta"], "cliffs_low": d["low"], "cliffs_high": d["high"],
                    "bound": f"b < a: delta <= -{DELTA_BOUND}, interval below 0",
                    "verdict": "passes" if (d["delta"] <= -DELTA_BOUND and eff["high"] < 0.0) else "fails",
                    "note": "; ".join(n for n in (eff["note"], d["note"]) if n)})
    if open_rows:
        out.append(ci_row("t3_wall_elongation", "elongation_wall", "open_field", [float(r["elongation_wall"]) for r in open_rows],
                          "> 0, interval above", lambda ci: "passes" if ci.low > 0.0 else "fails"))
    for m in TRACK_MODES:
        for stat in ("shift_mean", "skew_mean", "peak_shift_mean", "estimate_error_mean"):
            if by[m]:
                out.append(ci_row("reported", stat, m, [by[m][s][stat] for s in sorted(by[m])], "reported", lambda ci: "reported"))
    for stat in ("log_ratio_sr_wall", "log_ratio_raw_wall", "log_ratio_sr_interior", "area_ratio_wall", "area_ratio_interior", "estimate_error_median"):
        if open_rows:
            out.append(ci_row("reported", stat, "open_field", [float(r[stat]) for r in open_rows], "reported", lambda ci: "reported"))
    return out


OUTPUT_FILES = ("sr_track_per_seed.csv", "sr_track_cells.csv", "sr_open_per_seed.csv", "sr_open_cells.csv", "sr_effects.csv", "sr_manifest.json")


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEEDS[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--quick", action="store_true", help=f"{QUICK_LAPS} laps, {QUICK_OPEN_TICKS} open-field ticks, 200 replicates; needs --out")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    laps = QUICK_LAPS if args.quick else TRACK_LAPS
    open_ticks = QUICK_OPEN_TICKS if args.quick else OPEN_TICKS
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    full = tuple(seeds) == DEFAULT_SEEDS and not args.quick and n_boot >= 1000
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a partial run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    started = time.perf_counter()
    track_results = _pool(_track_job, [(m, s, laps) for m in TRACK_MODES for s in seeds], args.workers)
    open_results = _pool(_open_job, [(s, open_ticks) for s in seeds], args.workers)
    track_rows, track_cells = track_tables(track_results)
    open_rows, open_cells = open_tables(open_results)
    effects = effect_rows(track_rows, open_rows, n_boot)
    guards = {f"track/{m}": pseudo_replication_guard([{"seed": r["seed"], "walk": [r["walk"]]} for r in track_results if r["mode"] == m],
                                                     key="walk", allow=True) for m in TRACK_MODES}
    guards["open_field"] = pseudo_replication_guard([{"seed": r["seed"], "walk": [r["walk"]]} for r in open_results], key="walk", allow=True)
    cfg = m2b_config((10.0, 10.0))
    manifest = build_manifest(
        cfg, protocol="sr_fields", seeds=seeds, ticks_requested=sum(r["ticks"] for r in track_results) + open_ticks * len(seeds),
        extra={"learning_rate": LR, "discount": GAMMA, "track": {"bounds": list(TRACK_BOUNDS), "laps": laps, "speed": list(TRACK_SPEED),
                                                                "interior": TRACK_INTERIOR, "modes": list(TRACK_MODES), "stream": TRACK_STREAM},
               "open_field": {"ticks": open_ticks, "grid": OPEN_GRID, "wall_cell": WALL_CELL, "interior_cell": INTERIOR_CELL},
               "config_diff_from_research": [list(map(str, d)) for d in EngineConfig.research().diff(cfg)],
               "n_boot": n_boot, "full_evaluation": full, "quick": args.quick, "prereg": "docs/prereg/m2b_sr_fields.md",
               "dependencies": _dependency_versions(),
               "command": "python3 -m experiments.sr_fields " + " ".join(list(argv) if argv is not None else sys.argv[1:])},
    )
    manifest["guard"] = {k: (v if isinstance(v, int) else str(v)) for k, v in guards.items()}
    manifest["workers"] = args.workers if args.workers is not None else os.cpu_count()
    finish_manifest(manifest, ticks_run=sum(r["ticks"] for r in track_results) + open_ticks * len(seeds),
                    wall_seconds=time.perf_counter() - started)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / OUTPUT_FILES[0], TRACK_PER_SEED_COLUMNS, track_rows)
    write_csv(out / OUTPUT_FILES[1], TRACK_CELL_COLUMNS, track_cells)
    write_csv(out / OUTPUT_FILES[2], OPEN_PER_SEED_COLUMNS, open_rows)
    write_csv(out / OUTPUT_FILES[3], OPEN_CELL_COLUMNS, open_cells)
    write_csv(out / OUTPUT_FILES[4], EFFECT_COLUMNS, effects)
    write_manifest(out / OUTPUT_FILES[5], manifest)
    print("preregistered tests and reported statistics (docs/prereg/m2b_sr_fields.md):")
    for e in effects:
        est = "nan" if (isinstance(e["estimate"], float) and math.isnan(e["estimate"])) else f"{e['estimate']:.4g} [{e['low']:.4g}, {e['high']:.4g}]"
        dl = f" delta {e['cliffs_delta']:+.2f}" if e["cliffs_delta"] != "" else ""
        print(f"  {e['test']:24s} {e['statistic']:22s} {e['b']:11s} {est}{dl} {e['verdict']}")
    print(f"guards: {guards}")
    print(f"wrote {', '.join(OUTPUT_FILES)} to {out} in {manifest['timing']['wall_seconds']:.1f} s")
    return {"track": track_rows, "track_cells": track_cells, "open": open_rows, "open_cells": open_cells, "effects": effects, "guards": guards}


if __name__ == "__main__":
    main()
