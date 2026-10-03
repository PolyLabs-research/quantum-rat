"""Engine throughput: the only non-deterministic probe (wall-clock, this machine).

Claims (completeness, judge and critic, 2026-10-03): the default barren
engine runs at ~8,000-8,900 ticks/s in pure Python 3.11 on one core; the
console scenarios with objects, memory steering and noise 0.03 run at
~5,000-7,000 ticks/s (beacon, hidden_food, memory_maze). Any program that
adds numpy populations must restate this number.

Only the tick counts are deterministic; ticks/s depends on the machine and
is recorded in README.md as indicative.
"""

from __future__ import annotations

import time

from core.engine import Engine
from tools.probes._common import Results, budget, probe_main

SCENARIOS = ("beacon", "hidden_food", "memory_maze")


def run(scale: float = 1.0) -> Results:
    n = budget(3000, scale, 100)
    out: Results = {"config": f"{n} ticks per run; wall-clock, single process, this machine", "ticks_per_run": n}
    eng = Engine(seed=1)
    t0 = time.perf_counter()
    eng.run(n, reset=True)
    dt = time.perf_counter() - t0
    out["default_engine_ticks_per_s"] = round(n / dt)
    try:
        from ui.scenarios import make_scenario
    except Exception as exc:  # pragma: no cover - the console is optional for this probe
        out["scenarios"] = f"ui.scenarios unavailable: {exc}"
        return out
    for name in SCENARIOS:
        sc = make_scenario(name)
        cfg = sc.config()
        cfg.sensors.noise = 0.03
        eng = Engine(seed=3, config=cfg)
        sc.setup(eng)
        t0 = time.perf_counter()
        for i in range(n):
            td = eng.run(1)[0]
            sc.on_tick(eng, td.tick)
        dt = time.perf_counter() - t0
        out[f"{name}_ticks_per_s"] = round(n / dt)
    return out


main = probe_main(run, "engine throughput (machine-dependent)")

if __name__ == "__main__":
    main()
