"""What microsleep replay actually replays at engine defaults.

Claim (value-replay and sleep-energy audits, citing docs/decisions.md G17):
because the TRN gate multiplies egomotion into path integration and closes
(ATP < 0.35) some 25-50 ticks before a microsleep starts, the place estimate
is frozen while the body still moves. The 50-transition snapshot taken at
sleep onset is therefore almost entirely same-cell transitions (G17: median
98%, range 94-100%, at noise 0.03 over seeds 1-4), and the body moved a median
2.7 m (up to 5.9 m) during the frozen window before onset while the estimate
stayed in the sleep-onset cell. Microsleep replay mostly re-applies TD and
dwell extinction to the one cell the agent "fell asleep in".

The snapshot is read from ``Engine._replay_plan`` right after the first sleep
tick (a private attribute, read only). The frozen window is the run of ticks
before onset whose place bin equals the onset bin.
"""

from __future__ import annotations

import math
from typing import Dict, List

from core.engine import Engine
from tools.probes._common import Results, budget, mean, median, noisy_config, probe_main


def measure(seed: int, ticks: int, noise: float) -> Dict[str, object]:
    eng = Engine(seed=seed, config=noisy_config(noise))
    same_fracs: List[float] = []
    spans: List[int] = []
    frozen_moved: List[float] = []
    frozen_ticks: List[int] = []
    closed_before: List[int] = []
    trace = []
    asleep = False
    awake_closed_streak = 0
    for i in range(ticks):
        td = eng.run(1, reset=(i == 0))[0]
        trace.append(td)
        if td.microsleep_active and not asleep:
            plan = getattr(eng, "_replay_plan", None) or []
            if plan:
                same_fracs.append(sum(1 for f, t, _ in plan if f == t) / len(plan))
                spans.append(len(plan))
            closed_before.append(awake_closed_streak)
            # Frozen window: ticks before onset whose place bin equals the onset bin.
            onset_bin = eng.spatial.bins_at(td.grid_x, td.grid_y)
            j = i
            while j > 0 and eng.spatial.bins_at(trace[j - 1].grid_x, trace[j - 1].grid_y) == onset_bin:
                j -= 1
            frozen_ticks.append(i - j)
            frozen_moved.append(math.hypot(td.pos[0] - trace[j].pos[0], td.pos[1] - trace[j].pos[1]))
        asleep = td.microsleep_active
        if not asleep:
            awake_closed_streak = awake_closed_streak + 1 if td.trn_state == "CLOSED" else 0
    return {
        "sleeps_with_a_snapshot": len(same_fracs),
        "snapshot_span_min_max": [min(spans), max(spans)] if spans else None,
        "same_cell_fraction_median": median(same_fracs),
        "same_cell_fraction_min_max": [min(same_fracs), max(same_fracs)] if same_fracs else None,
        "awake_ticks_gate_CLOSED_before_onset_median": median(closed_before),
        "frozen_window_ticks_median": median(frozen_ticks),
        "body_displacement_in_frozen_window_m_median": median(frozen_moved),
        "body_displacement_in_frozen_window_m_max": max(frozen_moved) if frozen_moved else None,
    }


def run(scale: float = 1.0) -> Results:
    ticks = budget(3000, scale, 300)
    out: Results = {"config": f"EngineConfig() defaults (pacing off), barren world, {ticks} ticks", "ticks": ticks}
    out["noise0_seed1"] = measure(1, ticks, 0.0)
    rows = [measure(s, ticks, 0.03) for s in (1, 2, 3, 4)]
    out["noise0.03_seeds1-4_pooled"] = {
        "sleeps": sum(r["sleeps_with_a_snapshot"] for r in rows),
        "same_cell_fraction_median_of_seed_medians": median([r["same_cell_fraction_median"] for r in rows]),
        "same_cell_fraction_min": min(r["same_cell_fraction_min_max"][0] for r in rows if r["same_cell_fraction_min_max"]),
        "body_displacement_in_frozen_window_m_median_of_seed_medians": median(
            [r["body_displacement_in_frozen_window_m_median"] for r in rows]
        ),
        "body_displacement_in_frozen_window_m_max": max(
            r["body_displacement_in_frozen_window_m_max"] for r in rows if r["body_displacement_in_frozen_window_m_max"] is not None
        ),
        "frozen_window_ticks_mean_of_seed_medians": mean([r["frozen_window_ticks_median"] for r in rows]),
    }
    return out


main = probe_main(run, "microsleep replay content at engine defaults")

if __name__ == "__main__":
    main()
