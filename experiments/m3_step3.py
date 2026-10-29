"""M3 step 3's pilot: a learned action value over the place code, with replay, over step 2's battery (docs/prereg/m3_step3.md).

    python3 -m experiments.m3_step3 --phase pilot --workers 28          # spent seeds -> docs/data/m3/step3/pilot
    python3 -m experiments.m3_step3 --phase pilot --quick --out /tmp/s3  # the smoke test's run

The base is the research profile as G54 left it (history with the fixed schema on) with the step cap (``BASE``), not
``m3_part2.BASE`` (which pins history off for G51-G54's probes). Configurations on the research body: ``research``
(the profile); ``q_none``, ``q_uniform`` and ``q_reverse`` (the action value read as the memory term, replay by that
rule at the consumption pause); ``q_reverse_oracle`` (phi read at the body's true position: the positive control,
reported, never chosen). Scored by G53's statistics (``m3_part2.score``). The draft's selection rule, written before
the pilot: among the learner's configurations, the one passing the most bounds; ties to the simplest rule (none, then
reverse, then uniform); none is chosen that fails the track (its learned arm or either reflex arm). Exploratory on
spent seeds (gate and track 31-42, hidden food 1-8); the owner registers the confirmatory run.
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

from experiments import m3_part2 as p2
from experiments import rq4a_gate as rg
from experiments.linear_track_replay import _dependency_versions, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

SEEDS = {k: v for k, v in p2.PHASES["pilot"].items() if k != "out"}
BASE: Dict[str, Any] = {"place.reward_step_cap": True}  # the profile as G54 left it, with the cap
# The first pilot's read had no floor (amendment A1 added one, default 0.02): pinned so its tables regenerate as run.
AV: Dict[str, Any] = {"action_value.enabled": True, "value_memory.source": "action", "action_value.read_floor": 0.0}
# Amendment A1 (docs/prereg/m3_step3.md): the read floor, and history among the action value's features.
AV_FLOOR: Dict[str, Any] = {"action_value.enabled": True, "value_memory.source": "action", "action_value.read_floor": 0.02}
AV_HISTORY: Dict[str, Any] = {**AV_FLOOR, "action_value.history_features": True}
RULE_ORDER = ("none", "reverse", "uniform")  # the simplest first, for ties
PHASES: Dict[str, Dict[str, Any]] = {
    "pilot": {"out": Path("docs/data/m3/step3/pilot"), "configs": {
        "research": {},
        "q_none": {**AV, "replay.rule": "none"},
        "q_uniform": {**AV, "replay.rule": "uniform"},
        "q_reverse": {**AV, "replay.rule": "reverse"},
        "q_reverse_oracle": {**AV, "replay.rule": "reverse", "action_value.oracle_state": True},
    }, "learners": ("q_none", "q_uniform", "q_reverse")},
    "pilot2": {"out": Path("docs/data/m3/step3/pilot2"), "configs": {
        "research": {},
        "q_floor": {**AV_FLOOR, "replay.rule": "none"},
        "qh_none": {**AV_HISTORY, "replay.rule": "none"},
        "qh_uniform": {**AV_HISTORY, "replay.rule": "uniform"},
        "qh_reverse": {**AV_HISTORY, "replay.rule": "reverse"},
    }, "learners": ("q_floor", "qh_none", "qh_uniform", "qh_reverse")},
}
CONFIGS = PHASES["pilot"]["configs"]
LEARNER_CONFIGS = PHASES["pilot"]["learners"]
TRACK_BOUNDS = ("track_learned", "track_reflex_no_reward", "track_reflex_no_steer")


def select(scores: Sequence[Mapping[str, Any]], configs: Mapping[str, Mapping[str, Any]] = CONFIGS,
           learners: Sequence[str] = LEARNER_CONFIGS) -> Optional[str]:
    """The draft's rule: a learner configuration that passes the track; the most bounds; ties to the simplest rule."""
    eligible = [s for s in scores if s["config"] in learners and all(s["passes"][b] for b in TRACK_BOUNDS)]
    if not eligible:
        return None
    return sorted(eligible, key=lambda s: (-s["passed"], RULE_ORDER.index(configs[s["config"]]["replay.rule"])))[0]["config"]


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phase", choices=tuple(PHASES), default="pilot")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    spec = PHASES[args.phase]
    out = args.out or spec["out"]
    if args.quick and out.resolve() == spec["out"].resolve():
        parser.error("a quick run must not overwrite the committed tables: give --out")
    configs, learners = spec["configs"], spec["learners"]
    seeds = p2.QUICK if args.quick else SEEDS
    trials = rg.QUICK_TRIALS if args.quick else rg.TRIALS
    ticks = 300 if args.quick else p2.TICKS
    started = time.perf_counter()
    gate, track, food, open_field = p2.run_battery(configs, seeds, trials, ticks, args.workers, base=BASE)
    scores = [p2.score(c, gate, track, food) for c in configs]
    chosen = select(scores, configs, learners)
    write_csv(out / "gate.csv", ("config", "condition", "source", "session", "seed", "success"), gate)
    write_csv(out / "track.csv", ("config", "arm", "seed", "rewards", "traversals", "ticks_per_traversal", "traversals_late",
                                  "rest_share", "replay_events"), track)
    write_csv(out / "hidden_food.csv", ("config", "arm", "seed", "finds"), food)
    write_csv(out / "open_field.csv", ("config", "seed", "wall_zone_share", "coverage", "orbit_share", "stall_share"), open_field)
    track_summary = {c: {a: {k: statistics.mean(float(r[k]) for r in track if r["config"] == c and r["arm"] == a)
                             for k in ("rewards", "traversals", "ticks_per_traversal", "traversals_late", "rest_share", "replay_events")}
                         for a in p2.TRACK_ARMS} for c in configs}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps({"phase": args.phase, "seeds": {k: list(v) for k, v in seeds.items() if k != "out"},
                                                  "base": BASE, "configs": configs, "scores": scores, "chosen": chosen,
                                                  "track": track_summary, "quick": args.quick}, indent=1, sort_keys=True, default=str))
    manifest = build_manifest(p2.track_config(BASE), protocol=f"m3_step3:{args.phase}",
                              seeds=sorted(set(seeds["gate_seeds"]) | set(seeds["track_seeds"]) | set(seeds["food_seeds"])),
                              ticks_requested=0, extra={"base": BASE, "configs": configs, "phase": args.phase, "exploratory": True,
                                                        "quick": args.quick, "prereg": "docs/prereg/m3_step3.md (draft)",
                                                        "dependencies": _dependency_versions(),
                                                        "command": "python3 -m experiments.m3_step3 " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    finish_manifest(manifest, ticks_run=0, wall_seconds=time.perf_counter() - started)
    write_manifest(out / "manifest.json", manifest)
    print(f"{'config':17s} {'pass':>4s} elig  " + "  ".join(f"{b[:12]:>12s}" for b in p2.BOUNDS))
    for s in scores:
        cells = [f"{s['values'][b]:11.2f}{'+' if s['passes'][b] else '-'}" for b in p2.BOUNDS]
        print(f"{s['config']:17s} {s['passed']:4d} {'yes ' if s['eligible'] else 'no  '}  " + "  ".join(cells))
    print("track (mean per run): rewards, traversals, median ticks a traversal, traversals in the second half, rest share, replay events")
    for c, arms in track_summary.items():
        print(f"  {c:17s} " + "  |  ".join(f"{a}: {v['rewards']:5.1f} {v['traversals']:5.1f} {v['ticks_per_traversal']:6.1f} "
                                            f"{v['traversals_late']:5.1f} {v['rest_share']:.2f} {v['replay_events']:4.0f}" for a, v in arms.items()))
    print(f"chosen by the rule: {chosen}")
    print(f"wrote {out} in {time.perf_counter() - started:.1f} s")
    return {"scores": scores, "chosen": chosen, "track": track_summary}


if __name__ == "__main__":
    main()
