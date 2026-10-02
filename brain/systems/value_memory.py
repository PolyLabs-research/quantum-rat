"""A plastic place-value map learned by temporal-difference updates and replay.

Each place cell ``(bx, by)`` (the spatial system's integer bin coordinates)
carries a value: the expected (discounted) future reward from that place. Values
are learned by TD(0): on each transition ``s -> s'`` with reward ``r`` received
on arriving at ``s'``,

    V(s) <- V(s) + alpha * (r + gamma * V(s') - V(s))

so a place that leads toward reward keeps a high value even on zero-reward
steps (it bootstraps on its successor). This is what makes the map survive
repeated memory recall: following the learned gradient *reinforces* it rather
than decaying it toward the immediate (zero) reward -- the bug that an
"update toward immediate reward" rule had.

The same TD update is applied online (as the agent moves) and offline during
microsleep replay (``replay_transition`` / ``consolidate``), which propagates
value backward along the stored trajectory. Values generalize to neighbouring
cells with a decaying kernel (overlapping place fields;
``generalization_radius`` 0 disables it), so a single trajectory fills a
followable 2-D field instead of a thin one-cell path.

Small positive peaks that the agent builds by standing still are extinguished
by ``dwell_extinction`` (see ``record``): without it nothing but slow decay
removes them, and a tiny peak under the agent reads, once the steering signal is
normalized, as "every direction is worse than here".
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Iterable, Optional, Tuple

Cell = Tuple[int, int]


class ValueMemory:
    def __init__(
        self,
        learning_rate: float = 0.2,
        discount: float = 0.9,
        capacity: int = 200,
        generalization_radius: int = 0,
        generalization_falloff: float = 0.5,
        dwell_extinction: float = 0.0,
    ) -> None:
        self.lr = learning_rate
        self.dwell_extinction = dwell_extinction
        self.gamma = discount
        self.gen_radius = generalization_radius
        self.gen_falloff = generalization_falloff
        self.values: Dict[Cell, float] = {}
        self.trajectory: Deque[Tuple[Cell, float]] = deque(maxlen=capacity)
        self._prev_cell: Optional[Cell] = None  # last place, for the online TD transition

    def _kernel(self, cell: Cell) -> Iterable[Tuple[Cell, float]]:
        """Yield (cell, weight) over a neighbourhood; just the centre if radius 0."""
        bx, by = cell
        r = self.gen_radius
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                weight = self.gen_falloff ** (abs(dx) + abs(dy))
                yield (bx + dx, by + dy), weight

    def _td_update(self, cell: Cell, target: float) -> None:
        """Move V(cell) (and its neighbourhood) toward a TD target."""
        for nb, weight in self._kernel(cell):
            v = self.values.get(nb, 0.0)
            self.values[nb] = v + weight * self.lr * (target - v)

    def record(self, cell: Cell, reward: float) -> None:
        """Observe arrival at ``cell`` with ``reward``; log it and do the online TD backup.

        The reward is credited to the transition that led here (reward-on-arrival),
        so V(previous) bootstraps on V(cell). The first step of an episode has no
        predecessor and only logs.

        Dwell extinction: a same-cell (dwelling) transition on a positively valued
        place is charged ``dwell_extinction`` before the backup, so a peak the
        agent builds by standing still fades instead of holding it there. The
        charged reward is what gets logged, so replay applies the same thing.
        """
        if (
            self.dwell_extinction
            and self._prev_cell == cell
            and self.values.get(cell, 0.0) > 0.0
        ):
            reward -= self.dwell_extinction
        if self._prev_cell is not None:
            self._td_update(self._prev_cell, reward + self.gamma * self.values.get(cell, 0.0))
        self.trajectory.append((cell, reward))
        self._prev_cell = cell

    def reset_episode(self) -> None:
        """Mark an episode boundary so no transition links across a reset/teleport."""
        self._prev_cell = None

    def replay_transition(self, index: int) -> None:
        """Offline TD(0) backup for one stored transition (used during replay)."""
        if index < 0 or index + 1 >= len(self.trajectory):
            return
        from_cell, _ = self.trajectory[index]
        to_cell, reward_on_arrival = self.trajectory[index + 1]
        self._td_update(from_cell, reward_on_arrival + self.gamma * self.values.get(to_cell, 0.0))

    def consolidate(self, passes: int = 1) -> None:
        """Replay the whole trajectory backward ``passes`` times (offline sweep)."""
        for _ in range(passes):
            for index in range(len(self.trajectory) - 2, -1, -1):
                self.replay_transition(index)

    def value_of(self, cell: Cell) -> float:
        return self.values.get(cell, 0.0)


__all__ = ["ValueMemory"]
