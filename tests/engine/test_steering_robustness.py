"""Robust memory steering: freeze habituation, dwell extinction, primary-only map
content, cue gating and homeostatic pacing.

Each mechanism has a config switch. The last test proves the redesign is purely
additive: with every switch off (and the old value_gain), the lab-console
scenarios reproduce, bit for bit, traces recorded on the code before it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from brain.contracts import Observation, VisionRay
from brain.systems.basal_ganglia import _channel_scores, cue_gate_weight, wall_gate_signals
from brain.systems.value_memory import ValueMemory
from core.config import BasalGangliaConfig, EngineConfig
from core.engine import Engine
from core.world import WorldObject
from metrics.hash import RunHash
from ui.scenarios import make_scenario

# --------------------------------------------------------------------- helpers


def _set(config: Any, key: str, value: Any) -> None:
    obj = config
    *path, last = key.split(".")
    for part in path:
        obj = getattr(obj, part)
    assert hasattr(obj, last), key
    setattr(obj, last, value)


def _scenario_engine(scenario_id: str, *, seed: int = 1, noise: float = 0.0, overrides: Dict[str, Any] | None = None):
    scenario = make_scenario(scenario_id)
    config = scenario.config()
    config.sensors.noise = noise
    for key, value in (overrides or {}).items():
        _set(config, key, value)
    engine = Engine(seed=seed, config=config)
    scenario.setup(engine)
    return scenario, engine


def _step(scenario, engine) -> Any:
    td = engine.run(1)[0]
    scenario.on_tick(engine, td.tick)
    return td


def _run_hash(scenario_id: str, ticks: int, **kwargs) -> str:
    scenario, engine = _scenario_engine(scenario_id, **kwargs)
    run_hash = RunHash()
    for _ in range(ticks):
        run_hash.update(_step(scenario, engine))
    return run_hash.hexdigest()


def _obs(rays: Tuple[VisionRay, ...] = (), pain: float = 0.0) -> Observation:
    return Observation(vision_rays=rays, whisker_hits=(False, False), pain_signal=pain, forward_delta=0.0, turn_delta=0.0)


# ------------------------------------------------------- C1 freeze habituation


def _hazard_run(freeze_tau: float, ticks: int = 600):
    """hazard_field at heading 0 walks straight into a hazard's pain zone; no memory steering."""
    scenario, engine = _scenario_engine(
        "hazard_field", overrides={"basal_ganglia.value_gain": 0.0, "basal_ganglia.freeze_tau": freeze_tau}
    )
    streak = longest = 0
    for _ in range(ticks):
        _step(scenario, engine)
        ctx = engine.context
        frozen = ctx.action_name == "REST" and ctx.observation.pain_signal > 0.5
        streak = streak + 1 if frozen else 0
        longest = max(longest, streak)
    return scenario, longest, streak


def test_freeze_habituation_releases_a_pain_freeze_without_memory():
    # Without habituation, pain-REST is absorbing: resting keeps pain constant,
    # so the agent never leaves the pain zone (memory, the only other release,
    # is switched off here).
    stuck, longest_off, final_off = _hazard_run(freeze_tau=0.0)
    assert final_off > 500 and stuck.collected == 0
    # With habituation the freeze is brief and the agent goes on to forage.
    free, longest_on, final_on = _hazard_run(freeze_tau=15.0)
    assert longest_on < 30 and final_on < 30
    assert free.collected >= 5


def test_freeze_habituation_is_an_exact_no_op_without_hazards():
    for scenario_id in ("foraging", "open_field"):
        for noise in (0.0, 0.03):
            on = _run_hash(scenario_id, 500, noise=noise)
            off = _run_hash(scenario_id, 500, noise=noise, overrides={"basal_ganglia.freeze_tau": 0.0})
            assert on == off, (scenario_id, noise)
    scenario, engine = _scenario_engine("foraging", noise=0.03)
    for _ in range(300):
        _step(scenario, engine)
        assert engine.context.freeze_habituation == 1.0


def test_freeze_habituation_scales_only_the_pain_rest_term():
    cfg = BasalGangliaConfig()
    obs = _obs(pain=0.8)
    full = _channel_scores(obs, 0.0, 1.0, False, cfg, {"NE": 0.4})
    half = _channel_scores(obs, 0.0, 1.0, False, cfg, {"NE": 0.4}, freeze_habituation=0.5)
    pain_rest = cfg.rest_pain_gain * (1 + cfg.ne_threat_gain * 0.4) * 0.8
    assert half["REST"] == pytest.approx(full["REST"] - 0.5 * pain_rest)
    for name in ("FORWARD", "TURN_LEFT", "TURN_RIGHT"):
        assert half[name] == full[name]


def test_begin_episode_resets_the_freeze_level():
    _, engine = _scenario_engine("hazard_field", overrides={"basal_ganglia.value_gain": 0.0})
    engine.run(10)
    assert engine._freeze_level > 0.0
    engine.begin_episode()
    assert engine._freeze_level == 0.0


# --------------------------------------------------------- C2 dwell extinction


def test_dwell_extinction_charges_only_dwelling_on_positive_cells():
    vm = ValueMemory(learning_rate=0.5, discount=0.9, dwell_extinction=0.1)
    vm.record((0, 0), 0.0)  # first step: no predecessor
    vm.record((0, 0), 0.0)  # dwelling, but V(0,0) == 0: not charged
    assert vm.value_of((0, 0)) == 0.0

    vm.values[(0, 0)] = 0.5
    vm.record((0, 0), 0.0)  # dwelling on a positive cell: charged
    plain = 0.5 + 0.5 * (0.0 + 0.9 * 0.5 - 0.5)
    assert vm.value_of((0, 0)) == pytest.approx(plain + 0.5 * -0.1)
    # The trajectory keeps the reward actually received, never the charge.
    assert vm.trajectory[-1] == ((0, 0), 0.0)

    vm.values[(1, 0)] = 0.5
    before = vm.value_of((0, 0))
    vm.record((1, 0), 0.0)  # crossing into another (positive) cell is never charged
    assert vm.value_of((0, 0)) == pytest.approx(before + 0.5 * (0.9 * 0.5 - before))

    vm.values[(1, 0)] = -0.2
    vm.record((1, 0), 0.0)  # dwelling on a negative cell: not charged
    assert vm.value_of((1, 0)) == pytest.approx(-0.2 + 0.5 * (0.9 * -0.2 + 0.2))
    assert all(reward == 0.0 for _, reward in vm.trajectory)


def test_replay_charges_dwelling_only_while_the_cell_is_still_positive():
    vm = ValueMemory(learning_rate=0.5, discount=0.9, dwell_extinction=0.1)
    vm.values[(0, 0)] = 0.5
    vm.record((0, 0), 0.0)
    vm.record((0, 0), 0.0)
    vm.values[(0, 0)] = 0.5
    vm.replay_transition(0)  # positive at replay time: charged, as online
    assert vm.value_of((0, 0)) == pytest.approx(0.5 + 0.5 * (-0.1 + 0.9 * 0.5 - 0.5))
    vm.values[(0, 0)] = -0.05
    vm.replay_transition(0)  # no longer positive: not charged
    assert vm.value_of((0, 0)) == pytest.approx(-0.05 + 0.5 * (0.9 * -0.05 + 0.05))
    vm.values[(0, 0)] = 0.5
    vm.replay_transition(0, dwell_extinction=0.0)  # an explicit cost overrides the attribute
    assert vm.value_of((0, 0)) == pytest.approx(0.5 + 0.5 * (0.9 * 0.5 - 0.5))


def test_consolidating_a_dwell_trajectory_extinguishes_but_never_makes_aversion():
    # Review finding F1: the charged reward used to be logged and replayed
    # unconditionally, so consolidate(60) drove a dwelt-on cell to the
    # self-transition fixed point -c / (1 - gamma) = -0.2: extinction became
    # aversion. Now replay charges only while the cell is still positive, so the
    # charge alone can take a cell at most one backup below zero (-lr * c, the
    # same floor as online), after which bootstrapping relaxes it back to 0.
    lr, c = 0.2, 0.02
    vm = ValueMemory(learning_rate=lr, discount=0.9, dwell_extinction=c)
    vm.values[(0, 0)] = 0.05  # a small self-made peak
    for _ in range(10):  # the agent dwells on it for 10 ticks
        vm.record((0, 0), 0.0)
    online = vm.value_of((0, 0))
    assert 0.0 <= online < 0.05
    lowest = online
    for _ in range(60):
        vm.consolidate(passes=1)
        lowest = min(lowest, vm.value_of((0, 0)))
    assert lowest >= -lr * c - 1e-12
    assert -1e-3 < vm.value_of((0, 0)) <= online  # extinguished to ~0, not -0.2
    assert vm.value_of((0, 0)) > -c / (1 - 0.9) / 10


def test_dwell_extinction_defaults_off_in_the_class_and_on_in_the_engine():
    vm = ValueMemory()
    vm.values[(0, 0)] = 0.5
    vm.record((0, 0), 0.0)
    vm.record((0, 0), 0.0)
    assert vm.value_of((0, 0)) == pytest.approx(0.5 + 0.2 * (0.9 * 0.5 - 0.5))  # uncharged
    assert EngineConfig().value_memory.dwell_extinction == 0.02
    assert Engine(seed=1).value_memory.dwell_extinction == 0.02


def test_the_engine_passes_the_config_extinction_and_never_overwrites_the_attribute():
    # Review nit F10: the engine used to copy the config into the attribute every
    # tick, silently reverting a direct assignment. The config is now passed
    # explicitly and the attribute is left alone.
    engine = Engine(seed=1)
    seen = []
    record = engine.value_memory.record
    engine.value_memory.record = lambda cell, reward, dwell_extinction=None: (
        seen.append(dwell_extinction), record(cell, reward, dwell_extinction))[1]
    engine.value_memory.dwell_extinction = 0.07
    engine.config.value_memory.dwell_extinction = 0.03
    engine.run(3)
    assert seen == [0.03, 0.03, 0.03]
    assert engine.value_memory.dwell_extinction == 0.07


# ------------------------------------------------- C3 primary-only map content


def _approach(learn_shaping: bool, ticks: int = 4):
    config = EngineConfig()
    config.value_memory.learn_shaping = learn_shaping
    engine = Engine(seed=3, config=config)
    engine.world.add_object(WorldObject(6.0, 0.0, 0.5, "target"))
    rows = []
    for _ in range(ticks):  # facing the target; it is reached only after these ticks
        td = engine.run(1)[0]
        ctx = engine.context
        rows.append((td.reward, ctx.map_reward, ctx.neuromodulators["DA"]))
    return engine, rows


def test_approach_shaping_stays_out_of_the_map_but_reaches_dopamine():
    engine, rows = _approach(learn_shaping=False)
    assert all(map_reward == 0.0 for _, map_reward, _ in rows)
    assert all(reward > 0.0 for reward, _, _ in rows[1:])  # shaping is in ctx.reward / TickData
    assert max(da for _, _, da in rows) > 0.5  # and dopamine sees it
    assert max(engine.value_memory.values.values(), default=0.0) == 0.0

    shaped, rows_shaped = _approach(learn_shaping=True)
    assert [r[0] for r in rows_shaped] == [r[0] for r in rows]  # same reward either way
    assert all(map_reward == reward for reward, map_reward, _ in rows_shaped)
    assert max(shaped.value_memory.values.values()) > 0.0


def test_primary_map_reward_keeps_contact_and_real_pain_only():
    _, engine = _scenario_engine("hazard_field")
    contact = pain = False
    for _ in range(600):
        engine.run(1)
        ctx = engine.context
        p = ctx.observation.pain_signal
        expected_pain = -engine.config.reward.pain_weight * p if p > engine.map_pain_floor() else 0.0
        diff = ctx.map_reward - expected_pain
        assert diff == pytest.approx(0.0) or diff == pytest.approx(engine.config.reward.contact_bonus)
        contact |= diff > 0.5
        pain |= expected_pain < 0.0
    assert pain and contact
    # Sensor-noise pain (< 0.05) never enters the map.
    _, noisy = _scenario_engine("open_field", noise=0.03)
    for _ in range(200):
        noisy.run(1)
        assert noisy.context.map_reward == 0.0


def test_console_level_noise_cannot_write_pain_into_the_map():
    # Review finding: with a fixed 0.05 floor, console noise above 0.05 put pure
    # noise pain into the map (open_field, no hazards, noise 0.1: 132 of 500
    # ticks, min V -0.15). The floor is now max(0.05, sensors.noise).
    _, engine = _scenario_engine("open_field", noise=0.1)
    assert engine.map_pain_floor() == 0.1
    noisy_pain = 0
    for _ in range(500):
        engine.run(1)
        noisy_pain += engine.context.observation.pain_signal > 0.05
        assert engine.context.map_reward == 0.0
    assert noisy_pain > 50  # the noise really was above the old fixed floor
    assert min(engine.value_memory.values.values(), default=0.0) == 0.0


# ---------------------------------------------------------- C4 cue gating


def test_cue_gate_weight():
    close = _obs((VisionRay(0.2, "wall", 0.5), VisionRay(0.1, "target", 0.0)))
    assert cue_gate_weight(close, 2.0) == 0.0
    assert cue_gate_weight(_obs((VisionRay(0.3, "wall", 0.0),)), 2.0) == 1.0
    assert cue_gate_weight(_obs(()), 2.0) == 1.0
    assert cue_gate_weight(_obs((VisionRay(0.8, "target", 0.3),)), 2.0) == pytest.approx(0.6)
    assert cue_gate_weight(close, 0.0) == 1.0  # disabled
    assert cue_gate_weight(_obs((VisionRay(0.1, "hidden", 0.0),)), 2.0) == 1.0  # only visible targets count


def test_value_signals_on_the_context_are_the_gated_ones():
    scenario, engine = _scenario_engine("foraging", noise=0.03)
    muted = 0
    for _ in range(1500):
        _step(scenario, engine)
        ctx = engine.context
        assert ctx.cue_gate == cue_gate_weight(ctx.observation, engine.config.basal_ganglia.cue_gate_gain)
        if ctx.cue_gate == 0.0:
            muted += 1
            assert ctx.value_signals == (0.0, 0.0, 0.0)
        # The scores were produced from exactly the (gated) signals on the context.
        bg = engine.config.basal_ganglia
        rebuilt = _channel_scores(
            ctx.observation, ctx.wm_novelty, ctx.trn_gate_value, ctx.microsleep_active, bg,
            ctx.neuromodulators, *ctx.value_signals, ctx.criticality_gain, ctx.freeze_habituation,
            bg.pace_rest_bonus if ctx.pacing_active else 0.0,
        )
        assert rebuilt == ctx.action_scores
    assert muted > 0


# ------------------------------------------------------ C7 wall gating


def test_wall_gate_signals():
    wall = _obs((VisionRay(0.2, "wall", 0.0),))  # wall close ahead: closeness 0.8
    a, l, r, w = wall_gate_signals(1.0, -1.0, -1.0, wall, 1.0)
    assert w == pytest.approx(0.2)
    assert (a, l, r) == (pytest.approx(0.2), pytest.approx(-0.2), pytest.approx(-0.2))
    # A turn toward a better side and FORWARD giving way to it are kept.
    assert wall_gate_signals(-1.0, 1.0, -1.0, wall, 1.0)[:3] == (-1.0, 1.0, pytest.approx(-0.2))
    # No wall ahead (side walls and targets do not count), or gain 0: exact pass-through.
    side = _obs((VisionRay(0.1, "wall", 0.5), VisionRay(0.3, "target", 0.0)))
    assert wall_gate_signals(0.7, -0.3, 0.2, side, 1.0) == (0.7, -0.3, 0.2, 1.0)
    assert wall_gate_signals(0.7, -0.3, 0.2, _obs(()), 1.0) == (0.7, -0.3, 0.2, 1.0)
    assert wall_gate_signals(1.0, -1.0, -1.0, wall, 0.0) == (1.0, -1.0, -1.0, 1.0)
    # The split property max(signals) >= 0 survives gating.
    for sig in ((0.5, -1.0, -1.0), (-1.0, 1.0, 0.0), (0.0, -0.5, -0.5)):
        assert max(wall_gate_signals(*sig, wall, 1.0)[:3]) >= 0.0


def test_wall_gate_stops_memory_pinning_the_agent_against_a_wall():
    # foraging with pacing off, seed 5, noise 0.03, gain 1.5: without the gate the
    # agent spends hundreds of ticks pushing FORWARD into the boundary because
    # the remembered value lies beyond it, and collects 13 items (34-36 with it,
    # 36 at value_gain 0).
    def run(wall_gate_gain):
        scenario, engine = _scenario_engine("foraging", seed=5, noise=0.03, overrides={
            "basal_ganglia.pace_rest_bonus": 0.0, "basal_ganglia.wall_gate_gain": wall_gate_gain})
        gated = 0
        for _ in range(3000):
            _step(scenario, engine)
            gated += engine.context.wall_gate < 1.0
        return scenario.collected, gated

    pinned, _ = run(0.0)
    free, gated = run(1.0)
    assert pinned <= 20 and free >= 30 and gated > 0


# --------------------------------------------------------- C6 pacing latch


def test_pacing_latch_has_hysteresis():
    config = EngineConfig()
    config.basal_ganglia.pace_rest_bonus = 5.0
    engine = Engine(seed=1, config=config)
    seen: List[Tuple[float, bool]] = []
    for atp in (1.0, 0.6, 0.3, 0.6, 0.8, 0.95, 0.6):
        engine.astrocyte.atp = atp
        engine.run(1)
        ctx = engine.context
        seen.append((ctx.atp, ctx.pacing_active))
        if ctx.pacing_active:
            assert ctx.action_name == "REST" and ctx.action_scores["REST"] >= 5.0
    assert [active for _, active in seen] == [False, False, True, True, True, False, False]
    assert 0.4 < seen[1][0] < 0.9 and 0.4 < seen[3][0] < 0.9  # same ATP band, opposite states


def test_pacing_latch_releases_when_the_atp_ceiling_is_below_the_absolute_threshold():
    # Review finding: with absolute thresholds (0.4 / 0.9 ATP) and
    # astrocyte.atp_baseline = 0.85, resting could never reach 0.9, so the latch
    # never released and REST won for good (foraging seed 1: 4 items, REST on
    # 3926 of 4000 ticks). The thresholds are now fractions of the baseline.
    scenario, engine = _scenario_engine(
        "foraging", overrides={"astrocyte.atp_baseline": 0.85, "astrocyte.atp": 0.85}
    )
    latched = released = 0
    moves_after_latch = 0
    for _ in range(4000):
        was = engine._recovering
        _step(scenario, engine)
        now = engine._recovering
        latched += now and not was
        released += was and not now
        moves_after_latch += latched > 0 and engine.context.action_name != "REST"
    assert latched >= 1 and released >= 1
    assert moves_after_latch > 1000
    assert scenario.collected >= 20


def test_pacing_off_by_default_is_a_no_op():
    assert BasalGangliaConfig().pace_rest_bonus == 0.0
    # open_field runs itself into microsleep, so ATP crosses both thresholds;
    # with the bonus at 0 the latch thresholds must not matter at all.
    a = _run_hash("open_field", 800)
    b = _run_hash("open_field", 800, overrides={"basal_ganglia.pace_low": 0.95, "basal_ganglia.pace_high": 0.99})
    assert a == b
    scenario, engine = _scenario_engine("open_field")
    lows = 0
    for _ in range(800):
        _step(scenario, engine)
        lows += engine.context.atp < 0.4
        assert engine.context.pacing_active is False
    assert lows > 0


def test_pacing_is_on_only_in_the_energy_limited_scenarios():
    bonus = {sid: make_scenario(sid).config().basal_ganglia.pace_rest_bonus for sid in
             ("open_field", "beacon", "foraging", "hazard_field", "memory_maze")}
    assert bonus == {"open_field": 0.0, "beacon": 5.0, "foraging": 5.0, "hazard_field": 5.0, "memory_maze": 0.0}


# ---------------------------------------------------- per-engine state isolation


def _trace(scenario, engine, ticks: int, observe) -> List[str]:
    out = []
    for _ in range(ticks):
        td = _step(scenario, engine)
        observe(engine.context)
        out.append(hashlib.sha256(json.dumps(td.to_ordered_dict(), sort_keys=True).encode()).hexdigest())
    return out


def test_interleaved_engines_match_separate_runs():
    specs = [("hazard_field", 1, 0.0), ("beacon", 2, 0.03), ("hazard_field", 3, 0.03)]
    exercised = {"freeze": False, "pacing": False}

    def observe(ctx):
        exercised["freeze"] |= ctx.freeze_habituation < 1.0
        exercised["pacing"] |= ctx.pacing_active

    ticks = 1200
    separate = [_trace(*_scenario_engine(sid, seed=seed, noise=noise), ticks, observe) for sid, seed, noise in specs]
    runs = [_scenario_engine(sid, seed=seed, noise=noise) for sid, seed, noise in specs]
    interleaved: List[List[str]] = [[] for _ in specs]
    for _ in range(ticks):
        for i, (scenario, engine) in enumerate(runs):
            interleaved[i] += _trace(scenario, engine, 1, observe)
    assert interleaved == separate
    assert exercised == {"freeze": True, "pacing": True}  # the per-engine state was actually used


# ------------------------------------------------------- legacy equivalence

LEGACY_TICKS = 600
LEGACY_SEED = 1
LEGACY_CASES = [
    (scen, noise, gain)
    for scen in ("open_field", "beacon", "foraging", "hazard_field", "memory_maze")
    for noise in (0.0, 0.03)
    for gain in ((0.8, 1.5) if scen == "memory_maze" else (0.8,))
]
ALL_OFF = {
    "basal_ganglia.freeze_tau": 0.0,
    "value_memory.dwell_extinction": 0.0,
    "value_memory.learn_shaping": True,
    "basal_ganglia.cue_gate_gain": 0.0,
    "basal_ganglia.pace_rest_bonus": 0.0,
    "basal_ganglia.value_steer": "maxnorm",
    "basal_ganglia.wall_gate_gain": 0.0,
}
LEGACY_HASHES = json.loads((Path(__file__).with_name("steering_legacy_hashes.json")).read_text())


def legacy_digest(scenario_id: str, noise: float, value_gain: float, overrides: Dict[str, Any]) -> str:
    """Digest of a scenario run: TickData stream, scores and value signals, final map and status.

    This exact function, with no overrides, produced steering_legacy_hashes.json
    on the code before the redesign (commit 6c0ea9d).
    """
    scenario = make_scenario(scenario_id)
    config = scenario.config()
    config.sensors.noise = noise
    config.basal_ganglia.value_gain = value_gain
    for key, value in overrides.items():
        _set(config, key, value)
    engine = Engine(seed=LEGACY_SEED, config=config)
    scenario.setup(engine)
    run_hash = RunHash()
    extra = hashlib.sha256()
    for _ in range(LEGACY_TICKS):
        td = engine.run(1)[0]
        run_hash.update(td)
        ctx = engine.context
        extra.update(repr((sorted(ctx.action_scores.items()), ctx.value_signals)).encode())
        scenario.on_tick(engine, td.tick)
    values = sorted(engine.value_memory.values.items())
    extra.update(repr(values).encode())
    extra.update(repr(list(engine.value_memory.trajectory)).encode())
    extra.update(json.dumps(scenario.status(), sort_keys=True, default=str).encode())
    return hashlib.sha256((run_hash.hexdigest() + extra.hexdigest()).encode()).hexdigest()


@pytest.mark.parametrize("scenario_id,noise,value_gain", LEGACY_CASES)
def test_all_features_off_reproduces_the_pre_redesign_traces(scenario_id, noise, value_gain):
    digest = legacy_digest(scenario_id, noise, value_gain, ALL_OFF)
    assert digest == LEGACY_HASHES["cases"][f"{scenario_id}|{noise}|{value_gain}"]


def test_the_new_defaults_do_change_behaviour():
    # Guard against a vacuous legacy test: the defaults must actually differ.
    assert legacy_digest("hazard_field", 0.0, 0.8, {}) != LEGACY_HASHES["cases"]["hazard_field|0.0|0.8"]
