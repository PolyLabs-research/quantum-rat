# Critical Rat / Quantum Rat v2

**A deterministic “simulation as instrument” research engine for agent behaviour, assays, tournaments, and analysis.**

This repo is built around strict boundaries and reproducibility:

* **World (ground truth)** steps deterministically.
* **Brain** never reads world state directly — it receives an `Observation` and returns an `Action`.
* **A single seed** controls the run; determinism is enforced via trace hashing in CI.
* **Assays** run headless (JSONL ticks + summary outputs), and **tournaments** are reproducible + fair.
* **Analysis** converts runs into tables + plots, and a **replay GUI** lets you inspect runs tick-by-tick.

---

## What this is (and isn't)

This is an **engineering instrument first**: a deterministic, reproducible, testable
sandbox for building and measuring brain-inspired agents. The scaffolding (RNG discipline,
the World→Observation→Brain boundary, per-tick logging, the determinism gate, reproducible
tournaments) is the solid part and the point of the project.

The cognitive components are **scientifically grounded but deliberately simplified**, and
honestly at different stages of maturity:

* **Real models.** Criticality is a driven branching process whose avalanche-size
  distribution and κ statistic (Shew et al. 2009) behave correctly across sub-/critical/
  super-critical regimes. The perception loop is closed (vision/pain/whiskers come from real
  world geometry and drive behaviour). All four neuromodulators are causal: dopamine (reward-
  prediction error → exploration), norepinephrine (threat sensitivity), acetylcholine (sensory
  precision), serotonin (patience). A plastic place-value map is learned by TD(0) and consolidated
  by replay; the agent uses it for memory-guided navigation back to a now-hidden goal
  (`experiments/memory_navigation.py`). Repeated recall reinforces the map rather than eroding it,
  and replay is a data-efficiency speed-up (one demonstration + replay recalls in ~16 ticks vs ~66
  for online learning alone). Place values generalise to neighbouring cells (overlapping place
  fields), so this works at the engine's default spatial resolution and forward bias. Criticality
  is coupled to cognition too: a near-critical cortical gain (peaking at κ≈1) scales sensory
  precision, so the field is not just an instrumented side-process.
* **Honest limits / in progress.** Whether the criticality gain improves a given behaviour is
  task-dependent (navigation time is not a clean function of it), and the assays remain simple
  single-episode or few-trial tasks.

So: **this is not a validated model of a real rodent brain.** It's a place to build such
models one defensible piece at a time, with the engineering guaranteeing that whatever you
measure is reproducible. See `RECOMMENDATIONS.md` for what's done and what's next, and
`docs/decisions.md` for the rationale behind each step.

---

## What’s in here

### Engine features (current)
* **Central RNG authority** + injected RNG streams.
* **Per-tick TickData logging** (JSONL) + stable hashing.
* **Determinism regression gate** (baseline hashes + CI).
* **Sensors → Observation contract** (no “position cheating”).
* **Physiology + neuromodulation** logged.
* **Criticality field** + avalanche detection + κ (kappa).
* **TRN gating**, microsleep + replay gating.
* **Spatial system** driven purely by egomotion (HD + grid integrator + place id).
* **Working memory** (bounded) + deterministic basal ganglia action selection.
* **Action-driven world movement** (no random wandering).
* **Closed perception loop:** sensors raycast real world geometry (walls + `WorldObject`
  targets/hazards); the brain steers toward visible targets and away from walls.
* **`EngineConfig` seam** (`core/config.py`): every subsystem is tunable without editing source.

### Assays / Protocols (headless)
* `beacon` — navigate to a visible target (a direct test that sensing drives behaviour)
* `foraging` — collect several scattered targets (sighted agents collect them all, blind ones almost none)
* `open_field`
* `t_maze`
* `morris_water_maze`
* `survival_arena`

### Tournaments
* **AgentDNA** + deterministic fingerprinting; genes feed `EngineConfig` so agents differ behaviourally.
* **TournamentManager** + CLI runner.
* **Fairness:** Same environment/protocol seeds across agents; only agent offsets differ.
* **Stable leaderboard** ordering with explicit tie-break.

### Analysis
* Extract tournament/experiment runs to **Parquet**.
* Compute κ distribution, avalanche distributions, sleep/replay rates, score distributions.
* Generate `analysis/report/report.md` + plots.

### Replay GUI (read-only)
* Browse run directories.
* Select episode (agent + protocol).
* Scrub ticks (paged JSONL).
* Basic plots (kappa, avalanche, sleep/replay, spatial trace, actions).

---

## Repo layout (high level)

```text
core/        – Engine, world, sensors, rng, pipeline
brain/       – Contracts + systems (criticality, TRN, spatial, WM, BG, etc.)
metrics/     – TickData schema, logger, hash utilities
experiments/ – Protocol framework + headless runner
tournaments/ – Tournament manager + runner
agents/      – AgentDNA and agent container
analysis/    – Extract → metrics → report + plots
ui/          – Replay server + static frontend
tests/       – Determinism gate + unit/integration tests
docs/        – Decisions log + architecture/spec notes
artifacts/   – Agent proof artifacts, run evidence, etc.