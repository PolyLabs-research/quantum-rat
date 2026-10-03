"""The generalization kernel makes the value map bootstrap on itself.

Claim (value-replay audit, 2026-10-03): ``ValueMemory._td_update`` writes the
centre cell's bootstrap target into its Chebyshev neighbourhood with weight
``falloff^(|dx|+|dy|)``, so with ``generalization_radius > 0`` the goal cell is
pulled toward ``r + gamma * V(goal)`` through its own kernel. On a 12-cell
chain with one terminal reward of 1.0 (alpha 0.2, gamma 0.9):

* radius 0 converges to V(d) = gamma^d, V(goal-1) = 1.0 (correct);
* radius 2 (the maze and hidden-food setting) gives V(goal-1) ~ 4.27 after the
  standard 60 passes and ~6.07 at convergence;
* radius 1 converges to V = 10.0 = r / (1 - gamma).

V is therefore not an expected discounted return; its scale depends on the
radius, the pass count and the path geometry.
"""

from __future__ import annotations

from brain.systems.value_memory import ValueMemory
from tools.probes._common import Results, budget, probe_main

CHAIN = 12
PASSES = (60, 200, 1000, 5000)


def chain(radius: int, passes: int) -> ValueMemory:
    vm = ValueMemory(learning_rate=0.2, discount=0.9, generalization_radius=radius)
    for i in range(CHAIN):
        vm.record((i, 0), 1.0 if i == CHAIN - 1 else 0.0)
    vm.consolidate(passes=passes)
    return vm


def run(scale: float = 1.0) -> Results:
    passes = [budget(p, scale, 2) for p in PASSES]
    out: Results = {
        "config": f"ValueMemory(lr 0.2, gamma 0.9), {CHAIN}-cell straight chain, reward 1.0 on arrival at the last cell, "
        f"consolidate(passes) for passes in {passes}",
        "analytic_gamma_d_radius0": [round(0.9 ** (CHAIN - 2 - i), 4) for i in range(CHAIN - 1)] + [0.0],
    }
    for radius in (0, 1, 2):
        rows = {}
        for p in passes:
            vm = chain(radius, p)
            rows[f"passes{p}"] = {
                "V_goal_minus_1": vm.value_of((CHAIN - 2, 0)),
                "V_goal": vm.value_of((CHAIN - 1, 0)),
                "V_start": vm.value_of((0, 0)),
                "max_V": max(vm.values.values()),
            }
        out[f"radius{radius}"] = rows
    vm2 = chain(2, passes[0])
    out[f"radius2_passes{passes[0]}_values_along_chain"] = [round(vm2.value_of((i, 0)), 3) for i in range(CHAIN)]
    out[f"radius2_passes{passes[0]}_values_two_cells_off_chain"] = [round(vm2.value_of((i, 2)), 3) for i in range(CHAIN)]
    out["r_over_1_minus_gamma"] = 1.0 / (1.0 - 0.9)
    return out


main = probe_main(run, "kernel value inflation on a 12-cell chain")

if __name__ == "__main__":
    main()
