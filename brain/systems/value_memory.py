"""A plastic place-value map consolidated by replay.

This is the substrate the replay machinery was missing. Each visited place
(the spatial system's ``place_id``) carries a scalar value. Online, value moves
toward the reward received there. During microsleep, the recent trajectory is
replayed as temporal-difference updates, which propagate value *backward* from
rewarding places to the places that precede them -- i.e. replay consolidates
which locations predict reward. This is the concrete mechanism behind the
"replay improves performance" goal; wiring the consolidated map into navigation
is the remaining step (see RECOMMENDATIONS.md).
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Tuple


class ValueMemory:
    def __init__(self, learning_rate: float = 0.2, discount: float = 0.9, capacity: int = 200) -> None:
        self.lr = learning_rate
        self.gamma = discount
        self.values: Dict[int, float] = {}
        self.trajectory: Deque[Tuple[int, float]] = deque(maxlen=capacity)

    def record(self, place_id: int, reward: float) -> None:
        """Online update toward immediate reward, and log the step for replay."""
        self.trajectory.append((place_id, reward))
        v = self.values.get(place_id, 0.0)
        self.values[place_id] = v + self.lr * (reward - v)

    def replay_transition(self, index: int) -> None:
        """Offline TD(0) backup for one stored transition (used during replay).

        Replaying the buffer repeatedly propagates value backward along the
        trajectory, from rewarding places to the places that lead to them.
        """
        if index < 0 or index + 1 >= len(self.trajectory):
            return
        place, reward = self.trajectory[index]
        next_place, _ = self.trajectory[index + 1]
        v = self.values.get(place, 0.0)
        v_next = self.values.get(next_place, 0.0)
        td_target = reward + self.gamma * v_next
        self.values[place] = v + self.lr * (td_target - v)

    def consolidate(self, passes: int = 1) -> None:
        """Replay the whole trajectory backward ``passes`` times (offline sweep)."""
        for _ in range(passes):
            for index in range(len(self.trajectory) - 2, -1, -1):
                self.replay_transition(index)

    def value_of(self, place_id: int) -> float:
        return self.values.get(place_id, 0.0)


__all__ = ["ValueMemory"]
