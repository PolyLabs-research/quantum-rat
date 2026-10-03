"""Compare two TickData JSONL traces tick by tick within a float tolerance.

The cross-platform determinism gate (docs/determinism.md): ints, strings,
booleans and nulls must match exactly, floats within an absolute tolerance
(default 1e-9, per-field overrides), and a value that changed type is a
mismatch even when the numbers agree. The report names the worst float
deviation (field and tick) and the first mismatches; the exit code is 0 when
the traces agree and 1 otherwise.

    python3 tools/compare_traces.py tests/determinism/reference_trace_legacy.jsonl other.jsonl
    python3 tools/compare_traces.py ref.jsonl other.jsonl --atol 1e-9 --field-atol pos=1e-8

Standard library only, so it runs on any machine that produced a trace. The
function form, ``compare_traces``, takes paths or iterables of tick dicts.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

DEFAULT_ATOL = 1e-9

TraceSource = Union[str, Path, Iterable[Mapping[str, Any]]]


@dataclass(frozen=True)
class Mismatch:
    """One disagreement: ``difference`` is the absolute float gap, or ``None`` when not numeric."""

    tick: int
    path: str
    reference: Any
    candidate: Any
    difference: Optional[float]

    def describe(self) -> str:
        if self.difference is None:
            return f"tick {self.tick} {self.path}: {self.reference!r} != {self.candidate!r}"
        return (
            f"tick {self.tick} {self.path}: {self.reference!r} vs {self.candidate!r} "
            f"(|diff| = {self.difference:.3e})"
        )


@dataclass
class Comparison:
    """The outcome of ``compare_traces``."""

    ok: bool
    atol: float
    ticks_compared: int
    reference_ticks: int
    candidate_ticks: int
    worst_difference: float = 0.0  # largest absolute float gap seen, within tolerance or not
    worst_tick: Optional[int] = None
    worst_path: Optional[str] = None
    mismatches: List[Mismatch] = field(default_factory=list)

    def summary(self, max_mismatches: int = 10) -> str:
        lines = [
            f"ticks compared: {self.ticks_compared} "
            f"(reference {self.reference_ticks}, candidate {self.candidate_ticks}); atol {self.atol:g}"
        ]
        if self.worst_path is None:
            lines.append("worst float deviation: none (no float compared)")
        else:
            lines.append(
                f"worst float deviation: {self.worst_difference:.3e} at tick {self.worst_tick} {self.worst_path}"
            )
        if self.ok:
            lines.append("OK: traces agree within tolerance")
        else:
            lines.append(f"MISMATCH: {len(self.mismatches)} disagreement(s)")
            for item in self.mismatches[:max_mismatches]:
                lines.append("  " + item.describe())
            if len(self.mismatches) > max_mismatches:
                lines.append(f"  ... {len(self.mismatches) - max_mismatches} more")
        return "\n".join(lines)


def load_jsonl(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Read a JSONL trace (one tick per line, blank lines ignored)."""
    rows: List[Dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _rows(source: TraceSource) -> List[Mapping[str, Any]]:
    if isinstance(source, (str, Path)):
        return load_jsonl(source)
    return list(source)


def _float_gap(a: float, b: float) -> float:
    """Absolute difference with nan/inf handled: equal values (inf == inf, nan with nan) are 0."""
    if a == b or (math.isnan(a) and math.isnan(b)):
        return 0.0
    gap = abs(a - b)
    return math.inf if math.isnan(gap) else gap


class _Walker:
    """Recursive comparison of one tick, accumulating mismatches and the worst float gap."""

    def __init__(self, atol: float, field_atol: Mapping[str, float], result: Comparison) -> None:
        self.atol = atol
        self.field_atol = dict(field_atol)
        self.result = result

    def tolerance(self, path: str) -> float:
        if path in self.field_atol:
            return self.field_atol[path]
        top = path.split(".", 1)[0].split("[", 1)[0]
        return self.field_atol.get(top, self.atol)

    def mismatch(self, tick: int, path: str, ref: Any, cand: Any, difference: Optional[float]) -> None:
        self.result.mismatches.append(Mismatch(tick, path, ref, cand, difference))
        self.result.ok = False

    def visit(self, tick: int, path: str, ref: Any, cand: Any) -> None:
        # bool is a subclass of int, so it is checked first and compared exactly.
        if isinstance(ref, bool) or isinstance(cand, bool):
            if not (isinstance(ref, bool) and isinstance(cand, bool) and ref == cand):
                self.mismatch(tick, path, ref, cand, None)
            return
        if isinstance(ref, float) and isinstance(cand, float):
            gap = _float_gap(ref, cand)
            if gap > self.result.worst_difference or self.result.worst_path is None:
                self.result.worst_difference = gap
                self.result.worst_tick = tick
                self.result.worst_path = path
            if not gap <= self.tolerance(path):
                self.mismatch(tick, path, ref, cand, gap)
            return
        if isinstance(ref, int) and isinstance(cand, int):
            if ref != cand:
                self.mismatch(tick, path, ref, cand, None)
            return
        if isinstance(ref, (int, float)) and isinstance(cand, (int, float)):
            # One int and one float: a type change, which the hashes would also see.
            self.mismatch(tick, path, ref, cand, None)
            return
        if isinstance(ref, Mapping) and isinstance(cand, Mapping):
            for key in sorted(set(ref) | set(cand)):
                sub = f"{path}.{key}" if path else str(key)
                if key not in ref or key not in cand:
                    self.mismatch(tick, sub, ref.get(key, "<missing>"), cand.get(key, "<missing>"), None)
                    continue
                self.visit(tick, sub, ref[key], cand[key])
            return
        if isinstance(ref, (list, tuple)) and isinstance(cand, (list, tuple)):
            if len(ref) != len(cand):
                self.mismatch(tick, f"{path}[len]", len(ref), len(cand), None)
                return
            for index, (a, b) in enumerate(zip(ref, cand)):
                self.visit(tick, f"{path}[{index}]", a, b)
            return
        if ref is None and cand is None:
            return
        if isinstance(ref, str) and isinstance(cand, str):
            if ref != cand:
                self.mismatch(tick, path, ref, cand, None)
            return
        self.mismatch(tick, path, ref, cand, None)


def compare_traces(
    reference: TraceSource,
    candidate: TraceSource,
    *,
    atol: float = DEFAULT_ATOL,
    field_atol: Optional[Mapping[str, float]] = None,
) -> Comparison:
    """Compare ``candidate`` against ``reference`` tick by tick.

    ``field_atol`` overrides the tolerance per field, keyed by the top-level
    field name (``"pos"``) or a full path (``"neuromodulators.da"``,
    ``"pos[0]"``). A length difference is reported as a mismatch after the
    common prefix has been compared.
    """
    ref_rows = _rows(reference)
    cand_rows = _rows(candidate)
    common = min(len(ref_rows), len(cand_rows))
    result = Comparison(
        ok=True,
        atol=atol,
        ticks_compared=common,
        reference_ticks=len(ref_rows),
        candidate_ticks=len(cand_rows),
    )
    walker = _Walker(atol, field_atol or {}, result)
    for index in range(common):
        walker.visit(index, "", ref_rows[index], cand_rows[index])
    if len(ref_rows) != len(cand_rows):
        walker.mismatch(common, "<trace length>", len(ref_rows), len(cand_rows), None)
    return result


def _parse_field_atol(items: Sequence[str]) -> Dict[str, float]:
    overrides: Dict[str, float] = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise argparse.ArgumentTypeError(f"--field-atol expects NAME=TOL, got {item!r}")
        overrides[name] = float(value)
    return overrides


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reference", type=Path, help="Reference JSONL trace.")
    parser.add_argument("candidate", type=Path, help="Candidate JSONL trace to check against it.")
    parser.add_argument("--atol", type=float, default=DEFAULT_ATOL, help=f"Absolute float tolerance (default {DEFAULT_ATOL:g}).")
    parser.add_argument(
        "--field-atol",
        action="append",
        default=[],
        metavar="NAME=TOL",
        help="Per-field tolerance override (top-level field name or full path); repeatable.",
    )
    parser.add_argument("--max-report", type=int, default=10, help="Mismatches to print (default 10).")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        overrides = _parse_field_atol(args.field_atol)
    except argparse.ArgumentTypeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    result = compare_traces(args.reference, args.candidate, atol=args.atol, field_atol=overrides)
    print(result.summary(max_mismatches=args.max_report))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
