"""Replay rules over a memory of stored transitions (docs/research_plan.md section 2, M2a first pass).

A replay is a sequence of TD backups applied to a value learner from memory
rather than from the current step. Three of the plan's nine rules are here,
the ones the M2a linear-track experiment runs (``experiments.linear_track_replay``;
docs/m2a_linear_track.md):

- :class:`UniformReplay` (``"uniform"``, the plan's "random" floor): each backup
  is one stored transition drawn uniformly, with replacement, from everything
  in memory.
- :class:`ReverseTrajectoryReplay` (``"reverse_trajectory"``): the transitions
  of the episode that just ended, newest first, so value flows from the
  rewarded end back along the path in one sweep; when the episode is shorter
  than the budget the sweep starts again from the newest (the engine's
  microsleep replay cycles the same way, ``Engine._replay``).
- :class:`PrioritisedTDReplay` (``"prioritised_td"``, the plan's |delta|-gain
  rule): each backup is one stored transition drawn with probability
  proportional to ``|TD error| + epsilon``, where the TD error is **recomputed
  under the learner's current values before every draw** (``ValueFunction
  .td_error``), so priorities are never stale (prioritised sweeping proper,
  Moore & Atkeson 1993, with Schaul et al. 2016's proportional sampling at
  exponent 1). The cost is one pass over the memory per backup.

What they share: :func:`replay` runs exactly ``n_backups`` backups at a trigger
whatever the rule (the plan's fixed budget, so the rules differ in content and
not in the number of learning updates), while :func:`replay_thresholded` (the
plan's thresholded budget, M2a step 2) runs while the rule's ``priority``
exceeds a threshold up to a cap, so rules may differ in rate too; each backup is one stored transition
backed up as it was stored (its own ``terminal`` flag, its own successor), so
no backup ever links two episodes, and every draw comes from the one
``RNGStream`` handed in (the experiment's ``replay`` stream), never from the
environment's or the policy's. The result is a :class:`ReplayOutcome`: a
:class:`~brain.systems.replay_events.ReplayEvent` (trigger, rule, the cells
backed up in order, the direction) plus the transitions and TD errors behind
it.

Direction is the plan's definition: the sign of the position-time slope of
the replayed states along the track, read against the direction the body
travelled (:func:`sequence_direction`): positive is ``forward`` (the replay
runs the way the body ran), negative ``reverse``, zero or undefined
``neither``; the signed Pearson correlation ``sequence_r`` (+1 a perfect
forward sequence, -1 a perfect reverse one) is returned beside the label so a
reader can threshold it. The label is computed from the data for every rule,
the reverse rule included: its sweep runs the stored path backwards, which
reads ``reverse`` only in so far as that path made net progress.

No numpy: dict lookups, ``math.fsum`` and one ``random()`` per draw.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterator, List, Optional, Protocol, Sequence, Tuple

from brain.systems.replay_events import (
    DIRECTION_FORWARD,
    DIRECTION_NEITHER,
    DIRECTION_REVERSE,
    RULE_PRIORITISED_TD,
    RULE_REVERSE_TRAJECTORY,
    RULE_UNIFORM,
    TRIGGER_REWARD,
    ReplayEvent,
)
from core.rng import RNGStream

Cell = Tuple[int, int]


class Learner(Protocol):
    """What a rule needs of a value learner: ``brain.systems.value_learners.ValueFunction``'s backup and read."""

    def update(self, x: float, y: float, reward: float, x_next: float, y_next: float, terminal: bool) -> float: ...

    def td_error(self, x: float, y: float, reward: float, x_next: float, y_next: float, terminal: bool) -> float: ...


@dataclass(frozen=True)
class StoredTransition:
    """One experienced transition, as the learner's ``update`` takes it, plus where it came from.

    ``episode`` and ``index`` say which episode (lap) it belongs to and its
    position in it (0 = the episode's first); ``cell`` is the learner's cell of
    the start position, what a :class:`ReplayEvent` records. A terminal
    transition's successor is ignored by the backup (``V(terminal) = 0``), so a
    stored transition never carries another episode's state into a backup.
    """

    x: float
    y: float
    reward: float
    x_next: float
    y_next: float
    terminal: bool
    episode: int
    index: int
    cell: Cell
    # The action taken (M3 step 3, the action value over the place code): a learner with ``update_action`` is backed
    # up by it; empty for the M2a track rules, whose learners read the action off the geometry.
    action: str = ""

    def backup(self, learner: Learner) -> float:
        """Apply this transition's TD backup to ``learner``; returns the TD error."""
        if self.action and hasattr(learner, "update_action"):
            return learner.update_action(self.x, self.y, self.action, self.reward, self.x_next, self.y_next, self.terminal)  # type: ignore[attr-defined]
        return learner.update(self.x, self.y, self.reward, self.x_next, self.y_next, self.terminal)

    def td_error(self, learner: Learner) -> float:
        """This transition's TD error under ``learner``'s current values, without a backup."""
        if self.action and hasattr(learner, "td_error_action"):
            return learner.td_error_action(self.x, self.y, self.action, self.reward, self.x_next, self.y_next, self.terminal)  # type: ignore[attr-defined]
        return learner.td_error(self.x, self.y, self.reward, self.x_next, self.y_next, self.terminal)


class TransitionMemory:
    """A bounded store of :class:`StoredTransition`, oldest first; the newest ``capacity`` are kept."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"TransitionMemory needs capacity >= 1, got {capacity}")
        self._items: Deque[StoredTransition] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        return int(self._items.maxlen or 0)

    def append(self, transition: StoredTransition) -> None:
        self._items.append(transition)

    def all(self) -> List[StoredTransition]:
        """Every stored transition, oldest first (a snapshot)."""
        return list(self._items)

    def episode(self, episode: int) -> List[StoredTransition]:
        """The stored transitions of ``episode``, in experience order (those still in memory)."""
        return [t for t in self._items if t.episode == episode]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[StoredTransition]:
        return iter(list(self._items))


class ReplayRule(Protocol):
    """A rule picks the transition for each backup of a replay.

    ``begin`` is called once per replay with the memory and the episode that
    just ended; ``choose`` once per backup, with the learner as it stands
    after the previous backups, the stream to draw from and the backup's index
    ``k``; ``span`` is the size of the content the rule walks (for the event
    record); ``priority`` is what the plan's thresholded mode compares with
    its threshold before the ``k``-th backup (:func:`replay_thresholded`): the
    rule keeps replaying while it exceeds the threshold. ``value_scaled`` says whether that
    priority is in the learner's value units (a |TD error|, a gain), so a protocol that
    normalises its threshold by the value scale knows which rules to normalise (M2a step 4,
    docs/prereg/rq1_track_step4.md); a scale-free priority (an occupancy) reads False.
    """

    name: str
    value_scaled: bool

    def begin(self, memory: TransitionMemory, episode: int) -> None: ...

    def choose(self, memory: TransitionMemory, learner: Learner, stream: RNGStream, k: int) -> StoredTransition: ...

    def span(self, memory: TransitionMemory) -> int: ...

    def priority(self, memory: TransitionMemory, learner: Learner, k: int) -> float: ...


def _draw_index(stream: RNGStream, n: int) -> int:
    """One ``random()`` draw mapped to ``0 .. n - 1`` (the last index when the draw rounds up to 1)."""
    return min(int(stream.random() * n), n - 1)


class UniformReplay:
    """Uniform over every stored transition, with replacement; one ``random()`` per backup."""

    name = RULE_UNIFORM
    value_scaled = True  # priority: the mean |TD error| in memory

    def begin(self, memory: TransitionMemory, episode: int) -> None:
        if len(memory) == 0:
            raise ValueError("uniform replay needs at least one stored transition")

    def choose(self, memory: TransitionMemory, learner: Learner, stream: RNGStream, k: int) -> StoredTransition:
        items = memory.all()
        return items[_draw_index(stream, len(items))]

    def span(self, memory: TransitionMemory) -> int:
        return len(memory)

    def priority(self, memory: TransitionMemory, learner: Learner, k: int) -> float:
        """The mean |TD error| over the memory: what a uniform draw is worth on average."""
        items = memory.all()
        if not items:
            return 0.0
        return math.fsum(abs(t.td_error(learner)) for t in items) / len(items)


class ReverseTrajectoryReplay:
    """The episode that just ended, newest transition first, cycling if the budget outlasts it. No draw.

    ``priority`` (for the thresholded mode): ``"next"`` (M2a step 2) reads the |TD error| of the next
    transition of the sweep alone, so a sweep stops at an error-free consume whatever lies deeper in the
    lap; ``"remaining_max"`` (step 3, docs/prereg/rq1_track_gain_need.md change 1) reads the largest
    |TD error| over the remaining part of the one-pass sweep, so the sweep runs on through error-free
    transitions to reach error deeper in the lap and stops once nothing ahead exceeds the threshold.
    """

    name = RULE_REVERSE_TRAJECTORY
    value_scaled = True  # priority: a |TD error| of the sweep
    PRIORITIES = ("next", "remaining_max")

    def __init__(self, priority: str = "next") -> None:
        if priority not in self.PRIORITIES:
            raise ValueError(f"priority must be one of {self.PRIORITIES}, got {priority!r}")
        self.priority_kind = priority
        self._sequence: List[StoredTransition] = []

    def begin(self, memory: TransitionMemory, episode: int) -> None:
        self._sequence = memory.episode(episode)[::-1]
        if not self._sequence:
            raise ValueError(f"reverse-trajectory replay found no stored transition of episode {episode}")

    def choose(self, memory: TransitionMemory, learner: Learner, stream: RNGStream, k: int) -> StoredTransition:
        return self._sequence[k % len(self._sequence)]

    def span(self, memory: TransitionMemory) -> int:
        return len(self._sequence)

    def priority(self, memory: TransitionMemory, learner: Learner, k: int) -> float:
        """``"next"``: the |TD error| of the next transition of the sweep; ``"remaining_max"``: the largest over
        the transitions the sweep has yet to make. 0 once the sweep has covered the episode once (so a
        thresholded replay is at most one pass, no cycling)."""
        if k >= len(self._sequence):
            return 0.0
        if self.priority_kind == "next":
            return abs(self._sequence[k].td_error(learner))
        return max(abs(t.td_error(learner)) for t in self._sequence[k:])


class PrioritisedTDReplay:
    """Proportional to ``|TD error| + epsilon``, the error recomputed under the current values before each draw.

    One ``random()`` per backup, walked over the cumulative priorities in
    memory order (``math.fsum`` for the total, so the walk ends exactly at it).
    ``epsilon`` keeps a zero-error transition drawable; with every error 0
    (nothing learned yet) the draw is uniform.
    """

    name = RULE_PRIORITISED_TD
    value_scaled = True  # priority: the largest |TD error| in memory

    def __init__(self, epsilon: float = 1e-6) -> None:
        if not epsilon > 0.0 or not math.isfinite(epsilon):
            raise ValueError(f"epsilon must be a finite positive number, got {epsilon}")
        self.epsilon = float(epsilon)
        self.last_priorities: List[float] = []  # diagnostics: the priorities behind the last draw

    def begin(self, memory: TransitionMemory, episode: int) -> None:
        if len(memory) == 0:
            raise ValueError("prioritised replay needs at least one stored transition")

    def choose(self, memory: TransitionMemory, learner: Learner, stream: RNGStream, k: int) -> StoredTransition:
        items = memory.all()
        priorities = [abs(t.td_error(learner)) + self.epsilon for t in items]
        self.last_priorities = priorities
        total = math.fsum(priorities)
        u = stream.random() * total
        acc = 0.0
        for item, p in zip(items, priorities):
            acc += p
            if u < acc:
                return item
        return items[-1]  # u rounded up to the total

    def span(self, memory: TransitionMemory) -> int:
        return len(memory)

    def priority(self, memory: TransitionMemory, learner: Learner, k: int) -> float:
        """The largest |TD error| in memory: what the next draw is most likely to find."""
        items = memory.all()
        if not items:
            return 0.0
        return max(abs(t.td_error(learner)) for t in items)


RULES = {
    RULE_UNIFORM: UniformReplay,
    RULE_REVERSE_TRAJECTORY: ReverseTrajectoryReplay,
    RULE_PRIORITISED_TD: PrioritisedTDReplay,
}


def make_rule(name: str, epsilon: float = 1e-6, trajectory_priority: str = "next") -> ReplayRule:
    """A fresh rule by its plan name (``uniform``, ``reverse_trajectory``, ``prioritised_td``); the gain x need
    rules need an environment model and are made by ``brain.systems.replay_gain_need.GainNeedReplay``."""
    if name == RULE_PRIORITISED_TD:
        return PrioritisedTDReplay(epsilon)
    if name == RULE_REVERSE_TRAJECTORY:
        return ReverseTrajectoryReplay(trajectory_priority)
    try:
        return RULES[name]()
    except KeyError:
        raise ValueError(f"unknown replay rule {name!r}; one of {sorted(RULES)}") from None


def sequence_direction(positions: Sequence[float], travel_sign: int) -> Tuple[str, float]:
    """(direction, sequence_r) of a replayed sequence of track positions.

    ``sequence_r`` is the Pearson correlation between backup index and position,
    multiplied by ``travel_sign`` (+1 when the body ran toward increasing
    positions in the episode being replayed, -1 otherwise), so +1 is a perfect
    forward sequence and -1 a perfect reverse one. The direction is its sign:
    ``forward`` above 0, ``reverse`` below, ``neither`` at exactly 0 or when the
    correlation is undefined (fewer than two backups, or every position the
    same).
    """
    n = len(positions)
    if travel_sign not in (1, -1):
        raise ValueError("travel_sign must be +1 or -1")
    if n < 2:
        return DIRECTION_NEITHER, 0.0
    mean_i = (n - 1) / 2.0
    mean_x = math.fsum(positions) / n
    cov = math.fsum((i - mean_i) * (x - mean_x) for i, x in enumerate(positions))
    var_i = math.fsum((i - mean_i) ** 2 for i in range(n))
    var_x = math.fsum((x - mean_x) ** 2 for x in positions)
    if var_x == 0.0:
        return DIRECTION_NEITHER, 0.0
    r = travel_sign * cov / math.sqrt(var_i * var_x)
    if r > 0.0:
        return DIRECTION_FORWARD, r
    if r < 0.0:
        return DIRECTION_REVERSE, r
    return DIRECTION_NEITHER, 0.0


@dataclass(frozen=True)
class ReplayOutcome:
    """What one replay did: its event record plus the transitions and TD errors behind it."""

    event: ReplayEvent
    transitions: Tuple[StoredTransition, ...]
    deltas: Tuple[float, ...]  # the TD error each backup applied
    sequence_r: float

    @property
    def n_backups(self) -> int:
        return len(self.transitions)


def replay(
    rule: ReplayRule,
    memory: TransitionMemory,
    learner: Learner,
    n_backups: int,
    episode: int,
    stream: RNGStream,
    *,
    tick: int,
    travel_sign: int = 1,
    trigger: str = TRIGGER_REWARD,
) -> ReplayOutcome:
    """Run exactly ``n_backups`` backups of ``rule`` from ``memory`` into ``learner``.

    Every rule gets the same count, so conditions differ in content only; every
    draw comes from ``stream``. ``episode`` is the episode that just ended (what
    the reverse rule sweeps), ``tick`` the tick the replay happens at (recorded
    on the event, start and end alike: the replay is a pause, not engine ticks)
    and ``travel_sign`` the sign of the body's travel along the track in that
    episode, for the direction label.
    """
    if n_backups < 1:
        raise ValueError(f"a replay needs n_backups >= 1, got {n_backups}")
    rule.begin(memory, episode)
    chosen: List[StoredTransition] = []
    deltas: List[float] = []
    for k in range(n_backups):
        transition = rule.choose(memory, learner, stream, k)
        deltas.append(transition.backup(learner))
        chosen.append(transition)
    return _outcome(rule, memory, chosen, deltas, tick, travel_sign, trigger)


def replay_thresholded(
    rule: ReplayRule,
    memory: TransitionMemory,
    learner: Learner,
    threshold: float,
    cap: int,
    episode: int,
    stream: RNGStream,
    *,
    tick: int,
    travel_sign: int = 1,
    trigger: str = TRIGGER_REWARD,
) -> Optional[ReplayOutcome]:
    """The plan's thresholded budget: back up while ``rule.priority`` exceeds ``threshold``, at most ``cap`` times.

    The priority is read before every backup under the learner as it then
    stands, so a rule stops as soon as what it would replay next carries no
    more than ``threshold`` of TD error. Returns ``None`` when the first
    priority is already at or below the threshold (no backup, no event);
    otherwise the same :class:`ReplayOutcome` as :func:`replay`, with between
    1 and ``cap`` backups.
    """
    if cap < 1:
        raise ValueError(f"a thresholded replay needs cap >= 1, got {cap}")
    if not math.isfinite(threshold) or threshold < 0.0:
        raise ValueError(f"threshold must be a finite non-negative number, got {threshold}")
    rule.begin(memory, episode)
    chosen: List[StoredTransition] = []
    deltas: List[float] = []
    for k in range(cap):
        if not rule.priority(memory, learner, k) > threshold:
            break
        transition = rule.choose(memory, learner, stream, k)
        deltas.append(transition.backup(learner))
        chosen.append(transition)
    if not chosen:
        return None
    return _outcome(rule, memory, chosen, deltas, tick, travel_sign, trigger)


def _outcome(
    rule: ReplayRule,
    memory: TransitionMemory,
    chosen: Sequence[StoredTransition],
    deltas: Sequence[float],
    tick: int,
    travel_sign: int,
    trigger: str,
) -> ReplayOutcome:
    direction, r = sequence_direction([t.x for t in chosen], travel_sign)
    cells = tuple(t.cell for t in chosen)
    event = ReplayEvent(
        tick_start=tick,
        tick_end=tick,
        trigger=trigger,
        rule=rule.name,
        cells=cells,
        direction=direction,
        start_cell=cells[0],
        n_backups=len(cells),
        span=rule.span(memory),
    )
    return ReplayOutcome(event=event, transitions=tuple(chosen), deltas=tuple(deltas), sequence_r=r)


__all__ = [
    "Cell",
    "Learner",
    "PrioritisedTDReplay",
    "RULES",
    "ReplayOutcome",
    "ReplayRule",
    "ReverseTrajectoryReplay",
    "StoredTransition",
    "TransitionMemory",
    "UniformReplay",
    "make_rule",
    "replay",
    "replay_thresholded",
    "sequence_direction",
]
