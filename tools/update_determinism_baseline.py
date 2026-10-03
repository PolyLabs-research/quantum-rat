"""Regenerate determinism baseline hashes (guarded by explicit flag)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.determinism import BASELINE_PATH, DEFAULT_SEED, DEFAULT_TICKS, build_current_trace
from metrics.schema import SCHEMA_VERSION


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--i-know-what-im-doing",
        action="store_true",
        dest="force",
        help="Required to overwrite the committed baseline.",
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.force:
        raise SystemExit("Refusing to overwrite baseline without --i-know-what-im-doing")

    hashes = build_current_trace(seed=args.seed, ticks=args.ticks)
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(hashes, indent=2))
    meta = {
        "seed": args.seed,
        "ticks": args.ticks,
        "schema_version": SCHEMA_VERSION,
        "generated_by": Path(__file__).name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = BASELINE_PATH.with_name("baseline_meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"Wrote determinism baseline to {BASELINE_PATH} (seed={args.seed}, ticks={args.ticks})")


if __name__ == "__main__":
    main()
