"""A learned action value over the place code (M3 step 3; docs/prereg/m3_step3.md).

Q(phi, a) = w_a . phi for the three movement actions (``ACTIONS``: FORWARD, TURN_LEFT, TURN_RIGHT), phi the place
population's rates at the agent's estimate normalised to sum 1 (a partition of unity, as the SR's features are), so
each Q is a convex combination of its weights wherever any feature is nonzero (docs/value_learners.md). REST keeps its
reflex score: resting has no spatial consequence to learn.

**Experience** (``update``): every tick's transition (phi, a, r, phi') with Q-learning's target r + gamma max_a' Q(phi',
a') (r alone into a terminal) and eligibility traces per action, replacing (e_a <- max(gamma lam e_a, phi) for the
action taken, gamma lam e_a for the others; Sutton & Barto 2018 ch. 12, the binary-feature rule applied per
component) or accumulating (e_a <- gamma lam e_a + phi); then w_a <- w_a + lr delta e_a for every a. The traces of
the other actions carry the error too (naive Q(lambda), Sutton & Barto §12.10: Watkins's cut at an exploratory action
is not applied, the policy here being a softmax over scores the value is only one term of). Traces start at zero in
every episode and clear at a terminal. **Replay** (``update_target``): one backup of Q(phi, a) toward a target without
traces, as ``TabularQ.update_target`` does for Mattar & Daw's backups.

:class:`PlaceActionLearner` binds a ``LinearQ`` to a feature map phi(x, y): the learner the replay rules back up by
position and action (``StoredTransition.action``; ``brain.systems.replay_rules``) and the ``QLearner`` the gain x
need rule reads (``brain.systems.replay_mattar_daw``). Elementwise numpy and ``numpy.sum`` only, no BLAS product
(docs/determinism.md).
"""

from __future__ import annotations

import math
from typing import Callable, Dict, Sequence, Tuple

import numpy as np

ACTIONS: Tuple[str, ...] = ("FORWARD", "TURN_LEFT", "TURN_RIGHT")
TRACES = ("replacing", "accumulating")


class LinearQ:
    """Q(phi, a) = w_a . phi, learned by Q-learning with eligibility traces and by replay backups."""

    def __init__(self, n: int, learning_rate: float = 0.1, discount: float = 0.98, lam: float = 0.9,
                 traces: str = "replacing", actions: Sequence[str] = ACTIONS) -> None:
        if n < 1:
            raise ValueError("n must be at least 1")
        if not (math.isfinite(learning_rate) and learning_rate > 0.0):
            raise ValueError("learning_rate must be a positive finite number")
        if not (math.isfinite(discount) and 0.0 <= discount < 1.0):
            raise ValueError("discount must be in [0, 1)")
        if not 0.0 <= lam <= 1.0:
            raise ValueError("lam must lie in [0, 1]")
        if traces not in TRACES:
            raise ValueError(f"traces must be one of {TRACES}, got {traces!r}")
        if len(actions) < 1 or len(set(actions)) != len(actions):
            raise ValueError("actions must be a non-empty sequence of distinct names")
        self.n = int(n)
        self.lr = float(learning_rate)
        self.gamma = float(discount)
        self.lam = float(lam)
        self.traces = traces
        self.actions: Tuple[str, ...] = tuple(actions)
        self.w: Dict[str, np.ndarray] = {a: np.zeros(self.n, dtype=np.float64) for a in self.actions}
        self.e: Dict[str, np.ndarray] = {a: np.zeros(self.n, dtype=np.float64) for a in self.actions}
        self.updates = 0
        self.backups = 0

    def _check(self, action: str) -> None:
        if action not in self.w:
            raise ValueError(f"unknown action {action!r}; one of {self.actions}")

    def q(self, phi: np.ndarray) -> Dict[str, float]:
        """Q(phi, .) as a fresh dict in ``actions`` order."""
        return {a: float(np.sum(self.w[a] * phi)) for a in self.actions}

    def value(self, phi: np.ndarray) -> float:
        return max(self.q(phi).values())

    def advantages(self, phi: np.ndarray) -> Dict[str, float]:
        """Q(phi, a) less the mean over the actions: what the steering reads (which action, not how good here)."""
        q = self.q(phi)
        mean = math.fsum(q.values()) / len(q)
        return {a: v - mean for a, v in q.items()}

    def target(self, reward: float, phi_next: np.ndarray, terminal: bool) -> float:
        return reward if terminal else reward + self.gamma * self.value(phi_next)

    def td_error(self, phi: np.ndarray, action: str, reward: float, phi_next: np.ndarray, terminal: bool) -> float:
        self._check(action)
        return self.target(reward, phi_next, terminal) - self.q(phi)[action]

    def update(self, phi: np.ndarray, action: str, reward: float, phi_next: np.ndarray, terminal: bool) -> float:
        """One experienced transition: the traces fed and decayed, every action's weights moved by the error."""
        delta = self.td_error(phi, action, reward, phi_next, terminal)
        decay = self.gamma * self.lam
        for a in self.actions:
            if a == action:
                self.e[a] = np.maximum(decay * self.e[a], phi) if self.traces == "replacing" else decay * self.e[a] + phi
            else:
                self.e[a] = decay * self.e[a]
            self.w[a] = self.w[a] + (self.lr * delta) * self.e[a]
        self.updates += 1
        if terminal:
            self.reset_episode()
        return delta

    def update_target(self, phi: np.ndarray, action: str, target: float) -> float:
        """A replay backup: Q(phi, action) one step toward ``target``, no traces; returns the error before it."""
        self._check(action)
        delta = target - self.q(phi)[action]
        self.w[action] = self.w[action] + (self.lr * delta) * phi
        self.backups += 1
        return delta

    def reset_episode(self) -> None:
        for a in self.actions:
            self.e[a] = np.zeros(self.n, dtype=np.float64)

    def weight_norm(self) -> float:
        """The largest |w| over every action and feature: the scale of what has been learned."""
        return max(float(np.max(np.abs(self.w[a]))) for a in self.actions)

    def parameters(self) -> Dict[str, object]:
        return {"learner": "linear_q", "n": self.n, "learning_rate": self.lr, "discount": self.gamma, "lam": self.lam,
                "traces": self.traces, "actions": list(self.actions), "updates": self.updates, "backups": self.backups}


class PlaceActionLearner:
    """A ``LinearQ`` bound to phi(x, y): backed up by position and action (the replay rules) and read as Q(x, y, .)."""

    def __init__(self, learner: LinearQ, features: Callable[[float, float], np.ndarray]) -> None:
        self.learner = learner
        self.features = features

    def q(self, x: float, y: float) -> Dict[str, float]:
        return self.learner.q(self.features(x, y))

    def value(self, x: float, y: float) -> float:
        return self.learner.value(self.features(x, y))

    def update_target(self, x: float, y: float, action: str, target: float) -> float:
        return self.learner.update_target(self.features(x, y), action, target)

    def update_action(self, x: float, y: float, action: str, reward: float, x_next: float, y_next: float, terminal: bool) -> float:
        """A stored transition's backup (a replay): one step toward its Q-learning target, no traces."""
        target = self.learner.target(reward, self.features(x_next, y_next), terminal)
        return self.update_target(x, y, action, target)

    def td_error_action(self, x: float, y: float, action: str, reward: float, x_next: float, y_next: float, terminal: bool) -> float:
        return self.learner.td_error(self.features(x, y), action, reward, self.features(x_next, y_next), terminal)

    def update(self, x: float, y: float, reward: float, x_next: float, y_next: float, terminal: bool) -> float:
        raise TypeError("an action-value learner backs up a transition by its action: StoredTransition.action is empty")

    def td_error(self, x: float, y: float, reward: float, x_next: float, y_next: float, terminal: bool) -> float:
        raise TypeError("an action-value learner reads a transition's error by its action: StoredTransition.action is empty")

    def reset_episode(self) -> None:
        self.learner.reset_episode()

    def parameters(self) -> Dict[str, object]:
        return self.learner.parameters()


__all__ = ["ACTIONS", "LinearQ", "PlaceActionLearner", "TRACES"]
