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
from brain.systems.replay_events import RULE_NONE, RULE_PRIORITISED_TD, RULE_REVERSE_TRAJECTORY, RULE_UNIFORM
from brain.systems.replay_rules import ReplayOutcome, ReplayRule, StoredTransition, TransitionMemory, make_rule, replay
from brain.systems.value_learners import TabularTD0
from core.rng import RNG
from metrics.manifest import build_manifest, finish_manifest, write_manifest

CONDITIONS: Tuple[str, ...] = (RULE_NONE, RULE_UNIFORM, RULE_REVERSE_TRAJECTORY, RULE_PRIORITISED_TD)
ACTIONS: Tuple[str, ...] = ("FORWARD", "TURN")
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

    def __post_init__(self) -> None:
        if self.n_bins < 2 or self.laps < 1 or self.lap_cap < 1 or self.backups_per_trigger < 1 or self.memory_capacity < 1:
            raise ValueError("n_bins >= 2, laps, lap_cap, backups_per_trigger and memory_capacity >= 1")
        if not (self.bin_size > 0 and self.temperature > 0 and self.value_gain >= 0 and self.priority_epsilon > 0):
            raise ValueError("bin_size, temperature and priority_epsilon must be positive, value_gain >= 0")

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
    """The deterministic track: states, transitions, goal test and the learner's coordinates."""

    def __init__(self, cfg: TrackConfig) -> None:
        self.cfg = cfg

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
        return self.cfg.reward_east if goal == EAST else self.cfg.reward_west

    def position(self, state: State) -> Tuple[float, float]:
        """The learner's (x, y) for a state: x the cell centre, y encodes heading and goal in four distinct cells."""
        x = self.cfg.bin_size * (state.cell + 0.5)
        y = 0.25 if state.heading == EAST else -0.25
        if state.goal == WEST:
            y += 1.0
        return x, y

    def states(self) -> List[State]:
        return [State(i, h, g) for g in (EAST, WEST) for h in (EAST, WEST) for i in range(self.cfg.n_bins)]

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
        return delta

    def value_rmse(self) -> float:
        errors = [self.value(s) - self.track.optimal_value(s) for s in self.track.states()]
        return math.sqrt(math.fsum(e * e for e in errors) / len(errors))


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
            "final_value_rmse": laps[-1].value_rmse,
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


def _rule_for(condition: str, cfg: TrackConfig) -> Optional[ReplayRule]:
    if condition == RULE_NONE:
        return None
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}; one of {CONDITIONS}")
    return make_rule(condition, cfg.priority_epsilon)


def run_seed(condition: str, seed: int, cfg: TrackConfig = TrackConfig()) -> SeedRun:
    """One seed of one condition: ``cfg.laps`` laps, replay at every rewarded lap end."""
    track = LinearTrack(cfg)
    agent = TrackAgent(cfg, track)
    rule = _rule_for(condition, cfg)
    rng = RNG(seed=seed)
    action_stream = rng.stream(ACTION_STREAM)
    replay_stream = rng.stream(REPLAY_STREAM)
    laps: List[LapRecord] = []
    events: List[Dict[str, Any]] = []
    first_lap_actions: List[str] = []
    goal = EAST
    cumulative = 0
    for lap in range(cfg.laps):
        agent.learner.reset_episode()
        state = track.start_state(goal)
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
            if track.at_goal(state):
                reward = track.reward(goal)
                abs_deltas.append(abs(agent.store_and_learn(state, reward, state, True, lap, steps)))
                rewarded = True
                break
        cumulative += steps
        online_updates = steps + (1 if rewarded else 0)
        record = LapRecord(
            condition=condition, seed=seed, lap=lap + 1, goal="east" if goal == EAST else "west",
            steps=steps, turns=turns, blocked=blocked, rewarded=rewarded, reward=reward,
            online_updates=online_updates, replay_backups=0, replay_event=False, direction="",
            sequence_r=float("nan"), replay_from_this_lap=float("nan"), replay_mean_goal_distance=float("nan"),
            replay_remote_share=float("nan"), replay_mean_abs_delta=float("nan"),
            online_mean_abs_delta=math.fsum(abs_deltas) / len(abs_deltas), value_rmse=float("nan"),
            cumulative_steps=cumulative,
        )
        if rewarded and rule is not None:
            outcome: ReplayOutcome = replay(
                rule, agent.memory, agent.learner, cfg.backups_per_trigger, lap, replay_stream,
                tick=cumulative, travel_sign=goal,
            )
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
            events.append({
                **outcome.event.to_dict(),
                "condition": condition, "seed": seed, "lap": lap + 1, "goal": record.goal,
                "sequence_r": outcome.sequence_r, "episodes": [t.episode + 1 for t in outcome.transitions],
                "deltas": [round(d, 6) for d in outcome.deltas],
            })
        record.value_rmse = agent.value_rmse()
        laps.append(record)
        if rewarded:
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


EFFECT_METRICS = ("total_steps", "steps_last_quarter", "final_value_rmse", "laps_capped")
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
                   "replay_backups", "replay_budget_fraction", "replay_reverse_share", "replay_mean_sequence_r",
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
