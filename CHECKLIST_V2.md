# Quantum Rat v2.1 — Build Checklist (Agent-Gated)

This is the single source of truth for build progress.
Rule: no box may be checked unless its DoD is proven (tests/logs/artifacts).

> **Reconciled 2026-10-01.** Milestones 4–8 were implemented but left unchecked; each
> box below now cites its proving artifact and/or test. Where a DoD is only *partly*
> met (e.g. a subsystem is wired and logged but not yet scientifically validated), that
> is called out inline and tracked in `RECOMMENDATIONS.md`. Deeper design gaps are not
> hidden by a ticked box.

## 0) Legacy preservation + baseline capture
- [x] Preserve legacy state — the v1 source lives in git history at commit `0b81d62` (the last commit with the monolithic `app.py`, reachable from `main`). The old `critical-rat.zip` was a 421 KB archive of that same commit and has been removed. Recover v1 with `git checkout 0b81d62`. A local tag `legacy-v0.9` marks it; run `git push origin legacy-v0.9` to publish the friendly name (the automated session could not push tag refs — GitHub returned 403).
- [~] Capture legacy baseline trace for drift comparison — **CUT.** v2 is a fresh model, not a port; no v1 drift gate. See `docs/decisions.md` DEC-1.
  - [~] Run legacy for 2000 frames in deterministic mode — cut (DEC-1)
  - [~] Save `tests/fixtures/legacy_baseline.json` — cut (DEC-1)
  - [~] Document exact command + seed — cut (DEC-1)

## 1) Repo skeleton matches v2.1 spec (Milestone 0.1)
- [x] Directory tree exists: `core/ brain/ experiments/ metrics/ tournaments/ agents/ analysis/ ui/ tests/ docs/` (the original `app/` server was later removed — see `docs/decisions.md` DEC-2)
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
  - Done (2026-10-01): the perception loop is now closed. Sensors raycast real world geometry (walls + `WorldObject` targets/hazards) and the brain steers on it; proof is `tests/experiments/test_beacon_perception.py` (a sighted agent reaches a beacon, a blind one does not). See `docs/decisions.md` G2.

## 6) Physiology + neuromodulation (Milestone 2)
- [x] ATP/glycogen dynamics implemented, logged in TickData (`core/physiology.py`)
- [x] DA/5HT/NE/ACh updates deterministic + logged (`core/neuromodulation.py`)
  - Done / partly done (2026-10-01): physiology no longer collapses — effort-scaled demand + glycogen regeneration give a sustainable rest state (`tests/physiology/test_energy_equilibrium.py`). Dopamine is now causal (reward-prediction error → exploration; `tests/engine/test_neuromodulation.py`); NE/ACh/5HT are now state readouts but do not yet drive behaviour (tracked in `RECOMMENDATIONS.md`). See `docs/decisions.md` G4.

## 7) Criticality core (Milestone 3 — highest priority)
- [x] CriticalityField lattice implemented (`brain/systems/criticality.py`)
- [x] Avalanche detection + κ (EMA) implemented + logged; `criticality_active` now logged too (2026-10-01)
- [x] Validation sweep script exists + has assertions (`experiments/criticality_validation.py`)
- [x] Reduced sweep runs in CI (`tests/experiments/test_criticality_validation.py`)
  - Done (2026-10-01): reimplemented as a driven branching process; κ is now the Shew et al. (2009) statistic over the avalanche-size distribution. The sweep asserts real physics (κ rises monotonically and crosses ~1, mean avalanche size grows with coupling). See `docs/decisions.md` G3. Criticality is now also coupled to cognition: a near-critical cortical gain (peaking at κ≈1) scales sensory precision in action selection (`experiments/criticality_cognition.py`, `docs/decisions.md` G9).

## 8) TRN, microsleep, replay, memory (Milestone 4)
- [x] TRN gating states logged (`trn_state` in TickData) — proof: `artifacts/agentD_milestone4_proof.md`
- [x] Microsleep episodes reproducible (determinism gate + `tests/experiments/test_runner_determinism.py`)
- [x] Replay only occurs during microsleep (enforced by a guard in `core/engine.py` that raises otherwise)
  - Done (2026-10-01): a plastic place-value map is learned by TD(0) and consolidated by replay (`tests/engine/test_value_memory.py`); the agent uses it to navigate back to a now-hidden goal (`experiments/memory_navigation.py`, `tests/experiments/test_memory_navigation.py`). Repeated recall reinforces the map rather than eroding it, and replay is a data-efficiency speed-up (one demonstration + replay recalls in ~16 ticks vs ~66 for online learning alone) — the honest reading of Epic 4.3's "replay improves performance", at the engine's default spatial resolution and forward bias (spatial value generalisation, `generalization_radius`). See `docs/decisions.md` G4, G7, G8, G11.

## 9) Spatial + action selection (Milestone 5)
- [x] Grid/place/HD uses egomotion (`brain/systems/spatial.py`) — proof: `artifacts/agentF_milestone5_proof.md`
- [x] Working memory bounded + logged (`brain/systems/working_memory.py`, capacity-bounded deque)
- [x] Basal ganglia action selection deterministic (`brain/systems/basal_ganglia.py`)
  - Partly done (2026-10-01): path integration is now validated against ground truth (`tests/engine/test_path_integration_truth.py`). "Basal ganglia" remains a hand-tuned linear scorer (now vision- and dopamine-driven); a biologically structured version is future work.

## 10) Assays + UI parity (Milestone 6)
- [x] Headless experiment runner works (`experiments/runner.py`, `tests/experiments/test_protocol_lifecycle.py`) — proof: `artifacts/agentG_milestone6_proof.md`, `artifacts/agentH_milestone6_proof.md`
- [x] Open Field / T-Maze / Water Maze / Survival implemented as protocols (`experiments/protocols/`)
- [x] Flask UI reads from Engine history / run logs (no direct World access) — replay GUI proof: `artifacts/agentR_replay_gui_proof.md`
  - Done (2026-10-01): assay position references are now consistent — t_maze scores off true `pos`, like the other assays. Added a `beacon` assay (sense a single target) and a multi-landmark `foraging` assay (collect several scattered targets); both genuinely depend on vision (`tests/experiments/test_beacon_perception.py`, `test_foraging.py`).

## 11) Agent container + tournaments (Milestone 7)
- [x] AgentDNA + Agent container implemented (`agents/dna.py`, `agents/agent.py`) — proof: `artifacts/agentJ_milestone7_proof.md`
- [x] TournamentManager runs N agents fairly + reproducibly (`tests/tournaments/test_fairness.py`, `test_tournament_determinism.py`)
- [x] Leaderboard output stable under same seed (`tests/tournaments/`)
  - Done (2026-10-01): `Agent.configure_engine` now applies DNA to the basal-ganglia config (read every tick via the `EngineConfig` seam), so genes change behaviour and the leaderboard spreads across agents; `generate_population` now uses its `seed`. Proof: `tests/tournaments/test_dna_effect.py`.

## 12) Regression + analysis tooling (Milestone 8)
- [x] Regression harness exists and compares against a committed v2 baseline (`regression/run_regression.py`, `regression/compare.py`, `regression/baseline/`) — proof: `artifacts/agentL_regression_proof.md`. Legacy comparison cut (DEC-1).
  - Done (2026-10-01): the harness now runs in the test suite (hence CI) against the committed baseline (`tests/regression/test_regression_against_baseline.py`), and `regression/compare.py` compares numbers with a tolerance instead of exact equality.
- [x] Analysis scripts reproduce κ/performance and avalanche distributions (`analysis/`) — proof: `artifacts/agentM_analysis_proof.md`

## Notes / Decisions log
- [x] `docs/decisions.md` exists and records spec deviations + rationale (determinism-baseline changelog plus decisions G1 and DEC-1)

## Legend
- `[x]` done, DoD proven (artifact/test cited)
- `[~]` cut / out of scope (rationale in `docs/decisions.md`)
- Inline **Note** = box is legitimately checked at the DoD level, but a deeper design or
  scientific gap remains open; see `RECOMMENDATIONS.md`.
