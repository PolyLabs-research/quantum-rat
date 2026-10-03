"""Value learners for the research profile: tabular TD(0) and linear TD(lambda)
over Gaussian place features (docs/research_plan.md section 4, M1; docs/value_learners.md).

Both learners estimate V(place) = the expected discounted return from a place,
learned by temporal-difference updates from transitions ``(x, y) -> (x', y')``
with the reward received on arrival. A transition into a terminal place
bootstraps on 0 (``V(terminal) = 0``), so a terminal reward of 1.0 gives
V = gamma^d at d zero-reward steps before it, and never more than 1/(1 - gamma)
anywhere, which is the acceptance the chain protocol below checks.

``ValueFunction`` is the interface the engine will call once the place
population exists (M2b). ``brain.systems.value_memory.ValueMemory`` (tabular
TD(0) over 0.5-unit bins, with the legacy generalisation kernel and dwell
extinction) will be adapted to it then; until then the engine keeps using
``ValueMemory`` directly, and ``TabularTD0`` here is the kernel-free rule it
reduces to at ``generalization_radius = 0``.

numpy is used elementwise only (multiply, ``exp``, ``maximum``) and summed with
``numpy.sum`` (pairwise summation); no ``dot`` or other BLAS product feeds a
value, so the numbers are bit-identical across thread counts and kernels
(docs/determinism.md, "The numpy rules"). float64 throughout; no RNG is drawn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence, Tuple, runtime_checkable

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads (docs/determinism.md rule 2)
import numpy as np

Cell = Tuple[int, int]


@runtime_checkable
class ValueFunction(Protocol):
    """A learned value function over places.

    ``value(x, y)`` reads V at a position; ``update`` applies one TD backup for
    the transition ``(x, y) -> (x_next, y_next)`` with the reward received on
    arrival (``terminal`` means the arrival place has V = 0 by convention and
    ends the episode) and returns the TD error; ``reset_episode`` marks an
    episode boundary (traces are cleared, nothing links across it);
    ``parameters`` returns a JSON-serialisable dict for the run manifest,
    including ``learning_rate`` and ``discount``.
    """

    def value(self, x: float, y: float) -> float: ...

    def update(self, x: float, y: float, reward: float, x_next: float, y_next: float, terminal: bool) -> float: ...

    def reset_episode(self) -> None: ...

    def parameters(self) -> Dict[str, object]: ...


def _check_finite_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be a finite positive number, not {value!r}")


def _check_rates(learning_rate: float, discount: float) -> None:
    """A finite ``learning_rate > 0`` and a finite ``discount`` in [0, 1]: the
    bound V <= max reward / (1 - discount) and the TD fixed point need both."""
    _check_finite_positive("learning_rate", learning_rate)
    if not math.isfinite(discount) or not 0.0 <= discount <= 1.0:
        raise ValueError(f"discount must be a finite number in [0, 1], not {discount!r}")


class TabularTD0:
    """TD(0) over floor-binned cells, with V(terminal) = 0.

    The same arithmetic as ``ValueMemory`` at ``generalization_radius = 0`` and
    ``dwell_extinction = 0``: a position is binned to
    ``(floor(x / bin_size), floor(y / bin_size))`` (``SpatialSystem.bins_at``),
    unvisited cells read 0, and the backup is ``V(s) <- V(s) + lr * (target - V(s))``
    with ``target = reward + discount * V(s')`` (``reward`` alone when ``s'`` is
    terminal). ``ValueMemory._td_update`` writes ``v + weight * lr * (target - v)``
    with ``weight = falloff ** 0 = 1.0`` at radius 0 and a target of
    ``reward - 0.0 + discount * V(s')``, so the two agree bit for bit on the same
    transitions in the same order (tests/brain/test_value_learners.py). What
    ``ValueMemory`` adds is the trajectory log that replay reads and the kernel;
    what this class adds is the explicit terminal flag.
    """

    def __init__(self, bin_size: float = 0.5, learning_rate: float = 0.2, discount: float = 0.9) -> None:
        _check_finite_positive("bin_size", bin_size)
        _check_rates(learning_rate, discount)
        self.bin_size = float(bin_size)
        self.lr = float(learning_rate)
        self.gamma = float(discount)
        self.values: Dict[Cell, float] = {}

    def cell(self, x: float, y: float) -> Cell:
        return math.floor(x / self.bin_size), math.floor(y / self.bin_size)

    def value(self, x: float, y: float) -> float:
        return self.values.get(self.cell(x, y), 0.0)

    def update(self, x: float, y: float, reward: float, x_next: float, y_next: float, terminal: bool) -> float:
        cell = self.cell(x, y)
        v = self.values.get(cell, 0.0)
        if terminal:
            target = reward
        else:
            target = reward + self.gamma * self.values.get(self.cell(x_next, y_next), 0.0)
        delta = target - v
        self.values[cell] = v + self.lr * delta
        return delta

    def reset_episode(self) -> None:
        """Nothing is carried between transitions, so a boundary needs no action."""

    def parameters(self) -> Dict[str, object]:
        return {
            "learner": "tabular_td0",
            "bin_size": self.bin_size,
            "learning_rate": self.lr,
            "discount": self.gamma,
        }


class GaussianPlaceFeatures:
    """Gaussian place-cell features phi(x, y) over fixed centres.

    ``phi_j(p) = exp(-|p - c_j|^2 / (2 width^2))``, with the centres and the width
    in the same position units. With ``normalise=True`` (the default) the vector
    is divided by its sum, so the features form a partition of unity:
    ``phi_j >= 0`` and ``sum_j phi_j = 1`` at every position. A linear value
    ``V = sum_j w_j phi_j`` is then a convex combination of the weights, so
    ``min(w) <= V <= max(w)`` everywhere, including between centres and at the
    terminal. Without it the sum of the features grows with the width (about
    2.5 at one cell of width on the chain), the bootstrap target
    ``discount * V(s')`` is scaled by that factor, and once ``discount * sum(phi)``
    exceeds 1 the TD iteration has no finite fixed point; that is why the
    research profile's "V <= 1/(1 - discount)" acceptance is stated for
    normalised features (docs/value_learners.md).

    A position where every feature underflows to 0 (more than about 38.6
    widths from the nearest centre, where ``exp`` of the squared distance is
    below the smallest float64 subnormal; 19.3 units at a width of 0.5) reads
    V = 0 and receives no update; the convex-combination bound holds wherever
    any feature is nonzero (docs/value_learners.md).

    Computed with elementwise numpy and ``numpy.sum`` only (docs/determinism.md).
    """

    def __init__(self, centres: Sequence[Tuple[float, float]], width: float, normalise: bool = True) -> None:
        c = np.asarray(centres, dtype=np.float64).reshape(-1, 2)
        if c.shape[0] == 0:
            raise ValueError("at least one centre is needed")
        if not np.all(np.isfinite(c)):
            raise ValueError("every centre must be finite")
        _check_finite_positive("width", width)
        self.cx = np.ascontiguousarray(c[:, 0])
        self.cy = np.ascontiguousarray(c[:, 1])
        self.width = float(width)
        self.normalise = bool(normalise)
        self._two_width_sq = 2.0 * self.width * self.width

    @classmethod
    def grid(
        cls,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        spacing: float,
        width: float,
        normalise: bool = True,
    ) -> "GaussianPlaceFeatures":
        """Centres at the bin centres of a regular grid of pitch ``spacing`` over
        the rectangle ``[x_min, x_max] x [y_min, y_max]``, in a fixed order
        (rows of increasing y, x increasing within a row)."""
        if spacing <= 0.0:
            raise ValueError("spacing must be positive")
        nx = int(round((x_max - x_min) / spacing))
        ny = int(round((y_max - y_min) / spacing))
        if nx < 1 or ny < 1:
            raise ValueError("the rectangle must hold at least one bin in each direction")
        centres = [
            (x_min + spacing * (ix + 0.5), y_min + spacing * (iy + 0.5)) for iy in range(ny) for ix in range(nx)
        ]
        return cls(centres, width, normalise)

    @property
    def size(self) -> int:
        return int(self.cx.shape[0])

    def centres(self) -> List[Tuple[float, float]]:
        return [(float(x), float(y)) for x, y in zip(self.cx, self.cy)]

    def __call__(self, x: float, y: float) -> np.ndarray:
        dx = self.cx - x
        dy = self.cy - y
        phi = np.exp(-(dx * dx + dy * dy) / self._two_width_sq)
        if self.normalise:
            total = float(np.sum(phi))
            if total > 0.0:
                phi = phi / total
        return phi

    def parameters(self) -> Dict[str, object]:
        return {
            "features": "gaussian_place",
            "n": self.size,
            "width": self.width,
            "normalise": self.normalise,
            "x_range": [float(np.min(self.cx)), float(np.max(self.cx))],
            "y_range": [float(np.min(self.cy)), float(np.max(self.cy))],
        }


class LinearTDLambda:
    """Linear TD(lambda) with eligibility traces: V(p) = sum_j w_j phi_j(p).

    One backup (Sutton & Barto 2018, ch. 12): with ``delta = reward + discount *
    V(s') - V(s)`` (``reward - V(s)`` into a terminal), the trace is first
    decayed and fed with the current features, ``e <- discount * lam * e + phi(s)``
    (accumulating) or ``e <- max(discount * lam * e, phi(s))`` elementwise
    (replacing; the binary-feature rule applied per component), then
    ``w <- w + lr * delta * e``. Traces start at zero in every episode:
    ``reset_episode`` clears them, and so does a terminal transition. With
    ``lam = 0`` both trace kinds reduce to TD(0), ``w <- w + lr * delta * phi(s)``,
    and with one-hot features that is ``TabularTD0``.

    With normalised features V lies between the smallest and the largest
    weight (``GaussianPlaceFeatures``). Tsitsiklis & Van Roy 1997 give the
    convergence of linear TD(lambda) under on-policy sampling to a fixed point
    whose error against the true V is bounded by the best representable
    approximation; on the chain that bias is measured per width in
    docs/value_learners.md.

    The constructor checks the parameters (a finite ``learning_rate > 0``, a
    finite ``discount`` in [0, 1], ``lam`` in [0, 1]); it does not bound the
    learning rate against the features, so a rate too large for them (2.5 on
    the chain at 0.5 cell) diverges to non-finite weights without an error,
    which is left to the caller: ``run_chain`` stops at the first non-finite
    pass, and the engine's wiring in M2b checks the TD error it is returned.
    """

    TRACES = ("replacing", "accumulating")

    def __init__(
        self,
        features: GaussianPlaceFeatures,
        learning_rate: float = 0.2,
        discount: float = 0.9,
        lam: float = 0.0,
        traces: str = "replacing",
    ) -> None:
        if traces not in self.TRACES:
            raise ValueError(f"traces must be one of {self.TRACES}, not {traces!r}")
        if not 0.0 <= lam <= 1.0:
            raise ValueError("lam must lie in [0, 1]")
        _check_rates(learning_rate, discount)
        self.features = features
        self.lr = float(learning_rate)
        self.gamma = float(discount)
        self.lam = float(lam)
        self.traces = traces
        self.weights = np.zeros(features.size, dtype=np.float64)
        self.trace = np.zeros(features.size, dtype=np.float64)

    def value(self, x: float, y: float) -> float:
        return float(np.sum(self.weights * self.features(x, y)))

    def update(self, x: float, y: float, reward: float, x_next: float, y_next: float, terminal: bool) -> float:
        phi = self.features(x, y)
        v = float(np.sum(self.weights * phi))
        if terminal:
            target = reward
        else:
            target = reward + self.gamma * float(np.sum(self.weights * self.features(x_next, y_next)))
        delta = target - v
        decay = self.gamma * self.lam
        if self.traces == "accumulating":
            self.trace = decay * self.trace + phi
        else:
            self.trace = np.maximum(decay * self.trace, phi)
        self.weights = self.weights + (self.lr * delta) * self.trace
        if terminal:
            self.reset_episode()
        return delta

    def reset_episode(self) -> None:
        self.trace = np.zeros(self.features.size, dtype=np.float64)

    def parameters(self) -> Dict[str, object]:
        return {
            "learner": "linear_td_lambda",
            "learning_rate": self.lr,
            "discount": self.gamma,
            "lam": self.lam,
            "traces": self.traces,
            "features": self.features.parameters(),
        }


# --- The chain protocol -----------------------------------------------------
#
# 12 cells along x at bin 0.5 (centres 0.25 ... 5.75, y = 0.25), start at cell 0,
# one cell per transition, reward 1.0 on arriving at cell 11, which is terminal.
# The same construction as tools/probes/kernel_value_inflation.py, with the
# terminal flag explicit. d = 10 ... 0 counts the zero-reward steps from a cell
# to the rewarded step, so V(d) = discount^d (cell 10 is d = 0, V = 1.0); the goal
# cell itself bootstraps as 0, the probe's trailing 0 in [0.3487, ..., 0.9, 1, 0].

CHAIN_CELLS = 12
CHAIN_BIN = 0.5
CHAIN_REWARD = 1.0


def chain_positions(bin_size: float = CHAIN_BIN, cells: int = CHAIN_CELLS) -> List[Tuple[float, float]]:
    """The cell centres of the chain, cell 0 first."""
    return [(bin_size * (i + 0.5), bin_size * 0.5) for i in range(cells)]


def chain_targets(discount: float, cells: int = CHAIN_CELLS) -> List[float]:
    """discount^d for d = cells - 2 ... 0: the exact V of cells 0 ... cells - 2."""
    return [discount ** (cells - 2 - i) for i in range(cells - 1)]


def chain_features(
    width_cells: float, normalise: bool = True, bin_size: float = CHAIN_BIN, cells: int = CHAIN_CELLS
) -> GaussianPlaceFeatures:
    """Gaussian features centred on the chain's cells; ``width_cells`` is in cells
    (``width = width_cells * bin_size`` in position units)."""
    return GaussianPlaceFeatures.grid(
        0.0, bin_size * cells, 0.0, bin_size, spacing=bin_size, width=width_cells * bin_size, normalise=normalise
    )


@dataclass(frozen=True)
class ChainResult:
    values: List[float]  # V(d) for d = 10 ... 0 (cells 0 ... 10)
    targets: List[float]  # discount^d
    goal_value: float  # what the learner reads at the terminal cell (0 for the tabular rule)
    passes: int  # passes actually run
    converged: bool  # the per-pass change fell below tol (False when tol is None or the cap was hit)

    @property
    def errors(self) -> List[float]:
        return [v - t for v, t in zip(self.values, self.targets)]

    @property
    def max_error(self) -> float:
        return max(abs(e) for e in self.errors)

    @property
    def max_value(self) -> float:
        return max(self.values)

    @property
    def monotone(self) -> bool:
        """V(d) non-increasing in d, i.e. non-decreasing along the chain toward the goal."""
        return all(a <= b for a, b in zip(self.values, self.values[1:]))


def run_chain(
    learner: ValueFunction,
    passes: int,
    tol: Optional[float] = None,
    bin_size: float = CHAIN_BIN,
    cells: int = CHAIN_CELLS,
    reward: float = CHAIN_REWARD,
) -> ChainResult:
    """Run forward episodes along the chain and read V at every cell.

    Each pass is one episode: ``reset_episode``, then the ``cells - 1``
    transitions from cell 0 to the terminal cell, in order. With ``tol`` set the
    run stops after the first pass whose largest change in V over the
    non-terminal cells is below ``tol`` (or when a value stops being finite);
    ``passes`` is the cap either way.
    """
    positions = chain_positions(bin_size, cells)
    discount = float(learner.parameters()["discount"])
    targets = chain_targets(discount, cells)
    last = cells - 1
    previous: Optional[List[float]] = None
    current: List[float] = [learner.value(x, y) for x, y in positions[:-1]]
    run = 0
    converged = False
    for run in range(1, passes + 1):
        learner.reset_episode()
        for i in range(last):
            x, y = positions[i]
            x_next, y_next = positions[i + 1]
            terminal = i + 1 == last
            learner.update(x, y, reward if terminal else 0.0, x_next, y_next, terminal)
        current = [learner.value(x, y) for x, y in positions[:-1]]
        if not all(math.isfinite(v) for v in current):
            break
        if tol is not None and previous is not None:
            if max(abs(a - b) for a, b in zip(current, previous)) < tol:
                converged = True
                break
        previous = current
    goal_x, goal_y = positions[last]
    return ChainResult(
        values=current,
        targets=targets,
        goal_value=learner.value(goal_x, goal_y),
        passes=run,
        converged=converged,
    )


__all__ = [
    "CHAIN_BIN",
    "CHAIN_CELLS",
    "CHAIN_REWARD",
    "Cell",
    "ChainResult",
    "GaussianPlaceFeatures",
    "LinearTDLambda",
    "TabularTD0",
    "ValueFunction",
    "chain_features",
    "chain_positions",
    "chain_targets",
    "run_chain",
]
