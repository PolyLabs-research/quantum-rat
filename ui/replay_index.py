"""Run-directory helpers for the replay viewer: safe paths and paged JSONL reads."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Line-offset index per tick file, keyed by (path, mtime, size) so a file that
# changes on disk is re-indexed instead of being served from a stale index.
OFFSET_CACHE: Dict[Tuple[Path, int, int], List[int]] = {}
OFFSET_CACHE_LIMIT = 64


def get_run_root() -> Path:
    """The runs directory: ``$CRITICAL_RAT_RUNS_DIR``, defaulting to ``runs``."""
    run_dir_str = os.environ.get("CRITICAL_RAT_RUNS_DIR", "runs")
    return Path(run_dir_str).resolve()


def get_safe_path(run_id: str, *subpaths: str, root: Optional[Path] = None) -> Path:
    """Join ``run_id`` and ``subpaths`` under the runs root.

    Raises ValueError if the result (after resolving symlinks and ``..``) would
    fall outside the runs root.
    """
    run_root = Path(root).resolve() if root is not None else get_run_root()
    full_path = run_root.joinpath(run_id, *subpaths)
    real_path = os.path.realpath(full_path)
    if os.path.commonpath([run_root, real_path]) != str(run_root):
        raise ValueError(f"Path traversal attempt detected: {full_path}")
    return Path(real_path)


def get_jsonl_offsets(file_path: Path) -> List[int]:
    """Byte offset of the start of each line in a JSONL file (cached)."""
    stat = file_path.stat()
    key = (file_path, stat.st_mtime_ns, stat.st_size)
    cached = OFFSET_CACHE.get(key)
    if cached is not None:
        return cached

    offsets = [0]
    with open(file_path, "rb") as f:
        while f.readline():
            offsets.append(f.tell())
    offsets.pop()  # the last offset is EOF, not the start of a line

    if len(OFFSET_CACHE) >= OFFSET_CACHE_LIMIT:
        OFFSET_CACHE.pop(next(iter(OFFSET_CACHE)))
    OFFSET_CACHE[key] = offsets
    return offsets


def read_jsonl_paged(file_path: Path, start: int, limit: int) -> Tuple[List[Dict], int]:
    """Read ``limit`` records starting at record ``start``; also return the total count."""
    offsets = get_jsonl_offsets(file_path)
    total_lines = len(offsets)

    if start >= total_lines:
        return [], total_lines

    lines_to_read = min(limit, total_lines - start)

    ticks = []
    with open(file_path, "r", encoding="utf-8") as f:
        f.seek(offsets[start])
        for _ in range(lines_to_read):
            line = f.readline()
            if not line:
                break
            ticks.append(json.loads(line))

    return ticks, total_lines
