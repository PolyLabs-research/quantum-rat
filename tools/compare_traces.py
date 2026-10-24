"""Compare two TickData JSONL traces tick by tick within a float tolerance.

The cross-platform determinism gate (docs/determinism.md): ints, strings,
booleans and nulls must match exactly, floats within an absolute tolerance
(default 1e-9, per-field overrides), and a value that changed type is a
mismatch even when the numbers agree. The report names the worst float
deviation (field and tick) and the first mismatches; the exit code is 0 when
the traces agree and 1 otherwise.

    python3 tools/compare_traces.py tests/determinism/reference_trace_legacy.jsonl other.jsonl
    python3 tools/compare_traces.py ref.jsonl other.jsonl --atol 1e-9 --field-atol pos=1e-8
    python3 tools/compare_traces.py ref.jsonl other.jsonl \\
        --observations tests/determinism/reference_observations_legacy.jsonl other_observations.jsonl
One field of a tick is a hash of floats: ``obs_checksum`` is the SHA-256 of
the ``repr`` of the whole Observation (``core.sensors.observation_checksum``),
so a last-bit difference in a ray distance that the float tolerance accepts
still changes the string. Comparing the string exactly would defeat the
tolerance (the first macOS CI run differed from the Linux reference in 29
checksums of 200 ticks with a worst float deviation of 9e-16). The gate
therefore compares the numbers behind the hash: given the two traces'
observation sidecars (``--observations``; one ``core.determinism
.observation_record`` per tick, written from the same engine run as each
trace), a differing ``obs_checksum`` is **tolerated** when that tick's two
observation records agree, floats within the same tolerance and ray labels,
whisker bits and the tick index exactly, and is a **mismatch** otherwise.
Without the sidecars a differing checksum is a mismatch, as before: the tool
never ignores a hash difference it cannot account for. Tolerated hash
differences are counted and reported (``Comparison.tolerated_hashes``), and
the worst float deviation inside the observation records is reported beside
the trace's. ``wm_novelty`` (1.0 when the checksum changed since the previous
tick) is not in the hash-derived set: a difference there means the two
platforms disagree about whether the observation changed, which is reported
as the mismatch it is.

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
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

DEFAULT_ATOL = 1e-9

# TickData fields that are a hash of the tick's observation (metrics/schema.py).
# A difference in one of them is tolerated only when the observation sidecars
# show the hashed numbers agreeing within tolerance (module docstring).
HASH_DERIVED_FIELDS = ("obs_checksum",)
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


@dataclass(frozen=True)
class ToleratedHash:
    """A hash-derived field that differed while the observation it hashes agreed within tolerance."""
    tick: int
    path: str
    observation_difference: float  # the worst float gap inside that tick's observation records
    def describe(self) -> str:
        return (
            f"tick {self.tick} {self.path}: differs, observation agrees "
            f"(worst |diff| = {self.observation_difference:.3e})"
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
    # The hash-derived fields that differed and were accounted for by the
    # observation sidecars (module docstring); empty when none differed or no
    # sidecars were given. ``observation_ticks_compared`` is how many ticks had
    # observation records on both sides (0 without sidecars), and the
    # ``observation_worst_*`` fields the worst float gap seen inside them.
    tolerated_hashes: List[ToleratedHash] = field(default_factory=list)
    observation_ticks_compared: int = 0
    observation_worst_difference: float = 0.0
    observation_worst_tick: Optional[int] = None
    observation_worst_path: Optional[str] = None
    # Scratch: the worst observation gap of the tick being compared (set by ``compare_traces``).
    observation_worst_difference_at_tick: float = field(default=0.0, repr=False, compare=False)

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
        if self.observation_ticks_compared:
            if self.observation_worst_path is None:
                lines.append(f"observation records compared on {self.observation_ticks_compared} tick(s)")
            else:
                lines.append(
                    f"observation records compared on {self.observation_ticks_compared} tick(s); worst float "
                    f"deviation inside them: {self.observation_worst_difference:.3e} at tick "
                    f"{self.observation_worst_tick} {self.observation_worst_path}"
                )
        if self.tolerated_hashes:
            lines.append(
                f"tolerated hash difference(s): {len(self.tolerated_hashes)} "
                f"({', '.join(sorted({t.path for t in self.tolerated_hashes}))} differ while the observation "
                f"agrees within tolerance)"
            )
            for item in self.tolerated_hashes[:max_mismatches]:
                lines.append("  " + item.describe())
            if len(self.tolerated_hashes) > max_mismatches:
                lines.append(f"  ... {len(self.tolerated_hashes) - max_mismatches} more")
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
        self.hash_fields: Tuple[str, ...] = ()
        # Set per tick by ``compare_traces``: whether this tick's observation
        # records were both present and agreed within tolerance (None: no records).
        self.observation_agrees: Optional[bool] = None

    def tolerance(self, path: str) -> float:
        if path in self.field_atol:
            return self.field_atol[path]
        top = path.split(".", 1)[0].split("[", 1)[0]
        return self.field_atol.get(top, self.atol)

    def mismatch(self, tick: int, path: str, ref: Any, cand: Any, difference: Optional[float]) -> None:
        self.result.mismatches.append(Mismatch(tick, path, ref, cand, difference))
        self.result.ok = False

    def note_float(self, tick: int, path: str, gap: float) -> None:
        if gap > self.result.worst_difference or self.result.worst_path is None:
            self.result.worst_difference = gap
            self.result.worst_tick = tick
            self.result.worst_path = path
    def visit(self, tick: int, path: str, ref: Any, cand: Any) -> None:
        # bool is a subclass of int, so it is checked first and compared exactly.
        if isinstance(ref, bool) or isinstance(cand, bool):
            if not (isinstance(ref, bool) and isinstance(cand, bool) and ref == cand):
                self.mismatch(tick, path, ref, cand, None)
            return
        if isinstance(ref, float) and isinstance(cand, float):
            gap = _float_gap(ref, cand)
            self.note_float(tick, path, gap)
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
                if path in self.hash_fields and self.observation_agrees:
                    # The hash differs but the numbers it hashes agree within tolerance
                    # (this tick's observation records were compared first).
                    self.result.tolerated_hashes.append(
                        ToleratedHash(tick, path, self.result.observation_worst_difference_at_tick)
                    )
                    return
                self.mismatch(tick, path, ref, cand, None)
            return
        self.mismatch(tick, path, ref, cand, None)


class _ObservationWalker(_Walker):
    """The same comparison over one tick's observation records; its mismatches are
    reported under ``observation.`` and its worst float gap kept apart from the trace's."""
    PREFIX = "observation"
    def mismatch(self, tick: int, path: str, ref: Any, cand: Any, difference: Optional[float]) -> None:
        self.result.mismatches.append(Mismatch(tick, f"{self.PREFIX}.{path}" if path else self.PREFIX, ref, cand, difference))
        self.result.ok = False
        self.failed = True
    def note_float(self, tick: int, path: str, gap: float) -> None:
        if gap > self.tick_worst:
            self.tick_worst = gap
        if gap > self.result.observation_worst_difference or self.result.observation_worst_path is None:
            self.result.observation_worst_difference = gap
            self.result.observation_worst_tick = tick
            self.result.observation_worst_path = f"{self.PREFIX}.{path}"
    def tolerance(self, path: str) -> float:
        # Keyed under the sidecar's own namespace: ``observation.vision_rays[0].dist`` or ``observation``.
        full = f"{self.PREFIX}.{path}" if path else self.PREFIX
        if full in self.field_atol:
            return self.field_atol[full]
        return self.field_atol.get(self.PREFIX, self.atol)


    def compare_tick(self, tick: int, ref: Mapping[str, Any], cand: Mapping[str, Any]) -> Tuple[bool, float]:
        """(agrees, worst float gap) for one tick's two records."""
        self.failed = False
        self.tick_worst = 0.0
        self.visit(tick, "", ref, cand)
        return not self.failed, self.tick_worst


def _observation_rows(source: Optional[TraceSource], n_ticks: int, name: str) -> Optional[List[Mapping[str, Any]]]:
    if source is None:
        return None
    rows = _rows(source)
    if len(rows) != n_ticks:
        raise ValueError(f"{name} observation sidecar has {len(rows)} records for a trace of {n_ticks} ticks")
    return rows


def compare_traces(
    reference: TraceSource,
    candidate: TraceSource,
    *,
    atol: float = DEFAULT_ATOL,
    field_atol: Optional[Mapping[str, float]] = None,
    reference_observations: Optional[TraceSource] = None,
    candidate_observations: Optional[TraceSource] = None,
    hash_fields: Sequence[str] = HASH_DERIVED_FIELDS,
) -> Comparison:
    """Compare ``candidate`` against ``reference`` tick by tick.

    ``field_atol`` overrides the tolerance per field, keyed by the top-level
    field name (``"pos"``) or a full path (``"neuromodulators.da"``,
    ``"pos[0]"``; ``"observation.vision_rays[0].dist"`` for a sidecar field).
    A length difference is reported as a mismatch after the common prefix has
    been compared.
    ``reference_observations`` and ``candidate_observations`` are the two
    traces' observation sidecars (``core.determinism.observation_record`` per
    tick, one record per trace tick; both or neither). When given, every
    common tick's two records are compared the same way, their mismatches
    reported under ``observation.``, and a difference in a field of
    ``hash_fields`` on a tick whose records agree is a tolerated hash
    difference rather than a mismatch (module docstring). Without them a
    differing hash field is a mismatch.
    """
    if (reference_observations is None) != (candidate_observations is None):
        raise ValueError("give both observation sidecars or neither")
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
    ref_obs = _observation_rows(reference_observations, len(ref_rows), "reference")
    cand_obs = _observation_rows(candidate_observations, len(cand_rows), "candidate")
    walker = _Walker(atol, field_atol or {}, result)
    walker.hash_fields = tuple(hash_fields)
    observer = _ObservationWalker(atol, field_atol or {}, result) if ref_obs is not None else None
    for index in range(common):
        walker.observation_agrees = None
        result.observation_worst_difference_at_tick = 0.0
        if observer is not None and ref_obs is not None and cand_obs is not None:
            agrees, tick_worst = observer.compare_tick(index, ref_obs[index], cand_obs[index])
            result.observation_ticks_compared += 1
            walker.observation_agrees = agrees
            result.observation_worst_difference_at_tick = tick_worst
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
    parser.add_argument(
        "--observations",
        nargs=2,
        type=Path,
        metavar=("REF_OBS", "CAND_OBS"),
        default=None,
        help=(
            "The two traces' observation sidecars (reference_observations_<profile>.jsonl and the "
            "candidate's), one record per tick: a differing obs_checksum is then tolerated when the "
            "observation it hashes agrees within tolerance (module docstring). Without them it is a mismatch."
        ),
    )
    return parser.parse_args(argv)



def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        overrides = _parse_field_atol(args.field_atol)
    except argparse.ArgumentTypeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    ref_obs, cand_obs = (args.observations[0], args.observations[1]) if args.observations else (None, None)
    try:
        result = compare_traces(
            args.reference,
            args.candidate,
            atol=args.atol,
            field_atol=overrides,
            reference_observations=ref_obs,
            candidate_observations=cand_obs,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(result.summary(max_mismatches=args.max_report))
    return 0 if result.ok else 1



if __name__ == "__main__":
    sys.exit(main())
