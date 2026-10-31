"""What letting the memory term pass the wall gate does (disclosed check behind the correction to G55; spent seeds).

    .venv/bin/python -m tools.m3_step3_probes.wall_gate --workers 28     # writes wall_gate_out.txt beside this script

The wall gate is ``basal_ganglia.wall_gate_gain`` (1.0): it scales memory's push to hold course by the closeness of the
wall on the centre ray. With ``value_memory.source`` "action" the only memory term is the action value, so gain 0 there
is exactly "the learned action value passes the gate" (G55 D1's proposed third pilot); the SR rows show what the same
switch does to the profile. Part 1 runs step 2's battery (the pilot's spent seeds) for five configurations; part 2
measures, on four track seeds, where the action-value agent spends the run with the gate on and off.
"""

from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from core.engine import Engine
from core.world import WorldObject
from experiments import m3_part2 as p2
from experiments import m3_step3 as s3
from experiments import rq4a_gate as rg

OUT = Path(__file__).with_name("wall_gate_out.txt")
OFF = {"basal_ganglia.wall_gate_gain": 0.0}
P2 = s3.PHASES["pilot2"]["configs"]
CONFIGS = {
    "research": {},
    "research_nogate": {**OFF},
    "qh_none": P2["qh_none"],
    "qh_none_nogate": {**P2["qh_none"], **OFF},
    "qh_reverse_nogate": {**P2["qh_reverse"], **OFF},
}


def track_diagnostics(over, seed):
    eng = Engine(seed=seed, config=p2.track_config({**s3.BASE, **over}))
    sites = [WorldObject(x, 0.0, 0.5, "collected") for x in p2.TRACK_ENDS]
    for s in sites:
        eng.world.add_object(s)
    active = 1
    sites[active].kind = "hidden"
    eng.run(1, reset=True)
    meals = moves = turns = stuck = 0
    last = eng.agent.pos
    for _ in range(p2.TICKS):
        td = eng.run(1)[0]
        x, y = eng.agent.pos
        if math.hypot(x - sites[active].x, y) <= sites[active].radius:
            sites[active].kind = "collected"
            active = 1 - active
            sites[active].kind = "hidden"
            meals += 1
        if td.action_name != "REST":
            moves += 1
            turns += td.action_name.startswith("TURN")
        stuck += td.action_name == "FORWARD" and math.hypot(x - last[0], y - last[1]) < 0.05
        last = (x, y)
    return {"meals": meals, "turn_share": turns / max(moves, 1), "pressing_without_moving": stuck / p2.TICKS}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    lines = []
    gate, track, food, _ = p2.run_battery(CONFIGS, s3.SEEDS, rg.TRIALS, p2.TICKS, args.workers, base=s3.BASE)
    lines.append(f"{'config':18s} {'pass':>4s}  " + "  ".join(f"{b[:12]:>12s}" for b in p2.BOUNDS))
    for c in CONFIGS:
        s = p2.score(c, gate, track, food)
        lines.append(f"{c:18s} {s['passed']:4d}  " + "  ".join(f"{s['values'][b]:11.2f}{'+' if s['passes'][b] else '-'}" for b in p2.BOUNDS))
    lines.append("track, learned arm (mean per run): rewards, traversals")
    for c in CONFIGS:
        rr = [r for r in track if r["config"] == c and r["arm"] == "learned"]
        lines.append(f"  {c:18s} {statistics.mean(r['rewards'] for r in rr):5.1f} {statistics.mean(r['traversals'] for r in rr):5.1f}")
    lines.append("the action value on the track, seeds 31-34 (mean): meals, turn share of movement ticks, pressing forward without moving")
    for label, over in (("gate on", P2["qh_none"]), ("gate off", {**P2["qh_none"], **OFF})):
        rows = [track_diagnostics(over, s) for s in (31, 32, 33, 34)]
        lines.append(f"  {label:9s} " + "  ".join(f"{k} {statistics.mean(r[k] for r in rows):.3f}" for k in rows[0]))
    text = "\n".join(lines) + "\n"
    OUT.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
