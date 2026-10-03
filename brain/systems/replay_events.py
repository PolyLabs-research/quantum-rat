"""Microsleep replay as an explicit event object (docs/research_plan.md section 2, M1).

A :class:`ReplayEvent` is the record of one replay: the ticks it ran over, what
triggered it, which rule chose its content, the place cells it backed up in
order, and its direction. In M1 the only trigger is microsleep and the only
rules are the two that already exist in ``Engine._replay``: the
reverse-trajectory snapshot (``value_memory.replay_recent``, the default) and
the legacy TRN-index walk. The event is bookkeeping beside the backups: the
backups themselves, the engine context fields the console reads
(``replay_cell``, ``replay_back``, ``replay_span``) and TickData are exactly
as they were, so an event never enters a trace hash (the legacy gate proves
it, tests/engine/test_replay_events.py). A pluggable rule, stochastic
triggers and the console drawing each event on the arena come with later
milestones. Plan section 2's JSONL line (``tick``, ``trigger``, ``rule``,
``states``, ``direction``, ``start_dist_m``) maps onto ``tick_start``,
``trigger``, ``rule``, ``cells`` and ``direction`` here; ``start_dist_m``
waits for the place population that gives a distance its meaning.

:class:`OpenReplayEvent` is the mutable builder the engine holds while a
replay is in progress; :class:`ReplayLog` is the bounded record the finished
events go to (``engine.replay_log``). The headless runner writes them to
:data:`REPLAY_EVENTS_FILE` as they close, and the console's recording does
the same for the events its session holds.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterator, List, Optional, Tuple

Cell = Tuple[int, int]

TRIGGER_MICROSLEEP = "microsleep"
RULE_REVERSE_TRAJECTORY = "reverse_trajectory"  # value_memory.replay_recent = True (the default)
RULE_TRN_INDEX = "trn_index"  # value_memory.replay_recent = False (legacy)
DIRECTION_REVERSE = "reverse"
DIRECTION_FORWARD = "forward"
DEFAULT_LOG_SIZE = 256
REPLAY_EVENTS_FILE = "replay_events.jsonl"


@dataclass(frozen=True)
class ReplayEvent:
    """One completed replay.

    ``tick_start`` is the first tick the replay ran on (microsleep onset, when
    the plan is snapshotted) and ``tick_end`` the last one, inclusive: the last
    replay tick of the bout, or the last tick before ``Engine.begin_episode``
    cut it. ``cells`` are the place cells backed up, one per backup tick in
    backup order (the start cell of each replayed transition), so
    ``len(cells) == n_backups`` and ``start_cell`` is the first of them.
    ``span`` is the size of the content the rule walked: the snapshot's length
    for ``reverse_trajectory`` (the backups cycle through it if the sleep
    outlasts it, never at the defaults, where a 25-tick sleep walks at most 25
    of up to 50 transitions) and the TRN observation buffer's length for
    ``trn_index`` (the range its index walks).
    """

    tick_start: int
    tick_end: int
    trigger: str
    rule: str
    cells: Tuple[Cell, ...]
    direction: str
    start_cell: Optional[Cell]
    n_backups: int
    span: int

    def to_dict(self) -> Dict[str, Any]:
        """A JSON-serialisable dict (cells as lists): one line of replay_events.jsonl."""
        return {
            "tick_start": self.tick_start,
            "tick_end": self.tick_end,
            "trigger": self.trigger,
            "rule": self.rule,
            "cells": [[int(bx), int(by)] for bx, by in self.cells],
            "direction": self.direction,
            "start_cell": None if self.start_cell is None else [int(self.start_cell[0]), int(self.start_cell[1])],
            "n_backups": self.n_backups,
            "span": self.span,
        }


class OpenReplayEvent:
    """A replay in progress: opened on its first tick, fed one cell per backup, closed into a :class:`ReplayEvent`."""

    def __init__(self, tick_start: int, trigger: str, rule: str, direction: str, span: int) -> None:
        self.tick_start = tick_start
        self.tick_last = tick_start
        self.trigger = trigger
        self.rule = rule
        self.direction = direction
        self.span = span
        self.cells: List[Cell] = []

    def tick(self, tick: int) -> None:
        """Note a tick the replay ran on, whether or not it backed anything up."""
        self.tick_last = tick

    def backup(self, tick: int, cell: Cell) -> None:
        """Note the backup of a transition starting at ``cell`` on ``tick``."""
        self.tick_last = tick
        self.cells.append((int(cell[0]), int(cell[1])))

    def close(self) -> Optional[ReplayEvent]:
        """The finished event, or None when nothing was backed up (then there is no event)."""
        if not self.cells:
            return None
        cells = tuple(self.cells)
        return ReplayEvent(
            tick_start=self.tick_start,
            tick_end=self.tick_last,
            trigger=self.trigger,
            rule=self.rule,
            cells=cells,
            direction=self.direction,
            start_cell=cells[0],
            n_backups=len(cells),
            span=self.span,
        )


class ReplayLog:
    """A bounded record of finished replay events: the newest ``maxlen`` are kept, oldest first."""

    def __init__(self, maxlen: int = DEFAULT_LOG_SIZE) -> None:
        if maxlen < 1:
            raise ValueError(f"ReplayLog needs maxlen >= 1, got {maxlen}")
        self._events: Deque[ReplayEvent] = deque(maxlen=maxlen)

    @property
    def maxlen(self) -> int:
        return int(self._events.maxlen or 0)

    def append(self, event: ReplayEvent) -> None:
        self._events.append(event)

    def latest(self, n: int) -> List[ReplayEvent]:
        """The newest ``n`` events (fewer if the log holds fewer), oldest first."""
        if n <= 0:
            return []
        events = list(self._events)
        return events[-n:]

    def drain(self) -> List[ReplayEvent]:
        """Every held event, oldest first; the log is empty afterwards."""
        events = list(self._events)
        self._events.clear()
        return events

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[ReplayEvent]:
        return iter(list(self._events))

    def __bool__(self) -> bool:
        return bool(self._events)


__all__ = [
    "Cell",
    "DEFAULT_LOG_SIZE",
    "DIRECTION_FORWARD",
    "DIRECTION_REVERSE",
    "OpenReplayEvent",
    "REPLAY_EVENTS_FILE",
    "RULE_REVERSE_TRAJECTORY",
    "RULE_TRN_INDEX",
    "ReplayEvent",
    "ReplayLog",
    "TRIGGER_MICROSLEEP",
]
