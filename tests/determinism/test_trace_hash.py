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


def test_research_profile_trace_hash_matches_its_baseline() -> None:
    """The second baseline: EngineConfig.research() at the gate's seed and tick count.

    Regenerate with ``python -m tools.update_determinism_baseline --profile research
    --i-know-what-im-doing`` (once per milestone, docs/profiles.md).
    """
    from tools.update_determinism_baseline import build_profile_trace, load_profile_baseline

    baseline = load_profile_baseline("research")
    current = build_profile_trace("research")
    assert current == baseline, "Determinism regression: research-profile trace hash differs from its baseline"
