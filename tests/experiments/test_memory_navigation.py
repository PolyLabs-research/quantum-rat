"""Memory-guided navigation: the agent learns to return to a hidden goal, and
replay makes that learning more data-efficient.

With proper online TD learning the agent learns memory navigation from its own
experience, so repeated recall reinforces the value map rather than eroding it.
Replay (offline consolidation of a single demonstration) is a data-efficiency
speed-up: it reaches the goal sooner than online learning alone, not a
precondition for reaching it at all.

These tests pin the legacy profile (EngineConfig() defaults); see docs/decisions.md G22 and docs/profiles.md.
"""

from experiments.memory_navigation import run_memory_navigation


def test_visible_training_trial_is_reached():
    for replay in (True, False):
        results = run_memory_navigation(replay=replay)
        train = [r for r in results if r.visible]
        assert train and all(r.reached for r in train)


def test_replay_is_more_data_efficient_than_online_learning():
    # After a single demonstration, the replay agent recalls the hidden goal
    # much sooner than the agent that must learn online during the probe.
    with_replay = run_memory_navigation(replay=True, n_recall=1)
    online_only = run_memory_navigation(replay=False, n_recall=1)
    probe_on = next(r for r in with_replay if not r.visible)
    probe_off = next(r for r in online_only if not r.visible)
    assert probe_on.reached and probe_off.reached
    assert probe_on.ticks_to_goal < probe_off.ticks_to_goal


def test_repeated_recall_does_not_erode_the_map():
    # Repeated hidden-recall trials keep reaching the goal -- the value map is
    # reinforced by TD learning, not eroded (the fix for the former decay bug,
    # where zero-reward steps pulled consolidated values toward zero).
    results = run_memory_navigation(replay=False, n_train=1, n_recall=4)
    recall = [r for r in results if not r.visible]
    assert all(r.reached for r in recall)


def test_memory_navigation_is_deterministic():
    assert run_memory_navigation(replay=True) == run_memory_navigation(replay=True)
