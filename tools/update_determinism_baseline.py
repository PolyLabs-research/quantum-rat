"""Regenerate determinism baseline hashes (guarded by explicit flag).

One baseline per config profile (docs/profiles.md). ``--profile legacy`` (the
default) writes tests/determinism/baseline_hashes.json and baseline_meta.json
for ``EngineConfig.legacy()``, the files the gate has always used;
``--profile research`` writes baseline_hashes_research.json and
baseline_meta_research.json for ``EngineConfig.research()`` at the same seed
and tick count. ``tests/determinism/test_trace_hash.py`` checks both.
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
from core.determinism import BASELINE_PATH, DEFAULT_SEED, DEFAULT_TICKS, hash_trace
from core.engine import Engine
from metrics.schema import SCHEMA_VERSION

PROFILES: Dict[str, Callable[[], EngineConfig]] = {
    "legacy": EngineConfig.legacy,
    "research": EngineConfig.research,
}


def baseline_paths(profile: str) -> Tuple[Path, Path]:
    """(hashes file, meta file) for a profile. ``legacy`` keeps the original file names."""
    if profile == "legacy":
        return BASELINE_PATH, BASELINE_PATH.with_name("baseline_meta.json")
    return (
        BASELINE_PATH.with_name(f"baseline_hashes_{profile}.json"),
        BASELINE_PATH.with_name(f"baseline_meta_{profile}.json"),
    )


def build_profile_trace(profile: str, seed: int = DEFAULT_SEED, ticks: int = DEFAULT_TICKS) -> List[Dict[str, Any]]:
    """The hash list for ``PROFILES[profile]()`` at ``seed`` over ``ticks`` with the current code."""
    engine = Engine(seed=seed, config=PROFILES[profile]())
    return hash_trace(engine.run(ticks))


def load_profile_baseline(profile: str) -> List[Dict[str, Any]]:
    """The committed hash list for a profile."""
    path, _ = baseline_paths(profile)
    if not path.exists():
        raise FileNotFoundError(f"Baseline file missing: {path}")
    return json.loads(path.read_text())


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--i-know-what-im-doing",
        action="store_true",
        dest="force",
        help="Required to overwrite the committed baseline.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="legacy",
        help="Config profile to generate the baseline for (default: legacy).",
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
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    if not args.force:
        raise SystemExit("Refusing to overwrite baseline without --i-know-what-im-doing")

    hashes_path, meta_path = baseline_paths(args.profile)
    hashes = build_profile_trace(args.profile, seed=args.seed, ticks=args.ticks)
    hashes_path.parent.mkdir(parents=True, exist_ok=True)
    hashes_path.write_text(json.dumps(hashes, indent=2))
    meta = {
        "seed": args.seed,
        "ticks": args.ticks,
        "profile": args.profile,
        "schema_version": SCHEMA_VERSION,
        "generated_by": Path(__file__).name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    print(
        f"Wrote determinism baseline to {hashes_path} "
        f"(profile={args.profile}, seed={args.seed}, ticks={args.ticks})"
    )


if __name__ == "__main__":
    main()
