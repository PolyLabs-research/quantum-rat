"""The headline replay advantage is a single deterministic sample on a knife edge.

Claims (value-replay audit, 2026-10-03):

* ``run_memory_navigation`` (one visible trial, optional 60-pass consolidation,
  hidden probes) at the default goal (6, 3): replay 9 / 13 / 17 / 17 ticks
  (visible, then three hidden probes) vs no-replay 9 / 14 / 15 / 13, so the
  1-tick first-probe advantage reverses on later probes.
* After one 9-tick visible trial plus consolidation the map holds 87 cells
  with V > 1e-3 and max V = 2.125 for a single reward of 1.0 (kernel
  inflation, radius 2); without consolidation 25 cells and max V = 0.2.
"""

from __future__ import annotations

from core.engine import Engine
from core.world import WorldObject
from experiments.memory_navigation import (
    DEFAULT_GOAL,
    DEFAULT_GOAL_RADIUS,
    _run_trial,
    memory_nav_config,
    run_memory_navigation,
)
from tools.probes._common import Results, budget, probe_main


def run(scale: float = 1.0) -> Results:
    max_ticks = budget(200, scale, 20)
    n_recall = 3 if scale >= 0.5 else 1
    passes = budget(60, scale, 3)
    out: Results = {
        "config": f"experiments.memory_navigation defaults: seed 1337, goal {DEFAULT_GOAL} r {DEFAULT_GOAL_RADIUS}, "
        f"radius-2 kernel, approach_weight 0, max_ticks {max_ticks}, {passes} consolidation passes, "
        f"1 visible trial + {n_recall} hidden probes",
    }
    for replay in (True, False):
        rows = run_memory_navigation(replay, n_recall=n_recall, max_ticks=max_ticks, consolidation_passes=passes)
        out[f"ticks_to_goal_{'replay' if replay else 'no_replay'}"] = [r.ticks_to_goal for r in rows]
        out[f"reached_{'replay' if replay else 'no_replay'}"] = [r.reached for r in rows]

    for replay in (True, False):
        cfg = memory_nav_config()
        eng = Engine(seed=1337, config=cfg)
        eng.world.add_object(WorldObject(DEFAULT_GOAL[0], DEFAULT_GOAL[1], DEFAULT_GOAL_RADIUS, "target"))
        visible_ticks = _run_trial(eng, DEFAULT_GOAL, DEFAULT_GOAL_RADIUS, max_ticks)
        if replay:
            eng.value_memory.consolidate(passes=passes, dwell_extinction=cfg.value_memory.dwell_extinction)
        vals = eng.value_memory.values
        tag = "after_consolidation" if replay else "online_only"
        out[f"map_{tag}"] = {
            "visible_trial_ticks": visible_ticks,
            "trajectory_entries": len(eng.value_memory.trajectory),
            "cells_V_gt_1e-3": sum(1 for v in vals.values() if v > 1e-3),
            "max_V": max(vals.values()) if vals else 0.0,
            "goal_cell": eng.value_memory.goal_cell,
        }
    return out


main = probe_main(run, "memory-navigation replay advantage (knife edge)")

if __name__ == "__main__":
    main()
