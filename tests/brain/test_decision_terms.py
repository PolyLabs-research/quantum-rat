"""The decision as its terms (brain.systems.basal_ganglia.channel_terms) and the selection probabilities: readouts
that agree with the scores the engine decides on (decisions G39)."""

import math

from brain.systems.basal_ganglia import ACTION_ORDER, argmax_action, channel_terms, selection_probabilities
from core.config import EngineConfig
from core.engine import Engine


def _terms_for(eng: Engine):
    ctx = eng.context
    bg = eng.config.basal_ganglia
    pacing_rest = bg.pace_rest_bonus if ctx.pacing_active else 0.0
    return channel_terms(ctx.observation, ctx.wm_novelty, ctx.trn_gate_value, ctx.microsleep_active, bg, ctx.neuromodulators,
                         *ctx.value_signals, ctx.criticality_gain, ctx.freeze_habituation, pacing_rest,
                         ctx.previous_action)


def test_the_terms_sum_to_the_engines_scores_on_both_profiles_asleep_and_paced():
    paced = EngineConfig()
    paced.basal_ganglia.pace_rest_bonus = 5.0
    corridor = EngineConfig.research()  # the turn commitment's term (G45) on a narrow track, where it fires
    corridor.world.bounds = (10.0, 0.5)
    corridor.basal_ganglia.wall_avoid_range = 1.0 / 6.0
    corridor.basal_ganglia.turn_commitment = 0.3
    seen = {"asleep": 0, "paced": 0, "committed": 0}
    for cfg, ticks in ((EngineConfig.legacy(), 1500), (EngineConfig.research(), 400), (paced, 600), (corridor, 600)):
        eng = Engine(seed=5, config=cfg)
        for _ in range(ticks):
            eng.run(1)
            ctx = eng.context
            terms = _terms_for(eng)
            seen["asleep"] += ctx.microsleep_active
            seen["paced"] += ctx.pacing_active
            seen["committed"] += any(t.get("commit", 0.0) > 0.0 for t in _terms_for(eng).values())
            assert set(terms) == set(ctx.action_scores)
            for channel, score in ctx.action_scores.items():
                assert math.isclose(sum(terms[channel].values()), score, abs_tol=1e-12), (channel, terms[channel], score)
            if ctx.microsleep_active:
                assert terms == {"REST": {"microsleep": 1.0}}
    assert seen["asleep"] > 0 and seen["paced"] > 0 and seen["committed"] > 0  # every branch was exercised


def test_selection_probabilities_are_the_softmax_weights_or_the_argmax():
    scores = {"FORWARD": 1.0, "TURN_LEFT": 0.9, "TURN_RIGHT": 0.2, "REST": 0.0}
    p0 = selection_probabilities(scores, 0.0)
    assert p0 == {"FORWARD": 1.0, "TURN_LEFT": 0.0, "TURN_RIGHT": 0.0, "REST": 0.0}
    tie = dict(scores, TURN_LEFT=1.0)
    assert selection_probabilities(tie, 0.0)[argmax_action(tie)] == 1.0  # the argmax's tie order
    p = selection_probabilities(scores, 0.1)
    assert list(p) == list(ACTION_ORDER) and math.isclose(sum(p.values()), 1.0, abs_tol=1e-12)
    assert math.isclose(p["TURN_LEFT"] / p["FORWARD"], math.exp(-1.0), rel_tol=1e-9)  # exp((0.9 - 1.0) / 0.1)
    assert p["FORWARD"] > p["TURN_LEFT"] > p["TURN_RIGHT"] > p["REST"] > 0.0
    asleep = selection_probabilities({"REST": 1.0}, 0.1)
    assert asleep["REST"] == 1.0 and asleep["FORWARD"] == 0.0  # an unscored channel has weight 0
    assert selection_probabilities({}, 0.1) == {name: 0.0 for name in ACTION_ORDER}
