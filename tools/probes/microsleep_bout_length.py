"""Every microsleep lasts exactly 25 ticks: the recovery rule is dead.

Claim (sleep-energy audit, 2026-10-03): a microsleep ends early when ATP >
0.45 for 5 consecutive ticks, but during sleep demand is 0.2 so ATP rises only
0.007/tick from ~0.275 and reaches 0.45 on about the 25th tick; every one of
the 51 bouts in 3000 ticks lasted the full ``trn.duration`` of 25 ticks. Bout
length is a constant, not a function of anything.
"""

from __future__ import annotations

from core.config import AstrocyteConfig, TRNConfig
from tools.probes._common import Results, budget, mean, median, microsleep_bouts, probe_main, run_engine


def run(scale: float = 1.0) -> Results:
    ticks = budget(3000, scale, 300)
    trn = TRNConfig()
    a = AstrocyteConfig()
    trace, _ = run_engine(1, ticks)
    bouts, gaps = microsleep_bouts(trace)
    onset_atp, end_atp, early = [], [], 0
    asleep = False
    for i, td in enumerate(trace):
        if asleep and not td.microsleep_active:
            end_atp.append(trace[i - 1].atp)
            if trace[i - 1].microsleep_ticks_remaining > 1:
                early += 1  # ended by the recovery rule, not the countdown
        if td.microsleep_active and not asleep and any(not t.microsleep_active for t in trace[i:]):
            onset_atp.append(td.atp)  # onsets of bouts that complete within the run
        asleep = td.microsleep_active
    out: Results = {
        "config": f"seed 1, EngineConfig() defaults (pacing off), barren world, {ticks} ticks; "
        f"TRNConfig duration {trn.duration}, recovery_atp {trn.recovery_atp} for {trn.recovery_streak_needed} ticks",
        "atp_rise_per_sleep_tick": a.glycogen_regen * a.glycogen_to_atp_yield - a.atp_cost * a.rest_demand,
        "complete_bouts": len(bouts),
        "run_ended_during_a_bout": bool(trace[-1].microsleep_active),
        "distinct_bout_lengths": sorted(set(bouts)),
        "bouts_ended_early_by_recovery_rule": early,
        "atp_at_onset_mean": mean(onset_atp),
        "atp_at_last_sleep_tick_mean": mean(end_atp),
        "awake_gap_median_min": [median(gaps), min(gaps)] if gaps else None,
    }
    return out


main = probe_main(run, "microsleep bout length at engine defaults")

if __name__ == "__main__":
    main()
