"""The whole's pilot re-read tick by tick (disclosed check behind G56's reading; the pilot's seeds; post hoc, not a test).

    .venv/bin/python -m tools.whole_probes.need_activity --workers 28    # writes need_activity_out.txt and .csv beside this

The preregistered R2 compared movement when hungry (h >= 0.5) with movement when sated (h <= 0.1) and needed at least
5% of ticks in each state on 8 seeds; the whole regulated its energy inside that band and was almost never "hungry",
so R2 could not be scored. This re-runs every pilot configuration (same code, seeds and K: the runs are the pilot's,
checked meal for meal against its runs.csv) keeping the per-tick series, and reports, per configuration:

- the spread of the reserve over the run's second half (its standard deviation: how tightly it is held);
- the **within-run hunger contrast**: on awake ticks, the share moving in the hungriest third of the run's ticks less
  the share in the most sated third (terciles of the run's own hunger, so it exists whatever band the agent holds);
- the rest after meals (the share of the 150 ticks after each meal's pause spent still) and the sleep share.

None of these bounds were registered; the values are reported, not passed or failed.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads

from experiments import whole_resource as wr

HERE = Path(__file__).parent
PILOT = Path("docs/data/whole/resource/pilot/runs.csv")


def tercile_contrast(hunger: List[float], moving: List[bool], asleep: List[bool]) -> float:
    awake = sorted((h, m) for h, m, a in zip(hunger, moving, asleep) if not a)
    if len(awake) < 30:
        return float("nan")
    third = len(awake) // 3
    low, high = awake[:third], awake[-third:]
    return sum(m for _, m in high) / len(high) - sum(m for _, m in low) / len(low)


def one(job) -> Dict[str, Any]:
    res = wr.run_task(job, keep_series=True)
    s, row = res["series"], res["row"]
    late = s["energy"][len(s["energy"]) // 2:]
    return {"config": row["config"], "seed": row["seed"], "meals": row["meals"], "survived": row["survived"],
            "energy_mean_late": statistics.mean(late) if late else 0.0,
            "energy_sd_late": statistics.pstdev(late) if len(late) > 1 else 0.0,
            "hunger_contrast": tercile_contrast(s["hunger"], s["moving"], s["asleep"]),
            "postprandial_rest": row["postprandial_rest"], "sleep_share": row["sleep_share"], "efficiency": row["efficiency"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    configs = wr.configurations()
    jobs = [(c, ov, s, wr.TICKS, wr.FOOD_ENERGY, False) for c, ov in configs.items() for s in wr.PHASES["pilot"]["seeds"]]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(one, jobs, chunksize=1))
    with open(PILOT, newline="") as f:
        pilot = {(r["config"], int(r["seed"])): int(r["meals"]) for r in csv.DictReader(f)}
    mismatched = [(r["config"], r["seed"]) for r in rows if pilot.get((r["config"], r["seed"])) != r["meals"]]
    with open(HERE / "need_activity_out.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = [f"runs identical to the pilot's (meals, run by run): {not mismatched} ({len(rows)} runs; mismatched: {mismatched[:5]})",
             f"{'config':22s} {'surv':>4s} {'E late':>7s} {'E sd':>6s} {'hunger contrast':>16s} {'rest after meals':>17s} {'sleep':>6s} {'eff':>6s}"]
    for c in configs:
        rr = [r for r in rows if r["config"] == c]
        mean = lambda k: statistics.mean(r[k] for r in rr if r[k] == r[k])  # noqa: E731 (skips nan)
        lines.append(f"{c:22s} {sum(r['survived'] for r in rr):4d} {mean('energy_mean_late'):7.3f} {mean('energy_sd_late'):6.3f} "
                     f"{mean('hunger_contrast'):16.3f} {mean('postprandial_rest'):17.3f} {mean('sleep_share'):6.3f} {mean('efficiency'):6.2f}")
    text = "\n".join(lines) + "\n"
    (HERE / "need_activity_out.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
