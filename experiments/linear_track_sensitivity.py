"""Sensitivity of the M2a ranking to the policy and learning parameters, one at a time.

    python3 -m experiments.linear_track_sensitivity --workers 4          # 11 variants x 4 conditions x 30 seeds
    python3 -m experiments.linear_track_sensitivity --quick --seeds 2 --variants base,lr_0.5 --out /tmp/sens

The fixed evaluation of docs/m2a_linear_track.md ran one parameter set, chosen before the
run and never tuned. This script asks whether its ranking (prioritised < reverse <
uniform ~ none in total steps) depends on that set: each variant changes **one** parameter
from the fixed values (``base``), all four conditions are re-run at the same 30 seeds, and
the paired comparisons of ``experiments.linear_track_replay.analyse`` are recomputed. It is
a sensitivity analysis reported beside the fixed evaluation, not a search: the fixed
evaluation's numbers are the ones reported as the result, and nothing here feeds back
into them.

Variants (``VARIANTS``): learning rate 0.1 and 0.5 (fixed 0.2); discount 0.9 and 0.98
(0.95); temperature 0.05 and 0.2 with the forward prior rescaled so the untrained turn
probability stays 0.2 (the fixed 0.1), so this axis is the sharpness of the softmax alone;
untrained turn probability 0.1 and 0.3 at the fixed temperature (the prior alone);
value gain 5 and 20 (10). Everything else, the track, laps, cap, budget and memory, is
the fixed evaluation's.

Outputs (``--out``, default docs/data/m2a/track): sensitivity_effects.csv (one row per
variant x comparison for total steps: the paired mean difference with its BCa interval,
the share of seeds improved, Cliff's delta with its interval) and sensitivity_summary.csv
(one row per variant: the parameter and value, the four conditions' mean total steps and
capped laps, the ordering of the conditions by mean, whether the two sequence rules beat
``none`` with intervals excluding zero and whether uniform's interval includes zero), and
sensitivity_manifest.json. A partial run refuses the committed directory: give ``--out``.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from experiments.linear_track_replay import (
    CONDITIONS,
    DEFAULT_N_BOOT,
    DEFAULT_SEEDS,
    RULE_NONE,
    RULE_PRIORITISED_TD,
    RULE_REVERSE_TRAJECTORY,
    RULE_UNIFORM,
    TrackConfig,
    _dependency_versions,
    analyse,
    run_all,
    write_csv,
)
from metrics.manifest import build_manifest, finish_manifest, write_manifest

DEFAULT_OUT = Path("docs/data/m2a/track")
BASE = TrackConfig()


def _prior_for(turn_probability: float, temperature: float) -> float:
    """The forward prior that gives an untrained agent ``turn_probability`` per step at ``temperature``."""
    return temperature * math.log((1.0 - turn_probability) / turn_probability)


VARIANTS: Dict[str, Tuple[str, float, TrackConfig]] = {
    "base": ("base", math.nan, BASE),
    "lr_0.1": ("learning_rate", 0.1, replace(BASE, learning_rate=0.1)),
    "lr_0.5": ("learning_rate", 0.5, replace(BASE, learning_rate=0.5)),
    "gamma_0.9": ("discount", 0.9, replace(BASE, discount=0.9)),
    "gamma_0.98": ("discount", 0.98, replace(BASE, discount=0.98)),
    "tau_0.05": ("temperature", 0.05, replace(BASE, temperature=0.05, forward_prior=_prior_for(0.2, 0.05))),
    "tau_0.2": ("temperature", 0.2, replace(BASE, temperature=0.2, forward_prior=_prior_for(0.2, 0.2))),
    "turn_0.1": ("untrained_turn_probability", 0.1, replace(BASE, forward_prior=_prior_for(0.1, BASE.temperature))),
    "turn_0.3": ("untrained_turn_probability", 0.3, replace(BASE, forward_prior=_prior_for(0.3, BASE.temperature))),
    "gain_5": ("value_gain", 5.0, replace(BASE, value_gain=5.0)),
    "gain_20": ("value_gain", 20.0, replace(BASE, value_gain=20.0)),
}

EFFECT_COLUMNS = ("variant", "parameter", "value", "a", "b", "n", "mean_a", "mean_b", "mean_diff", "low", "high",
                  "fraction_b_lt_a", "cliffs_delta", "cliffs_low", "cliffs_high", "cliffs_magnitude", "note")
SUMMARY_COLUMNS = ("variant", "parameter", "value", "laps", "lap_cap", "mean_total_steps_none", "mean_total_steps_uniform",
                   "mean_total_steps_reverse_trajectory", "mean_total_steps_prioritised_td", "capped_laps_total",
                   "ordering_by_mean_total_steps", "sequence_rules_beat_none", "prioritised_beats_reverse", "uniform_null")
OUTPUT_FILES = ("sensitivity_effects.csv", "sensitivity_summary.csv", "sensitivity_manifest.json")


def _excludes_zero(effect: Mapping[str, Any]) -> bool:
    return effect["high"] < 0.0 or effect["low"] > 0.0


def analyse_variant(name: str, parameter: str, value: float, cfg: TrackConfig, seeds: Sequence[int], n_boot: int,
                    workers: Optional[int]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    runs = run_all(CONDITIONS, seeds, cfg, workers)
    result = analyse(runs, n_boot)
    effects = [e for e in result["effects"] if e["metric"] == "total_steps"]
    rows = [{"variant": name, "parameter": parameter, "value": value, **{k: e[k] for k in EFFECT_COLUMNS if k in e}} for e in effects]
    means = {c: float(sum(s["total_steps"] for s in result["per_seed"][c].values()) / len(result["per_seed"][c])) for c in CONDITIONS}
    by_pair = {(e["a"], e["b"]): e for e in effects}
    ordering = " < ".join(sorted(CONDITIONS, key=lambda c: means[c]))  # fewest total steps first
    summary = {
        "variant": name, "parameter": parameter, "value": value, "laps": cfg.laps, "lap_cap": cfg.lap_cap,
        **{f"mean_total_steps_{c}": means[c] for c in CONDITIONS},
        "capped_laps_total": int(sum(s["laps_capped"] for c in CONDITIONS for s in result["per_seed"][c].values())),
        "ordering_by_mean_total_steps": ordering,
        "sequence_rules_beat_none": bool(
            by_pair[(RULE_NONE, RULE_REVERSE_TRAJECTORY)]["high"] < 0.0 and by_pair[(RULE_NONE, RULE_PRIORITISED_TD)]["high"] < 0.0
        ),
        "prioritised_beats_reverse": bool(by_pair[(RULE_REVERSE_TRAJECTORY, RULE_PRIORITISED_TD)]["high"] < 0.0),
        "uniform_null": not _excludes_zero(by_pair[(RULE_NONE, RULE_UNIFORM)]),
    }
    return rows, summary


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variants", default=",".join(VARIANTS), help="comma-separated subset of " + ",".join(VARIANTS))
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEEDS[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--quick", action="store_true", help="6 laps, cap 300, 200 replicates; needs --out")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    names = [v.strip() for v in args.variants.split(",") if v.strip()]
    for name in names:
        if name not in VARIANTS:
            parser.error(f"unknown variant {name!r}; choose from {', '.join(VARIANTS)}")
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    full = names == list(VARIANTS) and tuple(seeds) == DEFAULT_SEEDS and not args.quick and n_boot >= 1000
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a partial run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    started = time.perf_counter()
    effect_rows: List[Dict[str, Any]] = []
    summaries: List[Dict[str, Any]] = []
    for name in names:
        parameter, value, cfg = VARIANTS[name]
        if args.quick:
            cfg = replace(cfg, laps=min(cfg.laps, 6), lap_cap=min(cfg.lap_cap, 300))
        rows, summary = analyse_variant(name, parameter, value, cfg, seeds, n_boot, args.workers)
        effect_rows.extend(rows)
        summaries.append(summary)
        print(f"{name:12s} {summary['ordering_by_mean_total_steps']}  sequence rules beat none: {summary['sequence_rules_beat_none']}  "
              f"prioritised beats reverse: {summary['prioritised_beats_reverse']}  uniform null: {summary['uniform_null']}")
    manifest = build_manifest(
        BASE, protocol="linear_track_sensitivity", seeds=seeds, ticks_requested=0,
        extra={"variants": {n: {"parameter": VARIANTS[n][0], "value": VARIANTS[n][1], "config": VARIANTS[n][2].to_dict()} for n in names},
               "conditions": list(CONDITIONS), "n_boot": n_boot, "full_evaluation": full, "quick": args.quick,
               "dependencies": _dependency_versions(),
               "command": "python3 -m experiments.linear_track_sensitivity " + " ".join(list(argv) if argv is not None else sys.argv[1:])},
    )
    manifest["workers"] = args.workers if args.workers is not None else os.cpu_count()
    finish_manifest(manifest, ticks_run=0, wall_seconds=time.perf_counter() - started)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / OUTPUT_FILES[0], EFFECT_COLUMNS, effect_rows)
    write_csv(args.out / OUTPUT_FILES[1], SUMMARY_COLUMNS, summaries)
    write_manifest(args.out / OUTPUT_FILES[2], manifest)
    print(f"wrote {', '.join(OUTPUT_FILES)} to {args.out} in {manifest['timing']['wall_seconds']:.1f} s")
    return {"effects": effect_rows, "summaries": summaries}


if __name__ == "__main__":
    main()
