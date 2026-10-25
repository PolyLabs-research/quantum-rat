"""RQ1 on the tabular linear track: the preregistered protocol runner (M2a remainder, steps 2-4).

    python3 -m experiments.linear_track_rq1 --workers 4                 # step 4: both modes x 7 conditions x 2 sessions x seeds 1-30
    python3 -m experiments.linear_track_rq1 --pilot --workers 4         # step 4's theta pilot (fixed mode, the baseline block, seeds 1-3)
    python3 -m experiments.linear_track_rq1 --version step3 --workers 4 # step 3's protocol into its directory
    python3 -m experiments.linear_track_rq1 --quick --seeds 2 --out /tmp/rq1   # the smoke test's run

The protocol is the fixed evaluation's track and agent (``experiments.linear_track_replay``)
with the preregistered additions: reward blocks of 20 laps, a pre-run pause at the start of
every lap beside the reward pause at its end, and two budget modes, fixed (20 backups per
pause) and thresholded (replay while the rule's priority exceeds theta, at most 100 per pause).
Replay events are read by the plan's definition (``analysis.replay_metrics``: >= 4 distinct
cells over >= 0.3 m, direction against the travel of the lap the replayed states belong to,
remote > 0.5 m from the agent).

Three versions (``--version``). Step 2 (G28; docs/prereg/rq1_track_tabular.md): the four floors,
four blocks (east 1.0 / 4.0 / 1.0 / 0.25, west 1.0 throughout), one theta, the trajectory rule's
"next" priority; ``docs/data/m2a/rq1``. Step 3 (G29; docs/prereg/rq1_track_gain_need.md): seven
conditions on the same blocks, theta per rule from its pilot, the trajectory rule's "remaining_max"
priority; ``docs/data/m2a/rq1_step3``. Step 4 (G30; docs/prereg/rq1_track_step4.md), the default:
the seven conditions in two sessions per seed, "increase" (baseline then x4) and "decrease"
(baseline then x0.25), each reward change read against the baseline block that precedes it; the
thresholded theta of a rule whose priority is in value units is multiplied by the learner's value
scale (the mean |V| over the states occupied so far) at every pause; ``docs/data/m2a/rq1_step4``.

Tables (``--out``, default the version's committed directory): rq1_pauses.csv.gz (one row per
pause: backups, events, their directions, remote count, the rule's priority and the value scale),
rq1_seed_blocks.csv (per condition, mode, session, seed, block, end and pause kind: backups and
events per stop and the shares), rq1_tests.csv (the preregistered tests (a)-(d) with estimate,
interval, bound and verdict), rq1_adaptation.csv (steps per lap by block and condition),
rq1_learning.csv (total steps over a session per condition with paired differences against none
and prioritised_td) and rq1_manifest.json; ``--write-events`` adds rq1_events.jsonl.gz, every
replay with its cells (not committed). ``--pilot`` writes rq1_pilot.csv instead: the per-rule
theta of the version's pilot rule. A partial run refuses the committed directory: give ``--out``.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from analysis.replay_metrics import extract_events
from analysis.stats import bootstrap_ci, cliffs_delta, paired_effect, pseudo_replication_guard, tost
from brain.systems.replay_events import RULE_NONE, TRIGGER_PRE_RUN, TRIGGER_REWARD
from brain.systems.replay_gain_need import GainNeedReplay
from brain.systems.replay_mattar_daw import MATTAR_DAW_CONDITIONS, MattarDawReplay
from brain.systems.replay_rules import make_rule
from experiments.linear_track_replay import (
    ALL_CONDITIONS,
    BUDGET_MODES,
    CONDITIONS,
    DEFAULT_N_BOOT,
    DEFAULT_SEEDS,
    GAIN_NEED_CONDITIONS,
    SeedRun,
    TrackConfig,
    _dependency_versions,
    _stat_seed,
    run_all,
    write_csv,
)
from metrics.manifest import build_manifest, finish_manifest, write_manifest

# Step 5 (G31; docs/prereg/rq1_track_mattar_daw.md), the default: step 4's protocol on the Q learner, with the floors
# rerun under it and the Mattar & Daw rule with and without its forward n-step extension; the (b) rate tests add the
# east change minus the west change (G30 C2); docs/data/m2a/rq1_step5.
VERSIONS = ("step2", "step3", "step4", "step5")
DEFAULT_VERSION = "step5"
DEFAULT_OUTS = {"step2": Path("docs/data/m2a/rq1"), "step3": Path("docs/data/m2a/rq1_step3"), "step4": Path("docs/data/m2a/rq1_step4"),
                "step5": Path("docs/data/m2a/rq1_step5")}
DEFAULT_OUT = DEFAULT_OUTS[DEFAULT_VERSION]
PREREGS = {"step2": "docs/prereg/rq1_track_tabular.md", "step3": "docs/prereg/rq1_track_gain_need.md", "step4": "docs/prereg/rq1_track_step4.md",
           "step5": "docs/prereg/rq1_track_mattar_daw.md"}
LEARNERS_BY_VERSION = {"step2": "v", "step3": "v", "step4": "v", "step5": "q"}
STEP3_CONDITIONS: Tuple[str, ...] = CONDITIONS + GAIN_NEED_CONDITIONS  # the seven of steps 3 and 4 (the v learner)
STEP5_CONDITIONS: Tuple[str, ...] = CONDITIONS + MATTAR_DAW_CONDITIONS  # the floors on the q learner and the two Mattar & Daw rules
# Steps 2 and 3: four blocks in one session.
BLOCKS: Tuple[Tuple[int, float, float], ...] = ((20, 1.0, 1.0), (20, 4.0, 1.0), (20, 1.0, 1.0), (20, 0.25, 1.0))
BLOCK_NAMES = ("baseline", "increase_x4", "washout", "decrease_x0.25")
FOUR_BLOCK = "four_block"
# Step 4 (G29 C2): two sessions per seed, each a baseline block then one change, so that each change is read against
# the baseline that precedes it (in the four-block protocol the decrease followed a washout block whose own surprise,
# |dr| 3.0, let an unsigned rule pass "down" for a magnitude reason). Both sessions run from the same seed, so their
# baseline blocks are the same 20 laps and the sessions part at lap 21.
TWO_SESSIONS: Dict[str, Tuple[Tuple[int, float, float], ...]] = {
    "increase": ((20, 1.0, 1.0), (20, 4.0, 1.0)), "decrease": ((20, 1.0, 1.0), (20, 0.25, 1.0)),
}
SESSIONS: Dict[str, Dict[str, Tuple[Tuple[int, float, float], ...]]] = {
    "step2": {FOUR_BLOCK: BLOCKS},
    "step3": {FOUR_BLOCK: BLOCKS},
    "step4": TWO_SESSIONS,
    "step5": TWO_SESSIONS,
}
SESSION_BLOCK_NAMES: Dict[str, Tuple[str, ...]] = {
    FOUR_BLOCK: BLOCK_NAMES, "increase": ("baseline", "increase_x4"), "decrease": ("baseline", "decrease_x0.25"),
}
# Step 2's theta: 0.02 was the preregistered value; the preregistered pilot rule moved it once, to the median online
# |TD error| of laps 11-20 of the no-replay pilot (0.0035; docs/prereg/rq1_track_tabular.md, "Pilot outcome"; G28).
THRESHOLD = 0.0035
# Step 3's theta per rule (docs/prereg/rq1_track_gain_need.md change 2): the median of the rule's own priority read
# before the reward pause over laps 11-20 of block 1 at seeds 1-3 in a fixed-budget pilot (G29).
THRESHOLDS_STEP3: Dict[str, Optional[float]] = {
    "uniform": 0.0027462, "reverse_trajectory": 0.137277, "prioritised_td": 0.155972,
    "gain_need": 1.59024e-07, "gain_only": 0.000269043, "need_only": 2.71085,
}
# Step 4's theta per rule (docs/prereg/rq1_track_step4.md change 2; G29 C3): the same pilot rule applied to the
# *normalised* priority, priority / value scale, for a rule whose priority is in value units (``--pilot``; the
# pilot's table is docs/data/m2a/rq1_step4/rq1_pilot.csv). ``None`` until the pilot has run; a thresholded run
# refuses a rule without a theta.
THRESHOLDS_STEP4: Dict[str, Optional[float]] = {
    "uniform": 0.130951, "reverse_trajectory": 2.25778, "prioritised_td": 1.59017,
    "gain_need": 6.13424e-06, "gain_only": 0.0102264, "need_only": 2.71085,
}
# Step 5's theta per rule: the step-4 pilot rule on the q learner's priorities (``--pilot --version step5``; the table
# is docs/data/m2a/rq1_step5/rq1_pilot.csv). ``None`` until the pilot has run.
THRESHOLDS_STEP5: Dict[str, Optional[float]] = {
    "uniform": 0.124286, "reverse_trajectory": 2.25714, "prioritised_td": 0.940048, "mattar_daw": 3.90938e-05, "mattar_daw_1step": 1.04689e-06,
}
THRESHOLD_SCALES = {"step2": "none", "step3": "none", "step4": "mean_abs_value", "step5": "mean_abs_value"}
THETA_TABLES: Dict[str, Dict[str, Optional[float]]] = {"step3": THRESHOLDS_STEP3, "step4": THRESHOLDS_STEP4, "step5": THRESHOLDS_STEP5}
PILOT_SEEDS: Tuple[int, ...] = (1, 2, 3)
BACKUP_CAP = 100
ENDS = ("east", "west")
TRIGGERS = (TRIGGER_REWARD, TRIGGER_PRE_RUN)
DIRECTION_BOUND = 0.6
REMOTE_BOUND = 0.10
DELTA_BOUND = 0.3
TOST_RELATIVE = 0.2


def version_conditions(version: str) -> Tuple[str, ...]:
    """The conditions a version runs: the four floors in step 2, the seven of the v learner in steps 3 and 4, the
    floors and the two Mattar & Daw rules on the q learner in step 5."""
    if version == "step2":
        return CONDITIONS
    if version == "step5":
        return STEP5_CONDITIONS
    return STEP3_CONDITIONS


def condition_is_value_scaled(condition: str) -> bool:
    """Whether the condition's rule has a priority in value units (``ReplayRule.value_scaled``); False for none."""
    if condition == RULE_NONE:
        return False
    if condition in GAIN_NEED_CONDITIONS:
        return GainNeedReplay.VALUE_SCALED[condition]
    if condition in MATTAR_DAW_CONDITIONS:
        return bool(MattarDawReplay.value_scaled)
    return bool(make_rule(condition).value_scaled)


def theta_for(condition: str, version: str, overrides: Optional[Mapping[str, float]] = None) -> float:
    """The thresholded theta of ``condition`` under ``version`` (``overrides`` win; step 2 has one theta for all)."""
    if overrides and condition in overrides:
        return float(overrides[condition])
    if version == "step2":
        return THRESHOLD
    theta = THETA_TABLES[version].get(condition)
    if theta is None:
        if condition == RULE_NONE:
            return THRESHOLD  # never used: none makes no pause
        raise ValueError(f"no theta for {condition!r} in {version}: run the pilot (--pilot; {PREREGS[version]}) or pass --theta {condition}=VALUE")
    return float(theta)


def session_for(version: str, session: Optional[str]) -> str:
    """``session`` checked against the version's sessions; the only session when there is one and none is given."""
    sessions = SESSIONS[version]
    if session is None:
        if len(sessions) != 1:
            raise ValueError(f"{version} runs the sessions {tuple(sessions)}: give one")
        return next(iter(sessions))
    if session not in sessions:
        raise ValueError(f"{version} has no session {session!r}; one of {tuple(sessions)}")
    return session


def protocol_config(mode: str, quick: bool = False, *, version: str = DEFAULT_VERSION, theta: Optional[float] = None,
                    session: Optional[str] = None) -> TrackConfig:
    """The preregistered protocol in ``mode``; ``quick`` shrinks every block to 2 laps.

    ``version`` selects the trajectory rule's thresholded priority ("next" for step 2, "remaining_max" since step 3),
    the theta scale ("mean_abs_value" in step 4) and the sessions; ``session`` is one of the version's (optional
    when it has one); ``theta`` is the thresholded threshold (step 2's single value when None).
    """
    if mode not in BUDGET_MODES:
        raise ValueError(f"mode must be one of {BUDGET_MODES}, got {mode!r}")
    if version not in VERSIONS:
        raise ValueError(f"version must be one of {VERSIONS}, got {version!r}")
    blocks = SESSIONS[version][session_for(version, session)]
    if quick:
        blocks = tuple((2, e, w) for _, e, w in blocks)
    return TrackConfig(
        laps=sum(b[0] for b in blocks), reward_blocks=blocks, pre_run_pause=True, budget_mode=mode,
        threshold=THRESHOLD if theta is None else float(theta), backup_cap=BACKUP_CAP,
        trajectory_priority="next" if version == "step2" else "remaining_max",
        threshold_scale=THRESHOLD_SCALES[version],
        learner=LEARNERS_BY_VERSION[version],
    )


def block_name(session: str, block: int) -> str:
    names = SESSION_BLOCK_NAMES[session]
    return names[block] if block < len(names) else str(block)


def cell_label(session: str, block: int) -> str:
    """How a (session, block) cell is named in a statistic: ``block2`` in the four-block protocol, ``increase_block2`` in step 4."""
    return f"block{block + 1}" if session == FOUR_BLOCK else f"{session}_block{block + 1}"


# --- per pause ----------------------------------------------------------------------------------------


PAUSE_COLUMNS = ("condition", "mode", "session", "seed", "lap", "block", "block_name", "end", "trigger", "lap_rewarded",
                 "n_backups", "n_events", "n_reverse", "n_forward", "n_neither", "n_remote", "backups_in_events",
                 "priority_before", "value_scale", "from_this_lap")


def pause_rows(run: SeedRun, mode: str, cfg: TrackConfig, session: str = FOUR_BLOCK) -> List[Dict[str, Any]]:
    """One row per pause of a seed's run: the pre-run pause that started each lap and the reward pause that ended it."""
    by_key: Dict[Tuple[str, int], List[Mapping[str, Any]]] = {}
    for event in run.events:
        by_key.setdefault((event["trigger"], int(event["lap"])), []).append(event)
    rows: List[Dict[str, Any]] = []
    for lap in run.laps:
        start_end = "west" if lap.goal == "east" else "east"  # the lap starts at the far end from its goal
        for trigger, end, backups, before, scale, from_this in (
            (TRIGGER_PRE_RUN, start_end, lap.pre_run_backups, lap.pre_run_priority_before, lap.pre_run_value_scale, math.nan),
            (TRIGGER_REWARD, lap.goal, lap.replay_backups, lap.reward_priority_before, lap.reward_value_scale, lap.replay_from_this_lap),
        ):
            if trigger == TRIGGER_REWARD and not lap.rewarded:
                continue  # a capped lap has no reward pause
            events = [e for record in by_key.get((trigger, lap.lap), []) for e in extract_events(record, cfg.n_bins)]
            rows.append({
                "condition": run.condition, "mode": mode, "session": session, "seed": run.seed, "lap": lap.lap,
                "block": lap.block, "block_name": block_name(session, lap.block),
                "end": end, "trigger": trigger, "lap_rewarded": lap.rewarded, "n_backups": backups,
                "n_events": len(events), "n_reverse": sum(e.direction == "reverse" for e in events),
                "n_forward": sum(e.direction == "forward" for e in events),
                "n_neither": sum(e.direction == "neither" for e in events),
                "n_remote": sum(e.remote for e in events), "backups_in_events": sum(e.n_backups for e in events),
                "priority_before": before,
                "value_scale": scale,  # mean |V| over the occupied states at the pause (step 4's theta multiplier)
                "from_this_lap": from_this,  # share of the reward pause's backups from the lap just run (NaN at pre-run pauses)
            })
    return rows


SEED_BLOCK_COLUMNS = ("condition", "mode", "session", "seed", "block", "block_name", "end", "trigger", "stops", "backups_per_stop",
                      "events_per_stop", "reverse_per_stop", "forward_per_stop", "remote_per_stop", "reverse_share",
                      "forward_share", "remote_share", "from_this_lap_share")


def seed_block_rows(pauses: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by: Dict[Tuple[Any, ...], List[Mapping[str, Any]]] = {}
    for p in pauses:
        by.setdefault((p["condition"], p["mode"], p["session"], int(p["seed"]), int(p["block"]), p["end"], p["trigger"]), []).append(p)
    out: List[Dict[str, Any]] = []
    for key, rows in sorted(by.items(), key=lambda kv: (ALL_CONDITIONS.index(kv[0][0]), kv[0][1:])):
        condition, mode, session, seed, block, end, trigger = key
        stops = len(rows)
        events = sum(r["n_events"] for r in rows)
        rev, fwd, rem = (sum(r[k] for r in rows) for k in ("n_reverse", "n_forward", "n_remote"))
        out.append({
            "condition": condition, "mode": mode, "session": session, "seed": seed, "block": block,
            "block_name": rows[0]["block_name"], "end": end, "trigger": trigger, "stops": stops,
            "backups_per_stop": sum(r["n_backups"] for r in rows) / stops,
            "events_per_stop": events / stops, "reverse_per_stop": rev / stops, "forward_per_stop": fwd / stops,
            "remote_per_stop": rem / stops,
            "reverse_share": rev / events if events else math.nan,
            "forward_share": fwd / events if events else math.nan,
            "remote_share": rem / events if events else math.nan,
            # backup-weighted share of the reward pauses' backups that came from the lap just run (NaN at pre-run pauses)
            "from_this_lap_share": (
                math.fsum(float(r["from_this_lap"]) * r["n_backups"] for r in rows if not math.isnan(float(r["from_this_lap"])) and r["n_backups"])
                / sum(r["n_backups"] for r in rows if not math.isnan(float(r["from_this_lap"])) and r["n_backups"])
                if any(not math.isnan(float(r["from_this_lap"])) and r["n_backups"] for r in rows) else math.nan
            ),
        })
    return out


# --- the preregistered tests --------------------------------------------------------------------------


TEST_COLUMNS = ("test", "condition", "mode", "statistic", "n", "estimate", "low", "high", "extra", "bound", "verdict", "note")
Cell = Tuple[str, int]  # (session, block)


def _per_seed(rows: Sequence[Mapping[str, Any]], condition: str, mode: str, metric: str, *, cells: Sequence[Cell],
              ends: Sequence[str], trigger: str) -> Dict[int, float]:
    """Per seed, ``metric`` pooled (stop-weighted) over the given (session, block) cells, ends and pause kind; shares pool their counts."""
    out: Dict[int, float] = {}
    seeds = sorted({int(r["seed"]) for r in rows if r["condition"] == condition and r["mode"] == mode})
    wanted = set(cells)
    for seed in seeds:
        sel = [r for r in rows if r["condition"] == condition and r["mode"] == mode and int(r["seed"]) == seed
               and (r["session"], int(r["block"])) in wanted and r["end"] in ends and r["trigger"] == trigger]
        if not sel:
            continue
        if metric.endswith("_share"):
            numer = metric.replace("_share", "_per_stop")
            events = math.fsum(r["events_per_stop"] * r["stops"] for r in sel)
            out[seed] = math.fsum(r[numer] * r["stops"] for r in sel) / events if events else math.nan
        else:
            stops = sum(r["stops"] for r in sel)
            out[seed] = math.fsum(r[metric] * r["stops"] for r in sel) / stops if stops else math.nan
    return out


def _ci_row(test: str, condition: str, mode: str, statistic: str, values: Mapping[int, float], n_boot: int,
            bound: str, verdict_fn, extra: str = "", undefined: str = "undefined (no events)") -> Dict[str, Any]:
    arr = np.array([v for v in values.values() if not (isinstance(v, float) and math.isnan(v))], dtype=np.float64)
    if arr.size == 0:
        return {"test": test, "condition": condition, "mode": mode, "statistic": statistic, "n": 0, "estimate": math.nan,
                "low": math.nan, "high": math.nan, "extra": extra, "bound": bound, "verdict": undefined, "note": ""}
    ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed(test, condition, mode, statistic))
    return {"test": test, "condition": condition, "mode": mode, "statistic": statistic, "n": int(arr.size),
            "estimate": ci.estimate, "low": ci.low, "high": ci.high, "extra": extra, "bound": bound,
            "verdict": verdict_fn(ci), "note": ci.note}


def _paired_row(test: str, condition: str, mode: str, statistic: str, a: Mapping[int, float], b: Mapping[int, float],
                n_boot: int, bound: str, expect: str) -> Dict[str, Any]:
    """``b - a`` paired by seed with Cliff's delta; ``expect`` is "up", "down" or "unchanged" (TOST)."""
    seeds = sorted(s for s in a if s in b and not math.isnan(a[s]) and not math.isnan(b[s]))
    va = np.array([a[s] for s in seeds], dtype=np.float64)
    vb = np.array([b[s] for s in seeds], dtype=np.float64)
    if len(seeds) < 2:
        return {"test": test, "condition": condition, "mode": mode, "statistic": statistic, "n": len(seeds), "estimate": math.nan,
                "low": math.nan, "high": math.nan, "extra": "", "bound": bound, "verdict": "undefined", "note": "fewer than two seeds"}
    eff = paired_effect(va, vb, n_boot=n_boot, seed=_stat_seed(test, condition, mode, statistic, "paired"))
    delta = cliffs_delta(va, vb, n_boot=n_boot, seed=_stat_seed(test, condition, mode, statistic, "cliff"))
    extra = f"delta {delta['delta']:+.3f} [{delta['low']:+.3f}, {delta['high']:+.3f}] ({delta['magnitude']}); mean_a {eff['mean_a']:.4g}, mean_b {eff['mean_b']:.4g}"
    notes = [n for n in (eff["note"], delta["note"]) if n]
    if expect == "up":
        verdict = "passes" if (delta["delta"] >= DELTA_BOUND and eff["low"] > 0.0) else "fails"
    elif expect == "down":
        verdict = "passes" if (delta["delta"] <= -DELTA_BOUND and eff["high"] < 0.0) else "fails"
    else:
        if np.all(va == va[0]) and np.all(vb == vb[0]) and va[0] == vb[0]:
            verdict, extra = "degenerate (every value identical)", extra + "; rates constant"
        elif abs(float(va.mean())) < 1e-12:
            # A baseline rate of 0 has no relative equivalence bound; the paired difference above is the reading.
            verdict, extra = "degenerate (baseline rate 0: relative TOST undefined)", extra + "; mean_a 0"
        else:
            eq = tost(va, vb, -TOST_RELATIVE, TOST_RELATIVE, relative=True, paired=True, n_boot=n_boot,
                      seed=_stat_seed(test, condition, mode, statistic, "tost"))
            verdict = "equivalent (TOST)" if eq["equivalent"] else "not shown equivalent (TOST)"
            extra += (f"; tost {eq['ci_level']:.0%} CI [{eq['ci_low']:.4g}, {eq['ci_high']:.4g}] against bounds "
                      f"[{eq['bound_low']:.4g}, {eq['bound_high']:.4g}]")
            if eq.get("note"):
                notes.append(str(eq["note"]))
    return {"test": test, "condition": condition, "mode": mode, "statistic": statistic, "n": len(seeds),
            "estimate": eff["mean_diff"], "low": eff["low"], "high": eff["high"], "extra": extra, "bound": bound,
            "verdict": verdict, "note": "; ".join(notes)}


def _slope_rows(pauses: Sequence[Mapping[str, Any]], condition: str, mode: str, metric: str, n_boot: int,
                cell: Cell = (FOUR_BLOCK, 0), test: str = "c_familiarity") -> Dict[str, Any]:
    """(c) per-seed slope of ``metric`` per stop against lap within the (session, block) ``cell`` (reward pauses, both ends)."""
    session, block = cell
    slopes: Dict[int, float] = {}
    seeds = sorted({int(p["seed"]) for p in pauses if p["condition"] == condition and p["mode"] == mode})
    for seed in seeds:
        sel = [p for p in pauses if p["condition"] == condition and p["mode"] == mode and int(p["seed"]) == seed
               and p["session"] == session and int(p["block"]) == block and p["trigger"] == TRIGGER_REWARD]
        xs = [float(p["lap"]) for p in sel]
        ys = [float(p[metric]) for p in sel]
        if len(xs) < 2:
            continue
        mx, my = math.fsum(xs) / len(xs), math.fsum(ys) / len(ys)
        sxx = math.fsum((x - mx) ** 2 for x in xs)
        slopes[seed] = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else math.nan
    return _ci_row(test, condition, mode, f"slope_of_{metric}_vs_lap_{cell_label(session, block)}", slopes, n_boot,
                   "slope < 0, interval excluding 0", lambda ci: "passes" if ci.high < 0.0 else "fails")


def _first_zero_rows(pauses: Sequence[Mapping[str, Any]], condition: str, mode: str, n_boot: int,
                     cell: Cell = (FOUR_BLOCK, 0), test: str = "c_familiarity") -> Dict[str, Any]:
    """(c), change 3: per seed, the first lap of the ``cell`` at which the reward pause made no backup (NaN if never)."""
    session, block = cell
    firsts: Dict[int, float] = {}
    seeds = sorted({int(p["seed"]) for p in pauses if p["condition"] == condition and p["mode"] == mode})
    for seed in seeds:
        sel = sorted((int(p["lap"]), int(p["n_backups"])) for p in pauses if p["condition"] == condition and p["mode"] == mode
                     and int(p["seed"]) == seed and p["session"] == session and int(p["block"]) == block and p["trigger"] == TRIGGER_REWARD)
        zero = [lap for lap, n in sel if n == 0]
        firsts[seed] = float(zero[0]) if zero else math.nan
    n_reached = sum(1 for v in firsts.values() if not math.isnan(v))
    verdict = f"reaches 0 at {n_reached} of {len(firsts)} seeds"
    return _ci_row(test, condition, mode, f"first_lap_with_zero_backups_{cell_label(session, block)}", firsts, n_boot,
                   "reported", lambda ci: verdict, extra=f"seeds reaching 0: {n_reached}", undefined=verdict)


def _tests_four_block(seed_blocks, pauses, condition: str, modes: Sequence[str], n_boot: int) -> List[Dict[str, Any]]:
    """Steps 2 and 3: the tests on the four-block protocol (unchanged from G28/G29)."""
    rows: List[Dict[str, Any]] = []
    gt = lambda bound: (lambda ci: "passes" if ci.low > bound else ("fails" if ci.estimate <= bound else "estimate above, interval not"))  # noqa: E731
    cells = lambda *blocks: tuple((FOUR_BLOCK, b) for b in blocks)  # noqa: E731
    if "fixed" in modes:
        # (a) direction by window: blocks 1 and 3 (unchanged rewards), both ends.
        rev = _per_seed(seed_blocks, condition, "fixed", "reverse_share", cells=cells(0, 2), ends=ENDS, trigger=TRIGGER_REWARD)
        rows.append(_ci_row("a_direction", condition, "fixed", "reverse_share_reward_pauses", rev, n_boot, f"> {DIRECTION_BOUND}", gt(DIRECTION_BOUND)))
        fwd = _per_seed(seed_blocks, condition, "fixed", "forward_share", cells=cells(0, 2), ends=ENDS, trigger=TRIGGER_PRE_RUN)
        rows.append(_ci_row("a_direction", condition, "fixed", "forward_share_pre_run_pauses", fwd, n_boot, f"> {DIRECTION_BOUND}", gt(DIRECTION_BOUND)))
        # (d) remote events: all pauses, all blocks.
        rem_r = _per_seed(seed_blocks, condition, "fixed", "remote_share", cells=cells(0, 1, 2, 3), ends=ENDS, trigger=TRIGGER_REWARD)
        rem_p = _per_seed(seed_blocks, condition, "fixed", "remote_share", cells=cells(0, 1, 2, 3), ends=ENDS, trigger=TRIGGER_PRE_RUN)
        rows.append(_ci_row("d_remote", condition, "fixed", "remote_share_reward_pauses", rem_r, n_boot, f">= {REMOTE_BOUND}",
                            lambda ci: "passes" if ci.estimate >= REMOTE_BOUND else "fails"))
        rows.append(_ci_row("d_remote", condition, "fixed", "remote_share_pre_run_pauses", rem_p, n_boot, f">= {REMOTE_BOUND}",
                            lambda ci: "passes" if ci.estimate >= REMOTE_BOUND else "fails"))
    if "thresholded" in modes:
        # (b) rate and reward change at the east end (reward pauses), the west end as the control.
        for metric in ("reverse_per_stop", "backups_per_stop", "events_per_stop"):
            for end in ENDS:
                pre = _per_seed(seed_blocks, condition, "thresholded", metric, cells=cells(0), ends=(end,), trigger=TRIGGER_REWARD)
                inc = _per_seed(seed_blocks, condition, "thresholded", metric, cells=cells(1), ends=(end,), trigger=TRIGGER_REWARD)
                wash = _per_seed(seed_blocks, condition, "thresholded", metric, cells=cells(2), ends=(end,), trigger=TRIGGER_REWARD)
                dec = _per_seed(seed_blocks, condition, "thresholded", metric, cells=cells(3), ends=(end,), trigger=TRIGGER_REWARD)
                if end == "east":
                    rows.append(_paired_row("b_rate_increase", condition, "thresholded", f"{metric}_east_block2_minus_block1", pre, inc, n_boot,
                                            f"up: delta >= {DELTA_BOUND}, interval > 0", "up"))
                    rows.append(_paired_row("b_rate_decrease", condition, "thresholded", f"{metric}_east_block4_minus_block3", wash, dec, n_boot,
                                            f"down: delta <= -{DELTA_BOUND}, interval < 0", "down"))
                    # Exploratory, not preregistered (G29): the decrease against the baseline block, because the
                    # washout block carries its own surprise (|dr| 3.0 against the decrease's 0.75), so a rule whose
                    # rate follows the size of the surprise can pass "down" against it for a magnitude reason.
                    rows.append(_paired_row("b_rate_decrease_vs_baseline_exploratory", condition, "thresholded",
                                            f"{metric}_east_block4_minus_block1", pre, dec, n_boot,
                                            f"exploratory: down: delta <= -{DELTA_BOUND}, interval < 0", "down"))
                else:
                    rows.append(_paired_row("b_control_end", condition, "thresholded", f"{metric}_west_block2_minus_block1", pre, inc, n_boot,
                                            f"unchanged: TOST +-{TOST_RELATIVE:.0%}", "unchanged"))
                    rows.append(_paired_row("b_control_end", condition, "thresholded", f"{metric}_west_block4_minus_block3", wash, dec, n_boot,
                                            f"unchanged: TOST +-{TOST_RELATIVE:.0%}", "unchanged"))
        fpre = _per_seed(seed_blocks, condition, "thresholded", "forward_per_stop", cells=cells(0), ends=("east",), trigger=TRIGGER_REWARD)
        finc = _per_seed(seed_blocks, condition, "thresholded", "forward_per_stop", cells=cells(1), ends=("east",), trigger=TRIGGER_REWARD)
        rows.append(_paired_row("b_forward_unchanged", condition, "thresholded", "forward_per_stop_east_block2_minus_block1", fpre, finc, n_boot,
                                f"unchanged: TOST +-{TOST_RELATIVE:.0%}", "unchanged"))
        # (c) familiarity within block 1 and, since step 3 (change 3), within block 3 too, with the first lap at 0.
        for block in (0, 2):
            rows.append(_slope_rows(pauses, condition, "thresholded", "n_backups", n_boot, (FOUR_BLOCK, block)))
            rows.append(_slope_rows(pauses, condition, "thresholded", "n_events", n_boot, (FOUR_BLOCK, block)))
            rows.append(_first_zero_rows(pauses, condition, "thresholded", n_boot, (FOUR_BLOCK, block)))
    return rows


# Step 4's cells. The two sessions share their baseline block (same seed, same 20 laps), so a pooled statistic counts
# it once, through the increase session's.
BASELINE_CELL: Cell = ("increase", 0)
CHANGE_CELLS: Dict[str, Cell] = {"increase": ("increase", 1), "decrease": ("decrease", 1)}
DISTINCT_CELLS: Tuple[Cell, ...] = (BASELINE_CELL, CHANGE_CELLS["increase"], CHANGE_CELLS["decrease"])


def _tests_step4(seed_blocks, pauses, condition: str, modes: Sequence[str], n_boot: int, versus_control: bool = False) -> List[Dict[str, Any]]:
    """Step 4 (docs/prereg/rq1_track_step4.md): (a) on the baseline block, (d) over the three distinct blocks, (b) each
    change against the baseline that precedes it in its session, (c) within the baseline block (preregistered) and,
    labelled ``c_after_change``, within each changed block. ``versus_control`` (step 5, G30 C2) adds the (b) rate tests
    as the east change minus the west change, (east block 2 − block 1) − (west block 2 − block 1), paired by seed, and
    the reverse share at the reward pauses of the changed blocks (``a_direction_after_change``)."""
    rows: List[Dict[str, Any]] = []
    gt = lambda bound: (lambda ci: "passes" if ci.low > bound else ("fails" if ci.estimate <= bound else "estimate above, interval not"))  # noqa: E731
    if "fixed" in modes:
        rev = _per_seed(seed_blocks, condition, "fixed", "reverse_share", cells=(BASELINE_CELL,), ends=ENDS, trigger=TRIGGER_REWARD)
        rows.append(_ci_row("a_direction", condition, "fixed", "reverse_share_reward_pauses_baseline", rev, n_boot, f"> {DIRECTION_BOUND}", gt(DIRECTION_BOUND)))
        fwd = _per_seed(seed_blocks, condition, "fixed", "forward_share", cells=(BASELINE_CELL,), ends=ENDS, trigger=TRIGGER_PRE_RUN)
        rows.append(_ci_row("a_direction", condition, "fixed", "forward_share_pre_run_pauses_baseline", fwd, n_boot, f"> {DIRECTION_BOUND}", gt(DIRECTION_BOUND)))
        rem_r = _per_seed(seed_blocks, condition, "fixed", "remote_share", cells=DISTINCT_CELLS, ends=ENDS, trigger=TRIGGER_REWARD)
        rem_p = _per_seed(seed_blocks, condition, "fixed", "remote_share", cells=DISTINCT_CELLS, ends=ENDS, trigger=TRIGGER_PRE_RUN)
        rows.append(_ci_row("d_remote", condition, "fixed", "remote_share_reward_pauses", rem_r, n_boot, f">= {REMOTE_BOUND}",
                            lambda ci: "passes" if ci.estimate >= REMOTE_BOUND else "fails"))
        rows.append(_ci_row("d_remote", condition, "fixed", "remote_share_pre_run_pauses", rem_p, n_boot, f">= {REMOTE_BOUND}",
                            lambda ci: "passes" if ci.estimate >= REMOTE_BOUND else "fails"))
        if versus_control:
            changed = tuple(CHANGE_CELLS.values())
            rev_c = _per_seed(seed_blocks, condition, "fixed", "reverse_share", cells=changed, ends=ENDS, trigger=TRIGGER_REWARD)
            rows.append(_ci_row("a_direction_after_change", condition, "fixed", "reverse_share_reward_pauses_changed_blocks", rev_c, n_boot,
                                f"> {DIRECTION_BOUND}", gt(DIRECTION_BOUND)))
            fwd_c = _per_seed(seed_blocks, condition, "fixed", "forward_share", cells=changed, ends=ENDS, trigger=TRIGGER_PRE_RUN)
            rows.append(_ci_row("a_direction_after_change", condition, "fixed", "forward_share_pre_run_pauses_changed_blocks", fwd_c, n_boot,
                                f"> {DIRECTION_BOUND}", gt(DIRECTION_BOUND)))
    if "thresholded" in modes:
        for metric in ("reverse_per_stop", "backups_per_stop", "events_per_stop"):
            for session, expect in (("increase", "up"), ("decrease", "down")):
                changes: Dict[str, Dict[int, float]] = {}
                for end in ENDS:
                    pre = _per_seed(seed_blocks, condition, "thresholded", metric, cells=((session, 0),), ends=(end,), trigger=TRIGGER_REWARD)
                    post = _per_seed(seed_blocks, condition, "thresholded", metric, cells=((session, 1),), ends=(end,), trigger=TRIGGER_REWARD)
                    changes[end] = {s: post[s] - pre[s] for s in pre if s in post}
                    stat = f"{metric}_{end}_{session}_block2_minus_block1"
                    if end == "east":
                        sign = ">=" if expect == "up" else "<="
                        rows.append(_paired_row("b_rate_increase" if expect == "up" else "b_rate_decrease", condition, "thresholded", stat,
                                                pre, post, n_boot, f"{expect}: delta {sign} {'' if expect == 'up' else '-'}{DELTA_BOUND}, interval {'>' if expect == 'up' else '<'} 0", expect))
                    else:
                        rows.append(_paired_row("b_control_end", condition, "thresholded", stat, pre, post, n_boot,
                                                f"unchanged: TOST +-{TOST_RELATIVE:.0%}", "unchanged"))
                if versus_control:
                    # The time control (G30 C2): the east change minus the west change, paired by seed (b - a = east - west).
                    sign = ">=" if expect == "up" else "<="
                    rows.append(_paired_row("b_rate_increase_vs_control" if expect == "up" else "b_rate_decrease_vs_control", condition, "thresholded",
                                            f"{metric}_east_minus_west_change_{session}", changes["west"], changes["east"], n_boot,
                                            f"{expect}: delta {sign} {'' if expect == 'up' else '-'}{DELTA_BOUND}, interval {'>' if expect == 'up' else '<'} 0", expect))
        for session in ("increase", "decrease"):
            fpre = _per_seed(seed_blocks, condition, "thresholded", "forward_per_stop", cells=((session, 0),), ends=("east",), trigger=TRIGGER_REWARD)
            fpost = _per_seed(seed_blocks, condition, "thresholded", "forward_per_stop", cells=((session, 1),), ends=("east",), trigger=TRIGGER_REWARD)
            rows.append(_paired_row("b_forward_unchanged", condition, "thresholded", f"forward_per_stop_east_{session}_block2_minus_block1",
                                    fpre, fpost, n_boot, f"unchanged: TOST +-{TOST_RELATIVE:.0%}", "unchanged"))
        for cell in DISTINCT_CELLS:
            test = "c_familiarity" if cell == BASELINE_CELL else "c_after_change"
            rows.append(_slope_rows(pauses, condition, "thresholded", "n_backups", n_boot, cell, test))
            rows.append(_slope_rows(pauses, condition, "thresholded", "n_events", n_boot, cell, test))
            rows.append(_first_zero_rows(pauses, condition, "thresholded", n_boot, cell, test))
    return rows


def rq1_tests(seed_blocks: Sequence[Mapping[str, Any]], pauses: Sequence[Mapping[str, Any]], conditions: Sequence[str],
              modes: Sequence[str], n_boot: int, version: str = DEFAULT_VERSION) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for condition in conditions:
        if condition == RULE_NONE:
            continue
        if version in ("step4", "step5"):
            rows.extend(_tests_step4(seed_blocks, pauses, condition, modes, n_boot, versus_control=(version == "step5")))
        else:
            rows.extend(_tests_four_block(seed_blocks, pauses, condition, modes, n_boot))
    return rows


LEARNING_COLUMNS = ("mode", "session", "condition", "n", "mean_total_steps", "low", "high", "laps_capped_total", "vs", "mean_diff",
                    "diff_low", "diff_high", "fraction_faster", "cliffs_delta", "cliffs_low", "cliffs_high", "cliffs_magnitude", "note")


def learning_rows(runs_by_key: Mapping[Tuple[str, str], Sequence[SeedRun]], n_boot: int) -> List[Dict[str, Any]]:
    """Learning speed over a session: per (mode, session) and condition the mean total steps over its laps with its
    interval, and the paired difference against ``none`` and against ``prioritised_td`` (the prereg's last prediction)."""
    out: List[Dict[str, Any]] = []
    for (mode, session), runs in runs_by_key.items():
        totals: Dict[str, Dict[int, float]] = {}
        capped: Dict[str, int] = {}
        for run in runs:
            totals.setdefault(run.condition, {})[run.seed] = float(sum(lap.steps for lap in run.laps))
            capped[run.condition] = capped.get(run.condition, 0) + sum(not lap.rewarded for lap in run.laps)
        for condition in [c for c in ALL_CONDITIONS if c in totals]:
            seeds = sorted(totals[condition])
            arr = np.array([totals[condition][s] for s in seeds], dtype=np.float64)
            ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed("learning", mode, session, condition))
            base = {"mode": mode, "session": session, "condition": condition, "n": int(arr.size), "mean_total_steps": ci.estimate,
                    "low": ci.low, "high": ci.high, "laps_capped_total": capped[condition]}
            for reference in (RULE_NONE, "prioritised_td"):
                if condition == RULE_NONE or reference == condition or reference not in totals:
                    continue  # none is the baseline: its row is the summary alone
                ref = np.array([totals[reference][s] for s in seeds], dtype=np.float64)
                eff = paired_effect(ref, arr, n_boot=n_boot, seed=_stat_seed("learning", mode, session, condition, reference))
                delta = cliffs_delta(ref, arr, n_boot=n_boot, seed=_stat_seed("learning_cliff", mode, session, condition, reference))
                out.append({**base, "vs": reference, "mean_diff": eff["mean_diff"], "diff_low": eff["low"], "diff_high": eff["high"],
                            "fraction_faster": float(np.mean(arr < ref)), "cliffs_delta": delta["delta"], "cliffs_low": delta["low"],
                            "cliffs_high": delta["high"], "cliffs_magnitude": delta["magnitude"],
                            "note": "; ".join(n for n in (eff["note"], delta["note"]) if n)})
            if condition == RULE_NONE:
                out.append({**base, "vs": "", "mean_diff": math.nan, "diff_low": math.nan, "diff_high": math.nan, "fraction_faster": math.nan,
                            "cliffs_delta": math.nan, "cliffs_low": math.nan, "cliffs_high": math.nan, "cliffs_magnitude": "", "note": ""})
    return out


ADAPTATION_COLUMNS = ("condition", "mode", "session", "block", "block_name", "lap_in_block", "n", "mean_steps", "low", "high", "median_steps", "fraction_capped")


def adaptation_rows(runs: Sequence[SeedRun], mode: str, n_boot: int, session: str = FOUR_BLOCK) -> List[Dict[str, Any]]:
    """Steps per lap by block and lap-in-block, per condition, for the runs of one ``mode`` and ``session``: how fast each re-learns a changed reward."""
    by: Dict[Tuple[str, str, int, int], List[Tuple[float, bool]]] = {}
    for run in runs:
        starts: Dict[int, int] = {}
        for lap in run.laps:
            starts.setdefault(lap.block, lap.lap)
            by.setdefault((run.condition, mode, lap.block, lap.lap - starts[lap.block] + 1), []).append((float(lap.steps), lap.rewarded))
    out: List[Dict[str, Any]] = []
    for (condition, mode, block, k), values in sorted(by.items(), key=lambda kv: (ALL_CONDITIONS.index(kv[0][0]), kv[0][1:])):
        arr = np.array([v for v, _ in values], dtype=np.float64)
        ci = bootstrap_ci(arr, np.mean, n_boot=n_boot, seed=_stat_seed("adapt", condition, mode, session, block, k))
        out.append({"condition": condition, "mode": mode, "session": session, "block": block,
                    "block_name": block_name(session, block), "lap_in_block": k,
                    "n": int(arr.size), "mean_steps": ci.estimate, "low": ci.low, "high": ci.high,
                    "median_steps": float(np.median(arr)), "fraction_capped": float(np.mean([not r for _, r in values]))})
    return out


# --- the theta pilot (steps 3 and 4's change 2) ---------------------------------------------------------


PILOT_COLUMNS = ("version", "condition", "statistic", "n_pauses", "theta", "min", "max", "laps", "seeds")


def pilot_rows(version: str, seeds: Sequence[int] = PILOT_SEEDS, workers: Optional[int] = None, quick: bool = False,
               conditions: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """The preregistered pilot that sets a version's thresholded theta per rule: fixed mode, the baseline block alone,
    ``seeds``; per rule the median of its priority read before the reward pause over the second half of the block
    (laps 11-20 of 20), divided by the value scale read then when the version scales its theta and the rule's
    priority is in value units (step 4). ``quick``: a 2-lap block, its second lap."""
    if version not in VERSIONS:
        raise ValueError(f"version must be one of {VERSIONS}, got {version!r}")
    session = next(iter(SESSIONS[version]))
    cfg = protocol_config("fixed", quick, version=version, session=session)
    baseline = cfg.blocks()[0]
    cfg = replace(cfg, laps=baseline[0], reward_blocks=(baseline,))
    first_lap = cfg.laps // 2 + 1  # laps 11-20 of 20
    out: List[Dict[str, Any]] = []
    for c in conditions or [c for c in version_conditions(version) if c != RULE_NONE]:
        scaled = cfg.threshold_scale == "mean_abs_value" and condition_is_value_scaled(c)
        values: List[float] = []
        for run in run_all((c,), seeds, cfg, workers):
            for lap in run.laps:
                if lap.lap >= first_lap and lap.rewarded and not math.isnan(lap.reward_priority_before):
                    v = lap.reward_priority_before
                    if scaled:
                        v = v / max(lap.reward_value_scale, cfg.threshold_scale_floor)
                    values.append(v)
        out.append({"version": version, "condition": c, "statistic": "priority / value_scale" if scaled else "priority",
                    "n_pauses": len(values), "theta": float(np.median(values)) if values else math.nan,
                    "min": min(values) if values else math.nan, "max": max(values) if values else math.nan,
                    "laps": f"{first_lap}-{cfg.laps}", "seeds": ",".join(str(s) for s in seeds)})
    return out


# --- the run --------------------------------------------------------------------------------------------


OUTPUT_FILES = ("rq1_pauses.csv.gz", "rq1_seed_blocks.csv", "rq1_tests.csv", "rq1_adaptation.csv", "rq1_learning.csv", "rq1_manifest.json")
EVENTS_FILE = "rq1_events.jsonl.gz"  # written with --write-events only (the pause table carries the counts)
PILOT_FILE = "rq1_pilot.csv"


def write_csv_gz(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    """``write_csv`` into a gzip file with a fixed header time, so two runs write identical bytes."""
    import csv
    import io

    from experiments.linear_track_replay import _fmt

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _fmt(row.get(k)) for k in columns})
    with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as fh:
        fh.write(buffer.getvalue().encode("utf-8"))


def read_csv_gz(path: Path) -> List[Dict[str, Any]]:
    import csv

    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_events(path: Path, events: Iterable[Mapping[str, Any]]) -> int:
    written = 0
    with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as fh:
        for event in events:
            fh.write((json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
            written += 1
    return written


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", choices=VERSIONS, default=DEFAULT_VERSION,
                        help="step2: the four floors, one theta, the 'next' trajectory priority (G28); step3: seven conditions, "
                             "theta per rule, 'remaining_max' (G29); step4: two sessions per seed, theta scaled by the value scale (G30); "
                             "step5: step 4's protocol on the Q learner with the floors and the Mattar & Daw rules (default)")
    parser.add_argument("--modes", default=",".join(BUDGET_MODES))
    parser.add_argument("--conditions", default=None, help="comma-separated; default: the version's set")
    parser.add_argument("--sessions", default=None, help="comma-separated; default: the version's set")
    parser.add_argument("--theta", action="append", default=[], metavar="CONDITION=VALUE", help="override a rule's thresholded theta")
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEEDS[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--quick", action="store_true", help="blocks of 2 laps, 200 replicates; needs --out")
    parser.add_argument("--pilot", action="store_true",
                        help=f"run the version's theta pilot instead (fixed mode, the baseline block, seeds 1-3 unless --seeds/--seed-start) and write {PILOT_FILE}")
    parser.add_argument("--write-events", action="store_true", help=f"also write every replay with its cells to {EVENTS_FILE} (several MB for the full run)")
    parser.add_argument("--out", type=Path, default=None, help="output directory (default: the version's committed directory)")
    args = parser.parse_args(argv)
    version = args.version
    conditions_of_version = version_conditions(version)
    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    conditions = conditions_of_version if args.conditions is None else tuple(c.strip() for c in args.conditions.split(",") if c.strip())
    sessions_of_version = tuple(SESSIONS[version])
    sessions = sessions_of_version if args.sessions is None else tuple(s.strip() for s in args.sessions.split(",") if s.strip())
    for m in modes:
        if m not in BUDGET_MODES:
            parser.error(f"unknown mode {m!r}")
    for c in conditions:
        if c not in ALL_CONDITIONS:
            parser.error(f"unknown condition {c!r}")
    for s in sessions:
        if s not in sessions_of_version:
            parser.error(f"unknown session {s!r} for {version}; one of {sessions_of_version}")
    overrides: Dict[str, float] = {}
    for item in args.theta:
        name, sep, value = item.partition("=")
        if not sep or name not in ALL_CONDITIONS:
            parser.error(f"--theta expects CONDITION=VALUE with a known condition, got {item!r}")
        overrides[name] = float(value)
    default_out = DEFAULT_OUTS[version]
    if args.out is None:
        args.out = default_out
    if args.pilot:
        # The pilot is written beside the version's tables (its own file) or wherever --out says.
        seeds = list(range(args.seed_start, args.seed_start + args.seeds)) if (args.seeds != len(DEFAULT_SEEDS) or args.seed_start != DEFAULT_SEEDS[0]) else list(PILOT_SEEDS)
        pilot_conditions = None if args.conditions is None else [c for c in conditions if c != RULE_NONE]
        rows = pilot_rows(version, seeds, args.workers, args.quick, pilot_conditions)
        args.out.mkdir(parents=True, exist_ok=True)
        write_csv(args.out / PILOT_FILE, PILOT_COLUMNS, rows)
        print(f"theta pilot, {version} ({PREREGS[version]}): fixed mode, the baseline block, seeds {seeds}")
        for r in rows:
            print(f"  {r['condition']:20s} {r['statistic']:24s} n {r['n_pauses']:>3} theta {r['theta']:.6g} (min {r['min']:.4g}, max {r['max']:.4g}) laps {r['laps']}")
        print(f"wrote {PILOT_FILE} to {args.out}")
        return {"pilot": rows}
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    full = (modes == BUDGET_MODES and conditions == conditions_of_version and sessions == sessions_of_version
            and tuple(seeds) == DEFAULT_SEEDS and not args.quick and n_boot >= 1000 and not overrides)
    if args.out.resolve() in {p.resolve() for p in DEFAULT_OUTS.values()} and not (full and args.out.resolve() == default_out.resolve()):
        parser.error(f"a partial run (or another version's) must not overwrite the committed tables in {args.out}: give --out")
    started = time.perf_counter()
    runs_by_key: Dict[Tuple[str, str], List[SeedRun]] = {}
    pauses: List[Dict[str, Any]] = []
    events: List[Mapping[str, Any]] = []
    # One config per (mode, condition, session): the thresholded theta is the rule's own since step 3.
    configs: Dict[Tuple[str, str, str], TrackConfig] = {}
    thetas: Dict[str, float] = {}
    for mode in modes:
        for c in conditions:
            theta = theta_for(c, version, overrides) if (mode == "thresholded" and c != RULE_NONE) else None
            if theta is not None:
                thetas[c] = theta
            for s in sessions:
                configs[(mode, c, s)] = protocol_config(mode, args.quick, version=version, theta=theta, session=s)
    guard: Dict[str, Any] = {}
    for mode in modes:
        for s in sessions:
            key_runs: List[SeedRun] = []
            for c in conditions:
                key_runs.extend(run_all((c,), seeds, configs[(mode, c, s)], args.workers))
            runs_by_key[(mode, s)] = key_runs
            for run in key_runs:
                pauses.extend(pause_rows(run, mode, configs[(mode, run.condition, s)], s))
                events.extend({**e, "mode": mode, "session": s} for e in run.events)
            for c in conditions:
                vectors = [{"seed": r.seed, "steps": [lap.steps for lap in r.laps]} for r in key_runs if r.condition == c]
                verdict = pseudo_replication_guard(vectors, key="steps", allow=True)
                guard[f"{mode}/{s}/{c}"] = {"distinct": verdict if isinstance(verdict, int) else None, "n": len(vectors),
                                            "message": verdict if isinstance(verdict, str) else ""}
    runs: List[SeedRun] = [r for key in runs_by_key for r in runs_by_key[key]]
    seed_blocks = seed_block_rows(pauses)
    tests = rq1_tests(seed_blocks, pauses, conditions, modes, n_boot, version)
    adaptation: List[Dict[str, Any]] = []
    for (mode, s), key_runs in runs_by_key.items():
        adaptation.extend(adaptation_rows(key_runs, mode, n_boot, s))
    base_cfg = configs[(modes[0], conditions[0], sessions[0])]
    manifest = build_manifest(
        base_cfg, protocol="linear_track_rq1", seeds=seeds,
        ticks_requested=sum(cfg.laps * cfg.lap_cap for cfg in configs.values()),
        extra={"version": version, "modes": list(modes), "conditions": list(conditions), "sessions": list(sessions),
               "configs": {f"{m}/{s}/{c}": configs[(m, c, s)].to_dict() for m in modes for s in sessions for c in conditions},
               "blocks": [list(b) for b in base_cfg.blocks()],  # the first session's; every session's are under session_blocks
               "session_blocks": {s: [list(b) for b in SESSIONS[version][s]] for s in sessions},
               "block_names": list(SESSION_BLOCK_NAMES[sessions[0]]),
               "session_block_names": {s: list(SESSION_BLOCK_NAMES[s]) for s in sessions},
               "threshold": THRESHOLD if version == "step2" else None, "thetas": thetas, "backup_cap": BACKUP_CAP,
               "threshold_scale": base_cfg.threshold_scale, "learner": base_cfg.learner,
               "trajectory_priority": base_cfg.trajectory_priority,
               "n_boot": n_boot, "full_evaluation": full, "quick": args.quick,
               "prereg": PREREGS[version],
               "dependencies": _dependency_versions(),
               "command": "python3 -m experiments.linear_track_rq1 " + " ".join(list(argv) if argv is not None else sys.argv[1:])},
    )
    manifest["guard"] = guard
    manifest["workers"] = args.workers if args.workers is not None else os.cpu_count()
    finish_manifest(manifest, ticks_run=sum(lap.steps for r in runs for lap in r.laps), wall_seconds=time.perf_counter() - started)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_csv_gz(out / OUTPUT_FILES[0], PAUSE_COLUMNS, pauses)
    write_csv(out / OUTPUT_FILES[1], SEED_BLOCK_COLUMNS, seed_blocks)
    write_csv(out / OUTPUT_FILES[2], TEST_COLUMNS, tests)
    write_csv(out / OUTPUT_FILES[3], ADAPTATION_COLUMNS, adaptation)
    learning = learning_rows(runs_by_key, n_boot)
    write_csv(out / OUTPUT_FILES[4], LEARNING_COLUMNS, learning)
    written = [out / name for name in OUTPUT_FILES]
    if args.write_events:
        write_events(out / EVENTS_FILE, events)
        written.append(out / EVENTS_FILE)
    write_manifest(out / OUTPUT_FILES[5], manifest)
    print(f"preregistered tests ({PREREGS[version]}):")
    for t in tests:
        est = "nan" if math.isnan(t["estimate"]) else f"{t['estimate']:.4g} [{t['low']:.4g}, {t['high']:.4g}]"
        print(f"  {t['test']:18s} {t['condition']:20s} {t['mode']:11s} {t['statistic']:52s} n {t['n']:>2} {est:34s} {t['verdict']}")
    print("learning speed (total steps over a session, paired against none):")
    for row in learning:
        if row["vs"] == RULE_NONE:
            print(f"  {row['mode']:11s} {row['session']:10s} {row['condition']:20s} {row['mean_total_steps']:8.0f} steps; vs none {row['mean_diff']:+8.0f} "
                  f"[{row['diff_low']:+8.0f}, {row['diff_high']:+8.0f}], faster on {row['fraction_faster']:.2f} of seeds")
    print(f"guard: {guard}")
    print(f"wrote {', '.join(p.name for p in written)} to {out} in {manifest['timing']['wall_seconds']:.1f} s")
    return {"pauses": pauses, "seed_blocks": seed_blocks, "tests": tests, "adaptation": adaptation, "learning": learning,
            "guard": guard, "runs_by_key": runs_by_key, "events": events}


if __name__ == "__main__":
    main()
