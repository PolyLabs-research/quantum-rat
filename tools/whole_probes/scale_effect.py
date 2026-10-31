"""What amendment A2's reward scale changed, seed for seed (disclosed check behind G59's reading; post hoc, no bounds).

    .venv/bin/python -m tools.whole_probes.scale_effect --workers 24    # writes scale_effect_out.txt beside this script

The re-pilot ran the half-food arena on seeds 1-12 only under the new scale, and the confirmatory run's old-scale
numbers are on other seeds; this runs the whole on seeds 1-12 in both arenas at scale 1 and at 9.7 (the re-pilot's
runs again, checked meal for meal), recording per run: the level over the second half, the share of awake ticks
moving, the mean vigour, the mean softmax temperature, the share of ticks on which the action value's largest
advantage reaches its read floor, meals, and the mean reward of a meal.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from core.engine import Engine
from core.world import WorldObject
from experiments import whole_resource as wr
from experiments.rq4a_gate import CUES

HERE = Path(__file__).parent
REPILOT = Path("docs/data/whole/resource/repilot/runs.csv")


def one(job):
    scale, env, seed = job
    parts = wr.scaled_parts(scale) if scale != 1.0 else wr.PARTS
    cfg = wr.engine_config(wr.configurations(parts)["whole"], wr.FOOD_ENERGY)
    eng = Engine(seed=seed, config=cfg)
    eng.world.cues.extend(CUES)
    patches = [WorldObject(x, y, wr.PATCH_RADIUS, "target") for (x, y) in wr.ENVIRONMENTS[env]]
    for p in patches:
        eng.world.add_object(p)
    eng.run(1, reset=True)
    regrow, energy, moving, vig, temp, above, values = {}, [], [], [], [], 0, []
    awake = 0
    floor = cfg.action_value.read_floor
    for t in range(wr.TICKS):
        td = eng.run(1)[0]
        c = eng.context
        if c.ingested_object is not None:
            c.ingested_object.kind = "collected"
            regrow[id(c.ingested_object)] = t + wr.REGROW
            values.append(c.meal_value)
        for p in patches:
            if regrow.get(id(p)) is not None and t >= regrow[id(p)]:
                p.kind = "target"
                del regrow[id(p)]
        energy.append(eng.metabolism.reserve)
        if not c.asleep:
            awake += 1
            moving.append(td.action_name != "REST")
        vig.append(c.vigour)
        temp.append(c.temperature)
        above += max(abs(v) for v in c.action_values) >= floor
        if c.starved:
            break
    late = energy[wr.TICKS // 2:]
    return {"scale": scale, "env": env, "seed": seed, "meals": len(values), "survived": not eng.metabolism.starved,
            "level_late": sum(late) / (wr.TICKS - wr.TICKS // 2), "moving_awake": sum(moving) / max(len(moving), 1),
            "mean_vigour": statistics.mean(vig), "mean_temperature": statistics.mean(temp), "steering_share": above / len(energy),
            "mean_meal_reward": statistics.mean(values) if values else float("nan")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    jobs = [(s, e, seed) for s in (1.0, wr.REWARD_SCALE) for e in ("full", "half") for seed in range(1, 13)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(one, jobs, chunksize=1))
    with open(REPILOT, newline="") as f:
        rep = {(r["env"], int(r["seed"])): int(r["meals"]) for r in csv.DictReader(f) if r["config"] == "whole"}
    same = all(rep[(r["env"], r["seed"])] == r["meals"] for r in rows if r["scale"] != 1.0)
    lines = [f"the scaled runs identical to the re-pilot's (meals, run by run): {same}",
             f"{'scale':>5s} {'arena':5s} {'survived':>8s} {'level':>6s} {'moving':>7s} {'vigour':>7s} {'temperature':>11s} "
             f"{'action value steers':>20s} {'meals':>6s} {'meal reward':>11s}"]
    for s in (1.0, wr.REWARD_SCALE):
        for e in ("full", "half"):
            rr = [r for r in rows if r["scale"] == s and r["env"] == e]
            m = lambda k: statistics.mean(r[k] for r in rr if r[k] == r[k])  # noqa: E731
            lines.append(f"{s:5.1f} {e:5s} {sum(r['survived'] for r in rr):8d} {m('level_late'):6.3f} {m('moving_awake'):7.3f} "
                         f"{m('mean_vigour'):7.3f} {m('mean_temperature'):11.3f} {m('steering_share'):20.3f} {m('meals'):6.1f} {m('mean_meal_reward'):11.3f}")
    text = "\n".join(lines) + "\n"
    (HERE / "scale_effect_out.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
