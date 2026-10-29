"""Three checks behind G52's reading of the history/motivation probe (disclosed exploration; spent seeds; not a result).

    .venv/bin/python -m tools.m3_hm_probes.diagnostics --workers 24

1. The capped per-feature step outside the track: hidden food, one seed, cap off against on (the probe's hidden-food,
   gate and open-field tables were byte-identical to G51's uncapped ones, so the cap should never bind there), and the
   largest share one place cell carries of phi in the open arena against the track.
2. Motivation's no-steering gate control (0.32 in the open arena with cues against 0.03): the same control with the
   curiosity reason removed (``motivation.reasons = ("forage",)``), so only hunger x reward could drive it. If the
   control falls back, the rise is the novelty drive: the agent rests where it is familiar and moves where it is not.
3. What the taste schema learned on the track (history on, the learned arm, one seed): the weights u per timescale.
"""

from __future__ import annotations

import argparse
import csv
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from brain.systems.successor_features import normalised
from core.config import EngineConfig
from core.engine import Engine
from core.world import WorldObject
from experiments import console_ablation as ca
from experiments import m3_hm_probe as hm
from experiments import m3_part2 as p2
from experiments import rq4a_gate as rg

OUT = Path("tools/m3_hm_probes/diagnostics_out")
SEEDS = tuple(range(31, 43))


def max_phi_share(cfg: EngineConfig, seed: int, ticks: int) -> float:
    eng = Engine(seed=seed, config=cfg)
    eng.run(1, reset=True)
    best = 0.0
    for _ in range(ticks):
        eng.run(1)
        best = max(best, float(np.max(normalised(eng.place_rates))))
    return best


def _control_job(job):
    cond, seed, reasons = job
    ov = {**p2.BASE, **hm.VISIT_ONLY, **hm.MOTIVATION_ON, "motivation.reasons": reasons}
    rows = rg.run_session("none", "hidden", seed, trials=rg.TRIALS, reward_rule="per_feature", still_start=True,
                          overrides=ov, **p2.GATE[cond])
    test = [r for r in rows if r["trial"] > rg.TRIALS // 2]
    return {"condition": cond, "seed": seed, "reasons": "+".join(reasons), "success": sum(r["reached"] for r in test) / len(test)}


def track_schema(seed: int, ticks: int):
    cfg = p2.track_config({**p2.BASE, **hm.HISTORY_ON})
    eng = Engine(seed=seed, config=cfg)
    sites = [WorldObject(x, 0.0, 0.5, "collected") for x in p2.TRACK_ENDS]
    for s in sites:
        eng.world.add_object(s)
    active = 1
    sites[active].kind = "hidden"
    eng.run(1, reset=True)
    rewards = 0
    for _ in range(ticks):
        eng.run(1)
        x, y = eng.agent.pos
        if math.hypot(x - sites[active].x, y - sites[active].y) <= sites[active].radius:
            sites[active].kind = "collected"
            active = 1 - active
            sites[active].kind = "hidden"
            rewards += 1
    return rewards, eng.history.summary()["schema"], float(np.min(eng.sr_weights)), float(np.max(eng.sr_weights))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lines = []

    finds = {}
    for cap in (False, True):
        r = ca.run_one(("hidden_food", "research", "steer", 1, p2.TICKS, {"place.reward_step_cap": cap}, ca.ARMS))
        finds[cap] = r["metrics"]["finds"]
    lines.append(f"1. hidden food seed 1, steer: finds cap off {finds[False]}, cap on {finds[True]}")
    open_share = max_phi_share(EngineConfig.research(), 1, 2000)
    track_share = max_phi_share(p2.track_config({}), 31, 2000)
    lines.append(f"   largest share of phi in one cell: open arena {open_share:.2f} (x4 = {4 * open_share:.2f}), "
                 f"track {track_share:.2f} (x4 = {4 * track_share:.2f}); the cap binds above 0.25")

    jobs = [(cond, s, reasons) for cond in ("open_anchor", "open_cues") for s in SEEDS
            for reasons in (("explore", "forage"), ("forage",))]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(_control_job, jobs, chunksize=1))
    with open(OUT / "novelty_control.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=("condition", "seed", "reasons", "success"))
        w.writeheader()
        w.writerows(rows)
    for cond in ("open_anchor", "open_cues"):
        for reasons in ("explore+forage", "forage"):
            vals = [r["success"] for r in rows if r["condition"] == cond and r["reasons"] == reasons]
            lines.append(f"2. no-steering control, hidden, {cond}, reasons {reasons}: {np.mean(vals):.3f} (seeds {SEEDS[0]}-{SEEDS[-1]})")

    rewards, schema, lo, hi = track_schema(31, p2.TICKS)
    lines.append(f"3. track seed 31, history on, learned arm: rewards {rewards}; taste schema u per timescale "
                 f"(10, 100, 1000 ticks) = {schema['taste']}; reward weights in [{lo:.2f}, {hi:.2f}]")

    text = "\n".join(lines) + "\n"
    (OUT / "summary.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
