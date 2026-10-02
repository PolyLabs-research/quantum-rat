"""Goal-vector memory: where reward was found, steered toward where the value map is flat.

Unit tests of the pure command function, of how the goal is written (by replay
of a rewarded transition, or online on contact) and extinguished (a visit to
the goal's place cell that finds no reward), and of the engine's arbitration
(the vector steers only where the map's largest sampled advantage is below
``value_memory.goal_vector_flat``).
"""

from __future__ import annotations

import math

import pytest

from brain.systems.basal_ganglia import TURN_RADIUS, goal_vector_signals
from brain.systems.value_memory import ValueMemory
from core.config import EngineConfig
from core.engine import Engine
from core.world import WorldObject
from metrics.hash import RunHash
from ui.scenarios import make_scenario

# ------------------------------------------------------------ pure function


@pytest.mark.parametrize("bearing", [0.0, 0.1, -0.1, 0.15, -0.15])
def test_no_command_when_facing_the_goal(bearing):
    assert goal_vector_signals(bearing, 5.0, 0.15, 0.3) == (0.0, 0.0, 0.0)


def test_turns_toward_the_goal_and_forward_gives_way():
    assert goal_vector_signals(1.0, 5.0, 0.15, 0.3) == (-1.0, 1.0, 0.0)
    assert goal_vector_signals(-1.0, 5.0, 0.15, 0.3) == (-1.0, 0.0, 1.0)
    assert goal_vector_signals(math.pi, 5.0, 0.15, 0.3) == (-1.0, 1.0, 0.0)
    fwd, left, right = goal_vector_signals(0.3, 5.0, 0.15, 0.3)  # half way up the ramp
    assert (fwd, left, right) == pytest.approx((-0.5, 0.5, 0.0))
    assert goal_vector_signals(0.2, 5.0, 0.15, 0.0) == (-1.0, 1.0, 0.0)  # ramp <= 0: a step


def test_no_command_for_a_goal_inside_the_turning_circle():
    # Abeam at 1 m lies inside the ~1 m-radius circle a run of turns traces:
    # turning toward it would orbit it, so the agent carries on instead.
    assert TURN_RADIUS == pytest.approx(1.0, abs=0.01)
    assert goal_vector_signals(math.pi / 2, 1.0, 0.15, 0.3) == (0.0, 0.0, 0.0)
    assert goal_vector_signals(-math.pi / 2, 1.9, 0.15, 0.3) == (0.0, 0.0, 0.0)
    assert goal_vector_signals(math.pi / 2, 2.1, 0.15, 0.3) == (-1.0, 1.0, 0.0)
    # Straight behind is never inside it: turn round.
    assert goal_vector_signals(math.pi, 0.5, 0.15, 0.3) == (-1.0, 1.0, 0.0)


def test_max_signal_is_never_negative():
    for i in range(-40, 41):
        for distance in (0.2, 1.0, 5.0):
            assert max(goal_vector_signals(i * math.pi / 40, distance, 0.15, 0.3)) >= 0.0


# ------------------------------------------------------------- goal writing


def test_replaying_a_rewarded_transition_writes_the_goal():
    vm = ValueMemory()
    for cell, reward in [((0, 0), 0.0), ((1, 0), 0.0), ((2, 0), 1.0)]:
        vm.record(cell, reward)
    assert vm.goal_cell is None  # online experience alone does not write it
    vm.replay_transition(0)
    assert vm.goal_cell is None  # an unrewarded transition does not either
    vm.replay_transition(1)
    assert vm.goal_cell == (2, 0)


def test_consolidation_writes_the_goal():
    vm = ValueMemory()
    for cell, reward in [((0, 0), 0.0), ((0, 1), 0.0), ((0, 2), -0.5), ((1, 2), 1.0), ((1, 3), 0.0)]:
        vm.record(cell, reward)
    vm.consolidate(3)
    assert vm.goal_cell == (1, 2)


# -------------------------------------------------------------- engine side


def _engine(**value_memory) -> Engine:
    config = EngineConfig()
    config.value_memory.goal_vector = True
    for key, value in value_memory.items():
        setattr(config.value_memory, key, value)
    return Engine(seed=1, config=config)


def test_flat_map_steers_toward_the_goal_behind():
    engine = _engine()
    engine.value_memory.goal_cell = (-12, 2)  # behind and slightly to the left (heading 0)
    engine.run(1)
    ctx = engine.context
    assert ctx.goal_vector_active
    assert ctx.value_signals == (-1.0, 1.0, 0.0)  # turn left, FORWARD gives way
    assert ctx.action_name == "TURN_LEFT"


def test_a_map_with_relief_keeps_control():
    engine = _engine()
    engine.value_memory.goal_cell = (-12, 2)
    engine.value_memory.values[(2, 0)] = 0.5  # something learned one lookahead ahead
    engine.run(1)
    assert not engine.context.goal_vector_active


def test_precedence_setting_lets_the_vector_override_the_map():
    engine = _engine(goal_vector_flat=float("inf"))
    engine.value_memory.goal_cell = (-12, 2)
    engine.value_memory.values[(2, 0)] = 0.5
    engine.run(1)
    assert engine.context.goal_vector_active


def test_off_means_no_steering_and_no_bookkeeping():
    config = EngineConfig()
    assert config.value_memory.goal_vector is False  # off in the core engine
    engine = Engine(seed=1, config=config)
    engine.value_memory.goal_cell = (1, 0)  # the agent walks through it without reward
    engine.run(10)
    assert not engine.context.goal_vector_active
    assert engine.value_memory.goal_cell == (1, 0)


def test_visits_without_reward_extinguish_the_goal():
    # The remembered goal is the start cell, with no reward there. The agent
    # walks off (FORWARD), turns back toward it, goes round the turning circle
    # instead of orbiting the point and passes through the cell: the first
    # pass leaves the goal held (one miss), a second one erases it.
    engine = _engine()
    engine.run(1)
    goal = engine.spatial.bins_at(engine.context.grid_x, engine.context.grid_y)
    engine.value_memory.goal_cell = goal
    passes = 0
    inside = False  # the walk-off from the start cell is not a visit (it began before the goal)
    for _ in range(200):
        engine.run(1)
        ctx = engine.context
        now = engine.spatial.bins_at(ctx.grid_x, ctx.grid_y) == goal
        if inside and not now:
            passes += 1
            if passes == 1:
                assert engine.value_memory.goal_cell == goal  # one miss is not enough
        inside = now
        if engine.value_memory.goal_cell is None:
            break
    assert engine.value_memory.goal_cell is None
    assert passes == engine.config.value_memory.goal_extinction_misses == 2


def test_a_visit_with_reward_keeps_the_goal():
    engine = _engine()
    engine.world.add_object(WorldObject(1.5, 0.0, 1.5, "hidden"))  # touching from the start
    engine.run(1)
    cell = engine.spatial.bins_at(engine.context.grid_x, engine.context.grid_y)
    engine.value_memory.goal_cell = cell
    for _ in range(6):
        engine.run(1)
    assert engine.value_memory.goal_cell == cell


# Extinction rule, driven tick by tick: (place cell of the estimate, target contact).
GOAL = (4, 2)
NEXT_DOOR = (5, 2)
AWAY = (0, 0)


def _drive(engine: Engine, steps) -> None:
    from core.engine import EngineContext

    b = engine.spatial.bin_size
    for cell, contact in steps:
        ctx = EngineContext(tick=0)
        ctx.grid_x, ctx.grid_y = (cell[0] + 0.5) * b, (cell[1] + 0.5) * b
        ctx.target_contact = contact
        engine._update_goal_memory(ctx)


def _held_goal(**value_memory) -> Engine:
    engine = _engine(**value_memory)
    engine.value_memory.goal_cell = GOAL
    return engine


def test_contact_on_the_tick_of_leaving_the_cell_counts_as_reward():
    # The bug: touching the goal from the cell next door, on the tick the agent
    # leaves the goal cell, was ignored and the goal erased (maze, heading 1.96,
    # seed 1, noise 0: 10 recalls instead of 89). Checked with a single miss
    # erasing, so the leaving tick alone decides.
    engine = _held_goal(goal_extinction_misses=1)
    _drive(engine, [(AWAY, False), (GOAL, False), (NEXT_DOOR, True)])
    assert engine.value_memory.goal_cell == GOAL
    _drive(engine, [(GOAL, False), (NEXT_DOOR, False)])  # the same pass without contact
    assert engine.value_memory.goal_cell is None


def test_one_miss_does_not_erase_two_in_a_row_do():
    engine = _held_goal()
    _drive(engine, [(GOAL, False), (AWAY, False)])
    assert engine.value_memory.goal_cell == GOAL
    _drive(engine, [(GOAL, False), (GOAL, False), (NEXT_DOOR, False)])
    assert engine.value_memory.goal_cell is None


def test_any_contact_resets_the_miss_count():
    # A pass through the part of the goal cell outside the contact circle, then
    # contact reached from another cell: the goal is still there.
    engine = _held_goal()
    for _ in range(5):
        _drive(engine, [(GOAL, False), (AWAY, False), (NEXT_DOOR, True), (AWAY, False)])
    assert engine.value_memory.goal_cell == GOAL
    # A rewarded visit resets the count too.
    _drive(engine, [(GOAL, False), (AWAY, False), (GOAL, True), (AWAY, False), (GOAL, False), (AWAY, False)])
    assert engine.value_memory.goal_cell == GOAL


def test_the_miss_count_survives_an_episode_boundary_and_restarts_for_a_new_goal():
    engine = _held_goal()
    _drive(engine, [(GOAL, False), (AWAY, False)])
    engine.begin_episode()  # a teleport keeps the goal, and so its miss count
    _drive(engine, [(GOAL, False), (AWAY, False)])
    assert engine.value_memory.goal_cell is None
    engine = _held_goal()
    _drive(engine, [(GOAL, False), (AWAY, False)])
    engine.value_memory.goal_cell = NEXT_DOOR  # a new goal written by replay
    _drive(engine, [(NEXT_DOOR, False), (AWAY, False)])
    assert engine.value_memory.goal_cell == NEXT_DOOR


def test_zero_disables_extinction():
    engine = _held_goal(goal_extinction_misses=0)
    for _ in range(5):
        _drive(engine, [(GOAL, False), (AWAY, False)])
    assert engine.value_memory.goal_cell == GOAL


@pytest.mark.parametrize("source,written", [("replay", False), ("online", True)])
def test_contact_writes_the_goal_only_when_online(source, written):
    engine = _engine(goal_vector_source=source)
    engine.world.add_object(WorldObject(1.5, 0.0, 1.5, "hidden"))
    engine.run(1)
    assert engine.context.target_contact
    expected = engine.spatial.bins_at(engine.context.grid_x, engine.context.grid_y) if written else None
    assert engine.value_memory.goal_cell == expected


def test_unknown_source_raises():
    engine = _engine(goal_vector_source="Replay")
    with pytest.raises(ValueError):
        engine.run(1)


def test_reward_free_world_is_unchanged_by_the_goal_vector():
    digests = []
    for on in (False, True):
        scenario = make_scenario("open_field")
        config = scenario.config()
        config.value_memory.goal_vector = on
        engine = Engine(seed=3, config=config)
        scenario.setup(engine)
        run_hash = RunHash()
        for _ in range(600):
            td = engine.run(1)[0]
            run_hash.update(td)
            scenario.on_tick(engine, td.tick)
        digests.append(run_hash.hexdigest())
        assert engine.value_memory.goal_cell is None
    assert digests[0] == digests[1]
