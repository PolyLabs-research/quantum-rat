"""The place-value map is learned by TD(0) and consolidated by replay.

TD with reward-on-arrival + bootstrapping means a place that leads toward reward
keeps its value even on zero-reward steps, so following the learned gradient
reinforces rather than erodes it (the repeated-recall erosion fix). Values also
generalize to neighbouring cells (overlapping place fields).

These tests pin the legacy profile (EngineConfig() defaults); see docs/decisions.md G22 and docs/profiles.md.
"""

from brain.systems.value_memory import ValueMemory


def test_online_td_credits_reward_to_the_previous_cell():
    vm = ValueMemory(learning_rate=0.5)
    vm.record((0, 0), 0.0)  # first step: no predecessor, logs only
    vm.record((1, 0), 1.0)  # arriving with reward -> V(previous) bootstraps toward it
    assert vm.value_of((0, 0)) > 0.0
    assert vm.value_of((1, 0)) == 0.0  # terminal cell not yet updated by an outgoing transition


def test_zero_reward_step_does_not_decay_a_valued_place():
    # A place whose successor is valuable keeps its value on a zero-reward step
    # (bootstrapping), instead of decaying toward the immediate zero reward.
    vm = ValueMemory(learning_rate=0.5, discount=0.9)
    vm.values[(6, 0)] = 1.0  # successor already valuable
    vm.record((5, 0), 0.0)  # arrive at (5,0); no predecessor yet
    vm.record((6, 0), 0.0)  # arrive at valuable (6,0) with zero reward
    # V((5,0)) is pulled UP toward gamma*V((6,0)) = 0.9, not down toward 0.
    assert vm.value_of((5, 0)) > 0.0


def test_replay_propagates_value_backward_along_trajectory():
    vm = ValueMemory(learning_rate=0.3, discount=0.9)
    for cell, reward in [((10, 0), 0.0), ((11, 0), 0.0), ((12, 0), 0.0), ((13, 0), 1.0)]:
        vm.record(cell, reward)
    vm.consolidate(passes=5)
    v10, v11, v12 = vm.value_of((10, 0)), vm.value_of((11, 0)), vm.value_of((12, 0))
    assert v12 > v11 > v10 > 0.0  # value decays backward from the goal with discounting


def test_generalization_spreads_value_to_neighbouring_cells():
    plain = ValueMemory(learning_rate=0.5, generalization_radius=0)
    wide = ValueMemory(learning_rate=0.5, generalization_radius=1, generalization_falloff=0.5)
    for vm in (plain, wide):
        vm.record((4, 5), 0.0)
        vm.record((5, 5), 1.0)  # updates V((4,5)); wide also spreads to its neighbours
    assert plain.value_of((3, 5)) == 0.0
    assert wide.value_of((3, 5)) > 0.0
    assert wide.value_of((4, 5)) > wide.value_of((3, 5))  # updated centre strongest
