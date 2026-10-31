"""The whole, part 1: resource management (docs/prereg/whole_resource.md; decisions G56).

    python3 -m experiments.whole_resource --phase calibrate --workers 4   # the base on seeds 1001-1004 -> K
    python3 -m experiments.whole_resource --phase pilot --workers 28      # 27 configurations x seeds 1-12
    python3 -m experiments.whole_resource --phase pilot --quick --out /tmp/wr   # the smoke test's run

The task (§3): a 2 m square arena with the gate's four distal cues and four visible food patches (radius 0.75 units at
(+-5, +-5)) that regrow 600 ticks after being eaten; the agent starts at the centre with E = 0.6; 9,000 ticks; metabolism
on in every configuration, starvation ending the run. The configurations (§5): the base (the research profile as G54
left it, with the capped step), the whole (the base with the twelve parts of ``PARTS``), the whole minus each part, the
base plus each part, and the whole with memory unread. Scored by the spark (§4: R1 homeostasis, R2 need-contingent
activity; R3 the memory margin, the whole only) and the emergence verdict (§5).

**Calibration** (§3): the base's behaviour does not depend on the food's energy K (it does not sense its energy, eats on
every contact and learns the contact bonus), so it runs with no cost charged (``metabolism.basal_cost`` 0, so it cannot
starve) and the cost it would have paid is computed from its speed tick by tick; K = that cost per meal, rounded to
0.005. ``FOOD_ENERGY`` holds the calibrated value (pre-run amendment P2).
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

from brain.systems.interoception import hunger as interoceptive_hunger
from core.body import BODY_PRESETS
from core.config import EngineConfig, MetabolismConfig
from core.engine import Engine
from core.world import WorldObject
from experiments.linear_track_replay import _dependency_versions, write_csv
from experiments.rq4a_gate import CUES
from metrics.manifest import build_manifest, finish_manifest, write_manifest

TICKS = 9000
PATCHES: Tuple[Tuple[float, float], ...] = ((5.0, 5.0), (-5.0, 5.0), (-5.0, -5.0), (5.0, -5.0))
PATCH_RADIUS = 0.75
REGROW = 600
SETPOINT = 0.8  # the analyst's hunger and deviation use interoception's setpoint and floor, sensed or not
HUNGER_FLOOR = 0.4
FOOD_ENERGY: Optional[float] = 0.065  # set by the calibration (pre-run amendment P2; docs/data/whole/resource/calibration)
PROVISIONAL_K = 0.075  # what the calibration runs with; the base's behaviour does not depend on it
BASAL = MetabolismConfig().basal_cost  # the cost the calibration's base would have paid a tick at rest
BASE: Dict[str, Any] = {"place.reward_step_cap": True}
PARTS: Dict[str, Dict[str, Any]] = {
    "interoception": {"interoception.enabled": True},
    "motivation": {"motivation.enabled": True, "motivation.hunger_source": "interoception", "motivation.vigour_floor": 1.0},
    "dopamine": {"neuromod.model": "biological", "neuromod.dopamine": True},
    "serotonin": {"neuromod.model": "biological", "neuromod.serotonin": True, "basal_ganglia.fiveht_patience_gain": 1.0},
    "noradrenaline": {"neuromod.model": "biological", "neuromod.noradrenaline": True, "basal_ganglia.ne_threat_gain": 0.5},
    "acetylcholine": {"neuromod.model": "biological", "neuromod.acetylcholine": True, "basal_ganglia.ach_precision_gain": 0.5},
    "sleep": {"sleep.enabled": True},
    "criticality": {"criticality.dynamic": True, "basal_ganglia.criticality_gain": 1.0, "basal_ganglia.criticality_scales_walls": True},
    "action_value": {"action_value.enabled": True, "action_value.history_features": True, "value_memory.source": "sr_action"},
    "replay": {"replay.sr_replay": True},
    "body": dict(BODY_PRESETS["rodent"]),
    "orienting": {"basal_ganglia.orient_gain": 1.0},
}
NO_MEMORY: Dict[str, Any] = {"basal_ganglia.value_gain": 0.0}
PHASES: Dict[str, Dict[str, Any]] = {
    "calibrate": {"seeds": (1001, 1002, 1003, 1004), "out": Path("docs/data/whole/resource/calibration")},
    "pilot": {"seeds": tuple(range(1, 13)), "out": Path("docs/data/whole/resource/pilot")},
}
QUICK_SEEDS = (1, 2)
QUICK_TICKS = 400
# The spark's bounds (§4) and the verdict's (§5)
SURVIVAL_MIN = 11
DEVIATION_MAX = 0.15
ACTIVITY_MIN = 0.3
STATE_SHARE_MIN = 0.05
STATE_SEEDS_MIN = 8
MEMORY_MARGIN = 1.25
BREAKS_MIN = 6
RUN_COLUMNS = ("config", "seed", "survived", "survival_ticks", "final_energy", "mean_dev_late", "low_share", "hungry_share",
               "sated_share", "moving_hungry", "moving_sated", "meals", "eaten", "spent", "spent_locomotion", "efficiency",
               "lost", "sleep_share", "sleep_bouts", "postprandial_rest", "replay_events", "mean_temperature", "mean_sensory_gain")


def merge(*dicts: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for d in dicts:
        out.update(d)
    return out


def whole() -> Dict[str, Any]:
    return merge(BASE, *PARTS.values())


def configurations() -> Dict[str, Dict[str, Any]]:
    """The 27 configurations of §5, name -> overrides on the research profile (the task's metabolism added by the run)."""
    configs: Dict[str, Dict[str, Any]] = {"base": dict(BASE), "whole": whole()}
    for name in PARTS:
        configs[f"whole-{name}"] = merge(BASE, *(ov for p, ov in PARTS.items() if p != name))
        if "neuromod.model" not in configs[f"whole-{name}"]:
            configs[f"whole-{name}"]["neuromod.model"] = "legacy"
    for name, ov in PARTS.items():
        configs[f"base+{name}"] = merge(BASE, ov)
    configs["whole_nomemory"] = merge(whole(), NO_MEMORY)
    return configs


def engine_config(overrides: Mapping[str, Any], food_energy: float, charge: bool = True) -> EngineConfig:
    cfg = EngineConfig.research()
    for key, value in {**overrides, "metabolism.enabled": True, "metabolism.food_energy": food_energy}.items():
        cfg.set_field(key, value)
    if not charge:  # calibration: nothing is charged, so the base cannot starve (its behaviour does not read E)
        cfg.metabolism.basal_cost = 0.0
    return cfg


def run_one(job: Tuple[str, Mapping[str, Any], int, int, float, bool]) -> Dict[str, Any]:
    """One run of the task; the per-run measures of §4 and a trace of E every 50 ticks."""
    return run_task(job)


def run_task(job: Tuple[str, Mapping[str, Any], int, int, float, bool], keep_series: bool = False) -> Dict[str, Any]:
    """``run_one``'s run; with ``keep_series`` the per-tick reserve, hunger, movement and sleep come back too (the
    disclosed checks in ``tools/whole_probes``; the pilot never asks for them)."""
    name, overrides, seed, ticks, food_energy, calibrate = job
    cfg = engine_config(overrides, food_energy, charge=not calibrate)
    eng = Engine(seed=seed, config=cfg)
    eng.world.cues.extend(CUES)
    patches = [WorldObject(x, y, PATCH_RADIUS, "target") for (x, y) in PATCHES]
    for p in patches:
        eng.world.add_object(p)
    regrow_at: Dict[int, int] = {}
    eng.run(1, reset=True)
    mc = cfg.metabolism
    would_cost = 0.0  # calibration: what the base would have paid
    energy: List[float] = []
    hunger_series: List[float] = []
    moving: List[bool] = []
    asleep: List[bool] = []
    meal_ticks: List[int] = []
    temps: List[float] = []
    gains: List[float] = []
    trace: List[Dict[str, Any]] = []
    survived, survival_ticks = True, ticks
    for t in range(ticks):
        if calibrate:
            would_cost += BASAL * (1.0 + mc.locomotion_factor * min(1.0, eng.speed_fraction()))
        td = eng.run(1)[0]
        ctx = eng.context
        if ctx.ingested_object is not None:
            ctx.ingested_object.kind = "collected"
            regrow_at[id(ctx.ingested_object)] = t + REGROW
            meal_ticks.append(t)
        for p in patches:
            due = regrow_at.get(id(p))
            if due is not None and t >= due:
                p.kind = "target"
                del regrow_at[id(p)]
        e, g = eng.metabolism.reserve, eng.metabolism.gut
        energy.append(e)
        hunger_series.append(interoceptive_hunger(e + g, SETPOINT, HUNGER_FLOOR))
        moving.append(td.action_name != "REST")
        asleep.append(ctx.asleep)
        temps.append(ctx.temperature)
        gains.append(ctx.criticality_gain)
        if t % 50 == 0:
            trace.append({"config": name, "seed": seed, "tick": t, "energy": round(e, 5), "gut": round(g, 5), "asleep": int(ctx.asleep)})
        if ctx.starved and not calibrate:
            survived, survival_ticks = False, t + 1
            break
    n = len(energy)
    late_from = ticks // 2
    late = [abs(x - SETPOINT) for x in energy[late_from:]] + [SETPOINT] * max(0, ticks - max(n, late_from))
    awake = [i for i in range(n) if not asleep[i]]
    hungry = [i for i in awake if hunger_series[i] >= 0.5]
    sated = [i for i in awake if hunger_series[i] <= 0.1]
    post = []
    for m in meal_ticks:
        window = [i for i in range(m + mc.consume_ticks, min(n, m + mc.consume_ticks + 150))]
        if window:
            post.append(sum(1 for i in window if not moving[i]) / len(window))
    met = eng.metabolism
    row = {
        "config": name, "seed": seed, "survived": survived, "survival_ticks": survival_ticks, "final_energy": round(energy[-1], 5),
        "mean_dev_late": statistics.mean(late) if late else SETPOINT,
        "low_share": (sum(1 for x in energy if x < 0.2) + (ticks - n)) / ticks,
        "hungry_share": len(hungry) / ticks, "sated_share": len(sated) / ticks,
        "moving_hungry": (sum(moving[i] for i in hungry) / len(hungry)) if hungry else float("nan"),
        "moving_sated": (sum(moving[i] for i in sated) / len(sated)) if sated else float("nan"),
        "meals": len(meal_ticks), "eaten": met.eaten, "spent": would_cost if calibrate else met.spent,
        "spent_locomotion": met.spent_locomotion,
        "efficiency": (met.eaten / met.spent_locomotion) if met.spent_locomotion > 0 else float("nan"),
        "lost": met.lost, "sleep_share": sum(asleep) / ticks, "sleep_bouts": eng.sleep.bouts if eng.sleep is not None else 0,
        "postprandial_rest": statistics.mean(post) if post else float("nan"),
        "replay_events": len(eng.replay_log), "mean_temperature": statistics.mean(temps), "mean_sensory_gain": statistics.mean(gains),
    }
    out: Dict[str, Any] = {"row": row, "trace": trace}
    if keep_series:
        out["series"] = {"energy": energy, "hunger": hunger_series, "moving": moving, "asleep": asleep, "meals": meal_ticks}
    return out


def _mean(values: Sequence[float]) -> float:
    vals = [v for v in values if not (isinstance(v, float) and math.isnan(v))]
    return statistics.mean(vals) if vals else float("nan")


def score(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """The spark's measures for one configuration's runs (§4)."""
    survived = sum(1 for r in rows if r["survived"])
    dev = _mean([r["mean_dev_late"] for r in rows])
    both = [r for r in rows if r["hungry_share"] >= STATE_SHARE_MIN and r["sated_share"] >= STATE_SHARE_MIN]
    activity = _mean([r["moving_hungry"] - r["moving_sated"] for r in both]) if both else float("nan")
    r1a, r1b = survived >= SURVIVAL_MIN, dev <= DEVIATION_MAX
    r2 = len(both) >= STATE_SEEDS_MIN and activity >= ACTIVITY_MIN
    return {"survived": survived, "mean_dev_late": dev, "activity_contrast": activity, "seeds_with_both_states": len(both),
            "R1a": r1a, "R1b": r1b, "R2": bool(r2), "spark": bool(r1a and r1b and r2),
            "efficiency": _mean([r["efficiency"] for r in rows]), "meals": _mean([r["meals"] for r in rows]),
            "sleep_share": _mean([r["sleep_share"] for r in rows]), "low_share": _mean([r["low_share"] for r in rows]),
            "postprandial_rest": _mean([r["postprandial_rest"] for r in rows])}


def verdict(scores: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """The emergence verdict (§5) and the synergy on the homeostasis score."""
    whole_spark = scores["whole"]["spark"]
    singles = {p: scores[f"base+{p}"]["spark"] for p in PARTS}
    breaks = {p: not scores[f"whole-{p}"]["spark"] for p in PARTS}
    base_dev = scores["base"]["mean_dev_late"]
    gains = {p: base_dev - scores[f"base+{p}"]["mean_dev_late"] for p in PARTS}
    r3 = (scores["whole"]["efficiency"] >= MEMORY_MARGIN * scores["whole_nomemory"]["efficiency"]
          and scores["whole"]["survived"] >= scores["whole_nomemory"]["survived"])
    return {"1_whole_shows_the_spark": whole_spark, "2_no_single_addition_shows_it": not any(singles.values()),
            "3_most_removals_break_it": sum(breaks.values()) >= BREAKS_MIN, "removals_that_break_it": [p for p, b in breaks.items() if b],
            "single_additions_that_show_it": [p for p, s in singles.items() if s], "R3_memory_margin": bool(r3),
            "synergy": {"whole_gain": base_dev - scores["whole"]["mean_dev_late"], "sum_of_single_gains": sum(gains.values()),
                        "single_gains": gains}}


def _pool(jobs, workers):
    if workers == 1:
        return [run_one(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_one, jobs, chunksize=1))


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
    calibrate = args.phase == "calibrate"
    if calibrate:
        configs, k = {"base": dict(BASE)}, PROVISIONAL_K
    else:
        if FOOD_ENERGY is None and not args.quick:
            parser.error("the food's energy is not calibrated yet: run --phase calibrate and record K (amendment P2)")
        configs, k = configurations(), (FOOD_ENERGY if FOOD_ENERGY is not None else PROVISIONAL_K)
    started = time.perf_counter()
    results = _pool([(c, ov, s, ticks, k, calibrate) for c, ov in configs.items() for s in seeds], args.workers)
    rows = [r["row"] for r in results]
    traces = [t for r in results for t in r["trace"]]
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "runs.csv", RUN_COLUMNS, rows)
    write_csv(out / "energy_trace.csv", ("config", "seed", "tick", "energy", "gut", "asleep"), traces)
    summary: Dict[str, Any] = {"phase": args.phase, "seeds": list(seeds), "ticks": ticks, "food_energy": k, "quick": args.quick,
                               "configs": configs}
    if calibrate:
        spent, meals = sum(r["spent"] for r in rows), sum(r["meals"] for r in rows)
        summary["calibration"] = {"would_have_spent": spent, "meals": meals, "cost_per_meal": spent / meals if meals else None,
                                  "K": round(round((spent / meals) / 0.005) * 0.005, 3) if meals else None}
        print(f"calibration: the base would have spent {spent:.4f} over {meals} meals on {len(seeds)} seeds -> "
              f"cost per meal {summary['calibration']['cost_per_meal']}; K = {summary['calibration']['K']}")
    else:
        scores = {c: score([r for r in rows if r["config"] == c]) for c in configs}
        summary["scores"] = scores
        summary["verdict"] = verdict(scores)
        print(f"{'config':24s} surv  dev_late  activity(n)  spark  meals   eff  sleep  low")
        for c, s in scores.items():
            print(f"{c:24s} {s['survived']:4d}  {s['mean_dev_late']:8.3f}  {s['activity_contrast']:7.3f}({s['seeds_with_both_states']:2d})  "
                  f"{'yes' if s['spark'] else 'no ':5s} {s['meals']:5.1f} {s['efficiency']:5.2f}  {s['sleep_share']:.2f}  {s['low_share']:.2f}")
        print(json.dumps(summary["verdict"], indent=1, default=str))
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str))
    manifest = build_manifest(engine_config(BASE, k, charge=not calibrate), protocol=f"whole_resource:{args.phase}", seeds=list(seeds),
                              ticks_requested=ticks, extra={"configs": configs, "phase": args.phase, "quick": args.quick,
                                                            "prereg": "docs/prereg/whole_resource.md (draft)", "food_energy": k,
                                                            "dependencies": _dependency_versions(),
                                                            "command": "python3 -m experiments.whole_resource " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    finish_manifest(manifest, ticks_run=sum(r["survival_ticks"] for r in rows), wall_seconds=time.perf_counter() - started)
    write_manifest(out / "manifest.json", manifest)
    print(f"wrote {out} in {time.perf_counter() - started:.1f} s")
    return summary


if __name__ == "__main__":
    main()
