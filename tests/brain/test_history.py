"""History (G52): decaying place-tagged traces fed by channels, and a learned schema of what they mean for reward."""

from __future__ import annotations

import math

import numpy as np
import pytest

from brain.systems.history import CHANNELS, History, HistoryInputs, HistorySettings


def _inputs(here, reward=0.0, vision=(), estimate=(0.0, 0.0, 0.0), rates_at=None):
    return HistoryInputs(here=np.asarray(here, dtype=float), primary_reward=reward, vision=list(vision), estimate=estimate,
                         rates_at=rates_at or (lambda x, y: np.zeros(len(here))))


def test_taste_writes_where_the_agent_ate_and_decays_on_each_timescale() -> None:
    h = History(3, HistorySettings(channels=("taste",), taste_timescales=(10.0, 100.0), reward_context=()))
    h.write(_inputs([1.0, 0.5, 0.0], reward=1.0))
    assert h.banks["taste"].traces[:, 0].tolist() == [1.0, 1.0] and h.banks["taste"].traces[0, 1] == 0.5
    h.decay()
    assert h.banks["taste"].traces[0, 0] == pytest.approx(math.exp(-0.1))
    assert h.banks["taste"].traces[1, 0] == pytest.approx(math.exp(-0.01))
    h.write(_inputs([1.0, 0.5, 0.0], reward=0.0))  # no meal, no event
    assert h.events_this_tick["taste"] == 0


def test_visit_builds_familiarity_slowly() -> None:
    h = History(2, HistorySettings(channels=("visit",), visit_familiarisation=50.0, reward_context=()))
    for _ in range(50):
        h.decay()
        h.write(_inputs([1.0, 0.0]))
    fam = h.familiarity(np.array([1.0, 0.0]))
    assert 0.55 < fam < 0.7 and h.familiarity(np.array([0.0, 1.0])) == 0.0


def test_sight_writes_at_the_seen_target() -> None:
    seen = []
    h = History(2, HistorySettings(channels=("sight",), sight_timescales=(10.0,), reward_context=()))
    h.write(_inputs([1.0, 0.0], vision=[(0.0, "target", 3.0), (0.5, "wall", 2.0)], estimate=(1.0, 2.0, 0.0),
                    rates_at=lambda x, y: (seen.append((x, y)), np.array([0.0, 1.0]))[1]))
    assert seen == [(4.0, 2.0)] and h.banks["sight"].traces[0].tolist() == [0.0, 1.0]


def test_the_schema_learns_that_a_place_just_eaten_at_is_empty() -> None:
    h = History(1, HistorySettings(channels=("taste",), taste_timescales=(10.0,), reward_context=("taste",)))
    phi = np.array([1.0])
    weights = np.array([1.0])  # the place has been rewarding
    for _ in range(200):  # eat, then come straight back to nothing
        h.write(_inputs([1.0], reward=1.0))
        errors = 0.0 - (weights + h.reward_adjustment())
        h.learn_schema(phi, errors, 0.5)
    assert h.schema["taste"][0] < -0.5  # just after eating here, expect little here


def test_unknown_or_inconsistent_channels_are_refused() -> None:
    with pytest.raises(ValueError):
        History(2, HistorySettings(channels=("smell",)))
    with pytest.raises(ValueError):
        History(2, HistorySettings(channels=("visit",), reward_context=("taste",)))
    assert {"taste", "visit", "sight"} <= set(CHANNELS)
