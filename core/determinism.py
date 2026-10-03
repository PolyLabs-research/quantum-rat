"""Deterministic trace generation and baseline helpers.

Single source of truth for the determinism gate, shared by the test suite,
the app's ``/determinism_check`` route, and the baseline-update tool.

These helpers previously lived under ``tests/determinism`` and were imported
by production/app code, which inverted the normal dependency direction
(shippable code depending on the test package). They now live here in
``core`` so tests depend on code, not the reverse.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core.engine import Engine
from metrics.hash import RunHash
from metrics.schema import TickData

DEFAULT_SEED = 1337
DEFAULT_TICKS = 200

# The committed baseline hashes live alongside the determinism tests.
BASELINE_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "determinism" / "baseline_hashes.json"
)


def generate_trace(seed: int, ticks: int, *, agent_offset: int = 0) -> List[TickData]:
    """Produce a deterministic ``TickData`` sequence for the given seed."""
    engine = Engine(seed=seed, agent_offset=agent_offset)
    return engine.run(ticks)


def build_current_trace(seed: int = DEFAULT_SEED, ticks: int = DEFAULT_TICKS) -> List[Dict[str, Any]]:
    """Build the per-tick + whole-run hash list for the current code."""
    run_hash = RunHash()
    hashes: List[Dict[str, Any]] = []
    for tick in generate_trace(seed=seed, ticks=ticks):
        digest = run_hash.update(tick)
        hashes.append({"tick": tick.tick, "hash": digest})
    hashes.append({"tick": "run", "hash": run_hash.hexdigest()})
    return hashes


def load_baseline() -> List[Dict[str, Any]]:
    """Load the committed baseline hash list."""
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(f"Baseline file missing: {BASELINE_PATH}")
    return json.loads(BASELINE_PATH.read_text())


__all__ = [
    "DEFAULT_SEED",
    "DEFAULT_TICKS",
    "BASELINE_PATH",
    "generate_trace",
    "build_current_trace",
    "load_baseline",
]
