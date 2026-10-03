"""How sensitive is behaviour to memory steering (``basal_ganglia.value_gain``)?

Runs the lab-console scenarios headless across a grid of ``value_gain`` values
and seeds (and optionally start headings), and reports each scenario's task
score. A robust memory system should give good scores over a broad band of
gains, with one default that works for all scenarios; a brittle one swings
between success and failure as the gain moves.

    python -m experiments.steering_sensitivity                 # default grid, noise 0.03, seeds 1-4
    python -m experiments.steering_sensitivity --gains 0,0.4,0.8,1.5 --seeds 4
    python -m experiments.steering_sensitivity --noise 0 --seeds 1 --headings 8
    python -m experiments.steering_sensitivity --noise-both --seeds 8
    python -m experiments.steering_sensitivity --seed-start 9 --seeds 8        # held-out seeds 9-16
    python -m experiments.steering_sensitivity --set value_memory.generalization_radius=2
    python -m experiments.steering_sensitivity --scenarios memory_maze --noise 0 --seeds 1 --maze-headings full

Options beyond the grid:
  --seeds N, --seed-start S  run seeds S .. S+N-1 (default 1..4).
  --headings N   also vary the start heading. beacon, foraging, hazard_field
                 and hidden_food start at heading 2*pi*i/N (i = 0..N-1), set
                 on the body and on the path-integration frame after setup.
                 memory_maze teleports to ui.scenarios.START_POSE at every
                 trial, so it runs with START_POSE = (0, 0, h) for the fixed,
                 memory-dependent set
                 h in {-0.2, -0.1, 0, 0.1, 0.2} whatever N is (0.3-0.4 face
                 the goal and need no memory). Every seed runs every heading.
  --maze-headings SET
                 the maze's start headings: "default" (the five above), "full"
                 (16 headings 2*pi*i/16 over the whole circle, including starts
                 facing away from the goal, which need a search on the visible
                 trial) or an integer N (N headings over the circle). Given
                 without --headings it varies the maze heading only; with
                 --noise-both it applies to the noise-0 block.
  --noise-both   two blocks in one run: --noise (default 0.03) over the seeds at
                 the default heading, and noise 0 over headings (8 for the open
                 scenarios, or --headings N; 5 for the maze) at seed S only.
                 Each block is summarised separately.
  --ticks N      override every scenario's tick budget (quick checks only).
  --json         print the raw rows (one list, both blocks) instead of tables.
Identical arguments give byte-identical --json output.

Noise caveat: sensor noise (default 0.03) makes each seed a genuinely different
run, so the numbers are distributions. At noise 0 the seed barely matters
(different seeds usually give the identical run), so ``--seeds N`` at noise 0
is close to N copies of one sample; vary the start heading instead
(``--noise 0 --seeds 1 --headings 8``). Since M0b item 8 the harness refuses
several seeds on a config with no stochastic element on (noise 0 and no
odometry noise or softmax temperature among the ``--set`` overrides) unless
``--allow-identical-seeds`` is given, which prints a warning and runs them
(``core.seeds``). Noise is also not neutral. In the stock
engine (6c0ea9d, max-norm steering with shaping in the map) clamped pain noise
entered the value map and acted as a hidden cost on dwelling, which masked
value-induced REST. Since G14 and G16 the map only learns pain above max(0.05,
sensors.noise), so that path is closed, but noise still perturbs vision, path
integration and the trial-level chaos of the maze; check both levels
(``--noise-both``).

Metrics per run (higher is better unless noted):
  beacon        beacons reached in the tick budget
  foraging      food items collected
  hazard_field  food items collected (hazard_contacts reported too, lower is better)
  hidden_food   hidden food items found (sites_found: distinct sites found at
                least once; blocks: finds per 500-tick block, the learning curve)
  memory_maze   hidden-goal recalls (score), attempted, recall_rate,
                median_recall_ticks and first_hidden_ticks (ticks of the first
                hidden trial, reached or timed out; lower is better; None if no
                hidden trial started), train_ticks (the visible trial; None if
                it did not end) and timeouts (hidden trials that timed out)
  all           vrest: share of all ticks on which REST was chosen although the
                same tick's scores without the value terms (FORWARD, TURN_LEFT and
                TURN_RIGHT minus value_gain * the value signal fed to them) would
                not choose REST. Microsleep ticks never count. Lower is better.

Summary per noise block: per scenario and gain the mean/min/max score and mean
vrest; robustness() (gains within 80% of each scenario's own best);
worst_fraction[g] = min over scenarios of mean[g] / best_mean(scenario); and
the contiguous good band of gains where worst_fraction >= 0.8 (and >= 0.85).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import ui.scenarios as scenarios_module
from brain.systems.spatial import wrap_angle
from core.config import EngineConfig
from core.engine import Engine
from core.seeds import require_seeds_are_samples
from ui.scenarios import make_scenario

SCENARIOS = ("beacon", "foraging", "hazard_field", "hidden_food", "memory_maze")
DEFAULT_GAINS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0)
TICKS = {"beacon": 3000, "foraging": 3000, "hazard_field": 3000, "hidden_food": 3000, "memory_maze": 1500}
# memory_maze start headings: small offsets where recall still depends on the value map.
MAZE_HEADINGS = (-0.2, -0.1, 0.0, 0.1, 0.2)
FULL_CIRCLE_HEADINGS = 16  # --maze-headings full
NOISE_BOTH_HEADINGS = 8  # open-scenario headings in the noise-0 block of --noise-both
ACTION_ORDER = ("FORWARD", "TURN_LEFT", "TURN_RIGHT", "REST")  # selection tie-break order
BAND_THRESHOLDS = (0.8, 0.85)
RECALL_OK = 0.9  # a maze run "recalls" when at least this share of its hidden trials reach the goal

Summary = Dict[str, Dict[float, Dict[str, Any]]]


@dataclass(frozen=True)
class Job:
    scenario: str
    value_gain: Optional[float]  # None = the scenario's own default
    seed: int
    noise: float
    ticks: int
    overrides: Tuple[Tuple[str, Any], ...] = ()
    heading: Optional[float] = None  # start heading in radians; None = START_POSE as is


MazeHeadings = Union[None, str, int]


def maze_heading_set(spec: MazeHeadings) -> List[float]:
    """The maze start headings for ``--maze-headings`` (None or "default": MAZE_HEADINGS)."""
    if spec is None or spec == "default":
        return list(MAZE_HEADINGS)
    if spec == "full":
        spec = FULL_CIRCLE_HEADINGS
    if isinstance(spec, str):
        try:
            spec = int(spec)
        except ValueError:
            raise ValueError(f"maze headings must be 'default', 'full' or an integer, got {spec!r}") from None
    if spec < 1:
        raise ValueError(f"maze headings must be >= 1, got {spec}")
    return [2.0 * math.pi * i / spec for i in range(spec)]


def headings_for(scenario: str, n: Optional[int], maze: MazeHeadings = None) -> List[Optional[float]]:
    """Start headings for ``--headings n`` / ``--maze-headings maze`` (``[None]`` = scenario default).

    The maze varies its heading when either is given (over ``maze_heading_set(maze)``);
    the open scenarios only with ``n``.
    """
    if n is not None and n < 1:
        raise ValueError(f"headings must be >= 1, got {n}")
    if scenario == "memory_maze":
        return [None] if n is None and maze is None else maze_heading_set(maze)
    if n is None:
        return [None]
    return [2.0 * math.pi * i / n for i in range(n)]


def _set(config: Any, key: str, value: Any) -> None:
    obj = config
    parts = key.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    if not hasattr(obj, parts[-1]):
        raise AttributeError(f"config has no field {key!r}")
    setattr(obj, parts[-1], value)


def _winner(scores: Mapping[str, float]) -> str:
    return max(ACTION_ORDER, key=lambda name: (scores.get(name, float("-inf")), -ACTION_ORDER.index(name)))


def is_value_rest(ctx: Any, value_gain: float) -> bool:
    """True when this tick chose REST but the no-value counterfactual would not.

    Reads the display-only readouts the engine leaves on its context:
    ``action_scores``, ``value_signals`` (the effective signals fed to action
    selection, i.e. after cue and wall gating) and ``action_name``. The counterfactual
    subtracts ``value_gain * signal`` from FORWARD / TURN_LEFT / TURN_RIGHT and
    keeps REST (freeze habituation and energy pacing act on REST only, so they
    stay in the counterfactual). tests/experiments/test_steering_sensitivity.py
    checks this against the engine's own scores recomputed with zero value input.
    Microsleep ticks (scores ``{"REST": 1.0}`` only) and engines that expose no
    scores never count.
    """
    scores = getattr(ctx, "action_scores", None) or {}
    if any(name not in scores for name in ACTION_ORDER):
        return False  # microsleep ({"REST": 1.0}) or no readout
    chosen = getattr(ctx, "action_name", None) or _winner(scores)
    if chosen != "REST":
        return False
    signals = tuple(getattr(ctx, "value_signals", None) or (0.0, 0.0, 0.0))
    ahead, left, right = (tuple(signals) + (0.0, 0.0, 0.0))[:3]
    counterfactual = dict(scores)
    counterfactual["FORWARD"] -= value_gain * ahead
    counterfactual["TURN_LEFT"] -= value_gain * left
    counterfactual["TURN_RIGHT"] -= value_gain * right
    return _winner(counterfactual) != "REST"


def _apply_heading(engine: Engine, heading: float) -> None:
    engine.agent.heading = heading
    engine.agent.last_heading = heading
    engine.spatial.state.hd_angle = wrap_angle(heading)


def _job_config(job: Job, scenario: Any) -> EngineConfig:
    """The engine config a job runs with: the scenario's own, plus the job's noise, overrides and gain."""
    config = scenario.config()
    config.sensors.noise = job.noise
    for key, value in job.overrides:
        _set(config, key, value)
    if job.value_gain is not None:
        config.basal_ganglia.value_gain = job.value_gain
    return config


def check_seeds_are_samples(jobs: Sequence[Job], allow_identical_seeds: bool = False) -> None:
    """The pseudo-replication guard (core.seeds) over a job list.

    Jobs that differ only in their seed are one group; a group of more than
    one seed must have a stochastic element on in its config (sensor noise,
    odometry noise or a softmax temperature, possibly from ``--set``), or
    ``PseudoReplicationError`` is raised, unless ``allow_identical_seeds``, in
    which case a warning line is printed and the jobs run. The guard is called
    once per distinct set of enabled elements, so the warning prints once.
    """
    seeds: Dict[Tuple[Any, ...], set] = {}
    first: Dict[Tuple[Any, ...], Job] = {}
    for job in jobs:
        key = (job.scenario, job.noise, job.overrides, job.value_gain, job.heading, job.ticks)
        seeds.setdefault(key, set()).add(job.seed)
        first.setdefault(key, job)
    checked: set = set()
    for key, group in seeds.items():  # insertion order: the job order
        if len(group) < 2:
            continue
        job = first[key]
        config = _job_config(job, make_scenario(job.scenario))
        elements = tuple(config.stochastic_elements())
        if elements in checked:
            continue
        checked.add(elements)
        require_seeds_are_samples(config, len(group), allow_identical_seeds=allow_identical_seeds)


def run_job(job: Job) -> Dict[str, Any]:
    saved_pose = scenarios_module.START_POSE
    maze_pose = job.heading is not None and job.scenario == "memory_maze"
    try:
        if maze_pose:
            # The maze teleports to START_POSE at every trial, so the heading must live there.
            scenarios_module.START_POSE = (0.0, 0.0, float(job.heading))
        scenario = make_scenario(job.scenario)
        config = _job_config(job, scenario)
        engine = Engine(seed=job.seed, config=config)
        scenario.setup(engine)
        if job.heading is not None and not maze_pose:
            _apply_heading(engine, job.heading)
        bg_config = getattr(engine.config, "basal_ganglia", None)
        value_rest = 0
        for _ in range(job.ticks):
            td = engine.run(1)[0]
            ctx = getattr(engine, "context", None)
            if ctx is not None and is_value_rest(ctx, getattr(bg_config, "value_gain", 0.0)):
                value_rest += 1
            scenario.on_tick(engine, td.tick)
    finally:
        scenarios_module.START_POSE = saved_pose

    out: Dict[str, Any] = {
        "scenario": job.scenario,
        "value_gain": config.basal_ganglia.value_gain,
        "seed": job.seed,
        "noise": job.noise,
        "heading": job.heading,
        "ticks": job.ticks,
    }
    if job.scenario == "beacon":
        out["score"] = scenario.visits
    elif job.scenario == "foraging":
        out["score"] = scenario.collected
    elif job.scenario == "hazard_field":
        out["score"] = scenario.collected
        out["hazard_contacts"] = scenario.hurts
    elif job.scenario == "hidden_food":
        out["score"] = scenario.collected
        out["sites_found"] = scenario.sites_found()
        out["blocks"] = scenario.blocks(job.ticks)
    elif job.scenario == "memory_maze":
        hidden = [t for t in scenario.history if not t["visible"]]
        reached = [t["ticks"] for t in hidden if t["reached"]]
        out["score"] = len(reached)
        out["attempted"] = len(hidden)
        out["recall_rate"] = len(reached) / len(hidden) if hidden else 0.0
        out["median_recall_ticks"] = statistics.median(reached) if reached else None
        out["first_hidden_ticks"] = hidden[0]["ticks"] if hidden else None
        visible = [t for t in scenario.history if t["visible"]]
        out["train_ticks"] = visible[0]["ticks"] if visible else None
        out["timeouts"] = len(hidden) - len(reached)
    out["vrest"] = value_rest / job.ticks if job.ticks > 0 else 0.0
    return out


def make_jobs(
    scenarios: Sequence[str] = SCENARIOS,
    gains: Sequence[Optional[float]] = DEFAULT_GAINS,
    seeds: Sequence[int] = (1, 2, 3, 4),
    noise: float = 0.03,
    overrides: Optional[Mapping[str, Any]] = None,
    ticks: Union[int, Mapping[str, int], None] = None,
    headings: Optional[int] = None,
    maze_headings: MazeHeadings = None,
) -> List[Job]:
    """The job grid, in output order: scenario, gain, seed, heading."""
    over = tuple(sorted((overrides or {}).items()))
    if isinstance(ticks, int):
        budget = {s: ticks for s in scenarios}
    else:
        budget = {**TICKS, **(ticks or {})}
    return [
        Job(s, g, seed, noise, budget[s], over, h)
        for s in scenarios
        for g in gains
        for seed in seeds
        for h in headings_for(s, headings, maze_headings)
    ]


def run_jobs(
    jobs: Sequence[Job], workers: Optional[int] = None, *, allow_identical_seeds: bool = False
) -> List[Dict[str, Any]]:
    """Run jobs in order; in-process when there is one job or ``workers == 1``.

    ``check_seeds_are_samples`` runs first: several seeds on a config with no
    stochastic element are refused unless ``allow_identical_seeds``.
    """
    check_seeds_are_samples(jobs, allow_identical_seeds)
    if len(jobs) <= 1 or workers == 1:
        return [run_job(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_job, jobs, chunksize=1))


def sweep(
    scenarios: Sequence[str] = SCENARIOS,
    gains: Sequence[Optional[float]] = DEFAULT_GAINS,
    seeds: Sequence[int] = (1, 2, 3, 4),
    noise: float = 0.03,
    overrides: Optional[Mapping[str, Any]] = None,
    ticks: Union[int, Mapping[str, int], None] = None,
    workers: Optional[int] = None,
    headings: Optional[int] = None,
    maze_headings: MazeHeadings = None,
    allow_identical_seeds: bool = False,
) -> List[Dict[str, Any]]:
    """Rows for every (scenario, gain, seed, heading). ``ticks``: int or per-scenario budgets."""
    jobs = make_jobs(scenarios, gains, seeds, noise, overrides, ticks, headings, maze_headings)
    return run_jobs(jobs, workers, allow_identical_seeds=allow_identical_seeds)


def sweep_both(
    scenarios: Sequence[str] = SCENARIOS,
    gains: Sequence[Optional[float]] = DEFAULT_GAINS,
    seeds: Sequence[int] = (1, 2, 3, 4),
    noise: float = 0.03,
    overrides: Optional[Mapping[str, Any]] = None,
    ticks: Union[int, Mapping[str, int], None] = None,
    workers: Optional[int] = None,
    headings: int = NOISE_BOTH_HEADINGS,
    maze_headings: MazeHeadings = None,
    allow_identical_seeds: bool = False,
) -> List[Dict[str, Any]]:
    """``noise`` over ``seeds`` at the default heading, then noise 0 over headings at ``seeds[0]``."""
    seeded = make_jobs(scenarios, gains, seeds, noise, overrides, ticks)
    headed = make_jobs(scenarios, gains, list(seeds)[:1], 0.0, overrides, ticks, headings, maze_headings)
    return run_jobs(seeded + headed, workers, allow_identical_seeds=allow_identical_seeds)


def by_noise(rows: Sequence[Mapping[str, Any]]) -> Dict[float, List[Mapping[str, Any]]]:
    """Split rows into noise blocks, in order of first appearance (rows without noise -> 0.03)."""
    blocks: Dict[float, List[Mapping[str, Any]]] = {}
    for row in rows:
        blocks.setdefault(row.get("noise", 0.03), []).append(row)
    return blocks


def summarise(rows: Sequence[Mapping[str, Any]]) -> Summary:
    """scenario -> gain -> {mean, min, max, n, (vrest), (recall_rate, recall_ok, first_hidden_ticks,
    median_recall_ticks, train_ticks)}.

    Summarise one noise block at a time (see ``by_noise``). Optional keys appear
    only when the rows carry them; maze tick entries are medians over the runs
    that have a value (None if none do). ``recall_ok`` is the share of runs
    whose recall rate is at least ``RECALL_OK`` (a run with no hidden trial
    counts as failing).
    """
    table: Dict[str, Dict[float, Dict[str, List[Any]]]] = {}
    for row in rows:
        cell = table.setdefault(row["scenario"], {}).setdefault(
            row["value_gain"], {"scores": [], "vrest": [], "rates": [], "first": [], "median": [], "train": []}
        )
        cell["scores"].append(row["score"])
        if "vrest" in row:
            cell["vrest"].append(row["vrest"])
        if "recall_rate" in row:
            cell["rates"].append(row["recall_rate"])
        if "first_hidden_ticks" in row:
            cell["first"].append(row["first_hidden_ticks"])
        if "median_recall_ticks" in row:
            cell["median"].append(row["median_recall_ticks"])
        if "train_ticks" in row:
            cell["train"].append(row["train_ticks"])
    out: Summary = {}
    for scen, by_gain in table.items():
        out[scen] = {}
        for gain, cell in sorted(by_gain.items()):
            s = cell["scores"]
            entry: Dict[str, Any] = {"mean": statistics.mean(s), "min": min(s), "max": max(s), "n": len(s)}
            if cell["vrest"]:
                entry["vrest"] = statistics.mean(cell["vrest"])
            if cell["rates"]:
                entry["recall_rate"] = statistics.mean(cell["rates"])
                entry["recall_ok"] = sum(r >= RECALL_OK for r in cell["rates"]) / len(cell["rates"])
            for key, name in (
                ("first", "first_hidden_ticks"), ("median", "median_recall_ticks"), ("train", "train_ticks")
            ):
                if cell[key]:
                    present = [v for v in cell[key] if v is not None]
                    entry[name] = statistics.median(present) if present else None
            out[scen][gain] = entry
    return out


def robustness(summary: Summary, fraction: float = 0.8) -> Dict[str, Dict[str, Any]]:
    """Per scenario: best mean, and the gains whose mean is within ``fraction`` of the best."""
    result = {}
    for scen, by_gain in summary.items():
        best = max(v["mean"] for v in by_gain.values())
        good = [g for g, v in by_gain.items() if best > 0 and v["mean"] >= fraction * best]
        result[scen] = {"best_mean": best, "good_gains": good, "n_gains": len(by_gain)}
    return result


def gain_fractions(summary: Summary) -> Dict[float, Dict[str, float]]:
    """gain -> scenario -> mean[g] / best_mean(scenario), over gains every scenario ran.

    A scenario that never scores (best mean 0) gives fraction 0: no gain is good for it.
    """
    if not summary:
        return {}
    best = {scen: max(v["mean"] for v in by_gain.values()) for scen, by_gain in summary.items()}
    common = set.intersection(*(set(by_gain) for by_gain in summary.values()))
    return {
        g: {scen: (summary[scen][g]["mean"] / best[scen] if best[scen] > 0 else 0.0) for scen in summary}
        for g in sorted(common)
    }


def worst_fraction(summary: Summary) -> Dict[float, float]:
    """gain -> min over scenarios of mean[g] / best_mean(scenario)."""
    return {g: min(fr.values()) for g, fr in gain_fractions(summary).items()}


def good_band(worst: Mapping[float, float], threshold: float = 0.8) -> List[float]:
    """The longest run of consecutive grid gains with ``worst >= threshold`` ([] if none).

    Ties go to the run with the higher mean fraction, then to the lower gains.
    """
    gains = sorted(worst)
    runs: List[List[float]] = []
    current: List[float] = []
    for g in gains:
        if worst[g] >= threshold:
            current.append(g)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    if not runs:
        return []
    # max() keeps the first of equal keys, i.e. the lower gains.
    return max(runs, key=lambda run: (len(run), statistics.mean(worst[g] for g in run)))


def _parse_value(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return text


def _describe_block(noise: float, rows: Sequence[Mapping[str, Any]]) -> str:
    seeds = sorted({r["seed"] for r in rows})
    if seeds == list(range(seeds[0], seeds[-1] + 1)) and len(seeds) > 1:
        seed_text = f"seeds {seeds[0]}-{seeds[-1]}"
    else:
        seed_text = ("seed " if len(seeds) == 1 else "seeds ") + ",".join(str(s) for s in seeds)
    open_headings = {r.get("heading") for r in rows if r["scenario"] != "memory_maze"}
    maze_headings = {r.get("heading") for r in rows if r["scenario"] == "memory_maze"}
    if open_headings | maze_headings <= {None}:
        heading_text = "start heading 0"
    else:
        parts = []
        if open_headings - {None}:
            parts.append(f"{len(open_headings - {None})} headings")
        if maze_headings - {None}:
            parts.append(f"maze {len(maze_headings - {None})} headings")
        heading_text = ", ".join(parts)
    return f"noise {noise:g}, {seed_text}, {heading_text}"


def _fmt_ticks(value: Any) -> str:
    return "-" if value is None else f"{value:g}"


def print_block(noise: float, rows: Sequence[Mapping[str, Any]]) -> None:
    summary = summarise(rows)
    print(f"\n=== {_describe_block(noise, rows)} ===")
    for scen, by_gain in summary.items():
        print(f"\n{scen}")
        for gain, v in by_gain.items():
            extra = f"  vrest {v['vrest']:4.0%}" if "vrest" in v else ""
            if "recall_rate" in v:
                extra += f"  recall {v['recall_rate']:.0%}"
            if "recall_ok" in v:
                extra += f" (ok {v['recall_ok']:.0%} of runs)"
            if "train_ticks" in v:
                extra += f"  train {_fmt_ticks(v['train_ticks'])}"
            if "first_hidden_ticks" in v:
                extra += f"  first {_fmt_ticks(v['first_hidden_ticks'])}"
            if "median_recall_ticks" in v:
                extra += f"  median {_fmt_ticks(v['median_recall_ticks'])}"
            print(f"  value_gain {gain:4.2f}: mean {v['mean']:6.1f}  (min {v['min']}, max {v['max']}){extra}")
    print("\nrobust band (>= 80% of best mean):")
    for scen, r in robustness(summary).items():
        print(f"  {scen:13s} best {r['best_mean']:.1f}; good at {r['good_gains']}")
    fractions = gain_fractions(summary)
    if not fractions:
        print("\nworst-scenario fraction: n/a (no gain was run for every scenario)")
        return
    print("\nworst-scenario fraction (min over scenarios of mean / best mean):")
    for gain, fr in fractions.items():
        limiting = min(fr, key=lambda s: (fr[s], s))
        print(f"  value_gain {gain:4.2f}: {fr[limiting]:.2f}  ({limiting})")
    worst = {g: min(fr.values()) for g, fr in fractions.items()}
    for threshold in BAND_THRESHOLDS:
        band = good_band(worst, threshold)
        text = f"{band[0]:.2f} .. {band[-1]:.2f} ({len(band)} gains)" if band else "none"
        print(f"  good band (worst >= {threshold:.2f}): {text}")


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", default=",".join(SCENARIOS))
    parser.add_argument("--gains", default=",".join(str(g) for g in DEFAULT_GAINS),
                        help="comma-separated value_gain grid; 'default' = each scenario's own")
    parser.add_argument("--seeds", type=int, default=4, help="number of seeds (default 4)")
    parser.add_argument("--seed-start", type=int, default=1, help="first seed (default 1)")
    parser.add_argument("--noise", type=float, default=0.03)
    parser.add_argument("--headings", type=int, default=None, metavar="N",
                        help="vary the start heading: N headings for open scenarios, 5 fixed for the maze")
    parser.add_argument("--maze-headings", default=None, metavar="SET",
                        help="maze start headings: 'default' (5 near 0), 'full' (16 over the circle) or N")
    parser.add_argument("--noise-both", action="store_true",
                        help="--noise over seeds, plus noise 0 over headings (8 or --headings N; maze 5)")
    parser.add_argument("--ticks", type=int, default=None, help="override every scenario's tick budget")
    parser.add_argument("--workers", type=int, default=None, help="worker processes (default: all cores)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="config override applied to every run, e.g. value_memory.lookahead=1.5")
    parser.add_argument("--json", action="store_true", help="print raw rows as JSON")
    parser.add_argument("--allow-identical-seeds", action="store_true",
                        help="run several seeds although no stochastic element is on (one sample, "
                             "not N; prints a warning instead of refusing, see core.seeds)")
    args = parser.parse_args(argv)
    if args.seeds < 1:
        parser.error("--seeds must be >= 1")
    if args.headings is not None and args.headings < 1:
        parser.error("--headings must be >= 1")
    if args.maze_headings is not None:
        try:
            maze_heading_set(args.maze_headings)
        except ValueError as exc:
            parser.error(str(exc))
    if args.noise_both and args.noise == 0.0:
        parser.error("--noise-both already runs a noise-0 block; give a nonzero --noise for the seed block")

    gains: List[Optional[float]] = [None if g == "default" else float(g) for g in args.gains.split(",")]
    overrides = {}
    for item in args.set:
        key, _, value = item.partition("=")
        overrides[key] = _parse_value(value)
    scenarios = args.scenarios.split(",")
    seeds = range(args.seed_start, args.seed_start + args.seeds)
    if args.noise_both:
        rows = sweep_both(scenarios, gains, seeds, args.noise, overrides, args.ticks, args.workers,
                          args.headings or NOISE_BOTH_HEADINGS, args.maze_headings,
                          allow_identical_seeds=args.allow_identical_seeds)
    else:
        rows = sweep(scenarios, gains, seeds, args.noise, overrides, args.ticks, args.workers, args.headings,
                     args.maze_headings, allow_identical_seeds=args.allow_identical_seeds)
    if args.json:
        print(json.dumps(rows, indent=1))
        return
    for noise, block in by_noise(rows).items():
        print_block(noise, block)


if __name__ == "__main__":
    main()
