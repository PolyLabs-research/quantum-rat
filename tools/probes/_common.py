"""Shared plumbing for the characterisation probes.

A probe is a module with ``run(scale: float = 1.0) -> dict`` returning labelled,
deterministic results (insertion order is the print order) and ``main(argv)``
built from :func:`probe_main`. ``scale`` multiplies every tick / pass budget;
:func:`budget` keeps each one above a floor so a probe still runs end to end at
``--scale 0.02`` (the CI smoke test). Recorded outputs are at scale 1.0.

Probes only read the engine: nothing in ``core``, ``brain``, ``ui`` or
``tests`` is modified by running one.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import EngineConfig  # noqa: E402
from core.engine import Engine  # noqa: E402
from metrics.schema import TickData  # noqa: E402

Results = Dict[str, Any]


def budget(n: int, scale: float, floor: int) -> int:
    """``n`` scaled by ``scale``, never below ``floor``."""
    return max(int(floor), int(round(n * scale)))


def fmt(value: Any) -> str:
    """Compact, stable rendering: floats to 4 decimals, containers recursively."""
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if abs(value) >= 1e6:
            return f"{value:.4g}"
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text if text not in ("", "-0") else "0"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {fmt(v)}" for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(fmt(v) for v in value) + "]"
    return str(value)


def print_results(title: str, results: Results) -> None:
    print(f"== {title}")
    for key, value in results.items():
        print(f"{key}: {fmt(value)}")


def probe_main(run: Callable[[float], Results], title: str) -> Callable[[Optional[Sequence[str]]], Results]:
    """Build a ``main(argv)`` that parses ``--scale`` and prints ``run(scale)``."""

    def main(argv: Optional[Sequence[str]] = None) -> Results:
        parser = argparse.ArgumentParser(description=title)
        parser.add_argument("--scale", type=float, default=1.0, help="budget multiplier (default 1.0)")
        args = parser.parse_args(argv)
        results = run(args.scale)
        print_results(title if args.scale == 1.0 else f"{title} (scale {args.scale})", results)
        return results

    return main


# --- engine helpers ---------------------------------------------------------


def run_engine(seed: int, ticks: int, config: Optional[EngineConfig] = None) -> Tuple[List[TickData], Engine]:
    """A fresh default-world engine (no objects) run for ``ticks``: (trace, engine)."""
    engine = Engine(seed=seed, config=config or EngineConfig())
    return engine.run(ticks, reset=True), engine


def run_protocol(
    protocol: Any,
    seed: int,
    ticks: int,
    config: Optional[EngineConfig] = None,
    heading: float = 0.0,
) -> Tuple[List[TickData], Engine]:
    """Run a headless ``experiments.protocols`` protocol tick by tick until it is done."""
    engine = Engine(seed=seed, config=config or EngineConfig())
    protocol.setup(engine)
    if heading:
        engine.agent.heading = heading
        engine.agent.last_heading = heading
    rows: List[TickData] = []
    for i in range(ticks):
        td = engine.run(1, reset=(i == 0))[0]
        protocol.on_tick(engine, td, i)
        rows.append(td)
        if protocol.is_done(engine, td, i):
            break
    return rows, engine


def noisy_config(noise: float) -> EngineConfig:
    cfg = EngineConfig()
    cfg.sensors.noise = noise
    return cfg


# --- trace statistics -------------------------------------------------------


def trn_state_counts(trace: Iterable[TickData]) -> Dict[str, int]:
    counts = {"OPEN": 0, "NARROW": 0, "CLOSED": 0}
    for td in trace:
        counts[td.trn_state] = counts.get(td.trn_state, 0) + 1
    return counts


def microsleep_bouts(trace: Sequence[TickData]) -> Tuple[List[int], List[int]]:
    """(complete bout lengths, awake gaps between consecutive bouts), in ticks.

    A bout still in progress when the trace ends is not a bout length (it was
    cut by the run, not by the model) and is left out; count onsets with
    :func:`microsleep_onsets` to include it.
    """
    bouts: List[int] = []
    gaps: List[int] = []
    cur = gap = 0
    for td in trace:
        if td.microsleep_active:
            if gap and bouts:
                gaps.append(gap)
            gap = 0
            cur += 1
        else:
            if cur:
                bouts.append(cur)
                cur = 0
            gap += 1
    return bouts, gaps


def microsleep_onsets(trace: Sequence[TickData]) -> int:
    """Number of microsleeps that started in the trace (including one still in progress at its end)."""
    return sum(1 for i, td in enumerate(trace) if td.microsleep_active and (i == 0 or not trace[i - 1].microsleep_active))


def frac(xs: Sequence[Any], pred: Callable[[Any], bool]) -> float:
    return sum(1 for x in xs if pred(x)) / max(1, len(xs))


def mean(xs: Sequence[float]) -> float:
    return statistics.fmean(xs) if xs else float("nan")


def median(xs: Sequence[float]) -> float:
    return statistics.median(xs) if xs else float("nan")


def path_length(points: Sequence[Tuple[float, float]]) -> float:
    return sum(
        math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]) for i in range(1, len(points))
    )


__all__ = [
    "ROOT",
    "Results",
    "budget",
    "fmt",
    "frac",
    "mean",
    "median",
    "microsleep_bouts",
    "microsleep_onsets",
    "noisy_config",
    "path_length",
    "print_results",
    "probe_main",
    "run_engine",
    "run_protocol",
    "trn_state_counts",
]
