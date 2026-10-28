"""Motivation (G52): loops with their own delays and time constants, composed into a drive to move."""

from __future__ import annotations

import math

import pytest

from brain.systems.motivation import REASONS, Loop, LoopSpec, Motivation, default_loops
from core.config import MotivationConfig


def test_a_follow_loop_rises_and_falls_at_its_own_rates() -> None:
    loop = Loop(LoopSpec("x", "s", "follow", tau_rise=1.0, tau_fall=100.0))
    assert loop.step(1.0) == pytest.approx(1.0 - math.exp(-1.0))
    for _ in range(20):
        loop.step(1.0)
    high = loop.value
    assert loop.step(0.0) == pytest.approx(high * math.exp(-0.01))


def test_an_accumulating_loop_sums_events_after_its_delay() -> None:
    loop = Loop(LoopSpec("s", "meal", "accumulate", gain=0.1, delay=3))
    assert [loop.step(1.0) for _ in range(5)] == pytest.approx([0.0, 0.0, 0.0, 0.1, 0.2])


def test_the_drive_is_a_soft_or_of_the_reasons() -> None:
    m = Motivation(default_loops(MotivationConfig()), hunger_initial=0.0)  # sated: curiosity is its only reason
    assert m.drive == 0.0  # nothing yet: no curiosity, not hungry
    for _ in range(100):
        m.step({"novelty": 1.0})
    assert m.drive > 0.99 and m.reason_levels["forage"] == 0.0
    for _ in range(2000):
        m.step({"novelty": 0.0})  # the place is familiar and it is not hungry: the agent loses its reasons
    assert m.drive < 0.01


def test_hunger_is_a_reason_on_its_own_and_the_reward_trace_sets_vigour() -> None:
    m = Motivation(default_loops(MotivationConfig()), hunger_initial=1.0)
    assert m.drive == pytest.approx(1.0) and m.reason_levels["forage"] == 1.0  # food-restricted: a reason before any find (G53)
    assert m.vigour() == pytest.approx(0.5)  # nothing found lately: it works at the floor of its vigour
    m.step({"novelty": 0.0, "reward": 1.0, "meal": 1.0})
    assert m.vigour() > 0.8  # a reward lifts the expectation, and the vigour, at once
    for _ in range(400):
        m.step({"meal": 1.0, "reward": 1.0})  # a meal a tick: after the gut's delay the satiety accumulates
    assert m.hunger() < 0.05 and m.reason_levels["forage"] < 0.05  # sated: hunger is no reason any more
    with pytest.raises(ValueError):
        Motivation(default_loops(MotivationConfig()), vigour_floor=1.5)


def test_reasons_are_a_registry() -> None:
    assert {"explore", "forage"} <= set(REASONS)
    with pytest.raises(ValueError):
        Motivation(default_loops(MotivationConfig()), reasons=("escape",))
