"""Where the action-value agent spends the track run (disclosed check behind G55's reading; spent seeds; not a result).

    .venv/bin/python -m tools.m3_step3_probes.emptied_end

The step 3 pilots' track, seed 31, 3,000 ticks: for the research profile, the first pilot's learner with replay none
and reverse, and pilot 2's (the floor alone; history among the features with replay none and reverse), the share of
ticks spent within 1.5 units of the end the agent has just eaten at (the empty one) and of the other end (the full
one), the number of meals, the share of ticks on which the wall gate mutes the memory term (a wall close ahead;
``wall_gate`` below 1), the share of movement ticks that are turns, the mean |advantage| the steering read, and the
advantages read at the empty end eight ticks after the first meals.
"""

from __future__ import annotations

import math
from pathlib import Path

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from core.engine import Engine
from core.world import WorldObject
from experiments import m3_part2 as p2
from experiments import m3_step3 as s3

OUT = Path("tools/m3_step3_probes/emptied_end_out.txt")
NEAR = 1.5


CONFIGS = {"research": s3.CONFIGS["research"], "q_none": s3.CONFIGS["q_none"], "q_reverse": s3.CONFIGS["q_reverse"],
           **{k: s3.PHASES["pilot2"]["configs"][k] for k in ("q_floor", "qh_none", "qh_reverse")}}


def run(name: str, seed: int = 31, ticks: int = p2.TICKS):
    cfg = p2.track_config({**s3.BASE, **CONFIGS[name]})
    eng = Engine(seed=seed, config=cfg)
    sites = [WorldObject(x, 0.0, 0.5, "collected") for x in p2.TRACK_ENDS]
    for s in sites:
        eng.world.add_object(s)
    active = 1
    sites[active].kind = "hidden"
    eng.run(1, reset=True)
    near_empty = near_full = muted = moves = turns = 0
    meals = 0
    adv_after_meal = []
    adv_sum = 0.0
    just_ate = 0
    for _ in range(ticks):
        td = eng.run(1)[0]
        ctx = eng.context
        x, y = eng.agent.pos
        empty_x, full_x = sites[1 - active].x, sites[active].x
        if math.hypot(x - full_x, y) <= sites[active].radius:
            sites[active].kind = "collected"
            active = 1 - active
            sites[active].kind = "hidden"
            meals += 1
            just_ate = 8
        if just_ate:
            just_ate -= 1
            if just_ate == 0 and eng.action_learner is not None:
                adv_after_meal.append(tuple(round(v, 3) for v in ctx.action_values))
        if abs(x - empty_x) <= NEAR:
            near_empty += 1
        elif abs(x - full_x) <= NEAR:
            near_full += 1
        muted += ctx.wall_gate < 1.0
        if td.action_name != "REST":
            moves += 1
            turns += td.action_name.startswith("TURN")
        adv_sum += max(abs(v) for v in ctx.action_values)
    return {"meals": meals, "near_empty": near_empty / ticks, "near_full": near_full / ticks, "muted": muted / ticks,
            "turn_share": turns / max(moves, 1), "mean_adv": adv_sum / ticks, "adv_after_meal": adv_after_meal[:3]}


def main() -> None:
    lines = [f"{'config':10s} meals  near empty  near full  wall-gated  turn share  mean |adv|"]
    for name in CONFIGS:
        r = run(name)
        lines.append(f"{name:10s} {r['meals']:5d}  {r['near_empty']:10.2f}  {r['near_full']:9.2f}  {r['muted']:10.2f}  "
                     f"{r['turn_share']:10.2f}  {r['mean_adv']:10.3f}"
                     + (f"   (F, L, R) 8 ticks after the first meals: {r['adv_after_meal']}" if r["adv_after_meal"] else ""))
    text = "\n".join(lines) + "\n"
    OUT.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
