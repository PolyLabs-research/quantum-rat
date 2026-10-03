"""Seeds are samples (docs/research_plan.md section 5, M0b item 8).

Three seeded elements and a guard: odometry noise on the self-motion estimate
(``sensors.odometry_speed_noise`` / ``odometry_turn_noise``, stream
"sensors_odometry"), softmax action selection
(``basal_ganglia.softmax_temperature``, stream "action_softmax"), and
``core.seeds.require_seeds_are_samples``, which refuses a multi-seed claim on
a config with none of the four stochastic parameters on. Each test is named
for what it proves. Runs are 200-300 ticks in the barren default world, so the
file takes a few seconds.
"""

from __future__ import annotations

import io
import json
import math
from typing import Dict, List, Sequence, Tuple

import pytest

from brain.systems.basal_ganglia import ACTION_ORDER, argmax_action, select_action_with_scores, softmax_sample
from core.config import STOCHASTIC_PARAMETERS, BasalGangliaConfig, EngineConfig
from core.determinism import DEFAULT_SEED, DEFAULT_TICKS, build_current_trace, hash_trace, load_baseline
from core.engine import Engine
from core.rng import RNG
from core.seeds import PseudoReplicationError, require_seeds_are_samples
from experiments import steering_sensitivity as ss
from experiments.memory_navigation import run_memory_navigation_seeds
from metrics.schema import TickData

ALL_STREAMS = ("neuromod", "criticality", "sensors_vision", "sensors_noise", "sensors_odometry", "action_softmax")
NEW_STREAMS = ("sensors_odometry", "action_softmax")
TICKS = 300


def _states(engine: Engine, names: Sequence[str]) -> Tuple[object, ...]:
    return tuple(engine.streams[n].getstate() for n in names)


def _research(speed: float = 0.0, turn: float = 0.0, tau: float = 0.0) -> EngineConfig:
    """``EngineConfig.research()`` with the three seeded elements set as given (all off by default)."""
    cfg = EngineConfig.research()
    cfg.sensors.odometry_speed_noise = speed
    cfg.sensors.odometry_turn_noise = turn
    cfg.basal_ganglia.softmax_temperature = tau
    return cfg


def _positions(trace: List[TickData]) -> List[Tuple[float, float]]:
    return [td.pos for td in trace]


def _estimates(trace: List[TickData]) -> List[Tuple[float, float]]:
    return [(td.grid_x, td.grid_y) for td in trace]


# --- (a) at 0 nothing is drawn -----------------------------------------------


@pytest.mark.exact_hash  # compares the legacy trace with the committed baseline (pytest.ini)
def test_with_every_stochastic_parameter_at_zero_the_new_streams_are_never_drawn_and_the_legacy_gate_passes() -> None:
    for config in (EngineConfig.legacy(), _research()):
        engine = Engine(seed=DEFAULT_SEED, config=config)
        assert set(NEW_STREAMS) <= set(engine.streams)
        before = _states(engine, NEW_STREAMS)
        engine.run(DEFAULT_TICKS)
        assert _states(engine, NEW_STREAMS) == before, config.profile
    # The legacy trace is the committed baseline, bit for bit (core.determinism, the gate's own path).
    assert build_current_trace() == load_baseline()
    # Each named stream derives its own child seed; the two new names leave the four old ones as they were.
    seeds = {name: RNG(DEFAULT_SEED).stream(name).seed for name in ALL_STREAMS}
    assert len(set(seeds.values())) == len(ALL_STREAMS)
    engine = Engine(seed=DEFAULT_SEED)
    assert {name: engine.streams[name].seed for name in ALL_STREAMS} == seeds


# --- (b) seeds are samples under the research profile ----------------------


def test_research_defaults_give_four_seeds_four_trajectories_and_the_same_seed_the_same_one() -> None:
    traces = {seed: Engine(seed=seed, config=EngineConfig.research()).run(TICKS) for seed in (1, 2, 3, 4)}
    positions = {seed: _positions(trace) for seed, trace in traces.items()}
    assert len({tuple(p) for p in positions.values()}) == 4
    for a in positions:
        for b in positions:
            if a < b:
                first = next(t for t in range(TICKS) if positions[a][t] != positions[b][t])
                assert first < 10, (a, b, first)  # measured: ticks 3-5
    again = Engine(seed=1, config=EngineConfig.research()).run(TICKS)
    assert hash_trace(again) == hash_trace(traces[1])
    assert _positions(again) == positions[1]
    # One random() per tick on the softmax stream and two gauss() per tick on the
    # odometry stream (forward first, then turn), whatever the trajectory does.
    engine = Engine(seed=1, config=EngineConfig.research())
    engine.run(TICKS)
    softmax_ref = RNG(1).stream("action_softmax")
    for _ in range(TICKS):
        softmax_ref.random()
    odometry_ref = RNG(1).stream("sensors_odometry")
    for _ in range(2 * TICKS):
        odometry_ref.gauss(0.0, 1.0)
    assert engine.streams["action_softmax"].getstate() == softmax_ref.getstate()
    assert engine.streams["sensors_odometry"].getstate() == odometry_ref.getstate()


# --- (c) odometry noise is on the estimate, not the body --------------------


def test_odometry_noise_moves_the_estimate_not_the_body_until_the_actions_diverge_and_leaves_the_sensor_streams_alone() -> None:
    """Research profile with the softmax at 0, so the arbiter is deterministic and
    only odometry differs. The noisy estimate feeds place_id (working-memory
    novelty) and value steering, so the actions can diverge; up to and including
    the first tick they do, the body's positions are identical (the world applies
    the previous tick's action before the sensors read), while the estimate
    differs from the first tick on. Measured at seed 1: in the barren default
    world no action differs within the 300 ticks (reward is 0 there, so the
    value map is never written and nothing downstream reads the estimate), so
    the window is the whole run and the two bodies trace one path."""
    exact = Engine(seed=1, config=_research()).run(TICKS)
    noisy = Engine(seed=1, config=_research(speed=0.1, turn=0.05)).run(TICKS)
    diverge = next((t for t in range(TICKS) if exact[t].action_name != noisy[t].action_name), TICKS - 1)
    assert diverge >= 1
    assert _positions(exact[: diverge + 1]) == _positions(noisy[: diverge + 1])
    # Tick 0: the body has not moved, so the forward draw scales a 0 (grid unchanged) and
    # the turn draw alone moves the heading estimate.
    assert exact[0].obs_forward_delta == noisy[0].obs_forward_delta == 0.0
    assert exact[0].obs_turn_delta == 0.0 != noisy[0].obs_turn_delta
    assert exact[0].hd_angle != noisy[0].hd_angle
    assert _estimates(exact[:1]) == _estimates(noisy[:1])
    # From the first moving tick on the position estimates differ too.
    first_move = next(t for t in range(1, TICKS) if exact[t].obs_forward_delta != 0.0)
    assert first_move <= diverge
    assert _estimates(exact[first_move : diverge + 1]) != _estimates(noisy[first_move : diverge + 1])
    # The clamp to [-1, 1] is kept as it is: below it (a TURN moves 0.3) every noisy
    # forward delta differs from the exact one; at full thrust (1.0, the top of the
    # range) positive speed errors are clamped away, so only slowing ones show.
    moving = [(a, b) for a, b in zip(exact, noisy) if a.obs_forward_delta != 0.0]
    below = [(a, b) for a, b in moving if abs(a.obs_forward_delta) < 1.0]
    full = [(a, b) for a, b in moving if a.obs_forward_delta == 1.0]
    assert below and full
    assert all(a.obs_forward_delta != b.obs_forward_delta for a, b in below)
    assert all(b.obs_forward_delta <= 1.0 for _, b in full)
    assert any(b.obs_forward_delta < 1.0 for _, b in full)
    # Stream isolation: with sensor noise on as well, the rangefinder and pain streams
    # are consumed identically whether or not odometry noise is on.
    with_sensor = _research()
    with_sensor.sensors.noise = 0.03
    with_both = _research(speed=0.1, turn=0.05)
    with_both.sensors.noise = 0.03
    a = Engine(seed=1, config=with_sensor)
    b = Engine(seed=1, config=with_both)
    a.run(TICKS)
    b.run(TICKS)
    assert _states(a, ("sensors_vision", "sensors_noise")) == _states(b, ("sensors_vision", "sensors_noise"))
    assert _states(a, ("sensors_odometry",)) == _states(Engine(seed=1), ("sensors_odometry",))  # untouched at 0
    assert _states(b, ("sensors_odometry",)) != _states(a, ("sensors_odometry",))


# --- (d) the softmax sampler -------------------------------------------------


def _softmax(scores: Dict[str, float], tau: float) -> Dict[str, float]:
    top = max(scores.values())
    weights = {k: math.exp((v - top) / tau) for k, v in scores.items()}
    total = sum(weights.values())
    return {k: w / total for k, w in weights.items()}


def test_softmax_sampler_is_the_argmax_as_the_temperature_vanishes_and_matches_the_softmax_at_tau_one() -> None:
    grid = [
        {"FORWARD": a, "TURN_LEFT": b, "TURN_RIGHT": c, "REST": d}
        for a in (0.0, 0.3, 0.9)
        for b in (-0.5, 0.2, 1.1)
        for c in (-1.0, 0.1, 0.8)
        for d in (0.05, 0.5)
    ]
    grid = [g for g in grid if len(set(g.values())) == 4]  # tie-free: a tie is split by the draw at tau > 0
    assert len(grid) == 54
    stream = RNG(5).stream("action_softmax")
    for scores in grid:
        assert softmax_sample(scores, 1e-9, stream) == argmax_action(scores), scores
    fresh = RNG(5).stream("action_softmax")  # exactly one draw per call
    for _ in grid:
        fresh.random()
    assert stream.getstate() == fresh.getstate()
    # The argmax keeps its fixed tie order (earliest in ACTION_ORDER wins) and a
    # channel missing from the scores (microsleep scores only REST) counts as -inf.
    assert argmax_action({name: 0.5 for name in ACTION_ORDER}) == "FORWARD"
    assert argmax_action({"REST": 1.0}) == "REST"
    assert softmax_sample({"REST": 1.0}, 0.1, stream) == "REST"
    with pytest.raises(ValueError):
        softmax_sample(grid[0], 0.0, stream)
    # tau = 1 over 20,000 draws: empirical frequencies within 0.02 of the softmax
    # probabilities (measured: within 0.008).
    scores = {"FORWARD": 1.0, "TURN_LEFT": 0.5, "TURN_RIGHT": 0.0, "REST": -1.0}
    expected = _softmax(scores, 1.0)
    stream = RNG(7).stream("action_softmax")
    counts = {name: 0 for name in ACTION_ORDER}
    n = 20_000
    for _ in range(n):
        counts[softmax_sample(scores, 1.0, stream)] += 1
    assert sum(counts.values()) == n
    for name in ACTION_ORDER:
        assert abs(counts[name] / n - expected[name]) < 0.02, name


def test_select_action_samples_only_at_a_positive_temperature_and_the_scores_stay_the_scores() -> None:
    engine = Engine(seed=1)
    engine.run(3)
    obs = engine.context.observation
    assert obs is not None
    argmax_action_, scores = select_action_with_scores(obs, 0.5, 1.0, False, config=BasalGangliaConfig())
    assert argmax_action_.name == argmax_action(scores)
    hot = BasalGangliaConfig(softmax_temperature=0.1)
    with pytest.raises(ValueError):
        select_action_with_scores(obs, 0.5, 1.0, False, config=hot)  # a temperature needs a stream
    stream = RNG(1).stream("action_softmax")
    sampled, hot_scores = select_action_with_scores(obs, 0.5, 1.0, False, config=hot, action_stream=stream)
    assert sampled.name in ACTION_ORDER
    assert hot_scores == scores  # nothing added to the scores (nor to TickData)
    assert stream.getstate() != RNG(1).stream("action_softmax").getstate()  # one draw taken
    # At 0 the stream is not touched even when one is passed.
    stream = RNG(1).stream("action_softmax")
    select_action_with_scores(obs, 0.5, 1.0, False, config=BasalGangliaConfig(), action_stream=stream)
    assert stream.getstate() == RNG(1).stream("action_softmax").getstate()


# --- (e) the guard -----------------------------------------------------------


def test_guard_refuses_two_seeds_at_legacy_defaults_and_passes_one_seed_sensor_noise_and_the_research_profile() -> None:
    with pytest.raises(PseudoReplicationError) as excinfo:
        require_seeds_are_samples(EngineConfig(), 2)
    assert isinstance(excinfo.value, ValueError)
    for name in STOCHASTIC_PARAMETERS:
        assert name in str(excinfo.value)
    assert require_seeds_are_samples(EngineConfig(), 1) == []
    assert require_seeds_are_samples(EngineConfig(), 0) == []
    noisy = EngineConfig()
    noisy.sensors.noise = 0.03
    assert require_seeds_are_samples(noisy, 2) == ["sensors.noise=0.03"]
    assert require_seeds_are_samples(EngineConfig.research(), 2) == [
        "sensors.odometry_speed_noise=0.05",
        "sensors.odometry_turn_noise=0.01",
        "basal_ganglia.softmax_temperature=0.1",
    ]
    # The bypass: one warning line, and the call returns instead of raising.
    out = io.StringIO()
    assert require_seeds_are_samples(EngineConfig(), 2, allow_identical_seeds=True, out=out) == []
    text = out.getvalue()
    assert text.startswith("warning: 2 seeds asked for") and text.count("\n") == 1
    assert "--allow-identical-seeds" in text


def test_harnesses_call_the_guard_and_their_bypass_flag_runs_the_seeds_with_a_warning(capsys) -> None:
    jobs = ss.make_jobs(["beacon"], [1.5], [1, 2], noise=0.0, ticks=5)
    with pytest.raises(PseudoReplicationError):
        ss.run_jobs(jobs, workers=1)
    rows = ss.run_jobs(jobs, workers=1, allow_identical_seeds=True)
    assert [r["seed"] for r in rows] == [1, 2]
    assert rows[0]["score"] == rows[1]["score"]  # the same run twice
    assert capsys.readouterr().err.count("warning:") == 1  # once, not once per job group
    # A stochastic element from the noise argument or from a --set override passes without the flag.
    assert len(ss.run_jobs(ss.make_jobs(["beacon"], [1.5], [1, 2], noise=0.03, ticks=5), workers=1)) == 2
    odometry = {"sensors.odometry_turn_noise": 0.05}
    assert len(ss.run_jobs(ss.make_jobs(["beacon"], [1.5], [1, 2], 0.0, odometry, ticks=5), workers=1)) == 2
    assert len(ss.run_jobs(ss.make_jobs(["beacon"], [1.5], [1], noise=0.0, ticks=5), workers=1)) == 1
    assert capsys.readouterr().err == ""
    # The command line: refused without the flag, run with it (JSON on stdout, the warning on stderr).
    argv = ["--scenarios", "beacon", "--gains", "1.5", "--seeds", "2", "--noise", "0", "--ticks", "5",
            "--workers", "1", "--json"]
    with pytest.raises(PseudoReplicationError):
        ss.main(argv)
    ss.main(argv + ["--allow-identical-seeds"])
    captured = capsys.readouterr()
    assert [r["seed"] for r in json.loads(captured.out)] == [1, 2]
    assert captured.err.count("warning:") == 1
    # Memory navigation: the same guard in front of its per-seed runner.
    with pytest.raises(PseudoReplicationError):
        run_memory_navigation_seeds(True, [1, 2], max_ticks=5)
    by_seed = run_memory_navigation_seeds(True, [1, 2], max_ticks=5, allow_identical_seeds=True)
    assert list(by_seed) == [1, 2] and by_seed[1] == by_seed[2]
    assert capsys.readouterr().err.count("warning:") == 1
    assert list(run_memory_navigation_seeds(True, [1], max_ticks=5)) == [1]
    research = run_memory_navigation_seeds(False, [1, 2], max_ticks=5, config=EngineConfig.research())
    assert list(research) == [1, 2]
    assert capsys.readouterr().err == ""


# --- (f) the element list ---------------------------------------------------


def test_stochastic_elements_lists_exactly_the_enabled_elements() -> None:
    assert EngineConfig().stochastic_elements() == []
    assert EngineConfig.legacy().stochastic_elements() == []
    assert EngineConfig.research().stochastic_elements() == [
        "sensors.odometry_speed_noise=0.05",
        "sensors.odometry_turn_noise=0.01",
        "basal_ganglia.softmax_temperature=0.1",
    ]
    values = {"sensors.noise": 0.03, "sensors.odometry_speed_noise": 0.2, "sensors.odometry_turn_noise": 0.01,
              "basal_ganglia.softmax_temperature": 0.5}
    assert tuple(values) == STOCHASTIC_PARAMETERS
    for name, value in values.items():  # one at a time
        cfg = EngineConfig()
        section, field_name = name.split(".")
        setattr(getattr(cfg, section), field_name, value)
        assert cfg.stochastic_elements() == [f"{name}={value}"]
    cfg = EngineConfig()  # all four, in STOCHASTIC_PARAMETERS order whatever the order they were set in
    for name, value in reversed(values.items()):
        section, field_name = name.split(".")
        setattr(getattr(cfg, section), field_name, value)
    assert cfg.stochastic_elements() == [f"{name}={value}" for name, value in values.items()]
    cfg = EngineConfig.research()  # back to 0 is off again
    cfg.sensors.odometry_speed_noise = 0.0
    cfg.sensors.odometry_turn_noise = 0.0
    cfg.basal_ganglia.softmax_temperature = 0.0
    assert cfg.stochastic_elements() == []
