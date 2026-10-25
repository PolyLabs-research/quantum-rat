"""M2a, first pass: tabular replay on a linear track, four conditions, paired over seeds.

    python3 -m experiments.linear_track_replay --workers 4            # the fixed evaluation: seeds 1-30, 4 conditions
    python3 -m experiments.linear_track_replay --seeds 3 --quick --out /tmp/track   # the smoke test's run
    python3 -m experiments.linear_track_replay --conditions none --seeds 3 --out /tmp/pilot   # a pilot (one condition)

The result is docs/m2a_linear_track.md (docs/decisions.md entry G26; docs/research_plan.md
section 4, M2a, of which this is the first subset: four of the nine rules, fixed-budget
mode only, no reward-change schedule, no console panel). A partial run (``--quick``,
fewer seeds or laps, a subset of the conditions) refuses the committed output directory:
give it ``--out``.

The specification below was fixed before the evaluation ran; the pilot that set the two
policy parameters marked (*) is described in docs/m2a_linear_track.md and used the
no-replay condition only.

Track and state
---------------
A linear track of ``n_bins`` = 40 cells of ``bin_size`` = 0.5 unit (20 units = 2.0 m,
docs/units.md; the plan's 10 x 0.5 box), cell ``i`` centred at ``x = 0.5 i + 0.25``. The
tabular state is ``(i, h, g)``: the cell, the heading ``h`` (+1 facing east, toward
increasing ``i``; -1 west) and the current goal end ``g`` (east or west), which the agent
knows (the end it has been running toward; the plan's "binary heading" plus the task
phase, so a state that is a goal in one lap is never an ordinary state in the next). The
state is the body's true cell: this is the plan's *tabular, oracle-state* arm, against
which M3's embodied (noisy path-integration) arm is to be compared; odometry noise plays
no part here. The state is handed to the existing tabular learner
(``brain.systems.value_learners.TabularTD0``, 0.5-unit bins) as a position: ``x`` as
above, ``y`` = +0.25 / -0.25 for ``h`` = +1 / -1, plus 1.0 when the goal is west, so the
four (``h``, ``g``) combinations fall in four distinct ``y`` cells and the table has
4 x 40 = 160 states.

Actions, laps, reward
---------------------
Two actions: FORWARD moves one cell in the heading direction (a step into the end wall
leaves the cell unchanged and counts as a step), TURN flips the heading in place. A lap is
an episode: it starts at the start end facing the goal end and ends when the agent enters
the goal cell, where a *consume* transition delivers the reward ``r`` = 1.0 (the same at
both ends; no reward-change schedule in this pass) as a terminal transition from the goal
state (V(terminal) = 0), so V(goal state) learns the reward about to be consumed, the
one-step lookahead below sees it, and the chain protocol of M1 is reproduced with cell 10
relabelled "goal" (docs/value_learners.md). After a rewarded lap the goal flips to the
other end and the next lap starts from the goal cell just reached, turned to face the new
goal (the turn-around is part of the inter-lap pause, not a decision). A lap that reaches
``lap_cap`` = 2,000 steps without reward ends unrewarded: the agent is put back at that
lap's start end facing the same goal, nothing is replayed (no reward, no trigger) and the
lap counts as capped. ``laps`` = 40 laps per seed; reset_episode at every lap end.

Online learning and exploration
-------------------------------
TD(0), learning rate 0.2 (M1's), discount 0.95 (so V stays above 0.1 along a 40-cell
lap: 0.95^39 = 0.135), V initialised at 0, one backup per step and one for the consume.
The policy is a softmax at temperature 0.1 (the research profile's) over two scores,
``FORWARD: prior + value_gain * V(s'_FORWARD)`` and ``TURN: value_gain * V(s'_TURN)``,
where ``s'`` is the state the action leads to (the track's transitions are known and
deterministic; this is the engine's own steering read, V one step ahead) and the
sampler is ``brain.systems.basal_ganglia.softmax_sample``, one ``random()`` per step on
the ``track_action`` stream. (*) ``prior`` = 0.1 ln 4 = 0.1386 makes an untrained agent
(V = 0) turn with probability 0.2 per step, a persistent random walk; (*) ``value_gain``
= 10 makes a value difference of 0.01 one temperature unit, so the learned gradient can
carry the far end of the track (0.95^39 (1 - 0.95^2) = 0.013 between facing toward and
away at 39 cells).

Replay
------
Four conditions, identical in everything above and in their first lap (no replay has
happened yet): ``none`` (no replay); ``uniform`` (one stored transition drawn uniformly
with replacement per backup); ``reverse_trajectory`` (the lap just completed, newest
transition first, cycling if it is shorter than the budget); ``prioritised_td`` (one
stored transition per backup drawn in proportion to |TD error| + 1e-6, the error
recomputed under the current values before every draw). Trigger: the reward-consumption
pause at the end of every rewarded lap, once per lap. Budget: exactly
``backups_per_trigger`` = 20 TD backups per trigger in each replay condition (so the
three differ in content, not in the number of learning updates); ``none`` makes none.
Memory: the newest ``memory_capacity`` = 2,000 stored transitions (about ten
learned laps), every one eligible for uniform and prioritised replay, each stored with
its own successor and terminal flag so no backup links two laps (the reverse rule reads
the just-completed lap only). Randomness: the ``replay`` stream, separate from
``track_action``; the environment draws nothing. Every replay is one event
(``brain.systems.replay_events.ReplayEvent``: trigger ``reward``, the rule, the cells in
backup order, the direction by the plan's position-time slope sign against the lap's
travel direction, with the signed correlation ``sequence_r`` beside it).

Outcome, budget, seeds
----------------------
Primary outcome: the total number of steps (actions) over the 40 laps of a seed, lower
is faster learning; a capped lap contributes its 2,000. Each replay condition is compared
with ``none`` paired by seed (``analysis.stats.paired_effect``, BCa 95% interval on the
mean difference, 10,000 replicates, and Cliff's delta), and the three replay conditions
with each other. Secondary: the learning curve (steps per lap, mean over seeds with a BCa
interval per lap), reward collected and laps capped, online and replay update counts and
the replay budget as a fraction of the online one, the value table's RMS error against
the exact V (0.95^d for d actions to the goal under the optimal policy), and the replay
content: direction fractions, mean sequence_r, the share of backups from the lap just
completed, the mean distance of backed-up states from the goal and the share more than
0.5 m (10 cells) from it. Seeds 1-30, the seed the independent unit; laps and steps are
aggregated within a seed before any interval. ``analysis.stats.pseudo_replication_guard``
runs on every per-seed lap-length vector.

Outputs (``--out``, default docs/data/m2a/track): track_laps.csv (one row per
condition x seed x lap), track_per_seed.csv (the tidy table: condition, task, seed,
metric, value), track_summary.csv (per condition and metric: n, mean, BCa interval, IQM),
track_learning_curve.csv, track_effects.csv (the paired comparisons),
track_replay_events.jsonl.gz (one event per replay, with the cells, gzip-compressed) and track_manifest.json
(``metrics.manifest``: code revision, platform, numerical environment, the whole
configuration, seeds, dependency versions, the guard's verdicts and the run time).
Floats are written with six significant digits; a second run writes byte-identical
tables, whatever the worker count.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy (analysis.stats) loads
import numpy as np

from analysis.stats import PseudoReplicationError, bootstrap_ci, cliffs_delta, paired_effect, pseudo_replication_guard, tidy_table, summarise
from brain.systems.basal_ganglia import softmax_sample
from brain.systems.replay_events import RULE_NONE, RULE_PRIORITISED_TD, RULE_REVERSE_TRAJECTORY, RULE_UNIFORM, TRIGGER_PRE_RUN, TRIGGER_REWARD
from brain.systems.replay_gain_need import MODES as GAIN_NEED_MODES
from brain.systems.replay_gain_need import GainNeedReplay
from brain.systems.replay_rules import ReplayOutcome, ReplayRule, StoredTransition, TransitionMemory, make_rule, replay, replay_thresholded
from brain.systems.successor import TabularSR
from brain.systems.value_learners import TabularTD0
from core.rng import RNG
from metrics.manifest import build_manifest, finish_manifest, write_manifest

CONDITIONS: Tuple[str, ...] = (RULE_NONE, RULE_UNIFORM, RULE_REVERSE_TRAJECTORY, RULE_PRIORITISED_TD)
GAIN_NEED_CONDITIONS: Tuple[str, ...] = tuple(GAIN_NEED_MODES)  # gain_need, gain_only, need_only (M2a step 3)
ALL_CONDITIONS: Tuple[str, ...] = CONDITIONS + GAIN_NEED_CONDITIONS
ACTIONS: Tuple[str, ...] = ("FORWARD", "TURN")
BUDGET_MODES: Tuple[str, ...] = ("fixed", "thresholded")
EAST, WEST = 1, -1  # goal ends and headings: +1 toward increasing cells, -1 toward decreasing
TASK = "linear_track"
DEFAULT_SEEDS: Tuple[int, ...] = tuple(range(1, 31))
DEFAULT_OUT = Path("docs/data/m2a/track")
DEFAULT_N_BOOT = 10_000
REMOTE_CELLS = 10  # 0.5 m at 0.05 m per cell: the plan's "remote event" distance
ACTION_STREAM = "track_action"
REPLAY_STREAM = "replay"


@dataclass(frozen=True)
class TrackConfig:
    """The fixed specification (module docstring). ``profile`` labels the manifest."""

    profile: str = "m2a_tabular_track"
    n_bins: int = 40
    bin_size: float = 0.5
    laps: int = 40
    lap_cap: int = 2000
    reward_east: float = 1.0
    reward_west: float = 1.0
    discount: float = 0.95
    learning_rate: float = 0.2
    temperature: float = 0.1
    forward_prior: float = 0.1386294361119891  # 0.1 * ln 4: untrained P(TURN) = 0.2
    value_gain: float = 10.0
    backups_per_trigger: int = 20
    memory_capacity: int = 2000
    priority_epsilon: float = 1e-6
    # --- M2a step 2 (docs/prereg/rq1_track_tabular.md); the defaults are the fixed evaluation's protocol ---
    # Reward blocks: (laps, reward_east, reward_west) in order; empty means one block of ``laps`` laps at
    # ``reward_east`` / ``reward_west``. When given, the lap counts must sum to ``laps``.
    reward_blocks: Tuple[Tuple[int, float, float], ...] = ()
    # A second replay pause at the start of every lap (after the turn-around, before the first step).
    pre_run_pause: bool = False
    # "fixed": exactly backups_per_trigger backups per pause; "thresholded": replay while the rule's
    # priority exceeds ``threshold``, at most ``backup_cap`` per pause (brain.systems.replay_rules.replay_thresholded).
    budget_mode: str = "fixed"
    threshold: float = 0.02
    backup_cap: int = 100
    # --- M2a step 3 (docs/prereg/rq1_track_gain_need.md change 1): the trajectory rule's thresholded priority ---
    trajectory_priority: str = "next"  # "next" (step 2) or "remaining_max" (step 3)
    # The successor representation's learning rate (its discount is ``discount``); learned in every condition.
    sr_learning_rate: float = 0.2

    def __post_init__(self) -> None:
        if self.n_bins < 2 or self.laps < 1 or self.lap_cap < 1 or self.backups_per_trigger < 1 or self.memory_capacity < 1:
            raise ValueError("n_bins >= 2, laps, lap_cap, backups_per_trigger and memory_capacity >= 1")
        if not (self.bin_size > 0 and self.temperature > 0 and self.value_gain >= 0 and self.priority_epsilon > 0):
            raise ValueError("bin_size, temperature and priority_epsilon must be positive, value_gain >= 0")
        if self.budget_mode not in BUDGET_MODES:
            raise ValueError(f"budget_mode must be one of {BUDGET_MODES}, got {self.budget_mode!r}")
        if self.backup_cap < 1 or not (math.isfinite(self.threshold) and self.threshold >= 0.0):
            raise ValueError("backup_cap >= 1 and a finite non-negative threshold")
        if self.trajectory_priority not in ("next", "remaining_max"):
            raise ValueError("trajectory_priority must be 'next' or 'remaining_max'")
        if not (0.0 < self.sr_learning_rate <= 1.0):
            raise ValueError("sr_learning_rate in (0, 1]")
        if self.reward_blocks:
            blocks = tuple(tuple(b) for b in self.reward_blocks)
            object.__setattr__(self, "reward_blocks", blocks)  # lists from a manifest become tuples
            if any(len(b) != 3 or int(b[0]) < 1 for b in blocks):
                raise ValueError("each reward block is (laps >= 1, reward_east, reward_west)")
            if sum(int(b[0]) for b in blocks) != self.laps:
                raise ValueError(f"reward blocks cover {sum(int(b[0]) for b in blocks)} laps, laps is {self.laps}")

    def blocks(self) -> Tuple[Tuple[int, float, float], ...]:
        """The reward blocks in force: the declared ones, or one block over every lap."""
        if self.reward_blocks:
            return tuple((int(n), float(e), float(w)) for n, e, w in self.reward_blocks)
        return ((self.laps, self.reward_east, self.reward_west),)

    def block_of(self, lap: int) -> Tuple[int, float, float]:
        """(block index, reward_east, reward_west) for a 0-based lap index."""
        start = 0
        for index, (n, east, west) in enumerate(self.blocks()):
            if lap < start + n:
                return index, east, west
            start += n
        raise ValueError(f"lap {lap} is beyond the {self.laps} laps")

    def untrained_turn_probability(self) -> float:
        return 1.0 / (1.0 + math.exp(self.forward_prior / self.temperature))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class State:
    cell: int
    heading: int  # EAST or WEST
    goal: int  # EAST or WEST


class LinearTrack:
    """The deterministic track: states, transitions, goal test and the learner's coordinates.

    ``reward_east`` and ``reward_west`` are the rewards in force (the current block's; ``set_rewards``)."""

    def __init__(self, cfg: TrackConfig) -> None:
        self.cfg = cfg
        self.reward_east = cfg.reward_east
        self.reward_west = cfg.reward_west

    def set_rewards(self, east: float, west: float) -> None:
        self.reward_east = float(east)
        self.reward_west = float(west)

    def goal_cell(self, goal: int) -> int:
        return self.cfg.n_bins - 1 if goal == EAST else 0

    def start_state(self, goal: int) -> State:
        """At the far end from ``goal``, facing it."""
        return State(cell=self.goal_cell(-goal), heading=goal, goal=goal)

    def step(self, state: State, action: str) -> Tuple[State, bool]:
        """(next state, blocked): FORWARD moves one cell along the heading (blocked at a wall), TURN flips it."""
        if action == "FORWARD":
            nxt = state.cell + state.heading
            if 0 <= nxt < self.cfg.n_bins:
                return State(nxt, state.heading, state.goal), False
            return state, True
        if action == "TURN":
            return State(state.cell, -state.heading, state.goal), False
        raise ValueError(f"unknown action {action!r}")

    def at_goal(self, state: State) -> bool:
        return state.cell == self.goal_cell(state.goal)

    def reward(self, goal: int) -> float:
        return self.reward_east if goal == EAST else self.reward_west

    def position(self, state: State) -> Tuple[float, float]:
        """The learner's (x, y) for a state: x the cell centre, y encodes heading and goal in four distinct cells."""
        x = self.cfg.bin_size * (state.cell + 0.5)
        y = 0.25 if state.heading == EAST else -0.25
        if state.goal == WEST:
            y += 1.0
        return x, y

    def states(self) -> List[State]:
        return [State(i, h, g) for g in (EAST, WEST) for h in (EAST, WEST) for i in range(self.cfg.n_bins)]

    def cyclic_transitions(self) -> Dict[int, Dict[int, float]]:
        """The lap structure as a transition structure over state indices under a uniform-random policy: FORWARD
        and TURN with probability one half each from every non-goal state, and from a goal state the turn-around
        to the next lap's start with probability one (the consume and the placement, as the agent lives them).
        What the successor representation is initialised from (docs/prereg/rq1_track_gain_need.md, pre-run
        amendment); ``TabularSR.update`` then learns on experience."""
        out: Dict[int, Dict[int, float]] = {}
        for state in self.states():
            s = self.index(state)
            if self.at_goal(state) and state.heading == state.goal:
                out[s] = {self.index(self.start_state(-state.goal)): 1.0}
                continue
            succ: Dict[int, float] = {}
            for action in ACTIONS:
                nxt = self.index(self.step(state, action)[0])
                succ[nxt] = succ.get(nxt, 0.0) + 0.5
            out[s] = succ
        return out

    # --- integer state indices (the successor representation and the gain x need rule; M2a step 3) ---

    @property
    def n_states(self) -> int:
        return 4 * self.cfg.n_bins

    def index(self, state: State) -> int:
        """cell + n_bins * [0 east-facing, 1 west-facing] + 2 n_bins * [0 goal east, 1 goal west]: the order of ``states()``."""
        return state.cell + self.cfg.n_bins * ((0 if state.heading == EAST else 1) + 2 * (0 if state.goal == EAST else 1))

    def state_of(self, index: int) -> State:
        n = self.cfg.n_bins
        cell, rest = index % n, index // n
        return State(cell, EAST if rest % 2 == 0 else WEST, EAST if rest // 2 == 0 else WEST)

    def index_of_position(self, x: float, y: float) -> int:
        """The state index of a learner position (the inverse of ``position``)."""
        cell = int(math.floor(x / self.cfg.bin_size))
        row = int(math.floor(y / self.cfg.bin_size))
        heading, goal = {0: (EAST, EAST), -1: (WEST, EAST), 2: (EAST, WEST), 1: (WEST, WEST)}[row]
        return self.index(State(cell, heading, goal))

    def steps_to_goal(self, state: State) -> int:
        """Actions to the goal state under the optimal policy (FORWARD toward it, one TURN if facing away)."""
        distance = abs(state.cell - self.goal_cell(state.goal))
        facing = state.heading == state.goal
        return distance + (0 if facing or distance == 0 else 1)

    def optimal_value(self, state: State) -> float:
        """The exact V under the optimal policy: reward * discount^(actions to the goal state)."""
        return self.reward(state.goal) * self.cfg.discount ** self.steps_to_goal(state)


class TrackAgent:
    """The learner, its memory and the policy that reads it."""

    def __init__(self, cfg: TrackConfig, track: LinearTrack) -> None:
        self.cfg = cfg
        self.track = track
        self.learner = TabularTD0(bin_size=cfg.bin_size, learning_rate=cfg.learning_rate, discount=cfg.discount)
        self.memory = TransitionMemory(cfg.memory_capacity)
        self.visits: Dict[State, int] = {}  # how often each state was occupied (the lap starts and every step's arrival)
        # The tabular successor representation (need): initialised from the track's known cyclic structure under a
        # uniform-random policy (Mattar & Daw give their agent the transition structure), then learned online from
        # the same transitions in every condition; nothing reads it back into V or the policy, only the gain x need
        # rules read it (docs/prereg/rq1_track_gain_need.md, pre-run amendment).
        self.sr = TabularSR(track.n_states, learning_rate=cfg.sr_learning_rate, discount=cfg.discount)
        self.sr.initialise_from(track.cyclic_transitions())

    def visit(self, state: State) -> None:
        self.visits[state] = self.visits.get(state, 0) + 1

    def value(self, state: State) -> float:
        return self.learner.value(*self.track.position(state))

    def scores(self, state: State) -> Dict[str, float]:
        forward, _ = self.track.step(state, "FORWARD")
        turn, _ = self.track.step(state, "TURN")
        return {
            "FORWARD": self.cfg.forward_prior + self.cfg.value_gain * self.value(forward),
            "TURN": self.cfg.value_gain * self.value(turn),
        }

    def act(self, state: State, stream) -> str:
        return softmax_sample(self.scores(state), self.cfg.temperature, stream, order=ACTIONS)

    def store_and_learn(self, state: State, reward: float, nxt: State, terminal: bool, lap: int, index: int) -> float:
        x, y = self.track.position(state)
        x2, y2 = self.track.position(nxt)
        transition = StoredTransition(x, y, reward, x2, y2, terminal, lap, index, self.learner.cell(x, y))
        delta = transition.backup(self.learner)
        self.memory.append(transition)
        if not terminal:
            # The consume is terminal for V but not for occupancy: the goal state's successor in the SR is the
            # next lap's start, which ``place`` records (docs/prereg/rq1_track_gain_need.md, pre-run amendment).
            self.sr.update(self.track.index(state), self.track.index(nxt), False)
        return delta

    def place(self, from_state: Optional[State], to_state: State) -> None:
        """The protocol moved the agent (the turn-around after a reward, the return after a capped lap): one
        occupancy transition for the SR, so need spans the lap structure the agent actually lives in."""
        if from_state is not None:
            self.sr.update(self.track.index(from_state), self.track.index(to_state), False)

    def value_rmse(self) -> float:
        """RMS error of V against the exact V* over all states, each state weighted equally."""
        errors = [self.value(s) - self.track.optimal_value(s) for s in self.track.states()]
        return math.sqrt(math.fsum(e * e for e in errors) / len(errors))

    def value_rmse_visited(self) -> float:
        """RMS error of V against V* weighted by how often each state was occupied so far (G26 D: the
        unweighted error is dominated by the states the policy never reaches)."""
        total = sum(self.visits.values())
        if total == 0:
            return math.nan
        weighted = math.fsum(n * (self.value(s) - self.track.optimal_value(s)) ** 2 for s, n in self.visits.items())
        return math.sqrt(weighted / total)


class TrackModel:
    """The track's side of ``brain.systems.replay_gain_need.ReplayModel``: state indices, the one-step
    structure (predecessors and successors by action), the agent's policy read on given values, V by index,
    the successor representation's need, and the state the agent acts from next (``set_acting``)."""

    def __init__(self, cfg: TrackConfig, track: LinearTrack, agent: "TrackAgent") -> None:
        self.cfg = cfg
        self.track = track
        self.agent = agent
        self._successors: Dict[int, Dict[str, int]] = {}
        self._predecessors: Dict[int, List[Tuple[int, str]]] = {i: [] for i in range(track.n_states)}
        for state in track.states():
            p = track.index(state)
            succ = {action: track.index(track.step(state, action)[0]) for action in ACTIONS}
            self._successors[p] = succ
            for action, s in succ.items():
                self._predecessors[s].append((p, action))
        self._acting: int = track.index(track.start_state(EAST))

    def state_index(self, x: float, y: float) -> int:
        return self.track.index_of_position(x, y)

    def predecessors(self, state: int) -> Sequence[Tuple[int, str]]:
        return self._predecessors[state]

    def successors(self, state: int) -> Mapping[str, int]:
        return self._successors[state]

    def action_scores(self, state: int, value_of: Mapping[int, float]) -> Mapping[str, float]:
        succ = self._successors[state]
        return {"FORWARD": self.cfg.forward_prior + self.cfg.value_gain * value_of[succ["FORWARD"]],
                "TURN": self.cfg.value_gain * value_of[succ["TURN"]]}

    def policy(self, scores: Mapping[str, float]) -> Mapping[str, float]:
        """The softmax ``softmax_sample`` draws from, as probabilities (same weights, same order)."""
        top = max(scores.values())
        weights = {a: math.exp((scores[a] - top) / self.cfg.temperature) for a in ACTIONS}
        total = math.fsum(weights.values())
        return {a: w / total for a, w in weights.items()}

    def value_of_index(self, state: int) -> float:
        return self.agent.learner.value(*self.track.position(self.track.state_of(state)))

    @property
    def learning_rate(self) -> float:
        return self.cfg.learning_rate

    def need(self, from_state: int, to_state: int) -> float:
        return self.agent.sr.need(from_state, to_state)

    def acting_state(self) -> int:
        return self._acting

    def set_acting(self, state: State) -> None:
        self._acting = self.track.index(state)


@dataclass
class LapRecord:
    condition: str
    seed: int
    lap: int
    goal: str
    steps: int
    turns: int
    blocked: int
    rewarded: bool
    reward: float
    online_updates: int
    replay_backups: int
    replay_event: bool
    direction: str
    sequence_r: float
    replay_from_this_lap: float  # share of the backups that replayed the lap just completed
    replay_mean_goal_distance: float  # mean |cell - goal cell| of the backed-up start states, in cells
    replay_remote_share: float  # share of backups more than REMOTE_CELLS from the goal
    replay_mean_abs_delta: float
    online_mean_abs_delta: float
    value_rmse: float
    cumulative_steps: int
    value_rmse_visited: float = float("nan")  # visit-weighted (appended at step 1 of the M2a remainder)
    # --- M2a step 2 (appended; the fixed evaluation's columns above are unchanged) ---
    block: int = 0  # the reward block this lap ran in
    reward_east: float = 1.0  # the block's rewards
    reward_west: float = 1.0
    pre_run_backups: int = 0  # backups made at the pre-run pause that started this lap
    pre_run_event: bool = False
    pre_run_direction: str = ""
    pre_run_sequence_r: float = float("nan")
    # --- M2a step 3: the rule's priority read before each pause's first backup (what the thresholded mode tests) ---
    reward_priority_before: float = float("nan")
    pre_run_priority_before: float = float("nan")


@dataclass
class SeedRun:
    condition: str
    seed: int
    laps: List[LapRecord]
    events: List[Dict[str, Any]]
    first_lap_actions: Tuple[str, ...]  # for the identical-first-lap check across conditions

    def summary(self) -> Dict[str, float]:
        laps = self.laps
        n = len(laps)
        quarter = max(1, n // 4)
        rewarded = [r for r in laps if r.rewarded]
        events = [r for r in laps if r.replay_event]
        online = sum(r.online_updates for r in laps)
        replayed = sum(r.replay_backups for r in laps)
        out: Dict[str, float] = {
            "total_steps": float(sum(r.steps for r in laps)),
            "steps_first_quarter": float(sum(r.steps for r in laps[:quarter])),
            "steps_last_quarter": float(sum(r.steps for r in laps[-quarter:])),
            "steps_lap_1": float(laps[0].steps),
            "laps_rewarded": float(len(rewarded)),
            "laps_capped": float(n - len(rewarded)),
            "reward_total": float(math.fsum(r.reward for r in laps)),
            "online_updates": float(online),
            "replay_backups": float(replayed),
            "replay_events": float(len(events)),
            "replay_budget_fraction": (replayed / online) if online else 0.0,
            "pre_run_backups": float(sum(r.pre_run_backups for r in laps)),
            "pre_run_events": float(sum(r.pre_run_event for r in laps)),
            "final_value_rmse": laps[-1].value_rmse,
            "final_value_rmse_visited": laps[-1].value_rmse_visited,
            "turns_total": float(sum(r.turns for r in laps)),
            "blocked_total": float(sum(r.blocked for r in laps)),
        }
        if events:
            out["replay_reverse_share"] = sum(r.direction == "reverse" for r in events) / len(events)
            out["replay_forward_share"] = sum(r.direction == "forward" for r in events) / len(events)
            out["replay_neither_share"] = sum(r.direction == "neither" for r in events) / len(events)
            out["replay_mean_sequence_r"] = math.fsum(r.sequence_r for r in events) / len(events)
            out["replay_mean_abs_sequence_r"] = math.fsum(abs(r.sequence_r) for r in events) / len(events)
            out["replay_from_this_lap"] = math.fsum(r.replay_from_this_lap for r in events) / len(events)
            out["replay_mean_goal_distance"] = math.fsum(r.replay_mean_goal_distance for r in events) / len(events)
            out["replay_remote_share"] = math.fsum(r.replay_remote_share for r in events) / len(events)
            out["replay_mean_abs_delta"] = math.fsum(r.replay_mean_abs_delta for r in events) / len(events)
        return out


def _rule_for(condition: str, cfg: TrackConfig, model: Optional[TrackModel] = None) -> Optional[ReplayRule]:
    if condition == RULE_NONE:
        return None
    if condition in GAIN_NEED_CONDITIONS:
        if model is None:
            raise ValueError(f"{condition} needs the track model")
        return GainNeedReplay(model, condition)
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}; one of {ALL_CONDITIONS}")
    return make_rule(condition, cfg.priority_epsilon, cfg.trajectory_priority)


def run_seed(condition: str, seed: int, cfg: TrackConfig = TrackConfig()) -> SeedRun:
    """One seed of one condition: ``cfg.laps`` laps, replay at every rewarded lap end."""
    track = LinearTrack(cfg)
    agent = TrackAgent(cfg, track)
    model = TrackModel(cfg, track, agent)
    rule = _rule_for(condition, cfg, model)
    rng = RNG(seed=seed)
    action_stream = rng.stream(ACTION_STREAM)
    replay_stream = rng.stream(REPLAY_STREAM)
    laps: List[LapRecord] = []
    events: List[Dict[str, Any]] = []
    first_lap_actions: List[str] = []
    goal = EAST
    cumulative = 0

    def do_replay(trigger: str, episode: int, travel: int, acting: State) -> Tuple[Optional[ReplayOutcome], float]:
        """One pause of the condition's rule under the configured budget mode: (outcome or None when nothing was
        replayed, the rule's priority before the first backup). ``acting`` is the state the agent acts from next."""
        if rule is None or len(agent.memory) == 0:
            return None, float("nan")
        if trigger == TRIGGER_PRE_RUN and not agent.memory.episode(episode):
            return None, float("nan")  # nothing completed yet to replay (the very first pause)
        model.set_acting(acting)
        rule.begin(agent.memory, episode)
        before = rule.priority(agent.memory, agent.learner, 0)
        if cfg.budget_mode == "thresholded":
            outcome = replay_thresholded(rule, agent.memory, agent.learner, cfg.threshold, cfg.backup_cap, episode,
                                         replay_stream, tick=cumulative, travel_sign=travel, trigger=trigger)
        else:
            outcome = replay(rule, agent.memory, agent.learner, cfg.backups_per_trigger, episode, replay_stream,
                             tick=cumulative, travel_sign=travel, trigger=trigger)
        return outcome, before

    def event_row(outcome: ReplayOutcome, lap: int, goal_name: str, agent_cell: int, block: int) -> Dict[str, Any]:
        """One line of the events file: the ReplayEvent plus the lap, its goal, the reward block and the cell the
        body waits in during the pause (what ``analysis.replay_metrics`` reads the remote flag against)."""
        return {
            **outcome.event.to_dict(),
            "condition": condition, "seed": seed, "lap": lap + 1, "goal": goal_name, "block": block,
            "agent_cell": agent_cell,
            "sequence_r": outcome.sequence_r, "episodes": [t.episode + 1 for t in outcome.transitions],
            "deltas": [round(d, 6) for d in outcome.deltas],
        }

    last_completed: Optional[int] = None  # the most recently completed lap (the reverse rule's content)
    last_state: Optional[State] = None  # where the agent stood when the previous lap ended
    for lap in range(cfg.laps):
        block, reward_east, reward_west = cfg.block_of(lap)
        track.set_rewards(reward_east, reward_west)
        agent.learner.reset_episode()
        state = track.start_state(goal)
        agent.place(last_state, state)
        agent.visit(state)
        goal_name = "east" if goal == EAST else "west"
        pre_run: Optional[ReplayOutcome] = None
        pre_run_before = float("nan")
        if cfg.pre_run_pause and last_completed is not None:
            # The pre-run pause: the body is turned to face the new goal; the replayed transitions are read
            # against the travel of the lap they belong to (the most recently completed one, for the reverse rule).
            pre_run, pre_run_before = do_replay(TRIGGER_PRE_RUN, last_completed, -goal, state)
            if pre_run is not None:
                events.append(event_row(pre_run, lap, goal_name, state.cell, block))  # the body waits at the start end
        goal_cell = track.goal_cell(goal)
        steps = turns = blocked = 0
        abs_deltas: List[float] = []
        rewarded = False
        reward = 0.0
        while steps < cfg.lap_cap:
            action = agent.act(state, action_stream)
            if lap == 0:
                first_lap_actions.append(action)
            nxt, was_blocked = track.step(state, action)
            steps += 1
            turns += action == "TURN"
            blocked += was_blocked
            abs_deltas.append(abs(agent.store_and_learn(state, 0.0, nxt, False, lap, steps - 1)))
            state = nxt
            agent.visit(state)
            if track.at_goal(state):
                reward = track.reward(goal)
                abs_deltas.append(abs(agent.store_and_learn(state, reward, state, True, lap, steps)))
                rewarded = True
                break
        cumulative += steps
        online_updates = steps + (1 if rewarded else 0)
        record = LapRecord(
            condition=condition, seed=seed, lap=lap + 1, goal=goal_name,
            steps=steps, turns=turns, blocked=blocked, rewarded=rewarded, reward=reward,
            online_updates=online_updates, replay_backups=0, replay_event=False, direction="",
            sequence_r=float("nan"), replay_from_this_lap=float("nan"), replay_mean_goal_distance=float("nan"),
            replay_remote_share=float("nan"), replay_mean_abs_delta=float("nan"),
            online_mean_abs_delta=math.fsum(abs_deltas) / len(abs_deltas), value_rmse=float("nan"),
            cumulative_steps=cumulative, block=block, reward_east=reward_east, reward_west=reward_west,
            pre_run_backups=pre_run.n_backups if pre_run is not None else 0,
            pre_run_event=pre_run is not None,
            pre_run_direction=pre_run.event.direction if pre_run is not None else "",
            pre_run_sequence_r=pre_run.sequence_r if pre_run is not None else float("nan"),
            pre_run_priority_before=pre_run_before,
        )
        outcome: Optional[ReplayOutcome] = None
        if rewarded:
            # At the reward pause the agent acts next from the turned-around start of the next lap.
            outcome, record.reward_priority_before = do_replay(TRIGGER_REWARD, lap, goal, track.start_state(-goal))
        if outcome is not None:
            cells = [t.cell[0] for t in outcome.transitions]
            distances = [abs(c - goal_cell) for c in cells]
            record.replay_backups = outcome.n_backups
            record.replay_event = True
            record.direction = outcome.event.direction
            record.sequence_r = outcome.sequence_r
            record.replay_from_this_lap = sum(t.episode == lap for t in outcome.transitions) / outcome.n_backups
            record.replay_mean_goal_distance = math.fsum(distances) / len(distances)
            record.replay_remote_share = sum(d > REMOTE_CELLS for d in distances) / len(distances)
            record.replay_mean_abs_delta = math.fsum(abs(d) for d in outcome.deltas) / len(outcome.deltas)
            events.append(event_row(outcome, lap, goal_name, goal_cell, block))  # the body waits at the goal
        record.value_rmse = agent.value_rmse()
        record.value_rmse_visited = agent.value_rmse_visited()
        laps.append(record)
        last_state = state
        if rewarded:
            last_completed = lap
            goal = -goal  # the next lap runs back; a capped lap is tried again from its start end
    return SeedRun(condition=condition, seed=seed, laps=laps, events=events, first_lap_actions=tuple(first_lap_actions))


# --- the comparison -------------------------------------------------------------------------


def _stat_seed(*key: Any) -> int:
    import hashlib

    return int.from_bytes(hashlib.sha256(repr(key).encode()).digest()[:4], "big")


def _paired_rows(by_condition: Mapping[str, Dict[int, Dict[str, float]]], metric: str, a: str, b: str,
                 n_boot: int) -> Dict[str, Any]:
    seeds = sorted(set(by_condition[a]) & set(by_condition[b]))
    va = np.array([by_condition[a][s][metric] for s in seeds], dtype=np.float64)
    vb = np.array([by_condition[b][s][metric] for s in seeds], dtype=np.float64)
    effect = paired_effect(va, vb, n_boot=n_boot, seed=_stat_seed("paired", metric, a, b))
    delta = cliffs_delta(va, vb, n_boot=n_boot, seed=_stat_seed("cliff", metric, a, b))
    return {
        "metric": metric, "a": a, "b": b, "n": len(seeds),
        "mean_a": effect["mean_a"], "mean_b": effect["mean_b"],
        "mean_diff": effect["mean_diff"], "low": effect["low"], "high": effect["high"],
        "fraction_b_lt_a": float(np.mean(vb < va)) if len(seeds) else float("nan"),
        "fraction_b_gt_a": effect["fraction_b_gt_a"], "fraction_ties": effect["fraction_ties"],
        "cliffs_delta": delta["delta"], "cliffs_low": delta["low"], "cliffs_high": delta["high"],
        "cliffs_magnitude": delta["magnitude"], "ci_method": effect["method"], "note": "; ".join(n for n in (effect["note"], delta["note"]) if n),
    }


EFFECT_METRICS = ("total_steps", "steps_last_quarter", "final_value_rmse", "final_value_rmse_visited", "laps_capped")
COMPARISONS = (
    (RULE_NONE, RULE_UNIFORM), (RULE_NONE, RULE_REVERSE_TRAJECTORY), (RULE_NONE, RULE_PRIORITISED_TD),
    (RULE_UNIFORM, RULE_REVERSE_TRAJECTORY), (RULE_UNIFORM, RULE_PRIORITISED_TD), (RULE_REVERSE_TRAJECTORY, RULE_PRIORITISED_TD),
)


def analyse(runs: Sequence[SeedRun], n_boot: int) -> Dict[str, Any]:
    """The tables of the comparison from the per-seed runs (pure: the same runs give the same tables)."""
    conditions = [c for c in CONDITIONS if any(r.condition == c for r in runs)]
    by_condition: Dict[str, Dict[int, Dict[str, float]]] = {c: {} for c in conditions}
    for run in runs:
        by_condition[run.condition][run.seed] = run.summary()
    # The guard: every per-seed lap-length vector distinct within a condition (seeds are samples).
    guard: Dict[str, Any] = {}
    for c in conditions:
        vectors = [{"seed": r.seed, "steps": [lap.steps for lap in r.laps]} for r in runs if r.condition == c]
        verdict = pseudo_replication_guard(vectors, key="steps", allow=True)
        guard[c] = {"distinct": verdict if isinstance(verdict, int) else None, "n": len(vectors),
                    "message": verdict if isinstance(verdict, str) else ""}
    # The design check: the first lap is the same across conditions at a seed (no replay has happened yet).
    first_laps: Dict[int, set] = {}
    for run in runs:
        first_laps.setdefault(run.seed, set()).add(run.first_lap_actions)
    first_lap_identical = all(len(v) == 1 for v in first_laps.values())
    # Tidy per-seed table and its summary.
    rows = []
    for c in conditions:
        for seed, summary in sorted(by_condition[c].items()):
            rows.append({"condition": c, "task": TASK, "seed": seed, **summary})
    tidy = tidy_table(rows)
    summary_table = summarise(tidy, by="condition", n_boot=n_boot, seed=_stat_seed("summary"))
    # Learning curve: per condition and lap, the mean steps over seeds with its interval.
    curve = []
    for c in conditions:
        per_seed = [r for r in runs if r.condition == c]
        n_laps = max(len(r.laps) for r in per_seed)
        for lap in range(1, n_laps + 1):
            records = [r.laps[lap - 1] for r in per_seed if len(r.laps) >= lap]
            values = np.array([rec.steps for rec in records], dtype=np.float64)
            rmse = np.array([rec.value_rmse for rec in records], dtype=np.float64)
            ci = bootstrap_ci(values, np.mean, n_boot=n_boot, seed=_stat_seed("curve", c, lap))
            curve.append({"condition": c, "lap": lap, "n": int(values.size), "mean_steps": ci.estimate,
                          "low": ci.low, "high": ci.high, "median_steps": float(np.median(values)),
                          "mean_value_rmse": float(rmse.mean()),
                          "fraction_capped": sum(not rec.rewarded for rec in records) / len(records)})
    effects = [
        _paired_rows(by_condition, metric, a, b, n_boot)
        for metric in EFFECT_METRICS
        for a, b in COMPARISONS
        if a in by_condition and b in by_condition
    ]
    return {
        "conditions": conditions, "per_seed": by_condition, "tidy": tidy, "summary": summary_table,
        "curve": curve, "effects": effects, "guard": guard, "first_lap_identical": first_lap_identical,
        "seeds": sorted({r.seed for r in runs}),
    }


# --- outputs ---------------------------------------------------------------------------------


def _fmt(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        return f"{value:.6g}"
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value))
    return value


def write_csv(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row.get(k)) for k in columns})


LAP_COLUMNS = tuple(LapRecord.__dataclass_fields__)
CURVE_COLUMNS = ("condition", "lap", "n", "mean_steps", "low", "high", "median_steps", "mean_value_rmse", "fraction_capped")
EFFECT_COLUMNS = ("metric", "a", "b", "n", "mean_a", "mean_b", "mean_diff", "low", "high", "fraction_b_lt_a",
                  "fraction_b_gt_a", "fraction_ties", "cliffs_delta", "cliffs_low", "cliffs_high", "cliffs_magnitude",
                  "ci_method", "note")
EVENTS_FILE = "track_replay_events.jsonl.gz"
OUTPUT_FILES = ("track_laps.csv", "track_per_seed.csv", "track_summary.csv", "track_learning_curve.csv",
                "track_effects.csv", EVENTS_FILE, "track_manifest.json")


def _dependency_versions() -> Dict[str, str]:
    from importlib import metadata

    out: Dict[str, str] = {"python": sys.version.split()[0]}
    for name in ("numpy", "pandas", "scipy", "threadpoolctl", "pyarrow"):
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "not installed"
    return out


def write_outputs(out: Path, runs: Sequence[SeedRun], result: Mapping[str, Any], manifest: Dict[str, Any]) -> List[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    laps = [asdict(lap) for run in runs for lap in run.laps]
    laps.sort(key=lambda r: (CONDITIONS.index(r["condition"]), r["seed"], r["lap"]))
    write_csv(out / "track_laps.csv", LAP_COLUMNS, laps)
    tidy = result["tidy"]
    tidy_rows = [{"condition": r.condition, "task": r.task, "seed": int(r.seed), "metric": r.metric, "value": float(r.value)} for r in tidy.itertuples(index=False)]
    write_csv(out / "track_per_seed.csv", ("condition", "task", "seed", "metric", "value"), tidy_rows)
    summary = result["summary"]
    write_csv(out / "track_summary.csv", list(summary.columns), [dict(zip(summary.columns, row)) for row in summary.itertuples(index=False)])
    write_csv(out / "track_learning_curve.csv", CURVE_COLUMNS, result["curve"])
    write_csv(out / "track_effects.csv", EFFECT_COLUMNS, result["effects"])
    write_events(out / EVENTS_FILE, (event for run in sorted(runs, key=lambda r: (CONDITIONS.index(r.condition), r.seed)) for event in run.events))
    write_manifest(out / "track_manifest.json", manifest)
    return [out / name for name in OUTPUT_FILES]


def write_events(path: Path, events: Iterable[Mapping[str, Any]]) -> int:
    """One canonical JSON line per replay event, gzip-compressed with a fixed header time, so two runs
    write byte-identical files (about 600 bytes per event uncompressed: the cells, the episodes and
    the TD errors of its backups). Returns the number of events written."""
    import gzip

    written = 0
    with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as fh:
        for event in events:
            fh.write((json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
            written += 1
    return written


def read_events(path: Path) -> List[Dict[str, Any]]:
    """The events ``write_events`` wrote."""
    import gzip

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def print_summary(result: Mapping[str, Any]) -> None:
    summary = result["summary"]
    print("per-condition means over seeds (BCa 95% interval):")
    for metric in ("total_steps", "steps_first_quarter", "steps_last_quarter", "laps_capped", "final_value_rmse",
                   "final_value_rmse_visited", "replay_backups", "replay_budget_fraction", "replay_reverse_share",
                   "replay_mean_sequence_r",
                   "replay_from_this_lap", "replay_remote_share"):
        rows = summary[summary["metric"] == metric]
        if rows.empty:
            continue
        cells = ", ".join(f"{r.condition} {r.mean:.4g} [{r.low:.4g}, {r.high:.4g}]" for r in rows.itertuples(index=False))
        print(f"  {metric:26s} {cells}")
    print("paired effects (b - a, mean with BCa 95% interval; Cliff's delta):")
    for e in result["effects"]:
        if e["metric"] != "total_steps":
            continue
        print(f"  {e['b']:20s} vs {e['a']:20s}: {e['mean_diff']:+9.1f} [{e['low']:+9.1f}, {e['high']:+9.1f}] steps; "
              f"b < a on {e['fraction_b_lt_a']:.2f} of seeds; delta {e['cliffs_delta']:+.3f} [{e['cliffs_low']:+.3f}, {e['cliffs_high']:+.3f}] ({e['cliffs_magnitude']})")
    print(f"guard: {result['guard']}")
    print(f"first lap identical across conditions at every seed: {result['first_lap_identical']}")


def _job(args: Tuple[str, int, TrackConfig]) -> SeedRun:
    condition, seed, cfg = args
    return run_seed(condition, seed, cfg)


def run_all(conditions: Sequence[str], seeds: Sequence[int], cfg: TrackConfig, workers: Optional[int] = None) -> List[SeedRun]:
    """Every (condition, seed) job, in a fixed order whatever the worker count."""
    jobs = [(c, s, cfg) for c in conditions for s in seeds]
    if workers == 1 or len(jobs) == 1:
        return [_job(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_job, jobs, chunksize=1))


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--conditions", default=",".join(CONDITIONS), help="comma-separated subset of " + ",".join(CONDITIONS))
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS), help="number of seeds (default 30)")
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEEDS[0])
    parser.add_argument("--laps", type=int, default=TrackConfig.laps)
    parser.add_argument("--lap-cap", type=int, default=TrackConfig.lap_cap)
    parser.add_argument("--backups", type=int, default=TrackConfig.backups_per_trigger, help="TD backups per replay trigger")
    parser.add_argument("--workers", type=int, default=None, help="worker processes (default: all cores)")
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--quick", action="store_true", help="a smoke-test budget (6 laps, cap 300, 200 replicates); needs --out")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    conditions = tuple(c.strip() for c in args.conditions.split(",") if c.strip())
    for c in conditions:
        if c not in CONDITIONS:
            parser.error(f"unknown condition {c!r}; choose from {', '.join(CONDITIONS)}")
    cfg = TrackConfig(laps=args.laps, lap_cap=args.lap_cap, backups_per_trigger=args.backups)
    n_boot = args.n_boot
    if args.quick:
        cfg = replace(cfg, laps=min(cfg.laps, 6), lap_cap=min(cfg.lap_cap, 300))
        n_boot = min(n_boot, 200)
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    full = (
        tuple(conditions) == CONDITIONS and tuple(seeds) == DEFAULT_SEEDS and cfg == TrackConfig()
        and n_boot >= 1000 and not args.quick
    )
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a partial run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    started = time.perf_counter()
    manifest = build_manifest(
        cfg, protocol="linear_track_replay", seeds=seeds, ticks_requested=cfg.laps * cfg.lap_cap * len(conditions),
        extra={
            "conditions": list(conditions), "task": TASK, "learner": TabularTD0(cfg.bin_size, cfg.learning_rate, cfg.discount).parameters(),
            "replay": {"trigger": "reward", "backups_per_trigger": cfg.backups_per_trigger, "memory_capacity": cfg.memory_capacity,
                       "priority_epsilon": cfg.priority_epsilon, "rules": [c for c in conditions if c != RULE_NONE]},
            "policy": {"temperature": cfg.temperature, "forward_prior": cfg.forward_prior, "value_gain": cfg.value_gain,
                       "untrained_turn_probability": cfg.untrained_turn_probability(), "sampler": "basal_ganglia.softmax_sample"},
            "rng_streams": {"action": ACTION_STREAM, "replay": REPLAY_STREAM, "environment": "none (deterministic track)"},
            "dependencies": _dependency_versions(), "n_boot": n_boot, "full_evaluation": full,
            "command": "python3 -m experiments.linear_track_replay " + " ".join(list(argv) if argv is not None else sys.argv[1:]),
        },
    )
    runs = run_all(conditions, seeds, cfg, args.workers)
    result = analyse(runs, n_boot)
    manifest["guard"] = result["guard"]
    manifest["first_lap_identical_across_conditions"] = result["first_lap_identical"]
    manifest["workers"] = args.workers if args.workers is not None else os.cpu_count()
    total_steps = sum(lap.steps for run in runs for lap in run.laps)
    finish_manifest(manifest, ticks_run=total_steps, wall_seconds=time.perf_counter() - started)
    paths = write_outputs(args.out, runs, result, manifest)
    print_summary(result)
    print(f"wrote {', '.join(p.name for p in paths)} to {args.out} in {manifest['timing']['wall_seconds']:.1f} s")
    return result


if __name__ == "__main__":
    main()
