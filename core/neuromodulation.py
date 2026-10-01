"""Neuromodulator updates driven by real state signals.

Previously these were a bounded random walk read by nothing. Now they are
deterministic functions of the agent's situation:

- **Dopamine (DA)** encodes a reward-prediction error: it rises above its 0.5
  baseline on better-than-expected reward and falls below on worse. The engine
  feeds DA into action selection (low DA boosts exploration), so dopamine
  closes a causal loop onto behaviour.
- **Norepinephrine (NE)** tracks arousal from pain and novelty.
- **Acetylcholine (ACh)** tracks sensory novelty (a proxy for uncertainty).
- **Serotonin (5HT)** tracks a slow mood baseline (expected reward).

NE/ACh/5HT are honest state readouts but do not yet drive behaviour; only DA
does. See RECOMMENDATIONS.md for the remaining work to make them control signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class NeuromodulatorSystem:
    levels: Dict[str, float] = field(
        default_factory=lambda: {"DA": 0.5, "5HT": 0.5, "NE": 0.0, "ACh": 0.0}
    )
    reward_lr: float = 0.1
    rpe_scale: float = 1.0
    expected_reward: float = 0.0

    def update(self, *, reward: float = 0.0, novelty: float = 0.0, pain: float = 0.0) -> Dict[str, float]:
        """Deterministically update modulators from reward, novelty and pain."""
        # Dopamine as reward-prediction error around an EMA baseline.
        self.expected_reward += self.reward_lr * (reward - self.expected_reward)
        rpe = reward - self.expected_reward
        self.levels["DA"] = _clamp(0.5 + 0.5 * _clamp(rpe / self.rpe_scale, -1.0, 1.0))
        # Norepinephrine: arousal from pain and novelty.
        self.levels["NE"] = _clamp(0.5 * pain + 0.5 * novelty)
        # Acetylcholine: precision / uncertainty proxy from novelty.
        self.levels["ACh"] = _clamp(novelty)
        # Serotonin: slow mood baseline from expected reward.
        self.levels["5HT"] = _clamp(0.5 + 0.5 * _clamp(self.expected_reward / self.rpe_scale, -1.0, 1.0))
        return dict(self.levels)


__all__ = ["NeuromodulatorSystem"]
