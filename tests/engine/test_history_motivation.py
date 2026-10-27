"""History and motivation in the engine (G52): off by default; on, the drive reaches action selection."""

from __future__ import annotations

import pytest

from brain.systems.basal_ganglia import channel_terms
from core.config import EngineConfig
from core.engine import Engine


def test_off_by_default() -> None:
    for cfg in (EngineConfig.legacy(), EngineConfig.research()):
        assert not cfg.history.enabled and not cfg.motivation.enabled
    e = Engine(seed=1, config=EngineConfig.research())
    e.run(5)
    assert e.history is None and e.motivation is None and e.context.motivation == 1.0


def test_motivation_needs_the_visit_channel_and_history_needs_the_place_code() -> None:
    cfg = EngineConfig.research()
    cfg.motivation.enabled = True
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)
    cfg = EngineConfig.legacy()
    cfg.history.enabled = True
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)


def test_an_agent_with_nothing_to_move_for_rests_and_the_terms_still_sum() -> None:
    cfg = EngineConfig.research()
    cfg.history.enabled = True
    cfg.motivation.enabled = True
    cfg.history.visit_familiarisation = 1.0  # everything familiar at once: curiosity never rises
    e = Engine(seed=2, config=cfg)
    trace = e.run(300)
    rest = sum(t.action_name == "REST" for t in trace[100:]) / 200
    assert e.context.motivation < 0.05 and rest > 0.5
    ctx = e.context
    terms = channel_terms(ctx.observation, ctx.wm_novelty, ctx.trn_gate_value, ctx.microsleep_active, e.config.basal_ganglia,
                          ctx.neuromodulators, *ctx.value_signals, ctx.criticality_gain, ctx.freeze_habituation, 0.0,
                          ctx.previous_action, ctx.motivation)
    for ch, parts in terms.items():
        assert sum(parts.values()) == pytest.approx(ctx.action_scores[ch])
    assert terms["REST"]["idle"] > 0.9
