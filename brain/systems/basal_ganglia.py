"""Deterministic Basal Ganglia-style action selector.

Scores four action channels from the Observation and selects the best with a
fixed tie-break. Weights come from a ``BasalGangliaConfig`` so AgentDNA and
protocols can tune behaviour. The selector now uses vision: it drives toward a
visible "target" and turns away from a close wall ahead.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

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
    modulators: Dict[str, float],
    value_ahead: float = 0.0,
    value_left: float = 0.0,
    value_right: float = 0.0,
    criticality_gain: float = 1.0,
) -> Dict[str, float]:
    if microsleep_active:
        return {"REST": 1.0}

    pain = observation.pain_signal
    c_target, c_wall, l_target, r_target, l_open, r_open = _vision_signals(observation)

    # Neuromodulatory control (all no-ops at baseline levels DA=0.5, NE=0, ACh=0, 5HT=0.5):
    da = modulators.get("DA", 0.5)
    ne = modulators.get("NE", 0.0)
    ach = modulators.get("ACh", 0.0)
    fiveht = modulators.get("5HT", 0.5)

    # Dopamine: below-baseline (worse-than-expected reward) boosts exploration.
    novelty_gain = config.novelty_gain * (1.0 + config.dopamine_explore_gain * (0.5 - da))
    # Acetylcholine sharpens sensory precision; near-critical cortical gain scales it too
    # (criticality_gain is 1.0 at criticality and <1 away from it). criticality_gain strength
    # 0 disables the coupling.
    crit_mod = (1.0 - config.criticality_gain) + config.criticality_gain * criticality_gain
    vision_gain = config.vision_gain * (1.0 + config.ach_precision_gain * ach) * crit_mod
    # Norepinephrine: arousal raises threat sensitivity (pain avoidance / freezing).
    pain_avoidance = config.pain_avoidance * (1.0 + config.ne_threat_gain * ne)
    rest_pain_gain = config.rest_pain_gain * (1.0 + config.ne_threat_gain * ne)
    # Serotonin: mood above baseline raises patience (willingness to rest / wait).
    rest_patience = config.fiveht_patience_gain * (fiveht - 0.5)

    scores: Dict[str, float] = {}
    scores["FORWARD"] = (
        config.forward_bias * trn_gain
        - pain_avoidance * pain
        + novelty_gain * wm_novelty
        + vision_gain * c_target
        + config.value_gain * value_ahead
        - config.wall_avoid_gain * c_wall
    )
    # The 0.5 floor guarantees a turn (not a futile forward) when a wall is close
    # ahead but both sides read blocked, e.g. when pinned on a boundary.
    scores["TURN_LEFT"] = (
        0.3 * wm_novelty
        + vision_gain * l_target
        + config.value_gain * value_left
        + max(config.turn_bias, 0.0)
        + config.wall_avoid_gain * c_wall * (0.5 + l_open)
    )
    scores["TURN_RIGHT"] = (
        0.3 * wm_novelty
        + vision_gain * r_target
        + config.value_gain * value_right
        + max(-config.turn_bias, 0.0)
        + config.wall_avoid_gain * c_wall * (0.5 + r_open)
    )
    scores["REST"] = rest_pain_gain * pain + 0.1 * (1.0 - trn_gain) + rest_patience
    return scores


ACTION_ORDER = ("FORWARD", "TURN_LEFT", "TURN_RIGHT", "REST")


def _action_for(name: str) -> Action:
    if name == "FORWARD":
        return Action(name="FORWARD", thrust=1.0, turn=0.0)
    if name == "TURN_LEFT":
        return Action(name="TURN_LEFT", thrust=0.3, turn=TURN_STEP)
    if name == "TURN_RIGHT":
        return Action(name="TURN_RIGHT", thrust=0.3, turn=-TURN_STEP)
    return Action(name="REST", thrust=0.0, turn=0.0)


def select_action_with_scores(
    observation: Observation,
    wm_novelty: float,
    trn_gain: float,
    microsleep_active: bool,
    config: Optional[BasalGangliaConfig] = None,
    modulators: Optional[Dict[str, float]] = None,
    value_ahead: float = 0.0,
    value_left: float = 0.0,
    value_right: float = 0.0,
    criticality_gain: float = 1.0,
) -> Tuple[Action, Dict[str, float]]:
    """Select an action and also return the channel scores that produced it.

    The scores are what a "decision" readout displays; returning them does not
    change which action is chosen.
    """
    config = config if config is not None else BasalGangliaConfig()
    modulators = modulators if modulators is not None else {}
    scores = _channel_scores(
        observation,
        wm_novelty,
        trn_gain,
        microsleep_active,
        config,
        modulators,
        value_ahead,
        value_left,
        value_right,
        criticality_gain,
    )
    # Deterministic tie-break order.
    order = list(ACTION_ORDER)
    best = max(order, key=lambda name: (scores.get(name, float("-inf")), -order.index(name)))
    return _action_for(best), scores


def select_action(
    observation: Observation,
    wm_novelty: float,
    trn_gain: float,
    microsleep_active: bool,
    config: Optional[BasalGangliaConfig] = None,
    modulators: Optional[Dict[str, float]] = None,
    value_ahead: float = 0.0,
    value_left: float = 0.0,
    value_right: float = 0.0,
    criticality_gain: float = 1.0,
) -> Action:
    action, _ = select_action_with_scores(
        observation,
        wm_novelty,
        trn_gain,
        microsleep_active,
        config,
        modulators,
        value_ahead,
        value_left,
        value_right,
        criticality_gain,
    )
    return action


__all__ = ["select_action", "select_action_with_scores", "ACTION_ORDER", "TURN_STEP"]
