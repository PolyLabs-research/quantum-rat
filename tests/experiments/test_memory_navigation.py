"""Replay consolidation enables memory-guided navigation to a hidden goal.

After a single visible demonstration trial and a sleep (replay) phase, the
agent returns to the now-hidden goal from its consolidated value map; without
that consolidation it does not. This is the end-to-end "replay improves
performance" result, in the value-driven regime where memory navigation is
demonstrable (see experiments/memory_navigation.py).
"""

from experiments.memory_navigation import run_memory_navigation


def test_visible_training_trial_is_reached():
    for replay in (True, False):
        results = run_memory_navigation(replay=replay)
        train = [r for r in results if r.visible]
        assert train and all(r.reached for r in train)  # vision solves the visible trial


def test_replay_enables_recall_of_hidden_goal():
    with_replay = run_memory_navigation(replay=True)
    without = run_memory_navigation(replay=False)
    first_probe_on = next(r for r in with_replay if not r.visible)
    first_probe_off = next(r for r in without if not r.visible)
    # Replay consolidation lets the agent reach the hidden goal from memory...
    assert first_probe_on.reached
    # ...while without consolidation it does not.
    assert not first_probe_off.reached
    assert first_probe_on.ticks_to_goal < first_probe_off.ticks_to_goal


def test_memory_navigation_is_deterministic():
    assert run_memory_navigation(replay=True) == run_memory_navigation(replay=True)
