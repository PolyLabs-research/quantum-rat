"""Guard: the criticality active-site count must actually be logged.

It is computed every tick by ``CriticalityField`` but was previously dropped
on the floor in ``Engine._log_tick``, so it sat at its default 0 in every
trace and in all downstream analysis. This test fails if that regresses.
"""

from core.determinism import generate_trace


def test_criticality_active_is_logged_and_non_constant():
    trace = generate_trace(seed=1337, ticks=200)
    actives = [t.criticality_active for t in trace]
    assert any(a > 0 for a in actives), "criticality_active is never populated (stuck at 0)"
    assert len(set(actives)) > 1, "criticality_active is constant across the trace; logging regressed"
