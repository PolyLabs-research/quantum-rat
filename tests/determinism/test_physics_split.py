"""The physics/behaviour split does its job, measured within one process.

No committed hash is involved here (both runs of each pair happen on the same
machine), so these tests run on every platform; the committed-baseline
versions of the same statements are in ``test_trace_hash_split.py``.
"""

from __future__ import annotations

import hashlib
from dataclasses import fields
from typing import Dict, List

import pytest

from core.config import EngineConfig
from core.determinism import DEFAULT_SEED, DEFAULT_TICKS, HASH_KINDS, PHYSICS_FIELDS, baseline_path, hash_trace
from core.engine import Engine
from metrics.hash import RunHash, hash_payload, tick_hash
from metrics.logger import _canonical_json, _normalize_tick
from metrics.schema import TickData


def _hashes(cfg: EngineConfig) -> Dict[str, List[dict]]:
    trace = Engine(seed=DEFAULT_SEED, config=cfg).run(DEFAULT_TICKS)
    return {kind: hash_trace(trace, kind) for kind in HASH_KINDS}


def _first_differing_tick(a: List[dict], b: List[dict]) -> int:
    return next(i for i, (x, y) in enumerate(zip(a, b)) if x != y)


def test_a_criticality_coupling_change_leaves_the_behaviour_hash_and_changes_the_physics_hash() -> None:
    """Measured at seed 1337 over 200 ticks under the legacy defaults: couplings 0.20,
    0.30, 0.35 and 0.40 all leave every behaviour tick unchanged (the lattice is dormant
    at the defaults, tools/probes/dormant_couplings) while the physics fields part
    from tick 17, 7, 3 and 3 respectively. Two of them are asserted here."""
    base = _hashes(EngineConfig())
    for coupling, first_tick in ((0.20, 17), (0.30, 7)):
        cfg = EngineConfig()
        cfg.criticality.coupling = coupling
        changed = _hashes(cfg)
        assert changed["behaviour"] == base["behaviour"], coupling
        assert changed["physics"] != base["physics"], coupling
        assert _first_differing_tick(changed["physics"], base["physics"]) == first_tick, coupling
        # The full hash would have invalidated the baseline for a change that moved no behaviour.
        assert changed["full"] != base["full"], coupling
        assert _first_differing_tick(changed["full"], base["full"]) == first_tick, coupling


def test_a_behavioural_change_changes_the_behaviour_hash() -> None:
    base = _hashes(EngineConfig())
    cfg = EngineConfig()
    cfg.basal_ganglia.forward_bias = 0.7
    changed = _hashes(cfg)
    assert changed["behaviour"] != base["behaviour"]
    assert changed["full"] != base["full"]


def test_the_split_holds_under_the_research_profile_too() -> None:
    """Research profile: the coupling change moves physics only, and the forward-bias
    change moves behaviour only. The second half is specific to this profile: with
    microsleep off ``replay_index`` stays -1 and the lattice draws from its own RNG
    stream, so a different trajectory leaves the physics fields exactly as they were."""
    base = _hashes(EngineConfig.research())
    coupled = EngineConfig.research()
    coupled.criticality.coupling = 0.30
    changed = _hashes(coupled)
    assert changed["behaviour"] == base["behaviour"]
    assert changed["physics"] != base["physics"]
    biased = EngineConfig.research()
    biased.basal_ganglia.forward_bias = 0.7
    changed = _hashes(biased)
    assert changed["behaviour"] != base["behaviour"]
    assert changed["physics"] == base["physics"]


def test_the_two_split_payloads_partition_the_full_tick() -> None:
    td = Engine(seed=DEFAULT_SEED).run(3)[-1]
    full = hash_payload(td, "full")
    behaviour = hash_payload(td, "behaviour")
    physics = hash_payload(td, "physics")
    assert set(full) == {f.name for f in fields(TickData)}
    assert set(physics) == {"tick", *PHYSICS_FIELDS}
    assert set(behaviour) == set(full) - set(PHYSICS_FIELDS)
    assert set(behaviour) & set(PHYSICS_FIELDS) == set()
    assert list(physics) == ["tick", *PHYSICS_FIELDS]  # fixed order
    for key in physics:
        assert physics[key] == full[key]
    for key in behaviour:
        assert behaviour[key] == full[key]
    assert hash_payload({"tick": 4, "atp": 0.5}, "behaviour") == {"tick": 4, "atp": 0.5}
    with pytest.raises(KeyError):
        hash_payload({"tick": 4, "atp": 0.5}, "physics")  # a physics field is missing


def test_the_full_kind_is_the_historical_hash() -> None:
    trace = Engine(seed=DEFAULT_SEED).run(5)
    for td in trace:
        expected = hashlib.sha256(_canonical_json(_normalize_tick(td)).encode("utf-8")).hexdigest()
        assert tick_hash(td) == tick_hash(td, "full") == expected
    assert RunHash().kind == "full"
    default_run, full_run = RunHash(), RunHash("full")
    for td in trace:
        assert default_run.update(td) == full_run.update(td) == tick_hash(td)
    assert default_run.hexdigest() == full_run.hexdigest() == hash_trace(trace)[-1]["hash"]


def test_unknown_kinds_and_profiles_are_rejected() -> None:
    td = TickData()
    with pytest.raises(ValueError):
        tick_hash(td, "nope")
    with pytest.raises(ValueError):
        RunHash("nope")
    with pytest.raises(ValueError):
        baseline_path("legacy", "nope")
    with pytest.raises(ValueError):
        baseline_path("nope", "full")
