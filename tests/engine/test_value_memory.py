"""Replay consolidates the plastic place-value map, with optional spatial
generalization.

Replaying a trajectory backward propagates value from rewarding places to the
places that lead to them. With a generalization radius, value also spreads to
neighbouring cells (overlapping place fields), so a single trajectory fills a
followable 2-D field instead of a thin one-cell path.
"""

from brain.systems.value_memory import ValueMemory


def test_online_record_moves_value_toward_reward():
    vm = ValueMemory(learning_rate=0.5)
    vm.record((1, 0), 1.0)
    assert 0.0 < vm.value_of((1, 0)) <= 1.0


def test_replay_propagates_value_backward_along_trajectory():
    vm = ValueMemory(learning_rate=0.3, discount=0.9)
    for cell, reward in [((10, 0), 0.0), ((11, 0), 0.0), ((12, 0), 0.0), ((13, 0), 1.0)]:
        vm.record(cell, reward)
    before = {c: vm.value_of(c) for c in [(10, 0), (11, 0), (12, 0)]}
    vm.consolidate(passes=5)
    after = {c: vm.value_of(c) for c in [(10, 0), (11, 0), (12, 0)]}
    assert all(after[c] > before[c] for c in after)
    assert after[(12, 0)] > after[(11, 0)] > after[(10, 0)]  # discounting


def test_generalization_spreads_value_to_neighbouring_cells():
    plain = ValueMemory(learning_rate=0.5, generalization_radius=0)
    wide = ValueMemory(learning_rate=0.5, generalization_radius=1, generalization_falloff=0.5)
    plain.record((5, 5), 1.0)
    wide.record((5, 5), 1.0)
    # Without generalization a neighbour stays at zero; with it, the neighbour gains value.
    assert plain.value_of((6, 5)) == 0.0
    assert wide.value_of((6, 5)) > 0.0
    assert wide.value_of((5, 5)) > wide.value_of((6, 5))  # centre strongest
