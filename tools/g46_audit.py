"""The audit of 2026-10-27: is the agent told anything it should not know? (docs/decisions.md G46)

Not one of ``tools.probes`` (those run single-process at a scale the characterisation test sets): a process pool over
experiment runs.

    python3 -m tools.g46_audit            # both parts, 28 workers, about a minute

Exploratory, on spent seeds, run before the retest was preregistered (docs/prereg/g46_retest.md discloses it). It
measures the two leaks the audit found and the weight of the gate's one unmeasured declared aid:

* **Hidden food, seeds 1-8, 3,000 ticks** (``experiments.console_ablation``'s arms: ``steer``, the scenario as the
  console runs it, and ``no_steer``, value gain 0). Research profile (U = 4, the scenario's setting): with the hidden
  sites sensed as before G46 (``sensors.unseen_block_rays`` True) and not sensed (the research default since G46).
  Legacy profile at sensor noise 0 (one deterministic run per arm, every seed a copy): as recorded (both leaks), with
  the rays fixed, with the shaping fixed, with both fixed.
* **The gate, seeds 31-42** (the confirmatory settings: per-feature rule, one rate, SR source, hidden session, the
  pre-G46 sensing and the carried-over first action, as the confirmatory ran): what the position estimate is told
  at each trial start (``anchor``, the true start; ``centre``; ``carry``, nothing), with the research instrument's
  heading oracle and wall reset and without them (``integrated``); the no-steering control; and the anchored gate
  with the sensing fixed. Success over trials 21-40.
"""

from __future__ import annotations

import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
from experiments import console_ablation as ca
from experiments import rq4a_gate as rg

LEAKS = {"sensors.unseen_block_rays": True, "reward.shape_hidden": True}
FIXED = {"sensors.unseen_block_rays": False, "reward.shape_hidden": False}
FOOD_CONDITIONS: Dict[str, Tuple[str, Dict[str, Any]]] = {
    "research, sites sensed (pre-G46)": ("research", LEAKS),
    "research, not sensed (G46)": ("research", FIXED),
    "legacy, as recorded (both leaks)": ("legacy", LEAKS),
    "legacy, rays fixed": ("legacy", {"sensors.unseen_block_rays": False, "reward.shape_hidden": True}),
    "legacy, shaping fixed": ("legacy", {"sensors.unseen_block_rays": True, "reward.shape_hidden": False}),
    "legacy, both fixed": ("legacy", FIXED),
}
FOOD_SEEDS = tuple(range(1, 9))
GATE_SEEDS = tuple(range(31, 43))
GATE_CONDITIONS: Dict[str, Dict[str, Any]] = {
    "anchor, oracle heading + wall reset (as registered)": {"start_estimate": "anchor"},
    "centre, oracle heading + wall reset": {"start_estimate": "centre"},
    "carry, oracle heading + wall reset": {"start_estimate": "carry"},
    "anchor, neither aid": {"start_estimate": "anchor", "estimate": "integrated"},
    "carry, neither aid (no aid at all)": {"start_estimate": "carry", "estimate": "integrated"},
    "anchor, sensing fixed (G46)": {"start_estimate": "anchor", "pre_g46": False},
}


def _food(job: Tuple[str, str, int]) -> Tuple[str, str, int, int]:
    name, arm, seed = job
    profile, overrides = FOOD_CONDITIONS[name]
    r = ca.run_one(("hidden_food", profile, arm, seed, 3000, dict(overrides), ca.ARMS))
    return name, arm, seed, r["metrics"]["finds"]


def _gate(job: Tuple[str, str, int]) -> Tuple[str, str, int, float]:
    name, source, seed = job
    options = {"pre_g46": True, **GATE_CONDITIONS[name]}
    rows = rg.run_session(source, "hidden", seed, reward_rule="per_feature", **options)
    test = [r for r in rows if r["trial"] > rg.LEARNING_TRIALS]
    return name, source, seed, sum(r["reached"] for r in test) / len(test)


def main(workers: int = 28) -> Dict[str, Any]:
    food_jobs = [(n, a, s) for n in FOOD_CONDITIONS for a in ca.ARMS for s in FOOD_SEEDS]
    gate_jobs = [(n, "sr", s) for n in GATE_CONDITIONS for s in GATE_SEEDS]
    gate_jobs += [("anchor, oracle heading + wall reset (as registered)", "none", s) for s in GATE_SEEDS]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        food = list(pool.map(_food, food_jobs, chunksize=1))
        gate = list(pool.map(_gate, gate_jobs, chunksize=1))
    out: Dict[str, Any] = {"food": {}, "gate": {}}
    print(f"hidden food, finds per 3,000 ticks, seeds {FOOD_SEEDS[0]}-{FOOD_SEEDS[-1]} (mean; steer - no_steer; seeds steer wins)")
    for name in FOOD_CONDITIONS:
        by = {a: [f for n, arm, _, f in food if n == name and arm == a] for a in ca.ARMS}
        diff = [x - y for x, y in zip(by["steer"], by["no_steer"])]
        out["food"][name] = by
        print(f"  {name:36s} steer {statistics.mean(by['steer']):6.2f}  no_steer {statistics.mean(by['no_steer']):6.2f}"
              f"  diff {statistics.mean(diff):+6.2f}  wins {sum(d > 0 for d in diff)}/{len(diff)}")
    print(f"the gate, SR hidden success over trials 21-40, seeds {GATE_SEEDS[0]}-{GATE_SEEDS[-1]}")
    for name in GATE_CONDITIONS:
        v = [x for n, src, _, x in gate if n == name and src == "sr"]
        out["gate"][name] = v
        print(f"  {name:52s} {statistics.mean(v):.3f}")
    control = [x for n, src, _, x in gate if src == "none"]
    out["gate"]["no steering (control), anchor"] = control
    print(f"  {'no steering (control), anchor':52s} {statistics.mean(control):.3f}")
    return out


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 28)
