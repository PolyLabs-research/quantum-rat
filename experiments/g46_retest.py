"""The retest after the audit of 2026-10-27 (docs/prereg/g46_retest.md; decisions G46).

    python3 -m experiments.g46_retest --workers 28                 # both parts, the registered seeds -> docs/data/g46
    python3 -m experiments.g46_retest --quick --out /tmp/g46       # the smoke test's run (two spent seeds, short budgets)

Part H, hidden food (fresh seeds 17-46, 3,000 ticks): the research profile's arms ``no_steer``, ``steer_u4`` (the
scenario's own U = 4) and ``steer_one_rate`` with the hidden sites sensed as before G46 and not sensed; the legacy
profile at sensor noise 0.03 (G23's setting B), memory on and off, as recorded, with the rays fixed, and with both
leaks fixed. Part G, the RQ4(a) gate (fresh seeds 125-154, the confirmatory settings, the sensing fixed, trials
started still) under four start conditions: the estimate told the true start (``anchor``, the registered protocol),
the centre, nothing (``carry``), and nothing with neither the heading oracle nor the wall reset (``embodied``).

``--quick`` refuses the committed output directory, so its meaningless numbers cannot overwrite the tables.
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

from analysis.stats import bootstrap_ci, paired_effect, pseudo_replication_guard
from experiments import console_ablation as ca
from experiments import rq4a_gate as rg
from experiments.linear_track_replay import _dependency_versions, _stat_seed, write_csv
from core.config import PRE_G50
from metrics.manifest import build_manifest, finish_manifest, write_manifest

PREREG = "docs/prereg/g46_retest.md"
FOOD_SEEDS: Tuple[int, ...] = tuple(range(17, 47))
GATE_SEEDS: Tuple[int, ...] = tuple(range(125, 155))
TICKS = 3000
QUICK_FOOD_SEEDS: Tuple[int, ...] = (1, 2)  # the smoke test runs on spent seeds, never on the registered ones
QUICK_GATE_SEEDS: Tuple[int, ...] = (31, 32)
QUICK_TICKS = 300
DEFAULT_OUT = Path("docs/data/g46")
N_BOOT = 10_000

LEAKS: Dict[str, Any] = {"sensors.unseen_block_rays": True, "reward.shape_hidden": True}
FIXED: Dict[str, Any] = {"sensors.unseen_block_rays": False, "reward.shape_hidden": False}
FOOD_ARMS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "research": {"no_steer": {"basal_ganglia.value_gain": 0.0}, "steer_u4": {},
                 "steer_one_rate": {"place.reward_unlearning_rate": None}},
    "legacy": {"no_steer": {"basal_ganglia.value_gain": 0.0}, "steer": {}},
}
FOOD_CONDITIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "research": {"pre_g46": LEAKS, "g46": {}},
    "legacy": {"pre_g46": {}, "rays_fixed": {"sensors.unseen_block_rays": False}, "g46": FIXED},
}
# Registered before the research profile adopted G48-G49's instrument (G50): pinned, so the design means what it said.
PROFILE_OVERRIDES: Dict[str, Dict[str, Any]] = {"research": dict(PRE_G50), "legacy": {"sensors.noise": 0.03}}
GATE_CONDITIONS: Dict[str, Dict[str, Any]] = {
    "anchor": {"start_estimate": "anchor", "estimate": "oracle_reset"},
    "centre": {"start_estimate": "centre", "estimate": "oracle_reset"},
    "carry": {"start_estimate": "carry", "estimate": "oracle_reset"},
    "embodied": {"start_estimate": "carry", "estimate": "integrated"},
}
FOOD_COLUMNS = ("profile", "condition", "arm", "seed", "finds", "unique_sites", "wall_fraction", "orbit_fraction", "digest")
FOOD_EFFECT_COLUMNS = ("profile", "test", "condition", "a", "b", "n", "mean_a", "mean_b", "estimate", "low", "high", "wins", "losses", "note")
CROSS_COLUMNS = ("test", "a", "b", "source", "n", "mean_a", "mean_b", "estimate", "low", "high", "note")


def food_overrides(profile: str, condition: str) -> Dict[str, Any]:
    return {**PROFILE_OVERRIDES[profile], **FOOD_CONDITIONS[profile][condition]}


def _food_job(job: Tuple[str, str, str, int, int]) -> Dict[str, Any]:
    profile, condition, arm, seed, ticks = job
    r = ca.run_one(("hidden_food", profile, arm, seed, ticks, food_overrides(profile, condition), FOOD_ARMS[profile]))
    m = r["metrics"]
    return {"profile": profile, "condition": condition, "arm": arm, "seed": seed, "finds": m["finds"],
            "unique_sites": m["unique_sites"], "wall_fraction": m["wall_fraction"], "orbit_fraction": m["orbit_fraction"],
            "digest": r["digest"]}


def run_food(seeds: Sequence[int], ticks: int, workers: Optional[int]) -> List[Dict[str, Any]]:
    jobs = [(p, c, a, s, ticks) for p in FOOD_CONDITIONS for c in FOOD_CONDITIONS[p] for a in FOOD_ARMS[p] for s in seeds]
    if workers == 1:
        return [_food_job(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_food_job, jobs, chunksize=1))


def _values(rows: Sequence[Mapping[str, Any]], profile: str, condition: str, arm: str, seeds: Sequence[int]) -> np.ndarray:
    by = {int(r["seed"]): float(r["finds"]) for r in rows if (r["profile"], r["condition"], r["arm"]) == (profile, condition, arm)}
    return np.array([by[s] for s in seeds], dtype=np.float64)


def _paired(a: np.ndarray, b: np.ndarray, n_boot: int, *key: Any) -> Dict[str, Any]:
    """b - a, paired by seed, with its BCa interval and the seeds b wins and loses."""
    eff = paired_effect(a, b, n_boot=n_boot, seed=_stat_seed(*key))
    return {"n": int(a.size), "mean_a": eff["mean_a"], "mean_b": eff["mean_b"], "estimate": eff["mean_diff"],
            "low": eff["low"], "high": eff["high"], "wins": int(np.sum(b > a)), "losses": int(np.sum(b < a)), "note": eff["note"]}


def food_effects(rows: Sequence[Mapping[str, Any]], seeds: Sequence[int], n_boot: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    guard: Dict[str, Any] = {}
    for p, conditions in FOOD_CONDITIONS.items():
        for c in conditions:
            for arm in FOOD_ARMS[p]:
                v = _values(rows, p, c, arm, seeds)
                digests = {int(r["seed"]): r["digest"] for r in rows if (r["profile"], r["condition"], r["arm"]) == (p, c, arm)}
                guard[f"{p}/{c}/{arm}"] = pseudo_replication_guard([digests[s] for s in seeds]) if len(seeds) > 1 else 1
                ci = bootstrap_ci(v, np.mean, n_boot=n_boot, seed=_stat_seed("g46_food_mean", p, c, arm))
                out.append({"profile": p, "test": "mean_finds", "condition": c, "b": arm, "n": ci.n, "mean_b": ci.estimate,
                            "estimate": ci.estimate, "low": ci.low, "high": ci.high, "note": ci.note})
            base = _values(rows, p, c, "no_steer", seeds)
            for arm in FOOD_ARMS[p]:
                if arm == "no_steer":
                    continue
                v = _values(rows, p, c, arm, seeds)
                out.append({"profile": p, "test": "steer_minus_no_steer", "condition": c, "a": "no_steer", "b": arm,
                            **_paired(base, v, n_boot, "g46_food_steer", p, c, arm)})
                if p == "legacy":
                    ci = rg.ratio_ci(v, base, n_boot, _stat_seed("g46_food_ratio", p, c, arm))
                    out.append({"profile": p, "test": "steer_over_no_steer", "condition": c, "a": "no_steer", "b": arm,
                                "n": int(v.size), "mean_a": float(np.mean(base)), "mean_b": float(np.mean(v)),
                                "estimate": ci.estimate, "low": ci.low, "high": ci.high, "note": ci.note})
        for c in conditions:
            if c == "pre_g46":
                continue
            for arm in FOOD_ARMS[p]:
                out.append({"profile": p, "test": "fix_effect", "condition": f"{c} - pre_g46", "a": "pre_g46", "b": c,
                            "note": arm, **{k: v for k, v in _paired(_values(rows, p, "pre_g46", arm, seeds),
                                                                    _values(rows, p, c, arm, seeds), n_boot,
                                                                    "g46_food_fix", p, c, arm).items() if k != "note"}})
    return out, guard


def _find(effects: Sequence[Mapping[str, Any]], **match: Any) -> Mapping[str, Any]:
    hits = [e for e in effects if all(e.get(k) == v for k, v in match.items())]
    if len(hits) != 1:
        raise KeyError(f"{match}: {len(hits)} rows")
    return hits[0]


def food_predictions(effects: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """H1-H5 of the preregistration, scored as written there."""
    def diff(p, c, arm):
        return _find(effects, profile=p, test="steer_minus_no_steer", condition=c, b=arm)

    def mean(p, c, arm):
        return _find(effects, profile=p, test="mean_finds", condition=c, b=arm)["estimate"]

    h1 = diff("research", "pre_g46", "steer_u4")
    h2 = diff("research", "g46", "steer_u4")
    h3 = _find(effects, profile="legacy", test="steer_over_no_steer", condition="pre_g46", b="steer")
    h3d = diff("legacy", "pre_g46", "steer")
    h4 = diff("legacy", "g46", "steer")
    h5 = diff("legacy", "rays_fixed", "steer")
    return {
        "H1": {"holds": abs(h1["estimate"]) <= 3.0 and h1["low"] <= 0.0 <= h1["high"],
               "read": f"research pre_g46 steer_u4 - no_steer {h1['estimate']:+.2f} [{h1['low']:+.2f}, {h1['high']:+.2f}]"},
        "H2": {"holds": (45.0 <= mean("research", "g46", "no_steer") <= 55.0 and 37.0 <= mean("research", "g46", "steer_u4") <= 47.0
                         and h2["high"] < 0.0 and mean("research", "g46", "steer_one_rate") < mean("research", "g46", "steer_u4")),
               "read": (f"research g46 no_steer {mean('research', 'g46', 'no_steer'):.2f}, steer_u4 {mean('research', 'g46', 'steer_u4'):.2f}, "
                        f"steer_one_rate {mean('research', 'g46', 'steer_one_rate'):.2f}; steer_u4 - no_steer {h2['estimate']:+.2f} "
                        f"[{h2['low']:+.2f}, {h2['high']:+.2f}]")},
        "H3": {"holds": 2.4 <= h3["estimate"] <= 3.6 and h3d["low"] > 0.0,
               "read": f"legacy pre_g46 steer / no_steer {h3['estimate']:.2f} [{h3['low']:.2f}, {h3['high']:.2f}]; diff {h3d['estimate']:+.2f}"},
        "H4": {"holds": h4["high"] < 0.0,
               "read": f"legacy g46 steer - no_steer {h4['estimate']:+.2f} [{h4['low']:+.2f}, {h4['high']:+.2f}], steer wins {h4['wins']}/{h4['n']}"},
        "H5": {"holds": h5["estimate"] < 0.0,
               "read": f"legacy rays_fixed steer - no_steer {h5['estimate']:+.2f} [{h5['low']:+.2f}, {h5['high']:+.2f}] (reported)"},
    }


def run_gate(seeds: Sequence[int], trials: int, workers: Optional[int]) -> Dict[str, List[Dict[str, Any]]]:
    return {c: rg.run_all(seeds, trials, workers, rg.SOURCES, "per_feature", None, "discrete", False,
                          still_start=True, pre_g46=False, pre_g50=True, **opts)
            for c, opts in GATE_CONDITIONS.items()}


def _sr_hidden(per_seed: Sequence[Mapping[str, Any]], source: str = "sr") -> Tuple[List[int], np.ndarray]:
    q = {int(r["seed"]): float(r["success_test"]) for r in per_seed if r["source"] == source and r["session"] == "hidden"}
    seeds = sorted(q)
    return seeds, np.array([q[s] for s in seeds], dtype=np.float64)


def gate_cross(per_seed: Mapping[str, Sequence[Mapping[str, Any]]], n_boot: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for source in ("sr", "tabular"):
        _, anchor = _sr_hidden(per_seed["anchor"], source)
        for c in GATE_CONDITIONS:
            if c == "anchor":
                continue
            _, v = _sr_hidden(per_seed[c], source)
            e = _paired(anchor, v, n_boot, "g46_gate_cross", source, c)
            out.append({"test": "condition_minus_anchor", "a": "anchor", "b": c, "source": source,
                        **{k: e[k] for k in ("n", "mean_a", "mean_b", "estimate", "low", "high", "note")}})
    for c in GATE_CONDITIONS:
        _, none = _sr_hidden(per_seed[c], "none")
        for source in ("sr", "tabular"):
            _, v = _sr_hidden(per_seed[c], source)
            e = _paired(none, v, n_boot, "g46_gate_control", source, c)
            out.append({"test": "source_minus_no_steering", "a": f"{c}/none", "b": f"{c}/{source}", "source": source,
                        **{k: e[k] for k in ("n", "mean_a", "mean_b", "estimate", "low", "high", "note")}})
    return out


def gate_predictions(per_seed: Mapping[str, Sequence[Mapping[str, Any]]], effects: Mapping[str, Sequence[Mapping[str, Any]]],
                     cross: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """G1-G3 of the preregistration, scored as written there."""
    def control(c):
        return _find(cross, test="source_minus_no_steering", b=f"{c}/sr")

    sr_anchor = float(np.mean(_sr_hidden(per_seed["anchor"])[1]))
    ratio = _find(effects["anchor"], test="g1_relative_success")
    g2 = {c: (float(np.mean(_sr_hidden(per_seed[c])[1])), control(c)) for c in ("centre", "carry")}
    g3 = control("embodied")
    return {
        "G1": {"holds": sr_anchor >= 0.95 and ratio["estimate"] >= 0.8,
               "read": f"anchor SR hidden {sr_anchor:.3f}; hidden / visible {ratio['estimate']:.3f} [{ratio['low']:.3f}, {ratio['high']:.3f}]"},
        "G2": {"holds": all(0.20 <= m <= 0.55 and e["low"] > 0.0 for m, e in g2.values()),
               "read": "; ".join(f"{c} SR hidden {m:.3f}, SR - none {e['estimate']:+.3f} [{e['low']:+.3f}, {e['high']:+.3f}]"
                                 for c, (m, e) in g2.items())},
        "G3": {"holds": g3["low"] <= 0.0,
               "read": f"embodied SR hidden {g3['mean_b']:.3f}, none {g3['mean_a']:.3f}; SR - none {g3['estimate']:+.3f} "
                       f"[{g3['low']:+.3f}, {g3['high']:+.3f}]"},
    }


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=N_BOOT)
    parser.add_argument("--quick", action="store_true", help="two seeds per part, short budgets, 200 replicates; needs --out")
    parser.add_argument("--parts", default="food,gate", help="comma-separated: food, gate")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    parts = [p.strip() for p in args.parts.split(",") if p.strip()]
    if not set(parts) <= {"food", "gate"}:
        parser.error("--parts takes food and/or gate")
    full = not args.quick and args.n_boot >= 1000 and set(parts) == {"food", "gate"}
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a partial or quick run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    food_seeds = QUICK_FOOD_SEEDS if args.quick else FOOD_SEEDS
    gate_seeds = QUICK_GATE_SEEDS if args.quick else GATE_SEEDS
    ticks = QUICK_TICKS if args.quick else TICKS
    trials = rg.QUICK_TRIALS if args.quick else rg.TRIALS
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    started = time.perf_counter()
    summary: Dict[str, Any] = {"prereg": PREREG, "full_evaluation": full, "quick": args.quick}
    ticks_run = 0
    if "food" in parts:
        rows = run_food(food_seeds, ticks, args.workers)
        effects, guard = food_effects(rows, food_seeds, n_boot)
        write_csv(args.out / "hidden_food" / "per_seed.csv", FOOD_COLUMNS, rows)
        write_csv(args.out / "hidden_food" / "effects.csv", FOOD_EFFECT_COLUMNS, effects)
        summary["food"] = {"seeds": list(food_seeds), "ticks": ticks, "guard": guard,
                           "predictions": food_predictions(effects) if not args.quick else "not scored (quick)"}
        ticks_run += ticks * len(rows)
    if "gate" in parts:
        trial_rows = run_gate(gate_seeds, trials, args.workers)
        learning = trials // 2
        per_seed = {c: rg.per_seed_rows(t, learning) for c, t in trial_rows.items()}
        effects_g = {c: rg.effect_rows(per_seed[c], n_boot) for c in trial_rows}
        for c, t in trial_rows.items():
            d = args.out / "gate" / c
            write_csv(d / "gate_trials.csv", rg.TRIAL_COLUMNS, t)
            write_csv(d / "gate_per_seed.csv", rg.PER_SEED_COLUMNS, per_seed[c])
            write_csv(d / "gate_curve.csv", rg.CURVE_COLUMNS, rg.curve_rows(t, n_boot))
            write_csv(d / "gate_effects.csv", rg.EFFECT_COLUMNS, effects_g[c])
            ticks_run += sum(int(r["ticks"]) for r in t)
        cross = gate_cross(per_seed, n_boot)
        write_csv(args.out / "gate" / "cross_condition_effects.csv", CROSS_COLUMNS, cross)
        summary["gate"] = {"seeds": list(gate_seeds), "trials": trials, "conditions": GATE_CONDITIONS,
                           "predictions": gate_predictions(per_seed, effects_g, cross) if not args.quick else "not scored (quick)"}
    cfg = rg.gate_config("sr", "per_feature")
    manifest = build_manifest(cfg, protocol="g46_retest", seeds=sorted(set(food_seeds) | set(gate_seeds)), ticks_requested=ticks_run,
                              extra={"prereg": PREREG, "parts": parts, "food_conditions": FOOD_CONDITIONS, "food_arms": FOOD_ARMS,
                                     "profile_overrides": PROFILE_OVERRIDES, "gate_conditions": GATE_CONDITIONS,
                                     "full_evaluation": full, "quick": args.quick, "n_boot": n_boot,
                                     "dependencies": _dependency_versions(),
                                     "command": "python3 -m experiments.g46_retest " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    manifest["workers"] = args.workers
    finish_manifest(manifest, ticks_run=ticks_run, wall_seconds=time.perf_counter() - started)
    args.out.mkdir(parents=True, exist_ok=True)
    write_manifest(args.out / "manifest.json", manifest)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str))
    for part in ("food", "gate"):
        preds = summary.get(part, {}).get("predictions")
        if isinstance(preds, dict):
            for name, p in preds.items():
                print(f"{name}: {'holds' if p['holds'] else 'FAILS'}  {p['read']}")
    print(f"wrote {args.out} in {time.perf_counter() - started:.1f} s{'' if full else ' (EXPLORATORY: not the registered run)'}")
    return summary


if __name__ == "__main__":
    main()
