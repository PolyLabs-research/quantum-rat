"""Bounded working memory updated deterministically from Observation and spatial cues.

The ``novelty`` it reports is a checksum-changed bit: 1.0 on a tick whose
observation checksum (``core.sensors.observation_checksum``, a hash of the
whole Observation) differs from the previous tick's, else 0.0. It is not a
measure of how new a place or stimulus is. At sensor noise 0 it is 1 on the
ticks where the observation changed at all, which in an empty arena means the
agent moved (0.61 of open-field ticks, 0.08 during microsleep); at sensor
noise 0.03 the noisy ray distances change every tick, so it is 1 on every
tick (``python -m tools.probes.novelty_pinning``, recorded in
tools/probes/README.md). Acetylcholine equals this bit and norepinephrine is
half of it (``core/neuromodulation.py``), and it adds ``novelty_gain`` to the
FORWARD score in the basal ganglia.

``load`` is the number of entries in the bounded buffer; it saturates at the
capacity (32) and is read by nothing.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Tuple

from brain.contracts import Observation


@dataclass
class WorkingMemoryState:
    load: int = 0
    novelty: float = 0.0  # 1.0 iff the observation checksum changed since the previous tick
    last_checksum: str = ""


class WorkingMemory:
    def __init__(self, capacity: int = 32) -> None:
        self.capacity = capacity
        self.buffer: Deque[Dict[str, float | int | str]] = deque(maxlen=capacity)
        self.state = WorkingMemoryState()

    def update(self, observation: Observation, place_id: int, obs_checksum: str) -> WorkingMemoryState:
        """Append the tick's entry and set novelty = 1.0 iff ``obs_checksum`` changed.

        The checksum covers the whole Observation, so any change in any ray
        distance, whisker bit, pain value or egomotion delta counts as novelty.
        """
        entry = {
            "pain": observation.pain_signal,
            "forward": observation.forward_delta,
            "turn": observation.turn_delta,
            "place_id": place_id,
            "checksum": obs_checksum,
        }
        self.buffer.append(entry)
        self.state.load = len(self.buffer)
        self.state.novelty = 1.0 if obs_checksum != self.state.last_checksum else 0.0
        self.state.last_checksum = obs_checksum
        return self.state


__all__ = ["WorkingMemory", "WorkingMemoryState"]
