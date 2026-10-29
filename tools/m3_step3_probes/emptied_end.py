"""Where the action-value agent spends the track run (disclosed check behind G55's reading; spent seeds; not a result).

    .venv/bin/python -m tools.m3_step3_probes.emptied_end

The step 3 pilot's track: for the research profile and the learner with replay none and reverse, seed 31, 3,000 ticks,
the share of ticks spent within 1.5 units of the end the agent has just eaten at (the empty one) and of the other end
(the full one), the number of meals, and the action value's advantages read at the empty end right after a meal.
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


def run(name: str, seed: int = 31, ticks: int = p2.TICKS):
    cfg = p2.track_config({**s3.BASE, **s3.CONFIGS[name]})
    eng = Engine(seed=seed, config=cfg)
    sites = [WorldObject(x, 0.0, 0.5, "collected") for x in p2.TRACK_ENDS]
    for s in sites:
        eng.world.add_object(s)
    active = 1
    sites[active].kind = "hidden"
    eng.run(1, reset=True)
    near_empty = near_full = 0
    meals = 0
    adv_after_meal = []
    just_ate = 0
    for _ in range(ticks):
        eng.run(1)
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
                adv_after_meal.append(tuple(round(v, 3) for v in eng.context.action_values))
        if abs(x - empty_x) <= NEAR:
            near_empty += 1
        elif abs(x - full_x) <= NEAR:
            near_full += 1
    return meals, near_empty / ticks, near_full / ticks, adv_after_meal[:4]


def main() -> None:
    lines = []
    for name in ("research", "q_none", "q_reverse"):
        meals, empty, full, adv = run(name)
        lines.append(f"{name:10s} meals {meals:3d}  ticks near the emptied end {empty:.2f}  near the full end {full:.2f}"
                     + (f"  advantages (F, L, R) 8 ticks after the first meals: {adv}" if adv else ""))
    text = "\n".join(lines) + "\n"
    OUT.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
