"""Motivation: loops that give the agent a reason to move, or not (M3; G52).

The agent's urge to go forward was a constant (FORWARD's bias, 0.8, every tick): never hungry, never full, never bored.
So a body that could run a corridor ran laps with no food at all, and one that could not, crawled even with food (G51);
no reflex could satisfy "laps must come from reward and memory". A rat moves because it is hungry, curious or afraid;
curiosity habituates in a familiar place, hunger falls as it eats, and how vigorously it works tracks the rate of
reward (Niv, Daw, Joel & Dayan 2007). This module is a set of such loops, built so more can be added.

**A loop** follows one named input signal through its own delay and time constants:

- ``follow``: y moves toward the (delayed) input x by 1 - exp(-1/tau) a tick, with tau = ``tau_rise`` when x > y and
  ``tau_fall`` otherwise (a level that rises fast and falls slowly, or the reverse);
- ``accumulate``: y = y * exp(-1/leak) + gain * x (delayed): it sums events and forgets them slowly.

``delay`` ticks pass between the input and the loop (a gut's lag before a meal registers, say).

**The built-in loops** (``default_loops``; the inputs come from the engine and the history module):

- ``curiosity`` follows ``novelty`` (1 - the familiarity of the place the agent is in, from history's visit channel);
- ``satiety`` accumulates ``meal`` (the agent ate) after a delay, forgetting it over hours;
- ``reward_trace`` follows ``reward`` (the agent was rewarded): up at once, down over minutes.

**The drive** to move is a soft OR of the reasons to, each in [0, 1] (``REASONS``): ``explore`` = curiosity and
``forage`` = hunger, with hunger = max(0, hunger_initial - satiety); drive = 1 - prod(1 - reason). G52 had forage =
hunger * reward_trace, which left a hungry agent that had found nothing lately with no reason to move but curiosity
(it rested 74% of a track run with food present); a food-restricted rat runs for food it has not found (G53, the
owner's decision). **Vigour** is where the reward trace acts: vigour_floor + (1 - vigour_floor) * reward_trace, the
rate of reward setting how hard the agent works, not whether (Niv et al. 2007). Action selection scales FORWARD's
bias by drive * vigour and gives REST its ``idle`` term in proportion to what is missing from the drive
(``basal_ganglia.unmotivated_rest``). A new motive is a loop (or several, with their own delays) and a reason that
reads them, registered by name; nothing else changes.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Mapping, Sequence

LOOP_KINDS = ("follow", "accumulate")


@dataclass(frozen=True)
class LoopSpec:
    name: str
    signal: str
    kind: str = "follow"
    tau_rise: float = 1.0
    tau_fall: float = 1.0
    gain: float = 1.0
    leak: float = math.inf
    delay: int = 0
    initial: float = 0.0


class Loop:
    def __init__(self, spec: LoopSpec) -> None:
        if spec.kind not in LOOP_KINDS:
            raise ValueError(f"loop kind must be one of {LOOP_KINDS}, got {spec.kind!r}")
        if spec.tau_rise <= 0.0 or spec.tau_fall <= 0.0 or spec.leak <= 0.0 or spec.delay < 0:
            raise ValueError(f"loop {spec.name}: time constants must be positive and the delay non-negative")
        self.spec = spec
        self.value = float(spec.initial)
        self._line: Deque[float] = deque([0.0] * spec.delay, maxlen=spec.delay) if spec.delay else deque()
        self._up = 1.0 - math.exp(-1.0 / spec.tau_rise)
        self._down = 1.0 - math.exp(-1.0 / spec.tau_fall)
        self._keep = math.exp(-1.0 / spec.leak) if math.isfinite(spec.leak) else 1.0

    def step(self, x: float) -> float:
        if self.spec.delay:
            delayed = self._line[0]
            self._line.append(float(x))
            x = delayed
        if self.spec.kind == "follow":
            rate = self._up if x > self.value else self._down
            self.value += (x - self.value) * rate
        else:
            self.value = self.value * self._keep + self.spec.gain * x
        return self.value


class Motivation:
    """The loops, stepped once a tick on the engine's signals, and the drive they compose."""

    def __init__(self, specs: Sequence[LoopSpec], hunger_initial: float = 1.0,
                 reasons: Sequence[str] = ("explore", "forage"), vigour_floor: float = 0.5) -> None:
        names = [s.name for s in specs]
        if len(set(names)) != len(names):
            raise ValueError("loop names must be unique")
        unknown = [r for r in reasons if r not in REASONS]
        if unknown:
            raise ValueError(f"unknown reason(s) {unknown}; registered: {tuple(REASONS)}")
        if not 0.0 <= vigour_floor <= 1.0:
            raise ValueError(f"vigour_floor must be in [0, 1], got {vigour_floor}")
        self.loops: Dict[str, Loop] = {s.name: Loop(s) for s in specs}
        self.hunger_initial = float(hunger_initial)
        self.vigour_floor = float(vigour_floor)
        # The sensed energy deficit, when interoception provides it (the whole, G56): hunger() returns it instead of
        # G53's meal-count estimate. None: the estimate.
        self.sensed_hunger: float | None = None
        self.reasons = tuple(reasons)
        self.reason_levels: Dict[str, float] = {}
        self.levels: Dict[str, float] = {name: loop.value for name, loop in self.loops.items()}
        self.drive = self._compose()

    def step(self, signals: Mapping[str, float]) -> float:
        for name, loop in self.loops.items():
            self.levels[name] = loop.step(float(signals.get(loop.spec.signal, 0.0)))
        self.drive = self._compose()
        return self.drive

    def hunger(self) -> float:
        if self.sensed_hunger is not None:
            return min(1.0, max(0.0, self.sensed_hunger))
        return max(0.0, self.hunger_initial - self.levels.get("satiety", 0.0))

    def vigour(self) -> float:
        """How hard the agent works for what it is after: the floor, plus the rest as the reward trace rises (G53)."""
        trace = min(1.0, max(0.0, self.levels.get("reward_trace", 0.0)))
        return self.vigour_floor + (1.0 - self.vigour_floor) * trace

    def _compose(self) -> float:
        missing = 1.0
        for name in self.reasons:
            level = min(1.0, max(0.0, REASONS[name](self)))
            self.reason_levels[name] = level
            missing *= 1.0 - level
        return 1.0 - missing


# reason name -> its level from the motivation's loops (each in [0, 1] after clipping)
REASONS: Dict[str, Callable[["Motivation"], float]] = {
    "explore": lambda m: m.levels.get("curiosity", 0.0),
    "forage": lambda m: m.hunger(),  # G53: hunger is a reason on its own; the reward trace sets vigour instead
}


def default_loops(cfg: object) -> List[LoopSpec]:
    """The built-in loops from a ``MotivationConfig``."""
    return [
        LoopSpec("curiosity", "novelty", "follow", tau_rise=cfg.curiosity_rise, tau_fall=cfg.curiosity_fall),
        LoopSpec("satiety", "meal", "accumulate", gain=cfg.satiety_per_meal, leak=cfg.satiety_digestion,
                 delay=int(cfg.satiety_delay)),
        LoopSpec("reward_trace", "reward", "follow", tau_rise=cfg.reward_trace_rise, tau_fall=cfg.reward_trace_fall),
    ]


__all__ = ["LOOP_KINDS", "Loop", "LoopSpec", "Motivation", "REASONS", "default_loops"]
