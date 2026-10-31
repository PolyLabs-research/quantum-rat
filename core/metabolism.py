"""The body's energy balance (the whole, docs/prereg/whole_resource.md §2.1; decisions G56).

Physics, not brain: the engine charges it every tick and the brain senses it only through interoception
(``brain.systems.interoception``). It replaces, in the whole's task, the audit's astrocyte, whose only effects were to
throttle movement and close the sensory gate; this one never throttles anything. Pure Python.

Each tick: the gut empties into the reserve (exponentially, time constant ``absorption_time``), then the tick's cost is
paid: ``basal_cost`` x (``sleep_factor`` asleep, else 1 + ``locomotion_factor`` x the speed fraction in [0, 1]). The
reserve is capped at 1 (what an absorption would carry past it is lost) and starves at 0.
"""

from __future__ import annotations

import math


class Metabolism:
    def __init__(self, start: float = 0.6, basal_cost: float = 1.0 / 9000.0, locomotion_factor: float = 2.0,
                 sleep_factor: float = 0.8, absorption_time: float = 300.0) -> None:
        if not (0.0 <= start <= 1.0) or absorption_time <= 0.0:
            raise ValueError("metabolism needs a start in [0, 1] and a positive absorption time")
        self.reserve = float(start)
        self.gut = 0.0
        self.basal_cost = float(basal_cost)
        self.locomotion_factor = float(locomotion_factor)
        self.sleep_factor = float(sleep_factor)
        self._absorb = 1.0 - math.exp(-1.0 / absorption_time)
        self.starved = self.reserve <= 0.0
        # Accounts, for the task's measures: energy eaten, spent (all, and on locomotion alone), lost to the cap.
        self.eaten = 0.0
        self.spent = 0.0
        self.spent_locomotion = 0.0
        self.lost = 0.0

    @property
    def effective(self) -> float:
        """Reserve plus what is in the gut: the state a meal's value is judged against."""
        return self.reserve + self.gut

    def tick(self, speed_fraction: float, asleep: bool = False) -> float:
        """Absorb, pay this tick's cost; returns the cost. Does nothing once starved."""
        if self.starved:
            return 0.0
        absorbed = self.gut * self._absorb
        self.gut -= absorbed
        self.reserve += absorbed
        if self.reserve > 1.0:
            self.lost += self.reserve - 1.0
            self.reserve = 1.0
        speed = min(1.0, max(0.0, speed_fraction))
        locomotion = 0.0 if asleep else self.basal_cost * self.locomotion_factor * speed
        cost = self.basal_cost * (self.sleep_factor if asleep else 1.0) + locomotion
        self.reserve -= cost
        self.spent += cost
        self.spent_locomotion += locomotion
        if self.reserve <= 0.0:
            self.reserve = 0.0
            self.starved = True
        return cost

    def eat(self, energy: float) -> None:
        if energy < 0.0:
            raise ValueError("a meal's energy must be non-negative")
        self.gut += energy
        self.eaten += energy


__all__ = ["Metabolism"]
