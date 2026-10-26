"""Split memory steering (``basal_ganglia.value_steer = "split"``, the default).

"split" turns the value map into a turn signal measured relative to ahead, with
a dead zone in units of the local relief; the older max-normalised advantages
("maxnorm") stay available behind the same switch. See ``split_value_signals``
and docs/decisions.md (G15) for why each part is there and what was measured.

These tests pin the legacy profile (EngineConfig() defaults); see docs/decisions.md G22 and docs/profiles.md.
"""

from __future__ import annotations

import itertools
import random

import pytest

from brain.systems.basal_ganglia import split_value_signals
from core.config import BasalGangliaConfig, EngineConfig
from experiments.memory_navigation import memory_nav_config, run_memory_navigation
from experiments.steering_sensitivity import Job, run_job


def _split(**kw) -> BasalGangliaConfig:
    return BasalGangliaConfig(value_steer="split", **kw)


def test_default_steering_is_split():
    assert BasalGangliaConfig().value_steer == "split"
    assert EngineConfig().basal_ganglia.value_steer == "split"


def test_flat_map_gives_no_steer():
    assert split_value_signals(0.0, 0.0, 0.0, 0.0, _split()) == (0.0, 0.0, 0.0)
    assert split_value_signals(4e-4, -2e-4, 1e-4, 4e-4, _split()) == (0.0, 0.0, 0.0)


def test_a_wobble_inside_the_relative_dead_zone_does_not_turn():
    # At a value peak every direction is downhill; the sides beat ahead by ~1-5%
    # of the relief. That used to command a full turn (orbit / zig-zag off the goal).
    fwd, left, right = split_value_signals(-0.270, -0.239, -0.239, 0.699, _split())
    assert (left, right) == (0.0, 0.0)
    assert fwd == 0.0  # ahead is downhill, so oppose_positive adds nothing either


def test_a_clear_lateral_gradient_turns_fully_and_forward_gives_way():
    cfg = _split()
    # left beats ahead by 0.5 of the relief: full left turn; right is worse: -1.
    fwd, left, right = split_value_signals(0.0, 0.5, -0.5, 1.0, cfg)
    assert left == 1.0 and right == -1.0
    assert fwd == -1.0  # oppose: FORWARD gives up what the turn gains
    # Ramp: d/s = 0.2 is half-way through the 0.1 dead zone + 0.2 ramp.
    _, left, _ = split_value_signals(0.0, 0.2, 0.0, 1.0, cfg)
    assert left == pytest.approx(0.5)


def test_uphill_ahead_keeps_forward_going():
    fwd, left, right = split_value_signals(1.0, 0.2, 0.1, 1.0, _split())
    assert fwd == 1.0 and left == -1.0 and right == -1.0


def test_exclusive_turns_commit_to_the_better_side():
    fwd, left, right = split_value_signals(-1.0, -0.2, -0.5, 1.0, _split())
    assert left == 1.0 and right == 0.0
    fwd, left, right = split_value_signals(-1.0, -0.6, -0.6, 1.0, _split())
    assert (left, right) == (1.0, 0.0)  # ties go left
    _, left, right = split_value_signals(-1.0, -0.6, -0.6, 1.0, _split(value_turn_exclusive=False))
    assert (left, right) == (1.0, 1.0)


def test_absolute_mode_reproduces_the_raw_unit_prototype():
    cfg = _split(value_turn_relative=False, value_turn_dead_zone=0.01, value_turn_ramp=0.02,
                 value_turn_exclusive=False, value_ahead_mode="zero")
    assert split_value_signals(-0.270, -0.239, -0.239, 0.699, cfg) == (0.0, 1.0, 1.0)
    assert split_value_signals(0.0, 0.015, -0.005, 0.015, cfg) == (0.0, pytest.approx(0.25), 0.0)


def test_value_can_never_push_every_move_down():
    # The max-norm signal reads (-1, -1, -1) at a local maximum, so REST (no value
    # term) wins: value-induced REST. Split signals are relative to ahead, so at
    # least one of the three is >= 0 whatever the map looks like.
    rng = random.Random(7)
    modes = ("zero", "oppose", "oppose_positive", "positive")
    for mode, exclusive, relative in itertools.product(modes, (False, True), (False, True)):
        cfg = _split(value_ahead_mode=mode, value_turn_exclusive=exclusive, value_turn_relative=relative)
        for _ in range(500):
            a, l, r = (rng.uniform(-2, 2) for _ in range(3))
            scale = max(abs(a), abs(l), abs(r), abs(rng.uniform(-2, 2)))
            assert max(split_value_signals(a, l, r, scale, cfg)) >= 0.0


def test_common_mode_adds_a_go_bias_only_when_every_direction_beats_here():
    cfg = _split(value_common_mode=0.1)
    plain = split_value_signals(0.3, 0.2, 0.1, 0.3, _split())
    biased = split_value_signals(0.3, 0.2, 0.1, 0.3, cfg)
    assert all(b > p for b, p in zip(biased, plain))
    assert split_value_signals(0.3, -0.2, 0.1, 0.3, cfg) == split_value_signals(0.3, -0.2, 0.1, 0.3, _split())


SPLIT = (("basal_ganglia.value_steer", "split"),)


@pytest.mark.parametrize("noise", [0.0, 0.03])
def test_split_lowers_the_maze_gain_threshold(noise):
    # Max-norm turns must beat FORWARD's ~0.7 lead, so the maze needs gain >= ~1.0;
    # split turns oppose FORWARD and saturate on a real gradient, so 0.4-0.8 work.
    # Seed 1, 1500 ticks: maxnorm 13-75 recalls at 0.4-0.8 vs 149-150 at 1.5.
    for gain in (0.4, 0.6, 0.8, 1.5, 3.0):
        row = run_job(Job("memory_maze", gain, 1, noise, 1500, SPLIT))
        assert row["score"] >= 140, (gain, row)
        assert row["first_hidden_ticks"] <= 20, (gain, row)
        assert row["vrest"] == 0.0, (gain, row)
    stock = run_job(Job("memory_maze", 0.6, 1, noise, 1500, (
        ("basal_ganglia.value_steer", "maxnorm"), ("basal_ganglia.wall_gate_gain", 0.0))))
    assert stock["score"] < 100


def test_replay_is_more_data_efficient_under_split_steering():
    # The same assertion as tests/experiments/test_memory_navigation.py under
    # split steering. The margin is thin (13 vs 14 ticks): in this geometry the
    # replayed gradient points along the agent's default heading, so replay and
    # one-demo online learning take nearly the same path, and only the approach
    # at the goal-disk edge differs. Max-norm passes by more (14 vs 22) because
    # its online agent value-rests for 8 ticks at the weak online peak.
    def config():
        c = memory_nav_config()
        c.basal_ganglia.value_steer = "split"
        return c

    with_replay = run_memory_navigation(replay=True, n_recall=1, config=config())
    online_only = run_memory_navigation(replay=False, n_recall=1, config=config())
    probe_on = next(r for r in with_replay if not r.visible)
    probe_off = next(r for r in online_only if not r.visible)
    assert probe_on.reached and probe_off.reached
    assert probe_on.ticks_to_goal < probe_off.ticks_to_goal
    repeated = run_memory_navigation(replay=False, n_train=1, n_recall=4, config=config())
    assert all(r.reached for r in repeated)


def test_unknown_steering_modes_are_rejected():
    # A misspelt mode used to fall through silently: value_steer="Split" ran
    # max-norm, and an unknown value_ahead_mode dropped FORWARD's value term.
    with pytest.raises(ValueError):
        split_value_signals(0.5, 1.0, -1.0, 1.0, BasalGangliaConfig(value_ahead_mode="opose_positive"))
    from core.engine import Engine

    engine = Engine(seed=1, config=EngineConfig(basal_ganglia=BasalGangliaConfig(value_steer="Split")))
    with pytest.raises(ValueError):
        engine.run(1)
