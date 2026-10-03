"""Characterisation probes: the research-readiness audit's measurements, committed.

Each module in this package reproduces one measurement that the audit of
2026-10-03 made with a scratch script, so the claim it supports can be re-run
on any commit:

    python -m tools.probes.<name>              # full budget (outputs in README.md)
    python -m tools.probes.<name> --scale 0.1  # a tenth of the tick/pass budget

Every probe exposes ``run(scale=1.0) -> dict`` and ``main(argv=None)``; see
``tools/probes/_common.py`` and ``tools/probes/README.md``. ``PROBES`` lists
them so the smoke test (tests/characterisation/test_probes_run.py) keeps each
one importable and runnable.
"""

PROBES = (
    "kappa_defaults",
    "criticality_critical_point",
    "dormant_couplings",
    "kernel_value_inflation",
    "replay_reach",
    "memory_nav_fragility",
    "microsleep_replay_content",
    "path_integration_capture",
    "energy_limit_cycle",
    "glycogen_pinning",
    "microsleep_bout_length",
    "novelty_pinning",
    "neuromod_traces",
    "open_field_motion",
    "assay_triviality",
    "seed_pseudoreplication",
    "runtime",
    "realised_speed",
    "odometry_growth",
)

__all__ = ["PROBES"]
