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
replay (``replay_backup`` / ``replay_transition`` / ``consolidate``), which
propagates value backward along the stored trajectory. Microsleep replays the
recent path in reverse (``recent_transitions``, see ``Engine._replay``).
``reset_episode`` marks a boundary in the trajectory, and no replay links a
transition across it. Values generalize to neighbouring
cells with a decaying kernel (overlapping place fields;
``generalization_radius`` 0 disables it), so a single trajectory fills a
followable 2-D field instead of a thin one-cell path.

Small positive peaks that the agent builds by staying put are extinguished by
``dwell_extinction`` (see ``record``): without it nothing but slow decay
removes them, and a tiny peak under the agent reads, once the steering signal is
normalized, as "every direction is worse than here". "Staying put" means a
transition whose start and end fall in the same place-cell bin, so it covers
REST and also the turns made in place (a TURN moves 0.3, usually inside one
0.5 bin). The charge is never logged: the trajectory keeps the reward actually
received, and replay re-applies the charge under the same rule as online
(same cell, and that cell's value still positive at replay time), so repeated
replay extinguishes a peak to zero instead of driving it negative.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Iterable, List, Optional, Tuple

Cell = Tuple[int, int]
Transition = Tuple[Cell, Cell, float]  # (from cell, to cell, reward received on arrival)


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
        # Default extinction cost for calls that do not pass one. An Engine
        # always passes config.value_memory.dwell_extinction explicitly, so
        # inside an Engine this attribute is not read.
        self.dwell_extinction = dwell_extinction
        self.gamma = discount
        self.gen_radius = generalization_radius
        self.gen_falloff = generalization_falloff
        self.values: Dict[Cell, float] = {}
        self.trajectory: Deque[Tuple[Cell, float]] = deque(maxlen=capacity)
        # Episode boundaries, kept beside the trajectory (whose (cell, reward)
        # entries stay as they were): _linked[i] says whether the i-th logged
        # entry was reached from the entry before it in the same episode, i.e.
        # False for the first step after reset_episode. Both deques are appended
        # in lockstep and share maxlen, so they stay aligned at their newest end
        # even when a caller clears ``trajectory`` (see ``_is_linked``).
        self._linked: Deque[bool] = deque(maxlen=capacity)
        self._prev_cell: Optional[Cell] = None  # last place, for the online TD transition
        # Goal-vector memory: the arrival cell of the last replayed transition
        # with positive reward (see replay_backup). With the default
        # primary-only map that is target contact; with learn_shaping on,
        # approach steps carry positive reward too and would also be written.
        # Only read when the engine's value_memory.goal_vector is on.
        self.goal_cell: Optional[Cell] = None

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

    def _extinction(self, dwell_extinction: Optional[float]) -> float:
        return self.dwell_extinction if dwell_extinction is None else dwell_extinction

    def _dwell_charge(self, from_cell: Optional[Cell], to_cell: Cell, extinction: float) -> float:
        """The extinction charge for ``from_cell -> to_cell``: ``extinction`` when the
        agent stayed in one place cell and that cell is (still) positively valued, else 0."""
        if extinction and from_cell == to_cell and self.values.get(to_cell, 0.0) > 0.0:
            return extinction
        return 0.0

    def record(self, cell: Cell, reward: float, dwell_extinction: Optional[float] = None) -> None:
        """Observe arrival at ``cell`` with ``reward``; log it and do the online TD backup.

        The reward is credited to the transition that led here (reward-on-arrival),
        so V(previous) bootstraps on V(cell). The first step of an episode has no
        predecessor and only logs.

        Dwell extinction: a same-cell (dwelling) transition on a positively valued
        place is charged the extinction cost before the backup, so a peak the
        agent builds by staying put fades instead of holding it there. The cost is
        ``dwell_extinction`` when given (the engine passes its config value on
        every call, so the config is the single source of truth inside an
        Engine), else the ``self.dwell_extinction`` set at construction. Only the
        uncharged ``reward`` is logged; replay re-applies the charge under the
        same rule (see ``replay_transition``).
        """
        charge = self._dwell_charge(self._prev_cell, cell, self._extinction(dwell_extinction))
        if self._prev_cell is not None:
            self._td_update(self._prev_cell, reward - charge + self.gamma * self.values.get(cell, 0.0))
        self.trajectory.append((cell, reward))
        self._linked.append(self._prev_cell is not None)
        self._prev_cell = cell

    def reset_episode(self) -> None:
        """Mark an episode boundary so no transition links across a reset/teleport."""
        self._prev_cell = None

    def _is_linked(self, index: int) -> bool:
        """Whether ``trajectory[index]`` was reached from ``trajectory[index - 1]``
        within one episode (no reset/teleport between them)."""
        n = len(self.trajectory)
        if index <= 0 or index >= n:
            return False
        offset = index - n  # aligned at the newest end; see __init__
        return -offset > len(self._linked) or self._linked[offset]

    def transition(self, index: int) -> Optional[Transition]:
        """The stored transition ``trajectory[index] -> trajectory[index + 1]``, or
        None if out of range or if it spans an episode boundary."""
        if index < 0 or not self._is_linked(index + 1):
            return None
        from_cell, _ = self.trajectory[index]
        to_cell, reward_on_arrival = self.trajectory[index + 1]
        return from_cell, to_cell, reward_on_arrival

    def recent_transitions(self, count: int) -> List[Transition]:
        """The transitions among the newest ``count + 1`` trajectory entries, most
        recent first, skipping any that span an episode boundary.

        This is the order of reverse replay: replaying it front to back carries
        value from the end of the path (where reward was found) back toward its
        start in one sweep. The list is a snapshot: later ``record`` calls do
        not change it.
        """
        n = len(self.trajectory)
        first = max(0, n - 1 - count)
        out: List[Transition] = []
        for index in range(n - 2, first - 1, -1):
            t = self.transition(index)
            if t is not None:
                out.append(t)
        return out

    def replay_backup(self, transition: Transition, dwell_extinction: Optional[float] = None) -> None:
        """Offline TD(0) backup for one transition (used during replay).

        A dwelling transition is charged the extinction cost only if its cell is
        still positive now, exactly as online, so replay can extinguish a
        self-made peak but never turn it into an aversive one.
        """
        from_cell, to_cell, reward_on_arrival = transition
        charge = self._dwell_charge(from_cell, to_cell, self._extinction(dwell_extinction))
        self._td_update(from_cell, reward_on_arrival - charge + self.gamma * self.values.get(to_cell, 0.0))
        if reward_on_arrival > 0.0:
            # Replaying a rewarded arrival writes its place as the goal.
            self.goal_cell = to_cell

    def replay_transition(self, index: int, dwell_extinction: Optional[float] = None) -> None:
        """Replay the stored transition at ``index`` (see ``replay_backup``); a no-op
        if it is out of range or spans an episode boundary."""
        t = self.transition(index)
        if t is not None:
            self.replay_backup(t, dwell_extinction)

    def consolidate(self, passes: int = 1, dwell_extinction: Optional[float] = None) -> None:
        """Replay the whole trajectory backward ``passes`` times (offline sweep).

        Transitions that span an episode boundary are skipped, so a sweep never
        links the end of one episode to the start of the next.
        """
        for _ in range(passes):
            for index in range(len(self.trajectory) - 2, -1, -1):
                self.replay_transition(index, dwell_extinction)

    def value_of(self, cell: Cell) -> float:
        return self.values.get(cell, 0.0)


__all__ = ["Cell", "Transition", "ValueMemory"]
