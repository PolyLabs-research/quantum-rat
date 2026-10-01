# Critical Rat / Quantum Rat v2

**A deterministic “simulation as instrument” research engine for agent behaviour, assays, tournaments, and analysis.**

This repo is built around strict boundaries and reproducibility:

* **World (ground truth)** steps deterministically.
* **Brain** never reads world state directly — it receives an `Observation` and returns an `Action`.
* **A single seed** controls the run; determinism is enforced via trace hashing in CI.
* **Assays** run headless (JSONL ticks + summary outputs), and **tournaments** are reproducible + fair.
* **Analysis** converts runs into tables + plots, and a **replay GUI** lets you inspect runs tick-by-tick.

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