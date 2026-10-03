"""Egomotion is derived from the agent's own motion, not absolute position.

Replaces an earlier ``xfail`` placeholder that asserted nothing (and had
started to xpass, which is a latent CI landmine under strict xfail). These
assertions exercise the real egomotion path in ``gather_observation`` /
``_compute_egomotion``.
"""

import math

from core.entities import Agent
from core.rng import RNG
from core.sensors import gather_observation


def _observe(agent: Agent):
    rng = RNG(seed=1337)
    return gather_observation(
        agent,
        vision_stream=rng.stream("sensors_vision"),
        noise_stream=rng.stream("sensors_noise"),
    )


def test_forward_motion_gives_positive_forward_delta():
    agent = Agent(id=0, pos=(0.0, 0.0), heading=0.0)
    agent.apply_motion(forward_delta=0.5, turn_delta=0.0)
    obs = _observe(agent)
    assert obs.forward_delta > 0.0
    assert abs(obs.turn_delta) < 1e-9


def test_backward_motion_gives_negative_forward_delta():
    agent = Agent(id=0, pos=(0.0, 0.0), heading=0.0)
    agent.apply_motion(forward_delta=-0.5, turn_delta=0.0)
    obs = _observe(agent)
    assert obs.forward_delta < 0.0


def test_turning_gives_turn_delta_and_no_forward():
    agent = Agent(id=0, pos=(0.0, 0.0), heading=0.0)
    agent.apply_motion(forward_delta=0.0, turn_delta=0.3)
    obs = _observe(agent)
    assert math.isclose(obs.turn_delta, 0.3, abs_tol=1e-9)
    assert abs(obs.forward_delta) < 1e-9
