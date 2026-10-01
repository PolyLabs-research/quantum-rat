"""Replay consolidates the plastic place-value map.

This is the substrate the replay machinery previously lacked. Replaying a
trajectory backward propagates value from rewarding places to the places that
lead to them -- the concrete sense in which replay "consolidates".
"""

from brain.systems.value_memory import ValueMemory


def test_online_record_moves_value_toward_reward():
    vm = ValueMemory(learning_rate=0.5)
    vm.record(1, 1.0)
    assert 0.0 < vm.value_of(1) <= 1.0


def test_replay_propagates_value_backward_along_trajectory():
    vm = ValueMemory(learning_rate=0.3, discount=0.9)
    for place, reward in [(10, 0.0), (11, 0.0), (12, 0.0), (13, 1.0)]:
        vm.record(place, reward)
    before = {p: vm.value_of(p) for p in (10, 11, 12)}
    vm.consolidate(passes=5)
    after = {p: vm.value_of(p) for p in (10, 11, 12)}
    # Consolidation lifts the value of places that lead to the reward...
    assert all(after[p] > before[p] for p in (10, 11, 12))
    # ...with closer-to-reward places more valuable (temporal discounting).
    assert after[12] > after[11] > after[10]
