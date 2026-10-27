"""M3 step 2, Part 1: reachable value probes over every task (docs/prereg/m3_step2.md; decisions G49).

    python3 -m experiments.m3_reachable --workers 28                 # fresh seeds 215-244 -> docs/data/m3/reachable
    python3 -m experiments.m3_reachable --quick --out /tmp/reach     # the smoke test's run (spent seeds, short budgets)

Every condition has the research profile with sideways odometry (G48); the probes are off (as every run so far) or on
(``value_memory.reachable_probes`` with ``sensors.free_space_sensing``: each direction of the value fan is read only
as far as the agent sees it could go). The battery: the RQ4(a) gate in the open and L arenas, told the start or told
nothing with the distal cues (G48), the three sources and both sessions, by start group; hidden food (the research
scenario, U = 4), memory steering and none; the track without reward and the open field (G44's measures), the reflex
alone.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from analysis.stats import bootstrap_ci, paired_effect
from experiments import body_characterisation as bc
from experiments import console_ablation as ca
from experiments import rq4a_gate as rg
from experiments.linear_track_replay import _dependency_versions, _stat_seed, write_csv
from core.config import PRE_G50
from metrics.manifest import build_manifest, finish_manifest, write_manifest

PREREG = "docs/prereg/m3_step2.md"
SEEDS: Tuple[int, ...] = tuple(range(215, 245))
QUICK_SEEDS: Tuple[int, ...] = (31, 32)  # spent
DEFAULT_OUT = Path("docs/data/m3/reachable")
N_BOOT = 10_000
TICKS = 3000
BASE: Dict[str, Any] = {"sensors.lateral_odometry": True}
PROBES: Dict[str, Dict[str, Any]] = {
    "off": {},
    "on": {"sensors.free_space_sensing": True, "value_memory.reachable_probes": True},
}
GATE: Dict[str, Dict[str, Any]] = {
    "open_anchor": {"layout": "open", "start_estimate": "anchor"},
    "open_cues": {"layout": "open", "start_estimate": "carry", "landmarks": True},
    "L_anchor": {"layout": "L", "start_estimate": "anchor"},
    "L_cues": {"layout": "L", "start_estimate": "carry", "landmarks": True},
}
GROUPS: Dict[str, Tuple[int, ...]] = {
    "all": tuple(range(len(rg.STARTS))),
    "blocked": rg.blocked_starts("L"),
    "direct": tuple(i for i in range(len(rg.STARTS)) if i not in rg.blocked_starts("L")),
}
GROUP_COLUMNS = ("condition", "probes", "source", "session", "seed", "group", "trials", "success", "latency_median")
FOOD_COLUMNS = ("probes", "arm", "seed", "finds", "orbit_fraction", "digest")
REFLEX_COLUMNS = ("world", "probes", "seed", "ticks_per_lap", "laps", "stall_share", "forward_share", "wall_zone_share",
                  "coverage", "orbit_share")
EFFECT_COLUMNS = ("test", "statistic", "a", "b", "n", "mean_a", "mean_b", "estimate", "low", "high", "wins", "losses", "note")


def _overrides(probes: str) -> Dict[str, Any]:
    """Registered before the research profile adopted these (G50): the old profile, then the design's own fields."""
    return {**PRE_G50, **BASE, **PROBES[probes]}


def run_gate(seeds: Sequence[int], trials: int, workers: Optional[int]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    return {(c, p): rg.run_all(seeds, trials, workers, rg.SOURCES, "per_feature", None, "discrete", False,
                               still_start=True, pre_g46=False, pre_g50=True, overrides=_overrides(p), **opts)
            for c, opts in GATE.items() for p in PROBES}


def gate_groups(cond: str, probes: str, trials: Sequence[Mapping[str, Any]], learning: int) -> List[Dict[str, Any]]:
    out = []
    for src in rg.SOURCES:
        for ses in rg.SESSIONS:
            for seed in sorted({int(r["seed"]) for r in trials}):
                for g, starts in GROUPS.items():
                    rows = [r for r in trials if r["source"] == src and r["session"] == ses and int(r["seed"]) == seed
                            and r["trial"] > learning and int(r["start"]) in starts]
                    hits = [r for r in rows if r["reached"]]
                    out.append({"condition": cond, "probes": probes, "source": src, "session": ses, "seed": seed, "group": g,
                                "trials": len(rows), "success": sum(r["reached"] for r in rows) / len(rows) if rows else math.nan,
                                "latency_median": float(np.median([r["latency"] for r in hits])) if hits else math.nan})
    return out


def _food_job(job: Tuple[str, str, int, int]) -> Dict[str, Any]:
    probes, arm, seed, ticks = job
    r = ca.run_one(("hidden_food", "research", arm, seed, ticks, _overrides(probes), ca.ARMS))
    return {"probes": probes, "arm": arm, "seed": seed, "finds": r["metrics"]["finds"],
            "orbit_fraction": r["metrics"]["orbit_fraction"], "digest": r["digest"]}


def _reflex_job(job: Tuple[str, str, int, int]) -> Dict[str, Any]:
    world, probes, seed, ticks = job
    r = bc.run_world(world, _overrides(probes), seed, ticks)
    return {"world": world, "probes": probes, "seed": seed, **{k: r.get(k, "") for k in REFLEX_COLUMNS if k in r}}


def _pool(fn, jobs, workers):
    if workers == 1:
        return [fn(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, jobs, chunksize=1))


def _vec(rows: Sequence[Mapping[str, Any]], seeds: Sequence[int], stat: str, **match: Any) -> np.ndarray:
    by = {int(r["seed"]): float(r[stat]) for r in rows if all(r[k] == v for k, v in match.items())}
    return np.array([by[s] for s in seeds], dtype=np.float64)


def _effect(test: str, statistic: str, a_name: str, a: np.ndarray, b_name: str, b: np.ndarray, n_boot: int) -> Dict[str, Any]:
    """b - a, paired by seed, over the seeds where both are defined."""
    keep = np.isfinite(a) & np.isfinite(b)
    a, b = a[keep], b[keep]
    if a.size < 2 or (np.all(a == a[0]) and np.all(b == b[0]) and a[0] == b[0]):
        same = a.size >= 2
        return {"test": test, "statistic": statistic, "a": a_name, "b": b_name, "n": int(a.size),
                "mean_a": float(np.mean(a)) if a.size else math.nan, "mean_b": float(np.mean(b)) if b.size else math.nan,
                "estimate": 0.0 if same else math.nan, "low": 0.0 if same else math.nan, "high": 0.0 if same else math.nan,
                "wins": 0, "losses": 0, "note": "identical constant vectors" if same else "fewer than two seeds"}
    eff = paired_effect(a, b, n_boot=n_boot, seed=_stat_seed("m3_reach", test, a_name, b_name))
    return {"test": test, "statistic": statistic, "a": a_name, "b": b_name, "n": int(a.size), "mean_a": eff["mean_a"],
            "mean_b": eff["mean_b"], "estimate": eff["mean_diff"], "low": eff["low"], "high": eff["high"],
            "wins": int(np.sum(b > a)), "losses": int(np.sum(b < a)), "note": eff["note"]}


def effects(groups, food, reflex, seeds, n_boot) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in GATE:
        for src in rg.SOURCES:
            for ses in rg.SESSIONS:
                for g in GROUPS:
                    m = dict(condition=c, source=src, session=ses, group=g)
                    out.append(_effect("probes_gate", f"{ses} success, {g} starts, probes on - off", f"{c}/off/{src}/{g}",
                                       _vec(groups, seeds, "success", probes="off", **m), f"{c}/on/{src}/{g}",
                                       _vec(groups, seeds, "success", probes="on", **m), n_boot))
    for p in PROBES:  # the memory against no steering, hidden, per condition and group
        for c in GATE:
            for g in GROUPS:
                out.append(_effect("memory_gate", f"hidden success, {g} starts, sr - none, probes {p}", f"{c}/{p}/none/{g}",
                                   _vec(groups, seeds, "success", condition=c, probes=p, source="none", session="hidden", group=g),
                                   f"{c}/{p}/sr/{g}",
                                   _vec(groups, seeds, "success", condition=c, probes=p, source="sr", session="hidden", group=g), n_boot))
    for arm in ca.ARMS:
        out.append(_effect("probes_food", f"hidden food finds, {arm}, probes on - off", f"off/{arm}",
                           _vec(food, seeds, "finds", probes="off", arm=arm), f"on/{arm}", _vec(food, seeds, "finds", probes="on", arm=arm), n_boot))
    for world, stats in (("track", ("ticks_per_lap", "stall_share", "forward_share")), ("open", ("wall_zone_share", "coverage", "orbit_share"))):
        for stat in stats:
            out.append(_effect("probes_reflex", f"{world} {stat}, probes on - off", f"{world}/off",
                               _vec(reflex, seeds, stat, world=world, probes="off"), f"{world}/on",
                               _vec(reflex, seeds, stat, world=world, probes="on"), n_boot))
    return out


def _find(effs, **m):
    hits = [e for e in effs if all(e.get(k) == v for k, v in m.items())]
    if len(hits) != 1:
        raise KeyError(f"{m}: {len(hits)}")
    return hits[0]


def predictions(groups, effs, seeds) -> Dict[str, Dict[str, Any]]:
    """R1-R5 of the preregistration, scored as written there."""
    def mean(stat="success", **m):
        v = _vec(groups, seeds, stat, **m)
        return float(np.nanmean(v)) if np.isfinite(v).any() else math.nan

    r1 = _find(effs, test="probes_gate", b="L_anchor/on/sr/blocked", statistic="hidden success, blocked starts, probes on - off")
    r1_on = mean(condition="L_anchor", probes="on", source="sr", session="hidden", group="blocked")
    lat_l = float(np.nanmedian(_vec(groups, seeds, "latency_median", condition="L_anchor", probes="on", source="sr", session="hidden", group="blocked")))
    lat_o = float(np.nanmedian(_vec(groups, seeds, "latency_median", condition="open_anchor", probes="on", source="sr", session="hidden", group="blocked")))
    vis = mean(condition="L_anchor", probes="on", source="sr", session="visible", group="all")
    cues = mean(condition="L_cues", probes="on", source="sr", session="hidden", group="all")
    open_d = [abs(_find(effs, test="probes_gate", b=f"{c}/on/{src}/all", statistic=f"{ses} success, all starts, probes on - off")["estimate"])
              for c in ("open_anchor", "open_cues") for src in rg.SOURCES for ses in rg.SESSIONS]
    food_d = abs(_find(effs, test="probes_food", b="on/steer")["estimate"])
    reflex_d = [abs(e["estimate"]) for e in effs if e["test"] == "probes_reflex"]
    controls = [mean(condition=c, probes=p, source="none", session="hidden", group="all") for c in GATE for p in PROBES]
    ctrl_d = [abs(_find(effs, test="probes_gate", b=f"{c}/on/none/all", statistic="hidden success, all starts, probes on - off")["estimate"]) for c in GATE]
    return {
        "R1": {"holds": r1_on >= 0.90 and r1["low"] > 0.4,
               "read": f"L told the start, SR hidden, blocked: on {r1_on:.3f}; on - off {r1['estimate']:+.3f} [{r1['low']:+.3f}, {r1['high']:+.3f}]"},
        "R2": {"holds": lat_l <= 2.5 * lat_o, "read": f"median latency, blocked starts, probes on: L {lat_l:.1f} against open {lat_o:.1f} (x{lat_l / lat_o:.2f})"},
        "R3": {"holds": vis >= 0.90 and cues >= 0.85, "read": f"L told the start SR visible {vis:.3f}; L told nothing with cues SR hidden {cues:.3f}"},
        "R4": {"holds": max(open_d) <= 0.03 and food_d <= 3.0 and max(reflex_d) == 0.0,
               "read": f"open arena largest |on - off| {max(open_d):.3f}; hidden food |on - off| {food_d:.2f} finds; reflex measures largest |diff| {max(reflex_d):.4g}"},
        "R5": {"holds": max(controls) <= 0.05 and max(ctrl_d) == 0.0,
               "read": f"no steering hidden, largest {max(controls):.3f}; largest change with the probes {max(ctrl_d):.4g}"},
    }


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=N_BOOT)
    parser.add_argument("--quick", action="store_true", help="two spent seeds, 8 trials, 300 ticks, 200 replicates; needs --out")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    full = not args.quick and args.n_boot >= 1000
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a quick run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    seeds = QUICK_SEEDS if args.quick else SEEDS
    trials = rg.QUICK_TRIALS if args.quick else rg.TRIALS
    ticks = 300 if args.quick else TICKS
    learning = trials // 2
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    started = time.perf_counter()
    gate_rows = run_gate(seeds, trials, args.workers)
    groups: List[Dict[str, Any]] = []
    for (c, p), rows in gate_rows.items():
        d = args.out / "gate" / f"{c}_{p}"
        per_seed = rg.per_seed_rows(rows, learning)
        write_csv(d / "gate_trials.csv", rg.TRIAL_COLUMNS, rows)
        write_csv(d / "gate_per_seed.csv", rg.PER_SEED_COLUMNS, per_seed)
        write_csv(d / "gate_effects.csv", rg.EFFECT_COLUMNS, rg.effect_rows(per_seed, n_boot))
        groups += gate_groups(c, p, rows, learning)
    food = _pool(_food_job, [(p, a, s, ticks) for p in PROBES for a in ca.ARMS for s in seeds], args.workers)
    reflex = _pool(_reflex_job, [(w, p, s, ticks) for w in ("track", "open") for p in PROBES for s in seeds], args.workers)
    effs = effects(groups, food, reflex, seeds, n_boot)
    write_csv(args.out / "gate" / "by_start_group.csv", GROUP_COLUMNS, groups)
    write_csv(args.out / "hidden_food.csv", FOOD_COLUMNS, food)
    write_csv(args.out / "reflex.csv", REFLEX_COLUMNS, reflex)
    write_csv(args.out / "effects.csv", EFFECT_COLUMNS, effs)
    preds = predictions(groups, effs, seeds) if not args.quick else "not scored (quick)"
    cfg = rg.gate_config("sr", "per_feature", overrides=_overrides("on"))
    manifest = build_manifest(cfg, protocol="m3_reachable", seeds=list(seeds), ticks_requested=0,
                              extra={"prereg": PREREG, "base": BASE, "probes": PROBES, "gate_conditions": GATE,
                                     "groups": {k: list(v) for k, v in GROUPS.items()}, "trials": trials, "ticks": ticks,
                                     "n_boot": n_boot, "full_evaluation": full, "quick": args.quick,
                                     "dependencies": _dependency_versions(),
                                     "command": "python3 -m experiments.m3_reachable " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    manifest["workers"] = args.workers
    finish_manifest(manifest, ticks_run=0, wall_seconds=time.perf_counter() - started)
    args.out.mkdir(parents=True, exist_ok=True)
    write_manifest(args.out / "manifest.json", manifest)
    (args.out / "summary.json").write_text(json.dumps({"prereg": PREREG, "seeds": list(seeds), "full_evaluation": full,
                                                       "predictions": preds}, indent=1, sort_keys=True, default=str))
    if isinstance(preds, dict):
        for k, v in preds.items():
            print(f"{k}: {'holds' if v['holds'] else 'FAILS'}  {v['read']}")
    print(f"wrote {args.out} in {time.perf_counter() - started:.1f} s{'' if full else ' (EXPLORATORY: not the registered run)'}")
    return {"groups": groups, "food": food, "reflex": reflex, "effects": effs}


if __name__ == "__main__":
    main()
