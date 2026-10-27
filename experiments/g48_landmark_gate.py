"""The gate with distal cues the agent learns to locate itself by (docs/prereg/g48_landmark_gate.md; decisions G48).

    python3 -m experiments.g48_landmark_gate --phase pilot --workers 28        # spent seeds 31-42 -> docs/data/g48/pilot
    python3 -m experiments.g48_landmark_gate --phase confirmatory --workers 28 # fresh seeds 185-214 -> docs/data/g48/confirmatory
    python3 -m experiments.g48_landmark_gate --quick --out /tmp/g48            # the smoke test's run

The gate's confirmatory settings on the research profile, trials started still, in the ``open`` and ``L`` arenas (G47),
with the estimate told the true start (``anchor``) or nothing (``carry``), and with the distal cues (``on``: the
agent sees the four cues of ``rq4a_gate.CUES`` and corrects its estimate from where it has learned they are) or
without them (``off``), the agent feeling its sideways displacement in every condition (``lateral_odometry``). Per start group as in G47 (``blocked``: the west and south starts; ``direct``:
the east and north), and per trial the mean distance between the estimate and the body.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from analysis.stats import bootstrap_ci, paired_effect
from experiments import rq4a_gate as rg
from experiments.linear_track_replay import _dependency_versions, _stat_seed, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

PREREG = "docs/prereg/g48_landmark_gate.md"
PHASES: Dict[str, Dict[str, Any]] = {
    "pilot": {"seeds": tuple(range(31, 43)), "out": Path("docs/data/g48/pilot")},  # spent seeds: exploratory
    "confirmatory": {"seeds": tuple(range(185, 215)), "out": Path("docs/data/g48/confirmatory")},
}
QUICK_SEEDS: Tuple[int, ...] = (31, 32)
N_BOOT = 10_000
# Every condition has the sideways odometry (sensors.lateral_odometry): the first pilot, without it, found the slide
# along a barrier that the agent could not feel biasing its learned cue map (docs/data/g48/pilot_without_lateral/,
# made at 296ae86; disclosed in the preregistration). The cues' effect is on against off on that same base.
CONDITIONS: Dict[str, Dict[str, Any]] = {
    f"{layout}_{start}_{cues}": {"layout": layout, "start_estimate": start, "landmarks": cues == "on", "lateral_odometry": True}
    for layout in ("open", "L") for start in ("anchor", "carry") for cues in ("off", "on")
}
# G47's agent (no sideways odometry, no cues) in the L arena, paired with the rest: the second pilot found G47's way
# round the wall leaning on the slide the agent could not feel, which carried its estimate through the wall.
CONDITIONS.update({f"L_{start}_off_nolateral": {"layout": "L", "start_estimate": start, "landmarks": False, "lateral_odometry": False}
                   for start in ("anchor", "carry")})
GROUPS: Dict[str, Tuple[int, ...]] = {
    "all": tuple(range(len(rg.STARTS))),
    "blocked": rg.blocked_starts("L"),
    "direct": tuple(i for i in range(len(rg.STARTS)) if i not in rg.blocked_starts("L")),
}
GROUP_COLUMNS = ("condition", "source", "session", "seed", "group", "trials", "success", "latency_median", "estimate_error",
                 "frame_spread")
EFFECT_COLUMNS = ("test", "statistic", "a", "b", "n", "mean_a", "mean_b", "estimate", "low", "high", "wins", "losses", "note")


def run_conditions(seeds: Sequence[int], trials: int, workers: Optional[int]) -> Dict[str, List[Dict[str, Any]]]:
    return {c: rg.run_all(seeds, trials, workers, rg.SOURCES, "per_feature", None, "discrete", False,
                          still_start=True, pre_g46=False, **opts)
            for c, opts in CONDITIONS.items()}


def group_rows(condition: str, trials: Sequence[Mapping[str, Any]], learning: int) -> List[Dict[str, Any]]:
    out = []
    for src in rg.SOURCES:
        for ses in rg.SESSIONS:
            for seed in sorted({int(r["seed"]) for r in trials}):
                for g, starts in GROUPS.items():
                    rows = [r for r in trials if r["source"] == src and r["session"] == ses and int(r["seed"]) == seed
                            and r["trial"] > learning and int(r["start"]) in starts]
                    hits = [r for r in rows if r["reached"]]
                    # frame_spread: how far the estimate's offset from the body on each arrival (estimate - body) lies
                    # from the mean of those offsets over the group's read arrivals: an estimate in a frame of its own,
                    # shifted as a whole but consistent from trial to trial, scores near 0 however large the shift.
                    if hits:
                        ox = float(np.mean([r["arrival_offset_x"] for r in hits]))
                        oy = float(np.mean([r["arrival_offset_y"] for r in hits]))
                        spread = float(np.mean([math.hypot(r["arrival_offset_x"] - ox, r["arrival_offset_y"] - oy) for r in hits]))
                    else:
                        spread = math.nan
                    out.append({"condition": condition, "source": src, "session": ses, "seed": seed, "group": g, "trials": len(rows),
                                "success": sum(r["reached"] for r in rows) / len(rows) if rows else math.nan,
                                "latency_median": float(np.median([r["latency"] for r in hits])) if hits else math.nan,
                                "estimate_error": float(np.mean([r["estimate_error_mean"] for r in rows])) if rows else math.nan,
                                "frame_spread": spread})
    return out


def _vec(rows: Sequence[Mapping[str, Any]], seeds: Sequence[int], stat: str = "success", **match: Any) -> np.ndarray:
    by = {int(r["seed"]): float(r[stat]) for r in rows if all(r[k] == v for k, v in match.items())}
    return np.array([by[s] for s in seeds], dtype=np.float64)


def _effect(test: str, statistic: str, a_name: str, a: np.ndarray, b_name: str, b: np.ndarray, n_boot: int) -> Dict[str, Any]:
    """b - a, paired by seed, over the seeds where both are defined (frame_spread is undefined without an arrival)."""
    keep = np.isfinite(a) & np.isfinite(b)
    a, b = a[keep], b[keep]
    if a.size < 2:
        return {"test": test, "statistic": statistic, "a": a_name, "b": b_name, "n": int(a.size), "estimate": math.nan,
                "note": "fewer than two seeds with both defined"}
    eff = paired_effect(a, b, n_boot=n_boot, seed=_stat_seed("g48", test, a_name, b_name))
    return {"test": test, "statistic": statistic, "a": a_name, "b": b_name, "n": int(a.size), "mean_a": eff["mean_a"],
            "mean_b": eff["mean_b"], "estimate": eff["mean_diff"], "low": eff["low"], "high": eff["high"],
            "wins": int(np.sum(b > a)), "losses": int(np.sum(b < a)), "note": eff["note"]}


def effects(groups: Sequence[Mapping[str, Any]], seeds: Sequence[int], n_boot: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for layout, group in (("open", "all"), ("L", "blocked"), ("L", "direct"), ("L", "all")):
        for start in ("anchor", "carry"):
            off, on = f"{layout}_{start}_off", f"{layout}_{start}_on"
            for src in ("sr", "tabular", "none"):
                # what the cues add: on - off, hidden success
                out.append(_effect(f"cues_{layout}_{start}", f"hidden success, {group} starts, cues on - off",
                                   f"{off}/{src}/{group}", _vec(groups, seeds, condition=off, source=src, session="hidden", group=group),
                                   f"{on}/{src}/{group}", _vec(groups, seeds, condition=on, source=src, session="hidden", group=group), n_boot))
            # the mechanism: the estimate's error over the read trials, and its frame's spread across them, on - off
            for stat in ("estimate_error", "frame_spread"):
                out.append(_effect(f"{stat}_{layout}_{start}", f"{stat} (units), {group} starts, sr hidden, cues on - off",
                                   f"{off}/sr/{group}", _vec(groups, seeds, stat, condition=off, source="sr", session="hidden", group=group),
                                   f"{on}/sr/{group}", _vec(groups, seeds, stat, condition=on, source="sr", session="hidden", group=group), n_boot))
        # with the cues, told nothing against told the start: what is left of the anchor's weight
        out.append(_effect(f"anchor_left_{layout}", f"hidden success, {group} starts, sr: carry with cues - anchor without",
                           f"{layout}_anchor_off/sr/{group}", _vec(groups, seeds, condition=f"{layout}_anchor_off", source="sr", session="hidden", group=group),
                           f"{layout}_carry_on/sr/{group}", _vec(groups, seeds, condition=f"{layout}_carry_on", source="sr", session="hidden", group=group), n_boot))
        # G47's agent against the same with the sideways odometry (L only): what the unfelt slide did
        if layout == "L":
            for start in ("anchor", "carry"):
                for stat in ("success", "estimate_error"):
                    out.append(_effect(f"lateral_{start}_{stat}", f"{stat}, {group} starts, sr hidden, sideways odometry on - off (no cues)",
                                       f"L_{start}_off_nolateral/sr/{group}",
                                       _vec(groups, seeds, stat, condition=f"L_{start}_off_nolateral", source="sr", session="hidden", group=group),
                                       f"L_{start}_off/sr/{group}",
                                       _vec(groups, seeds, stat, condition=f"L_{start}_off", source="sr", session="hidden", group=group), n_boot))
        # the learned memory against no steering, told nothing, with the cues
        out.append(_effect(f"memory_{layout}_carry_on", f"hidden success, {group} starts, sr - none, carry with cues",
                           f"{layout}_carry_on/none/{group}", _vec(groups, seeds, condition=f"{layout}_carry_on", source="none", session="hidden", group=group),
                           f"{layout}_carry_on/sr/{group}", _vec(groups, seeds, condition=f"{layout}_carry_on", source="sr", session="hidden", group=group), n_boot))
    return out


def cell_means(groups: Sequence[Mapping[str, Any]], seeds: Sequence[int], n_boot: int) -> List[Dict[str, Any]]:
    out = []
    for c in CONDITIONS:
        for src in rg.SOURCES:
            for ses in rg.SESSIONS:
                for g in GROUPS:
                    for stat in ("success", "estimate_error", "frame_spread"):
                        v = _vec(groups, seeds, stat, condition=c, source=src, session=ses, group=g)
                        v = v[np.isfinite(v)]
                        if v.size < 2:
                            continue
                        ci = bootstrap_ci(v, np.mean, n_boot=n_boot, seed=_stat_seed("g48_mean", c, src, ses, g, stat))
                        out.append({"test": f"mean_{stat}", "statistic": f"{ses} {stat}, {g} starts", "b": f"{c}/{src}/{ses}/{g}",
                                    "n": ci.n, "mean_b": ci.estimate, "estimate": ci.estimate, "low": ci.low, "high": ci.high, "note": ci.note})
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
        write_csv(d / "gate_trials.csv", rg.TRIAL_COLUMNS + ("estimate_error_mean", "estimate_offset_x", "estimate_offset_y",
                                                            "arrival_offset_x", "arrival_offset_y"), rows)
        write_csv(d / "gate_per_seed.csv", rg.PER_SEED_COLUMNS, per_seed)
        write_csv(d / "gate_effects.csv", rg.EFFECT_COLUMNS, rg.effect_rows(per_seed, n_boot))
        groups += group_rows(c, rows, learning)
        ticks_run += sum(int(r["ticks"]) for r in rows)
    eff = cell_means(groups, seeds, n_boot) + effects(groups, seeds, n_boot)
    write_csv(out / "by_start_group.csv", GROUP_COLUMNS, groups)
    write_csv(out / "effects.csv", EFFECT_COLUMNS, eff)
    cfg = rg.gate_config("sr", "per_feature", landmarks=True, lateral_odometry=True)
    manifest = build_manifest(cfg, protocol=f"g48_landmark_gate:{args.phase}", seeds=list(seeds), ticks_requested=ticks_run,
                              extra={"prereg": PREREG, "phase": args.phase, "conditions": CONDITIONS,
                                     "cues": [vars(c) for c in rg.CUES], "landmark_gain": rg.LANDMARK_GAIN,
                                     "layouts": {k: [vars(b) for b in v] for k, v in rg.LAYOUTS.items()},
                                     "groups": {k: list(v) for k, v in GROUPS.items()}, "trials": trials, "n_boot": n_boot,
                                     "full_evaluation": full and args.phase == "confirmatory", "exploratory": args.phase == "pilot" or not full,
                                     "quick": args.quick, "dependencies": _dependency_versions(),
                                     "command": "python3 -m experiments.g48_landmark_gate " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    manifest["workers"] = args.workers
    finish_manifest(manifest, ticks_run=ticks_run, wall_seconds=time.perf_counter() - started)
    out.mkdir(parents=True, exist_ok=True)
    write_manifest(out / "manifest.json", manifest)
    print(f"{args.phase}: seeds {seeds[0]}-{seeds[-1]}; hidden success over trials {learning + 1}-{trials}, all starts "
          f"(L: blocked / direct); mean estimate error (units), SR hidden")
    for c in CONDITIONS:
        parts = []
        for src in rg.SOURCES:
            if c.startswith("L_"):
                b = float(np.mean(_vec(groups, seeds, condition=c, source=src, session="hidden", group="blocked")))
                d_ = float(np.mean(_vec(groups, seeds, condition=c, source=src, session="hidden", group="direct")))
                parts.append(f"{src} {b:.3f}/{d_:.3f}")
            else:
                parts.append(f"{src} {float(np.mean(_vec(groups, seeds, condition=c, source=src, session='hidden', group='all'))):.3f}")
        err = float(np.mean(_vec(groups, seeds, "estimate_error", condition=c, source="sr", session="hidden", group="all")))
        spread = float(np.nanmean(_vec(groups, seeds, "frame_spread", condition=c, source="sr", session="hidden", group="all")))
        print(f"  {c:24s} {'  '.join(parts)}   error {err:.2f}  frame spread {spread:.2f}")
    print(f"wrote {out} in {time.perf_counter() - started:.1f} s")
    return {"groups": groups, "effects": eff}


if __name__ == "__main__":
    main()
