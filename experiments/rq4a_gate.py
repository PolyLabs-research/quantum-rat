"""M2b step 4: the RQ4(a) gate, relative to the visible-goal ceiling (docs/prereg/m2b_gate.md).

    python3 -m experiments.rq4a_gate --workers 4                 # 3 sources x 2 sessions x 30 seeds, writes docs/data/m2b/gate
    python3 -m experiments.rq4a_gate --quick --seeds 2 --out /tmp/gate   # the smoke test's run

The plan's RQ4(a): from four start poses in the 2 m open field, with the embodied estimate, the agent reaches a learned
goal within 60 s. By the owner's decision of 2026-10-25 (decisions G36) the gate is relative: the hidden-goal success
rate after 20 trials as a share of the same agent's visible-goal success rate from the same starts, so that it measures
what M2b built (the estimate, the place code and its value) rather than the motor policy, whose visible-goal ceiling a
probe put at 13 of 20 (docs/m2b_place_code.md). Both absolute rates are reported.

Every run: step 1's M2b estimate (heading oracle sigma 0.05, wall-contact reset), step 2's 400-cell population, a goal
of radius 1 unit (0.1 m) at (5, 5) units, four start poses 1 unit from each wall's midpoint facing the centre, the
order shuffled per block of four from a protocol stream (the same order in every session and source of a seed), the
body placed and the estimate re-anchored at each start (the agent knows where it is put down: declared), and an
episode boundary for every value learner. 40 trials of up to 300 ticks (60 s). ``hidden`` session: the goal is hidden;
after a 60 s miss it becomes visible for up to 300 more ticks (guidance, the water maze's convention mapped to an agent
that cannot be carried). ``visible`` session: the goal is visible from the start; a miss ends the trial. Three value
sources steer (``value_memory.source``): ``sr`` (V = M R over the place code, the plan's path), ``tabular`` (the value
map over the estimate's bins, the plan's ablation) and ``none`` (no value steering, the control).

Tables (``--out``): gate_trials.csv (one row per trial), gate_per_seed.csv, gate_curve.csv (success by block of four),
gate_effects.csv (the preregistered tests and the reported comparisons) and gate_manifest.json.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from analysis.stats import bootstrap_ci, cliffs_delta, paired_effect
from core.config import EngineConfig
from core.engine import Engine
from core.rng import RNG
from core.world import WorldObject
from experiments.estimate_correction import ORACLE_NOISE, engine_config
from experiments.linear_track_replay import _dependency_versions, _stat_seed, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

GOAL = (5.0, 5.0)
GOAL_RADIUS = 1.0
STARTS: Tuple[Tuple[float, float, float], ...] = ((-9.0, 0.0, 0.0), (9.0, 0.0, math.pi), (0.0, -9.0, math.pi / 2), (0.0, 9.0, -math.pi / 2))
TRIALS = 40
LEARNING_TRIALS = 20  # the gate reads trials 21-40
TIMEOUT = 300  # 60 s
GUIDE = 300  # the hidden session's visible guidance after a miss
SOURCES: Tuple[str, ...] = ("sr", "tabular", "none")
SESSIONS: Tuple[str, ...] = ("hidden", "visible")
PROTOCOL_STREAM = "gate_protocol"
RATIO_BOUND = 0.80
ERROR_BOUND = 2.0  # units (0.2 m)
DEFAULT_SEEDS: Tuple[int, ...] = tuple(range(1, 31))
DEFAULT_OUT = Path("docs/data/m2b/gate")
DEFAULT_N_BOOT = 10_000
QUICK_TRIALS = 8
# The preregistrations a run can answer to, with the settings each fixes (decisions G36): the gate as first
# preregistered, and the confirmatory gate on fresh seeds with the per-feature reward rule written after its failure.
DEFAULT_PREREG = "docs/prereg/m2b_gate.md"
# Both ran the SR's reward rule with one rate for rewarded and unrewarded ticks (``reward_unlearning_rate`` None): the
# gate sets that explicitly, so it reproduces as registered whatever the research profile's default (decisions G42).
PREREGS: Dict[str, Dict[str, Any]] = {
    DEFAULT_PREREG: {"seeds": DEFAULT_SEEDS, "reward_rule": "nlms", "reward_unlearning_rate": None, "out": DEFAULT_OUT},
    "docs/prereg/m2b_gate_confirmatory.md": {"seeds": tuple(range(31, 61)), "reward_rule": "per_feature",
                                             "reward_unlearning_rate": None,
                                             "out": Path("docs/data/m2b/gate_confirmatory")},
}


def gate_config(source: str, reward_rule: str = "nlms", reward_unlearning_rate: Optional[float] = None) -> EngineConfig:
    """Step 1's M2b estimate, step 2's population, and the value source that steers (``reward_rule``: the SR's R rule;
    "nlms" is the preregistered one, "per_feature" the exploratory one of decisions G36). ``reward_unlearning_rate`` is
    set explicitly (None: one rate, as both gate runs were registered; decisions G41/G42), so the gate does not
    inherit a later change to the research profile's default."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}, got {source!r}")
    cfg = engine_config("oracle_reset", ORACLE_NOISE)
    cfg.place.enabled = True
    cfg.place.reward_rule = reward_rule
    cfg.place.reward_unlearning_rate = reward_unlearning_rate
    cfg.value_memory.source = source
    return cfg


def start_order(seed: int, trials: int) -> List[int]:
    """The start index of every trial: a permutation of the four starts per block, from the protocol stream."""
    stream = RNG(seed=seed).stream(PROTOCOL_STREAM)
    order: List[int] = []
    while len(order) < trials:
        block = [0, 1, 2, 3]
        stream.shuffle(block)
        order.extend(block)
    return order[:trials]


def _reached(eng: Engine) -> bool:
    x, y = eng.agent.pos
    return math.hypot(x - GOAL[0], y - GOAL[1]) <= GOAL_RADIUS


def run_session(source: str, session: str, seed: int, trials: int = TRIALS, reward_rule: str = "nlms",
                reward_unlearning_rate: Optional[float] = None) -> List[Dict[str, Any]]:
    if session not in SESSIONS:
        raise ValueError(f"session must be one of {SESSIONS}")
    eng = Engine(seed=seed, config=gate_config(source, reward_rule, reward_unlearning_rate))
    goal = WorldObject(GOAL[0], GOAL[1], GOAL_RADIUS, "hidden" if session == "hidden" else "target")
    eng.world.add_object(goal)
    rows: List[Dict[str, Any]] = []
    first = True
    for trial, start in enumerate(start_order(seed, trials), start=1):
        sx, sy, sh = STARTS[start]
        a = eng.agent
        a.pos = a.last_pos = (sx, sy)
        a.heading = a.last_heading = sh
        st = eng.spatial.state
        st.grid_x, st.grid_y, st.hd_angle = sx, sy, sh  # the agent knows where it is put down (declared)
        eng.reset_value_episode()
        goal.kind = "hidden" if session == "hidden" else "target"
        latency, guided_latency = None, None
        ticks = 0
        for t in range(TIMEOUT):
            ticks += 1
            eng.run(1, reset=first)
            first = False
            if _reached(eng):
                latency = t + 1
                break
        arrival_error = math.nan
        if latency is not None:
            arrival_error = math.hypot(eng.spatial.state.grid_x - a.pos[0], eng.spatial.state.grid_y - a.pos[1])
        elif session == "hidden":
            goal.kind = "target"  # guidance: the goal shows itself after a miss
            for t in range(GUIDE):
                ticks += 1
                eng.run(1)
                if _reached(eng):
                    guided_latency = TIMEOUT + t + 1
                    break
        rows.append({"source": source, "session": session, "seed": seed, "trial": trial, "start": start,
                     "reached": latency is not None, "latency": latency if latency is not None else "",
                     "guided": latency is None and session == "hidden", "guided_reached": guided_latency is not None,
                     "arrival_error": arrival_error, "ticks": ticks})
    return rows


def _job(args: Tuple[str, str, int, int, str, Optional[float]]) -> List[Dict[str, Any]]:
    return run_session(*args)


def run_all(seeds: Sequence[int], trials: int, workers: Optional[int], sources: Sequence[str] = SOURCES,
            reward_rule: str = "nlms", reward_unlearning_rate: Optional[float] = None) -> List[Dict[str, Any]]:
    jobs = [(src, ses, s, trials, reward_rule, reward_unlearning_rate) for src in sources for ses in SESSIONS for s in seeds]
    if workers == 1 or len(jobs) == 1:
        out = [_job(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            out = list(pool.map(_job, jobs, chunksize=1))
    return [row for rows in out for row in rows]


# --- tables -------------------------------------------------------------------------------------------


TRIAL_COLUMNS = ("source", "session", "seed", "trial", "start", "reached", "latency", "guided", "guided_reached", "arrival_error", "ticks")
PER_SEED_COLUMNS = ("source", "session", "seed", "success_learning", "success_test", "latency_median_test", "arrival_error_median_test",
                    "test_arrivals", "guided_reached_share")
CURVE_COLUMNS = ("source", "session", "block", "n", "success", "low", "high")
EFFECT_COLUMNS = ("test", "statistic", "a", "b", "n", "mean_a", "mean_b", "estimate", "low", "high", "cliffs_delta", "cliffs_low",
                  "cliffs_high", "bound", "verdict", "note")


def per_seed_rows(trials: Sequence[Mapping[str, Any]], learning: int) -> List[Dict[str, Any]]:
    by: Dict[Tuple[str, str, int], List[Mapping[str, Any]]] = {}
    for r in trials:
        by.setdefault((r["source"], r["session"], int(r["seed"])), []).append(r)
    out = []
    for (src, ses, seed), rows in sorted(by.items(), key=lambda kv: (SOURCES.index(kv[0][0]), SESSIONS.index(kv[0][1]), kv[0][2])):
        learn = [r for r in rows if r["trial"] <= learning]
        test = [r for r in rows if r["trial"] > learning]
        hits = [r for r in test if r["reached"]]
        guided = [r for r in rows if r["guided"]]
        out.append({"source": src, "session": ses, "seed": seed,
                    "success_learning": sum(r["reached"] for r in learn) / len(learn) if learn else math.nan,
                    "success_test": sum(r["reached"] for r in test) / len(test) if test else math.nan,
                    "latency_median_test": float(np.median([r["latency"] for r in hits])) if hits else math.nan,
                    "arrival_error_median_test": float(np.median([r["arrival_error"] for r in hits])) if hits else math.nan,
                    "test_arrivals": len(hits),
                    "guided_reached_share": sum(r["guided_reached"] for r in guided) / len(guided) if guided else math.nan})
    return out


def curve_rows(trials: Sequence[Mapping[str, Any]], n_boot: int) -> List[Dict[str, Any]]:
    out = []
    for src in SOURCES:
        for ses in SESSIONS:
            rows = [r for r in trials if r["source"] == src and r["session"] == ses]
            if not rows:
                continue
            seeds = sorted({int(r["seed"]) for r in rows})
            blocks = sorted({(int(r["trial"]) - 1) // 4 + 1 for r in rows})
            for b in blocks:
                per_seed = np.array([np.mean([r["reached"] for r in rows if int(r["seed"]) == s and (int(r["trial"]) - 1) // 4 + 1 == b])
                                     for s in seeds], dtype=np.float64)
                ci = bootstrap_ci(per_seed, np.mean, n_boot=n_boot, seed=_stat_seed("gate_curve", src, ses, b))
                out.append({"source": src, "session": ses, "block": b, "n": len(seeds), "success": ci.estimate, "low": ci.low, "high": ci.high})
    return out


def ratio_ci(hidden: np.ndarray, visible: np.ndarray, n_boot: int, seed: int):
    """mean(hidden) / mean(visible), paired by seed, with a BCa interval: the bootstrap resamples seed indices and the
    statistic maps a resample to the ratio of its means (``bootstrap_ci`` takes one array; the indices are it)."""
    idx = np.arange(hidden.size, dtype=np.float64)

    def stat(sample: np.ndarray) -> float:
        k = sample.astype(np.int64)
        v = float(np.mean(visible[k]))
        return float(np.mean(hidden[k])) / v if v > 0.0 else math.nan

    return bootstrap_ci(idx, stat, n_boot=n_boot, seed=seed)


def effect_rows(per_seed: Sequence[Mapping[str, Any]], n_boot: int) -> List[Dict[str, Any]]:
    base = {k: "" for k in EFFECT_COLUMNS}
    by: Dict[Tuple[str, str], Dict[int, Mapping[str, Any]]] = {}
    for r in per_seed:
        by.setdefault((r["source"], r["session"]), {})[int(r["seed"])] = r
    out: List[Dict[str, Any]] = []

    def values(src: str, ses: str, stat: str) -> Tuple[List[int], np.ndarray]:
        q = by.get((src, ses), {})
        seeds = sorted(q)
        return seeds, np.array([float(q[s][stat]) for s in seeds], dtype=np.float64)

    for src in SOURCES:
        seeds, hid = values(src, "hidden", "success_test")
        _, vis = values(src, "visible", "success_test")
        if not seeds:
            continue
        ci = ratio_ci(hid, vis, n_boot, _stat_seed("gate_ratio", src))
        primary = src == "sr"
        out.append({**base, "test": "g1_relative_success" if primary else "reported_relative_success", "statistic": "hidden / visible, trials 21-40",
                    "a": "visible", "b": "hidden", "n": len(seeds), "mean_a": float(np.mean(vis)), "mean_b": float(np.mean(hid)),
                    "estimate": ci.estimate, "low": ci.low, "high": ci.high, "bound": f">= {RATIO_BOUND}" if primary else "reported",
                    "verdict": ("passes" if ci.estimate >= RATIO_BOUND else "fails") if primary else "reported", "note": f"{src}; {ci.note}".rstrip("; ")})
    seeds, err = values("sr", "hidden", "arrival_error_median_test")
    finite = err[~np.isnan(err)]
    if finite.size:
        ci = bootstrap_ci(finite, np.mean, n_boot=n_boot, seed=_stat_seed("gate_error"))
        out.append({**base, "test": "g2_arrival_error", "statistic": "per-seed median estimate error at arrival, hidden, trials 21-40",
                    "b": "sr", "n": int(finite.size), "mean_b": ci.estimate, "estimate": ci.estimate, "low": ci.low, "high": ci.high,
                    "bound": f"< {ERROR_BOUND} units, interval below", "verdict": "passes" if ci.high < ERROR_BOUND else "fails",
                    "note": f"seeds without an arrival: {int(np.sum(np.isnan(err)))}"})
    else:
        out.append({**base, "test": "g2_arrival_error", "statistic": "per-seed median estimate error at arrival, hidden, trials 21-40",
                    "b": "sr", "n": 0, "estimate": math.nan, "bound": f"< {ERROR_BOUND} units", "verdict": "undefined (no arrival)"})
    for src in SOURCES:
        for ses in SESSIONS:
            seeds, v = values(src, ses, "success_test")
            if seeds:
                ci = bootstrap_ci(v, np.mean, n_boot=n_boot, seed=_stat_seed("gate_abs", src, ses))
                out.append({**base, "test": "reported_absolute_success", "statistic": "success, trials 21-40", "b": f"{src}/{ses}", "n": len(seeds),
                            "estimate": ci.estimate, "low": ci.low, "high": ci.high, "bound": "reported", "verdict": "reported", "note": ci.note})
    for a, b in (("none", "sr"), ("tabular", "sr"), ("none", "tabular")):
        sa, va = values(a, "hidden", "success_test")
        sb, vb = values(b, "hidden", "success_test")
        if sa and sb and sa == sb:
            eff = paired_effect(va, vb, n_boot=n_boot, seed=_stat_seed("gate_paired", a, b))
            d = cliffs_delta(va, vb, n_boot=n_boot, seed=_stat_seed("gate_cliff", a, b))
            out.append({**base, "test": "reported_paired_hidden", "statistic": "success, trials 21-40, hidden", "a": a, "b": b, "n": len(sa),
                        "mean_a": eff["mean_a"], "mean_b": eff["mean_b"], "estimate": eff["mean_diff"], "low": eff["low"], "high": eff["high"],
                        "cliffs_delta": d["delta"], "cliffs_low": d["low"], "cliffs_high": d["high"], "bound": "reported", "verdict": "reported",
                        "note": "; ".join(n for n in (eff["note"], d["note"]) if n)})
    return out


OUTPUT_FILES = ("gate_trials.csv", "gate_per_seed.csv", "gate_curve.csv", "gate_effects.csv", "gate_manifest.json")


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEEDS[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--quick", action="store_true", help=f"{QUICK_TRIALS} trials (the gate reads the second half), 200 replicates; needs --out")
    parser.add_argument("--sources", default=",".join(SOURCES), help="comma-separated; default all three")
    parser.add_argument("--reward-rule", default="nlms", choices=("nlms", "per_feature"),
                        help="the SR's reward rule: nlms (preregistered) or per_feature (exploratory, decisions G36)")
    parser.add_argument("--reward-unlearning-rate", type=float, default=None,
                        help="the SR's per-feature unlearning rate (decisions G41); default: none, one rate, as both gate "
                             "runs were registered. Any value marks the run exploratory")
    parser.add_argument("--prereg", default=DEFAULT_PREREG,
                        help="the preregistration this run answers to (a run away from its settings is marked exploratory)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.prereg not in PREREGS:
        parser.error(f"--prereg must be one of {tuple(PREREGS)}")
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    trials = QUICK_TRIALS if args.quick else TRIALS
    learning = trials // 2
    n_boot = min(args.n_boot, 200) if args.quick else args.n_boot
    sources = tuple(s.strip() for s in args.sources.split(",") if s.strip())
    for s in sources:
        if s not in SOURCES:
            parser.error(f"unknown source {s!r}")
    spec = PREREGS[args.prereg]
    full = (tuple(seeds) == spec["seeds"] and not args.quick and n_boot >= 1000 and sources == SOURCES
            and args.reward_rule == spec["reward_rule"] and args.reward_unlearning_rate == spec["reward_unlearning_rate"])
    for committed in (p["out"] for p in PREREGS.values()):
        if args.out.resolve() == Path(committed).resolve() and not (full and Path(committed).resolve() == Path(spec["out"]).resolve()):
            parser.error(f"a partial run (or another preregistration's) must not overwrite the committed tables in {committed}: give --out")
    started = time.perf_counter()
    trial_rows = run_all(seeds, trials, args.workers, sources, args.reward_rule, args.reward_unlearning_rate)
    per_seed = per_seed_rows(trial_rows, learning)
    curve = curve_rows(trial_rows, n_boot)
    effects = effect_rows(per_seed, n_boot)
    cfg = gate_config(sources[0], args.reward_rule, args.reward_unlearning_rate)
    manifest = build_manifest(
        cfg, protocol="rq4a_gate", seeds=seeds, ticks_requested=len(seeds) * len(sources) * len(SESSIONS) * trials * (TIMEOUT + GUIDE),
        extra={"goal": list(GOAL), "goal_radius": GOAL_RADIUS, "starts": [list(s) for s in STARTS], "trials": trials,
               "learning_trials": learning, "timeout": TIMEOUT, "guide": GUIDE, "sources": list(sources), "sessions": list(SESSIONS),
               "reward_rule": args.reward_rule, "reward_unlearning_rate": args.reward_unlearning_rate, "exploratory": not full,
               "ratio_bound": RATIO_BOUND, "error_bound": ERROR_BOUND, "protocol_stream": PROTOCOL_STREAM,
               "config_diff_from_research": {src: [list(map(str, d)) for d in EngineConfig.research().diff(gate_config(src, args.reward_rule, args.reward_unlearning_rate))] for src in sources},
               "n_boot": n_boot, "full_evaluation": full, "quick": args.quick, "prereg": args.prereg,
               "dependencies": _dependency_versions(),
               "command": "python3 -m experiments.rq4a_gate " + " ".join(list(argv) if argv is not None else sys.argv[1:])},
    )
    manifest["workers"] = args.workers if args.workers is not None else os.cpu_count()
    finish_manifest(manifest, ticks_run=sum(int(r["ticks"]) for r in trial_rows), wall_seconds=time.perf_counter() - started)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / OUTPUT_FILES[0], TRIAL_COLUMNS, trial_rows)
    write_csv(out / OUTPUT_FILES[1], PER_SEED_COLUMNS, per_seed)
    write_csv(out / OUTPUT_FILES[2], CURVE_COLUMNS, curve)
    write_csv(out / OUTPUT_FILES[3], EFFECT_COLUMNS, effects)
    write_manifest(out / OUTPUT_FILES[4], manifest)
    print(f"tests and reported statistics ({args.prereg}{'' if full else '; EXPLORATORY: not the preregistered settings'}):")
    for e in effects:
        est = "nan" if (isinstance(e["estimate"], float) and math.isnan(e["estimate"])) else f"{e['estimate']:.4g}"
        rng = "" if e["low"] == "" or (isinstance(e["low"], float) and math.isnan(e["low"])) else f" [{e['low']:.4g}, {e['high']:.4g}]"
        print(f"  {e['test']:28s} {e['a'] or '':8s} {e['b']:18s} {est}{rng} {e['verdict']} {e['note']}")
    print(f"wrote {', '.join(OUTPUT_FILES)} to {out} in {manifest['timing']['wall_seconds']:.1f} s")
    return {"trials": trial_rows, "per_seed": per_seed, "curve": curve, "effects": effects}


if __name__ == "__main__":
    main()
