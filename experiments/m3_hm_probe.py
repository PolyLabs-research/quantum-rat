"""History and motivation over M3 step 2's battery: an exploratory probe (decisions G52).

    python3 -m experiments.m3_hm_probe --workers 28            # spent seeds -> docs/data/m3/history_motivation/probe
    python3 -m experiments.m3_hm_probe --quick --out /tmp/hm    # the smoke test's run

Two bodies, the research profile (``B0``) and the orienting response with G45's wall response (``B1``, Part 2's
``o1_n_S``: it runs a corridor and approaches a visible goal, but its reflex alone shuttled), each with history off or
on (``H``: taste and visit channels, the taste traces conditioning the SR's expected reward) and motivation off or on
(``M``: curiosity, satiety and a reward trace composing the drive to move). Every configuration runs Part 2's battery
(``experiments.m3_part2.run_battery``) on the pilot's spent seeds and is scored against the same eleven bounds; ``B0_H0M0``
and ``B1_H0M0`` are the pilot's ``o0_n_L`` and ``o1_n_S`` again. Exploratory: no selection, no registration.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from experiments import m3_part2 as p2
from experiments import rq4a_gate as rg
from experiments.linear_track_replay import _dependency_versions, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

OUT = Path("docs/data/m3/history_motivation/probe")
BODIES: Dict[str, Dict[str, Any]] = {"B0": {}, "B1": dict(p2.CONFIGS["o1_n_S"])}
# "history.schema": None keeps these what they were when the probe ran (the schema learned, G52), now that the research
# profile carries a fixed schema (G54); a configuration that wants one sets it on top (m3_g53_probes, history_fast_schema).
HISTORY_ON: Dict[str, Any] = {"history.enabled": True, "history.channels": ("taste", "visit"), "history.reward_context": ("taste",),
                              "history.schema": None}
VISIT_ONLY: Dict[str, Any] = {"history.enabled": True, "history.channels": ("visit",), "history.reward_context": (), "history.schema": None}
MOTIVATION_ON: Dict[str, Any] = {"motivation.enabled": True}


def configs() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for b, body in BODIES.items():
        for h in (0, 1):
            for m in (0, 1):
                ov = dict(body)
                if h:
                    ov.update(HISTORY_ON)
                elif m:
                    ov.update(VISIT_ONLY)  # motivation reads novelty from the visit channel; no reward context
                if m:
                    ov.update(MOTIVATION_ON)
                out[f"{b}_H{h}M{m}"] = ov
    return out


CONFIGS = configs()


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    if args.quick and args.out.resolve() == OUT.resolve():
        parser.error("a quick run must not overwrite the committed tables: give --out")
    seeds = p2.QUICK if args.quick else p2.PHASES["pilot"]
    trials = rg.QUICK_TRIALS if args.quick else rg.TRIALS
    ticks = 300 if args.quick else p2.TICKS
    started = time.perf_counter()
    gate, track, food, open_field = p2.run_battery(CONFIGS, seeds, trials, ticks, args.workers)
    scores = [p2.score(c, gate, track, food) for c in CONFIGS]
    out = args.out
    write_csv(out / "gate.csv", ("config", "condition", "source", "session", "seed", "success"), gate)
    write_csv(out / "track.csv", ("config", "arm", "seed", "rewards", "traversals", "ticks_per_traversal", "traversals_late",
                                  "rest_share"), track)
    write_csv(out / "hidden_food.csv", ("config", "arm", "seed", "finds"), food)
    write_csv(out / "open_field.csv", ("config", "seed", "wall_zone_share", "coverage", "orbit_share", "stall_share"), open_field)
    track_summary = {c: {a: {k: statistics.mean(float(r[k]) for r in track if r["config"] == c and r["arm"] == a)
                             for k in ("rewards", "traversals", "traversals_late", "rest_share")}
                         for a in p2.TRACK_ARMS} for c in CONFIGS}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps({"configs": {k: {kk: list(vv) if isinstance(vv, tuple) else vv for kk, vv in v.items()}
                                                              for k, v in CONFIGS.items()},
                                                  "scores": scores, "track": track_summary, "quick": args.quick},
                                                 indent=1, sort_keys=True, default=str))
    manifest = build_manifest(p2.track_config({}), protocol="m3_hm_probe", seeds=sorted(set(seeds["gate_seeds"]) | set(seeds["track_seeds"]) | set(seeds["food_seeds"])),
                              ticks_requested=0, extra={"configs": CONFIGS, "exploratory": True, "quick": args.quick,
                                                        "dependencies": _dependency_versions(),
                                                        "command": "python3 -m experiments.m3_hm_probe " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    finish_manifest(manifest, ticks_run=0, wall_seconds=time.perf_counter() - started)
    write_manifest(out / "manifest.json", manifest)
    print(f"{'config':9s} {'pass':>4s} elig  " + "  ".join(f"{b[:12]:>12s}" for b in p2.BOUNDS))
    for s in scores:
        cells = [f"{s['values'][b]:11.2f}{'+' if s['passes'][b] else '-'}" for b in p2.BOUNDS]
        print(f"{s['config']:9s} {s['passed']:4d} {'yes ' if s['eligible'] else 'no  '}  " + "  ".join(cells))
    print("track (mean per run): rewards, traversals, traversals in the second half, rest share")
    for c, arms in track_summary.items():
        print(f"  {c:9s} " + "  |  ".join(f"{a}: {v['rewards']:5.1f} {v['traversals']:5.1f} {v['traversals_late']:5.1f} {v['rest_share']:.2f}"
                                          for a, v in arms.items()))
    print(f"wrote {out} in {time.perf_counter() - started:.1f} s")
    return {"scores": scores, "track": track_summary}


if __name__ == "__main__":
    main()
