"""The two research-profile confounds removed in M2a (docs/decisions.md G26; docs/profiles.md).

1. **The forward clamp.** Odometry speed noise is applied before the Observation's
   forward range is enforced. Under the legacy range (``sensors.forward_delta_limit``
   1.0) a full-thrust FORWARD step of 1.0 sits at the top of the range, so a positive
   speed error is clamped away and a full-speed step's estimate averages
   1 - sigma / sqrt(2 pi) = 0.980 at sigma 0.05 (docs/odometry.md). The research
   profile now declares a range of 2.0, so the error keeps both signs and the mean
   is 1.0. The legacy profile keeps 1.0 and its trace hash (the determinism gate).
2. **The checksum "novelty" bit.** It still enters legacy action selection (0.2 on
   FORWARD through ``novelty_gain``, 0.3 on each TURN through ``novelty_turn_gain``,
   the literal it replaces); the research profile sets both gains to 0, so the bit
   is logged and feeds the ACh and NE traces but moves no decision.

Each test is named for what it proves. Runs are a few hundred to 3,000 ticks.
"""

from __future__ import annotations

import math
import statistics
from typing import List

import pytest

from brain.contracts import Observation, VisionRay
from brain.systems.basal_ganglia import _channel_scores, select_action_with_scores
from core.config import BasalGangliaConfig, EngineConfig, SensorConfig
from core.engine import Engine
from core.entities import Agent
from core.sensors import _compute_egomotion, gather_observation
from core.world import World

TICKS = 3000


class _FixedDraws:
    """A stand-in for an ``RNGStream`` that returns the given standard normal deviates in order."""

    def __init__(self, draws: List[float]) -> None:
        self._draws = list(draws)

    def gauss(self, mu: float, sigma: float) -> float:
        return mu + sigma * self._draws.pop(0)


def _agent_after_forward(step: float = 1.0) -> Agent:
    agent = Agent(id=0, pos=(0.0, 0.0), heading=0.0)
    agent.apply_motion(forward_delta=step, turn_delta=0.0)
    return agent


# --- 1. the forward clamp ---------------------------------------------------------


def test_the_research_range_keeps_a_positive_speed_error_that_the_legacy_range_clamps_away() -> None:
    legacy = SensorConfig(odometry_speed_noise=0.05)
    research = SensorConfig(odometry_speed_noise=0.05, forward_delta_limit=2.0)
    assert legacy.forward_delta_limit == 1.0  # the legacy contract is the default
    agent = _agent_after_forward(1.0)
    # xi = +1: a 5% fast reading. Legacy clamps it to 1.0; research keeps 1.05.
    assert _compute_egomotion(agent, legacy, _FixedDraws([1.0]))[0] == 1.0
    assert _compute_egomotion(agent, research, _FixedDraws([1.0]))[0] == pytest.approx(1.05)
    # xi = -1: a 5% slow reading survives either range.
    assert _compute_egomotion(agent, legacy, _FixedDraws([-1.0]))[0] == pytest.approx(0.95)
    assert _compute_egomotion(agent, research, _FixedDraws([-1.0]))[0] == pytest.approx(0.95)
    # The research range is a clamp too, at 2.0: an impossible 25-sigma reading is held there.
    assert _compute_egomotion(agent, research, _FixedDraws([25.0]))[0] == 2.0
    # Without a config the legacy range applies, and at sigma 0 nothing is drawn or changed.
    assert _compute_egomotion(agent)[0] == 1.0
    assert _compute_egomotion(agent, SensorConfig(forward_delta_limit=2.0), _FixedDraws([]))[0] == 1.0


def test_validate_takes_the_contracts_range_and_defaults_to_the_legacy_one() -> None:
    obs = Observation(vision_rays=(VisionRay(0.5, "wall", 0.0),), whisker_hits=(False, False), pain_signal=0.0,
                      forward_delta=1.3, turn_delta=0.0)
    with pytest.raises(ValueError):
        obs.validate()  # the legacy range, 1.0
    obs.validate(forward_limit=2.0)
    with pytest.raises(ValueError):
        obs.validate(forward_limit=0.0)
    # gather_observation validates against the config's range, so a wide reading passes in research.
    world = World()
    agent = _agent_after_forward(1.0)
    world.add_agent(agent)
    stream = Engine(seed=3, config=EngineConfig.research()).streams["sensors_odometry"]
    cfg = EngineConfig.research().sensors
    cfg.odometry_speed_noise = 0.4  # large, so some draw exceeds 1.0 within a few ticks
    seen_above_one = False
    for _ in range(50):
        obs = gather_observation(agent, world, config=cfg, odometry_stream=stream)
        seen_above_one = seen_above_one or obs.forward_delta > 1.0
        assert abs(obs.forward_delta) <= 2.0
    assert seen_above_one


def test_a_full_speed_step_is_estimated_at_one_on_average_under_the_research_profile() -> None:
    """The confound measured: a straight walk in a box too big to reach a wall, research
    defaults (speed noise 0.05), 3,000 ticks. Under the legacy range the mean estimated
    full-thrust step was 0.980 (docs/odometry.md: 1 - 0.05 / sqrt(2 pi) = 0.9801); under
    the research range it is 1.0 within sampling error, with both signs present in about
    equal measure."""
    def run(limit: float):
        cfg = EngineConfig.research()
        cfg.place.enabled = False  # a 5,000-unit box would hold a 10^8-cell population; the odometry contract needs none
        cfg.history.enabled = False  # its traces are over that population (G54)
        cfg.value_memory.source = "tabular"
        cfg.world.bounds = (5000.0, 5000.0)
        cfg.sensors.forward_delta_limit = limit
        engine = Engine(seed=1337, config=cfg)
        trace = engine.run(TICKS)
        steps = [trace[t].obs_forward_delta for t in range(1, TICKS) if trace[t - 1].action_name == "FORWARD"]
        return steps

    research = run(2.0)
    legacy_range = run(1.0)
    assert len(research) > 2000 and len(legacy_range) > 2000  # the barren-world walk is nearly all FORWARD
    mean_r = statistics.fmean(research)
    mean_l = statistics.fmean(legacy_range)
    sd = statistics.pstdev(research)
    assert abs(mean_r - 1.0) < 3 * sd / math.sqrt(len(research)) + 1e-9, (mean_r, sd)  # zero-mean
    assert abs(mean_r - 1.0) < 0.004
    assert 0.9801 - 0.004 < mean_l < 0.9801 + 0.004, mean_l  # the clamp bias, reproduced at the legacy range
    assert max(legacy_range) <= 1.0
    above = sum(s > 1.0 for s in research) / len(research)
    assert 0.44 < above < 0.56, above  # both signs, about half each
    assert 0.03 < sd < 0.07  # the 5% multiplicative error, as drawn
    # The two runs draw the same deviates (same seed, same stream): the research reading
    # equals the legacy one wherever the legacy one was not clamped.
    for r, l in zip(research, legacy_range):
        if l < 1.0:
            assert r == l


def test_the_body_does_not_read_the_range_and_the_legacy_profile_is_unchanged() -> None:
    cfg_a = EngineConfig.research()
    cfg_b = EngineConfig.research()
    for cfg in (cfg_a, cfg_b):  # no population in the 5,000-unit box (as above), so no history either (G54)
        cfg.place.enabled = False
        cfg.history.enabled = False
        cfg.value_memory.source = "tabular"
    cfg_b.sensors.forward_delta_limit = 1.0
    cfg_a.basal_ganglia.softmax_temperature = cfg_b.basal_ganglia.softmax_temperature = 0.0  # a deterministic arbiter
    cfg_a.world.bounds = cfg_b.world.bounds = (5000.0, 5000.0)
    a = Engine(seed=1, config=cfg_a).run(300)
    b = Engine(seed=1, config=cfg_b).run(300)
    # Nothing in the barren box reads the estimate back into behaviour, so the bodies walk one path
    # while the estimates differ from the first full-thrust tick with a positive draw.
    assert [td.pos for td in a] == [td.pos for td in b]
    assert [td.action_name for td in a] == [td.action_name for td in b]
    assert any(ta.obs_forward_delta > 1.0 for ta in a) and all(tb.obs_forward_delta <= 1.0 for tb in b)
    assert EngineConfig().sensors.forward_delta_limit == EngineConfig.legacy().sensors.forward_delta_limit == 1.0


# --- 2. the novelty bit -----------------------------------------------------------


def _observations() -> List[Observation]:
    """A few observations: open space, a wall ahead, a target to the left, pain."""
    rays = lambda c, l, r, kinds: (  # noqa: E731
        VisionRay(l, kinds[0], 0.6), VisionRay(c, kinds[1], 0.0), VisionRay(r, kinds[2], -0.6)
    )
    return [
        Observation(rays(1.0, 1.0, 1.0, ("", "", "")), (False, False), 0.0, 1.0, 0.0),
        Observation(rays(0.1, 0.2, 0.9, ("wall", "wall", "")), (True, False), 0.0, 0.3, 0.3),
        Observation(rays(0.6, 1.0, 1.0, ("target", "", "")), (False, False), 0.0, 1.0, 0.0),
        Observation(rays(1.0, 0.5, 1.0, ("", "hazard", "")), (False, False), 0.6, 0.0, 0.0),
    ]


def test_in_the_research_profile_the_novelty_bit_moves_no_channel_score() -> None:
    bg = EngineConfig.research().basal_ganglia
    assert bg.novelty_gain == 0.0 and bg.novelty_turn_gain == 0.0
    modulators = {"DA": 0.2, "NE": 1.0, "ACh": 1.0, "5HT": 0.5}  # dopamine low: the legacy novelty term would be boosted
    for obs in _observations():
        off = _channel_scores(obs, 0.0, 1.0, False, bg, modulators, 0.1, -0.2, 0.3)
        on = _channel_scores(obs, 1.0, 1.0, False, bg, modulators, 0.1, -0.2, 0.3)
        assert on == off


def test_in_the_legacy_profile_the_bit_adds_exactly_the_documented_terms() -> None:
    bg = BasalGangliaConfig()
    assert (bg.novelty_gain, bg.novelty_turn_gain) == (0.2, 0.3)
    baseline = {"DA": 0.5, "NE": 0.0, "ACh": 0.0, "5HT": 0.5}  # no dopamine modulation of the FORWARD term
    for obs in _observations():
        off = _channel_scores(obs, 0.0, 1.0, False, bg, baseline)
        on = _channel_scores(obs, 1.0, 1.0, False, bg, baseline)
        assert on["FORWARD"] - off["FORWARD"] == pytest.approx(0.2)
        assert on["TURN_LEFT"] - off["TURN_LEFT"] == pytest.approx(0.3)
        assert on["TURN_RIGHT"] - off["TURN_RIGHT"] == pytest.approx(0.3)
        assert on["REST"] == off["REST"]
    # The turn term is the config field, so a different value shows up as such.
    half = BasalGangliaConfig(novelty_turn_gain=0.15)
    obs = _observations()[0]
    assert (_channel_scores(obs, 1.0, 1.0, False, half, baseline)["TURN_LEFT"]
            - _channel_scores(obs, 0.0, 1.0, False, half, baseline)["TURN_LEFT"]) == pytest.approx(0.15)


def test_the_bit_is_still_computed_logged_and_fed_to_the_traces_under_research() -> None:
    """Research profile, deterministic arbiter, exact odometry, so the bit is 0 on ticks where the
    observation did not change (a REST, or a step that changes no ray) and 1 where it did."""
    cfg = EngineConfig.research()
    cfg.sensors.odometry_speed_noise = 0.0
    cfg.sensors.odometry_turn_noise = 0.0
    cfg.basal_ganglia.softmax_temperature = 0.0
    trace = Engine(seed=1337, config=cfg).run(600)
    values = {td.wm_novelty for td in trace}
    assert values <= {0.0, 1.0} and 1.0 in values
    for td in trace:
        assert td.neuromodulators["ACh"] == td.wm_novelty
        assert td.neuromodulators["NE"] == pytest.approx(0.5 * td.obs_pain + 0.5 * td.wm_novelty)
    # And the decision is the same whatever the bit says: re-score every tick with the bit
    # flipped and the same inputs, the chosen action does not move.
    engine = Engine(seed=1337, config=cfg)
    for _ in range(300):
        td = engine.run(1)[0]
        ctx = engine.context
        assert ctx is not None and ctx.observation is not None
        flipped, _ = select_action_with_scores(
            ctx.observation, 1.0 - ctx.wm_novelty, ctx.trn_gate_value, ctx.microsleep_active, cfg.basal_ganglia,
            ctx.neuromodulators, *ctx.value_signals, ctx.criticality_gain, ctx.freeze_habituation,
        )
        assert flipped.name == td.action_name


def test_decoupling_the_bit_changes_the_research_walk_and_leaves_legacy_alone() -> None:
    """With the bit coupled (the pre-M2a research profile), the 0.3 turn term made a TURN a
    1-in-500 softmax draw when nothing is in view (docs/odometry.md); without it a TURN is
    an exp(-0.8 / 0.1) draw. The two research walks part; legacy keeps its gains."""
    coupled = EngineConfig.research()
    coupled.basal_ganglia.novelty_gain = 0.2
    coupled.basal_ganglia.novelty_turn_gain = 0.3
    a = Engine(seed=1337, config=EngineConfig.research()).run(300)
    b = Engine(seed=1337, config=coupled).run(300)
    assert [td.pos for td in a] != [td.pos for td in b]
    # Legacy is bit-identical by rule; the determinism gate (tests/determinism/test_trace_hash.py)
    # is the test of that, so this file does not read the committed hashes itself.
    assert EngineConfig().diff(EngineConfig.legacy()) == []
    assert (EngineConfig().basal_ganglia.novelty_gain, EngineConfig().basal_ganglia.novelty_turn_gain) == (0.2, 0.3)
