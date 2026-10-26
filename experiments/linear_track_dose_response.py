"""Dose-response of the fixed-budget replay effect: 5, 10, 20 and 40 backups per pause (docs/prereg/rq1_track_tabular.md).

    python3 -m experiments.linear_track_dose_response --workers 4
    python3 -m experiments.linear_track_dose_response --quick --seeds 2 --doses 5,20 --out /tmp/dose

The fixed evaluation (docs/m2a_linear_track.md) made exactly 20 backups at every reward
pause. If the effect of a rule is the error-carrying backups it makes (G26, G27), it
should grow with the number of them: this runs the same 40-lap stable-reward protocol at
``DOSES`` backups per pause for all four conditions at the same seeds (``none`` is the
same run at every dose) and reports, per dose, the paired effect against ``none`` and,
per condition, the per-seed slope of total steps on log2(dose). Preregistered
predictions: reverse and prioritised slopes negative with intervals excluding zero and
effects growing with the dose; uniform's effect interval including zero at every dose.
The dose 20 reproduces the fixed evaluation to the digit.

Outputs (``--out``, default docs/data/m2a/rq1): dose_response_effects.csv,
dose_response_slopes.csv, dose_response_manifest.json. A partial run refuses the
committed directory: give ``--out``.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from analysis.stats import bootstrap_ci
from experiments.linear_track_replay import (
    CONDITIONS,
    DEFAULT_N_BOOT,
    DEFAULT_SEEDS,
    RULE_NONE,
    TrackConfig,
    _dependency_versions,
    _stat_seed,
    analyse,
    run_all,
    write_csv,
)
from metrics.manifest import build_manifest, finish_manifest, write_manifest

DEFAULT_OUT = Path("docs/data/m2a/rq1")
DOSES = (5, 10, 20, 40)
BASE = TrackConfig()
EFFECT_COLUMNS = ("dose", "a", "b", "n", "mean_a", "mean_b", "mean_diff", "low", "high", "fraction_b_lt_a",
                  "cliffs_delta", "cliffs_low", "cliffs_high", "cliffs_magnitude", "note")
SLOPE_COLUMNS = ("condition", "n", "doses", "mean_slope_per_log2_dose", "low", "high", "seeds_with_negative_slope",
                 "mean_total_steps_by_dose", "effect_grows_with_dose", "ci_method", "note")
OUTPUT_FILES = ("dose_response_effects.csv", "dose_response_slopes.csv", "dose_response_manifest.json")


def _slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    mx, my = math.fsum(xs) / n, math.fsum(ys) / n
    sxx = math.fsum((x - mx) ** 2 for x in xs)
    return math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else math.nan


def run_doses(doses: Sequence[int], seeds: Sequence[int], base: TrackConfig, workers: Optional[int], n_boot: int) -> Dict[str, Any]:
    per_dose: Dict[int, Dict[str, Any]] = {}
    for dose in doses:
        cfg = replace(base, backups_per_trigger=dose)
        runs = run_all(CONDITIONS, seeds, cfg, workers)
        per_dose[dose] = analyse(runs, n_boot)
    effects: List[Dict[str, Any]] = []
    for dose in doses:
        for e in per_dose[dose]["effects"]:
            if e["metric"] == "total_steps" and e["a"] == RULE_NONE:
                effects.append({"dose": dose, **{k: e[k] for k in EFFECT_COLUMNS if k in e}})
    slopes: List[Dict[str, Any]] = []
    log_doses = [math.log2(d) for d in doses]
    for c in CONDITIONS:
        if c == RULE_NONE:
            continue
        per_seed_slopes = []
        for seed in seeds:
            totals = [per_dose[d]["per_seed"][c][seed]["total_steps"] for d in doses]
            per_seed_slopes.append(_slope(log_doses, totals))
        arr = np.array(per_seed_slopes, dtype=np.float64)
        ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed("dose_slope", c))
        means = {d: float(np.mean([per_dose[d]["per_seed"][c][s]["total_steps"] for s in seeds])) for d in doses}
        none_means = {d: float(np.mean([per_dose[d]["per_seed"][RULE_NONE][s]["total_steps"] for s in seeds])) for d in doses}
        effect_by_dose = [means[d] - none_means[d] for d in doses]
        slopes.append({
            "condition": c, "n": int(arr.size), "doses": list(doses),
            "mean_slope_per_log2_dose": ci.estimate, "low": ci.low, "high": ci.high,
            "seeds_with_negative_slope": float(np.mean(arr < 0)),
            "mean_total_steps_by_dose": [round(means[d], 1) for d in doses],
            "effect_grows_with_dose": all(b < a for a, b in zip(effect_by_dose, effect_by_dose[1:])),
            "ci_method": ci.method, "note": ci.note,
        })
    return {"per_dose": per_dose, "effects": effects, "slopes": slopes}


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--doses", default=",".join(map(str, DOSES)))
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEEDS[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--quick", action="store_true", help="6 laps, 200 replicates; needs --out")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    doses = tuple(int(d) for d in args.doses.split(",") if d.strip())
    if len(doses) < 2 or any(d < 1 for d in doses) or len(set(doses)) != len(doses):
        parser.error("--doses needs at least two distinct positive counts")
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    base = BASE
    n_boot = args.n_boot
    if args.quick:
        base = replace(base, laps=6)  # the lap cap stays: at 300 steps hardly a lap of the 40-cell track completes
        n_boot = min(n_boot, 200)
    full = doses == DOSES and tuple(seeds) == DEFAULT_SEEDS and not args.quick and n_boot >= 1000
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a partial run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    started = time.perf_counter()
    result = run_doses(doses, seeds, base, args.workers, n_boot)
    manifest = build_manifest(
        base, protocol="linear_track_dose_response", seeds=seeds, ticks_requested=0,
        extra={"doses": list(doses), "conditions": list(CONDITIONS), "n_boot": n_boot, "full_evaluation": full,
               "quick": args.quick, "dependencies": _dependency_versions(),
               "prereg": "docs/prereg/rq1_track_tabular.md",
               "command": "python3 -m experiments.linear_track_dose_response " + " ".join(list(argv) if argv is not None else sys.argv[1:])},
    )
    manifest["workers"] = args.workers if args.workers is not None else os.cpu_count()
    finish_manifest(manifest, ticks_run=0, wall_seconds=time.perf_counter() - started)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / OUTPUT_FILES[0], EFFECT_COLUMNS, result["effects"])
    write_csv(args.out / OUTPUT_FILES[1], SLOPE_COLUMNS, result["slopes"])
    write_manifest(args.out / OUTPUT_FILES[2], manifest)
    for row in result["slopes"]:
        print(f"{row['condition']:20s} slope per log2 dose {row['mean_slope_per_log2_dose']:+8.1f} [{row['low']:+8.1f}, {row['high']:+8.1f}] "
              f"steps; negative on {row['seeds_with_negative_slope']:.2f} of seeds; totals by dose {row['mean_total_steps_by_dose']}; "
              f"effect grows with dose: {row['effect_grows_with_dose']}")
    print(f"wrote {', '.join(OUTPUT_FILES)} to {args.out} in {manifest['timing']['wall_seconds']:.1f} s")
    return result


if __name__ == "__main__":
    main()
