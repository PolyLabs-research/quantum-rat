"""Where the whole's energy went in part 2's smell pilot, and what memory did after the move (disclosed check behind
G60's reading; post hoc, no bounds).

    .venv/bin/python -m tools.whole_probes.smell_budget --workers 24    # writes smell_budget_out.txt beside this script

Re-runs four of the pilot's configurations (the whole; memory unread; without interoception; without dopamine, whose
vigour is then pinned at 1) on its seeds 1-12: the pilot's runs again, checked meal for meal and tick for tick
against docs/data/whole/change/smell_pilot/runs.csv. Per run and half (before the move, after it): the energy budget
per tick (eaten, the basal cost, the locomotor cost), the share of awake ticks moving, vigour, sensed hunger, the share
asleep, memory's pull (the largest value signal times the gain that reads it), and the smell encounters (the odour at
either nostril rising past 0.05) with the share that end in a meal within a minute. From five minutes before the move
to ten after, minute by minute: meals, the share of awake ticks moving, sensed hunger, the reserve, memory's pull, and
the share of time near an old place and near a new one (within 2 units).
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from core.engine import Engine
from core.world import WorldObject
from experiments import whole_change as wc
from experiments import whole_resource as wr
from experiments.rq4a_gate import CUES

HERE = Path(__file__).parent
PILOT = Path("docs/data/whole/change/smell_pilot/runs.csv")
CONFIGS = ("whole", "whole_nomemory", "whole-interoception", "whole-dopamine")
SMELL_ON = 0.05
MEAL_WITHIN = 300  # a minute
MINUTE = 300
MINUTES_BEFORE = 5
MINUTES_AFTER = 10


def one(job):
    name, seed = job
    overrides = wr.configurations(wc.smell_parts())[name]
    cfg = wr.engine_config(overrides, wr.FOOD_ENERGY)
    eng = Engine(seed=seed, config=cfg)
    eng.world.cues.extend(CUES)
    first, second = wc.layouts(bool(wc.FOURTH_PATCH))
    patches = [WorldObject(x, y, wr.PATCH_RADIUS, "hidden") for (x, y) in first]
    for p in patches:
        eng.world.add_object(p)
    regrow = {}
    eng.run(1, reset=True)
    change = wc.windows(wc.TICKS)["change"][0]
    met = eng.metabolism
    gain = cfg.basal_ganglia.value_gain
    halves = {h: {"ticks": 0, "awake": 0, "moving": 0, "vigour": 0.0, "hunger": 0.0, "pull": 0.0, "encounters": 0,
                  "found": 0, "eaten": 0.0, "basal": 0.0, "loco": 0.0} for h in ("before", "after")}
    minutes = [{"meals": 0, "old": 0, "new": 0, "pull": 0.0, "ticks": 0, "awake": 0, "moving": 0, "hunger": 0.0, "reserve": 0.0}
               for _ in range(MINUTES_BEFORE + MINUTES_AFTER)]
    meals, smelling, open_encounters = [], False, []
    for t in range(wc.TICKS):
        if t == change:
            for p, (x, y) in zip(patches, second):
                p.x, p.y, p.kind = x, y, "hidden"
            regrow.clear()
        spent, loco, eaten = met.spent, met.spent_locomotion, met.eaten
        td = eng.run(1)[0]
        c = eng.context
        if c.ingested_object is not None:
            c.ingested_object.kind = "collected"
            regrow[id(c.ingested_object)] = t + wr.REGROW
            meals.append(t)
        for p in patches:
            if regrow.get(id(p)) is not None and t >= regrow[id(p)]:
                p.kind = "hidden"
                del regrow[id(p)]
        h = halves["before" if t < change else "after"]
        h["ticks"] += 1
        h["eaten"] += met.eaten - eaten
        h["loco"] += met.spent_locomotion - loco
        h["basal"] += (met.spent - spent) - (met.spent_locomotion - loco)
        if not c.asleep:
            h["awake"] += 1
            h["moving"] += td.action_name != "REST"
        h["vigour"] += c.vigour
        h["hunger"] += c.hunger
        pull = gain * max(abs(v) for v in c.value_signals)
        h["pull"] += pull
        odour = c.observation.odour if c.observation is not None else None
        now = odour is not None and max(odour) >= SMELL_ON
        if now and not smelling:
            h["encounters"] += 1
            open_encounters.append((t, h))
        if c.ingested_object is not None:
            for start, hh in open_encounters:
                if t - start <= MEAL_WITHIN:
                    hh["found"] += 1
            open_encounters = []
        open_encounters = [(s, hh) for s, hh in open_encounters if t - s <= MEAL_WITHIN]
        smelling = now
        m = (t - change) // MINUTE + MINUTES_BEFORE
        if 0 <= m < MINUTES_BEFORE + MINUTES_AFTER:
            x, y = eng.agent.pos
            mm = minutes[m]
            mm["ticks"] += 1
            mm["awake"] += not c.asleep
            mm["moving"] += (not c.asleep) and td.action_name != "REST"
            mm["hunger"] += c.hunger
            mm["reserve"] += met.reserve
            mm["meals"] += c.ingested_object is not None
            mm["old"] += any(math.hypot(x - a, y - b) <= wc.ZONE for (a, b) in first)
            mm["new"] += any(math.hypot(x - a, y - b) <= wc.ZONE for (a, b) in second)
            mm["pull"] += pull
        if c.starved:
            break
    return {"config": name, "seed": seed, "meals": len(meals), "ticks_run": t + 1, "starved": met.starved, "halves": halves,
            "minutes": minutes}


def _rate(h, key):
    return h[key] / h["ticks"] if h["ticks"] else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    jobs = [(c, s) for c in CONFIGS for s in range(1, 13)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        runs = list(pool.map(one, jobs, chunksize=1))
    with open(PILOT, newline="") as f:
        pilot = {(r["config"], int(r["seed"])): (int(r["meals"]), int(r["survival_ticks"])) for r in csv.DictReader(f)}
    same = all(pilot[(r["config"], r["seed"])] == (r["meals"], r["ticks_run"]) for r in runs)
    lines = [f"the pilot's runs again (meals and ticks run, run by run): {same}", "",
             "per tick x1e4 (means over seeds; a starved run's halves end where it starved)",
             f"{'config':20s} {'half':6s} {'eaten':>6s} {'basal':>6s} {'moving':>6s} {'net':>6s} {'awake moving':>12s} "
             f"{'vigour':>6s} {'hunger':>6s} {'asleep':>6s} {'memory pull':>11s} {'smell encounters':>16s} {'-> meal':>7s}"]
    for name in CONFIGS:
        rr = [r for r in runs if r["config"] == name]
        for half in ("before", "after"):
            hs = [r["halves"][half] for r in rr if r["halves"][half]["ticks"]]
            m = lambda f: statistics.mean(f(h) for h in hs)  # noqa: E731
            eaten, basal, loco = m(lambda h: _rate(h, "eaten")), m(lambda h: _rate(h, "basal")), m(lambda h: _rate(h, "loco"))
            enc = sum(h["encounters"] for h in hs)
            lines.append(f"{name:20s} {half:6s} {eaten * 1e4:6.2f} {basal * 1e4:6.2f} {loco * 1e4:6.2f} {(eaten - basal - loco) * 1e4:+6.2f} "
                         f"{m(lambda h: h['moving'] / h['awake'] if h['awake'] else 0.0):12.2f} {m(lambda h: _rate(h, 'vigour')):6.2f} "
                         f"{m(lambda h: _rate(h, 'hunger')):6.2f} {m(lambda h: 1 - h['awake'] / h['ticks']):6.2f} "
                         f"{m(lambda h: _rate(h, 'pull')):11.3f} {enc / len(hs):16.1f} "
                         f"{(sum(h['found'] for h in hs) / enc if enc else float('nan')):7.2f}")
    lines += ["", "from five minutes before the move to ten after, minute by minute (means over the runs alive in that minute)"]
    for name in CONFIGS:
        rr = [r for r in runs if r["config"] == name]
        lines.append(f"{name}: minute  alive  meals  awake moving  hunger  reserve  memory pull  near old  near new")
        for k in range(MINUTES_BEFORE + MINUTES_AFTER):
            alive = [r["minutes"][k] for r in rr if r["minutes"][k]["ticks"]]
            if not alive:
                continue
            a = lambda f: statistics.mean(f(x) for x in alive)  # noqa: E731
            awake = [x["moving"] / x["awake"] for x in alive if x["awake"]]
            moving = f"{statistics.mean(awake):13.2f}" if awake else f"{'asleep':>13s}"
            lines.append(f"{'':{len(name) + 2}s}{k - MINUTES_BEFORE:+6d} {len(alive):6d} {a(lambda x: x['meals']):6.1f} "
                         f"{moving} {a(lambda x: x['hunger'] / x['ticks']):7.2f} "
                         f"{a(lambda x: x['reserve'] / x['ticks']):8.3f} {a(lambda x: x['pull'] / x['ticks']):12.2f} "
                         f"{a(lambda x: x['old'] / x['ticks']):9.2f} {a(lambda x: x['new'] / x['ticks']):9.2f}")
    text = "\n".join(lines) + "\n"
    (HERE / "smell_budget_out.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
