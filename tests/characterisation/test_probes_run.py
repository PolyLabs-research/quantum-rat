"""Smoke test: every characterisation probe imports, runs at a tiny budget and prints.

The probes in ``tools/probes`` are the research-readiness audit's measurements
(2026-10-03) made reproducible. This test does not pin their numbers (the
recorded outputs live in tools/probes/README.md and the numbers are expected
to move as the model changes); it keeps the probes alive: each must expose
``run(scale)`` and ``main(argv)``, run end to end at a small budget, return a
non-empty dict of labelled results, be deterministic across two calls, and
print one ``label: value`` line per result. The whole module runs in a few
seconds (``--scale 0.02`` to ``0.05`` per probe).
"""

from __future__ import annotations

import importlib
import math

import pytest

from tools.probes import PROBES
from tools.probes._common import fmt

SCALE = 0.03
# Probes whose full budget is large get a smaller scale so the suite stays fast.
SCALE_OVERRIDES = {"criticality_critical_point": 0.02, "kappa_defaults": 0.02}


def _finite(value) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return not (isinstance(value, float) and math.isinf(value))
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(v) for v in value)
    return True


@pytest.mark.parametrize("name", PROBES)
def test_probe_runs_at_tiny_budget(name: str, capsys) -> None:
    module = importlib.import_module(f"tools.probes.{name}")
    scale = SCALE_OVERRIDES.get(name, SCALE)
    results = module.run(scale)
    assert isinstance(results, dict) and len(results) >= 2
    assert "config" in results
    assert _finite(results)
    if name != "runtime":  # the only probe that measures wall-clock
        # Compare the printed rendering: a NaN (e.g. a mean over zero sleeps at a
        # tiny budget) is a legitimate result but never equals itself.
        assert fmt(module.run(scale)) == fmt(results), "probe is not deterministic"
    printed = module.main(["--scale", str(scale)])
    assert printed.keys() == results.keys()
    out = capsys.readouterr().out
    assert out.startswith("== ")
    for key in results:
        assert f"\n{key}: " in out


def test_probe_list_matches_package_contents() -> None:
    import pkgutil

    import tools.probes as pkg

    modules = {m.name for m in pkgutil.iter_modules(pkg.__path__) if not m.name.startswith("_")}
    assert modules == set(PROBES)
