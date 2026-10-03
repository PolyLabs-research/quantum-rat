"""Regenerate determinism baselines (guarded by explicit flag).

One set of baselines per config profile (docs/profiles.md, docs/determinism.md).
``--profile research`` (the default) writes, for ``EngineConfig.research()`` at
the gate's seed and tick count, the three hash kinds of the same trace
(``baseline_hashes_research.json``, the full file the gate uses;
``baseline_behaviour_research.json``; ``baseline_physics_research.json``), plus
``baseline_meta_research.json`` and ``reference_trace_research.jsonl``, the
JSONL trace the cross-platform tolerance gate compares against. Overwriting the
committed set needs ``--i-know-what-im-doing``.

The legacy set (``baseline_hashes.json``, ``baseline_behaviour_legacy.json``,
``baseline_physics_legacy.json``, ``baseline_meta.json``,
``reference_trace_legacy.jsonl``) is never re-recorded: the legacy profile is
bit-identical by rule (docs/decisions.md G22), so ``--profile legacy`` is
refused unless ``--out-dir`` points somewhere else.

``--out-dir DIR`` writes a profile's files into another directory, with no flag
needed, so a regeneration can be diffed against the committed files without
touching them (the way to check the legacy set).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import EngineConfig
from core.determinism import (
    BASELINE_DIR,
    BASELINE_PATH,
    DEFAULT_SEED,
    DEFAULT_TICKS,
    HASH_KINDS,
    baseline_meta_path,
    baseline_path,
    generate_profile_trace,
    hash_trace,
    reference_trace_path,
    write_reference_trace,
)
from metrics.schema import SCHEMA_VERSION

PROFILES: Dict[str, Callable[[], EngineConfig]] = {
    "legacy": EngineConfig.legacy,
    "research": EngineConfig.research,
}


def baseline_paths(profile: str, directory: Optional[Path] = None) -> Tuple[Path, Path]:
    """(full hashes file, meta file) for a profile. ``legacy`` keeps the original file names."""
    return baseline_path(profile, "full", directory), baseline_meta_path(profile, directory)


def build_profile_trace(
    profile: str, seed: int = DEFAULT_SEED, ticks: int = DEFAULT_TICKS, kind: str = "full"
) -> List[Dict[str, Any]]:
    """The ``kind`` hash list for ``PROFILES[profile]()`` at ``seed`` over ``ticks`` with the current code."""
    return hash_trace(generate_profile_trace(profile, seed=seed, ticks=ticks), kind)


def load_profile_baseline(profile: str, kind: str = "full") -> List[Dict[str, Any]]:
    """The committed hash list for a profile and kind."""
    path = baseline_path(profile, kind)
    if not path.exists():
        raise FileNotFoundError(f"Baseline file missing: {path}")
    return json.loads(path.read_text())


def write_profile_baselines(
    profile: str,
    seed: int = DEFAULT_SEED,
    ticks: int = DEFAULT_TICKS,
    directory: Optional[Path] = None,
) -> Dict[str, Path]:
    """Run the profile once and write its three hash files, meta file and reference trace.

    Returns the written paths keyed by hash kind, ``meta`` and ``reference_trace``.
    """
    trace = generate_profile_trace(profile, seed=seed, ticks=ticks)
    written: Dict[str, Path] = {}
    for kind in HASH_KINDS:
        path = baseline_path(profile, kind, directory)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(hash_trace(trace, kind), indent=2))
        written[kind] = path
    reference = reference_trace_path(profile, directory)
    write_reference_trace(trace, reference)
    written["reference_trace"] = reference
    meta_path = baseline_meta_path(profile, directory)
    meta = {
        "seed": seed,
        "ticks": ticks,
        "profile": profile,
        "schema_version": SCHEMA_VERSION,
        "hash_kinds": list(HASH_KINDS),
        "files": {key: path.name for key, path in written.items()},
        "generated_by": Path(__file__).name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    written["meta"] = meta_path
    return written


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--i-know-what-im-doing",
        action="store_true",
        dest="force",
        help="Required to overwrite the committed research baseline (not needed with --out-dir).",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="research",
        help=(
            "Config profile to generate the baselines for (default: research). "
            "The committed legacy set is never re-recorded: 'legacy' needs --out-dir."
        ),
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=DEFAULT_TICKS,
        help=f"Number of ticks to generate (default: {DEFAULT_TICKS}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Seed to use for the trace (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help=(
            "Write the files into this directory instead of the committed location "
            f"({BASELINE_PATH.parent}); the committed files are then left untouched."
        ),
    )
    return parser.parse_args(argv)


LEGACY_RULE = (
    "Refusing to re-record the committed legacy baselines: the legacy profile is bit-identical "
    "by rule (docs/decisions.md G22, docs/determinism.md). Pass --out-dir DIR to write the "
    "legacy set elsewhere and diff it against tests/determinism/."
)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    target = Path(args.out_dir).resolve() if args.out_dir is not None else BASELINE_DIR
    writes_committed_set = target == BASELINE_DIR
    if writes_committed_set and args.profile == "legacy":
        print(LEGACY_RULE, file=sys.stderr)
        raise SystemExit(2)
    if writes_committed_set and not args.force:
        raise SystemExit("Refusing to overwrite the committed baseline without --i-know-what-im-doing")

    written = write_profile_baselines(args.profile, seed=args.seed, ticks=args.ticks, directory=args.out_dir)
    for key, path in written.items():
        print(f"Wrote {key}: {path}")
    print(f"(profile={args.profile}, seed={args.seed}, ticks={args.ticks})")


if __name__ == "__main__":
    main()
