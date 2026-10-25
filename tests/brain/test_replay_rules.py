"""Replay rules over a transition memory (brain/systems/replay_rules.py; docs/m2a_linear_track.md).

Each test is named for what it proves: the three rules pick what they say, every rule
spends exactly the budget it is given, no backup links two episodes, the draws come
from the one stream handed in, the direction label is the plan's slope sign, and the
learner's ``td_error`` is ``update`` without the write.
"""

from __future__ import annotations

import math
from typing import List

import pytest

from brain.systems.replay_events import (
    DIRECTION_FORWARD,
    DIRECTION_NEITHER,
    DIRECTION_REVERSE,
    RULE_PRIORITISED_TD,
    RULE_REVERSE_TRAJECTORY,
    RULE_UNIFORM,
    TRIGGER_REWARD,
)
from brain.systems.replay_rules import (
    PrioritisedTDReplay,
    ReverseTrajectoryReplay,
    StoredTransition,
    TransitionMemory,
    UniformReplay,
    make_rule,
    replay,
    replay_thresholded,
    sequence_direction,
)
from brain.systems.value_learners import LinearTDLambda, TabularTD0, chain_features
from core.rng import RNG

BIN = 0.5
GAMMA = 0.9
LR = 0.2


def _learner() -> TabularTD0:
    return TabularTD0(bin_size=BIN, learning_rate=LR, discount=GAMMA)


def _x(cell: int) -> float:
    return BIN * (cell + 0.5)


def _episode(memory: TransitionMemory, learner: TabularTD0, episode: int, cells: List[int], reward: float = 1.0) -> None:
    """Store a path through ``cells`` (y = 0.25) ending in a terminal consume at the last cell, without learning."""
    for k in range(len(cells) - 1):
        memory.append(StoredTransition(_x(cells[k]), 0.25, 0.0, _x(cells[k + 1]), 0.25, False, episode, k, learner.cell(_x(cells[k]), 0.25)))
    last = cells[-1]
    memory.append(StoredTransition(_x(last), 0.25, reward, _x(last), 0.25, True, episode, len(cells) - 1, learner.cell(_x(last), 0.25)))


def test_td_error_is_update_without_the_write_for_both_learners() -> None:
    tab = _learner()
    tab.values[(3, 0)] = 0.5
    before = dict(tab.values)
    delta = tab.td_error(_x(2), 0.25, 0.0, _x(3), 0.25, False)
    assert delta == pytest.approx(GAMMA * 0.5) and tab.values == before
    assert tab.td_error(_x(3), 0.25, 1.0, _x(3), 0.25, True) == pytest.approx(0.5)  # terminal: reward - V(s)
    assert tab.update(_x(2), 0.25, 0.0, _x(3), 0.25, False) == pytest.approx(delta)
    assert tab.values[(2, 0)] == pytest.approx(LR * delta)
    lin = LinearTDLambda(chain_features(0.125), learning_rate=LR, discount=GAMMA)
    lin.weights[:] = 0.3
    w = lin.weights.copy()
    d = lin.td_error(0.25, 0.25, 0.0, 0.75, 0.25, False)
    assert d == pytest.approx(GAMMA * 0.3 - 0.3) and (lin.weights == w).all()
    assert lin.update(0.25, 0.25, 0.0, 0.75, 0.25, False) == pytest.approx(d)


def test_the_memory_is_bounded_and_keeps_episodes_apart() -> None:
    memory = TransitionMemory(5)
    learner = _learner()
    _episode(memory, learner, 0, [0, 1, 2])  # 3 transitions
    _episode(memory, learner, 1, [2, 1, 0])  # 3 more: the oldest of episode 0 falls out
    assert len(memory) == 5 and memory.capacity == 5
    assert [t.episode for t in memory.all()] == [0, 0, 1, 1, 1]
    assert [t.index for t in memory.episode(1)] == [0, 1, 2]
    assert [t.index for t in memory.episode(0)] == [1, 2]
    assert memory.episode(7) == []
    with pytest.raises(ValueError):
        TransitionMemory(0)


def test_reverse_trajectory_sweeps_the_just_finished_episode_newest_first_and_cycles() -> None:
    memory = TransitionMemory(100)
    learner = _learner()
    _episode(memory, learner, 0, [0, 1, 2, 3])  # an earlier lap, left alone
    _episode(memory, learner, 1, [3, 4, 5, 6, 7])  # the lap that just ended: 4 moves + a consume at 7
    stream = RNG(1).stream("replay")
    before = stream.getstate()
    outcome = replay(make_rule(RULE_REVERSE_TRAJECTORY), memory, learner, 7, 1, stream, tick=99, travel_sign=1)
    assert [t.cell[0] for t in outcome.transitions] == [7, 6, 5, 4, 3, 7, 6]  # newest first, then round again
    assert all(t.episode == 1 for t in outcome.transitions)
    assert stream.getstate() == before  # no draw: the sweep is deterministic
    assert outcome.event.rule == RULE_REVERSE_TRAJECTORY and outcome.event.trigger == TRIGGER_REWARD
    assert outcome.event.n_backups == 7 == len(outcome.event.cells) and outcome.event.span == 5
    assert outcome.event.tick_start == outcome.event.tick_end == 99
    # The first backup is the consume (reward 1.0 into a fresh table: delta 1.0), then the chain fills in.
    assert outcome.deltas[0] == pytest.approx(1.0) and outcome.deltas[1] == pytest.approx(GAMMA * LR)
    assert learner.values[(7, 0)] > learner.values[(6, 0)] > learner.values[(5, 0)] > 0.0
    assert (3, 0) in learner.values and (0, 0) not in learner.values  # nothing of episode 0 was touched
    # The replayed cells run opposite to the body's travel (east, +1): a reverse sequence.
    assert outcome.event.direction == DIRECTION_REVERSE and outcome.sequence_r < 0
    with pytest.raises(ValueError):
        replay(make_rule(RULE_REVERSE_TRAJECTORY), memory, learner, 3, 9, stream, tick=0)  # no such episode in memory


def test_uniform_draws_every_stored_transition_with_replacement_from_the_given_stream() -> None:
    memory = TransitionMemory(100)
    learner = _learner()
    _episode(memory, learner, 0, [0, 1, 2, 3, 4])
    _episode(memory, learner, 1, [4, 3, 2, 1, 0])
    stream = RNG(2).stream("replay")
    reference = RNG(2).stream("replay")
    outcome = replay(make_rule(RULE_UNIFORM), memory, learner, 400, 1, stream, tick=0, travel_sign=-1)
    for _ in range(400):
        reference.random()
    assert stream.getstate() == reference.getstate()  # exactly one random() per backup
    stored = set(memory.all())
    assert set(outcome.transitions) <= stored
    assert len(set(outcome.transitions)) == len(stored)  # 400 draws over 10 items: every one drawn (with replacement)
    assert {t.episode for t in outcome.transitions} == {0, 1}
    assert outcome.event.span == 10 and outcome.n_backups == 400


def test_prioritised_draws_in_proportion_to_the_current_td_error_and_refreshes_it() -> None:
    memory = TransitionMemory(100)
    learner = _learner()
    _episode(memory, learner, 0, [0, 1, 2, 3])  # three zero-reward moves and a consume at cell 3
    rule = PrioritisedTDReplay(epsilon=1e-6)
    stream = RNG(3).stream("replay")
    # Fresh table: only the consume has a TD error (1.0); the others have 0 + epsilon.
    rule.begin(memory, 0)
    first = rule.choose(memory, learner, stream, 0)
    assert first.terminal and first.cell == (3, 0)
    assert rule.last_priorities == pytest.approx([1e-6, 1e-6, 1e-6, 1.0 + 1e-6])
    first.backup(learner)  # V(3) = 0.2: now the move 2 -> 3 has error 0.18 and the consume 0.8
    second = rule.choose(memory, learner, stream, 1)
    assert rule.last_priorities == pytest.approx([1e-6, 1e-6, GAMMA * LR + 1e-6, 1.0 - LR + 1e-6])
    assert second.cell in {(2, 0), (3, 0)}  # the two with error; which one is the stream's draw
    # Over many backups through ``replay`` the error propagates back along the chain: every cell gets value.
    learner = _learner()
    outcome = replay(make_rule(RULE_PRIORITISED_TD), memory, learner, 60, 0, RNG(3).stream("replay"), tick=0)
    assert all(learner.values.get((c, 0), 0.0) > 0.0 for c in range(4))
    assert learner.values[(3, 0)] > learner.values[(2, 0)] > learner.values[(1, 0)] > learner.values[(0, 0)]
    assert outcome.event.rule == RULE_PRIORITISED_TD and outcome.n_backups == 60
    # Proportional sampling: with one transition's error 1 and three at 0, the first draw is that
    # one for every stream (the epsilon mass is 3e-6).
    for seed in range(20):
        fresh = _learner()
        rule.begin(memory, 0)
        assert rule.choose(memory, fresh, RNG(seed).stream("replay"), 0).cell == (3, 0)
    with pytest.raises(ValueError):
        PrioritisedTDReplay(epsilon=0.0)


def test_every_rule_spends_exactly_the_budget_and_never_links_two_episodes() -> None:
    memory = TransitionMemory(1000)
    learner = _learner()
    _episode(memory, learner, 0, [0, 1, 2, 3, 4, 5])
    _episode(memory, learner, 1, [5, 4, 3, 2, 1, 0])
    stored = {(t.x, t.y, t.x_next, t.y_next, t.terminal, t.episode) for t in memory.all()}
    for name in (RULE_UNIFORM, RULE_REVERSE_TRAJECTORY, RULE_PRIORITISED_TD):
        for budget in (1, 7, 20):
            fresh = _learner()
            outcome = replay(make_rule(name), memory, fresh, budget, 1, RNG(5).stream("replay"), tick=0, travel_sign=-1)
            assert outcome.n_backups == budget == outcome.event.n_backups == len(outcome.deltas)
            # Each backup is one stored transition as stored: its own successor, its own terminal flag.
            assert all((t.x, t.y, t.x_next, t.y_next, t.terminal, t.episode) in stored for t in outcome.transitions)
            # The learner received exactly ``budget`` writes: replaying the same transitions by hand reproduces it.
            check = _learner()
            for t in outcome.transitions:
                t.backup(check)
            assert check.values == fresh.values
    with pytest.raises(ValueError):
        replay(make_rule(RULE_UNIFORM), memory, _learner(), 0, 1, RNG(5).stream("replay"), tick=0)
    with pytest.raises(ValueError):
        make_rule("gain_need")


def test_sequence_direction_is_the_slope_sign_against_the_travel_direction() -> None:
    assert sequence_direction([0.25, 0.75, 1.25], 1) == (DIRECTION_FORWARD, pytest.approx(1.0))
    assert sequence_direction([0.25, 0.75, 1.25], -1) == (DIRECTION_REVERSE, pytest.approx(-1.0))
    assert sequence_direction([1.25, 0.75, 0.25], 1) == (DIRECTION_REVERSE, pytest.approx(-1.0))
    direction, r = sequence_direction([0.25, 1.25, 0.75], 1)
    assert direction == DIRECTION_FORWARD and 0.0 < r < 1.0
    assert sequence_direction([0.75, 0.75, 0.75], 1) == (DIRECTION_NEITHER, 0.0)  # no spread
    assert sequence_direction([0.75], 1) == (DIRECTION_NEITHER, 0.0)  # one backup
    assert sequence_direction([], -1) == (DIRECTION_NEITHER, 0.0)
    assert sequence_direction([0.25, 0.75, 0.25], 1) == (DIRECTION_NEITHER, 0.0)  # symmetric: slope exactly 0
    with pytest.raises(ValueError):
        sequence_direction([0.25, 0.75], 2)
    # A cycling reverse sweep (budget longer than the lap) lowers |r| below 1 but keeps the sign.
    memory = TransitionMemory(100)
    learner = _learner()
    _episode(memory, learner, 0, [0, 1, 2])
    outcome = replay(make_rule(RULE_REVERSE_TRAJECTORY), memory, learner, 5, 0, RNG(1).stream("replay"), tick=0, travel_sign=1)
    assert outcome.event.direction == DIRECTION_REVERSE and -1.0 < outcome.sequence_r < 0.0
    assert math.isfinite(outcome.sequence_r)


# --- the thresholded budget (M2a step 2; docs/prereg/rq1_track_tabular.md) --------------------------------------


def test_each_rule_reports_the_priority_the_thresholded_mode_compares() -> None:
    memory = TransitionMemory(100)
    learner = _learner()
    _episode(memory, learner, 0, [0, 1, 2, 3])  # three zero-error moves and a consume with error 1
    stream = RNG(1).stream("replay")
    uniform, reverse, prio = make_rule(RULE_UNIFORM), make_rule(RULE_REVERSE_TRAJECTORY), make_rule(RULE_PRIORITISED_TD)
    for rule in (uniform, reverse, prio):
        rule.begin(memory, 0)
    assert uniform.priority(memory, learner, 0) == pytest.approx(1.0 / 4)  # the mean |TD error| over memory
    assert prio.priority(memory, learner, 0) == pytest.approx(1.0)  # the largest
    assert reverse.priority(memory, learner, 0) == pytest.approx(1.0)  # the next of its sweep: the consume
    assert reverse.priority(memory, learner, 1) == pytest.approx(0.0)  # then the move into the goal, still 0 before any backup
    assert reverse.priority(memory, learner, 4) == 0.0  # beyond one pass: nothing
    reverse.choose(memory, learner, stream, 0).backup(learner)  # V(3) = 0.2
    assert reverse.priority(memory, learner, 1) == pytest.approx(GAMMA * LR)
    assert prio.priority(memory, learner, 0) == pytest.approx(1.0 - LR)
    assert uniform.priority(TransitionMemory(5), learner, 0) == 0.0 and prio.priority(TransitionMemory(5), learner, 0) == 0.0


def test_thresholded_replay_runs_while_the_priority_exceeds_the_threshold_up_to_the_cap() -> None:
    memory = TransitionMemory(100)
    learner = _learner()
    _episode(memory, learner, 0, [0, 1, 2, 3, 4, 5, 6, 7])  # errors along the sweep: 1, 0.18, 0.032, 0.0058, ...
    stream = RNG(1).stream("replay")
    outcome = replay_thresholded(make_rule(RULE_REVERSE_TRAJECTORY), memory, learner, 0.02, 100, 0, stream, tick=5, travel_sign=1)
    assert outcome is not None and outcome.n_backups == 3  # 1 > 0.02, 0.18 > 0.02, 0.032 > 0.02, 0.0058 stops it
    assert [t.cell[0] for t in outcome.transitions] == [7, 6, 5]
    assert outcome.event.trigger == TRIGGER_REWARD and outcome.event.direction == DIRECTION_REVERSE
    # A lower threshold runs further (the chain of errors is 1, 0.18, 0.032, 0.0058, 0.00105, 0.00019, 0.000034:
    # six exceed 1e-4); the cap binds first when it is small; one pass at most for the sweep.
    assert replay_thresholded(make_rule(RULE_REVERSE_TRAJECTORY), memory, _learner(), 1e-4, 100, 0, stream, tick=0).n_backups == 6
    assert replay_thresholded(make_rule(RULE_REVERSE_TRAJECTORY), memory, _learner(), 1e-4, 2, 0, stream, tick=0).n_backups == 2
    assert replay_thresholded(make_rule(RULE_REVERSE_TRAJECTORY), memory, _learner(), 0.0, 100, 0, stream, tick=0).n_backups == 8
    # Nothing above the threshold: no backup, no event, None.
    learned = _learner()
    replay_thresholded(make_rule(RULE_REVERSE_TRAJECTORY), memory, learned, 0.0, 100, 0, stream, tick=0)
    for _ in range(50):  # drive the table to its fixed point on this episode
        replay(make_rule(RULE_REVERSE_TRAJECTORY), memory, learned, 8, 0, stream, tick=0)
    assert replay_thresholded(make_rule(RULE_REVERSE_TRAJECTORY), memory, learned, 0.02, 100, 0, stream, tick=0) is None
    # The prioritised rule follows the error wherever it moves; the uniform rule's mean sits below a modest threshold.
    prio = replay_thresholded(make_rule(RULE_PRIORITISED_TD), memory, _learner(), 0.02, 100, 0, RNG(2).stream("replay"), tick=0)
    assert prio is not None and 1 <= prio.n_backups <= 100 and prio.transitions[0].terminal
    assert replay_thresholded(make_rule(RULE_UNIFORM), memory, _learner(), 0.2, 100, 0, RNG(2).stream("replay"), tick=0) is None
    uni = replay_thresholded(make_rule(RULE_UNIFORM), memory, _learner(), 0.1, 100, 0, RNG(2).stream("replay"), tick=0)
    assert uni is not None and uni.n_backups >= 1  # the mean |error| 1/8 exceeds 0.1 until the consume is backed up
    with pytest.raises(ValueError):
        replay_thresholded(make_rule(RULE_UNIFORM), memory, _learner(), 0.1, 0, 0, stream, tick=0)
    with pytest.raises(ValueError):
        replay_thresholded(make_rule(RULE_UNIFORM), memory, _learner(), -0.1, 10, 0, stream, tick=0)
    # The pre-run trigger is a name the event carries.
    out = replay_thresholded(make_rule(RULE_REVERSE_TRAJECTORY), memory, _learner(), 0.02, 100, 0, stream, tick=0, trigger="pre_run")
    assert out is not None and out.event.trigger == "pre_run"
