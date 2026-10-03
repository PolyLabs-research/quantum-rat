"""The cross-platform tolerance gate (docs/determinism.md).

Each profile's current 200-tick trace must agree with the committed reference
trace (``reference_trace_<profile>.jsonl``, seed 1337) within
``tools/compare_traces.py``'s default tolerance: 1e-9 absolute on floats,
exact for everything else. On the machine that wrote the references the
agreement is exact; the gate asserts the tolerance, which is the claim made
across platforms. The other tests check the comparison tool itself: a 1e-6
perturbation is flagged with its tick and field, non-floats are exact, and the
command line exits 1 on a mismatch.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.determinism import PROFILE_NAMES, generate_profile_trace, reference_trace_path, write_reference_trace
from tools.compare_traces import DEFAULT_ATOL, compare_traces, load_jsonl

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_current_trace_matches_the_reference_within_tolerance(profile: str, tmp_path: Path) -> None:
    current = write_reference_trace(generate_profile_trace(profile), tmp_path / f"{profile}.jsonl")
    result = compare_traces(reference_trace_path(profile), current)
    assert result.ok, result.summary()
    assert result.ticks_compared == result.reference_ticks == result.candidate_ticks == 200
    assert result.worst_difference <= DEFAULT_ATOL


def test_the_comparison_flags_a_one_millionth_perturbation_and_honours_the_tolerance() -> None:
    rows = load_jsonl(reference_trace_path("legacy"))
    perturbed = copy.deepcopy(rows)
    perturbed[10]["atp"] += 1e-6
    result = compare_traces(rows, perturbed)
    assert not result.ok
    assert (result.worst_tick, result.worst_path) == (10, "atp")
    assert result.worst_difference == pytest.approx(1e-6, rel=1e-3)
    assert [(m.tick, m.path) for m in result.mismatches] == [(10, "atp")]
    assert "tick 10 atp" in result.summary()
    # The same gap passes once the tolerance covers it, globally or for that field only.
    assert compare_traces(rows, perturbed, atol=1e-5).ok
    assert compare_traces(rows, perturbed, field_atol={"atp": 1e-5}).ok
    assert not compare_traces(rows, perturbed, field_atol={"pos": 1e-5}).ok
    # A gap below the default tolerance passes, and is still the worst deviation reported.
    small = copy.deepcopy(rows)
    small[3]["pos"][0] += 1e-10
    result = compare_traces(rows, small)
    assert result.ok
    assert (result.worst_tick, result.worst_path) == (3, "pos[0]")
    assert not compare_traces(rows, small, atol=1e-11).ok
    assert not compare_traces(rows, small, field_atol={"pos[0]": 1e-11}).ok


def test_the_comparison_is_exact_for_everything_that_is_not_a_float() -> None:
    rows = load_jsonl(reference_trace_path("legacy"))

    def flagged(mutate) -> list:
        candidate = copy.deepcopy(rows)
        mutate(candidate)
        result = compare_traces(rows, candidate)
        assert not result.ok
        return [(m.tick, m.path, m.difference) for m in result.mismatches]

    def set_item(index, key, value):
        def mutate(candidate):
            candidate[index][key] = value

        return mutate

    assert flagged(set_item(5, "score", rows[5]["score"] + 1)) == [(5, "score", None)]
    assert flagged(set_item(6, "action_name", "REST" if rows[6]["action_name"] != "REST" else "FORWARD")) == [(6, "action_name", None)]
    assert flagged(set_item(7, "microsleep_active", not rows[7]["microsleep_active"])) == [(7, "microsleep_active", None)]
    assert flagged(set_item(8, "neuromodulators", {**rows[8]["neuromodulators"], "DA": rows[8]["neuromodulators"]["DA"] + 1e-6}))[0][:2] == (8, "neuromodulators.DA")
    # A type change is a mismatch even when the numbers are equal (1.0 -> 1, 0 -> 0.0).
    assert flagged(set_item(0, "atp", 1)) == [(0, "atp", None)]
    assert flagged(set_item(0, "score", float(rows[0]["score"]))) == [(0, "score", None)]
    assert flagged(set_item(0, "replay_active", 0)) == [(0, "replay_active", None)]

    def drop_key(candidate):
        del candidate[2]["kappa"]

    assert flagged(drop_key) == [(2, "kappa", None)]

    def extra_tick(candidate):
        candidate.append(copy.deepcopy(candidate[-1]))

    assert flagged(extra_tick) == [(200, "<trace length>", None)]


def test_the_command_line_exits_0_on_agreement_and_1_on_a_mismatch(tmp_path: Path) -> None:
    reference = reference_trace_path("research")
    rows = load_jsonl(reference)
    rows[42]["atp"] += 1e-6
    perturbed = tmp_path / "perturbed.jsonl"
    perturbed.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))

    def run(candidate: Path, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / "compare_traces.py"), str(reference), str(candidate), *extra],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )

    same = run(reference)
    assert same.returncode == 0, same.stdout + same.stderr
    assert "OK" in same.stdout
    different = run(perturbed)
    assert different.returncode == 1, different.stdout + different.stderr
    assert "MISMATCH" in different.stdout and "tick 42 atp" in different.stdout
    assert run(perturbed, "--atol", "1e-5").returncode == 0
    assert run(perturbed, "--field-atol", "atp=1e-5").returncode == 0
