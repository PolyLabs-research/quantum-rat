"""Glycogen is a pass-through, not a store.

Claim (sleep-energy audit, 2026-10-03): glycogen is exhausted within ~150
ticks of exploring and then pinned at exactly 0.03 (= glycogen_regen, the
per-tick regeneration that is immediately transferred to ATP) for the rest of
the run (mean ~0.10 over 3000 ticks). From then on the two-compartment energy
model collapses to a single linear tank, and the console's glycogen panel
displays a constant.
"""

from __future__ import annotations

from core.config import AstrocyteConfig
from tools.probes._common import Results, budget, mean, probe_main, run_engine


def run(scale: float = 1.0) -> Results:
    ticks = budget(3000, scale, 200)
    regen = AstrocyteConfig().glycogen_regen
    trace, _ = run_engine(1, ticks)
    g = [td.glycogen for td in trace]
    pinned = [abs(x - regen) < 1e-12 for x in g]
    first = next((i for i, p in enumerate(pinned) if p), None)
    out: Results = {
        "config": f"seed 1, EngineConfig() defaults (pacing off), barren world, {ticks} ticks",
        "glycogen_regen": regen,
        "glycogen_initial": g[0],
        "glycogen_min_max_mean": [min(g), max(g), mean(g)],
        "first_tick_glycogen_pinned_at_regen": first,
        "frac_ticks_pinned_after_first": (sum(pinned[first:]) / len(pinned[first:])) if first is not None else 0.0,
        "ticks_glycogen_above_0_1_after_first": sum(1 for x in g[first:] if x > 0.1) if first is not None else None,
    }
    return out


main = probe_main(run, "glycogen pinning at the per-tick regeneration")

if __name__ == "__main__":
    main()
