"""The orienting response (M3 step 2, Part 2): a target seen to one side and none ahead turns the agent toward it."""

from __future__ import annotations

import pytest

from brain.contracts import Observation, VisionRay
from brain.systems.basal_ganglia import _channel_scores, channel_terms
from core.config import BasalGangliaConfig


def _obs(rays) -> Observation:
    return Observation(vision_rays=tuple(VisionRay(dist=d, obj_type=k, angle=a) for a, d, k in rays),
                       whisker_hits=(False, False), pain_signal=0.0, forward_delta=0.0, turn_delta=0.0)


LEFT = [(0.0, 1.0, ""), (0.6, 0.6, "target"), (-0.6, 1.0, "")]
AHEAD = [(0.0, 0.6, "target"), (0.6, 1.0, ""), (-0.6, 1.0, "")]


def _scores(rays, gain):
    cfg = BasalGangliaConfig(orient_gain=gain)
    return _channel_scores(_obs(rays), 0.0, 1.0, False, cfg, {}), channel_terms(_obs(rays), 0.0, 1.0, False, cfg, {})


def test_a_target_to_the_left_adds_the_gain_to_the_left_turn_only() -> None:
    off, _ = _scores(LEFT, 0.0)
    on, terms = _scores(LEFT, 1.0)
    assert on["TURN_LEFT"] == pytest.approx(off["TURN_LEFT"] + 1.0)
    assert on["TURN_RIGHT"] == off["TURN_RIGHT"] and on["FORWARD"] == off["FORWARD"]
    assert on["TURN_LEFT"] > on["FORWARD"]  # it outweighs the forward bias: the agent turns to face what it sees
    assert terms["TURN_LEFT"]["orient"] == 1.0 and terms["TURN_RIGHT"]["orient"] == 0.0
    for ch, parts in terms.items():
        assert sum(parts.values()) == pytest.approx(on[ch])


def test_no_orienting_once_the_target_is_ahead_or_when_none_is_seen() -> None:
    off, _ = _scores(AHEAD, 0.0)
    on, _ = _scores(AHEAD, 1.0)
    assert on == off
    none_off, _ = _scores([(0.0, 1.0, ""), (0.6, 1.0, ""), (-0.6, 1.0, "")], 0.0)
    none_on, _ = _scores([(0.0, 1.0, ""), (0.6, 1.0, ""), (-0.6, 1.0, "")], 1.0)
    assert none_on == none_off
