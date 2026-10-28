"""G53's two probes over M3 step 2's battery: history with a fixed schema; motivation with hunger as a reason (exploratory).

    python3 -m experiments.m3_g53_probes --phase schema --workers 28      # -> docs/data/m3/history_motivation/fixed_schema
    python3 -m experiments.m3_g53_probes --phase forage --workers 28      # -> docs/data/m3/history_motivation/forage
    python3 -m experiments.m3_g53_probes --phase schema --quick --out /tmp/g53   # the smoke test's run

The owner's decisions after G52's probe (docs/decisions.md G52 D3, D4). Both phases run Part 2's battery
(``experiments.m3_part2.run_battery``) on the pilot's spent seeds for the two bodies of G52's probe, ``B0`` the research
profile and ``B1`` the orienting response with G45's wall response, and score by G53's statistics (traversals per run;
the gate's control as a margin).

``schema``: history on (taste and visit; taste conditioning the SR's expected reward) with the schema *fixed*, so the
representation is tested apart from its learning and R keeps G36's rule. Three schemas over the taste traces at 2 s,
20 s and 200 s, each set from a stated reason before the run: ``learned`` (−0.29, −0.25, +0.66), what G52's learning
found on the track (a place eaten at within a lap holds less; one eaten at within a regrowth holds more); ``fast``
(−1, 0, 0), the place is empty while the agent is still at it, and nothing beyond; ``lap`` (0, −1, 0), a place eaten
at within about a traversal (20 s) is empty, the reward's full size, and longer ago it is as remembered. Rewards are
0 or 1, so −1 cancels a place's reward while that trace is 1.

``forage``: motivation on (the visit channel for novelty; no reward context) with G53's composition — hunger a reason
on its own, the reward trace setting vigour (floor 0.5) — against G52's, which rested a hungry agent that had found
nothing lately. Exploratory: no selection, no registration.
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

from experiments import m3_hm_probe as hm
from experiments import m3_part2 as p2
from experiments import rq4a_gate as rg
from experiments.linear_track_replay import _dependency_versions, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

OUT = {"schema": Path("docs/data/m3/history_motivation/fixed_schema"), "forage": Path("docs/data/m3/history_motivation/forage")}
SCHEMAS: Dict[str, tuple] = {"learned": (-0.29, -0.25, 0.66), "fast": (-1.0, 0.0, 0.0), "lap": (0.0, -1.0, 0.0)}


def configs(phase: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for b, body in hm.BODIES.items():
        if phase == "schema":
            for name, u in SCHEMAS.items():
                out[f"{b}_S{name}"] = {**body, **hm.HISTORY_ON, "history.schema": {"taste": u}}
        else:
            out[f"{b}_M1"] = {**body, **hm.VISIT_ONLY, **hm.MOTIVATION_ON}
    return out


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phase", choices=tuple(OUT), required=True)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    out = args.out or OUT[args.phase]
    if args.quick and out.resolve() == OUT[args.phase].resolve():
        parser.error("a quick run must not overwrite the committed tables: give --out")
    cfgs = configs(args.phase)
    seeds = p2.QUICK if args.quick else p2.PHASES["pilot"]
    trials = rg.QUICK_TRIALS if args.quick else rg.TRIALS
    ticks = 300 if args.quick else p2.TICKS
    started = time.perf_counter()
    gate, track, food, open_field = p2.run_battery(cfgs, seeds, trials, ticks, args.workers)
    scores = [p2.score(c, gate, track, food) for c in cfgs]
    write_csv(out / "gate.csv", ("config", "condition", "source", "session", "seed", "success"), gate)
    write_csv(out / "track.csv", ("config", "arm", "seed", "rewards", "traversals", "ticks_per_traversal", "traversals_late",
                                  "rest_share"), track)
    write_csv(out / "hidden_food.csv", ("config", "arm", "seed", "finds"), food)
    write_csv(out / "open_field.csv", ("config", "seed", "wall_zone_share", "coverage", "orbit_share", "stall_share"), open_field)
    track_summary = {c: {a: {k: statistics.mean(float(r[k]) for r in track if r["config"] == c and r["arm"] == a)
                             for k in ("rewards", "traversals", "ticks_per_traversal", "traversals_late", "rest_share")}
                         for a in p2.TRACK_ARMS} for c in cfgs}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps({"phase": args.phase, "configs": cfgs, "scores": scores, "track": track_summary,
                                                  "quick": args.quick}, indent=1, sort_keys=True, default=str))
    manifest = build_manifest(p2.track_config({}), protocol=f"m3_g53_probes:{args.phase}",
                              seeds=sorted(set(seeds["gate_seeds"]) | set(seeds["track_seeds"]) | set(seeds["food_seeds"])),
                              ticks_requested=0, extra={"configs": cfgs, "phase": args.phase, "exploratory": True, "quick": args.quick,
                                                        "dependencies": _dependency_versions(),
                                                        "command": "python3 -m experiments.m3_g53_probes " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    finish_manifest(manifest, ticks_run=0, wall_seconds=time.perf_counter() - started)
    write_manifest(out / "manifest.json", manifest)
    print(f"{'config':12s} {'pass':>4s} elig  " + "  ".join(f"{b[:12]:>12s}" for b in p2.BOUNDS))
    for s in scores:
        cells = [f"{s['values'][b]:11.2f}{'+' if s['passes'][b] else '-'}" for b in p2.BOUNDS]
        print(f"{s['config']:12s} {s['passed']:4d} {'yes ' if s['eligible'] else 'no  '}  " + "  ".join(cells))
    print("track (mean per run): rewards, traversals, median ticks a traversal, traversals in the second half, rest share")
    for c, arms in track_summary.items():
        print(f"  {c:12s} " + "  |  ".join(f"{a}: {v['rewards']:5.1f} {v['traversals']:5.1f} {v['ticks_per_traversal']:6.1f} "
                                            f"{v['traversals_late']:5.1f} {v['rest_share']:.2f}" for a, v in arms.items()))
    print(f"wrote {out} in {time.perf_counter() - started:.1f} s")
    return {"scores": scores, "track": track_summary}


if __name__ == "__main__":
    main()
