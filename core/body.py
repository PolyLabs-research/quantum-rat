"""A rodent-like body (M3 step 1, ``docs/prereg/m3_body.md``; decisions G44).

``RodentBody`` replaces ``World.step``'s fixed steps for one agent when ``body.model`` is ``"rodent"``. Its state is a
speed ``s`` (m/s) and an angular velocity ``w`` (rad/s). Each tick:

1. the chosen action sets targets: FORWARD (``run_speed``, 0), TURN_LEFT (``turn_speed``, +``turn_rate``),
   TURN_RIGHT (``turn_speed``, -``turn_rate``), REST (0, 0), each multiplied by the energy scale;
2. ``w`` and then ``s`` take one exactly discretised Ornstein-Uhlenbeck step toward their targets,
   ``x <- x* + (x - x*) a + sigma sqrt(1 - a^2) xi`` with ``a = exp(-dt / tau)``; ``s`` is clipped at 0; a draw is made
   from the ``body_motion`` stream only when that process's sigma is above 0;
3. the heading turns by ``w dt``;
4. wall following: for each arena wall (x walls, then y walls) closer than ``wall_align_distance`` that the heading
   points into, the heading turns toward the nearer wall-parallel direction by the fraction
   ``(1 - d / wall_align_distance) * min(1, s / run_speed)``;
5. the body moves ``s dt`` metres along the heading (converted to units) and is clamped to the bounds as before.

After RatInABox (George et al. 2024): its agent's speed and rotational velocity are Ornstein-Uhlenbeck processes
fitted to Sargolini et al. (2006), a control signal drifts the velocity, and near a wall the velocity turns to run
along it. The differences, stated: here the drift is the chosen action's target (one of four), the agent can turn in
place (RatInABox's heading is its velocity's direction, so it cannot), and the wall rule turns the heading only (no
repulsive push), so a body running along a wall still touches it and the wall-contact reset (M2b) still fires.

Pure Python (``math`` only); the brain never reads this state.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from core.config import BodyConfig, UnitsConfig

TWO_PI = 2.0 * math.pi


def _wrap(a: float) -> float:
    return (a + math.pi) % TWO_PI - math.pi


class RodentBody:
    """The rodent-like body for one agent; ``step`` moves it, ``reset`` stills it (the animal is put down)."""

    def __init__(self, config: BodyConfig, units: UnitsConfig, stream: Optional[object] = None) -> None:
        self.config = config
        self.units = units
        self.stream = stream
        self.speed = 0.0  # m/s
        self.angular_velocity = 0.0  # rad/s

    def reset(self) -> None:
        self.speed = 0.0
        self.angular_velocity = 0.0

    def targets(self, action_name: str, energy_scale: float = 1.0) -> Tuple[float, float]:
        """(target speed m/s, target angular velocity rad/s) for an action name."""
        c = self.config
        if action_name == "FORWARD":
            s, w = c.run_speed, 0.0
        elif action_name == "TURN_LEFT":
            s, w = c.turn_speed, c.turn_rate
        elif action_name == "TURN_RIGHT":
            s, w = c.turn_speed, -c.turn_rate
        else:  # REST, or anything the selection did not name
            s, w = 0.0, 0.0
        return s * energy_scale, w * energy_scale

    def _ou(self, x: float, target: float, tau: float, sigma: float, dt: float) -> float:
        a = math.exp(-dt / tau)
        x = target + (x - target) * a
        if sigma > 0.0:
            if self.stream is None:
                raise ValueError("a rodent body with noise needs the body_motion stream")
            x += sigma * math.sqrt(1.0 - a * a) * self.stream.gauss(0.0, 1.0)
        return x

    def align_to_walls(self, x: float, y: float, heading: float, bounds: Tuple[float, float]) -> float:
        """The heading after wall following, given the position (units) and the arena's half-extents (units)."""
        c = self.config
        zone = c.wall_align_distance / self.units.metres_per_unit  # units
        weight = min(1.0, self.speed / c.run_speed)
        if weight <= 0.0:
            return heading
        bx, by = bounds
        # (distance to the wall in units, the wall's inward normal angle, the two wall-parallel directions)
        walls = (
            (bx - x, math.pi, (0.5 * math.pi, -0.5 * math.pi)),  # east wall: heading into it has cos > 0
            (x + bx, 0.0, (0.5 * math.pi, -0.5 * math.pi)),  # west wall
            (by - y, -0.5 * math.pi, (0.0, math.pi)),  # north wall
            (y + by, 0.5 * math.pi, (0.0, math.pi)),  # south wall
        )
        for d, inward, parallels in walls:
            if d >= zone:
                continue
            # The heading points into the wall when it is against the wall's inward normal.
            if math.cos(heading - inward) >= 0.0:
                continue
            target = min(parallels, key=lambda p: abs(_wrap(p - heading)))
            fraction = (1.0 - max(0.0, d) / zone) * weight
            heading = heading + fraction * _wrap(target - heading)
        return heading

    def step(self, agent: object, action_name: str, bounds: Tuple[float, float], energy_scale: float = 1.0) -> None:
        """Move ``agent`` one tick (``agent.remember_state`` first, as ``Agent.apply_motion`` does)."""
        c = self.config
        dt = self.units.dt_s
        s_target, w_target = self.targets(action_name, energy_scale)
        self.angular_velocity = self._ou(self.angular_velocity, w_target, c.rotational_coherence_time, c.rotational_noise, dt)
        self.speed = max(0.0, self._ou(self.speed, s_target, c.speed_coherence_time, c.speed_noise, dt))
        agent.remember_state()
        x, y = agent.pos
        heading = agent.heading + self.angular_velocity * dt
        heading = self.align_to_walls(x, y, heading, bounds)
        step = self.speed * dt / self.units.metres_per_unit
        nx = min(max(x + step * math.cos(heading), -bounds[0]), bounds[0])
        ny = min(max(y + step * math.sin(heading), -bounds[1]), bounds[1])
        agent.heading = heading
        agent.pos = (nx, ny)

    def parameters(self) -> dict:
        c = self.config
        return {"model": "rodent", "run_speed": c.run_speed, "turn_speed": c.turn_speed, "turn_rate": c.turn_rate,
                "speed_coherence_time": c.speed_coherence_time, "speed_noise": c.speed_noise,
                "rotational_coherence_time": c.rotational_coherence_time, "rotational_noise": c.rotational_noise,
                "wall_align_distance": c.wall_align_distance}


# The step's three conditions (docs/prereg/m3_body.md): today's body, the rodent body without noise, and with
# RatInABox's noise (rotational 120 deg/s, speed 0.08 m/s).
BODY_PRESETS = {
    "discrete": {"body.model": "discrete"},
    "rodent_quiet": {"body.model": "rodent", "body.rotational_noise": 0.0, "body.speed_noise": 0.0},
    "rodent": {"body.model": "rodent", "body.rotational_noise": 120.0 * math.pi / 180.0, "body.speed_noise": 0.08},
}


def apply_body_preset(config: object, name: str) -> object:
    """Set ``config``'s body fields to the named preset (``BODY_PRESETS``); returns the config."""
    if name not in BODY_PRESETS:
        raise ValueError(f"unknown body preset {name!r}; one of {tuple(BODY_PRESETS)}")
    for key, value in BODY_PRESETS[name].items():
        config.set_field(key, value)
    return config


__all__ = ["BODY_PRESETS", "RodentBody", "apply_body_preset"]
