"""Four scalar neuromodulator traces, deterministic functions of reward, pain and the working-memory novelty bit.

- DA = 0.5 + 0.5 * clamp(reward - running mean of reward): reward minus an EMA,
  not a prediction error over states. In reward-free protocols it sits at
  exactly 0.5.
- NE = 0.5 * pain + 0.5 * novelty, where novelty is the checksum-changed bit
  (1 on every tick at sensor noise 0.03).
- ACh = that bit.
- 5HT = 0.5 + 0.5 * clamp(running mean): a lagged copy of DA's input.

Each enters action selection through one gain in BasalGangliaConfig
(dopamine_explore_gain, ach_precision_gain, ne_threat_gain,
fiveht_patience_gain); the research profile sets all four to 0 and keeps the
traces logged. Measured traces: tools/probes/neuromod_traces and
novelty_pinning.
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
