"""Replay of the successor map (SR-Dyna; the whole, docs/prereg/whole_resource.md §2.2; decisions G56).

A bounded memory of the agent's transitions in its own estimate frame; the engine replays them into the successor
features M only (Russek, Momennejad, Botvinick, Gershman & Daw 2017): at a meal the current episode's most recent
transitions, newest first (reverse replay at reward, Foster & Wilson 2006), and asleep a few a tick drawn uniformly
(Wilson & McNaughton 1994). The reward weights and the action value are learned online only. Pure Python; the draws
come from the engine's ``replay`` stream.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Tuple


@dataclass(frozen=True)
class MapTransition:
    x: float
    y: float
    x_next: float
    y_next: float
    episode: int
    cell: Tuple[int, int]


class SRReplay:
    def __init__(self, capacity: int = 3000) -> None:
        if capacity < 1:
            raise ValueError("SRReplay needs capacity >= 1")
        self.memory: Deque[MapTransition] = deque(maxlen=capacity)
        self.backups = 0

    def store(self, transition: MapTransition) -> None:
        self.memory.append(transition)

    def reverse_sweep(self, episode: int, budget: int) -> List[MapTransition]:
        """The episode's last ``budget`` stored transitions, newest first."""
        if budget < 1:
            return []
        own = [t for t in self.memory if t.episode == episode]
        return own[-budget:][::-1]

    def draws(self, n: int, stream) -> List[MapTransition]:
        """``n`` transitions drawn uniformly with replacement (one ``random()`` each)."""
        if not self.memory or n < 1:
            return []
        size = len(self.memory)
        return [self.memory[min(int(stream.random() * size), size - 1)] for _ in range(n)]


__all__ = ["MapTransition", "SRReplay"]
