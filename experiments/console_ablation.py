"""Matched-seed ablation of memory steering on a console scenario (docs/decisions.md G40).

Two arms on the same seeds: ``steer``, the scenario as configured on the profile
(``ui.scenarios.profile_config``), and ``no_steer``, the same with
``basal_ganglia.value_gain = 0``: the value learners still run and the RNG
streams are consumed alike, so the arms differ only in whether learned value
reaches the scores. Each run logs every tick's decision (``metrics.decisions``)
and is summarised by ``analysis.orbits``. Per seed and arm the table carries
finds (target contacts), unique sites (where the scenario counts them), distance,
distance per find, the wall-contact share of ticks, loops, orbits, the share of
ticks spent in orbit, the orbit ticks by category (productive, memory, wall,
other), the mean immediate memory influence and the reward. The summary pairs
the arms by seed (``analysis.stats.paired_effect``, BCa intervals) after the
pseudo-replication guard: on the legacy profile at sensor noise 0 every seed is
the same run, so pass ``--set sensors.noise=0.03`` there.

Diagnostic, not a preregistered result: it says what memory steering does to
the circling and the finds in this scenario, not whether the rule is right.

    python -m experiments.console_ablation --scenario hidden_food --profile research \\
        --seeds 1-8 --ticks 3000 --workers 4 --out docs/data/console_ablation/hidden_food_research
    python -m experiments.console_ablation --scenario hidden_food --profile legacy --set sensors.noise=0.03 ...
    python -m analysis.orbits docs/data/console_ablation/hidden_food_research/decisions_steer_s1.jsonl
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.engine import Engine  # noqa: I001  (core pins the BLAS thread counts; import it before numpy, docs/determinism.md rule 2)

import numpy as np

from analysis.orbits import CATEGORIES, summarise
from analysis.stats import PseudoReplicationError, paired_effect, pseudo_replication_guard
from metrics.decisions import decision_record, write_decisions
from metrics.manifest import build_manifest, finish_manifest, write_manifest
from ui.scenarios import DEFAULT_PROFILE, PROFILE_IDS, SCENARIOS, make_scenario, profile_config

ARMS: Dict[str, Dict[str, Any]] = {"steer": {}, "no_steer": {"basal_ganglia.value_gain": 0.0}}
METRICS: Tuple[str, ...] = (
    "finds", "unique_sites", "distance", "distance_per_find", "wall_fraction", "loops", "orbits", "orbit_fraction",
    "orbit_ticks_productive", "orbit_ticks_memory", "orbit_ticks_wall", "orbit_ticks_other", "mean_memory_influence", "reward",
)
BOUT_COLUMNS = ("arm", "seed", "tick_start", "ticks", "loops", "direction", "mean_radius", "closure", "centre_x", "centre_y",
                "contacts", "reward", "target_visible_fraction", "dominant", "memory_influence", "turn_prob",
                "turn_prob_without_memory", "category")
DEFAULT_SEEDS = tuple(range(1, 9))
DEFAULT_TICKS = 3000
QUICK_SEEDS = (1, 2)
QUICK_TICKS = 200
OUTPUT_FILES = ("ablation_per_seed.csv", "ablation_bouts.csv", "ablation_summary.json", "manifest.json")


def parse_seeds(text: str) -> Tuple[int, ...]:
    seeds: List[int] = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            seeds.extend(range(int(a), int(b) + 1))
        elif part:
            seeds.append(int(part))
    return tuple(seeds)


def parse_set(items: Sequence[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in items or ():
        key, _, value = item.partition("=")
        try:
            out[key.strip()] = json.loads(value)
        except json.JSONDecodeError:
            out[key.strip()] = value
    return out


def arm_config(scenario_id: str, profile: str, arm: str, overrides: Mapping[str, Any]):
    scenario = make_scenario(scenario_id)
    cfg, _ = profile_config(scenario, profile)
    for key, value in overrides.items():
        cfg.set_field(key, value)
    for key, value in ARMS[arm].items():
        cfg.set_field(key, value)
    return scenario, cfg


def run_one(args: Tuple[str, str, str, int, int, Dict[str, Any]]) -> Dict[str, Any]:
    scenario_id, profile, arm, seed, ticks, overrides = args
    scenario, cfg = arm_config(scenario_id, profile, arm, overrides)
    eng = Engine(seed=seed, config=cfg)
    scenario.setup(eng)
    bx, by = eng.world.bounds
    records: List[Dict[str, Any]] = []
    wall = 0
    digest = hashlib.sha256()
    for _ in range(ticks):
        td = eng.run(1)[0]
        records.append(decision_record(eng))  # the decision of this tick, before the scenario acts on it
        scenario.on_tick(eng, td.tick)
        x, y = td.pos
        wall += abs(x) >= bx - 1e-9 or abs(y) >= by - 1e-9
        digest.update(f"{x:.9f},{y:.9f};".encode())
    s = summarise(records)
    unique = scenario.sites_found() if hasattr(scenario, "sites_found") else None
    finds = s["contacts"]
    metrics = {
        "finds": finds,
        "unique_sites": unique,
        "distance": s["distance"],
        "distance_per_find": (s["distance"] / finds) if finds else None,
        "wall_fraction": wall / ticks,
        "loops": s["loops"],
        "orbits": s["orbits"],
        "orbit_fraction": s["orbit_fraction"],
        **{f"orbit_ticks_{c}": s["by_category"][c]["ticks"] for c in CATEGORIES},
        "mean_memory_influence": s["mean_memory_influence"],
        "reward": sum(r["reward"] for r in records),
    }
    bouts = []
    for b in s["bouts"]:
        row = {k: b.get(k) for k in BOUT_COLUMNS if k not in ("arm", "seed", "centre_x", "centre_y")}
        row["centre_x"], row["centre_y"] = (round(b["centre"][0], 3), round(b["centre"][1], 3))
        bouts.append(row)
    return {"arm": arm, "seed": seed, "metrics": metrics, "bouts": bouts, "records": records, "digest": digest.hexdigest()[:16],
            "status": scenario.status()}


def run_all(scenario_id: str, profile: str, seeds: Sequence[int], ticks: int, overrides: Mapping[str, Any],
            workers: Optional[int]) -> List[Dict[str, Any]]:
    jobs = [(scenario_id, profile, arm, seed, ticks, dict(overrides)) for arm in ARMS for seed in seeds]
    if workers == 1 or len(jobs) == 1:
        return [run_one(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_one, jobs, chunksize=1))


def effects(results: Sequence[Mapping[str, Any]], seeds: Sequence[int], n_boot: int) -> Dict[str, Any]:
    by = {(r["arm"], r["seed"]): r["metrics"] for r in results}
    out: Dict[str, Any] = {}
    for metric in METRICS:
        pairs = [(by[("no_steer", s)][metric], by[("steer", s)][metric]) for s in seeds]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if len(pairs) < 2:
            out[metric] = {"note": "fewer than two seeds with a value in both arms", "n": len(pairs)}
            continue
        a = np.array([p[0] for p in pairs], dtype=float)
        b = np.array([p[1] for p in pairs], dtype=float)
        out[metric] = paired_effect(a, b, n_boot=n_boot)
    return out


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def write_outputs(out: Path, scenario_id: str, profile: str, seeds: Sequence[int], ticks: int, overrides: Mapping[str, Any],
                  results: Sequence[Mapping[str, Any]], eff: Mapping[str, Any], guard: Any, wall_seconds: float,
                  keep_records: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "ablation_per_seed.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "task", "seed", "metric", "value"])
        for r in sorted(results, key=lambda r: (r["arm"], r["seed"])):
            for metric in METRICS:
                v = r["metrics"][metric]
                w.writerow([r["arm"], scenario_id, r["seed"], metric, "" if v is None else v])
    with open(out / "ablation_bouts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=BOUT_COLUMNS)
        w.writeheader()
        for r in sorted(results, key=lambda r: (r["arm"], r["seed"])):
            for b in r["bouts"]:
                w.writerow({"arm": r["arm"], "seed": r["seed"], **{k: b.get(k) for k in BOUT_COLUMNS if k not in ("arm", "seed")}})
    if keep_records:
        for r in results:
            write_decisions(out / f"decisions_{r['arm']}_s{r['seed']}.jsonl", r["records"])
    means = {arm: {m: float(np.mean([r["metrics"][m] for r in results if r["arm"] == arm and r["metrics"][m] is not None]))
                   if any(r["metrics"][m] is not None for r in results if r["arm"] == arm) else None for m in METRICS} for arm in ARMS}
    summary = {
        "scenario": scenario_id, "profile": profile, "seeds": list(seeds), "ticks": ticks, "overrides": dict(overrides),
        "arms": ARMS, "guard": guard, "per_arm_means": means, "effects": _jsonable(eff),
        "status": {f"{r['arm']}_s{r['seed']}": r["status"] for r in results},
        "wall_seconds": round(wall_seconds, 1),
    }
    (out / "ablation_summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    _, cfg = arm_config(scenario_id, profile, "steer", overrides)
    manifest = build_manifest(cfg, protocol=f"console_ablation:{scenario_id}", seeds=list(seeds), ticks_requested=ticks,
                              extra={"profile_requested": profile, "arms": ARMS, "overrides": dict(overrides),
                                     "experiment": "experiments.console_ablation"})
    finish_manifest(manifest, ticks_run=ticks * len(seeds) * len(ARMS), wall_seconds=wall_seconds)
    write_manifest(out / "manifest.json", manifest)


def format_effects(scenario_id: str, profile: str, seeds: Sequence[int], ticks: int, means: Mapping[str, Mapping[str, Any]],
                   eff: Mapping[str, Any]) -> str:
    lines = [f"{scenario_id} on {profile}, {len(seeds)} seeds x {ticks} ticks: steer vs no_steer (value_gain 0), paired by seed",
             f"{'metric':<24}{'no_steer':>10}{'steer':>10}{'diff':>9}  95% CI (BCa)       steer > no_steer"]
    for metric in METRICS:
        e = eff[metric]
        a, b = means["no_steer"][metric], means["steer"][metric]
        fa = "—" if a is None else f"{a:.2f}"
        fb = "—" if b is None else f"{b:.2f}"
        if "mean_diff" in e:
            lines.append(f"{metric:<24}{fa:>10}{fb:>10}{e['mean_diff']:>+9.2f}  [{e['low']:+.2f}, {e['high']:+.2f}]{'*' if e['low'] > 0 or e['high'] < 0 else ' '}  {100 * e['fraction_b_gt_a']:.0f}% of seeds"
                         + (f"  ({e['note']})" if e.get("note") else ""))
        else:
            lines.append(f"{metric:<24}{fa:>10}{fb:>10}      —  {e.get('note', '')}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", default="hidden_food", choices=sorted(SCENARIOS))
    parser.add_argument("--profile", default=DEFAULT_PROFILE, choices=list(PROFILE_IDS))
    parser.add_argument("--seeds", default=None, help="e.g. 1-8 or 1,2,5 (default 1-8; --quick: 1,2)")
    parser.add_argument("--ticks", type=int, default=None, help=f"ticks per run (default {DEFAULT_TICKS}; --quick: {QUICK_TICKS})")
    parser.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE", help="config override applied to both arms (repeatable)")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=10_000)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keep-records", action="store_true", help="also write every run's decisions.jsonl beside the tables")
    parser.add_argument("--allow-identical-seeds", action="store_true", help="run on even when two seeds gave identical trajectories (the guard then only warns)")
    parser.add_argument("--quick", action="store_true", help=f"{len(QUICK_SEEDS)} seeds x {QUICK_TICKS} ticks, for a smoke run")
    args = parser.parse_args(argv)
    seeds = parse_seeds(args.seeds) if args.seeds else (QUICK_SEEDS if args.quick else DEFAULT_SEEDS)
    ticks = args.ticks or (QUICK_TICKS if args.quick else DEFAULT_TICKS)
    overrides = parse_set(args.set)
    started = time.perf_counter()
    results = run_all(args.scenario, args.profile, seeds, ticks, overrides, args.workers)
    steer_digests = {r["seed"]: r["digest"] for r in results if r["arm"] == "steer"}
    try:
        guard: Any = pseudo_replication_guard([steer_digests[s] for s in seeds], allow=args.allow_identical_seeds)
    except PseudoReplicationError as exc:
        raise SystemExit(f"{exc}\n(on the legacy profile at sensor noise 0 every seed is one run: pass --set sensors.noise=0.03, "
                         f"or --allow-identical-seeds to run on)") from None
    eff = effects(results, seeds, args.n_boot)
    wall = time.perf_counter() - started
    write_outputs(args.out, args.scenario, args.profile, seeds, ticks, overrides, results, eff, guard, wall, args.keep_records)
    summary = json.loads((args.out / "ablation_summary.json").read_text())
    print(format_effects(args.scenario, args.profile, seeds, ticks, summary["per_arm_means"], eff))
    if isinstance(guard, str):
        print(f"warning: {guard}")
    print(f"wrote {args.out} ({wall:.0f} s)")
    return summary


if __name__ == "__main__":
    main()
