"""The RQ4(a) gate with barriers in the way (docs/prereg/g47_barrier_gate.md; decisions G47).

    python3 -m experiments.g47_barrier_gate --phase pilot --workers 28        # spent seeds 31-42, exploratory -> docs/data/g47/pilot
    python3 -m experiments.g47_barrier_gate --phase confirmatory --workers 28 # fresh seeds 155-184 -> docs/data/g47/confirmatory
    python3 -m experiments.g47_barrier_gate --quick --out /tmp/g47            # the smoke test's run

The gate's protocol (the confirmatory settings: per-feature rule, one rate, three sources, both sessions, 40 trials,
the gate reads 21-40) on the research profile, trials started still, in two arenas, ``open`` and ``L`` (two solid
walls shielding the goal's south and west sides, ``experiments.rq4a_gate.LAYOUTS``), each with the estimate told the
true start (``anchor``) and told nothing (``carry``). In ``L`` the west and the south start need a detour
(``rq4a_gate.blocked_starts``); the east and the north pass a gap. Nothing in the agent knows the barriers: it sees
them as walls, is stopped by them, and learns what it learns from where it has been.
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
from experiments import rq4a_gate as rg
from experiments.linear_track_replay import _dependency_versions, _stat_seed, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

PREREG = "docs/prereg/g47_barrier_gate.md"
PHASES: Dict[str, Dict[str, Any]] = {
    "pilot": {"seeds": tuple(range(31, 43)), "out": Path("docs/data/g47/pilot")},  # spent seeds: exploratory
    "confirmatory": {"seeds": tuple(range(155, 185)), "out": Path("docs/data/g47/confirmatory")},
}
QUICK_SEEDS: Tuple[int, ...] = (31, 32)
N_BOOT = 10_000
CONDITIONS: Dict[str, Dict[str, Any]] = {
    f"{layout}_{start}": {"layout": layout, "start_estimate": start}
    for layout in ("open", "L") for start in ("anchor", "carry")
}
GROUPS = {"blocked": rg.blocked_starts("L"), "direct": tuple(i for i in range(len(rg.STARTS)) if i not in rg.blocked_starts("L"))}
GROUP_COLUMNS = ("condition", "source", "session", "seed", "group", "trials", "success", "latency_median")
EFFECT_COLUMNS = ("test", "statistic", "a", "b", "n", "mean_a", "mean_b", "estimate", "low", "high", "wins", "losses", "note")


def run_conditions(seeds: Sequence[int], trials: int, workers: Optional[int]) -> Dict[str, List[Dict[str, Any]]]:
    return {c: rg.run_all(seeds, trials, workers, rg.SOURCES, "per_feature", None, "discrete", False,
                          still_start=True, pre_g46=False, pre_g50=True, **opts)  # registered before G50
            for c, opts in CONDITIONS.items()}


def group_rows(condition: str, trials: Sequence[Mapping[str, Any]], learning: int) -> List[Dict[str, Any]]:
    """Per source, session, seed and start group (``GROUPS``): success and median latency over the read trials."""
    out = []
    for src in rg.SOURCES:
        for ses in rg.SESSIONS:
            for seed in sorted({int(r["seed"]) for r in trials}):
                for g, starts in GROUPS.items():
                    rows = [r for r in trials if r["source"] == src and r["session"] == ses and int(r["seed"]) == seed
                            and r["trial"] > learning and int(r["start"]) in starts]
                    hits = [r for r in rows if r["reached"]]
                    out.append({"condition": condition, "source": src, "session": ses, "seed": seed, "group": g,
                                "trials": len(rows), "success": sum(r["reached"] for r in rows) / len(rows) if rows else math.nan,
                                "latency_median": float(np.median([r["latency"] for r in hits])) if hits else math.nan})
    return out


def _vec(rows: Sequence[Mapping[str, Any]], seeds: Sequence[int], **match: Any) -> np.ndarray:
    by = {int(r["seed"]): float(r["success"]) for r in rows if all(r[k] == v for k, v in match.items())}
    return np.array([by[s] for s in seeds], dtype=np.float64)


def _effect(test: str, statistic: str, a_name: str, a: np.ndarray, b_name: str, b: np.ndarray, n_boot: int) -> Dict[str, Any]:
    """b - a, paired by seed."""
    eff = paired_effect(a, b, n_boot=n_boot, seed=_stat_seed("g47", test, a_name, b_name))
    return {"test": test, "statistic": statistic, "a": a_name, "b": b_name, "n": int(a.size), "mean_a": eff["mean_a"],
            "mean_b": eff["mean_b"], "estimate": eff["mean_diff"], "low": eff["low"], "high": eff["high"],
            "wins": int(np.sum(b > a)), "losses": int(np.sum(b < a)), "note": eff["note"]}


def effects(groups: Sequence[Mapping[str, Any]], seeds: Sequence[int], n_boot: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    hid = dict(session="hidden")
    for start in ("anchor", "carry"):
        for src in ("sr", "tabular"):
            for g in GROUPS:
                # E1: what the barriers cost, per start group (paired by seed: the same seed in the open arena)
                out.append(_effect(f"barrier_cost_{start}", f"hidden success, {g} starts, L - open", f"open_{start}/{src}/{g}",
                                   _vec(groups, seeds, condition=f"open_{start}", source=src, group=g, **hid),
                                   f"L_{start}/{src}/{g}", _vec(groups, seeds, condition=f"L_{start}", source=src, group=g, **hid), n_boot))
                # E2: does the learned memory find the way around? (the source against no value steering, in L)
                out.append(_effect(f"memory_in_L_{start}", f"hidden success, {g} starts, {src} - none", f"L_{start}/none/{g}",
                                   _vec(groups, seeds, condition=f"L_{start}", source="none", group=g, **hid),
                                   f"L_{start}/{src}/{g}", _vec(groups, seeds, condition=f"L_{start}", source=src, group=g, **hid), n_boot))
    for start in ("anchor", "carry"):
        for g in GROUPS:  # the visible ceiling: the reflex alone, with and without the barriers
            out.append(_effect(f"visible_cost_{start}", f"visible success, {g} starts, L - open, sr", f"open_{start}/sr/{g}",
                               _vec(groups, seeds, condition=f"open_{start}", source="sr", group=g, session="visible"),
                               f"L_{start}/sr/{g}", _vec(groups, seeds, condition=f"L_{start}", source="sr", group=g, session="visible"), n_boot))
    return out


def cell_means(groups: Sequence[Mapping[str, Any]], seeds: Sequence[int], n_boot: int) -> List[Dict[str, Any]]:
    out = []
    for c in CONDITIONS:
        for src in rg.SOURCES:
            for ses in rg.SESSIONS:
                for g in GROUPS:
                    v = _vec(groups, seeds, condition=c, source=src, session=ses, group=g)
                    ci = bootstrap_ci(v, np.mean, n_boot=n_boot, seed=_stat_seed("g47_mean", c, src, ses, g))
                    out.append({"test": "mean_success", "statistic": f"{ses} success, {g} starts", "b": f"{c}/{src}/{ses}/{g}",
                                "n": ci.n, "mean_b": ci.estimate, "estimate": ci.estimate, "low": ci.low, "high": ci.high,
                                "note": ci.note})
    return out


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phase", choices=tuple(PHASES), default="pilot")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=N_BOOT)
    parser.add_argument("--quick", action="store_true", help="two spent seeds, 8 trials, 200 replicates; needs --out")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    spec = PHASES[args.phase]
    out = args.out or spec["out"]
    committed = [p["out"].resolve() for p in PHASES.values()]
    full = not args.quick and args.n_boot >= 1000
    if out.resolve() in committed and (not full or out.resolve() != spec["out"].resolve()):
        parser.error(f"a quick or mismatched run must not overwrite the committed tables in {out}: give --out")
    seeds = QUICK_SEEDS if args.quick else spec["seeds"]
    trials = rg.QUICK_TRIALS if args.quick else rg.TRIALS
    learning = trials // 2
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    started = time.perf_counter()
    trial_rows = run_conditions(seeds, trials, args.workers)
    groups: List[Dict[str, Any]] = []
    ticks_run = 0
    for c, rows in trial_rows.items():
        d = out / c
        per_seed = rg.per_seed_rows(rows, learning)
        write_csv(d / "gate_trials.csv", rg.TRIAL_COLUMNS, rows)
        write_csv(d / "gate_per_seed.csv", rg.PER_SEED_COLUMNS, per_seed)
        write_csv(d / "gate_curve.csv", rg.CURVE_COLUMNS, rg.curve_rows(rows, n_boot))
        write_csv(d / "gate_effects.csv", rg.EFFECT_COLUMNS, rg.effect_rows(per_seed, n_boot))
        groups += group_rows(c, rows, learning)
        ticks_run += sum(int(r["ticks"]) for r in rows)
    eff = cell_means(groups, seeds, n_boot) + effects(groups, seeds, n_boot)
    write_csv(out / "by_start_group.csv", GROUP_COLUMNS, groups)
    write_csv(out / "effects.csv", EFFECT_COLUMNS, eff)
    cfg = rg.gate_config("sr", "per_feature")
    manifest = build_manifest(cfg, protocol=f"g47_barrier_gate:{args.phase}", seeds=list(seeds), ticks_requested=ticks_run,
                              extra={"prereg": PREREG, "phase": args.phase, "conditions": CONDITIONS,
                                     "layouts": {k: [vars(b) for b in v] for k, v in rg.LAYOUTS.items()},
                                     "groups": {k: list(v) for k, v in GROUPS.items()}, "trials": trials, "n_boot": n_boot,
                                     "full_evaluation": full and args.phase == "confirmatory", "exploratory": args.phase == "pilot" or not full,
                                     "quick": args.quick, "dependencies": _dependency_versions(),
                                     "command": "python3 -m experiments.g47_barrier_gate " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    manifest["workers"] = args.workers
    finish_manifest(manifest, ticks_run=ticks_run, wall_seconds=time.perf_counter() - started)
    out.mkdir(parents=True, exist_ok=True)
    write_manifest(out / "manifest.json", manifest)
    print(f"{args.phase}: seeds {seeds[0]}-{seeds[-1]}, hidden success over trials {learning + 1}-{trials} (blocked / direct starts)")
    for c in CONDITIONS:
        line = []
        for src in rg.SOURCES:
            b = float(np.mean(_vec(groups, seeds, condition=c, source=src, session="hidden", group="blocked")))
            d_ = float(np.mean(_vec(groups, seeds, condition=c, source=src, session="hidden", group="direct")))
            line.append(f"{src} {b:.3f}/{d_:.3f}")
        vb = float(np.mean(_vec(groups, seeds, condition=c, source="sr", session="visible", group="blocked")))
        vd = float(np.mean(_vec(groups, seeds, condition=c, source="sr", session="visible", group="direct")))
        print(f"  {c:12s} {'  '.join(line)}   visible sr {vb:.3f}/{vd:.3f}")
    print(f"wrote {out} in {time.perf_counter() - started:.1f} s")
    return {"groups": groups, "effects": eff}


if __name__ == "__main__":
    main()
