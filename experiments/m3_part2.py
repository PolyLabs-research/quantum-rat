"""M3 step 2, Part 2: one action selection for every task (docs/prereg/m3_step2.md, Part 2).

    python3 -m experiments.m3_part2 --phase pilot --workers 28     # spent seeds -> docs/data/m3/part2/pilot
    python3 -m experiments.m3_part2 --quick --out /tmp/p2           # the smoke test's run

Eight configurations of the research profile (as G50 left it): the orienting response off or on
(``basal_ganglia.orient_gain`` 0 / 1.0), the field of view narrow or a rat's (3 rays over 1.2 rad / 11 over 300
degrees), the wall response long-range or G45's (``wall_avoid_range`` 1.0 / 1/6 with ``turn_commitment`` 0.3). Each
runs the whole battery, and is scored against the draft's bounds; the selection rule (written in the draft before the
pilot) picks one: a configuration whose reflex alone runs laps is never chosen; among the rest, the most bounds passed;
ties to the fewest changes from the research profile.

The track: 10 x 0.5 units (2 m x 0.1 m), the agent put down at the centre facing +x, food at both ends (radius 0.5
at x = -9 and +9) alternating (eaten at one end, it appears at the other), with the renewable-reward unlearning rate
(``place.reward_unlearning_rate`` 4, G43's scenario setting for reward that empties); 3,000 ticks; ticks per traversal
is the median interval between arrivals at alternate end zones (|x| >= 8).

Scored since G53 (the owner's decisions at G52 D2 and D4) by traversals per run, not the median interval, which an
agent resting most of the run passed by moving fast when it moved: the learned arm at least ``TRACK_MIN_TRAVERSALS``
(42: half of the 83 a run at the physical minimum of 36 ticks a traversal allows), each reflex arm at most half the
learned arm's; and the gate's control as a margin, the SR's hidden success over the same configuration's no-steering
agent by at least ``CONTROL_MARGIN`` in every condition (a control that explores is still the control). The tables
keep the median interval. G51's and G52's committed tables were scored by the earlier statistics; G53 re-reads them.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

from core.config import PRE_G54, RESEARCH_G50, EngineConfig
from core.engine import Engine
from core.world import WorldObject
from experiments import body_characterisation as bc
from experiments import console_ablation as ca
from experiments import rq4a_gate as rg
from experiments.linear_track_replay import _dependency_versions, write_csv
from metrics.manifest import build_manifest, finish_manifest, write_manifest

PHASES: Dict[str, Dict[str, Any]] = {
    "pilot": {"gate_seeds": tuple(range(31, 43)), "track_seeds": tuple(range(31, 43)), "food_seeds": tuple(range(1, 9)),
              "out": Path("docs/data/m3/part2/pilot")},
}
QUICK = {"gate_seeds": (31,), "track_seeds": (31, 32), "food_seeds": (1,)}
TICKS = 3000
TRACK_ENDS = (-9.0, 9.0)
TRACK_U = 4.0
ORIENT = {"o0": {}, "o1": {"basal_ganglia.orient_gain": 1.0}}
VISION = {"n": {}, "w": {"sensors.fov": 5.235987755982989, "sensors.vision_rays": 11}}
WALL = {"L": {}, "S": {"basal_ganglia.wall_avoid_range": 1 / 6, "basal_ganglia.turn_commitment": 0.3}}
CONFIGS: Dict[str, Dict[str, Any]] = {f"{o}_{v}_{w}": {**ORIENT[o], **VISION[v], **WALL[w]}
                                      for o in ORIENT for v in VISION for w in WALL}
GATE: Dict[str, Dict[str, Any]] = {
    "open_anchor": {"layout": "open", "start_estimate": "anchor"},
    "L_anchor": {"layout": "L", "start_estimate": "anchor"},
    "open_cues": {"layout": "open", "start_estimate": "carry", "landmarks": True},
    "L_cues": {"layout": "L", "start_estimate": "carry", "landmarks": True},
}
TRACK_ARMS = ("learned", "no_steer", "no_reward")
# Every configuration's base (G52): the per-feature step capped at the target. Without it the track's unlearning rate
# (4) diverged the reward weights wherever one place cell carried more than half of phi (G51's first pilot). History
# off (PRE_G54): the battery is the research profile as G50 left it plus the cap, which is what G51-G54's probes ran
# on; a configuration that wants history (m3_hm_probe, m3_g53_probes, history_fast_schema) sets it on top.
BASE: Dict[str, Any] = {"place.reward_step_cap": True, **PRE_G54}
BOUNDS = ("track_learned", "track_reflex_no_reward", "track_reflex_no_steer", "open_hidden", "open_visible", "L_hidden",
          "L_visible", "cues_open", "cues_L", "hidden_food", "controls")
REFLEX_BOUNDS = ("track_reflex_no_reward", "track_reflex_no_steer")
TRACK_MIN_TRAVERSALS = 42.0  # G53: half of the 83 traversals a 3,000-tick run at the physical minimum (36 ticks) allows
CONTROL_MARGIN = 0.5  # G53: the SR's hidden success over the no-steering agent of the same configuration, every condition
FOOD_FLOOR = 0.9 * 41.2  # G46's research memory steering, less 10%


def changes(name: str) -> int:
    """How many of the three candidates a configuration changes from the research profile."""
    return sum(part not in ("o0", "n", "L") for part in name.split("_"))


def _gate_job(job: Tuple[str, Mapping[str, Any], str, str, str, int, int]) -> Dict[str, Any]:
    cfg, overrides, cond, src, ses, seed, trials = job
    rows = rg.run_session(src, ses, seed, trials=trials, reward_rule="per_feature", still_start=True,
                          overrides=dict(overrides), **GATE[cond])
    test = [r for r in rows if r["trial"] > trials // 2]
    return {"config": cfg, "condition": cond, "source": src, "session": ses, "seed": seed,
            "success": sum(r["reached"] for r in test) / len(test)}


def track_config(overrides: Mapping[str, Any]) -> EngineConfig:
    cfg = EngineConfig.research()
    cfg.world.bounds = tuple(bc.TRACK_BOUNDS)
    cfg.place.reward_unlearning_rate = TRACK_U
    cfg.place.reward_step_cap = True  # BASE: never past the target (G52)
    for key, value in overrides.items():
        cfg.set_field(key, value)
    return cfg


def _track_job(job: Tuple[str, Mapping[str, Any], str, int, int]) -> Dict[str, Any]:
    cfg_name, overrides, arm, seed, ticks = job
    ov = dict(overrides)
    if arm == "no_steer":
        ov["basal_ganglia.value_gain"] = 0.0
    eng = Engine(seed=seed, config=track_config(ov))
    sites = [WorldObject(x, 0.0, 0.5, "collected") for x in TRACK_ENDS]
    for s in sites:
        eng.world.add_object(s)
    active = 1
    if arm != "no_reward":
        sites[active].kind = "hidden"
    eng.run(1, reset=True)
    rewards, prev_end, arrivals, rests = 0, None, [], 0
    for t in range(ticks):
        rests += eng.run(1)[0].action_name == "REST"
        x, y = eng.agent.pos
        if arm != "no_reward" and math.hypot(x - sites[active].x, y - sites[active].y) <= sites[active].radius:
            sites[active].kind = "collected"
            active = 1 - active
            sites[active].kind = "hidden"
            rewards += 1
        end = -1 if x <= -8.0 else (1 if x >= 8.0 else None)
        if end is not None and end != prev_end:
            arrivals.append(t)
            prev_end = end
    gaps = [b - a for a, b in zip(arrivals, arrivals[1:])]
    return {"config": cfg_name, "arm": arm, "seed": seed, "rewards": rewards, "traversals": len(gaps),
            "ticks_per_traversal": float(statistics.median(gaps)) if gaps else float(ticks),
            "traversals_late": sum(1 for a in arrivals[1:] if a >= ticks // 2), "rest_share": rests / ticks,
            "replay_events": len(eng.replay_log)}  # M3 step 3: the events the run's replay made (0 without one)


def _food_job(job: Tuple[str, Mapping[str, Any], str, int, int]) -> Dict[str, Any]:
    cfg_name, overrides, arm, seed, ticks = job
    r = ca.run_one(("hidden_food", "research", arm, seed, ticks, dict(overrides), ca.ARMS))
    return {"config": cfg_name, "arm": arm, "seed": seed, "finds": r["metrics"]["finds"]}


def _open_job(job: Tuple[str, Mapping[str, Any], int, int]) -> Dict[str, Any]:
    cfg_name, overrides, seed, ticks = job
    r = bc.run_world("open", {**RESEARCH_G50, **dict(overrides)}, seed, ticks)  # undo bc's PRE_G50 pin: today's profile
    return {"config": cfg_name, "seed": seed, **{k: r[k] for k in ("wall_zone_share", "coverage", "orbit_share", "stall_share")}}


def _pool(fn, jobs, workers):
    if workers == 1:
        return [fn(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, jobs, chunksize=1))


def run_battery(configs: Mapping[str, Mapping[str, Any]], seeds: Mapping[str, Sequence[int]], trials: int, ticks: int,
                workers: Optional[int], base: Optional[Mapping[str, Any]] = None):
    """Every configuration (name -> overrides) through the battery: the gate, the track, hidden food, the open field, each
    on ``base`` (``BASE`` unless given: the capped per-feature step with history pinned off; M3 step 3 gives the profile
    as G54 left it) with the configuration's own fields on top."""
    base = BASE if base is None else dict(base)
    configs = {c: {**base, **dict(ov)} for c, ov in configs.items()}
    gate = _pool(_gate_job, [(c, ov, cond, src, ses, s, trials) for c, ov in configs.items() for cond in GATE
                             for src in ("sr", "none") for ses in rg.SESSIONS for s in seeds["gate_seeds"]], workers)
    track = _pool(_track_job, [(c, ov, a, s, ticks) for c, ov in configs.items() for a in TRACK_ARMS for s in seeds["track_seeds"]], workers)
    food = _pool(_food_job, [(c, ov, a, s, ticks) for c, ov in configs.items() for a in ca.ARMS for s in seeds["food_seeds"]], workers)
    open_field = _pool(_open_job, [(c, ov, s, ticks) for c, ov in configs.items() for s in seeds["track_seeds"]], workers)
    return gate, track, food, open_field


def score(cfg: str, gate, track, food) -> Dict[str, Any]:
    def g(cond, src, ses):
        return float(np.mean([float(r["success"]) for r in gate if (r["config"], r["condition"], r["source"], r["session"]) == (cfg, cond, src, ses)]))

    def t(arm):  # traversals per run (G53); the tables keep the median interval too
        return float(np.mean([float(r["traversals"]) for r in track if (r["config"], r["arm"]) == (cfg, arm)]))

    finds = float(np.mean([float(r["finds"]) for r in food if (r["config"], r["arm"]) == (cfg, "steer")]))
    margin = min(g(c, "sr", "hidden") - g(c, "none", "hidden") for c in GATE)  # the control as a margin (G53)
    values = {"track_learned": t("learned"), "track_reflex_no_reward": t("no_reward"), "track_reflex_no_steer": t("no_steer"),
              "open_hidden": g("open_anchor", "sr", "hidden"), "open_visible": g("open_anchor", "sr", "visible"),
              "L_hidden": g("L_anchor", "sr", "hidden"), "L_visible": g("L_anchor", "sr", "visible"),
              "cues_open": g("open_cues", "sr", "hidden"), "cues_L": g("L_cues", "sr", "hidden"),
              "hidden_food": finds, "controls": margin}
    passes = {"track_learned": values["track_learned"] >= TRACK_MIN_TRAVERSALS,
              "track_reflex_no_reward": values["track_reflex_no_reward"] <= values["track_learned"] / 2,
              "track_reflex_no_steer": values["track_reflex_no_steer"] <= values["track_learned"] / 2,
              "open_hidden": values["open_hidden"] >= 0.95, "open_visible": values["open_visible"] >= 0.90,
              "L_hidden": values["L_hidden"] >= 0.90, "L_visible": values["L_visible"] >= 0.90,
              "cues_open": values["cues_open"] >= 0.85, "cues_L": values["cues_L"] >= 0.85,
              "hidden_food": values["hidden_food"] >= FOOD_FLOOR, "controls": values["controls"] >= CONTROL_MARGIN}
    return {"config": cfg, "values": values, "passes": passes, "passed": sum(passes.values()), "changes": changes(cfg),
            "eligible": all(passes[b] for b in REFLEX_BOUNDS)}


def select(scores: Sequence[Mapping[str, Any]]) -> Optional[str]:
    """The draft's rule: never a configuration whose reflex alone runs laps; then the most bounds; then the fewest changes."""
    eligible = [s for s in scores if s["eligible"]]
    if not eligible:
        return None
    best = sorted(eligible, key=lambda s: (-s["passed"], s["changes"], s["config"]))[0]
    return best["config"]


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phase", choices=tuple(PHASES), default="pilot")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="a seed or two, 8 trials, 300 ticks; needs --out")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    spec = PHASES[args.phase]
    out = args.out or spec["out"]
    if args.quick and out.resolve() == spec["out"].resolve():
        parser.error(f"a quick run must not overwrite the committed tables in {out}: give --out")
    seeds = QUICK if args.quick else spec
    trials = rg.QUICK_TRIALS if args.quick else rg.TRIALS
    ticks = 300 if args.quick else TICKS
    started = time.perf_counter()
    gate, track, food, open_field = run_battery(CONFIGS, seeds, trials, ticks, args.workers)
    scores = [score(c, gate, track, food) for c in CONFIGS]
    chosen = select(scores)
    write_csv(out / "gate.csv", ("config", "condition", "source", "session", "seed", "success"), gate)
    write_csv(out / "track.csv", ("config", "arm", "seed", "rewards", "traversals", "ticks_per_traversal"), track)
    write_csv(out / "hidden_food.csv", ("config", "arm", "seed", "finds"), food)
    write_csv(out / "open_field.csv", ("config", "seed", "wall_zone_share", "coverage", "orbit_share", "stall_share"), open_field)
    summary = {"phase": args.phase, "seeds": {k: list(v) for k, v in seeds.items() if k != "out"}, "configs": CONFIGS,
               "bounds": BOUNDS, "reflex_bounds": REFLEX_BOUNDS, "scores": scores, "chosen": chosen, "quick": args.quick}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str))
    manifest = build_manifest(track_config({}), protocol=f"m3_part2:{args.phase}", seeds=sorted(set(seeds["gate_seeds"]) | set(seeds["track_seeds"]) | set(seeds["food_seeds"])),
                              ticks_requested=0, extra={"configs": CONFIGS, "phase": args.phase, "quick": args.quick, "exploratory": True,
                                                        "dependencies": _dependency_versions(),
                                                        "command": "python3 -m experiments.m3_part2 " + " ".join(list(argv) if argv is not None else sys.argv[1:])})
    finish_manifest(manifest, ticks_run=0, wall_seconds=time.perf_counter() - started)
    write_manifest(out / "manifest.json", manifest)
    print(f"{'config':10s} {'pass':>4s} elig  " + "  ".join(f"{b[:12]:>12s}" for b in BOUNDS))
    for s in scores:
        cells = []
        for b in BOUNDS:
            v = s["values"][b]
            cells.append(f"{v:11.2f}{'+' if s['passes'][b] else '-'}")
        print(f"{s['config']:10s} {s['passed']:4d} {'yes ' if s['eligible'] else 'no  '}  " + "  ".join(cells))
    print(f"chosen by the rule: {chosen}")
    print(f"wrote {out} in {time.perf_counter() - started:.1f} s")
    return summary


if __name__ == "__main__":
    main()
