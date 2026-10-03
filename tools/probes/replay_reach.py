"""How far back along a trajectory 60 reverse passes carry a usable gradient.

Claims (value-replay audit, 2026-10-03):

* Gradient reach is limited by gamma 0.9, alpha 0.2, 60 passes, capacity 200
  and the 1e-3 flatness threshold: after a 300-step trial only the last ~26
  cells carry V > 1e-3 (the steering threshold) and only the last 200 steps
  are stored at all (the first cell with any value is step 100).
* Reward-on-arrival leaves the goal cell itself at V = 0 at radius 0 (nothing
  is recorded after the terminal step): a value hole at the goal.
* Dwell extinction erases a self-made 0.5 peak to 0 in 60 passes with the
  0.02 charge, and so does plain replay of same-cell zero-reward transitions
  without it.
"""

from __future__ import annotations

from brain.systems.value_memory import ValueMemory
from tools.probes._common import Results, budget, probe_main

STEER_THRESHOLD = 1e-3


def run(scale: float = 1.0) -> Results:
    steps = budget(300, scale, 30)
    passes = budget(60, scale, 3)
    capacity = 200
    out: Results = {
        "config": f"ValueMemory(lr 0.2, gamma 0.9, capacity {capacity}, radius 0); straight {steps}-step trajectory, "
        f"reward 1.0 at the last step, consolidate(passes={passes})",
    }
    vm = ValueMemory(learning_rate=0.2, discount=0.9, capacity=capacity)
    for i in range(steps):
        vm.record((i, 0), 1.0 if i == steps - 1 else 0.0)
    vm.consolidate(passes=passes)
    vals = [vm.value_of((i, 0)) for i in range(steps)]
    out["trajectory_steps"] = steps
    out["stored_entries"] = len(vm.trajectory)
    out["first_step_with_any_value"] = next((i for i, v in enumerate(vals) if v > 0), None)
    out["first_step_with_V_above_steer_threshold"] = next((i for i, v in enumerate(vals) if v > STEER_THRESHOLD), None)
    out["steps_with_V_above_steer_threshold"] = sum(1 for v in vals if v > STEER_THRESHOLD)
    out["V_goal_minus_1"] = vals[-2]
    out["V_goal_cell_radius0"] = vals[-1]

    # Dwell extinction on a self-made peak.
    for charge in (0.02, 0.0):
        vm = ValueMemory(learning_rate=0.2, discount=0.9)
        for _ in range(10):
            vm.record((0, 0), 0.0)
        vm.values[(0, 0)] = 0.5
        vm.consolidate(passes=passes, dwell_extinction=charge)
        out[f"dwell_peak_0.5_after_{passes}_passes_charge_{charge}"] = vm.value_of((0, 0))
    return out


main = probe_main(run, "reach of reverse replay along a long trajectory")

if __name__ == "__main__":
    main()
