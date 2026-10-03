"""Microsleep replay replays the recent path, most recent first, never across a reset.

Before this change (``value_memory.replay_recent=False``, kept for the legacy
digests) the engine used TRNGate.replay_index, a position in the TRN's
observation buffer (0..replay_window-1), as an index into the value trajectory
counted from its OLDEST end, so sleep replayed transitions ~150-200 ticks old.
Now the engine snapshots the newest ``trn.replay_window`` transitions at sleep
onset and backs up the k-th of them (most recent first) on the k-th replay tick.
TRNGate.replay_index and its TickData logging are unchanged.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from brain.systems.value_memory import ValueMemory
from core.config import EngineConfig
from core.engine import Engine
from metrics.hash import RunHash
from ui.sim_session import SimSession


# ------------------------------------------------------------ ValueMemory unit


def _vm(cells, resets=()) -> ValueMemory:
    vm = ValueMemory(learning_rate=0.5, discount=0.9)
    for i, cell in enumerate(cells):
        if i in resets:
            vm.reset_episode()
        vm.record(cell, 0.0)
    return vm


def test_recent_transitions_are_the_newest_most_recent_first():
    vm = _vm([(i, 0) for i in range(10)])
    assert vm.recent_transitions(3) == [((8, 0), (9, 0), 0.0), ((7, 0), (8, 0), 0.0), ((6, 0), (7, 0), 0.0)]
    assert len(vm.recent_transitions(50)) == 9  # all of them, when fewer exist
    assert vm.recent_transitions(0) == []
    assert _vm([]).recent_transitions(5) == [] and _vm([(0, 0)]).recent_transitions(5) == []


def test_no_transition_spans_an_episode_boundary():
    # 0,1,2 | reset | 3,4 : the 2 -> 3 link is not a transition.
    vm = _vm([(i, 0) for i in range(5)], resets={3})
    pairs = [(a[0], b[0]) for a, b, _ in vm.recent_transitions(10)]
    assert pairs == [(3, 4), (1, 2), (0, 1)]
    assert vm.transition(2) is None and vm.transition(3) == ((3, 0), (4, 0), 0.0)
    # replay_transition and consolidate skip it too: a rewarded start of the
    # second episode never leaks into the end of the first.
    vm.trajectory[3] = ((3, 0), 1.0)
    vm.replay_transition(2)
    vm.consolidate(passes=5)
    assert vm.value_of((2, 0)) == 0.0


def test_boundaries_stay_aligned_when_a_caller_clears_the_trajectory():
    # The maze and the assay clear the trajectory between trials; the boundary
    # flags are aligned at the newest end, so they still match.
    vm = _vm([(i, 0) for i in range(4)])
    vm.trajectory.clear()
    vm.reset_episode()
    for cell in [(10, 0), (11, 0)]:
        vm.record(cell, 0.0)
    vm.reset_episode()
    vm.record((12, 0), 0.0)
    assert [(a[0], b[0]) for a, b, _ in vm.recent_transitions(10)] == [(10, 11)]


def test_consolidate_unchanged_without_boundaries():
    # The explicit sweep of a single episode is exactly the old one.
    cells = [((10, 0), 0.0), ((11, 0), 0.0), ((12, 0), 0.0), ((13, 0), 1.0)]
    vm = ValueMemory(learning_rate=0.3, discount=0.9)
    for cell, r in cells:
        vm.record(cell, r)
    vm.consolidate(passes=5)
    ref = {}
    lr, gamma = 0.3, 0.9
    ref[(10, 0)] = 0.0
    ref.update({(11, 0): 0.0, (12, 0): lr * 1.0})  # the online backup of the rewarded step
    for _ in range(5):
        for i in (2, 1, 0):
            (a, _), (b, r) = cells[i], cells[i + 1]
            ref[a] = ref.get(a, 0.0) + lr * (r + gamma * ref.get(b, 0.0) - ref.get(a, 0.0))
    for cell in ((10, 0), (11, 0), (12, 0)):
        assert vm.value_of(cell) == pytest.approx(ref[cell], abs=1e-12)


# --------------------------------------------------------------- Engine replay


def _replay_log(engine: Engine, ticks: int, before_tick=None):
    """Step ``engine`` and log, per tick, the snapshot it would take now and the
    transitions replay actually backed up."""
    backed: List[Tuple] = []
    original = engine.value_memory.replay_backup

    def spy(transition, dwell_extinction=None):
        backed.append(transition)
        return original(transition, dwell_extinction)

    engine.value_memory.replay_backup = spy  # instance attribute: this engine only
    rows = []
    for _ in range(ticks):
        if before_tick is not None:
            before_tick(engine)
        snapshot = engine.value_memory.recent_transitions(engine.trn_gate.replay_window)
        newest = engine.value_memory.trajectory[-1][0] if engine.value_memory.trajectory else None
        n_before = len(backed)
        td = engine.run(1)[0]
        rows.append((td, snapshot, newest, backed[n_before:], engine.context.replay_cell))
    return rows


def _sleeps(rows):
    """Split the log into runs of consecutive replay ticks."""
    sleeps, current = [], []
    for row in rows:
        if row[0].replay_active:
            current.append(row)
        elif current:
            sleeps.append(current)
            current = []
    if current:
        sleeps.append(current)
    return sleeps


def test_microsleep_replays_the_recent_path_backward_from_a_stable_snapshot():
    engine = Engine(seed=1337)
    rows = _replay_log(engine, 600)
    sleeps = _sleeps(rows)
    assert len(sleeps) >= 2
    grew = False
    for sleep in sleeps:
        onset_snapshot, newest_before = sleep[0][1], sleep[0][2]
        assert onset_snapshot, "the agent had a path to replay"
        # The first replayed transition ends at the newest entry before sleep:
        # the most recent step, not one ~150-200 ticks old.
        assert onset_snapshot[0][1] == newest_before
        for k, (td, snapshot_now, _, backed, cell) in enumerate(sleep):
            # The k-th replay tick backs up transition k of the ONSET snapshot,
            # even though the trajectory keeps growing (and shifting) during sleep.
            expected = onset_snapshot[k % len(onset_snapshot)]
            assert backed == [expected]
            assert cell == expected[0]
            grew |= snapshot_now != onset_snapshot
        # TRN index logging is untouched: it still counts 0, 1, 2, ...
        assert [row[0].replay_index for row in sleep][:3] == [0, 1, 2]
    assert grew, "the trajectory moved during sleep, so the snapshot was actually needed"


def test_replay_cycles_the_snapshot_when_sleep_outlasts_it():
    config = EngineConfig()
    config.trn.replay_window = 4  # 4 transitions, 25-tick sleeps
    engine = Engine(seed=1337, config=config)
    sleeps = _sleeps(_replay_log(engine, 600))
    long_sleep = max(sleeps, key=len)
    assert len(long_sleep) > 8
    snapshot = long_sleep[0][1]
    assert len(snapshot) == 4
    assert [row[3][0] for row in long_sleep] == [snapshot[k % 4] for k in range(len(long_sleep))]


@pytest.mark.parametrize("replay_recent", [True, False])
def test_microsleep_replay_never_links_across_a_reset(replay_recent):
    # An episode boundary before every tick (the value map's part of
    # begin_episode; the full call would also cancel the running action, so the
    # agent would never tire and sleep) leaves no transition inside any
    # episode, so replay (both the new and the legacy indexing) backs up nothing.
    config = EngineConfig()
    config.value_memory.replay_recent = replay_recent
    engine = Engine(seed=1337, config=config)
    rows = _replay_log(engine, 600, before_tick=lambda e: e.value_memory.reset_episode())
    replay_ticks = [row for row in rows if row[0].replay_active]
    assert replay_ticks, "microsleep happened"
    assert all(row[3] == [] and row[4] is None for row in replay_ticks)


def test_default_world_trace_does_not_depend_on_replay_indexing():
    # The default world places no targets, so the value map stays flat and which
    # transitions sleep replays cannot change the TickData stream.
    def digest(replay_recent):
        config = EngineConfig()
        config.value_memory.replay_recent = replay_recent
        run_hash = RunHash()
        trace = Engine(seed=1337, config=config).run(600, reset=True)
        for td in trace:
            run_hash.update(td)
        return run_hash.hexdigest(), sum(td.replay_active for td in trace)

    (new, replays), (old, _) = digest(True), digest(False)
    assert replays > 0 and new == old


def test_console_highlights_the_cell_replay_actually_backed_up():
    session = SimSession("open_field", seed=7)
    seen = 0
    for _ in range(600):
        session.step(1)
        frame = session.frame()
        ctx = session.engine.context
        if frame["replay"]["active"] and ctx.replay_cell is not None:
            assert frame["replay"]["cell"] == session._cell_center(*ctx.replay_cell)
            assert 1 <= frame["replay"]["back"] <= frame["replay"]["span"]
            seen += 1
    assert seen > 0


@pytest.mark.parametrize("clear_trajectory", [True, False])
def test_a_teleport_during_microsleep_ends_the_replay_of_the_previous_episode(clear_trajectory):
    # The snapshot taken at sleep onset used to survive begin_episode, so after
    # a teleport mid-sleep replay kept backing up the previous episode's path
    # (32 times in the maze with rest and fatigue pacing off, seeds 1-8). The
    # agent sleeps on, but replays nothing more; the next sleep snapshots afresh.
    from ui.scenarios import make_scenario, teleport_to_start

    scenario = make_scenario("open_field")
    config = scenario.config()
    config.sensors.noise = 0.03
    engine = Engine(seed=1, config=config)
    scenario.setup(engine)
    for _ in range(2000):
        engine.run(1)
        if engine.context.replay_active and engine.context.replay_back >= 3:
            break
    assert engine.context.replay_active and engine.context.replay_span > 3
    if clear_trajectory:  # as the maze does between trials
        engine.value_memory.trajectory.clear()
    teleport_to_start(engine)
    asleep = 0
    while True:
        engine.run(1)
        ctx = engine.context
        if not ctx.replay_active:
            break
        asleep += 1
        assert ctx.replay_cell is None and ctx.replay_back == 0
    assert asleep >= 3  # the teleport did not end the sleep itself
    for _ in range(2000):  # the next sleep replays again
        engine.run(1)
        if engine.context.replay_cell is not None:
            break
    assert engine.context.replay_back == 1


def test_an_awake_reset_leaves_the_next_sleep_free_to_snapshot():
    # begin_episode ends the replay of a sleep in progress ([] = "nothing more
    # to replay"), but when the agent is awake it only unsets the plan (None),
    # so a microsleep starting even on the very next tick takes a fresh snapshot.
    engine = Engine(seed=1)
    engine.run(5)
    engine.trn_gate.replay_active = False
    engine.begin_episode()
    assert engine._replay_plan is None
    engine.trn_gate.replay_active = True
    engine.begin_episode()
    assert engine._replay_plan == []
