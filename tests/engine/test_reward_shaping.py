"""Approach shaping rewards the agent's own progress, not changes to the world."""

from core.engine import Engine
from core.world import WorldObject


def _engine_between_two_targets():
    engine = Engine(seed=3)
    near = WorldObject(1.0, 0.0, 0.5, "target")
    far = WorldObject(-8.0, 0.0, 0.5, "target")
    engine.world.add_object(near)
    engine.world.add_object(far)
    return engine, near, far


def test_eating_the_nearest_target_is_not_punished():
    engine, near, _ = _engine_between_two_targets()
    engine.run(3)
    # The near item is eaten: the nearest target is now ~8 m away. That jump is
    # not the agent's doing, so it must not show up as a large negative reward.
    near.kind = "collected"
    reward = engine.run(1)[0].reward
    assert reward > -0.5


def test_moving_a_target_is_not_charged_to_the_agent():
    engine, near, _ = _engine_between_two_targets()
    engine.run(3)
    near.x, near.y = 7.0, 7.0  # e.g. a beacon hops away
    assert engine.run(1)[0].reward > -0.5


def test_approaching_the_same_target_is_still_rewarded():
    engine = Engine(seed=3)
    engine.world.add_object(WorldObject(6.0, 0.0, 0.5, "target"))
    trace = engine.run(6)
    # Facing the target from the start pose, forward motion closes the distance
    # (it arrives within a few ticks; afterwards it overshoots and moves away).
    assert all(t.reward > 0 for t in trace[1:5])
    assert sum(t.reward for t in trace[1:5]) > 1.0
