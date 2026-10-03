"""Deterministic TRN gating, microsleep detection, and replay gating."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable, Tuple

from brain.contracts import Observation

TRN_STATES = ("OPEN", "NARROW", "CLOSED")


@dataclass
class MicrosleepState:
    active: bool = False
    ticks_remaining: int = 0
    below_threshold_streak: int = 0
    recovery_streak: int = 0


@dataclass
class TRNGate:
    microsleep: MicrosleepState = field(default_factory=MicrosleepState)
    replay_buffer: Deque[Observation] = field(default_factory=deque)
    replay_index: int = -1
    replay_active: bool = False
    replay_window: int = 50

    trigger_atp: float = 0.30
    trigger_streak: int = 10
    duration: int = 25
    recovery_atp: float = 0.45
    recovery_streak_needed: int = 5
    # Gate thresholds (see core.config.TRNConfig; the defaults are the values
    # that were hard-coded in trn_state before they became configuration).
    closed_below_atp: float = 0.35
    open_at_atp: float = 0.55
    narrow_above_kappa: float = 1.1
    narrow_gain: float = 0.4
    # False: no bout ever starts (a bout already in progress still runs out).
    microsleep_enabled: bool = True

    def update_microsleep(self, atp: float) -> None:
        ms = self.microsleep
        if ms.active:
            ms.ticks_remaining -= 1
            if atp > self.recovery_atp:
                ms.recovery_streak += 1
            else:
                ms.recovery_streak = 0
            if ms.ticks_remaining <= 0 or ms.recovery_streak >= self.recovery_streak_needed:
                ms.active = False
                ms.ticks_remaining = 0
                ms.recovery_streak = 0
            return

        if not self.microsleep_enabled:
            return

        if atp < self.trigger_atp:
            ms.below_threshold_streak += 1
        else:
            ms.below_threshold_streak = 0

        if ms.below_threshold_streak >= self.trigger_streak:
            ms.active = True
            ms.ticks_remaining = self.duration
            ms.below_threshold_streak = 0
            ms.recovery_streak = 0

    def update_replay(self, observation: Observation) -> Tuple[bool, int]:
        """Update replay buffer and index; return (active, index)."""
        # Maintain buffer of most recent observations
        self.replay_buffer.append(observation)
        if len(self.replay_buffer) > self.replay_window:
            self.replay_buffer.popleft()

        if not self.microsleep.active:
            self.replay_active = False
            self.replay_index = -1
            return self.replay_active, self.replay_index

        # When microsleep active, play through buffer deterministically
        if not self.replay_active:
            self.replay_active = True
            self.replay_index = 0
        else:
            self.replay_index += 1

        if self.replay_index >= len(self.replay_buffer):
            # Loop over buffer deterministically
            self.replay_index = 0

        return self.replay_active, self.replay_index

    def trn_state(self, atp: float, kappa: float) -> Tuple[str, float]:
        """Return (state, gate_value) where gate_value in [0,1].

        The branch order is the original one: CLOSED beats OPEN beats NARROW.
        At the default thresholds this is the table that was hard-coded here
        (0.35 / 0.55 / 1.1 / 0.4).
        """
        if self.microsleep.active or atp < self.closed_below_atp:
            return "CLOSED", 0.0
        if atp >= self.open_at_atp and kappa <= self.narrow_above_kappa:
            return "OPEN", 1.0
        if self.closed_below_atp <= atp < self.open_at_atp or kappa > self.narrow_above_kappa:
            return "NARROW", self.narrow_gain
        return "NARROW", self.narrow_gain


__all__ = ["TRNGate", "TRN_STATES"]
