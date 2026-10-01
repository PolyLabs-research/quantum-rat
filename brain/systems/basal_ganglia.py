"""Deterministic Basal Ganglia-style action selector.

Scores four action channels from the Observation and selects the best with a
fixed tie-break. Weights come from a ``BasalGangliaConfig`` so AgentDNA and
protocols can tune behaviour. The selector now uses vision: it drives toward a
visible "target" and turns away from a close wall ahead.
"""

from __future__ import annotations

from typing import Dict, Optional

from brain.contracts import Action, Observation
from core.config import BasalGangliaConfig

TURN_STEP = 0.3  # radians per tick equivalent


def _vision_signals(observation: Observation):
    """Extract target/wall closeness ahead, left and right from vision rays."""
    center_target = center_wall = 0.0
    left_target = right_target = 0.0
    left_open = right_open = 0.0
    rays = observation.vision_rays
    if rays:
        fwd = min(rays, key=lambda r: abs(r.angle))
        if fwd.obj_type == "target":
            center_target = 1.0 - fwd.dist
        elif fwd.obj_type == "wall":
            center_wall = 1.0 - fwd.dist
    for ray in rays:
        closeness = 1.0 - ray.dist
        if ray.angle > 1e-6:
            left_open = max(left_open, ray.dist)
            if ray.obj_type == "target":
                left_target = max(left_target, closeness)
        elif ray.angle < -1e-6:
            right_open = max(right_open, ray.dist)
            if ray.obj_type == "target":
                right_target = max(right_target, closeness)
    return center_target, center_wall, left_target, right_target, left_open, right_open


def _channel_scores(
    observation: Observation,
    wm_novelty: float,
    trn_gain: float,
    microsleep_active: bool,
    config: BasalGangliaConfig,
) -> Dict[str, float]:
    if microsleep_active:
        return {"REST": 1.0}

    pain = observation.pain_signal
    c_target, c_wall, l_target, r_target, l_open, r_open = _vision_signals(observation)

    scores: Dict[str, float] = {}
    scores["FORWARD"] = (
        config.forward_bias * trn_gain
        - config.pain_avoidance * pain
        + config.novelty_gain * wm_novelty
        + config.vision_gain * c_target
        - config.wall_avoid_gain * c_wall
    )
    # The 0.5 floor guarantees a turn (not a futile forward) when a wall is close
    # ahead but both sides read blocked, e.g. when pinned on a boundary.
    scores["TURN_LEFT"] = (
        0.3 * wm_novelty
        + config.vision_gain * l_target
        + max(config.turn_bias, 0.0)
        + config.wall_avoid_gain * c_wall * (0.5 + l_open)
    )
    scores["TURN_RIGHT"] = (
        0.3 * wm_novelty
        + config.vision_gain * r_target
        + max(-config.turn_bias, 0.0)
        + config.wall_avoid_gain * c_wall * (0.5 + r_open)
    )
    scores["REST"] = config.rest_pain_gain * pain + 0.1 * (1.0 - trn_gain)
    return scores


def select_action(
    observation: Observation,
    wm_novelty: float,
    trn_gain: float,
    microsleep_active: bool,
    config: Optional[BasalGangliaConfig] = None,
) -> Action:
    config = config if config is not None else BasalGangliaConfig()
    scores = _channel_scores(observation, wm_novelty, trn_gain, microsleep_active, config)
    # Deterministic tie-break order.
    order = ["FORWARD", "TURN_LEFT", "TURN_RIGHT", "REST"]
    best = max(order, key=lambda name: (scores.get(name, float("-inf")), -order.index(name)))
    if best == "FORWARD":
        return Action(name="FORWARD", thrust=1.0, turn=0.0)
    if best == "TURN_LEFT":
        return Action(name="TURN_LEFT", thrust=0.3, turn=TURN_STEP)
    if best == "TURN_RIGHT":
        return Action(name="TURN_RIGHT", thrust=0.3, turn=-TURN_STEP)
    return Action(name="REST", thrust=0.0, turn=0.0)


__all__ = ["select_action", "TURN_STEP"]
