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

## G7 — Value-guided navigation and replay-improves-navigation demonstrated
**Date:** 2026-10-01  
**Why:** Completing the replay story. The brain now reads the consolidated place-value map to steer toward higher-value directions (a normalized, magnitude-robust advantage over the current place; `core/engine.py` `_value_signals`, `brain/systems/spatial.py` `place_id_at`, `BasalGangliaConfig.value_gain`). A new water-maze-style experiment (`experiments/memory_navigation.py`) shows the end-to-end effect: after one visible training trial and a sleep (replay) phase, the agent returns to the now-hidden goal from memory (reaching it in ~20-30 ticks across seeds), whereas without consolidation it never does (times out). A "hidden" goal still rewards on contact but is invisible to vision.  
**Scope / honesty:** This holds in a value-driven regime (low `forward_bias`, higher `value_gain`, coarse place fields via `bin_size=2.0` so a single trajectory generalises into a followable 2-D field). The default forward-biased explorer does not exhibit memory navigation — its forward drive swamps the shallow value gradient, and fine place bins make a single trajectory a thin, non-generalising path. That is a limitation of the simple policy/representation, not of the replay mechanism, and is documented in the module and RECOMMENDATIONS.md.  
**Impact:** No determinism or regression baseline change (value steering is a no-op on the barren default/tournament worlds; the experiment uses its own config). New test `tests/experiments/test_memory_navigation.py`.

## G8 — Spatial value generalization (overlapping place fields)
**Date:** 2026-10-01  
**Why:** A single trajectory produced a thin, one-cell-wide value path that the agent fell off, so memory navigation only worked in a contrived regime (coarse bins, low forward bias). `ValueMemory` is now keyed by integer place-cell coordinates `(bx, by)` and spreads each update to neighbouring cells with a decaying kernel (`generalization_radius`, `generalization_falloff`) — overlapping place fields that fill a followable 2-D value field. With generalization, the memory-navigation assay now works at the engine's DEFAULT spatial resolution (`bin_size=0.5`) and DEFAULT `forward_bias=0.8` (reaching the hidden goal in ~14 ticks with replay vs timeout without, identical across 5 seeds); only `value_gain` and `generalization_radius` are turned up.  
**Scope / honesty:** `generalization_radius` defaults to 0 (exact one-cell map, no behavioural change on barren worlds), so determinism and regression baselines are unaffected. Repeated memory recall still gradually erodes the map because online learning continues during recall; the robust claim is the first post-consolidation probe.  
**Impact:** `brain/systems/value_memory.py` rekeyed to cells + kernel; `brain/systems/spatial.py` gained `bins_at`; `core/engine.py` and `core/config.py` updated; `experiments/memory_navigation.py` now uses the near-default config; `tests/engine/test_value_memory.py` updated with a generalization test.

## G9 — Criticality coupled to cognition via a near-critical cortical gain
**Date:** 2026-10-01  
**Why:** The criticality field was an instrumented side-process. Near-criticality is associated with maximal dynamic range / information transmission, so `near_critical_gain(kappa)` (a Gaussian peaking at kappa=1, width `CriticalityConfig.gain_width`) is now computed each tick from the field's kappa and scales sensory (vision) precision in action selection, gated by `BasalGangliaConfig.criticality_gain` (strength; default 0 = off). A sweep (`experiments/criticality_cognition.py`) confirms the gain peaks in the near-critical regime (coupling ~0.25-0.30, sigma~1): gains ~0.61 (subcritical) < ~0.99 (critical) > ~0.82 (supercritical).  
**Scope / honesty:** The coupling strength defaults to 0, so determinism and regression baselines are unaffected. The direct, asserted prediction is that the cortical GAIN peaks near criticality; whether a given behaviour (e.g. beacon time) improves is task-dependent and not claimed, because navigation time is not a monotonic function of sensory gain in this simple policy.  
**Impact:** `brain/systems/criticality.py` gained `near_critical_gain`; `core/config.py` and `brain/systems/basal_ganglia.py` gained the gain coupling; `core/engine.py` computes and passes it; new `experiments/criticality_cognition.py` and `tests/experiments/test_criticality_cognition.py`.

## G10 — Multi-landmark foraging assay
**Date:** 2026-10-01  
**Why:** The assays used single landmarks. Added `experiments/protocols/foraging.py` (registered in the runner): several scattered targets, each removed once collected, scored by how many are collected with a small time penalty. With a wide field of view a sighted agent collects all of them (e.g. 5/5 in ~190 ticks) while a vision-blind agent collects almost none (1/5) — a multi-goal test that vision drives sustained behaviour.  
**Impact:** New protocol + `tests/experiments/test_foraging.py`; `foraging` is now in the runner's protocol list. No determinism/regression baseline change (the gate and regression use other protocols; foraging demonstrations use their own wide-vision config).

## G11 — Value map learned by online TD(0); repeated-recall erosion fixed
**Date:** 2026-10-01  
**Why:** Online value learning updated each visited cell toward the *immediate* reward, so on zero-reward steps it decayed consolidated values toward 0. During repeated hidden-goal recall the agent re-treads the consolidated path, so this actively erased the map and recall failed after the first probe. Replaced it with proper online TD(0) using reward-on-arrival and bootstrapping: on a transition s→s' with reward r received at s', `V(s) ← V(s) + α(r + γV(s') − V(s))`. A place leading toward reward now keeps its value on zero-reward steps (it bootstraps on its successor), so following the gradient reinforces the map instead of decaying it. `replay_transition` was corrected to credit the reward received on arrival at the successor cell; the engine resets the episode (`value_memory.reset_episode()`) on `run(reset=True)` so no transition links across a trial teleport.  
**Consequences (honest):** With correct online learning the agent learns memory navigation from its own experience, so repeated recall no longer erodes — it keeps reaching and gets faster across trials. This also corrected the earlier "replay is necessary for recall" claim (an artifact of the deficient online rule): replay is now shown as a **data-efficiency** speed-up — one demonstration + replay recalls in ~16 ticks vs ~66 for online learning alone, both reaching, robust across 5 seeds.  
**Scope:** No determinism/regression baseline change — on the barren default/tournament worlds reward is 0, so TD targets stay 0 and values never move. Tests updated: `tests/engine/test_value_memory.py` (TD semantics + a no-decay-on-zero-reward test) and `tests/experiments/test_memory_navigation.py` (data-efficiency + repeated-recall-stability).

## G12 — Value lookahead widened to escape a false local maximum (corrects G11)
**Date:** 2026-10-01  
**Why:** G11 said repeated recall "keeps reaching" across trials. That overstated it: in the replay arm the agent timed out on the 4th hidden-goal trial. The value signal only sampled directions ±`TURN_STEP` (about 17°) either side of the heading, so a value peak further to the side looked like "every step is downhill" and the agent stalled in a false local maximum. `Engine.VALUE_FAN_OFFSETS = (TURN_STEP, 0.8, 1.4)` now samples each side out to about 80° and takes the best per side, so a peak off to the side reads as "turn that way".  
**Result:** 6/6 hidden-goal recalls across 5 seeds for both the replay and no-replay arms.  
**Scope:** No determinism/regression baseline change (value steering is a no-op on reward-free worlds, where the value map stays at 0).  
**Impact:** `core/engine.py` (`_value_signals`).

## G13 — Approach shaping no longer punishes eating (found with the lab console)
**Date:** 2026-10-01  
**Why:** The reward's approach term is `approach_weight × (previous distance − current distance)` to the *nearest* target. When the nearest target disappeared (food eaten) or moved (a beacon hopped), the nearest distance jumped by several metres, and the agent was charged that jump as a large negative reward on the next tick: −2.4 to −8.9 after every collection in foraging, and up to −13.9 in the beacon and hazard scenarios. That dipped dopamine right after each success and painted the value map red next to food. The term is now applied only while the nearest target is the same object at the same position as on the previous tick; a change in the target set resets the shaping baseline for one tick.  
**Result (5 seeds × 3000 ticks, live scenarios):** foraging 110 → 120 items; hazard field 55 → 80 items; worst single-tick reward now −0.9 to −1.0 (the pain term) instead of −8.9 to −13.9.  
**Trade-off (honest):** the beacon chase got worse (30 → 20 beacons). The old spike accidentally acted as an extinction signal for the beacon's previous spot. Without it, the value map keeps the old spot attractive and, at the default memory steering (0.8), the agent often returns there first (perseveration). Memory steering 0.3–0.4 recovers or beats the old count (13–19 per 3000 ticks). The same change hurts the hazard field (0 items at 0.4), so no default was retuned; the console exposes the slider and the Beacon scenario's notes describe the effect.  
**Scope:** No determinism or regression baseline change: the gate and regression assays have a single fixed target. Covered by `tests/engine/test_reward_shaping.py`, which fails on the old code.  
**Impact:** `core/engine.py` (`_nearest_target`, `_compute_reward`, `begin_episode`).

## DEC-3 — A live lab console replaces the Plotly replay page
**Date:** 2026-10-01  
**Why:** The old GUI was a read-only replay page that loaded Plotly from a CDN and showed a handful of plots. The model now has real criticality, causal neuromodulators, a learned value map, replay and fatigue, none of which you could watch. `python -m ui` starts a local console with a **Live** view (five scenarios on the real engine, brain panels, live parameters, event log, record-to-replay) and a refreshed **Replay** view (arena with the run's scene, charts with click-to-seek, key moments, tick inspector).  
**Design choices:**
- No third-party JS, no CDN and no build step: plain HTML/CSS and ES modules, so it works offline and needs only Flask.
- Instrumentation only: scenarios arrange the world and run the protocol, while the brain still sees only its `Observation`. Engine additions are read-only accessors (`Engine.context`, decision scores, value signals, criticality cells) that were verified to leave the determinism and regression baselines unchanged.
- Secure local defaults: binds to `127.0.0.1`, rejects non-loopback `Host` headers, POSTs must be JSON, request size and steps per call are capped, parameters are whitelisted and clamped, and a strict CSP is set. `debug=False` is used, where the old entry point ran `debug=True` on `0.0.0.0`.
- Runs now save a `scene.json` (bounds, objects, start pose, glycogen store) from the experiment runner, tournaments (`--include-ticks`) and live recordings, so a replay can draw the world.
- The Memory maze rests the agent between trials (40 ticks of resting physiology, no brain ticks) as real water-maze protocols do, and the rest can be toggled. Over 1500 ticks: 149/149 recalls with rest and replay (median 10 ticks), 87/87 with rest and no replay (median 17), and 7/11 without rest in either arm, because fatigue narrows the sensory gate and path integration drifts.
- *Sensor noise* is exposed as a live parameter. With it off (the default), behaviour is identical across seeds, since the seed then only drives the criticality lattice. With it on, seeds give different runs.

`ui/replay_server.py` remains as a compatibility shim (`from ui.replay_server import app`, `python -m ui.replay_server`).  
**Impact:** new `ui/server.py`, `ui/__main__.py`, `ui/scenarios.py`, `ui/sim_session.py`, `ui/static/` and `metrics/scene.py`; `tests/ui/test_server.py` and `tests/ui/test_sim_session.py` added.

## G14 — Robust memory steering: behaviour no longer hinges on `value_gain`
**Date:** 2026-10-02  
**Read with G15 and G16.** G16 makes G15's split steering the default, corrects the C2 replay rule and the dwell definition below, makes the pacing thresholds relative, raises the map's pain floor with sensor noise, adds wall gating, and re-reports the acceptance numbers with pacing on and off. The numbers in this entry are for max-norm steering (the G14 engine) on the grid {0, 0.4, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0}; on the harness's full default grid (with 0.2 and 0.6) some are less flattering (e.g. the noise-0 worst fraction at gain 2.0 is 0.926, not 0.959).  
**Why:** Behaviour swung with memory steering (`basal_ganglia.value_gain`). A diagnosis found the chain: the TD value map never extinguished tiny self-made positive peaks (approach shaping and same-cell self-bootstrap, ~0.03-0.1); `_value_signals` max-normalises advantages, so at such a local maximum the signals read (-1,-1,-1) and REST, which has no value term, wins (value-induced REST, "vREST", 29-96% of ticks); pain-driven REST was an absorbing freeze that only the value signal's common mode released; the REST trap had been acting as accidental energy pacing; memory overrode visible targets; and sensor noise 0.03 hid most of this, because clamped pain noise acted as a hidden extinction cost. At noise 0 the stock engine collapsed for gains >= 0.8 (beacon 8.0 at the old default 0.8 vs 14.2 at 0.4). This corrects the trade-off described in G13: the 0.3-0.4 steering advice there is obsolete.  
**Changes (all in config, `_channel_scores` stays pure; per-engine state lives on `Engine`):**
- C1 freeze habituation (`freeze_tau=15`, `freeze_pain_threshold=0.2`, `freeze_decay=0.9`): the pain->REST drive is scaled by `exp(-F/tau)`, F counting recent pain-freeze ticks.
- C2 dwell extinction (`value_memory.dwell_extinction=0.02`): a same-cell transition on a positive cell is charged before the TD backup. *Corrected in G16:* as first written the charged reward was stored in the trajectory and replayed unconditionally, which drove dwelt-on cells toward -c/(1-gamma) = -0.2 (aversion, not extinction); and "same cell" means the same place-cell bin, so turns made in place are charged too, not only REST.
- C3 primary-only map (`value_memory.learn_shaping=False`): the map learns contact reward and real pain (>= 0.05; since G16 > max(0.05, sensors.noise)) only; `ctx.reward`, TickData and dopamine still see the shaped reward.
- C4 cue gating (`cue_gate_gain=2.0`): value signals are multiplied by `max(0, 1 - gain * closeness of the nearest visible target)`.
- C5 `value_gain` default 0.8 -> 1.5 (the maze needs >= ~1.0-1.2 to beat FORWARD's lead).
- C6 homeostatic pacing (`pace_rest_bonus`, latch `pace_low=0.4` / `pace_high=0.9`, since G16 fractions of `astrocyte.atp_baseline`): off in the core engine, 5.0 in the beacon, foraging and hazard-field console scenarios. Most of the absolute score gains below come from pacing, not from memory: see G16 for the pacing-off numbers.
- C0 harness: `experiments/steering_sensitivity.py` gained `--headings`, `--noise-both`, `--seed-start`, the vREST metric, maze tick metrics and the worst-scenario band.  
**Rejected:** a global (target-gated) living cost: visited cells turn negative, so traversed paths become repulsive and online maze learning breaks (online probe 131 vs 28 ticks; test_repeated_recall fails). Soft normalisation (`adv/(max|adv|+0.05)`) and a no-local-max veto (zero signals when all advantages are negative): neither did better than the bundle without them, and both break `test_replay_is_more_data_efficient_than_online_learning` (soft: replay 14 vs online 13; veto: replay probe times out at 200; it also drops the maze to 74 at gain 1.5).  
**Acceptance (steering_sensitivity, 8 seeds at noise 0.03 plus held-out seeds 9-16, and 8 headings / 5 maze headings at noise 0; gains 1.2-3.0):** worst-scenario fraction of own best 0.85-0.97 (seeds 1-8), 0.89-0.92 (held-out), 0.86-0.96 (noise 0); stock 0.67-0.70, 0.56-0.77 and 0.15-0.19. At the default gain (new 1.5 / stock 0.8, maze 1.5 in both), noise 0.03 / noise 0: beacon 24.6 / 23.8 (stock 10.8 / 8.0), foraging 50.8 / 45.1 (34.0 / 17.9), hazard_field 33.4 / 34.1 (18.6 / 13.4), memory_maze 142.1 / 146.8 recalls at recall rate 1.00 (143.5 / 146.4). vREST in the open scenarios is at most 0.08 at gains 0.8-3.0 (stock up to 0.96). Hazard field at gains 0 and 0.4 is >= 0.89 of its best (stock 0 items at noise 0.03). All of these are with pacing on; the G14 engine with pacing off scored about stock level (beacon 10.5, foraging 36.0, hazard 16.1 at gain 1.5, noise 0.03), with foraging vREST 0.20-0.24.  
**Honest limits:** the maze still needs gain >= ~1.0 (0.23-0.68 of best at 0.8; 0.23 is held-out seeds 9-16, 35.9 recalls where stock got 57.1): value turns must beat FORWARD's lead, which these changes do not address (G15 does). The maze is below stock at the band edges (noise 0.03: 121.1 vs 126.8 at gain 1.2, 121.2 vs 130.6 at 3.0). Maze vREST rises to ~0.17-0.18 at gain 3.0. Resampling the 8 seeds puts the band edges at 1.2 and 3.0 above 0.85 only 56-61% of the time. Outside the maze, memory changed the chosen action on only 2-7% of ticks (stock 59-63%): the open-scenario robustness was won by muting memory (cue gating, a sparse primary-only map), not by making it useful.  
**Tests:** `tests/engine/test_steering_robustness.py` (per-component, no-op cases, pacing hysteresis, interleaved engines, and bit-identical legacy digests of 6c0ea9d with every feature off in `tests/engine/steering_legacy_hashes.json`, which must never be re-recorded); `tests/experiments/test_steering_sensitivity.py` (harness, plus a check of the vREST counterfactual against the engine's own zero-value scores). `tests/experiments/test_foraging.py::test_blind_agent_forages_far_fewer` was restated: the blind agent used to "forage poorly" by camping on a self-made peak (resting on 87% of ticks); it now collects 2 of 5, so the test asserts the sighted agent clears the patch, the blind agent collects under half, and the sighted rate is >= 10x the blind rate.  
**Scope:** No determinism or regression baseline change; `tests/experiments/test_memory_navigation.py` is unedited and passes (replay probe 14 ticks vs online 22; stock 14 vs 28; G16 shows that the 8-tick margin was the online agent's value-induced REST). The determinism and regression protocols place no targets, so they never exercise the value map: "baselines unchanged" says nothing about steering. The Memory maze "rest off" demo still degrades (recall rate 0.71 / 0.75 vs 1.00 with rest).

## G15 — Split memory steering: lowers the maze's gain threshold (the default since G16)
**Date:** 2026-10-02  
**Status:** written when split was config-gated and off by default; G16 makes it the default. The numbers below are for split on the G14 engine, before G16's replay, pain-floor and wall-gating changes; G16 re-reports them.  
**Why:** After G14 the only gain dependence left was the maze's lower band edge (RC5): max-normalised value turns compete as separate TURN channels against FORWARD's ~0.7 lead, so the maze needs `value_gain` >= ~1.0-1.2 (memory_maze at 0.4/0.6/0.8/1.0: 18.8/38.1/65.9/117.6 recalls at noise 0.03, 57.8/69.2/106.4/139.2 at noise 0).  
**Change:** `basal_ganglia.value_steer = "split"` replaces the three value signals with `split_value_signals` (pure, in `brain/systems/basal_ganglia.py`): turn signals measured relative to ahead, `sign(d) * clip((|d|/s - 0.1)/0.2, 0, 1)` with `d = side - ahead` and `s = max|advantage|`; when both sides beat ahead only the better one turns (ties left); FORWARD's term is `max(0, ahead/s) - max(turns)` ("oppose_positive"); no common mode. As first committed the default stayed `"maxnorm"`; G16 flips it to `"split"`.  
**Why each part (measured; prototypes in raw value units, as first proposed):**
- Plain split (ahead 0, step turns) moves the noise-0.03 edge to 0.4 but collapses above it: 63 recalls and a 300-tick (timed-out) first hidden trial at every gain >= 0.8. The raw-unit dead zone (0.01/0.02) gives 101-132 with first-trial latency 30-66 ticks and is non-monotone. Cause: at the value peak (end of the demonstration, at the goal-disk edge) every direction is downhill and the side fans beat ahead by ~1-5% of the relief; a raw-unit threshold turns that into a full turn, so the agent zig-zags L/R straight off the map or orbits. Max-norm never did this because its turn must beat FORWARD's lead by a fraction of the relief, i.e. its dead zone is implicitly relative. Hence the dead zone in units of `s`.
- Exclusive turns: with both sides +1 the agent alternated L/R (each TURN moves 0.3 forward) and walked out of the map (seed 2: 4 recalls).
- FORWARD gives up what the turn gains, so a turn needs half the gain (band edge 0.8 -> 0.4). Keeping the positive part of ahead (`oppose_positive`) keeps hazard_field near G14 (32.6 vs 30.4 without it at gain 1.5), and it is what makes the replay test and the first-trial latency compatible: with `oppose` alone, dead zones <= 0.12 pass the replay test mostly orbit at the peak (first hidden trial 29-185 ticks), while larger ones fail it (15 vs 14); only (0.12, 0.2) did both, at 3 of 8 gains. With `oppose_positive`, (0.1, 0.2) does both and passes the replay test at gains 0.8-3.0.
- Positive-only common mode (`value_common_mode=0.1`) measured but not needed: with freeze habituation (G14 C1) it changes nothing at gains >= 0.4 except hazard_field at gains 0/0.4 (0.929/0.992 vs 0.901/0.964 of best); split has no negative common mode, so `max(signals) >= 0` always and value-induced REST is structurally impossible.
- Tried and dropped: an absolute floor on `s` (soft normalisation for weak maps; does not slow the one-demo online agent), holding turns at a local maximum (worse in most settings; maze down to 0.41 of best), dropping or down-weighting the 1.4 rad fan (moves the one-seed failures around).  
**Results** (`steering_sensitivity`, noise 0.03 seeds 1-8 / noise 0 8 headings, maze 5 / held-out seeds 9-16; G14 in brackets): memory_maze at gains 0.4/0.6/0.8/1.0: 126.0/153.9/147.6/147.6 (18.8/38.1/65.9/117.6); 136.8/143.6/145.8/158.8 (57.8/69.2/106.4/139.2); 149.9/131.4/148.6/148.6 (24.8/34.4/35.9/145.4). First hidden trial 15 / 10-11 ticks (13-14 / 10-12). Worst-scenario fraction >= 0.80 from 0.4 to 3.0 in all three blocks (G14: from 1.0); >= 0.85 from 0.6 / 0.4 / 0.4 (G14: 1.2 / 1.0 / 1.0); at 1.2-3.0: 0.920-0.924 / 0.929-0.944 / 0.870-0.905 (0.852-0.961 / 0.858-0.933 / 0.886-0.924). vREST 0.000 in every scenario including the maze (maze 0.17-0.18 at gain 3.0 in G14). At gain 1.5: beacon 24.6 / 23.4 / 24.2, foraging 48.8 / 48.9 / 46.9 (50.8 / 45.1 / 52.0), hazard_field 32.6 / 31.4 / 34.0 (33.4 / 34.1 / 33.9), maze 147.2 / 158.6 / 130.4 (142.1 / 146.8 / 149.6). Rest-off demo at 1.5: recall rate 0.70 / 0.69 vs 1.00 with rest.  
**Replay test:** `test_replay_is_more_data_efficient_than_online_learning` passes under split, but by 13 vs 14 ticks (max-norm: 14 vs 22). In that geometry the replayed gradient points along the agent's default heading, so the replay agent and the one-demonstration online agent take the same straight path and differ only at the goal-disk edge. Max-norm's 8-tick margin comes from an 8-tick value-induced REST of the online agent at its weak peak, and max-norm fails the same test at gains 0.4-1.2. Under split the test passes at gains 0.8-3.0 and, at noise 0.03, on 8/8 seeds at 0.8, 1.5 and 3.0 (max-norm 0/8 at 0.8). It is parameter-sensitive: dead zone 0.08-0.12 with ramp 0.15-0.3 passes at gain 1.5, but (0.12, 0.2) and dead zones >= 0.14 give 15 vs 14.  
**Costs if adopted:** memory becomes roughly neutral in the open scenarios (foraging -2.0 / +3.8 / -5.1 and hazard_field -0.8 / -2.7 / +0.1 at gain 1.5); one held-out seed (13) times out 3-4 hidden trials at gains 0.6-1.5 (fatigue-driven path-integration drift plus an orbit around the shifted peak), giving the 0.870 held-out minimum. Flipping the default would also need `tests/experiments/test_steering_sensitivity.py::test_is_value_rest_matches_the_engine_no_value_scores[beacon]` to run longer (its precondition that the value path fires within 1500 ticks fails: memory is silent in beacon until tick ~1500).  
**Tests:** `tests/engine/test_split_steering.py`. `ALL_OFF` in `tests/engine/test_steering_robustness.py` now pins `value_steer="maxnorm"` so the legacy digests do not depend on the default.  
**Impact:** `brain/systems/basal_ganglia.py` (`split_value_signals`), `core/engine.py` (`_value_signals`), `core/config.py` (`BasalGangliaConfig.value_steer`, `value_turn_*`, `value_ahead_mode`, `value_common_mode`).

## G16 — Split steering is the default; replay extinction, pacing and pain-floor fixes; wall gating; final acceptance
**Date:** 2026-10-02  
**Why:** G14 and G15 left review findings open: replayed dwell charges turned extinction into aversion, the pacing latch could become absorbing, console-level noise wrote pain into the map, no test guarded the behavioural outcome, the core engine (pacing off) was never measured, and the replay-test margin under split was 1 tick. Split steering (G15) gave the widest band at both noise levels with no value-induced REST, so it becomes the default.  
**Changes:**
- `BasalGangliaConfig.value_steer = "split"` (default). `"maxnorm"` stays available; the legacy all-off digests pin it and are bit-identical.
- Replay extinction (fixes G14 C2): the trajectory stores the reward actually received; `replay_transition` charges a transition only when it stays in one place-cell bin and that cell is still positive at replay time, the same rule as online. `consolidate(60)` on a 10-tick dwell trajectory now ends at ~0 instead of -0.2, and never goes below the one-backup online floor -lr*c = -0.004. In the pain-free scenarios over 3000 ticks, min V is -0.003 at worst and no cell is below -0.01 (it was -0.06 to -0.08, with 2-11 such cells). `record`, `replay_transition` and `consolidate` take the extinction cost explicitly. The engine passes `config.value_memory.dwell_extinction` and no longer overwrites the `ValueMemory` attribute each tick.
- Dwell definition: "dwelling" is a transition within one place-cell bin, so turns made in place are charged as well as REST. Charging only zero-thrust (REST) dwelling was measured under split (full grid, both noise levels). Every cell was within 1% except the maze at gain 0.4 (129.1 vs 125.1 at noise 0.03, 136.4 vs 136.8 at noise 0). That is not clearly better, so the bin rule stays.
- Pacing thresholds: `pace_low` and `pace_high` are now fractions of `astrocyte.atp_baseline`, which is bit-identical at baseline 1.0. With absolute thresholds and `atp_baseline` 0.85 the latch never released (REST on 3926 of 4000 ticks); now it releases.
- Map pain floor: only pain > max(0.05, `sensors.noise`) enters the value map. This is a sensory-reliability floor: pain noise is uniform in ±noise, so anything at or below that level may be noise alone. At console noise 0.1 the open field used to get noise pain in its map on 132 of 500 ticks.
- Wall gating (new; `wall_gate_gain=1.0`, 0 disables). Let c be the centre-ray wall closeness that wall avoidance already uses, and `w = max(0, 1 - gain*c)`. The gate scales FORWARD's positive value signal and the negative turn signals by w. Turns toward a better side are kept, so `max(signals) >= 0` still holds.
  - How it was found: while writing the guards, with pacing off, the remembered value lay beyond the wall (or path-integration drift had put it there). FORWARD's memory pull beat wall avoidance, and the agent pressed into the wall until microsleep. In foraging seeds 5-7 at noise 0.03 and gain 1.5 this took 500-745 ticks and the agent collected 13-21 items, against 34-36 at gain 0.
  - Rejected variants: gating FORWARD only (vREST 0.003-0.006); gating all three signals (maze at gain 0.4 falls to 110-119); discounting the ahead advantage before split (the maze's first hidden trial times out at noise 0.03).
- Console:
  - The decision panel shows the split steering commands ("Memory steer") and the wall gate.
  - The cue-gate help is corrected: the gates read raw vision rays, independent of vision drive.
  - New live parameter: "Wall gating of memory".  
**Acceptance:** measured with `experiments/steering_sensitivity.py` on the grid {0, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0}, in three runs:
- (a) `--noise-both`: seeds 1-8 at noise 0.03, plus seed 1 over 8 headings at noise 0 (maze: 5 headings);
- (b) held-out seeds 9-16 at noise 0.03;
- (c) as (a) with `--set basal_ganglia.pace_rest_bonus=0`, the core engine's energy policy.

The table gives the worst-scenario fraction: the minimum over scenarios of mean / own best.

| gain | 0 | 0.4 | 0.6 | 0.8 | 1.0 | 1.2 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|---|---|
| (a) noise 0.03, pacing on | 0.004 | 0.860 | 0.980 | 0.963 | 0.959 | 0.959 | 0.956 | 0.955 | 0.963 |
| (a) noise 0, pacing on | 0.001 | 0.864 | 0.902 | 0.944 | 0.936 | 0.936 | 0.936 | 0.940 | 0.929 |
| (b) held-out, pacing on | 0.003 | 0.885 | 0.943 | 0.915 | 0.872 | 0.876 | 0.872 | 0.905 | 0.905 |
| (c) noise 0.03, pacing off | 0.004 | 0.860 | 0.917 | 0.917 | 0.952 | 0.893 | 0.893 | 0.881 | 0.881 |
| (c) noise 0, pacing off | 0.001 | 0.864 | 0.902 | 0.975 | 0.921 | 0.952 | 0.951 | 0.897 | 0.889 |

The good band (worst >= 0.80, and also >= 0.85) is 0.4-3.0 in all five blocks. For comparison, G14 (max-norm, pacing on) had 1.0-3.0 at >= 0.80 and 1.2-3.0 at >= 0.85. Before wall gating, pacing off at noise 0.03 had 0.4-2.0 at >= 0.80 and only 0.6 at >= 0.85.  
**Bootstrap caveat:** the seeds (or headings) of each scenario were resampled 2000 times; the figures are P(worst >= 0.85).
- (a) at noise 0.03: 1.00 for gains 0.6-3.0, but only 0.60 at gain 0.4.
- (a) at noise 0: 0.61 at gain 0.4 and 0.84 at gain 0.6.
- (b) held-out: 0.72-0.73 at gains 1.0-1.5, because of one seed (see below).
- (c) pacing off: 0.56-0.92 at gains 1.2-3.0 at noise 0.03, and 0.71 at gain 3.0 at noise 0.

Cells near 0.85 are thin, and with 8 samples the band edges cannot be located more sharply than this.  
**Floors at the default gain 1.5:**

| scenario | (a) noise 0.03, pacing on | (a) noise 0, pacing on | (b) held-out, pacing on | (c) noise 0.03, pacing off | (c) noise 0, pacing off |
|---|---|---|---|---|---|
| beacon | 24.6 | 23.4 | 24.2 | 9.4 | 9.6 |
| foraging | 48.4 | 48.6 | 47.0 | 35.2 | 31.4 |
| hazard_field | 31.8 | 31.2 | 34.0 | 14.9 | 15.4 |
| memory_maze | 147.1 | 157.8 | 130.4 | 147.1 | 157.8 |

Pacing is off in the maze in every block, so its (c) numbers equal (a). Maze recall rate is 1.00 / 1.00 / 0.977 and median recall 10 / 9 / 10 ticks in (a) noise 0.03 / (a) noise 0 / (b). Stock (6c0ea9d at its defaults, noise 0.03) scored 10.75 / 34.0 / 18.6 / 143.5.
- Flatness (max/min mean over gains 0.4-3.0) is at most 1.07 with pacing on and at most 1.12 with pacing off.
- vREST is 0.000 in every cell of every block, maze included. G14 had maze vREST 0.17-0.18 at gain 3.0; stock reached 0.96.  
**What memory buys:** score at value_gain 1.5 minus score at 0, paired by seed or heading. Each line gives pacing on, (a) noise 0.03 / (a) noise 0 / (b), then pacing off, (c) noise 0.03 / (c) noise 0.
- memory_maze: everything. 0.2-0.6 recalls without memory, 130-158 with it.
- hazard_field: +2.8% / -1.2% / +8.8%; -7.0% / -2.4%. Only the held-out block is clearly positive (7 wins, 0 losses).
- foraging: -2.5% / +6.0% / -4.1%; -3.1% / -3.1%. Neutral within the paired spread (sd 2-6 items).
- beacon: -3.4% / -5.6% / -8.1%; -10.7% / -4.9%. Slightly negative in every block (0-1 wins). The beacon has always moved on from a remembered spot, so memory there is stale.

Most of the console scenarios' gains over stock come from fatigue pacing, not from memory. With pacing off at gain 1.5 the scores are 9.4 / 35.2 / 14.9, about stock level. In the open scenarios, split steering and wall gating buy one thing: memory no longer hurts much at any gain, with pacing on or off.  
**Memory maze at low gains** (recalls at gains 0.4 / 0.6 / 0.8 / 1.0, G14 in brackets):
- (a) noise 0.03: 132.4 / 153.9 / 148.1 / 147.6 (18.8 / 38.1 / 65.9 / 117.6). At gain 0.4 the recall rate is 1.00 and the median first hidden trial 14.5 ticks.
- (a) noise 0: 137.6 / 143.6 / 157.6 / 158.8 (57.8 / 69.2 / 106.4 / 139.2). First hidden trial 10-11 ticks.
- (b) held-out: 132.2 / 149.5 / 148.6 / 130.4 (24.8 / 34.4 / 35.9 / 145.4).

The held-out dip at gains 1.0-1.5 is one seed. Seed 13 gets 7-13 recalls, with 3-4 timed-out hidden trials: fatigue narrows the sensory gate, path integration drifts, and the agent orbits the shifted peak. The other seven seeds get 147-148. This seed sets the held-out floor (130.4) and the 0.872 cells.  
**Replay finding:**
- Under max-norm (G14), `test_replay_is_more_data_efficient_than_online_learning` passed by 14 vs 22 ticks. But 9 of the online probe's 22 ticks were REST, so the margin was the value-induced REST trap, not replay. Max-norm replay could also hurt: at goal (3, 7) replay took 76 ticks (34 of them REST) against 36 online.
- Under the final defaults the replay probe never rests. Over six goals (start heading 0, `memory_nav_config`), replay / online probe ticks are:
  - (6, 3): 13 / 14
  - (6, -3): 11 / 14
  - (4, 5): 30 / 36
  - (2, 6): 42 / 65
  - (7, 0): 9 / 9
  - (3, 7): 33 / 36
  - total: 138 / 174
- This is a single deterministic sample, and it is fragile. At value_gain 0.8, or with a split dead zone of 0.12, the replay probe to (6, -3) times out. At sensor noise 0.03 the off-axis demonstrations wander (104-123 ticks) and both arms time out on three goals.
- In the maze scenario (1500 ticks), replay on / off gives 147 / 91 recalls, with median recall 10 / 16 ticks. The first hidden trial is not faster with replay: 15 / 13 ticks.  
**Tests:**
- `tests/experiments/test_steering_guards.py` tests behaviour:
  - foraging and hazard_field at gains 1.5 and 3.0 score within 80% of gain 0, with pacing on and off;
  - vREST <= 0.15;
  - maze recall rate >= 0.9 at gains 0.8-3.0.
  
  5 of its 11 tests fail on stock-like steering (max-norm, no extinction), and wall_gate_gain=0 alone fails the pacing-off foraging case. The maze guard does not discriminate.
- `tests/experiments/test_replay_geometry.py` checks the six-goal replay result.
- `tests/engine/test_steering_robustness.py` has new unit tests for replay extinction, the explicit extinction argument, relative pacing, the noise pain floor and wall gating.  
**Scope:** Determinism and regression baselines are unchanged, because the value map stays flat there. The legacy all-off digests pin `value_steer="maxnorm"` and `wall_gate_gain=0` and are bit-identical. `test_is_value_rest_matches_the_engine_no_value_scores[beacon]` now runs 2000 ticks, because under split, memory is silent in beacon until about tick 1500.  
**Impact:** `core/config.py`, `core/engine.py`, `brain/systems/basal_ganglia.py` (`wall_gate_signals`), `brain/systems/value_memory.py`, `ui/sim_session.py`, `ui/static/js/brain.js`, `ui/scenarios.py`, `experiments/memory_navigation.py`, `experiments/steering_sensitivity.py`, README.
