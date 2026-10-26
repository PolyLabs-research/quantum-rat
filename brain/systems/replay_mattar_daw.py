"""The Mattar & Daw (2018) rule on a tabular Q learner, with the forward n-step extension (M2a step 5,
docs/prereg/rq1_track_mattar_daw.md; docs/research_plan.md section 2).

Prioritised memory access as published, as far as this track and learner allow: the agent learns
Q(s, a) by Q-learning (``brain.systems.value_learners.TabularQ``) and acts by a softmax over Q(s, .);
a replay backup of a stored transition e = (s, a, r, s') is the expected value of the backup,
EVB(e) = need(s) x gain(e). **Gain** is read at the acted-from state s over its actions: the backup
moves Q(s, a) by lr x delta; the policy at s is the softmax over the action scores read on Q(s, .)
(the same scores the agent acts on); gain(e) = sum_a [pi_new(a|s) - pi_old(a|s)] Q_new(s, a), the
expected value of acting at s under the new policy minus under the old, both read with the updated
values. A gain below ``gain_floor`` reads as ``gain_floor`` (Mattar & Daw's minimum gain), so that
when every gain is negligible the order among candidates is need's. **Need** is the successor
representation's expected discounted occupancy of s from the state the agent acts from next
(``model.need``, as in ``brain.systems.replay_gain_need``).

**The forward n-step extension** (our reading of Mattar & Daw's n-step backups). The rule keeps the
chain of its backups within the pause while each continues the last one forward (its state is the
last one's successor state). Beside every one-step candidate, each stored transition t that
continues the chain forward is a candidate as the *extension*: the n-step backup of the chain's
first transition e_1 through the chain and t, target = sum_i discount^(i-1) r_i + discount^n x
max_a Q(s_(n+1), a) (nothing beyond a terminal t), EVB = need(s_1) x gain of that backup at s_1.
When an extension is chosen the chain's first Q(s_1, a_1) is backed up toward the n-step target
(one TD backup, counted like any other) and the chain grows by t; the replay record shows t's cell,
the state the sequence advanced to. When a one-step candidate is chosen the chain restarts at it.
Ties go to the extension (it continues a sequence), then to the most recently stored transition.
Without the extension (``extension=False``, the ``mattar_daw_1step`` ablation) the rule is the
one-step argmax alone.

Selection is the argmax over the distinct stored transitions (duplicates are one candidate) plus
the extensions, recomputed after every backup; no draw is made (nothing is consumed from the
``replay`` stream). ``priority`` (the thresholded mode) is the largest EVB; it is in value units
(``value_scaled``). The ``model`` (``QReplayModel``) is the environment's part: state indices for
learner coordinates, the action a transition took, the action scores and the softmax, the learning
rate and discount, the need, and the state the agent acts from next.
"""

from __future__ import annotations

import math
from typing import Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, Union

from brain.systems.replay_rules import Learner, RNGStream, StoredTransition, TransitionMemory

MATTAR_DAW = "mattar_daw"
MATTAR_DAW_1STEP = "mattar_daw_1step"
MATTAR_DAW_CONDITIONS: Tuple[str, ...] = (MATTAR_DAW, MATTAR_DAW_1STEP)
DEFAULT_GAIN_FLOOR = 1e-10
# What ``priority`` reads before a pause's first backup, when the chain is empty (M2a step 6, G31 C3). "one_step": the
# largest one-step EVB alone (step 5), which for the extension rule is orders of magnitude below the EVBs it reaches
# once a chain exists, so a theta set on it either never starts the rule or binds its cap. "seeded": also the EVB of
# extending a would-be chain seeded with the acting state's most recent outgoing transition (the chain the rule's
# first forward step would build), so that the first-backup priority is on the scale of the later ones. ``choose`` is
# the same under both: the seed is not backed up, only read.
PRIORITY_MODES: Tuple[str, ...] = ("one_step", "seeded")


class QReplayModel(Protocol):
    """What the gain, the need and the extension need from the environment and the agent."""

    def state_index(self, x: float, y: float) -> int: ...

    def action_of(self, x: float, y: float, x_next: float, y_next: float) -> str: ...

    def action_scores(self, q: Mapping[str, float]) -> Mapping[str, float]: ...

    def policy(self, scores: Mapping[str, float]) -> Mapping[str, float]: ...

    def learning_rate(self) -> float: ...

    def discount(self) -> float: ...

    def need(self, from_state: int, to_state: int) -> float: ...

    def acting_state(self) -> int: ...


class QLearner(Learner, Protocol):
    """The learner the rule reads Q from and backs up toward a target (``TabularQ``)."""

    def q(self, x: float, y: float) -> Dict[str, float]: ...

    def value(self, x: float, y: float) -> float: ...

    def update_target(self, x: float, y: float, action: str, target: float) -> float: ...


def gain_q(model: QReplayModel, q_old: Mapping[str, float], action: str, step: float) -> float:
    """The gain of moving ``Q(s, action)`` by ``step`` at a state whose action values are ``q_old``: the expected
    improvement of the decision at s under the softmax, read with the updated values (module docstring)."""
    q_new = dict(q_old)
    q_new[action] = q_old[action] + step
    pi_old = model.policy(model.action_scores(q_old))
    pi_new = model.policy(model.action_scores(q_new))
    return math.fsum((pi_new[a] - pi_old[a]) * q_new[a] for a in q_new)


class ExtendedBackup:
    """The n-step backup of a chain's first transition through ``appended``: walks like a ``StoredTransition``
    for the replay machinery (its position, cell and lap are the appended transition's, the state the sequence
    advanced to) while its backup moves the first transition's Q toward the n-step ``target``."""

    def __init__(self, first: StoredTransition, appended: StoredTransition, action: str, target: float, length: int) -> None:
        self.first = first
        self.appended = appended
        self.action = action
        self.target = target
        self.length = length  # transitions in the backup, chain plus the appended one
        self.x, self.y, self.reward = appended.x, appended.y, appended.reward
        self.x_next, self.y_next, self.terminal = appended.x_next, appended.y_next, appended.terminal
        self.episode, self.index, self.cell = appended.episode, appended.index, appended.cell

    def backup(self, learner: Learner) -> float:
        return learner.update_target(self.first.x, self.first.y, self.action, self.target)  # type: ignore[attr-defined]

    def td_error(self, learner: Learner) -> float:
        return self.target - learner.q(self.first.x, self.first.y)[self.action]  # type: ignore[attr-defined]


Candidate = Union[StoredTransition, ExtendedBackup]


class MattarDawReplay:
    """Argmax replay by EVB = need x gain on a Q learner, with (``extension``) or without the forward n-step extension."""

    value_scaled = True  # a gain is in value units

    def __init__(self, model: QReplayModel, extension: bool = True, gain_floor: float = DEFAULT_GAIN_FLOOR,
                 priority_mode: str = "one_step", name: Optional[str] = None) -> None:
        if not (math.isfinite(gain_floor) and gain_floor >= 0.0):
            raise ValueError("gain_floor must be a finite non-negative number")
        if priority_mode not in PRIORITY_MODES:
            raise ValueError(f"priority_mode must be one of {PRIORITY_MODES}, got {priority_mode!r}")
        self.model = model
        self.extension = bool(extension)
        self.gain_floor = float(gain_floor)
        self.priority_mode = priority_mode
        self.name = name or (MATTAR_DAW if extension else MATTAR_DAW_1STEP)
        self.chain: List[StoredTransition] = []
        self.last_choice: str = ""  # "one_step" or "extension": diagnostics

    def begin(self, memory: TransitionMemory, episode: int) -> None:
        if len(memory) == 0:
            raise ValueError(f"{self.name} replay needs at least one stored transition")
        self.chain = []

    @staticmethod
    def _distinct(memory: TransitionMemory) -> List[StoredTransition]:
        """The distinct (s, s', r, terminal) transitions in memory, each by its latest occurrence, oldest first."""
        latest: Dict[Tuple[float, float, float, float, float, bool], StoredTransition] = {}
        for t in memory.all():  # oldest first: later duplicates overwrite earlier ones
            latest[(t.x, t.y, t.x_next, t.y_next, t.reward, t.terminal)] = t
        return list(latest.values())

    def _evb(self, state: int, q_old: Mapping[str, float], action: str, delta: float) -> float:
        gain = gain_q(self.model, q_old, action, self.model.learning_rate() * delta)
        return self.model.need(self.model.acting_state(), state) * max(gain, self.gain_floor)

    def _one_step(self, t: StoredTransition, learner: QLearner) -> float:
        action = self.model.action_of(t.x, t.y, t.x_next, t.y_next)
        return self._evb(self.model.state_index(t.x, t.y), learner.q(t.x, t.y), action, t.td_error(learner))

    def _extensions(self, distinct: Sequence[StoredTransition], learner: QLearner,
                    chain: Optional[Sequence[StoredTransition]] = None) -> List[Tuple[float, ExtendedBackup]]:
        """The extension candidates of ``chain`` (the rule's own when None): one per stored transition that continues it."""
        chain = self.chain if chain is None else chain
        if not self.extension or not chain or chain[-1].terminal:
            return []
        first, last = chain[0], chain[-1]
        action = self.model.action_of(first.x, first.y, first.x_next, first.y_next)
        q_first = learner.q(first.x, first.y)
        gamma = self.model.discount()
        out: List[Tuple[float, ExtendedBackup]] = []
        for t in distinct:
            if (t.x, t.y) != (last.x_next, last.y_next):
                continue
            target, disc = 0.0, 1.0
            for e in (*chain, t):
                target += disc * e.reward
                disc *= gamma
            if not t.terminal:
                target += disc * learner.value(t.x_next, t.y_next)
            delta = target - q_first[action]
            evb = self._evb(self.model.state_index(first.x, first.y), q_first, action, delta)
            out.append((evb, ExtendedBackup(first, t, action, target, len(chain) + 1)))
        return out

    def _seed(self, distinct: Sequence[StoredTransition]) -> Optional[StoredTransition]:
        """The acting state's most recent outgoing stored transition: the chain the rule's first forward step would build."""
        acting = self.model.acting_state()
        own = [t for t in distinct if self.model.state_index(t.x, t.y) == acting]
        return own[-1] if own else None  # distinct is oldest first by latest occurrence

    def _ranked(self, memory: TransitionMemory, learner: QLearner) -> List[Tuple[float, int, int, Candidate]]:
        """(EVB, is_extension, recency, candidate), the best last: EVB, then extensions over one-step backups, then recency."""
        distinct = self._distinct(memory)
        scored: List[Tuple[float, int, int, Candidate]] = [(self._one_step(t, learner), 0, i, t) for i, t in enumerate(distinct)]
        scored.extend((evb, 1, len(distinct) + i, ext) for i, (evb, ext) in enumerate(self._extensions(distinct, learner)))
        scored.sort(key=lambda item: (item[0], item[1], item[2]))
        return scored

    def choose(self, memory: TransitionMemory, learner: Learner, stream: RNGStream, k: int) -> Candidate:  # type: ignore[override]
        best = self._ranked(memory, learner)[-1][3]  # type: ignore[arg-type]
        if isinstance(best, ExtendedBackup):
            self.chain.append(best.appended)
            self.last_choice = "extension"
        else:
            self.chain = [best]
            self.last_choice = "one_step"
        return best

    def span(self, memory: TransitionMemory) -> int:
        return len(self._distinct(memory))

    def priority(self, memory: TransitionMemory, learner: Learner, k: int) -> float:
        """The largest EVB among the candidates (what the thresholded mode compares with theta x scale); under
        ``priority_mode="seeded"`` with an empty chain, also among the extensions of the seeded chain (module notes)."""
        best = self._ranked(memory, learner)[-1][0]  # type: ignore[arg-type]
        if self.priority_mode == "seeded" and self.extension and not self.chain:
            distinct = self._distinct(memory)
            seed = self._seed(distinct)
            if seed is not None:
                for evb, _ in self._extensions(distinct, learner, [seed]):  # type: ignore[arg-type]
                    best = max(best, evb)
        return best


__all__ = ["DEFAULT_GAIN_FLOOR", "ExtendedBackup", "MATTAR_DAW", "MATTAR_DAW_1STEP", "MATTAR_DAW_CONDITIONS", "PRIORITY_MODES",
           "MattarDawReplay", "QLearner", "QReplayModel", "gain_q"]
