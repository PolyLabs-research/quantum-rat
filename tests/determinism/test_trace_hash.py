from __future__ import annotations

from core.determinism import (
    BASELINE_PATH,
    DEFAULT_SEED,
    DEFAULT_TICKS,
    build_current_trace,
    load_baseline,
)

# Re-exported so existing ``from tests.determinism.test_trace_hash import ...``
# call sites keep working; the canonical home is ``core.determinism``.
__all__ = [
    "BASELINE_PATH",
    "DEFAULT_SEED",
    "DEFAULT_TICKS",
    "build_current_trace",
    "load_baseline",
]


def test_trace_hash_matches_baseline() -> None:
    baseline = load_baseline()
    current = build_current_trace()
    assert current == baseline, "Determinism regression: trace hash differs from baseline"
