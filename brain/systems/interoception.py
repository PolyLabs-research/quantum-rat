"""Interoception: the agent's sense of its own energy (the whole, docs/prereg/whole_resource.md §2.2; decisions G56).

Pure functions of the effective energy E_eff (reserve plus gut, ``core.metabolism``), the setpoint and a typical meal K.

- **Drive** D(x) = ((x - setpoint) / setpoint)^2: the distance from the setpoint, convex, so a fixed meal is worth more
  the hungrier the agent is (homeostatic reinforcement learning, Keramati & Gutkin 2014).
- **A meal's reward** is the drive it removes, normalised so the hungriest meal brings 1:
  [D(E_eff) - D(E_eff + K)] / [D(0) - D(K)]. Past the setpoint it is negative: eating when full is aversive.
- **The consummatory reflex** eats on contact only when that reward is positive (a brainstem reflex terminated by
  satiety signals; Grill & Norgren 1978).
- **Hunger** h = clamp((setpoint - E_eff) / (setpoint - floor), 0, 1): 0 at the setpoint, 1 from ``floor`` down.
- **Incentive** = the reward a meal would bring now, clipped to [0, 1]: what a cue of food is worth in the present
  state (incentive salience; Toates 1986; Zhang, Berridge, Tindell, Smith & Aldridge 2009).
- **Satiety** (serotonin's input) = clamp((E_eff - (setpoint - band)) / band, 0, 1).
"""

from __future__ import annotations


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def drive(x: float, setpoint: float) -> float:
    return ((x - setpoint) / setpoint) ** 2


def meal_reward(e_eff: float, energy: float, setpoint: float) -> float:
    """The drive a meal of ``energy`` removes from state ``e_eff``, over the drive the hungriest such meal removes."""
    best = drive(0.0, setpoint) - drive(energy, setpoint)
    if best <= 0.0:
        raise ValueError("a meal must reduce the drive of an empty agent: energy must be below twice the setpoint")
    return (drive(e_eff, setpoint) - drive(e_eff + energy, setpoint)) / best


def hunger(e_eff: float, setpoint: float, floor: float) -> float:
    return _clamp((setpoint - e_eff) / (setpoint - floor))


def incentive(e_eff: float, energy: float, setpoint: float) -> float:
    return _clamp(meal_reward(e_eff, energy, setpoint))


def satiety(e_eff: float, setpoint: float, band: float) -> float:
    return _clamp((e_eff - (setpoint - band)) / band)


__all__ = ["drive", "hunger", "incentive", "meal_reward", "satiety"]
