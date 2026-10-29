"""The fixed two-second taste schema, confirmatory on fresh seeds (docs/prereg/history_fast_schema.md; decisions G54).

    python3 -m experiments.history_fast_schema --phase confirmatory --workers 28
        -> docs/data/m3/history_motivation/fast_schema_confirmatory
    python3 -m experiments.history_fast_schema --phase confirmatory --quick --out /tmp/fs    # the smoke test's run

The research profile, two arms matched by seed, ``none`` (the profile as it stands) and ``fast`` (history on: taste and
visit channels, taste conditioning the SR's expected reward through the fixed schema (-1, 0, 0)), over M3 step 2's
battery (``experiments.m3_part2.run_battery``) on seeds none run before: gate and track 245-274, hidden food 47-76.
Bounds K1-K3 as preregistered, paired by seed (``analysis.stats.paired_effect``, BCa 95%); G53's eleven bounds for
both arms reported beside them.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from analysis.stats import paired_effect
from core.config import PRE_G54
from experiments import m3_hm_probe as hm
from experiments import m3_part2 as p2
from experiments import rq4a_gate as rg
from experiments.linear_track_replay import _dependency_versions, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

OUT = Path("docs/data/m3/history_motivation/fast_schema_confirmatory")
FAST = {**hm.HISTORY_ON, "history.schema": {"taste": (-1.0, 0.0, 0.0)}}
# ``none`` is the research profile as it stood at the registration (1c55df3), before G54 adopted the change: pinned.
CONFIGS: Dict[str, Dict[str, Any]] = {"none": dict(PRE_G54), "fast": FAST}
SEEDS = {"gate_seeds": tuple(range(245, 275)), "track_seeds": tuple(range(245, 275)), "food_seeds": tuple(range(47, 77))}
GATE_VALUES = {"open_hidden": ("open_anchor", "sr", "hidden"), "L_hidden": ("L_anchor", "sr", "hidden"),
               "open_visible": ("open_anchor", "sr", "visible"), "L_visible": ("L_anchor", "sr", "visible"),
               "cues_open": ("open_cues", "sr", "hidden"), "cues_L": ("L_cues", "sr", "hidden")}
GATE_LOSS = 0.03  # K2: the mean difference fast - none at least -0.03 on each value
TRACK_LOSS = 0.1  # K3: the interval's lower end above -0.1 x mean(none)


def per_seed(rows: Sequence[Mapping[str, Any]], key: str, **match: Any) -> Dict[int, float]:
    return {int(r["seed"]): float(r[key]) for r in rows if all(str(r[k]) == str(v) for k, v in match.items())}


def paired(a: Mapping[int, float], b: Mapping[int, float], seeds: Sequence[int], n_boot: int) -> Dict[str, Any]:
    return paired_effect([a[s] for s in seeds], [b[s] for s in seeds], n_boot=n_boot, seed=0)


def bounds(gate, track, food, seeds: Mapping[str, Sequence[int]], n_boot: int) -> Dict[str, Any]:
    """The preregistered bounds (docs/prereg/history_fast_schema.md), fast against none, paired by seed."""
    k1 = paired(per_seed(food, "finds", config="none", arm="steer"), per_seed(food, "finds", config="fast", arm="steer"),
                seeds["food_seeds"], n_boot)
    k2 = {name: paired(per_seed(gate, "success", config="none", condition=cond, source=src, session=ses),
                       per_seed(gate, "success", config="fast", condition=cond, source=src, session=ses), seeds["gate_seeds"], n_boot)
          for name, (cond, src, ses) in GATE_VALUES.items()}
    k3 = paired(per_seed(track, "traversals", config="none", arm="learned"), per_seed(track, "traversals", config="fast", arm="learned"),
                seeds["track_seeds"], n_boot)
    reported = {
        "food_no_steer": paired(per_seed(food, "finds", config="none", arm="no_steer"), per_seed(food, "finds", config="fast", arm="no_steer"),
                                seeds["food_seeds"], n_boot),
        "track_rewards": paired(per_seed(track, "rewards", config="none", arm="learned"), per_seed(track, "rewards", config="fast", arm="learned"),
                                seeds["track_seeds"], n_boot),
    }
    return {"K1_finds_steer": {**k1, "passes": bool(k1["low"] > 0.0)},
            "K2_gate_no_loss": {name: {**e, "passes": bool(e["mean_diff"] >= -GATE_LOSS)} for name, e in k2.items()},
            "K2_passes": all(e["mean_diff"] >= -GATE_LOSS for e in k2.values()),
            "K3_track_traversals": {**k3, "bound": -TRACK_LOSS * k3["mean_a"], "passes": bool(k3["low"] > -TRACK_LOSS * k3["mean_a"])},
            "reported": reported}


def _line(name: str, e: Mapping[str, Any]) -> str:
    return (f"  {name:22s} none {e['mean_a']:7.2f}  fast {e['mean_b']:7.2f}  diff {e['mean_diff']:+7.2f} "
            f"[{e['low']:+7.2f}, {e['high']:+7.2f}]  {'PASS' if e.get('passes') else ('FAIL' if 'passes' in e else '')}")


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phase", choices=("confirmatory",), default="confirmatory")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--n-boot", type=int, default=10_000)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    if args.quick and args.out.resolve() == OUT.resolve():
        parser.error("a quick run must not overwrite the committed tables: give --out")
    seeds = p2.QUICK if args.quick else SEEDS
    trials = rg.QUICK_TRIALS if args.quick else rg.TRIALS
    ticks = 300 if args.quick else p2.TICKS
    n_boot = 200 if args.quick else args.n_boot
    started = time.perf_counter()
    gate, track, food, open_field = p2.run_battery(CONFIGS, seeds, trials, ticks, args.workers)
    scores = [p2.score(c, gate, track, food) for c in CONFIGS]
    verdict = bounds(gate, track, food, seeds, n_boot)
    out = args.out
    write_csv(out / "gate.csv", ("config", "condition", "source", "session", "seed", "success"), gate)
    write_csv(out / "track.csv", ("config", "arm", "seed", "rewards", "traversals", "ticks_per_traversal", "traversals_late",
                                  "rest_share"), track)
    write_csv(out / "hidden_food.csv", ("config", "arm", "seed", "finds"), food)
    write_csv(out / "open_field.csv", ("config", "seed", "wall_zone_share", "coverage", "orbit_share", "stall_share"), open_field)
    track_summary = {c: {a: {k: statistics.mean(float(r[k]) for r in track if r["config"] == c and r["arm"] == a)
                             for k in ("rewards", "traversals", "ticks_per_traversal", "rest_share")} for a in p2.TRACK_ARMS} for c in CONFIGS}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps({"phase": args.phase, "configs": CONFIGS, "seeds": {k: list(v) for k, v in seeds.items()},
                                                  "bounds": verdict, "scores": scores, "track": track_summary, "quick": args.quick},
                                                 indent=1, sort_keys=True, default=str))
    manifest = build_manifest(p2.track_config({}), protocol=f"history_fast_schema:{args.phase}",
                              seeds=sorted(set(seeds["gate_seeds"]) | set(seeds["track_seeds"]) | set(seeds["food_seeds"])),
                              ticks_requested=0, extra={"configs": CONFIGS, "phase": args.phase, "quick": args.quick,
                                                        "prereg": "docs/prereg/history_fast_schema.md", "dependencies": _dependency_versions(),
                                                        "command": "python3 -m experiments.history_fast_schema " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    finish_manifest(manifest, ticks_run=0, wall_seconds=time.perf_counter() - started)
    write_manifest(out / "manifest.json", manifest)
    print(f"{'config':8s} {'pass':>4s} elig  " + "  ".join(f"{b[:12]:>12s}" for b in p2.BOUNDS))
    for s in scores:
        cells = [f"{s['values'][b]:11.2f}{'+' if s['passes'][b] else '-'}" for b in p2.BOUNDS]
        print(f"{s['config']:8s} {s['passed']:4d} {'yes ' if s['eligible'] else 'no  '}  " + "  ".join(cells))
    print("preregistered bounds (fast - none, paired by seed, BCa 95%):")
    print(_line("K1 finds, steering", verdict["K1_finds_steer"]))
    for name, e in verdict["K2_gate_no_loss"].items():
        print(_line(f"K2 {name}", e))
    print(_line("K3 track traversals", verdict["K3_track_traversals"]))
    for name, e in verdict["reported"].items():
        print(_line(f"reported {name}", e))
    print(f"K1 {'PASS' if verdict['K1_finds_steer']['passes'] else 'FAIL'}; K2 {'PASS' if verdict['K2_passes'] else 'FAIL'}; "
          f"K3 {'PASS' if verdict['K3_track_traversals']['passes'] else 'FAIL'}")
    print(f"wrote {out} in {time.perf_counter() - started:.1f} s")
    return {"bounds": verdict, "scores": scores}


if __name__ == "__main__":
    main()
