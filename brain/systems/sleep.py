"""Homeostatic sleep (the whole, docs/prereg/whole_resource.md §2.2; decisions G56).

Replaces, in the whole, the audit's microsleep (an ATP alarm with fixed 25-tick bouts). Sleep pressure S is Borbély's
process S (1982): awake it rises toward 1, S += (1 - S)(1 - exp(-1 / wake_time_constant)); asleep it falls,
S x exp(-1 / sleep_time_constant). Sleep begins when S reaches ``onset`` while hunger is below
``hunger_blocks_onset`` (a hungry animal stays awake: orexin, Yamanaka et al. 2003) and nothing hurts; it ends when S
falls to ``offset``, hunger reaches ``hunger_wakes``, or something hurts. What sleep does (the closed thalamic gate,
the lower metabolic rate, acetylcholine at 0, replay) is the engine's. Pure Python.
"""

from __future__ import annotations

import math


class SleepHomeostat:
    def __init__(self, wake_time_constant: float = 3000.0, sleep_time_constant: float = 600.0, onset: float = 0.6,
                 offset: float = 0.2, hunger_blocks_onset: float = 0.25, hunger_wakes: float = 0.5) -> None:
        if wake_time_constant <= 0.0 or sleep_time_constant <= 0.0 or not (0.0 <= offset < onset <= 1.0):
            raise ValueError("sleep needs positive time constants and 0 <= offset < onset <= 1")
        self.pressure = 0.0
        self.asleep = False
        self.bouts = 0
        self.ticks_asleep = 0
        self._rise = 1.0 - math.exp(-1.0 / wake_time_constant)
        self._keep = math.exp(-1.0 / sleep_time_constant)
        self.onset, self.offset = float(onset), float(offset)
        self.hunger_blocks_onset, self.hunger_wakes = float(hunger_blocks_onset), float(hunger_wakes)

    def step(self, hunger: float, pain: float) -> bool:
        """One tick: the pressure moves, then the state; returns whether the agent sleeps this tick."""
        if self.asleep:
            self.pressure *= self._keep
            if self.pressure <= self.offset or hunger >= self.hunger_wakes or pain > 0.0:
                self.asleep = False
        else:
            self.pressure += (1.0 - self.pressure) * self._rise
            if self.pressure >= self.onset and hunger < self.hunger_blocks_onset and pain <= 0.0:
                self.asleep = True
                self.bouts += 1
        self.ticks_asleep += self.asleep
        return self.asleep


__all__ = ["SleepHomeostat"]
