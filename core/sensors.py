"""Sensor outputs and Observation construction.

Vision, whiskers and pain are computed from real world geometry (walls and
circular objects), not from noise. Egomotion stays derived from the agent's
own motion, optionally with seeded odometry noise (a multiplicative speed
error and an additive heading error, ``SensorConfig.odometry_*``) on the
estimate only. Sensors are allowed to read the World (that is their job); the
Brain only ever sees the resulting immutable Observation.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from typing import List, Optional, Tuple

from brain.contracts import Observation, VisionRay
from core.config import SensorConfig
from core.entities import Agent
from core.rng import RNGStream
from core.world import World


def _normalize(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _compute_egomotion(
    agent: Agent,
    config: Optional[SensorConfig] = None,
    odometry_stream: Optional[RNGStream] = None,
) -> Tuple[float, float]:
    """(forward_delta, turn_delta): the agent's own estimate of its motion this tick.

    The raw displacement is projected on the heading (sign = forward/backward)
    and the raw heading change is taken as is; both are then clamped to the
    Observation's ranges ([-1, 1] units and [-pi, pi] radians). Odometry noise
    (``SensorConfig.odometry_speed_noise`` / ``odometry_turn_noise``) perturbs
    the raw values before the clamp: the forward displacement d becomes
    d * (1 + sigma_speed * xi) and the heading change gets + N(0, sigma_turn),
    with xi a standard normal deviate. The forward draw is made first, then
    the turn draw, each only when its sigma is > 0 (so at 0 nothing is drawn
    and the trace is bit-identical to exact odometry), and each on every tick
    its sigma is on, whether or not the body moved. The body's true motion is
    never touched: this is the estimate the spatial system integrates. The
    clamp is unchanged, and a FORWARD step (1.0) sits at the top of its range,
    so on full-thrust ticks only a slowing speed error survives it.
    """
    dx = agent.pos[0] - agent.last_pos[0]
    dy = agent.pos[1] - agent.last_pos[1]
    # Project displacement onto heading to preserve forward/backward sign.
    heading = agent.heading
    distance = dx * math.cos(heading) + dy * math.sin(heading)
    turn_delta = agent.heading - agent.last_heading
    if config is not None and odometry_stream is not None:
        if config.odometry_speed_noise > 0.0:
            distance *= 1.0 + config.odometry_speed_noise * odometry_stream.gauss(0.0, 1.0)
        if config.odometry_turn_noise > 0.0:
            turn_delta += odometry_stream.gauss(0.0, config.odometry_turn_noise)
    # Clamp egomotion to normalized ranges to satisfy validation.
    return _normalize(distance, -1.0, 1.0), _normalize(turn_delta, -math.pi, math.pi)


def _ray_wall_distance(px: float, py: float, dx: float, dy: float, bounds: Tuple[float, float]) -> float:
    """Distance to the bounding box exit for a ray starting inside the box."""
    bx, by = bounds
    best = math.inf
    if dx > 1e-12:
        best = min(best, (bx - px) / dx)
    elif dx < -1e-12:
        best = min(best, (-bx - px) / dx)
    if dy > 1e-12:
        best = min(best, (by - py) / dy)
    elif dy < -1e-12:
        best = min(best, (-by - py) / dy)
    return max(0.0, best)


def _ray_circle_distance(
    px: float, py: float, dx: float, dy: float, cx: float, cy: float, r: float
) -> Optional[float]:
    """Nearest non-negative distance along a unit ray to a circle, or None."""
    ox, oy = px - cx, py - cy
    c = ox * ox + oy * oy - r * r
    if c <= 0.0:
        return 0.0  # starting inside the circle
    b = 2.0 * (dx * ox + dy * oy)
    disc = b * b - 4.0 * c
    if disc < 0.0:
        return None
    sqrt_disc = math.sqrt(disc)
    t1 = (-b - sqrt_disc) / 2.0
    if t1 >= 0.0:
        return t1
    t2 = (-b + sqrt_disc) / 2.0
    if t2 >= 0.0:
        return t2
    return None


def _cast_ray(agent: Agent, world: World, rel_angle: float, max_range: float) -> Tuple[float, str]:
    """Cast one ray; return (normalized distance in [0,1], object kind or "")."""
    phi = agent.heading + rel_angle
    dx, dy = math.cos(phi), math.sin(phi)
    px, py = agent.pos
    nearest = _ray_wall_distance(px, py, dx, dy, world.bounds)
    kind = "wall"
    for obj in world.objects:
        t = _ray_circle_distance(px, py, dx, dy, obj.x, obj.y, obj.radius)
        if t is not None and t < nearest:
            nearest = t
            kind = obj.kind
    if nearest > max_range:
        return 1.0, ""  # nothing within sensing range
    return _normalize(nearest / max_range, 0.0, 1.0), kind


def _ray_angles(n: int, fov: float) -> List[float]:
    if n <= 1:
        return [0.0]
    step = fov / (n - 1)
    return [(-fov / 2.0) + step * i for i in range(n)]


def _pain_from_hazards(agent: Agent, world: World, pain_zone: float) -> float:
    px, py = agent.pos
    pain = 0.0
    for obj in world.objects:
        if obj.kind != "hazard":
            continue
        surface = max(0.0, math.hypot(px - obj.x, py - obj.y) - obj.radius)
        if surface < pain_zone:
            pain = max(pain, 1.0 - surface / pain_zone)
    return _normalize(pain, 0.0, 1.0)


def gather_observation(
    agent: Agent,
    world: Optional[World] = None,
    *,
    config: Optional[SensorConfig] = None,
    vision_stream: Optional[RNGStream] = None,
    noise_stream: Optional[RNGStream] = None,
    odometry_stream: Optional[RNGStream] = None,
) -> Observation:
    """Collect normalized sensor outputs for the agent from world geometry.

    ``vision_stream`` and ``noise_stream`` carry ``config.noise`` (rangefinder
    and pain); ``odometry_stream`` carries the odometry noise on egomotion (see
    ``_compute_egomotion``). A stream that is None, or a noise parameter that
    is 0, means no draw from it.
    """
    world = world if world is not None else World()
    config = config if config is not None else SensorConfig()

    rays = []
    for angle in _ray_angles(config.vision_rays, config.fov):
        dist, kind = _cast_ray(agent, world, angle, config.vision_range)
        if config.noise > 0.0 and vision_stream is not None:
            dist = _normalize(dist + vision_stream.uniform(-config.noise, config.noise), 0.0, 1.0)
        rays.append(VisionRay(dist=dist, obj_type=kind, angle=_normalize(angle, -math.pi, math.pi)))

    left = _cast_ray(agent, world, config.whisker_angle, config.vision_range)[0] * config.vision_range
    right = _cast_ray(agent, world, -config.whisker_angle, config.vision_range)[0] * config.vision_range
    whisker_hits = (left < config.whisker_range, right < config.whisker_range)

    pain_signal = _pain_from_hazards(agent, world, config.pain_zone)
    if config.noise > 0.0 and noise_stream is not None:
        pain_signal = _normalize(pain_signal + noise_stream.uniform(-config.noise, config.noise), 0.0, 1.0)

    forward_delta, turn_delta = _compute_egomotion(agent, config, odometry_stream)
    obs = Observation(
        vision_rays=tuple(rays),
        whisker_hits=whisker_hits,
        pain_signal=pain_signal,
        forward_delta=forward_delta,
        turn_delta=turn_delta,
    )
    obs.validate()
    return obs


def observation_checksum(obs: Observation) -> str:
    """Compute a stable checksum of an observation."""
    data = asdict(obs)

    def _normalize_obj(obj):
        if isinstance(obj, dict):
            return {k: _normalize_obj(obj[k]) for k in sorted(obj)}
        if isinstance(obj, list):
            return [_normalize_obj(v) for v in obj]
        return obj

    normalized = _normalize_obj(data)
    payload = repr(normalized).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = ["gather_observation", "observation_checksum"]
