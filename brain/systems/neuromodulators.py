"""The four neuromodulators in their roles (the whole, docs/prereg/whole_resource.md §2.2; decisions G56).

Replaces, when ``neuromod.model`` is "biological", the audit's scalar traces (``core.neuromodulation``: dopamine as
reward minus a running mean, acetylcholine as a checksum bit). Each modulator is on only when its part is; a part that
is off holds its neutral level (DA 0.5, 5HT 0.5, NE 0, ACh 0) and couples to nothing. The levels go into the
engine's ``ctx.neuromodulators``, where the arbiter's existing couplings read them (``ach_precision_gain`` on vision,
``ne_threat_gain`` on pain, ``fiveht_patience_gain`` on REST); the couplings below are the engine's.

- **Dopamine** (Schultz, Dayan & Montague 1997; Niv, Daw, Joel & Dayan 2007): DA = 0.5 + 0.5 clamp(delta / delta_ref)
  for the TD error delta the engine hands over; the **tonic** level is a reward trace (up at once to a meal's reward,
  down over ``tonic_fall`` ticks), and **vigour** = floor + (1 - floor) x tonic scales the forward bias; the replay
  budget at a meal is round(budget x min(1, |delta| / delta_ref)) (Ambrose, Pfeiffer & Foster 2016).
- **Serotonin** (Blundell 1977; Antin et al. 1975): 5HT = 0.5 + 0.5 x satiety: post-ingestive rest.
- **Noradrenaline** (Yu & Dayan 2005; Aston-Jones & Cohen 2005): a trace of |delta| / delta_ref (up at once, down
  over ``ne_fall`` ticks) plus pain; the softmax temperature x (1 + gain x NE).
- **Acetylcholine** (Hasselmo 1999, 2006; Yu & Dayan 2005): ACh = novelty weight x novelty + motion weight x moving
  while awake, 0 asleep; the SR's learning rate x (0.5 + ACh); awake replay only at or below the threshold.
"""

from __future__ import annotations

import math
from typing import Dict


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


NEUTRAL: Dict[str, float] = {"DA": 0.5, "5HT": 0.5, "NE": 0.0, "ACh": 0.0}


class BiologicalNeuromodulators:
    def __init__(self, config) -> None:  # core.config.NeuromodConfig with model "biological"
        self.c = config
        self.levels: Dict[str, float] = dict(NEUTRAL)
        self.tonic = 0.0
        self.ne_trace = 0.0
        self._tonic_keep = math.exp(-1.0 / config.tonic_fall)
        self._ne_keep = math.exp(-1.0 / config.ne_fall)

    def update(self, *, delta: float, reward: float, pain: float, novelty: float, moving: bool, asleep: bool,
               satiety: float) -> Dict[str, float]:
        c = self.c
        if c.dopamine:
            self.levels["DA"] = _clamp(0.5 + 0.5 * _clamp(delta / c.delta_ref, -1.0, 1.0))
            self.tonic *= self._tonic_keep
            if reward > 0.0:
                self.tonic = max(self.tonic, min(1.0, reward))
        if c.serotonin:
            self.levels["5HT"] = _clamp(0.5 + 0.5 * satiety)
        if c.noradrenaline:
            self.ne_trace = max(self.ne_trace * self._ne_keep, _clamp(abs(delta) / c.delta_ref))
            self.levels["NE"] = _clamp(self.ne_trace + pain)
        if c.acetylcholine:
            self.levels["ACh"] = 0.0 if asleep else _clamp(c.ach_novelty_weight * novelty + c.ach_motion_weight * float(moving))
        return dict(self.levels)

    def vigour(self) -> float:
        return self.c.vigour_floor + (1.0 - self.c.vigour_floor) * _clamp(self.tonic) if self.c.dopamine else 1.0

    def temperature_factor(self) -> float:
        return 1.0 + self.c.ne_temperature_gain * self.levels["NE"] if self.c.noradrenaline else 1.0

    def sr_learning_scale(self) -> float:
        return 0.5 + self.levels["ACh"] if self.c.acetylcholine else 1.0

    def replay_allowed(self) -> bool:
        return self.levels["ACh"] <= self.c.ach_replay_threshold if self.c.acetylcholine else True

    def replay_budget(self, delta: float, default: int) -> int:
        if not self.c.dopamine:
            return default
        return int(round(self.c.replay_budget * min(1.0, abs(delta) / self.c.delta_ref)))


__all__ = ["BiologicalNeuromodulators", "NEUTRAL"]
