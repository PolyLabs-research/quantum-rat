"""The split baselines (docs/determinism.md): behaviour and physics hashes, both profiles.

Exact-hash gates, like ``test_trace_hash.py``: they state same-platform bit
identity (marked ``exact_hash``, so the macOS CI job deselects them,
``.github/workflows/ci.yml``); the cross-platform claim is the tolerance gate in
``test_cross_platform_tolerance.py``. Regenerate the research baselines with
``python3 tools/update_determinism_baseline.py --profile research --i-know-what-im-doing``;
the legacy set is never re-recorded (docs/determinism.md).
"""

from __future__ import annotations

import pytest

from core.config import EngineConfig
from core.determinism import (
    DEFAULT_SEED,
    DEFAULT_TICKS,
    HASH_KINDS,
    PROFILE_NAMES,
    generate_profile_trace,
    hash_trace,
    load_baseline,
)
from core.engine import Engine

pytestmark = pytest.mark.exact_hash  # same-platform bit identity (pytest.ini, docs/determinism.md)


@pytest.mark.parametrize("profile", PROFILE_NAMES)
@pytest.mark.parametrize("kind", ("behaviour", "physics"))
def test_split_hash_matches_its_committed_baseline(profile: str, kind: str) -> None:
    current = hash_trace(generate_profile_trace(profile), kind)
    assert current == load_baseline(profile, kind), (
        f"Determinism regression: the {kind} hash of the {profile} profile differs from its "
        "baseline. " + (
            "The legacy set is never re-recorded: the legacy profile is bit-identical by rule "
            "(docs/decisions.md G22), so the change itself is the regression."
            if profile == "legacy" else
            "If the change is intended, regenerate with: python3 tools/update_determinism_baseline.py "
            "--profile research --i-know-what-im-doing (docs/determinism.md)."
        )
    )


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_the_three_committed_baselines_of_a_profile_label_the_same_ticks_with_different_digests(
    profile: str,
) -> None:
    baselines = {kind: load_baseline(profile, kind) for kind in HASH_KINDS}
    labels = {kind: [row["tick"] for row in rows] for kind, rows in baselines.items()}
    assert labels["full"] == labels["behaviour"] == labels["physics"] == list(range(DEFAULT_TICKS)) + ["run"]
    digests = {kind: [row["hash"] for row in rows] for kind, rows in baselines.items()}
    assert len({digests["full"][-1], digests["behaviour"][-1], digests["physics"][-1]}) == 3
    # No tick hashes the same under two kinds: the payloads are different sets of fields.
    for tick in range(DEFAULT_TICKS):
        assert len({digests[kind][tick] for kind in HASH_KINDS}) == 3, tick


def test_a_criticality_internals_change_keeps_the_committed_behaviour_hash_and_changes_the_physics_hash() -> None:
    """Criticality coupling 0.30 at the legacy defaults (the lattice is dormant at the
    defaults: tools/probes/dormant_couplings, docs/profiles.md). Measured at seed 1337
    over 200 ticks: all 200 behaviour ticks equal the baseline, the physics hashes part
    from tick 7 and the full hash parts with them, which is why the split exists."""
    cfg = EngineConfig()
    cfg.criticality.coupling = 0.30
    trace = Engine(seed=DEFAULT_SEED, config=cfg).run(DEFAULT_TICKS)
    assert hash_trace(trace, "behaviour") == load_baseline("legacy", "behaviour")
    physics = hash_trace(trace, "physics")
    physics_baseline = load_baseline("legacy", "physics")
    assert physics != physics_baseline
    first_differing_tick = next(i for i, (a, b) in enumerate(zip(physics, physics_baseline)) if a != b)
    assert first_differing_tick == 7
    assert hash_trace(trace, "full") != load_baseline("legacy", "full")


def test_a_behavioural_change_changes_the_committed_behaviour_hash() -> None:
    cfg = EngineConfig()
    cfg.basal_ganglia.forward_bias = 0.7
    trace = Engine(seed=DEFAULT_SEED, config=cfg).run(DEFAULT_TICKS)
    assert hash_trace(trace, "behaviour") != load_baseline("legacy", "behaviour")
    assert hash_trace(trace, "full") != load_baseline("legacy", "full")
