"""The cross-platform tolerance gate (docs/determinism.md).

Each profile's current 200-tick trace must agree with the committed reference
trace (``reference_trace_<profile>.jsonl``, seed 1337) within
``tools/compare_traces.py``'s default tolerance: 1e-9 absolute on floats,
exact for everything else, with one accounted-for exception: ``obs_checksum``
is a hash of the Observation's float ``repr``s, so a last-bit difference the
tolerance accepts still changes it (the first macOS CI run: 29 and 15
checksums of 200 ticks differed at a worst float deviation of 9e-16). The gate
therefore also writes the current run's observation sidecar and compares it
with the committed ``reference_observations_<profile>.jsonl`` field by field,
floats within the tolerance, ray labels and whisker bits exactly; a differing
checksum on a tick whose observations agree is tolerated and counted, and is
a mismatch otherwise. On the machine that wrote the references the agreement
is exact and nothing is tolerated; the gate asserts the tolerance, which is
the claim made across platforms. The other tests check the comparison tool
itself: a 1e-6 perturbation is flagged with its tick and field, non-floats are
exact, a checksum difference without sidecars or with disagreeing sidecars is
a mismatch, and the command line exits 1 on a mismatch.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.determinism import (
    PROFILE_NAMES,
    generate_profile_trace,
    generate_profile_trace_with_observations,
    hash_trace,
    reference_observations_path,
    reference_trace_path,
    write_observation_trace,
    write_reference_trace,
)
from metrics.logger import _canonical_json
from tools.compare_traces import DEFAULT_ATOL, HASH_DERIVED_FIELDS, compare_traces, load_jsonl

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_current_trace_matches_the_reference_within_tolerance(profile: str, tmp_path: Path) -> None:
    trace, observations = generate_profile_trace_with_observations(profile)
    current = write_reference_trace(trace, tmp_path / f"{profile}.jsonl")
    current_obs = write_observation_trace(observations, tmp_path / f"{profile}_observations.jsonl")
    result = compare_traces(
        reference_trace_path(profile),
        current,
        reference_observations=reference_observations_path(profile),
        candidate_observations=current_obs,
    )
    assert result.ok, result.summary()
    assert result.ticks_compared == result.reference_ticks == result.candidate_ticks == 200
    assert result.observation_ticks_compared == 200
    assert result.worst_difference <= DEFAULT_ATOL
    assert result.observation_worst_difference <= DEFAULT_ATOL
    # Every tolerated checksum difference is one the sidecars accounted for; the
    # summary names how many (0 on the machine that wrote the references).
    assert all(t.path in HASH_DERIVED_FIELDS for t in result.tolerated_hashes)
    if result.tolerated_hashes:
        assert f"tolerated hash difference(s): {len(result.tolerated_hashes)}" in result.summary()
    else:
        assert "tolerated" not in result.summary()


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_the_committed_sidecar_is_the_committed_traces_observation(profile: str) -> None:
    """Both files are committed, so this holds on every platform: tick for tick, the sidecar's
    forward, turn and pain fields are the trace's ``obs_*`` summary fields, and the sidecar has
    the record layout the gate reads."""
    trace = load_jsonl(reference_trace_path(profile))
    sidecar = load_jsonl(reference_observations_path(profile))
    assert len(trace) == len(sidecar) == 200
    for tick, record in zip(trace, sidecar):
        assert record["tick"] == tick["tick"]
        assert record["forward_delta"] == tick["obs_forward_delta"]
        assert record["turn_delta"] == tick["obs_turn_delta"]
        assert record["pain_signal"] == tick["obs_pain"]
        expected_keys = {"tick", "vision_rays", "whisker_hits", "pain_signal", "forward_delta", "turn_delta"}
        if profile == "research":  # the heading oracle and the wall-contact sensing, on since M2b's exit (G37)
            expected_keys |= {"heading", "wall_contacts"}
            assert isinstance(record["heading"], float) and isinstance(record["wall_contacts"], list)
            # and since G50 the sideways odometry, the distal cues in view (none in this arena) and the free space
            expected_keys |= {"lateral_delta", "landmarks", "free_space"}
            assert isinstance(record["lateral_delta"], float) and record["landmarks"] == [] and len(record["free_space"]) == 7
        assert set(record) == expected_keys
        assert len(record["whisker_hits"]) == 2 and all(isinstance(b, bool) for b in record["whisker_hits"])
        assert record["vision_rays"] and all(set(r) == {"dist", "obj_type", "angle"} for r in record["vision_rays"])


@pytest.mark.exact_hash  # same-platform bit identity of the sidecar (pytest.ini, docs/determinism.md)
@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_the_current_observations_equal_the_committed_sidecar_bit_for_bit(profile: str) -> None:
    trace, observations = generate_profile_trace_with_observations(profile)
    assert [_canonical_json(o) for o in observations] == [
        line for line in reference_observations_path(profile).read_text(encoding="utf-8").splitlines() if line
    ]
    # And the run that wrote them is the gate's run: the same trace as generate_profile_trace.
    assert hash_trace(trace) == hash_trace(generate_profile_trace(profile))


def test_a_checksum_difference_is_tolerated_only_when_the_sidecars_account_for_it() -> None:
    rows = load_jsonl(reference_trace_path("legacy"))
    sidecar = load_jsonl(reference_observations_path("legacy"))
    changed = copy.deepcopy(rows)
    changed[8]["obs_checksum"] = "0" * 64
    changed[41]["obs_checksum"] = "1" * 64
    # Without sidecars: a mismatch, as for any string.
    result = compare_traces(rows, changed)
    assert not result.ok and [(m.tick, m.path) for m in result.mismatches] == [(8, "obs_checksum"), (41, "obs_checksum")]
    assert result.observation_ticks_compared == 0 and result.tolerated_hashes == []
    # With sidecars whose observations agree exactly: tolerated, counted, not a mismatch.
    result = compare_traces(rows, changed, reference_observations=sidecar, candidate_observations=sidecar)
    assert result.ok, result.summary()
    assert [(t.tick, t.path, t.observation_difference) for t in result.tolerated_hashes] == [
        (8, "obs_checksum", 0.0), (41, "obs_checksum", 0.0)
    ]
    assert result.observation_ticks_compared == 200
    assert "tolerated hash difference(s): 2" in result.summary() and "tick 8 obs_checksum: differs" in result.summary()
    # With a last-bit observation difference under the tolerance: still tolerated, and the gap is reported.
    nudged = copy.deepcopy(sidecar)
    nudged[8]["vision_rays"][0]["dist"] += 1e-15
    result = compare_traces(rows, changed, reference_observations=sidecar, candidate_observations=nudged)
    assert result.ok, result.summary()
    assert result.tolerated_hashes[0].observation_difference == pytest.approx(1e-15, rel=0.5)
    assert (result.observation_worst_tick, result.observation_worst_path) == (8, "observation.vision_rays[0].dist")
    # An observation difference above the tolerance on the checksum's tick: the checksum
    # is a mismatch and so is the observation field, reported under ``observation.``.
    bad = copy.deepcopy(sidecar)
    bad[8]["vision_rays"][0]["dist"] += 1e-6
    result = compare_traces(rows, changed, reference_observations=sidecar, candidate_observations=bad)
    assert not result.ok
    assert [(m.tick, m.path) for m in result.mismatches] == [(8, "observation.vision_rays[0].dist"), (8, "obs_checksum")]
    assert [(t.tick, t.path) for t in result.tolerated_hashes] == [(41, "obs_checksum")]
    # A categorical observation difference (a ray label, a whisker bit) is never tolerated.
    for mutate in (
        lambda rec: rec["vision_rays"][0].__setitem__("obj_type", "target"),
        lambda rec: rec["whisker_hits"].__setitem__(0, not rec["whisker_hits"][0]),
    ):
        cat = copy.deepcopy(sidecar)
        mutate(cat[41])
        result = compare_traces(rows, changed, reference_observations=sidecar, candidate_observations=cat)
        assert not result.ok and (41, "obs_checksum") in [(m.tick, m.path) for m in result.mismatches]
    # An observation difference on a tick whose checksum agrees is itself a mismatch: the sidecar is part of the gate.
    result = compare_traces(rows, rows, reference_observations=sidecar, candidate_observations=bad)
    assert not result.ok and [(m.tick, m.path) for m in result.mismatches] == [(8, "observation.vision_rays[0].dist")]
    # Sidecars come in pairs, and each must have one record per tick.
    with pytest.raises(ValueError):
        compare_traces(rows, rows, reference_observations=sidecar)
    with pytest.raises(ValueError):
        compare_traces(rows, rows, reference_observations=sidecar, candidate_observations=sidecar[:-1])


def test_wm_novelty_is_not_hash_derived_and_stays_exact() -> None:
    """The checksum-changed bit says whether the observation changed since the previous tick; two
    platforms disagreeing about that is a mismatch, whatever the sidecars say."""
    assert HASH_DERIVED_FIELDS == ("obs_checksum",)
    rows = load_jsonl(reference_trace_path("legacy"))
    sidecar = load_jsonl(reference_observations_path("legacy"))
    flipped = copy.deepcopy(rows)
    flipped[8]["wm_novelty"] = 1.0 - flipped[8]["wm_novelty"]
    result = compare_traces(rows, flipped, reference_observations=sidecar, candidate_observations=sidecar)
    assert not result.ok and [(m.tick, m.path) for m in result.mismatches] == [(8, "wm_novelty")]


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
    # A per-field tolerance for a sidecar field is keyed under ``observation.``.
    sidecar = load_jsonl(reference_observations_path("legacy"))
    nudged = copy.deepcopy(sidecar)
    nudged[3]["pain_signal"] += 1e-6
    assert not compare_traces(rows, rows, reference_observations=sidecar, candidate_observations=nudged).ok
    assert compare_traces(
        rows, rows, reference_observations=sidecar, candidate_observations=nudged, field_atol={"observation.pain_signal": 1e-5}
    ).ok
    assert compare_traces(
        rows, rows, reference_observations=sidecar, candidate_observations=nudged, field_atol={"observation": 1e-5}
    ).ok


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
    sidecar = reference_observations_path("research")
    rows = load_jsonl(reference)
    rows[42]["atp"] += 1e-6
    perturbed = tmp_path / "perturbed.jsonl"
    perturbed.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))
    rehashed = load_jsonl(reference)
    rehashed[17]["obs_checksum"] = "f" * 64
    rehashed_path = tmp_path / "rehashed.jsonl"
    rehashed_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rehashed))

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
    # A checksum difference: 1 without the sidecars, 0 (tolerated and reported) with them.
    assert run(rehashed_path).returncode == 1
    tolerated = run(rehashed_path, "--observations", str(sidecar), str(sidecar))
    assert tolerated.returncode == 0, tolerated.stdout + tolerated.stderr
    assert "tolerated hash difference(s): 1" in tolerated.stdout and "tick 17 obs_checksum" in tolerated.stdout
    # A sidecar of the wrong length is a usage error (exit 2), not a silent pass.
    short = tmp_path / "short_observations.jsonl"
    short.write_text("".join(sidecar.read_text().splitlines(keepends=True)[:-1]))
    assert run(rehashed_path, "--observations", str(sidecar), str(short)).returncode == 2
