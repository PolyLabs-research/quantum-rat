"""Dopamine's tonic level as a rate (G61): the reward rate and the energy rate against the held peak (G56)."""

from __future__ import annotations

import math

import pytest

from brain.systems.neuromodulators import BiologicalNeuromodulators
from core.config import EngineConfig, NeuromodConfig
from core.engine import Engine


def _da(**kw) -> NeuromodConfig:
    return NeuromodConfig(model="biological", dopamine=True, **kw)


def _step(nm, reward=0.0, energy=0.0):
    return nm.update(delta=0.0, reward=reward, pain=0.0, novelty=0.0, moving=False, asleep=False, satiety=0.0, energy=energy)


def test_peak_is_the_default_and_holds_the_last_meal() -> None:
    assert NeuromodConfig().tonic_model == "peak" and EngineConfig.research().neuromod.tonic_model == "peak"
    nm = BiologicalNeuromodulators(_da())
    _step(nm, reward=0.8)
    assert nm.tonic == 0.8 and nm.vigour() == pytest.approx(0.9)
    _step(nm)
    assert nm.tonic == pytest.approx(0.8 * math.exp(-1 / 600))


def test_the_reward_rate_is_a_leaky_mean_over_its_reference() -> None:
    nm = BiologicalNeuromodulators(_da(tonic_model="reward_rate", rate_time=3000.0, rate_ref=0.01))
    for _ in range(150):  # one reward of 1 every 200 ticks: a rate of 0.005, half the reference
        for k in range(200):
            _step(nm, reward=1.0 if k == 0 else 0.0)
    assert nm.rate == pytest.approx(0.005, rel=0.1) and nm.vigour() == pytest.approx(0.75, abs=0.03)
    nm.rate = 0.05  # above the reference: full vigour
    _step(nm)
    assert nm.vigour() == 1.0


def test_the_energy_rate_reads_income_against_the_cost_of_running() -> None:
    nm = BiologicalNeuromodulators(_da(tonic_model="energy_rate", rate_time=10.0), energy_ref=0.002)
    for _ in range(200):
        _step(nm, reward=5.0, energy=0.001)  # the reward's size does not enter
    assert nm.tonic == pytest.approx(0.5, abs=1e-6) and nm.vigour() == pytest.approx(0.75, abs=1e-6)
    with pytest.raises(ValueError):
        BiologicalNeuromodulators(_da(tonic_model="energy_rate"))  # no cost to read income against


def test_validation_and_the_engine_wiring() -> None:
    with pytest.raises(ValueError):
        NeuromodConfig(tonic_model="mean")
    with pytest.raises(ValueError):
        _da(tonic_model="reward_rate")  # no reference
    with pytest.raises(ValueError):
        _da(rate_time=0.0)
    cfg = EngineConfig.research()
    for key, value in {"metabolism.enabled": True, "neuromod.model": "biological", "neuromod.dopamine": True,
                       "neuromod.tonic_model": "energy_rate"}.items():
        cfg.set_field(key, value)
    e = Engine(seed=1, config=cfg)
    m = cfg.metabolism
    assert e.bio_neuromod._rate_ref == pytest.approx(m.basal_cost * (1 + m.locomotion_factor))
    e.run(20, reset=True)
    assert 0.5 <= e.context.vigour <= 1.0
