"""The rodent-like body (core.body.RodentBody; M3 step 1, docs/prereg/m3_body.md, decisions G44)."""

import math

import pytest

from core.body import BODY_PRESETS, RodentBody, apply_body_preset
from core.config import BodyConfig, EngineConfig, UnitsConfig
from core.determinism import DEFAULT_SEED, DEFAULT_TICKS, hash_trace, load_baseline
from core.engine import Engine
from core.entities import Agent


class _Stream:
    def __init__(self) -> None:
        self.draws = 0

    def gauss(self, mu: float, sigma: float) -> float:
        self.draws += 1
        return 0.5


def _body(**fields) -> RodentBody:
    return RodentBody(BodyConfig(model="rodent", **fields), UnitsConfig(), _Stream())


def test_the_config_validates_and_the_default_is_the_discrete_body() -> None:
    assert BodyConfig().model == "discrete" and EngineConfig.research().body.model == "discrete"
    for bad in ({"model": "hexapod"}, {"run_speed": 0.0}, {"turn_speed": -0.1}, {"rotational_noise": float("nan")}):
        with pytest.raises(ValueError):
            BodyConfig(**bad)
    cfg = apply_body_preset(EngineConfig.research(), "rodent")
    assert cfg.body.model == "rodent" and cfg.body.rotational_noise == pytest.approx(2.0944, abs=1e-4) and cfg.body.speed_noise == 0.08
    assert EngineConfig.from_dict(cfg.to_dict()).diff(cfg) == []
    assert set(BODY_PRESETS) == {"discrete", "rodent_quiet", "rodent"}
    with pytest.raises(ValueError):
        apply_body_preset(EngineConfig(), "centaur")


def test_the_processes_relax_toward_the_action_targets_exactly() -> None:
    body = _body()
    agent = Agent(id=0, pos=(0.0, 0.0))
    body.step(agent, "FORWARD", (10.0, 10.0))
    a = math.exp(-0.2 / 0.7)
    assert body.speed == pytest.approx(0.5 * (1.0 - a)) and body.angular_velocity == 0.0
    assert agent.pos[0] == pytest.approx(body.speed * 0.2 / 0.1) and agent.pos[1] == 0.0
    for _ in range(40):
        body.step(agent, "FORWARD", (100.0, 10.0))
    assert body.speed == pytest.approx(0.5, abs=1e-4)  # 0.5 (1 - a^41)
    assert body.stream.draws == 0  # no noise configured: nothing drawn


def test_a_turn_is_made_in_place_and_rest_stills_the_body() -> None:
    body = _body()
    agent = Agent(id=0, pos=(0.0, 0.0))
    for _ in range(30):
        body.step(agent, "TURN_LEFT", (10.0, 10.0))
    assert body.speed == 0.0 and agent.pos == (0.0, 0.0)  # turn_speed 0: no turning circle
    assert body.angular_velocity == pytest.approx(1.5, abs=1e-9)
    a = math.exp(-0.2 / 0.08)
    assert agent.heading == pytest.approx(sum(0.2 * 1.5 * (1.0 - a ** k) for k in range(1, 31)), rel=1e-9)
    body.step(agent, "REST", (10.0, 10.0))
    assert abs(body.angular_velocity) < 1.5 * math.exp(-0.2 / 0.08) + 1e-12
    body.reset()
    assert body.speed == 0.0 and body.angular_velocity == 0.0


def test_noise_draws_from_the_stream_only_when_on() -> None:
    quiet = _body()
    noisy = _body(rotational_noise=2.0, speed_noise=0.08)
    agent_q, agent_n = Agent(id=0, pos=(0.0, 0.0)), Agent(id=0, pos=(0.0, 0.0))
    quiet.step(agent_q, "FORWARD", (10.0, 10.0))
    noisy.step(agent_n, "FORWARD", (10.0, 10.0))
    assert quiet.stream.draws == 0 and noisy.stream.draws == 2  # rotation first, then speed
    assert agent_n.heading != 0.0


def test_wall_following_turns_a_heading_into_a_wall_toward_the_nearer_parallel() -> None:
    body = _body()
    body.speed = 0.5  # running
    # 0.1 units from the north wall, heading 30 degrees into it: turned most of the way to east (0).
    h = body.align_to_walls(0.0, 9.9, math.radians(30.0), (10.0, 10.0))
    assert 0.0 <= h < math.radians(30.0) * 0.2
    # Heading away from the wall: untouched; outside the zone (0.1 m = 1 unit): untouched.
    assert body.align_to_walls(0.0, 9.9, math.radians(-30.0), (10.0, 10.0)) == math.radians(-30.0)
    assert body.align_to_walls(0.0, 8.0, math.radians(30.0), (10.0, 10.0)) == math.radians(30.0)
    # Turning in place (speed 0): no alignment, so a turn away from a wall can complete.
    body.speed = 0.0
    assert body.align_to_walls(0.0, 9.95, math.radians(80.0), (10.0, 10.0)) == math.radians(80.0)
    # Heading into the east wall at 100 degrees from it: the nearer parallel is north (pi/2).
    body.speed = 0.5
    h = body.align_to_walls(9.99, 0.0, math.radians(10.0), (10.0, 10.0))
    assert h > math.radians(10.0)


def test_the_engine_runs_the_rodent_body_deterministically_and_the_defaults_are_untouched() -> None:
    cfg = apply_body_preset(EngineConfig.research(), "rodent")
    a = Engine(seed=5, config=cfg).run(300, reset=True)
    b = Engine(seed=5, config=apply_body_preset(EngineConfig.research(), "rodent")).run(300, reset=True)
    assert [td.pos for td in a] == [td.pos for td in b]
    c = Engine(seed=6, config=apply_body_preset(EngineConfig.research(), "rodent")).run(300, reset=True)
    assert [td.pos for td in a] != [td.pos for td in c]  # the body's noise is seeded
    # Without odometry noise or the oracle's noise, the estimate integrates the rodent body's motion exactly.
    quiet = apply_body_preset(EngineConfig.research(), "rodent_quiet")
    quiet.sensors.odometry_speed_noise = quiet.sensors.odometry_turn_noise = quiet.sensors.heading_oracle_noise = 0.0
    quiet.basal_ganglia.softmax_temperature = 0.0
    eng = Engine(seed=1, config=quiet)
    trace = eng.run(400, reset=True)
    assert max(math.hypot(td.grid_x - td.pos[0], td.grid_y - td.pos[1]) for td in trace) < 1e-6
    assert eng.body is not None and Engine(seed=1, config=EngineConfig.research()).body is None


@pytest.mark.exact_hash  # same-platform bit identity (pytest.ini)
def test_the_body_option_leaves_both_baselines_bit_identical() -> None:
    for profile, cfg in (("legacy", EngineConfig.legacy()), ("research", EngineConfig.research())):
        assert hash_trace(Engine(seed=DEFAULT_SEED, config=cfg).run(DEFAULT_TICKS)) == load_baseline(profile)


def test_the_corridor_options_default_off_and_the_commitment_needs_a_wall_ahead() -> None:
    """M3 step 1b (G45): wall_avoid_range 1.0 and turn_commitment 0 are every result to date; the commitment adds to
    the previous tick's turn only while a wall is ahead."""
    from brain.systems.basal_ganglia import _channel_scores
    from brain.contracts import Observation, VisionRay
    from core.config import BasalGangliaConfig

    bg = BasalGangliaConfig()
    assert bg.wall_avoid_range == 1.0 and bg.turn_commitment == 0.0 and EngineConfig.research().basal_ganglia.turn_commitment == 0.0
    wall_ahead = Observation(vision_rays=(VisionRay(dist=0.05, obj_type="wall", angle=0.0),), whisker_hits=(False, False), pain_signal=0.0,
                             forward_delta=0.0, turn_delta=0.0)
    clear = Observation(vision_rays=(VisionRay(dist=0.9, obj_type="wall", angle=0.0),), whisker_hits=(False, False), pain_signal=0.0,
                        forward_delta=0.0, turn_delta=0.0)
    on = BasalGangliaConfig(wall_avoid_range=1.0 / 6.0, turn_commitment=0.3)
    base = _channel_scores(wall_ahead, 0.0, 1.0, False, on, {}, previous_action="FORWARD")
    committed = _channel_scores(wall_ahead, 0.0, 1.0, False, on, {}, previous_action="TURN_LEFT")
    assert committed["TURN_LEFT"] == pytest.approx(base["TURN_LEFT"] + 0.3) and committed["TURN_RIGHT"] == base["TURN_RIGHT"]
    # 0.9 of the vision range away is beyond the 1/6 range: no wall ahead, no commitment, no wall term.
    far = _channel_scores(clear, 0.0, 1.0, False, on, {}, previous_action="TURN_LEFT")
    assert far["TURN_LEFT"] == 0.0 and far["FORWARD"] == on.forward_bias
    # Off (the defaults): the same wall 0.9 of the range away still counts, as it always has.
    assert _channel_scores(clear, 0.0, 1.0, False, bg, {}, previous_action="TURN_LEFT")["TURN_LEFT"] > 0.0


def test_a_one_tick_turn_of_pi_is_a_valid_observation() -> None:
    """G45: the egomotion clamp gives exactly +-pi for a one-tick turn of pi or more; the contract accepts it, as it
    accepts a heading of pi (it rejected 3.141592653589793 against a bound of 3.14159 until then)."""
    import math

    from brain.contracts import Observation, VisionRay

    for turn in (math.pi, -math.pi):
        Observation(vision_rays=(VisionRay(dist=0.5, obj_type="wall", angle=math.pi),), whisker_hits=(False, False),
                    pain_signal=0.0, forward_delta=0.0, turn_delta=turn).validate()
    with pytest.raises(ValueError):
        Observation(vision_rays=(), whisker_hits=(False, False), pain_signal=0.0, forward_delta=0.0, turn_delta=3.2).validate()
