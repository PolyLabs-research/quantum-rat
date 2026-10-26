"""Every test that reads a committed hash file carries the ``exact_hash`` marker.

The macOS CI job runs ``pytest -m "not exact_hash"`` (``.github/workflows/ci.yml``):
the committed hashes were recorded on Linux, and across platforms only agreement
within tolerance is claimed (docs/determinism.md). A gate added without the marker
would turn the cross-platform job into an exact comparison the design does not
make, so this test scans the suite's source for the readers of committed hash
files and requires the marker on each test function that uses one (or
``pytestmark`` on its module).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List

TESTS = Path(__file__).resolve().parents[1]

# How a test gets at a committed hash file: the loaders, the file names, the directory.
READERS = (
    "load_baseline(",
    "load_profile_baseline(",
    "baseline_hashes",
    "steering_legacy_hashes",
    "regression/baseline",
    "regression\" / \"baseline",
)


def _has_marker(decorators: List[ast.expr]) -> bool:
    for node in decorators:
        text = ast.unparse(node)
        if text in ("pytest.mark.exact_hash", "pytest.mark.exact_hash()"):
            return True
    return False


def _module_marked(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            if "exact_hash" in ast.unparse(node.value):
                return True
    return False


def _unmarked_readers() -> List[str]:
    missing: List[str] = []
    for path in sorted(TESTS.rglob("test_*.py")):
        if path == Path(__file__).resolve():
            continue
        source = path.read_text(encoding="utf-8")
        if not any(reader in source for reader in READERS):
            continue
        tree = ast.parse(source)
        if _module_marked(tree):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                body = ast.get_source_segment(source, node) or ""
                if any(reader in body for reader in READERS) and not _has_marker(node.decorator_list):
                    missing.append(f"{path.relative_to(TESTS.parent)}::{node.name}")
    return missing


def test_every_test_that_reads_a_committed_hash_file_is_marked_exact_hash() -> None:
    assert _unmarked_readers() == [], (
        "these tests compare against a committed hash file without the exact_hash marker, so the "
        "macOS job (-m 'not exact_hash') would run them as exact comparisons: mark them (pytest.ini)"
    )


def test_the_scan_finds_the_known_gates() -> None:
    marked = {
        "tests/determinism/test_trace_hash.py",
        "tests/determinism/test_trace_hash_split.py",
        "tests/regression/test_regression_against_baseline.py",
        "tests/engine/test_profiles.py",
        "tests/engine/test_steering_robustness.py",
        "tests/engine/test_seeds_as_samples.py",
    }
    found = {
        str(path.relative_to(TESTS.parent))
        for path in TESTS.rglob("test_*.py")
        if path != Path(__file__).resolve() and any(r in path.read_text(encoding="utf-8") for r in READERS)
    }
    assert marked <= found, sorted(marked - found)
