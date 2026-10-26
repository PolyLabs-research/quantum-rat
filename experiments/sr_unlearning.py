"""The SR's reward unlearning rate on hidden food, research profile: a preregistered A/B (G41).

Preregistration: ``docs/prereg/sr_unlearning_rate.md``. The circling measurement (G40) found that on the
research profile the SR value steering costs a third of the hidden-food finds through orbits that
start just after a meal, beside the emptied site: the value at the place outlasts the reward. The
per-feature reward rule moves each active cell's weight toward the reward it sees at one rate; this
experiment gives the rule a separate **unlearning rate** ``U`` for ticks that see no reward
(``PlaceConfig.reward_unlearning_rate``) and asks whether a higher ``U`` removes the persistence and
restores the finds.

Arms, all on ``hidden_food`` on the research profile, matched by seed (``experiments.console_ablation``
runs and summarises them; every run logs its decisions and is cut into orbits by ``analysis.orbits``):

- ``no_steer``: ``basal_ganglia.value_gain = 0`` (memory not read): the floor the steering has to beat.
- ``u0.5``: the rule as it stands (``U`` = the learning rate 0.5): the baseline.
- ``u<U>``: ``place.reward_unlearning_rate = U``; the pilot runs ``U`` in {1, 2, 4} on seeds 1–8, the
  confirmatory run the one ``U`` the pilot's rule picks, on seeds 9–16.

Effects: each ``u<U>`` arm against ``u0.5`` and against ``no_steer``, paired by seed with BCa intervals.

    python -m experiments.sr_unlearning --phase pilot --out docs/data/console_ablation/sr_unlearning_pilot
    python -m experiments.sr_unlearning --phase confirmatory --unlearning 2 \\
        --prereg docs/prereg/sr_unlearning_rate.md --out docs/data/console_ablation/sr_unlearning_confirmatory
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.engine import Engine  # noqa: F401,I001  (core before numpy: docs/determinism.md rule 2)

import numpy as np

from analysis.stats import PseudoReplicationError, pseudo_replication_guard
from experiments import console_ablation as ca
from metrics.manifest import build_manifest, finish_manifest, write_manifest

SCENARIO = "hidden_food"
PROFILE = "research"
BASELINE = "u0.5"
BASELINE_RATE = 0.5
PILOT_RATES = (1.0, 2.0, 4.0)
PILOT_SEEDS = tuple(range(1, 9))
CONFIRMATORY_SEEDS = tuple(range(9, 17))
TICKS = 3000
QUICK_SEEDS = (1, 2)
QUICK_TICKS = 150
OUTPUT_FILES = ("unlearning_per_seed.csv", "unlearning_bouts.csv", "unlearning_summary.json", "manifest.json")


def arm_name(rate: float) -> str:
    return f"u{rate:g}"


def arms_for(rates: Sequence[float]) -> Dict[str, Dict[str, Any]]:
    arms: Dict[str, Dict[str, Any]] = {
        "no_steer": {"basal_ganglia.value_gain": 0.0},
        BASELINE: {"place.reward_unlearning_rate": BASELINE_RATE},
    }
    for rate in rates:
        arms[arm_name(rate)] = {"place.reward_unlearning_rate": float(rate)}
    return arms


def choose_rate(means: Mapping[str, Mapping[str, Optional[float]]], rates: Sequence[float]) -> float:
    """The pilot's rule (preregistered): the ``U`` arm with the highest mean finds; a tie goes to the smaller ``U``."""
    best = None
    for rate in sorted(rates):
        finds = means[arm_name(rate)]["finds"]
        if best is None or (finds is not None and finds > best[1]):
            best = (rate, finds if finds is not None else float("-inf"))
    assert best is not None
    return best[0]


def analyse(results: Sequence[Mapping[str, Any]], seeds: Sequence[int], rates: Sequence[float], n_boot: int) -> Dict[str, Any]:
    arms = list(arms_for(rates))
    means = ca.arm_means(results, arms)
    eff: Dict[str, Any] = {}
    for rate in rates:
        name = arm_name(rate)
        eff[name] = {
            "vs_baseline": ca.effects(results, seeds, n_boot, a_arm=BASELINE, b_arm=name),
            "vs_no_steer": ca.effects(results, seeds, n_boot, a_arm="no_steer", b_arm=name),
        }
    eff[BASELINE] = {"vs_no_steer": ca.effects(results, seeds, n_boot, a_arm="no_steer", b_arm=BASELINE)}
    return {"per_arm_means": means, "effects": ca._jsonable(eff)}


def bounds(analysis: Mapping[str, Any], rate: float, seeds: Sequence[int]) -> Dict[str, Any]:
    """The preregistered bounds (docs/prereg/sr_unlearning_rate.md) for the arm ``u<rate>``."""
    name = arm_name(rate)
    means = analysis["per_arm_means"]
    k1 = analysis["effects"][name]["vs_baseline"]["finds"]
    k2_b, k2_u = means[BASELINE]["orbit_ticks_memory"], means[name]["orbit_ticks_memory"]
    k2_diff = analysis["effects"][name]["vs_baseline"]["orbit_ticks_memory"]
    k3 = analysis["effects"][name]["vs_no_steer"]["finds"]
    floor = means["no_steer"]["finds"]
    return {
        "arm": name,
        "n_seeds": len(seeds),
        "K1_finds_vs_baseline": {"mean_diff": k1.get("mean_diff"), "low": k1.get("low"), "high": k1.get("high"),
                                 "passes": bool("low" in k1 and k1["low"] > 0.0)},
        "K2_memory_orbit_ticks": {"baseline": k2_b, "arm": k2_u, "ratio": (k2_u / k2_b) if k2_b else None,
                                  "mean_diff": k2_diff.get("mean_diff"), "low": k2_diff.get("low"), "high": k2_diff.get("high"),
                                  "passes": bool(k2_b and k2_u is not None and k2_u / k2_b <= 0.5)},
        "K3_finds_vs_no_steer": {"mean_diff": k3.get("mean_diff"), "low": k3.get("low"), "high": k3.get("high"),
                                 "floor_mean": floor, "bound": -0.1 * floor if floor is not None else None,
                                 "passes": bool("low" in k3 and floor is not None and k3["low"] > -0.1 * floor)},
    }


def format_report(phase: str, seeds: Sequence[int], ticks: int, rates: Sequence[float], analysis: Mapping[str, Any],
                  chosen: Optional[float], verdict: Optional[Mapping[str, Any]]) -> str:
    means = analysis["per_arm_means"]
    arms = list(arms_for(rates))
    lines = [f"{phase}: hidden_food on research, seeds {seeds[0]}-{seeds[-1]} ({len(seeds)}), {ticks} ticks; arms {', '.join(arms)}",
             f"{'metric':<24}" + "".join(f"{a:>10}" for a in arms)]
    for metric in ("finds", "unique_sites", "distance_per_find", "wall_fraction", "orbits", "orbit_fraction",
                   "orbit_ticks_memory", "orbit_ticks_productive", "orbit_ticks_wall", "mean_memory_influence", "reward"):
        row = f"{metric:<24}"
        for a in arms:
            v = means[a][metric]
            row += f"{'—' if v is None else f'{v:.2f}':>10}"
        lines.append(row)
    lines.append("paired effects (b - a, BCa 95%):")
    for rate in rates:
        name = arm_name(rate)
        for against, key in (("u0.5", "vs_baseline"), ("no_steer", "vs_no_steer")):
            e = analysis["effects"][name][key]["finds"]
            m = analysis["effects"][name][key]["orbit_ticks_memory"]
            if "mean_diff" in e:
                lines.append(f"  {name} vs {against}: finds {e['mean_diff']:+.2f} [{e['low']:+.2f}, {e['high']:+.2f}]"
                             f"{'*' if e['low'] > 0 or e['high'] < 0 else ' '}  memory-orbit ticks {m['mean_diff']:+.0f} [{m['low']:+.0f}, {m['high']:+.0f}]")
    if chosen is not None:
        lines.append(f"pilot rule picks U = {chosen:g} (highest mean finds; ties to the smaller U)")
    if verdict is not None:
        for k, v in verdict.items():
            if isinstance(v, dict) and "passes" in v:
                lines.append(f"  {k}: {'PASS' if v['passes'] else 'FAIL'}  {json.dumps({kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != 'passes'})}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", choices=("pilot", "confirmatory"), required=True)
    parser.add_argument("--unlearning", type=float, default=None, help="the confirmatory arm's U (the pilot's choice)")
    parser.add_argument("--rates", default=None, help="pilot rates, e.g. 1,2,4 (default %s)" % ",".join(f"{r:g}" for r in PILOT_RATES))
    parser.add_argument("--seeds", default=None, help="override the phase's seeds (pilot 1-8, confirmatory 9-16)")
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=10_000)
    parser.add_argument("--prereg", type=str, default=None, help="the preregistration this run is tied to (recorded in the manifest)")
    parser.add_argument("--keep-records", action="store_true")
    parser.add_argument("--quick", action="store_true", help=f"{len(QUICK_SEEDS)} seeds x {QUICK_TICKS} ticks, a smoke run")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.phase == "pilot":
        rates = tuple(float(r) for r in args.rates.split(",")) if args.rates else PILOT_RATES
        default_seeds = PILOT_SEEDS
    else:
        if args.unlearning is None:
            raise SystemExit("--phase confirmatory needs --unlearning U (the pilot's choice)")
        rates = (float(args.unlearning),)
        default_seeds = CONFIRMATORY_SEEDS
    seeds = ca.parse_seeds(args.seeds) if args.seeds else (QUICK_SEEDS if args.quick else default_seeds)
    ticks = args.ticks or (QUICK_TICKS if args.quick else TICKS)
    arms = arms_for(rates)
    started = time.perf_counter()
    results = ca.run_all(SCENARIO, PROFILE, seeds, ticks, {}, args.workers, arms=arms)
    digests = {r["seed"]: r["digest"] for r in results if r["arm"] == BASELINE}
    try:
        guard: Any = pseudo_replication_guard([digests[s] for s in seeds])
    except PseudoReplicationError as exc:
        raise SystemExit(str(exc)) from None
    analysis = analyse(results, seeds, rates, args.n_boot)
    chosen = choose_rate(analysis["per_arm_means"], rates) if args.phase == "pilot" else rates[0]
    verdict = bounds(analysis, chosen, seeds)
    wall = time.perf_counter() - started
    out = args.out
    ca.write_tables(out, SCENARIO, results, args.keep_records, prefix="unlearning")
    summary = {
        "phase": args.phase, "scenario": SCENARIO, "profile": PROFILE, "seeds": list(seeds), "ticks": ticks,
        "rates": list(rates), "arms": arms, "guard": guard, "prereg": args.prereg,
        "chosen_rate": chosen, "bounds": ca._jsonable(verdict), **analysis,
        "status": {f"{r['arm']}_s{r['seed']}": r["status"] for r in results}, "wall_seconds": round(wall, 1),
    }
    (out / "unlearning_summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    _, cfg = ca.arm_config(SCENARIO, PROFILE, arm_name(chosen), {}, arms)
    manifest = build_manifest(cfg, protocol=f"sr_unlearning:{args.phase}", seeds=list(seeds), ticks_requested=ticks,
                              extra={"profile_requested": PROFILE, "arms": arms, "prereg": args.prereg, "phase": args.phase,
                                     "experiment": "experiments.sr_unlearning"})
    finish_manifest(manifest, ticks_run=ticks * len(seeds) * len(arms), wall_seconds=wall)
    write_manifest(out / "manifest.json", manifest)
    print(format_report(args.phase, seeds, ticks, rates, analysis, chosen if args.phase == "pilot" else None,
                        verdict if args.phase == "confirmatory" else None))
    print(f"wrote {out} ({wall:.0f} s)")
    return summary


if __name__ == "__main__":
    main()
