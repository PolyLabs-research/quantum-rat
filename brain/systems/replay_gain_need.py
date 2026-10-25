"""Gain x need replay and its ablations (Mattar & Daw 2018; docs/research_plan.md section 2; M2a step 3,
docs/prereg/rq1_track_gain_need.md).

The expected value of backing up a stored transition e = (s -> s', r) is the product of
two terms. **Gain** is how much better the agent would act after the backup: the backup
moves V(s) to V(s) + lr * delta, the decisions that read V(s) are those at s's
predecessors p (the states with an action into s, which the environment ``model``
supplies), and at each p the policy is the model's softmax over the values one step
ahead; gain(e) = sum over p and actions a of [pi_new(a|p) - pi_old(a|p)] * V_new(s'(p, a)),
the expected value of acting at p under the new policy minus under the old, both read
with the updated values (Mattar & Daw's gain with Q(p, a) = V(s'(p, a))). It is
non-negative. **Need** is the expected discounted future occupancy of s from the state the
agent will act from next, a row of the tabular successor representation
(``brain.systems.successor.TabularSR``) the model exposes.

Three rules, one class: ``gain_need`` (EVB = need * gain), ``gain_only`` (gain), ``need_only``
(need). Selection is the argmax over the *distinct* stored transitions (a deterministic
track makes duplicates identical candidates; ties go to the most recently stored),
recomputed after every backup; no draw is made, so these rules consume nothing from the
``replay`` stream. They implement the ``brain.systems.replay_rules.ReplayRule`` protocol:
``begin``, ``choose``, ``span`` and ``priority`` (the largest EVB in memory, for the
thresholded mode), so ``replay`` and ``replay_thresholded`` run them unchanged.

The ``model`` (``ReplayModel``) is the environment's part: state indices for learner
coordinates, predecessors and successors by action, the policy's scores and softmax,
the value by state, the learning rate, the need, and the state the agent acts from next.
``experiments.linear_track_replay.TrackModel`` is the track's.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from brain.systems.replay_rules import Learner, StoredTransition, TransitionMemory
from core.rng import RNGStream

MODES = ("gain_need", "gain_only", "need_only")


class ReplayModel(Protocol):
    """What the gain and need terms need from the environment and the agent."""

    def state_index(self, x: float, y: float) -> int: ...

    def predecessors(self, state: int) -> Sequence[Tuple[int, str]]: ...

    def successors(self, state: int) -> Mapping[str, int]: ...

    def action_scores(self, state: int, value_of: Mapping[int, float]) -> Mapping[str, float]: ...

    def policy(self, scores: Mapping[str, float]) -> Mapping[str, float]: ...

    def value_of_index(self, state: int) -> float: ...

    @property
    def learning_rate(self) -> float: ...

    def need(self, from_state: int, to_state: int) -> float: ...

    def acting_state(self) -> int: ...


def gain_of(model: ReplayModel, state: int, delta: float) -> float:
    """The gain of moving V(state) by ``model.learning_rate * delta``: the expected improvement in the
    decisions at the state's predecessors, read with the updated values (module docstring)."""
    new_value = model.value_of_index(state) + model.learning_rate * delta
    total = 0.0
    for p, _ in model.predecessors(state):
        successors = model.successors(p)
        old_values: Dict[int, float] = {s: model.value_of_index(s) for s in successors.values()}
        new_values = dict(old_values)
        if state in new_values:
            new_values[state] = new_value
        pi_old = model.policy(model.action_scores(p, old_values))
        pi_new = model.policy(model.action_scores(p, new_values))
        for action, s_next in successors.items():
            total += (pi_new[action] - pi_old[action]) * new_values[s_next]
    return total


class GainNeedReplay:
    """Argmax replay by EVB = need * gain, or by one factor alone (``mode``)."""

    def __init__(self, model: ReplayModel, mode: str = "gain_need") -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        self.model = model
        self.mode = mode
        self.name = mode
        self.last_priorities: Dict[Tuple[float, float, float, float, float, bool], float] = {}  # diagnostics

    def begin(self, memory: TransitionMemory, episode: int) -> None:
        if len(memory) == 0:
            raise ValueError(f"{self.name} replay needs at least one stored transition")

    def _distinct(self, memory: TransitionMemory) -> List[StoredTransition]:
        """One candidate per distinct (s, s', r, terminal), the most recently stored occurrence."""
        latest: Dict[Tuple[float, float, float, float, float, bool], StoredTransition] = {}
        for t in memory.all():  # oldest first: later duplicates overwrite earlier ones
            latest[(t.x, t.y, t.x_next, t.y_next, t.reward, t.terminal)] = t
        return list(latest.values())

    def evb(self, transition: StoredTransition, learner: Learner) -> float:
        state = self.model.state_index(transition.x, transition.y)
        acting = self.model.acting_state()
        need = self.model.need(acting, state) if self.mode != "gain_only" else 1.0
        if self.mode == "need_only":
            return need
        gain = gain_of(self.model, state, transition.td_error(learner))
        return need * gain

    def _ranked(self, memory: TransitionMemory, learner: Learner) -> List[Tuple[float, StoredTransition]]:
        candidates = self._distinct(memory)
        scored = [(self.evb(t, learner), t) for t in candidates]
        self.last_priorities = {(t.x, t.y, t.x_next, t.y_next, t.reward, t.terminal): v for v, t in scored}
        return scored

    def choose(self, memory: TransitionMemory, learner: Learner, stream: RNGStream, k: int) -> StoredTransition:
        """The distinct transition with the largest priority; ties to the most recently stored (the list is in
        first-occurrence order of the latest occurrences, so the later entry wins a tie)."""
        best: Optional[Tuple[float, int, StoredTransition]] = None
        for position, (value, t) in enumerate(self._ranked(memory, learner)):
            key = (value, t.episode, t.index, position)
            if best is None or key > (best[0], best[2].episode, best[2].index, best[1]):
                best = (value, position, t)
        assert best is not None
        return best[2]

    def span(self, memory: TransitionMemory) -> int:
        return len(self._distinct(memory))

    def priority(self, memory: TransitionMemory, learner: Learner, k: int) -> float:
        ranked = self._ranked(memory, learner)
        return max(v for v, _ in ranked) if ranked else 0.0


__all__ = ["GainNeedReplay", "MODES", "ReplayModel", "gain_of"]
