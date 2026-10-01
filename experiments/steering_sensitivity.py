"""How sensitive is behaviour to memory steering (``basal_ganglia.value_gain``)?

Runs the lab-console scenarios headless across a grid of ``value_gain`` values
and seeds, and reports each scenario's task score. A robust memory system should
give good scores over a broad band of gains, with one default that works for all
scenarios; a brittle one swings between success and failure as the gain moves.

Sensor noise (default 0.03) makes each seed a genuinely different run, so the
numbers are distributions rather than one chaotic trajectory.

    python -m experiments.steering_sensitivity                 # default grid
    python -m experiments.steering_sensitivity --gains 0,0.4,0.8,1.5 --seeds 4
    python -m experiments.steering_sensitivity --set value_memory.generalization_radius=2

Metrics (higher is better unless noted):
  beacon        beacons reached in the tick budget
  foraging      food items collected
  hazard_field  food items collected (hazard contacts reported too)
  memory_maze   hidden-goal recalls (reached / attempted) and median recall ticks
"""

from __future__ import annotations

import argparse
import json
import statistics
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.engine import Engine
from ui.scenarios import make_scenario

SCENARIOS = ("beacon", "foraging", "hazard_field", "memory_maze")
DEFAULT_GAINS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0)
TICKS = {"beacon": 3000, "foraging": 3000, "hazard_field": 3000, "memory_maze": 1500}


@dataclass(frozen=True)
class Job:
    scenario: str
    value_gain: Optional[float]  # None = the scenario's own default
    seed: int
    noise: float
    ticks: int
    overrides: Tuple[Tuple[str, Any], ...] = ()


def _set(config: Any, key: str, value: Any) -> None:
    obj = config
    parts = key.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    if not hasattr(obj, parts[-1]):
        raise AttributeError(f"config has no field {key!r}")
    setattr(obj, parts[-1], value)


def run_job(job: Job) -> Dict[str, Any]:
    scenario = make_scenario(job.scenario)
    config = scenario.config()
    config.sensors.noise = job.noise
    for key, value in job.overrides:
        _set(config, key, value)
    if job.value_gain is not None:
        config.basal_ganglia.value_gain = job.value_gain
    engine = Engine(seed=job.seed, config=config)
    scenario.setup(engine)
    for _ in range(job.ticks):
        td = engine.run(1)[0]
        scenario.on_tick(engine, td.tick)

    out: Dict[str, Any] = {
        "scenario": job.scenario,
        "value_gain": config.basal_ganglia.value_gain,
        "seed": job.seed,
    }
    if job.scenario == "beacon":
        out["score"] = scenario.visits
    elif job.scenario == "foraging":
        out["score"] = scenario.collected
    elif job.scenario == "hazard_field":
        out["score"] = scenario.collected
        out["hazard_contacts"] = scenario.hurts
    elif job.scenario == "memory_maze":
        hidden = [t for t in scenario.history if not t["visible"]]
        reached = [t["ticks"] for t in hidden if t["reached"]]
        out["score"] = len(reached)
        out["attempted"] = len(hidden)
        out["recall_rate"] = len(reached) / len(hidden) if hidden else 0.0
        out["median_recall_ticks"] = statistics.median(reached) if reached else None
    return out


def sweep(
    scenarios: Sequence[str] = SCENARIOS,
    gains: Sequence[Optional[float]] = DEFAULT_GAINS,
    seeds: Sequence[int] = (1, 2, 3, 4),
    noise: float = 0.03,
    overrides: Dict[str, Any] | None = None,
    ticks: Dict[str, int] | None = None,
    workers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    over = tuple(sorted((overrides or {}).items()))
    budget = {**TICKS, **(ticks or {})}
    jobs = [Job(s, g, seed, noise, budget[s], over) for s in scenarios for g in gains for seed in seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_job, jobs, chunksize=1))


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Dict[float, Dict[str, float]]]:
    """scenario -> gain -> {mean, min, max, (recall_rate)}."""
    table: Dict[str, Dict[float, Dict[str, float]]] = {}
    for row in rows:
        cell = table.setdefault(row["scenario"], {}).setdefault(row["value_gain"], {"scores": [], "rates": []})
        cell["scores"].append(row["score"])
        if "recall_rate" in row:
            cell["rates"].append(row["recall_rate"])
    out: Dict[str, Dict[float, Dict[str, float]]] = {}
    for scen, by_gain in table.items():
        out[scen] = {}
        for gain, cell in sorted(by_gain.items()):
            s = cell["scores"]
            entry = {"mean": statistics.mean(s), "min": min(s), "max": max(s)}
            if cell["rates"]:
                entry["recall_rate"] = statistics.mean(cell["rates"])
            out[scen][gain] = entry
    return out


def robustness(summary: Dict[str, Dict[float, Dict[str, float]]], fraction: float = 0.8) -> Dict[str, Dict[str, Any]]:
    """Per scenario: best mean, and the gains whose mean is within ``fraction`` of the best."""
    result = {}
    for scen, by_gain in summary.items():
        best = max(v["mean"] for v in by_gain.values())
        good = [g for g, v in by_gain.items() if best > 0 and v["mean"] >= fraction * best]
        result[scen] = {"best_mean": best, "good_gains": good, "n_gains": len(by_gain)}
    return result


def _parse_value(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", default=",".join(SCENARIOS))
    parser.add_argument("--gains", default=",".join(str(g) for g in DEFAULT_GAINS),
                        help="comma-separated value_gain grid; 'default' = each scenario's own")
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--noise", type=float, default=0.03)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="config override applied to every run, e.g. value_memory.lookahead=1.5")
    parser.add_argument("--json", action="store_true", help="print raw rows as JSON")
    args = parser.parse_args()

    gains: List[Optional[float]] = [None if g == "default" else float(g) for g in args.gains.split(",")]
    overrides = {}
    for item in args.set:
        key, _, value = item.partition("=")
        overrides[key] = _parse_value(value)
    rows = sweep(args.scenarios.split(","), gains, range(1, args.seeds + 1), args.noise, overrides)
    if args.json:
        print(json.dumps(rows, indent=1))
        return
    summary = summarise(rows)
    for scen, by_gain in summary.items():
        print(f"\n{scen}")
        for gain, v in by_gain.items():
            extra = f"  recall {v['recall_rate']:.0%}" if "recall_rate" in v else ""
            print(f"  value_gain {gain:4.2f}: mean {v['mean']:6.1f}  (min {v['min']}, max {v['max']}){extra}")
    print("\nrobust band (>= 80% of best mean):")
    for scen, r in robustness(summary).items():
        print(f"  {scen:13s} best {r['best_mean']:.1f}; good at {r['good_gains']}")


if __name__ == "__main__":
    main()
