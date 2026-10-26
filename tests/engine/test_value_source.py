"""The value source the steering reads (M2b step 4, docs/prereg/m2b_gate.md): "tabular" (as before), "sr" (V = M R
over the place code, learned online) and "none" (no value steering)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from brain.systems.successor_features import normalised
from core.config import VALUE_SOURCES, EngineConfig, ValueMemoryConfig
from core.engine import Engine, EngineContext


def _cfg(source: str, place: bool = True) -> EngineConfig:
    cfg = EngineConfig.research()
    cfg.place.enabled = place
    cfg.value_memory.source = source
    return cfg


def test_the_sources_and_their_requirements() -> None:
    assert VALUE_SOURCES == ("tabular", "sr", "none") and ValueMemoryConfig().source == "tabular"
    with pytest.raises(ValueError):
        ValueMemoryConfig(source="model")
    with pytest.raises(ValueError):
        Engine(seed=1, config=_cfg("sr", place=False))
    assert EngineConfig.legacy().value_memory.source == "tabular"
    assert EngineConfig.research().value_memory.source == "sr"  # since M2b's exit (decisions G37)
    eng = Engine(seed=1, config=_cfg("tabular"))
    assert eng.sr is None and eng.sr_weights is None


def test_the_sr_source_learns_online_and_reads_v_equals_phi_dot_mt_r() -> None:
    cfg = _cfg("sr")
    cfg.place.reward_rule = "nlms"  # the rule this test's arithmetic states; per_feature is the default since G37 (tested below)
    eng = Engine(seed=2, config=cfg)
    eng.run(50, reset=True)
    assert eng.sr.updates == 49 and not np.any(eng.sr_weights)  # no reward yet: R stays 0
    # A rewarded arrival: the reward weights move toward the reward at the arrival's features.
    phi = normalised(eng.place_rates)
    before = float(np.sum(phi * eng.sr_weights))
    eng._sr_learn(1.0)
    after = float(np.sum(normalised(eng.place_rates) * eng.sr_weights))
    assert after - before == pytest.approx(0.5 * (1.0 - before))  # normalised LMS at rate 0.5
    st = eng.spatial.state
    u = np.sum(eng.sr.M * eng.sr_weights[:, None], axis=0)
    assert eng.sr_value(st.grid_x, st.grid_y) == pytest.approx(float(np.sum(normalised(eng.place.rates(st.grid_x, st.grid_y)) * u)))
    assert eng._value_at(st.grid_x, st.grid_y) == eng.sr_value(st.grid_x, st.grid_y)
    far = (-st.grid_x * 0.0 - 9.0, -9.0) if st.grid_x > 0 else (9.0, 9.0)
    assert eng.sr_value(st.grid_x, st.grid_y) > eng.sr_value(*far)
    # The episode boundary: no transition links across it.
    eng.reset_value_episode()
    assert eng._sr_prev is None and eng.value_memory._prev_cell is None
    n = eng.sr.updates
    eng.run(1)
    assert eng.sr.updates == n  # the first tick after a boundary has no predecessor
    eng.run(1)
    assert eng.sr.updates == n + 1


def test_none_gives_no_value_steering_and_tabular_reads_the_map() -> None:
    eng = Engine(seed=3, config=_cfg("none", place=False))
    eng.run(5, reset=True)
    eng.value_memory.values[(0, 0)] = 5.0
    ctx = EngineContext(tick=0)
    ctx.grid_x, ctx.grid_y, ctx.hd_angle = 0.25, 0.25, 0.0
    assert eng._value_signals(ctx) == (0.0, 0.0, 0.0)
    tab = Engine(seed=3, config=_cfg("tabular", place=False))
    tab.run(5, reset=True)
    tab.value_memory.values[(2, 0)] = 5.0
    assert tab._value_at(1.25, 0.25) == 5.0 and tab._value_at(-3.0, 0.0) == tab.value_memory.value_of(tab.spatial.bins_at(-3.0, 0.0))
    assert tab._value_signals(ctx) != (0.0, 0.0, 0.0)


def test_the_exploratory_per_feature_reward_rule_keeps_r_non_negative() -> None:
    """decisions G36: the preregistered NLMS rule rings a point reward with negative weights; the exploratory
    per-feature rule moves each weight toward the reward seen while its cell is active, so R >= 0 when r >= 0."""
    from core.config import REWARD_RULES, PlaceConfig

    assert REWARD_RULES == ("nlms", "per_feature") and PlaceConfig().reward_rule == "nlms"
    with pytest.raises(ValueError):
        PlaceConfig(reward_rule="td")
    results = {}
    for rule in REWARD_RULES:
        cfg = _cfg("sr")
        cfg.place.reward_rule = rule
        eng = Engine(seed=4, config=cfg)
        eng.run(20, reset=True)
        eng._sr_learn(1.0)  # one rewarded arrival, then unrewarded ticks nearby
        for _ in range(30):
            eng.run(1)
        results[rule] = eng.sr_weights.copy()
    assert float(results["per_feature"].min()) >= 0.0 and float(results["per_feature"].max()) > 0.0
    assert float(results["nlms"].min()) < 0.0  # the ring
