"""The whole, part 2: foraging when the world changes (docs/prereg/whole_change.md; decisions G58), and its second
design, by smell (docs/prereg/whole_smell.md; G60).

    python3 -m experiments.whole_change --phase pilot --workers 28         # 27 configurations x seeds 1-12 (G58)
    python3 -m experiments.whole_change --phase design --workers 4         # the second design's feasibility rule
    python3 -m experiments.whole_change --phase smell --workers 28         # 29 configurations x seeds 1-12 (G60)
    python3 -m experiments.whole_change --phase design3 --workers 24       # the third design's economy rule
    python3 -m experiments.whole_change --phase smell3 --workers 28        # its pilot (G62)
    python3 -m experiments.whole_change --phase pilot --quick --out /tmp/wc  # the smoke test's run

Part 1's arena, cues, body physics, food (K = 0.065) and 27 configurations (``experiments.whole_resource``). Three
visible patches move, without a signal, half way through a 60-minute run. The spark (§3): A1 survival, A2 recovery
(the intake in the last quarter-hour against the quarter-hour before the change), A3 extinction (time near the old
patches in the last quarter-hour against chance). The windows are fractions of the run, so a quick run keeps them.

The second design: the patches are hidden (smelled, not seen), the parts run on amendment A2's reward scale with
olfaction the thirteenth (29 configurations), and two validity checks come before the verdict: V1, memory is needed
(the whole's intake in the quarter-hour before the move at least 1.25 times the whole's with memory unread), and V2,
the move is a surprise (more ground covered in the five minutes after it than in the five before, paired by seed).
``--phase design`` checks the feasibility rule (§2) on seeds 2001-2004: the whole's mean meals before the move, the
run stopped there, so nothing after the move is seen before the pilot.

The third design (docs/prereg/whole_smell_short.md; G62): the odour's length 0.5 units (three patches mark 12% of the
floor at the encounter threshold, against the second design's 66%), and the food's energy K the smallest on a ladder
at which the whole is in balance before the move (``--phase design3``, seeds 4001-4004), the reward scale following K.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from analysis.stats import paired_effect
from core.engine import Engine
from core.world import WorldObject
from experiments import whole_resource as wr
from experiments.linear_track_replay import _dependency_versions, write_csv
from experiments.rq4a_gate import CUES
from metrics.manifest import build_manifest, finish_manifest, write_manifest

Layout = Tuple[Tuple[float, float], ...]

TICKS = 18000
FIRST: Layout = ((5.0, 5.0), (-6.0, -2.0), (2.0, -6.0))
SECOND: Layout = ((-5.0, 5.0), (6.0, -2.0), (-2.0, -6.0))
ZONE = 2.0  # units around an old patch's centre that count as "near" it
ARENA_AREA = 20.0 * 20.0


def chance(first: Layout) -> float:
    """The share of the arena the old zones cover."""
    return len(first) * math.pi * ZONE ** 2 / ARENA_AREA


CHANCE = chance(FIRST)  # 9.4%
SURVIVAL_MIN = 11
RECOVERY_MIN = 0.8
EXTINCTION_MAX = 1.5
ALIVE_SEEDS_MIN = 8
# The second design (docs/prereg/whole_smell.md; G60): the thirteenth part; the feasibility rule (§2), whose fourth
# patch is added to each layout only if the whole eats fewer than FEASIBLE_MEALS meals before the move on the design
# seeds; condition 3's bound for thirteen parts (§5); V1's margin (§3)
OLFACTION: Dict[str, Any] = {"sensors.olfaction": True, "basal_ganglia.smell_gain": 0.6}
# (in the first layout, the second), amendment P1's places: the draft's (-6, 6) and (6, 6) were 1.4 units from the
# other layout's patches, inside an old zone
FOURTH: Tuple[Tuple[float, float], Tuple[float, float]] = ((-2.0, 7.0), (2.0, 7.0))
FEASIBLE_MEALS = 6.0
# set by --phase design (§2); None: the rule not yet checked. False: 24.75 meals before the move on the design seeds
# (the bound 6; docs/data/whole/change/smell_design), so three patches
FOURTH_PATCH: Optional[bool] = False
SMELL_BREAKS_MIN = 7
V1_MARGIN = 1.25
# The third design (docs/prereg/whole_smell_short.md; G62): the odour's length (§1.1: three patches mark at most 15% of
# the floor at C >= 0.05; 0.5 marks 12%); the economy rule's ladder and bound (§1.2: the reserve over the ten minutes
# before the move, on average over the design seeds, none starving); K as the rule set it
SHORT_LENGTH = 0.5
K_LADDER: Tuple[float, ...] = (0.065, 0.08, 0.10, 0.125, 0.15, 0.20)
BALANCE_MIN = 0.6
# set by --phase design3 (§1.2); None: the rule not yet applied. 0.08: the smallest rung in balance (the reserve 0.63
# over the ten minutes before the move; docs/data/whole/change/short_design)
SHORT_K: Optional[float] = 0.08
QUICK_K = 0.10  # a quick run's K while SHORT_K is unset (the smoke test)
PHASES: Dict[str, Dict[str, Any]] = {
    "pilot": {"seeds": tuple(range(1, 13)), "out": Path("docs/data/whole/change/pilot"), "prereg": "docs/prereg/whole_change.md"},
    "design": {"seeds": (2001, 2002, 2003, 2004), "out": Path("docs/data/whole/change/smell_design"),
               "prereg": "docs/prereg/whole_smell.md"},
    "smell": {"seeds": tuple(range(1, 13)), "out": Path("docs/data/whole/change/smell_pilot"), "prereg": "docs/prereg/whole_smell.md"},
    "design3": {"seeds": (4001, 4002, 4003, 4004), "out": Path("docs/data/whole/change/short_design"),
                "prereg": "docs/prereg/whole_smell_short.md"},
    "smell3": {"seeds": tuple(range(1, 13)), "out": Path("docs/data/whole/change/short_pilot"),
               "prereg": "docs/prereg/whole_smell_short.md"},
}
QUICK_SEEDS = (1,)
QUICK_TICKS = 1200
TRACE_EVERY = 150
COLUMNS = ("config", "seed", "survived", "survival_ticks", "final_energy", "min_energy_after", "meals", "meals_before", "meals_after",
           "intake_before", "intake_after", "recovery", "efficiency_before", "efficiency_after", "old_zone_post5", "old_zone_after",
           "first_new_meal", "coverage_pre5", "coverage_post5", "ne_pre5", "ne_post5", "temperature_pre5", "temperature_post5",
           "sleep_share", "replay_events")
SMELL_COLUMNS = COLUMNS + ("meals_pre_move",)
DESIGN_COLUMNS = ("config", "seed", "survived", "survival_ticks", "meals_pre_move", "final_energy", "sleep_share")
DESIGN3_COLUMNS = ("config", "seed", "food_energy", "survived", "survival_ticks", "meals_pre_move", "reserve_pre10", "final_energy",
                   "sleep_share")


def smell_parts(odour_length: Optional[float] = None, food_energy: Optional[float] = None) -> Dict[str, Dict[str, Any]]:
    """The second design's thirteen parts (§5): part 1's twelve on amendment A2's reward scale, and olfaction. The third
    design's: the odour's ``odour_length``, and the scale following ``food_energy`` (9.7 x 0.065 / K, §1.3)."""
    scale = wr.REWARD_SCALE if food_energy is None else wr.REWARD_SCALE * wr.FOOD_ENERGY / food_energy
    parts = wr.scaled_parts(scale)
    parts["olfaction"] = dict(OLFACTION) if odour_length is None else {**OLFACTION, "sensors.odour_length": odour_length}
    return parts


def layouts(fourth: bool) -> Tuple[Layout, Layout]:
    """(the first layout, the second), with the feasibility rule's fourth patch if ``fourth``."""
    return (FIRST + (FOURTH[0],), SECOND + (FOURTH[1],)) if fourth else (FIRST, SECOND)


def windows(ticks: int) -> Dict[str, Tuple[int, int]]:
    """The change at half the run; the quarter before it, the last quarter, five minutes (a twelfth) either side."""
    change, twelfth = ticks // 2, ticks // 12
    return {"change": (change, change), "before": (ticks // 4, change), "after": (3 * ticks // 4, ticks),
            "pre5": (change - twelfth, change), "post5": (change, change + twelfth)}


def _share(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def run_task(job: Tuple[Any, ...]) -> Dict[str, Any]:
    """One run: ``(name, overrides, seed, ticks)``, part 2's visible patches in ``FIRST`` then ``SECOND``; or with
    ``(kind, first, second, until)`` appended, patches of ``kind`` in the given layouts, the run stopped at ``until``;
    and a food energy after those (part 1's K unless given)."""
    name, overrides, seed, ticks, *task = job
    kind, first, second, until, *rest = task if task else ("target", FIRST, SECOND, ticks)
    food = rest[0] if rest else wr.FOOD_ENERGY
    w = windows(ticks)
    change = w["change"][0]
    cfg = wr.engine_config(overrides, food)
    eng = Engine(seed=seed, config=cfg)
    eng.world.cues.extend(CUES)
    patches = [WorldObject(x, y, wr.PATCH_RADIUS, kind) for (x, y) in first]
    for p in patches:
        eng.world.add_object(p)
    regrow_at: Dict[int, int] = {}
    eng.run(1, reset=True)
    energy: List[float] = []
    near_old: List[bool] = []
    awake: List[bool] = []
    moving_bins: List[Tuple[int, int]] = []
    ne: List[float] = []
    temps: List[float] = []
    meal_ticks: List[int] = []
    cum: Dict[int, Tuple[float, float]] = {}  # tick -> (eaten, locomotor energy spent) at the window edges
    edges = {w["before"][0], change, w["after"][0]}
    trace: List[Dict[str, Any]] = []
    survived, survival_ticks = True, until
    met = eng.metabolism
    for t in range(until):
        if t in edges:
            cum[t] = (met.eaten, met.spent_locomotion)
        if t == change:  # the patches move, without a signal: every one has food at its new place
            for p, (x, y) in zip(patches, second):
                p.x, p.y, p.kind = x, y, kind
            regrow_at.clear()
        td = eng.run(1)[0]
        ctx = eng.context
        if ctx.ingested_object is not None:
            ctx.ingested_object.kind = "collected"
            regrow_at[id(ctx.ingested_object)] = t + wr.REGROW
            meal_ticks.append(t)
        for p in patches:
            due = regrow_at.get(id(p))
            if due is not None and t >= due:
                p.kind = kind
                del regrow_at[id(p)]
        x, y = eng.agent.pos
        energy.append(met.reserve)
        near_old.append(any(math.hypot(x - ox, y - oy) <= ZONE for (ox, oy) in first))
        awake.append(not ctx.asleep)
        moving_bins.append((math.floor(x / 0.5), math.floor(y / 0.5)))
        ne.append(ctx.neuromodulators.get("NE", 0.0))
        temps.append(ctx.temperature)
        if t % TRACE_EVERY == 0:
            trace.append({"config": name, "seed": seed, "tick": t, "energy": round(met.reserve, 5), "gut": round(met.gut, 5),
                          "asleep": int(ctx.asleep)})
        if ctx.starved:
            survived, survival_ticks = False, t + 1
            break
    n = len(energy)
    end = (met.eaten, met.spent_locomotion)

    def at(tick: int) -> Tuple[float, float]:
        return cum.get(tick, end)  # a starved run's later edges are its end

    def rate(a: int, b: int) -> float:
        return (at(b)[0] if b < ticks else end[0]) - at(a)[0]

    b0, b1 = w["before"]
    a0, a1 = w["after"]
    eaten_before, eaten_after = rate(b0, b1), rate(a0, a1)
    loco_before = at(b1)[1] - at(b0)[1]
    loco_after = end[1] - at(a0)[1]

    def window_share(flags: Sequence[bool], a: int, b: int) -> float:
        idx = [i for i in range(a, min(b, n)) if awake[i]]
        return _share([flags[i] for i in idx])

    after_meals = [m for m in meal_ticks if m >= change]
    row = {
        "config": name, "seed": seed, "survived": survived, "survival_ticks": survival_ticks,
        "final_energy": round(energy[-1], 5), "min_energy_after": min(energy[change:]) if n > change else 0.0,
        "meals": len(meal_ticks), "meals_before": sum(1 for m in meal_ticks if b0 <= m < b1),
        "meals_after": sum(1 for m in meal_ticks if a0 <= m < a1),
        "intake_before": eaten_before / (b1 - b0), "intake_after": eaten_after / (a1 - a0),
        "recovery": (eaten_after / (a1 - a0)) / (eaten_before / (b1 - b0)) if eaten_before > 0 else float("nan"),
        "efficiency_before": eaten_before / loco_before if loco_before > 0 else float("nan"),
        "efficiency_after": eaten_after / loco_after if loco_after > 0 else float("nan"),
        "old_zone_post5": window_share(near_old, *w["post5"]), "old_zone_after": window_share(near_old, a0, a1),
        "first_new_meal": (after_meals[0] - change) if after_meals else float("nan"),
        "coverage_pre5": len(set(moving_bins[w["pre5"][0]:min(w["pre5"][1], n)])),
        "coverage_post5": len(set(moving_bins[w["post5"][0]:min(w["post5"][1], n)])),
        "ne_pre5": _share(ne[w["pre5"][0]:min(w["pre5"][1], n)]), "ne_post5": _share(ne[w["post5"][0]:min(w["post5"][1], n)]),
        "temperature_pre5": _share(temps[w["pre5"][0]:min(w["pre5"][1], n)]),
        "temperature_post5": _share(temps[w["post5"][0]:min(w["post5"][1], n)]),
        "sleep_share": (n - sum(awake)) / until, "replay_events": len(eng.replay_log),
        "meals_pre_move": sum(1 for m in meal_ticks if m < change),
        "food_energy": food, "reserve_pre10": _reserve_before(energy, change, ticks // 6),
    }
    return {"row": row, "trace": trace}


def _reserve_before(energy: Sequence[float], change: int, span: int) -> float:
    """The mean reserve over the ``span`` ticks before ``change``; ticks after a starvation count 0."""
    return sum(energy[max(0, change - span):min(change, len(energy))]) / span


def _mean(values: Sequence[float]) -> float:
    vals = [v for v in values if not (isinstance(v, float) and math.isnan(v))]
    return statistics.mean(vals) if vals else float("nan")


def score(rows: Sequence[Mapping[str, Any]], chance_share: float = CHANCE) -> Dict[str, Any]:
    """The spark (§3) for one configuration's runs; ``chance_share`` is the old zones' share of the arena."""
    survived = sum(1 for r in rows if r["survived"])
    before, after = _mean([r["intake_before"] for r in rows]), _mean([r["intake_after"] for r in rows])
    alive = [r["old_zone_after"] for r in rows if not (isinstance(r["old_zone_after"], float) and math.isnan(r["old_zone_after"]))]
    old_zone = _mean(alive)
    a1 = survived >= SURVIVAL_MIN
    a2 = before > 0 and after >= RECOVERY_MIN * before
    a3 = len(alive) >= ALIVE_SEEDS_MIN and old_zone <= EXTINCTION_MAX * chance_share
    return {"survived": survived, "intake_before": before, "intake_after": after, "recovery": (after / before) if before > 0 else float("nan"),
            "old_zone_after": old_zone, "old_zone_bound": EXTINCTION_MAX * chance_share, "seeds_alive_after": len(alive),
            "A1": a1, "A2": bool(a2), "A3": bool(a3), "spark": bool(a1 and a2 and a3),
            "old_zone_post5": _mean([r["old_zone_post5"] for r in rows]), "first_new_meal": _mean([r["first_new_meal"] for r in rows]),
            "coverage_pre5": _mean([r["coverage_pre5"] for r in rows]), "coverage_post5": _mean([r["coverage_post5"] for r in rows]),
            "ne_pre5": _mean([r["ne_pre5"] for r in rows]), "ne_post5": _mean([r["ne_post5"] for r in rows]),
            "efficiency_before": _mean([r["efficiency_before"] for r in rows]), "efficiency_after": _mean([r["efficiency_after"] for r in rows]),
            "sleep_share": _mean([r["sleep_share"] for r in rows]), "meals": _mean([r["meals"] for r in rows]),
            "min_energy_after": _mean([r["min_energy_after"] for r in rows])}


def verdict(scores: Mapping[str, Mapping[str, Any]], parts: Optional[Mapping[str, Any]] = None,
            breaks_min: Optional[int] = None) -> Dict[str, Any]:
    """The verdict's three conditions over ``parts`` (part 1's twelve unless given), condition 3 at ``breaks_min``."""
    parts = wr.PARTS if parts is None else parts
    breaks_min = wr.BREAKS_MIN if breaks_min is None else breaks_min
    singles = {p: scores[f"base+{p}"]["spark"] for p in parts}
    breaks = {p: not scores[f"whole-{p}"]["spark"] for p in parts}
    w, nm = scores["whole"], scores["whole_nomemory"]
    return {"1_whole_shows_the_spark": w["spark"], "2_no_single_addition_shows_it": not any(singles.values()),
            "3_most_removals_break_it": sum(breaks.values()) >= breaks_min, "removals_that_break_it": [p for p, b in breaks.items() if b],
            "single_additions_that_show_it": [p for p, s in singles.items() if s],
            "memory_margin_reported": {"before": [w["efficiency_before"], nm["efficiency_before"]],
                                       "after": [w["efficiency_after"], nm["efficiency_after"]]}}


def validity(whole: Sequence[Mapping[str, Any]], nomemory: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """The second design's validity checks (§3), read before the verdict: V1, the whole's mean intake in the quarter-hour
    before the move at least ``V1_MARGIN`` times the whole's with memory unread; V2, the ground covered (0.5-unit bins)
    in the five minutes after the move against the five before, paired by seed, the BCa interval's lower end above 0."""
    with_memory, without = _mean([r["intake_before"] for r in whole]), _mean([r["intake_before"] for r in nomemory])
    ratio = with_memory / without if without > 0 else (math.inf if with_memory > 0 else float("nan"))
    cover = paired_effect([r["coverage_pre5"] for r in whole], [r["coverage_post5"] for r in whole])
    return {"V1_memory_needed": bool(ratio >= V1_MARGIN), "V1_ratio": ratio, "V1_intake_whole": with_memory,
            "V1_intake_nomemory": without, "V2_move_surprises": bool(cover["low"] > 0.0), "V2_coverage": cover}


def design_rule(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """The feasibility rule (§2): the whole's mean meals before the move on the design seeds, at least FEASIBLE_MEALS."""
    meals = [r["meals_pre_move"] for r in sorted(rows, key=lambda r: r["seed"])]
    mean = statistics.mean(meals)
    return {"meals_pre_move": meals, "mean": mean, "bound": FEASIBLE_MEALS, "passes": mean >= FEASIBLE_MEALS,
            "starved_before_move": sum(1 for r in rows if not r["survived"])}


def economy_rule(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """The third design's economy rule (§1.2): per rung of the ladder, the mean reserve over the ten minutes before the
    move and the runs that starved; K is the smallest rung in balance (at least BALANCE_MIN, none starved), else None."""
    rungs = {}
    for k in sorted({r["food_energy"] for r in rows}):
        rr = [r for r in rows if r["food_energy"] == k]
        reserve = statistics.mean(r["reserve_pre10"] for r in rr)
        starved = sum(1 for r in rr if not r["survived"])
        rungs[k] = {"reserve_pre10": reserve, "starved": starved, "meals_pre_move": statistics.mean(r["meals_pre_move"] for r in rr),
                    "in_balance": reserve >= BALANCE_MIN and starved == 0}
    chosen = next((k for k, v in rungs.items() if v["in_balance"]), None)
    return {"rungs": rungs, "bound": BALANCE_MIN, "K": chosen}


def _pool(jobs, workers):
    if workers == 1:
        return [run_task(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_task, jobs, chunksize=1))


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phase", choices=tuple(PHASES), required=True)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    spec = PHASES[args.phase]
    out = args.out or spec["out"]
    if args.quick and out.resolve() == spec["out"].resolve():
        parser.error("a quick run must not overwrite the committed tables: give --out")
    seeds = QUICK_SEEDS if args.quick else spec["seeds"]
    ticks = QUICK_TICKS if args.quick else TICKS
    if args.phase == "smell" and FOURTH_PATCH is None and not args.quick:
        parser.error("the feasibility rule has not been checked: run --phase design and set FOURTH_PATCH (§2)")
    if args.phase == "smell3" and SHORT_K is None and not args.quick:
        parser.error("the economy rule has not been applied: run --phase design3 and set SHORT_K (§1.2)")
    smell = args.phase != "pilot"
    first, second = layouts(bool(FOURTH_PATCH)) if args.phase in ("design", "smell") else (FIRST, SECOND)
    chance_share = chance(first)
    food = wr.FOOD_ENERGY
    if args.phase == "pilot":
        configs, columns = wr.configurations(), COLUMNS
        jobs = [(c, ov, s, ticks) for c, ov in configs.items() for s in seeds]
    elif args.phase == "design":  # the whole only, stopped at the move: nothing after it is seen before the pilot
        configs, columns = {"whole": wr.configurations(smell_parts())["whole"]}, DESIGN_COLUMNS
        jobs = [("whole", configs["whole"], s, ticks, "hidden", first, second, ticks // 2) for s in seeds]
    elif args.phase == "design3":  # every rung of the ladder, the whole only, stopped at the move
        configs = {f"whole K={k:g}": wr.configurations(smell_parts(SHORT_LENGTH, k))["whole"] for k in K_LADDER}
        columns = DESIGN3_COLUMNS
        jobs = [(f"whole K={k:g}", configs[f"whole K={k:g}"], s, ticks, "hidden", first, second, ticks // 2, k)
                for k in K_LADDER for s in seeds]
    elif args.phase == "smell3":
        food = SHORT_K if SHORT_K is not None else QUICK_K
        configs, columns = wr.configurations(smell_parts(SHORT_LENGTH, food)), SMELL_COLUMNS
        jobs = [(c, ov, s, ticks, "hidden", first, second, ticks, food) for c, ov in configs.items() for s in seeds]
    else:
        configs, columns = wr.configurations(smell_parts()), SMELL_COLUMNS
        jobs = [(c, ov, s, ticks, "hidden", first, second, ticks) for c, ov in configs.items() for s in seeds]
    started = time.perf_counter()
    results = _pool(jobs, args.workers)
    rows = [r["row"] for r in results]
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "runs.csv", columns, rows)
    write_csv(out / "energy_trace.csv", ("config", "seed", "tick", "energy", "gut", "asleep"), [t for r in results for t in r["trace"]])
    summary: Dict[str, Any] = {"phase": args.phase, "seeds": list(seeds), "ticks": ticks, "food_energy": food,
                               "quick": args.quick, "windows": windows(ticks), "configs": configs}
    if smell:
        summary.update({"kind": "hidden", "first": first, "second": second, "fourth_patch": FOURTH_PATCH,
                        "reward_scale": wr.REWARD_SCALE})
    if args.phase in ("design3", "smell3"):
        summary.update({"odour_length": SHORT_LENGTH, "fourth_patch": None, "food_energy": None if args.phase == "design3" else food,
                        "reward_scale": None if args.phase == "design3" else wr.REWARD_SCALE * wr.FOOD_ENERGY / food})
    if args.phase == "design":
        summary["rule"] = design_rule(rows)
        print(json.dumps(summary["rule"], indent=1))
    elif args.phase == "design3":
        summary["rule"] = economy_rule(rows)
        print(json.dumps(summary["rule"], indent=1))
    else:
        scores = {c: score([r for r in rows if r["config"] == c], chance_share) for c in configs}
        summary.update({"chance": chance_share, "scores": scores})
        if smell:
            summary["validity"] = validity([r for r in rows if r["config"] == "whole"], [r for r in rows if r["config"] == "whole_nomemory"])
            summary["verdict"] = verdict(scores, smell_parts(), SMELL_BREAKS_MIN)  # the part names, the same in either design
        else:
            summary["verdict"] = verdict(scores)
        print(f"{'config':24s} surv  intake b->a (recov)   old zone after(bound)  first new meal  cover pre->post  NE pre->post  A1 A2 A3 spark")
        for c, s in scores.items():
            print(f"{c:24s} {s['survived']:4d}  {s['intake_before'] * 1e4:5.2f}->{s['intake_after'] * 1e4:5.2f} ({s['recovery']:.2f})   "
                  f"{s['old_zone_after']:.3f}({s['old_zone_bound']:.3f})         {s['first_new_meal']:7.0f}        "
                  f"{s['coverage_pre5']:5.0f}->{s['coverage_post5']:5.0f}    {s['ne_pre5']:.2f}->{s['ne_post5']:.2f}   "
                  + "  ".join("+" if s[k] else "-" for k in ("A1", "A2", "A3")) + f"  {'yes' if s['spark'] else 'no'}")
        if smell:
            print(json.dumps(summary["validity"], indent=1, default=str))
        print(json.dumps(summary["verdict"], indent=1, default=str))
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str))
    manifest = build_manifest(wr.engine_config(wr.BASE, food), protocol=f"whole_change:{args.phase}", seeds=list(seeds),
                              ticks_requested=ticks, extra={"configs": configs, "phase": args.phase, "quick": args.quick,
                                                            "prereg": f"{spec['prereg']} (draft)", "food_energy": summary["food_energy"],
                                                            "dependencies": _dependency_versions(),
                                                            "command": "python3 -m experiments.whole_change " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    finish_manifest(manifest, ticks_run=sum(r["survival_ticks"] for r in rows), wall_seconds=time.perf_counter() - started)
    write_manifest(out / "manifest.json", manifest)
    print(f"wrote {out} in {time.perf_counter() - started:.1f} s")
    return summary


if __name__ == "__main__":
    main()
