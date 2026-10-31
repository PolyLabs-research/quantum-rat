"""Dopamine's tonic level as a rate: does it lower vigour where food is scarce? (G61; exploratory design probe before
any registration, on fresh design seeds 3001-3012, never used again.)

    .venv/bin/python -m tools.whole_probes.tonic_rate --workers 24    # writes tonic_rate_out.txt beside this script

G59 C1 recommended making tonic dopamine an average rate of reward, on the reading that a lower rate of reward would
lower vigour in scarcity. Checked before this probe against G59's own numbers: with reward as drive reduction a hungry
meal is worth more, and the whole's reward per tick was about six times higher in the half-food arena (24.1 meals at
4.62) than in the familiar one (19.9 at 0.96), so a reward-rate tonic should raise vigour there. The probe runs the
whole (part 1's parts, A2's scale 9.7) in both of part 1's arenas with three tonic models:

- ``peak``: as built (G56), the last meal's reward held and falling over 2 minutes;
- ``reward_rate``: a leaky mean of the reward per tick over 10 minutes, over 0.0042 (twice the whole's familiar-arena
  rate in G59, so that vigour there starts near the held peak's 0.73; a probe setting, not a registered value);
- ``energy_rate``: a leaky mean of the energy eaten per tick over 10 minutes, over the cost of moving at full speed
  (fixed by metabolism; no free setting).

Per run: survival, the level over the second half (dead ticks 0), the share of awake ticks moving, mean vigour, meals,
efficiency (energy eaten per unit spent moving) and the mean reward of a meal. Predictions written before the run: the
reward rate raises vigour in the half-food arena above the held peak's; the energy rate is uncertain, since a regulator
eats what it spends and its income then tracks its effort.
"""

from __future__ import annotations

import argparse
import statistics
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from core.engine import Engine
from core.world import WorldObject
from experiments import whole_resource as wr
from experiments.rq4a_gate import CUES

HERE = Path(__file__).parent
SEEDS = tuple(range(3001, 3013))
MODELS = {"peak": {}, "reward_rate": {"neuromod.tonic_model": "reward_rate", "neuromod.rate_ref": 0.0042},
          "energy_rate": {"neuromod.tonic_model": "energy_rate"}}


def one(job):
    model, env, seed = job
    cfg = wr.engine_config({**wr.configurations(wr.scaled_parts(wr.REWARD_SCALE))["whole"], **MODELS[model]}, wr.FOOD_ENERGY)
    eng = Engine(seed=seed, config=cfg)
    eng.world.cues.extend(CUES)
    patches = [WorldObject(x, y, wr.PATCH_RADIUS, "target") for (x, y) in wr.ENVIRONMENTS[env]]
    for p in patches:
        eng.world.add_object(p)
    eng.run(1, reset=True)
    regrow, energy, moving, vig, values = {}, [], [], [], []
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
            moving.append(td.action_name != "REST")
        vig.append(c.vigour)
        if c.starved:
            break
    met = eng.metabolism
    half = wr.TICKS // 2
    return {"model": model, "env": env, "seed": seed, "survived": not met.starved,
            "level_late": sum(energy[half:]) / (wr.TICKS - half), "moving_awake": sum(moving) / max(len(moving), 1),
            "vigour": statistics.mean(vig), "meals": len(values),
            "efficiency": met.eaten / met.spent_locomotion if met.spent_locomotion > 0 else float("nan"),
            "meal_reward": statistics.mean(values) if values else float("nan")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    jobs = [(m, e, s) for m in MODELS for e in ("full", "half") for s in SEEDS]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(one, jobs, chunksize=1))
    lines = [f"the whole, seeds {SEEDS[0]}-{SEEDS[-1]}, part 1's arenas, scale {wr.REWARD_SCALE}",
             f"{'tonic model':12s} {'arena':5s} {'survived':>8s} {'level':>6s} {'moving':>7s} {'vigour':>7s} {'meals':>6s} "
             f"{'efficiency':>10s} {'meal reward':>11s}"]
    levels = {}
    for m in MODELS:
        for e in ("full", "half"):
            rr = [r for r in rows if r["model"] == m and r["env"] == e]
            mean = lambda k: statistics.mean(r[k] for r in rr if r[k] == r[k])  # noqa: E731
            levels[(m, e)] = mean("level_late")
            lines.append(f"{m:12s} {e:5s} {sum(r['survived'] for r in rr):8d} {mean('level_late'):6.3f} {mean('moving_awake'):7.3f} "
                         f"{mean('vigour'):7.3f} {mean('meals'):6.1f} {mean('efficiency'):10.2f} {mean('meal_reward'):11.3f}")
    lines.append("")
    lines += [f"level drop, familiar -> half food, {m}: {levels[(m, 'full')] - levels[(m, 'half')]:.3f} (A1's bound 0.10)" for m in MODELS]
    text = "\n".join(lines) + "\n"
    (HERE / "tonic_rate_out.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
