"""Deterministic Basal Ganglia-style action selector.

Scores four action channels from the Observation and selects the best with a
fixed tie-break. Weights come from a ``BasalGangliaConfig`` so AgentDNA and
protocols can tune behaviour. The selector now uses vision: it drives toward a
visible "target" and turns away from a close wall ahead.
"""

from __future__ import annotations

import math
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
    freeze_habituation: float = 1.0,
    pacing_rest: float = 0.0,
) -> Dict[str, float]:
    """Score each action channel. A pure function of its arguments.

    ``freeze_habituation`` (h in [0, 1]) scales only the pain->REST drive, so a
    freeze habituates; ``pacing_rest`` is an extra REST drive while the agent is
    recovering energy. Both are computed by the engine from its own per-engine
    state (see ``Engine._brain_step``); their defaults (1.0, 0.0) are no-ops.
    """
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
    scores["REST"] = rest_pain_gain * pain * freeze_habituation + 0.1 * (1.0 - trn_gain) + rest_patience
    if pacing_rest:
        scores["REST"] += pacing_rest
    return scores


def cue_gate_weight(observation: Observation, gain: float) -> float:
    """Weight on memory steering given what is in view (cue gating).

    ``s`` is the closeness (1 - normalized distance) of the nearest visible
    target over all vision rays, 0 if none is visible; the weight is
    ``max(0, 1 - gain * s)``. With no target in view, or ``gain`` 0, it is
    exactly 1.0, so the value signals pass through unchanged.
    """
    if gain <= 0.0:
        return 1.0
    closeness = 0.0
    for ray in observation.vision_rays:
        if ray.obj_type == "target":
            closeness = max(closeness, 1.0 - ray.dist)
    return max(0.0, 1.0 - gain * closeness)


def wall_gate_signals(
    ahead: float, left: float, right: float, observation: Observation, gain: float
) -> Tuple[float, float, float, float]:
    """Wall gating of memory steering: a wall close ahead mutes memory's push to hold course.

    ``c`` is the closeness (1 - normalized distance) of a wall on the centre
    vision ray, the same signal wall avoidance uses, and ``w = max(0, 1 - gain *
    c)``. FORWARD's positive (memory pulls straight on) signal and the negative
    turn signals (memory says "turning is worse than straight on") are scaled
    by ``w``; turns toward a better side and FORWARD's negative part are kept.
    Without it a remembered place beyond a wall (or one that path-integration
    drift has moved behind it) held the agent pressing into the wall: with
    pacing off, foraging lost 13-23 items on 3 of 8 seeds that way (13-21
    collected at gain 1.5 against 34-39 at gain 0). The
    split property ``max(signals) >= 0`` is preserved. Returns the gated
    signals and ``w``; with no wall ahead, or ``gain`` 0, ``w`` is exactly 1.0
    and the signals pass through unchanged. Reads raw vision rays, independent
    of ``vision_gain``.
    """
    if gain <= 0.0:
        return ahead, left, right, 1.0
    _, c_wall, *_ = _vision_signals(observation)
    w = max(0.0, 1.0 - gain * c_wall)
    if w == 1.0:
        return ahead, left, right, 1.0
    return (
        ahead * w if ahead > 0.0 else ahead,
        left * w if left < 0.0 else left,
        right * w if right < 0.0 else right,
        w,
    )


VALUE_STEER_MODES = ("split", "maxnorm")
VALUE_AHEAD_MODES = ("zero", "maxnorm", "positive", "oppose", "oppose_positive")


def split_value_signals(
    ahead: float, left: float, right: float, scale: float, config: BasalGangliaConfig
) -> Tuple[float, float, float]:
    """Value signals for ``value_steer == "split"``. A pure function of its arguments.

    ``ahead``, ``left`` and ``right`` are the advantages (value there minus value
    here) straight ahead and of the best fan cell on each side; ``scale`` is the
    largest advantage magnitude over every sampled direction.

    The turn signals are measured relative to ahead, so they say "which way to
    turn", never "how good is everything". A side turns only when it beats ahead
    by more than ``value_turn_dead_zone`` (a fraction of the local relief
    ``scale`` when ``value_turn_relative``), ramping to full strength over
    ``value_turn_ramp``. Because nothing is measured against here, a local maximum
    never lowers FORWARD (max-norm's (-1, -1, -1) veto is gone): with the
    default ahead modes max(signals) >= 0. REST can still win *because of*
    value only when FORWARD is already below REST for other reasons (e.g. a
    narrowed sensory gate plus a wall ahead) and negative turn signals push the
    turns below it too; measured value-induced REST is 0 at gains 0.4-3.0 in
    every sweep, and 0.0067 of ticks for one maze heading at gain 0.2. Because
    the dead zone is relative, a 1% wobble at a peak does not command a full
    turn (which made the agent orbit or zig-zag off the goal). Raises
    ValueError on an unknown ``value_ahead_mode``.
    """
    eps, width = config.value_turn_dead_zone, config.value_turn_ramp
    if config.value_turn_relative:
        if scale < 1e-3:  # locally flat map -> no steer
            return 0.0, 0.0, 0.0
        norm = 1.0 / scale
    else:
        norm = 1.0

    def turn(d: float) -> float:
        excess = abs(d) * norm - eps
        if excess <= 0.0:
            return 0.0
        mag = 1.0 if width <= 0.0 else min(1.0, excess / width)
        return mag if d > 0.0 else -mag

    tl, tr = turn(left - ahead), turn(right - ahead)
    if config.value_turn_exclusive and tl > 0.0 and tr > 0.0:
        # Both sides beat ahead: commit to the better one (ties go left) instead
        # of alternating L/R, which zig-zags straight on, off the remembered goal.
        if left >= right:
            tr = 0.0
        else:
            tl = 0.0
    mode = config.value_ahead_mode
    if mode not in VALUE_AHEAD_MODES:
        raise ValueError(f"Unknown value_ahead_mode {mode!r}; expected one of {VALUE_AHEAD_MODES}")
    fwd = 0.0
    if mode in ("oppose", "oppose_positive"):
        # FORWARD gives up what the stronger turn gains, so a turn needs only
        # half the gain it would against FORWARD's fixed lead.
        fwd = -max(tl, tr, 0.0)
    if mode in ("maxnorm", "positive", "oppose_positive") and scale >= 1e-3:
        fwd += ahead / scale if mode == "maxnorm" else max(0.0, ahead / scale)
    if config.value_common_mode > 0.0:
        floor = min(ahead, left, right)
        if floor > 0.0:  # every direction beats here: a direction-free "go"
            cm = math.tanh(floor / config.value_common_mode)
            fwd, tl, tr = fwd + cm, tl + cm, tr + cm
    return fwd, tl, tr


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
    freeze_habituation: float = 1.0,
    pacing_rest: float = 0.0,
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
        freeze_habituation,
        pacing_rest,
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
    freeze_habituation: float = 1.0,
    pacing_rest: float = 0.0,
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
        freeze_habituation,
        pacing_rest,
    )
    return action


__all__ = [
    "select_action",
    "select_action_with_scores",
    "cue_gate_weight",
    "split_value_signals",
    "wall_gate_signals",
    "ACTION_ORDER",
    "TURN_STEP",
    "VALUE_STEER_MODES",
    "VALUE_AHEAD_MODES",
]
