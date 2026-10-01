## B1 — Determinism baseline regenerated after Criticality integration
**Date:** 2025-12-16  
**Why:** `kappa` and `avalanche_size` switched from placeholder values to real `CriticalityField` outputs, which are included in the determinism hash.  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `tests/determinism/baseline_hashes.json` updated; determinism gate remains enforced.

## B2 — Determinism baseline regenerated after Observation wiring
**Date:** 2025-12-16  
**Why:** TickData now logs observation-derived fields and checksums; hashing reflects real Observation output each tick.  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `tests/determinism/baseline_hashes.json` and `tests/determinism/baseline_meta.json` updated; determinism gate remains enforced.

## D1 — Baseline regenerated for TRN/microsleep/replay logging (Milestone 4)
**Date:** 2025-12-16  
**Why:** TickData schema v2.1.2 logs TRN state, microsleep, and replay signals; determinism hash now includes these fields.  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `tests/determinism/baseline_hashes.json` and `tests/determinism/baseline_meta.json` updated; determinism gate remains enforced.

## E1 — Baseline regenerated for Spatial logging (Milestone 5A)
**Date:** 2025-12-16  
**Why:** TickData schema v2.1.3 logs spatial outputs (hd_angle, grid_x, grid_y, place_id) derived from egomotion; hashes include these fields.  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `tests/determinism/baseline_hashes.json` and `tests/determinism/baseline_meta.json` updated; determinism gate remains enforced.

## F1 — Baseline regenerated for Working Memory + Action logging (Milestone 5B)
**Date:** 2025-12-16  
**Why:** TickData schema v2.1.4 logs working memory load/novelty and action outputs; world movement now driven by deterministic actions.  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `tests/determinism/baseline_hashes.json` and `tests/determinism/baseline_meta.json` updated; determinism gate remains enforced.

## F2 — Baseline regenerated after egomotion sign fix
**Date:** 2025-12-16  
**Why:** Egomotion forward_delta now preserves sign (projection onto heading); determinism hash includes observation-derived fields.  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `tests/determinism/baseline_hashes.json` and `tests/determinism/baseline_meta.json` updated; determinism gate remains enforced.

## G1 — Determinism helpers moved to core/, criticality_active logged, baseline regenerated
**Date:** 2026-10-01  
**Why:** Two changes touched the determinism hash. (1) `generate_trace`, `build_current_trace`, `BASELINE_PATH` and the seed/tick constants moved from `tests/determinism` into a new `core/determinism.py`, so app code (`app/routes/api.py`) and the baseline tool no longer import the test package. (2) `Engine._log_tick` now populates `criticality_active`; the field already existed in `TickData` but was never set, so it sat at 0 in every trace and all downstream analysis. Schema bumped 2.1.4 → 2.1.5.  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `tests/determinism/baseline_hashes.json` and `baseline_meta.json` updated; determinism gate remains enforced and passes. A new guard test (`tests/determinism/test_criticality_logged.py`) asserts `criticality_active` stays non-constant so this logging cannot silently regress.

## DEC-1 — Legacy v1 parity is out of scope; no drift comparison
**Date:** 2026-10-01  
**Decision:** v2 (Critical Rat) is a fresh model, not a faithful port of the v1 monolith. We will **not** capture a v1 behavioural baseline or gate v2 against v1 drift. `CHECKLIST_V2.md` §0 (legacy preservation + baseline capture) is closed as **cut**, except that the v1 source remains preserved in git history at commit `0b81d62` (reachable from `main`).  
**Why:** The v1 `app.py` is a ~180 KB monolith with a different architecture; exact parity was never a goal, and a drift gate against it would be high effort and low value for a solo research build. The determinism gate already protects v2 against its own regressions, which is what matters.  
**Impact:** `critical-rat.zip` (a 421 KB archive of commit `0b81d62`) removed from the repo; recover v1 with `git checkout 0b81d62`. A local `legacy-v0.9` tag marks that commit but could not be pushed from the automated session (GitHub returned 403 on tag refs); run `git push origin legacy-v0.9` to publish it. The regression harness compares v2 against its own committed baseline only (and is not yet wired into CI — tracked in RECOMMENDATIONS.md).

## G2 — Baseline regenerated after closing the perception loop (v2 "NEXT" work)
**Date:** 2026-10-01  
**Why:** Behaviour changed (the determinism trace values moved; the TickData schema shape did not, so schema_version stays 2.1.5). Changes: (1) an `EngineConfig` injection seam (`core/config.py`) now feeds every subsystem — defaults for unchanged systems are byte-identical; (2) sensors now raycast real world geometry (walls + `WorldObject` targets/hazards) instead of emitting RNG noise, and the basal ganglia steer toward visible targets and away from walls, so perception drives behaviour; (3) the astrocyte uses effort-scaled demand plus glycogen regeneration so a resting agent sustains and only sustained effort triggers microsleep.  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `tests/determinism/baseline_hashes.json` + `baseline_meta.json` updated; gate still enforced and passing. New tests: `tests/experiments/test_beacon_perception.py` (sighted agent reaches a beacon, blind one does not), `tests/physiology/test_energy_equilibrium.py`, `tests/tournaments/test_dna_effect.py`.

## DEC-2 — Removed the vestigial app/ Flask server
**Date:** 2026-10-01  
**Decision:** Deleted the `app/` package (and `tests/api/`). It drove a live engine but serialized a ~50-field hardcoded-zeros dict matching the retired v1 frontend schema, served no frontend, and imported from the test package. The `ui/` replay GUI is the supported server.  
**Why:** It tracked a dead contract and was pure maintenance burden. A live-engine view, if wanted later, should be rebuilt against the real `TickData` schema on top of the new `EngineConfig` seam.  
**Impact:** `app/` and `tests/api/` removed; `core/determinism.py` (added in G1) is now the only home of the determinism helpers the app used to re-import. `legacy-v0.9` / commit `0b81d62` still hold the old code if needed.

## G3 — Criticality reimplemented as a driven branching process; real kappa statistic
**Date:** 2026-10-01  
**Why:** The previous lattice was bistable (silent below branching ratio 1, runaway above) and never produced a power-law avalanche distribution, and `kappa` was an EMA of the active-count ratio, not the criticality statistic. Replaced with the standard Beggs & Plenz driven branching process (seed one cell when quiescent, each active cell activates each neighbour with probability `coupling`, so sigma = 4*coupling), and compute `kappa` as the Shew et al. (2009) statistic over the avalanche-size distribution (reference power-law exponent 1.5). The validation sweep now asserts real physics: kappa rises monotonically and crosses ~1, mean avalanche size grows with coupling (subcritical 0.77 -> critical 0.91 -> supercritical 1.15 at seed 123).  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `brain/systems/criticality.py` rewritten; `experiments/criticality_validation.py` and its CI test assert the regime trends; determinism baseline regenerated (gate still passing). Obsolete `CriticalityConfig` fields (fire_threshold, noise_drive, refractory_reset, max_activity) removed.

## G4 — Reward signal, causal dopamine, and replay-consolidated value map
**Date:** 2026-10-01  
**Why:** Neuromodulators were a random walk read by nothing, and replay cycled a buffer that consolidated nothing. Introduced a coherent reward loop: (1) the engine computes a per-tick `reward` from the world (distance closed toward the nearest target, a contact bonus, minus pain) and logs it (schema 2.1.5 -> 2.1.6); (2) dopamine now encodes a reward-prediction error around an EMA baseline and feeds action selection (low dopamine boosts exploration), so it closes a causal loop onto behaviour; (3) a plastic `ValueMemory` (place_id -> value) is updated online and, during microsleep, the existing replay gating drives temporal-difference backups that propagate value backward along the trajectory — replay now consolidates which places predict reward. NE/ACh/5HT are now deterministic readouts of pain/novelty/mood but do not yet drive behaviour (documented in RECOMMENDATIONS.md). The consolidated value map is not yet used for navigation (future work).  
**Command:** `python3 tools/update_determinism_baseline.py --i-know-what-im-doing`  
**Params:** seed=1337, ticks=200  
**Impact:** `core/neuromodulation.py` rewritten; `brain/systems/value_memory.py` added; `core/engine.py`, `core/config.py`, `brain/systems/basal_ganglia.py`, `metrics/schema.py` updated; new tests for dopamine and value consolidation; determinism baseline regenerated.

## G5 — Behavioural assertions, regression gate, and honest framing
**Date:** 2026-10-01  
**Why:** Closing out the "earn the science" work. Added a path-integration-tracks-truth test; made `regression/compare.py` tolerance-aware (numeric comparison within rel/abs tolerance instead of exact equality) and regenerated the committed `regression/baseline/` to current behaviour, with a new test that gates current tournament output against it in the suite (hence CI). Added a "What this is (and isn't)" section to the README stating plainly that this is an engineering instrument with grounded-but-simplified cognition, not a validated rodent-brain model.  
**Impact:** `regression/compare.py`, `regression/baseline/` and the README updated; new tests `tests/engine/test_path_integration_truth.py` and `tests/regression/test_regression_against_baseline.py`. No determinism-baseline change (behaviour of the default engine unchanged).

## G6 — Norepinephrine, acetylcholine and serotonin become control signals
**Date:** 2026-10-01  
**Why:** Only dopamine drove behaviour; the other three were state readouts. Coupled each to action selection with a neuroscience-grounded role: acetylcholine sharpens sensory precision (scales the vision drive), norepinephrine raises threat/arousal sensitivity (scales pain avoidance and freezing), serotonin raises patience (willingness to rest). All couplings are config-gated and no-ops at baseline modulator levels (DA=0.5, NE=0, ACh=0, 5HT=0.5), and only bite when there is something to modulate (a target in view, pain present, reward shaping mood). The default/barren traces are therefore unchanged (determinism and regression baselines unaffected).  
**Impact:** `brain/systems/basal_ganglia.py` and `core/config.py` updated; `select_action` now takes the full modulator dict; tests in `tests/engine/test_neuromodulation.py` assert each coupling changes behaviour and that baseline levels are no-ops. No baseline regeneration needed.
