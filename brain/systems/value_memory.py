"""A plastic place-value map consolidated by replay, with spatial generalization.

Each place cell ``(bx, by)`` (the spatial system's integer bin coordinates)
carries a scalar value. Online, value moves toward the reward received there.
During microsleep the recent trajectory is replayed as temporal-difference
updates, propagating value *backward* from rewarding places to the places that
precede them -- replay consolidation.

Values generalize to neighbouring cells with a decaying kernel (overlapping
place fields), so a single trajectory fills a smooth 2-D field the agent can
follow instead of a thin one-cell-wide path. ``generalization_radius = 0``
disables this and recovers an exact one-cell map.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Iterable, Tuple

Cell = Tuple[int, int]


class ValueMemory:
    def __init__(
        self,
        learning_rate: float = 0.2,
        discount: float = 0.9,
        capacity: int = 200,
        generalization_radius: int = 0,
        generalization_falloff: float = 0.5,
    ) -> None:
        self.lr = learning_rate
        self.gamma = discount
        self.gen_radius = generalization_radius
        self.gen_falloff = generalization_falloff
        self.values: Dict[Cell, float] = {}
        self.trajectory: Deque[Tuple[Cell, float]] = deque(maxlen=capacity)

    def _kernel(self, cell: Cell) -> Iterable[Tuple[Cell, float]]:
        """Yield (cell, weight) over a neighbourhood; just the centre if radius 0."""
        bx, by = cell
        r = self.gen_radius
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                weight = self.gen_falloff ** (abs(dx) + abs(dy))
                yield (bx + dx, by + dy), weight

    def _update(self, cell: Cell, target: float) -> None:
        for nb, weight in self._kernel(cell):
            v = self.values.get(nb, 0.0)
            self.values[nb] = v + weight * self.lr * (target - v)

    def record(self, cell: Cell, reward: float) -> None:
        """Online update toward immediate reward, and log the step for replay."""
        self.trajectory.append((cell, reward))
        self._update(cell, reward)

    def replay_transition(self, index: int) -> None:
        """Offline TD(0) backup for one stored transition (used during replay)."""
        if index < 0 or index + 1 >= len(self.trajectory):
            return
        cell, reward = self.trajectory[index]
        next_cell, _ = self.trajectory[index + 1]
        v_next = self.values.get(next_cell, 0.0)
        self._update(cell, reward + self.gamma * v_next)

    def consolidate(self, passes: int = 1) -> None:
        """Replay the whole trajectory backward ``passes`` times (offline sweep)."""
        for _ in range(passes):
            for index in range(len(self.trajectory) - 2, -1, -1):
                self.replay_transition(index)

    def value_of(self, cell: Cell) -> float:
        return self.values.get(cell, 0.0)


__all__ = ["ValueMemory"]
