# Quantum Rat v2.1 — Build Checklist (Agent-Gated)

This is the single source of truth for build progress.
Rule: no box may be checked unless its DoD is proven (tests/logs/artifacts).

> **Reconciled 2026-10-01.** Milestones 4–8 were implemented but left unchecked; each
> box below now cites its proving artifact and/or test. Where a DoD is only *partly*
> met (e.g. a subsystem is wired and logged but not yet scientifically validated), that
> is called out inline and tracked in `RECOMMENDATIONS.md`. Deeper design gaps are not
> hidden by a ticked box.

## 0) Legacy preservation + baseline capture
- [x] Preserve legacy state — v1 is tagged `legacy-v0.9` (commit `0b81d62`, last commit with the monolithic `app.py`). The old `critical-rat.zip` was a 421 KB archive of the same commit and has been removed. Recover v1 with `git checkout legacy-v0.9`.
- [~] Capture legacy baseline trace for drift comparison — **CUT.** v2 is a fresh model, not a port; no v1 drift gate. See `docs/decisions.md` DEC-1.
  - [~] Run legacy for 2000 frames in deterministic mode — cut (DEC-1)
  - [~] Save `tests/fixtures/legacy_baseline.json` — cut (DEC-1)
  - [~] Document exact command + seed — cut (DEC-1)

## 1) Repo skeleton matches v2.1 spec (Milestone 0.1)
- [x] Directory tree exists: `app/ core/ brain/ experiments/ metrics/ tests/ docs/`
- [x] Imports resolve (no circular deps)
- [x] Placeholder README updated to point to v2.1 spec + backlog

## 2) Deterministic RNG infrastructure (Milestone 0.2)
- [x] Single RNG authority implemented (`core/rng.py`)
- [x] No raw `random` / `np.random` usage outside RNG authority (audited: zero leaks)
- [x] Agent-level seed offset support exists

## 3) TickData + logging (Milestone 0.3)
- [x] `metrics/schema.py` defines TickData (+ schema_version, now 2.1.5)
- [x] `metrics/logger.py` emits JSONL per tick
- [x] Per-tick hash helper exists (stable ordering, deterministic)

## 4) CI determinism gate (Milestone 0.4)
- [x] `tests/determinism/` baseline trace hashes committed
- [x] CI fails on any determinism regression (`tests/determinism/test_trace_hash.py`)
- [x] Baseline update requires explicit flag/script (auditable) — last regenerated 2026-10-01 for `criticality_active` logging + schema 2.1.5 (see `docs/decisions.md` G1); earlier regen 2025-12-16 after Criticality integration

## 5) World + sensors + Observation contract (Milestone 1)
- [x] Deterministic world stepping (`core/world.py`, `core/entities.py`)
- [x] Sensors produce normalized Observation (`core/sensors.py`, `brain/contracts.py`) — proof: `artifacts/agentC_observation_proof.md`
- [x] Observation includes egomotion/proprioception (no position cheating) — real egomotion test in `tests/egomotion/test_egomotion_stub.py`
  - Note: vision/whisker/pain channels are currently noise and the world has no features, so the perception loop is open. Tracked in `RECOMMENDATIONS.md` (close-the-loop).

## 6) Physiology + neuromodulation (Milestone 2)
- [x] ATP/glycogen dynamics implemented, logged in TickData (`core/physiology.py`)
- [x] DA/5HT/NE/ACh updates deterministic + logged (`core/neuromodulation.py`)
  - Note: neuromodulators are logged but inert (no downstream coupling); physiology drains to collapse under constant demand. Tracked in `RECOMMENDATIONS.md`.

## 7) Criticality core (Milestone 3 — highest priority)
- [x] CriticalityField lattice implemented (`brain/systems/criticality.py`)
- [x] Avalanche detection + κ (EMA) implemented + logged; `criticality_active` now logged too (2026-10-01)
- [x] Validation sweep script exists + has assertions (`experiments/criticality_validation.py`)
- [x] Reduced sweep runs in CI (`tests/experiments/test_criticality_validation.py`)
  - Note: the current monotonic assertion is weak (passes trivially at low step counts); κ is an active-ratio EMA, not the criticality κ statistic. Tracked in `RECOMMENDATIONS.md`.

## 8) TRN, microsleep, replay, memory (Milestone 4)
- [x] TRN gating states logged (`trn_state` in TickData) — proof: `artifacts/agentD_milestone4_proof.md`
- [x] Microsleep episodes reproducible (determinism gate + `tests/experiments/test_runner_determinism.py`)
- [x] Replay only occurs during microsleep (enforced by a guard in `core/engine.py` that raises otherwise)
  - Note: replay cycles a buffer but does not yet consolidate/learn (Epic 4.3 DoD "replay improves performance" is NOT met). Tracked in `RECOMMENDATIONS.md`.

## 9) Spatial + action selection (Milestone 5)
- [x] Grid/place/HD uses egomotion (`brain/systems/spatial.py`) — proof: `artifacts/agentF_milestone5_proof.md`
- [x] Working memory bounded + logged (`brain/systems/working_memory.py`, capacity-bounded deque)
- [x] Basal ganglia action selection deterministic (`brain/systems/basal_ganglia.py`)
  - Note: path integration is unvalidated against ground truth; "basal ganglia" is a hand-tuned linear scorer. Tracked in `RECOMMENDATIONS.md`.

## 10) Assays + UI parity (Milestone 6)
- [x] Headless experiment runner works (`experiments/runner.py`, `tests/experiments/test_protocol_lifecycle.py`) — proof: `artifacts/agentG_milestone6_proof.md`, `artifacts/agentH_milestone6_proof.md`
- [x] Open Field / T-Maze / Water Maze / Survival implemented as protocols (`experiments/protocols/`)
- [x] Flask UI reads from Engine history / run logs (no direct World access) — replay GUI proof: `artifacts/agentR_replay_gui_proof.md`
  - Note: assay position references are inconsistent (t_maze scores off the internal estimate `grid_x`, others off true `pos`). Tracked in `RECOMMENDATIONS.md`.

## 11) Agent container + tournaments (Milestone 7)
- [x] AgentDNA + Agent container implemented (`agents/dna.py`, `agents/agent.py`) — proof: `artifacts/agentJ_milestone7_proof.md`
- [x] TournamentManager runs N agents fairly + reproducibly (`tests/tournaments/test_fairness.py`, `test_tournament_determinism.py`)
- [x] Leaderboard output stable under same seed (`tests/tournaments/`)
  - Note: `Agent.configure_engine` is currently a no-op, so AgentDNA parameters are never applied — agents do not yet differ behaviourally and the leaderboard reflects RNG offset, not genome. `generate_population` also ignores its `seed`. Tracked in `RECOMMENDATIONS.md` (the make-DNA-real unlock).

## 12) Regression + analysis tooling (Milestone 8)
- [x] Regression harness exists and compares against a committed v2 baseline (`regression/run_regression.py`, `regression/compare.py`, `regression/baseline/`) — proof: `artifacts/agentL_regression_proof.md`. Legacy comparison cut (DEC-1).
  - Note: the harness is not yet executed by CI or the test suite, and compares with exact equality (no float tolerance). Tracked in `RECOMMENDATIONS.md`.
- [x] Analysis scripts reproduce κ/performance and avalanche distributions (`analysis/`) — proof: `artifacts/agentM_analysis_proof.md`

## Notes / Decisions log
- [x] `docs/decisions.md` exists and records spec deviations + rationale (determinism-baseline changelog plus decisions G1 and DEC-1)

## Legend
- `[x]` done, DoD proven (artifact/test cited)
- `[~]` cut / out of scope (rationale in `docs/decisions.md`)
- Inline **Note** = box is legitimately checked at the DoD level, but a deeper design or
  scientific gap remains open; see `RECOMMENDATIONS.md`.
