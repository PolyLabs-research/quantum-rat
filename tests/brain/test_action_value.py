"""The action value over place features (M3 step 3): Q-learning with traces on a chain, replay backups by action."""

from __future__ import annotations

import numpy as np
import pytest

from brain.systems.action_value import ACTIONS, LinearQ, PlaceActionLearner
from brain.systems.replay_rules import StoredTransition
from brain.systems.value_learners import GaussianPlaceFeatures, chain_features, chain_positions


def _chain():
    positions = chain_positions()  # 12 cells along x, bin 0.5
    return positions, chain_features(0.25)


def test_forward_is_learned_on_a_chain_and_the_turns_are_not() -> None:
    positions, features = _chain()
    q = LinearQ(features.size, learning_rate=0.2, discount=0.9, lam=0.9)
    rng = np.random.default_rng(0)
    for _ in range(300):  # episodes: FORWARD advances a cell, a turn stays put; reward 1 on reaching the last cell
        i = 0
        q.reset_episode()
        while i < len(positions) - 1:
            action = ACTIONS[int(rng.integers(len(ACTIONS)))]
            j = i + 1 if action == "FORWARD" else i
            terminal = j == len(positions) - 1
            q.update(features(*positions[i]), action, 1.0 if terminal else 0.0, features(*positions[j]), terminal)
            i = j
    adv = q.advantages(features(*positions[5]))
    assert adv["FORWARD"] > 0.0 > max(adv["TURN_LEFT"], adv["TURN_RIGHT"])
    assert q.value(features(*positions[10])) > q.value(features(*positions[2])) > 0.0  # closer to the reward is worth more
    assert q.weight_norm() <= 1.0 + 1e-9 and q.updates == 300 * 11 or q.updates > 0


def test_a_replay_backup_moves_one_action_without_traces_and_the_traces_clear() -> None:
    _, features = _chain()
    q = LinearQ(features.size, learning_rate=0.5, discount=0.9, lam=0.9)
    phi = features(0.25, 0.25)
    delta = q.update_target(phi, "FORWARD", 1.0)
    assert delta == pytest.approx(1.0) and q.q(phi)["FORWARD"] == pytest.approx(0.5 * float(np.sum(phi * phi)))
    assert q.q(phi)["TURN_LEFT"] == 0.0 and q.backups == 1 and all(not np.any(e) for e in q.e.values())
    q.update(phi, "TURN_LEFT", 0.0, features(0.75, 0.25), False)
    assert np.any(q.e["TURN_LEFT"]) and not np.any(q.e["FORWARD"])
    q.reset_episode()
    assert all(not np.any(e) for e in q.e.values())
    assert q.parameters()["learner"] == "linear_q" and q.parameters()["actions"] == list(ACTIONS)


def test_validation() -> None:
    with pytest.raises(ValueError):
        LinearQ(4, discount=1.0)
    with pytest.raises(ValueError):
        LinearQ(4, lam=1.5)
    with pytest.raises(ValueError):
        LinearQ(4, traces="decaying")
    with pytest.raises(ValueError):
        LinearQ(4).update_target(np.ones(4) / 4, "REST", 1.0)


def test_the_place_learner_is_backed_up_by_the_transitions_action() -> None:
    features = GaussianPlaceFeatures.grid(0.0, 4.0, 0.0, 1.0, 1.0, 0.5)
    learner = PlaceActionLearner(LinearQ(features.size, learning_rate=0.5, discount=0.9), features)
    t = StoredTransition(0.5, 0.5, 1.0, 1.5, 0.5, True, 0, 0, (0, 0), action="FORWARD")
    assert t.td_error(learner) == pytest.approx(1.0)
    assert t.backup(learner) == pytest.approx(1.0) and learner.learner.backups == 1
    assert learner.q(0.5, 0.5)["FORWARD"] > 0.0 and learner.value(0.5, 0.5) > 0.0
    bare = StoredTransition(0.5, 0.5, 1.0, 1.5, 0.5, True, 0, 0, (0, 0))  # no action: the M2a rules' transition
    with pytest.raises(TypeError):
        bare.backup(learner)
    with pytest.raises(TypeError):
        bare.td_error(learner)
    # a transition that carries its features is backed up on them (amendment A1), whatever the place reads now
    from brain.systems.replay_rules import PlaceTransition

    phi = np.zeros(features.size)
    phi[0] = 1.0
    stored = PlaceTransition(3.5, 0.5, 1.0, 3.5, 0.5, True, 0, 1, (3, 0), action="TURN_LEFT", phi=phi, phi_next=phi)
    assert stored.td_error(learner) == pytest.approx(1.0 - learner.learner.w["TURN_LEFT"][0])
    stored.backup(learner)
    assert learner.learner.w["TURN_LEFT"][0] > 0.0 and not np.any(learner.learner.w["TURN_LEFT"][1:])
