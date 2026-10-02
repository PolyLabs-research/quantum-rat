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
- The Memory maze rests the agent between trials (40 ticks of resting physiology, no brain ticks) as real water-maze protocols do, and the rest can be toggled. Over 1500 ticks: 149/149 recalls with rest and replay (median 10 ticks), 87/87 with rest and no replay (median 17), and 7/11 without rest in either arm, because fatigue narrows the sensory gate and path integration drifts. *Since G18 the maze paces fatigue, so with rest off recall no longer fails (rate 1.00, 29 recalls); the failure needs fatigue pacing at 0 as well.*
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
- Positive-only common mode (`value_common_mode=0.1`) measured but not needed: with freeze habituation (G14 C1) it changes nothing at gains >= 0.4 except hazard_field at gains 0/0.4 (0.929/0.992 vs 0.901/0.964 of best); split has no negative common mode, so (with the default ahead mode) `max(signals) >= 0` and a value-map local maximum never lowers FORWARD. This is not a structural guarantee against value-induced REST: REST can still win because of value when FORWARD is already below REST for other reasons and the turn signals are negative (a pure-function counterexample exists at default config: narrowed gate, wall ahead, here a local maximum). Measured vREST is 0 at gains 0.4-3.0 in every block, and 0.0067 of ticks for one maze heading at gain 0.2.
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
  - How it was found: while writing the guards, with pacing off, the remembered value lay beyond the wall (or path-integration drift had put it there). FORWARD's memory pull beat wall avoidance, and the agent pressed into the wall until microsleep. In foraging seeds 5-7 at noise 0.03 and gain 1.5 this took 500-745 ticks and the agent collected 13-21 items, against 34-39 at gain 0 (a loss of 13-23 items per seed).
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

Pacing is off in the maze in every block, so its (c) numbers equal (a). *(Since G18 the maze paces at `pace_low` 0.6; see G20 for the re-measured blocks.)* Maze recall rate is 1.00 / 1.00 / 0.977 and median recall 10 / 9 / 10 ticks in (a) noise 0.03 / (a) noise 0 / (b). Stock (6c0ea9d at its defaults, noise 0.03) scored 10.75 / 34.0 / 18.6 / 143.5.
- Flatness (max/min mean over gains 0.4-3.0) is at most 1.07 with pacing on and at most 1.12 with pacing off.
- Mode strings are validated: an unknown `value_steer` or `value_ahead_mode` raises ValueError (a misspelt "Split" used to run max-norm silently).
- vREST is 0.000 in every cell of every block, maze included (an empirical result at gains 0.4-3.0, not a structural guarantee; see G15). G14 had maze vREST 0.17-0.18 at gain 3.0; stock reached 0.96.  
**What memory buys:** score at value_gain 1.5 minus score at 0, paired by seed or heading. Each line gives pacing on, (a) noise 0.03 / (a) noise 0 / (b), then pacing off, (c) noise 0.03 / (c) noise 0.
- memory_maze: everything. 0.2-0.6 recalls without memory, 130-158 with it.
- hazard_field: +2.8% / -1.2% / +8.8%; -7.0% / -2.4%. Only the held-out block is clearly positive (7 wins, 0 losses).
- foraging: -2.5% / +6.0% / -4.1%; -3.1% / -3.1%. Neutral within the paired spread (sd 2-6 items).
- beacon: -3.4% / -5.6% / -8.1%; -10.7% / -4.9%. Slightly negative in every block (0-1 wins). The beacon has always moved on from a remembered spot, so memory there is stale.

Most of the console scenarios' gains over stock come from fatigue pacing, not from memory. With pacing off at gain 1.5 (the core-engine energy policy) the scores at noise 0.03 are beacon 9.4 / foraging 35.2 / hazard_field 14.9 against stock (all new features off, gain 0.8) 10.75 / 34.0 / 18.6: beacon -13%, foraging +4%, hazard_field -20%. At noise 0 the pacing-off engine beats stock in all three (9.6 / 31.4 / 15.4 vs 8.0 / 17.9 / 13.4). With pacing off, gain 0 is the best gain in every open scenario except foraging at noise 0.03. In the open scenarios, split steering and wall gating buy one thing: memory no longer hurts much at any gain, with pacing on or off.  
**Memory maze at low gains** (recalls at gains 0.4 / 0.6 / 0.8 / 1.0, G14 in brackets):
- (a) noise 0.03: 132.4 / 153.9 / 148.1 / 147.6 (18.8 / 38.1 / 65.9 / 117.6). At gain 0.4 the recall rate is 1.00 and the median first hidden trial 14.5 ticks.
- (a) noise 0: 137.6 / 143.6 / 157.6 / 158.8 (57.8 / 69.2 / 106.4 / 139.2). First hidden trial 10-11 ticks.
- (b) held-out: 132.2 / 149.5 / 148.6 / 130.4 (24.8 / 34.4 / 35.9 / 145.4).

The held-out dips come from one seed failing non-monotonically in gain. Seed 13 collapses at gains 0.4 (8 recalls), 1.0, 1.2 and 1.5 (7-13 recalls, with 3-4 timed-out hidden trials: fatigue narrows the sensory gate, path integration drifts, and the agent orbits the shifted peak), but not at 0.6, 0.8, 2.0 or 3.0 (145-153). The other seven seeds get 147-150. This one chaotic seed sets both the held-out gain-0.4 cell (132.2) and the 1.0-1.5 cells (130.4, worst fraction 0.872). Bootstrap over seeds, P(worst fraction >= 0.85): (a) noise 0.03 1.00 at gains 0.6-3.0 but 0.60 at 0.4; (a) noise 0 0.61 / 0.84 at 0.4 / 0.6, 1.00 from 0.8; (b) 0.72-0.73 at 1.0-1.5; (c) noise 0.03 0.99 / 0.92 / 0.87 / 0.85 / 0.56 at 1.0 / 1.2 / 1.5 / 2.0 / 3.0. So the robust claim is the >= 0.80 band; individual 0.85 cells at the band edges pass on these seeds but not on every resample.  
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
- This is a single deterministic sample, and it is fragile. Every gain from 0.8 to 1.3 fails the same way: the replay probe to (6, -3) takes one different action at tick 3, passes about 0.3 outside the goal disk and times out (326 / 174). Gains 1.4-3.0 pass (138-147 / 174), so the default 1.5 sits about 0.1 above that edge. A split dead zone of 0.12 also fails it. At sensor noise 0.03 the off-axis demonstrations wander (104-123 ticks) and both arms time out on three goals.
- In the maze scenario (1500 ticks), replay on / off gives 147 / 91 recalls, with median recall 10 / 16 ticks. The first hidden trial is not faster with replay: 15 / 13 ticks.  
**Tests:**
- `tests/experiments/test_steering_guards.py` tests behaviour:
  - foraging and hazard_field at gains 1.5 and 3.0 score within 80% of gain 0, with pacing on and off;
  - vREST <= 0.15;
  - maze recall rate >= 0.9 at gains 0.8-3.0.
  
  - maze recalls at gains 0.4 and 0.6 >= 80% of those at 1.5 (summed over three noise-0 headings; measured 0.90 / 0.89).

  On stock-like steering (max-norm, no extinction) the four vREST cells, the pacing-off foraging score and both low-gain maze guards fail (stock-like 0.53 / 0.38; max-norm alone 0.25 / 0.65). wall_gate_gain=0 alone fails the pacing-off foraging case. The maze recall-rate guard does not discriminate on its own. Tightest margin at the defaults: foraging with pacing off at gain 3.0, 33 vs 39 items (0.846 against the 0.8 bound).
- `tests/experiments/test_replay_geometry.py` checks the six-goal replay result.
- `tests/engine/test_steering_robustness.py` has new unit tests for replay extinction, the explicit extinction argument, relative pacing, the noise pain floor and wall gating.  
**Scope:** Determinism and regression baselines are unchanged, because the value map stays flat there. The legacy all-off digests pin `value_steer="maxnorm"` and `wall_gate_gain=0` and are bit-identical. `test_is_value_rest_matches_the_engine_no_value_scores[beacon]` now runs 2000 ticks, because under split, memory is silent in beacon until about tick 1500.
**Known, pre-existing, not changed here:** microsleep replay passes the TRN observation-buffer index (0..replay_window-1) to `ValueMemory.replay_transition`, which indexes the trajectory deque from its oldest end. Sleep therefore replays transitions about 150-200 ticks old (every second entry, in forward order) rather than the recent path, and the replay-time extinction rule inherits that. Explicit consolidation (`consolidate`, used by the memory maze and the assay) is unaffected. Fixing it changes microsleep-replay behaviour in every long run, so it belongs in its own change. *Fixed in G17.*  
**Impact:** `core/config.py`, `core/engine.py`, `brain/systems/basal_ganglia.py` (`wall_gate_signals`), `brain/systems/value_memory.py`, `ui/sim_session.py`, `ui/static/js/brain.js`, `ui/scenarios.py`, `experiments/memory_navigation.py`, `experiments/steering_sensitivity.py`, README.

## G17 — Microsleep replay replays the recent path, in reverse, never across a reset
**Date:** 2026-10-02  
**Why:** The engine passed `TRNGate.replay_index`, a position in the TRN's observation buffer (0..`replay_window`-1), to `ValueMemory.replay_transition`. That method indexes the trajectory deque (maxlen 200) from its oldest end. So sleep replayed transitions ~150-200 ticks old, every second one, forward (the deque shifts by one per tick while the index also advances by one), and the replay-time extinction rule (G16) inherited this. `reset_episode` also left no boundary in the trajectory. G16 recorded this as a known, pre-existing problem.  
**Change** (`value_memory.replay_recent`, default True; False in the legacy `ALL_OFF`):
- At sleep onset `Engine._replay` snapshots `ValueMemory.recent_transitions(trn.replay_window)`. The k-th replay tick backs up transition k of the snapshot, most recent first, and cycles if sleep outlasts it. A sleep lasts `trn.duration` (25) ticks, so at the defaults at most 25 of the 50 snapshotted transitions are replayed and the cycling never happens. The deque moving during sleep does not change it.
- **Biology, corrected (G21).** The reverse order is borrowed from the *awake*, reward-associated reverse replay of Foster & Wilson 2006 and Diba & Buzsaki 2007. Replay during sleep (NREM) is mostly forward (Lee & Wilson 2002; Ji & Wilson 2007). This model's replay is neither: it is gated by fatigue (TRN microsleep), not time-compressed (one transition per tick), and it covers at most 25 transitions.
- **Corrected in G21:** the snapshot of a sleep in progress survived `begin_episode`, so replay continued over the previous episode after a teleport. `begin_episode` now ends the replay of that sleep.
- `ValueMemory` records episode boundaries in a `_linked` deque beside the trajectory. The (cell, reward) entries are unchanged, and the deque is aligned at the newest end so it survives `trajectory.clear()`. `transition`, `recent_transitions`, `replay_transition` and `consolidate` never link across a boundary. This part is unflagged: every existing `consolidate` caller (maze, assay) clears the trajectory before teleporting, so it is a no-op there. The legacy digests and the six-goal replay numbers are unchanged.
- `replay_transition` is split into `transition(index)` and `replay_backup(transition)`. Both replay rules go through `replay_backup`, which since G18 also writes the goal memory.
- `TRNGate.replay_index` and `TickData` are unchanged, and so are the determinism and regression baselines.
- The console highlights the cell replay actually backed up (`ctx.replay_cell`; "Replaying k of N steps back"). The old `vm.trajectory[replay_index]` lookup was the wrong cell and one tick stale.

**Effect** (re-measured on the merged branch with G18 and G19; G16's harness grid, the four G16 scenarios, against 235cfdc):
- **Console defaults: none.** With pacing on, beacon, foraging, hazard_field and hidden_food never microsleep, and since G18 the maze does not either. All open-scenario rows of G16 blocks (a) and (b) are byte-identical to 235cfdc. The maze and hidden_food rows are identical under `replay_recent` true and false (default headings, the full circle, both noise levels). Before G18 the maze differed under the two rules only in runs that collapse into fatigue (gains 0.2-0.4, held-out seed 13), where outcomes are chaotic.
- **Pacing off (the core-engine energy policy): small, mostly positive at noise 0.03, mixed at noise 0.** Worst fraction at gains 0.4-3.0 is 0.895-0.988 (235cfdc: 0.860-0.952) at noise 0.03 and 0.864-0.976 (0.864-0.975) at noise 0. Part of the noise-0.03 rise at gain 0.4 is G18's maze change (132.4 → 137.8 recalls), not replay. At the default gain 1.5, recent vs legacy:
  - beacon, noise 0.03: 10.4 vs 9.4 (7 seeds better, 0 worse);
  - hazard_field, noise 0: 14.0 vs 15.4 (1 better, 5 worse), so the noise-0 worst fraction at 1.5 falls from 0.951 to 0.889;
  - foraging: 36.0 vs 35.3 at noise 0.03 (2 better, 2 worse) and 32.0 vs 31.4 at noise 0 (3 better, 4 worse);
  - hidden_food (G19; re-measured after G21's regrow fix): 3.62 vs 4.62 at noise 0.03 and 3.12 vs 4.12 at noise 0 (small counts; 2 seeds better and 4 worse at each noise level).

  The >= 0.80 and >= 0.85 bands of the four G16 scenarios stay 0.4-3.0. The tightest guard margin (foraging, pacing off, gain 3.0) moves from 33/39 to 35/39.
- **Memory maze with rest off and fatigue pacing 0** (since G18 the only maze setting that still microsleeps): neutral. At gain 1.5 over 1500 ticks: 8.0 vs 9.0 recalls at noise 0 (rate 0.67 vs 0.75), and 8.5 vs 8.25 at noise 0.03 over seeds 1-4 (rate 0.68 vs 0.69).

**What replay now writes** (measured over 3000 ticks, seeds 1-4, noise 0.03, gain 1.5):
- **Open field** (no pacing; 51.5 sleeps and 1278 replay ticks per run). The replayed cell is a median 0 place-cell bins from the agent (legacy: 3 bins) and a median 13 steps back (legacy: 187 ticks old). The open field has no reward, so the value map stays exactly 0 under either rule. The console can show *where* replay is, but not value being written.
- **The place estimate froze before sleep; the body did not.** When ATP drops below 0.35 the TRN closes, and a closed gate freezes path integration (`spatial.step` with `sensory_gain` 0). So the last ~30-50 transitions before sleep stay in one place-cell bin, while the body keeps moving: a median 2.7 m (up to 5.9 m) while the estimate stayed in the sleep-onset cell (open field, seeds 1-4, noise 0.03, 206 sleeps; re-measured in G21). A median 98% (94-100%) of each 50-transition snapshot is same-cell transitions, covering 1-4 distinct cells. The freeze is a model artefact (the TRN gate scales the egomotion fed to path integration), not biology.
- **Recent replay writes *less* along a path than the stale rule did.** With pacing off (foraging, hazard_field, beacon, hidden_food), it changes the value of 0.17-0.67 distinct cells per sleep, against 0.58-2.45 under the legacy rule. It backs up 15-27 moving transitions per run, against 58-83. So it mostly re-applies TD and dwell extinction to the cell the agent sleeps in. Reverse replay could carry value back along a path only if place cells kept updating until sleep.
- **A candidate follow-up.** A scratch variant on the branch skipped unrewarded same-cell transitions, i.e. replayed the recent sequence of places. With pacing off it scored a little better: worst fraction 0.906-0.997 at noise 0.03, and 0.952 at gain 1.5 and noise 0. It was measured on one sample and not adopted. It belongs with keeping path integration live until sleep as a follow-up.

**Tests:**
- `tests/engine/test_replay_recent.py`: order and recency, a stable snapshot while the deque grows, cycling (with `replay_window` 4), no cross-boundary transitions under either rule, the default-world trace independent of the flag, the console replay cell, and (G21) a teleport during microsleep.
- `test_wall_gate_stops_memory_pinning_the_agent_against_a_wall` moved from seed 5 to seed 13 (since G21: seeds 13 and 15). Seed 5 no longer pins under recent replay (39 items without the gate). Over seeds 1-16, pinning without the gate dropped from 6 seeds to 2 (13: 12 items without the gate, 34 with it; 15: 14 and 28). Seed 13 pins under both rules.
- `ALL_OFF` pins `replay_recent=False`; the legacy digests are bit-identical.

**Harness pitfall:** `--set` parses values as JSON, so `value_memory.replay_recent=False` (capitalised) becomes a truthy string. Use lowercase `false`.  
**Impact:** `brain/systems/value_memory.py`, `core/config.py`, `core/engine.py`, `ui/sim_session.py`, `ui/static/js/brain.js`.

## G18 — Off-axis memory-maze starts: a replay-written goal vector and gate-safe pacing
**Date:** 2026-10-02  
**Why:** The console memory maze (goal (6, 3), start (0, 0)) recalled only from start headings within about 0.7 rad of the goal bearing. `steering_sensitivity --maze-headings full` (new; 16 headings over 2π) measured this at 235cfdc:
- at noise 0, 4 of 16 headings recall on at least 90% of hidden trials, at every gain from 0.4 to 3.0 (38-43 recalls, recall rate 0.31-0.35);
- at noise 0.03 (seeds 1-4, gain 1.5), 14 of 64 runs do (22%).

**Diagnosis** (measured on the branch; two of the three suspected causes were wrong or incomplete):
- **Fan width is not the cause.** Value sampling out to π, or averaging lookaheads of 1, 2 and 4 m, still gives 4/16. The multi-scale lookahead hurt heading 0 (63 vs 147 recalls).
- **The flat start region comes from the TD discount.** The demonstration does start at the start, but from a start facing away the visible trial is a search of 34-129 ticks instead of 6-9. Values fall by γ=0.9 per step. So after consolidation the largest advantage the agent can sample at the start is 4e-4 to 4e-9 on 11 of the 12 failing headings, below the 1e-3 at which the map gives no command.
- **Path integration drifts during the search.** ATP drops below 0.55, the TRN narrows the sensory gate, and the gate also scales the egomotion fed to path integration. On 7 of the 12 failing headings the internal frame had shifted 1.8-12 m by the time the agent touched the goal.
- **A failure then cascades.** A 300-tick timeout leaves the agent tired (start ATP 0.4-0.7, 100-175 microsleep ticks per trial), and recall collapses for the rest of the session.

**Change:**
- **`value_memory.goal_vector`** (off in the core engine):
  - Replaying a rewarded transition stores its arrival cell as the goal (`ValueMemory.goal_cell`, written in `replay_backup`). This covers both sleep consolidation and microsleep replay.
  - Where the map's largest sampled advantage is below `goal_vector_flat` (1e-3, the map's own no-steer threshold, now `Engine.VALUE_FLAT`), the agent turns toward the goal by path integration. The commands come from the pure function `basal_ganglia.goal_vector_signals`:
    - it turns when |bearing| exceeds 0.15, with FORWARD giving way;
    - it never pushes forward, so `max(signals) >= 0`;
    - it gives no command while the goal is inside the ~1 m circle a run of turns traces, because turning would orbit it.
  - A visit to the goal's place cell that finds no reward erases it. **Corrected in G21:** that rule erased goals that had not moved (contact on the leaving tick was ignored, and a pass through the part of the cell outside the contact circle counted as a miss). The goal is now erased after two unrewarded visits in a row (`goal_extinction_misses`), any contact resetting the count.
- **Maze pacing.** `MemoryMaze` turns the goal vector on, together with fatigue pacing at `pace_low` 0.6, just above the gate's narrowing threshold of 0.55. At integration this value became one shared constant, `ui.scenarios.GATE_SAFE_PACE_LOW`, because G19's hidden food uses it for the same reason.
- **Console.** It draws the goal memory and says when the vector is steering.

**Results.** Variant table at gain 1.5 (share of runs that recall, i.e. recall rate >= 0.9). The baseline and final rows were re-measured on the merged branch. The middle rows are the branch's own measurements, made under legacy microsleep replay.

| variant | noise 0 (16 headings) | noise 0.03 (64 runs) |
|---|---|---|
| baseline (235cfdc) | 25% (42.6 recalls) | 22% (38.3) |
| goal vector alone | 44% | 33% |
| pacing at 0.6 alone | 56% (median recall 133 ticks) | 58% |
| goal vector + pacing 0.4 | 50% | 33% |
| goal vector + pacing 0.6 (fix/three, one-miss extinction) | 100% (85.9 recalls, rate 1.00) | 97% (77.3 recalls, rate 0.97) |
| **+ two-miss extinction (G21, fix/three-final)** | **100%** (90.8 recalls, rate 1.00) | **98%** (80.2 recalls, rate 0.98) |

- **Across gains** (noise 0, gains 0.4 / 0.8 / 1.5 / 3.0; re-measured with G21's extinction rule): 76.8 / 88.9 / 90.8 / 90.2 recalls at mean rate 0.998-1.000, against 38.1-42.6 at rate 0.31-0.35 before. All 16 headings recall at every gain. Under the one-miss rule it was 70.1 / 85.1 / 85.9 / 90.2, with heading 5.50 failing at gain 0.8 (rate 0.80); those low counts were the extinction bugs.
- **The failing noise-0.03 run.** Seed 3, heading 3.53, never finds the goal on the visible trial (300-tick timeout). Seed 2, heading 3.93 (2 of 5 under the one-miss rule) now recalls 34 of 34.
- **Per heading** at gain 1.5 and noise 0, recalls range from 13 (heading 5.11) to 197 (0.39); the lowest rate is 0.97 (heading 2.75).
- **Default maze headings and the open scenarios.** All beacon, foraging and hazard_field rows are byte-identical to 235cfdc (pacing on). The maze changes at gain 0 (0.62 → 0 chance recalls) and at gain 0.4 at noise 0.03 (132.4 → 138.5); every other default-heading cell is identical.
- **Held-out seeds 9-16.**
  - Recall rate is >= 0.99 at every gain.
  - G16's seed-13 collapse at gains 1.0-1.5 is gone: cell means go from 130.4 to 145.0-146.5, and seed 13 itself gets 124-136 there.
  - The 0.6 and 0.8 cells drop by 6-8 recalls (143.9, 141.0), because pacing rests take time. Seed 13 gets 92-108 at gains 0.4-0.8.
- **Replay now matters off axis.** On the full circle at gain 1.5 and noise 0, replay on / off gives 90.8 / 32.4 recalls at rate 1.00 / 0.67 (G21), and only 7 of 16 headings recall without replay. At the default heading the comparison is unchanged: 147 / 91 recalls, median 10 / 16 ticks.
- **No interaction with G17's replay rule.** With pacing at 0.6 the maze never microsleeps at console defaults, and full-circle and default-heading rows are identical under `replay_recent` true and false.

**Rejected or not defaulted:**
- **Storing the goal online on contact** (`goal_vector_source="online"`). It does slightly better in the maze (92.2 recalls, 100% of runs). But in `memory_nav_config` it lets the one-demonstration online agent beat the replay agent (prototype: 108 vs 138 total probe ticks over six goals), which fails `test_replay_geometry`. Tying the goal to replay keeps replay's role.
- **Vector precedence** (`goal_vector_flat` huge). It is clearly better at recall: 126.6 vs 85.9 on the full circle, and 186 vs 147 at the default heading with noise 0.03. But the value map, including its pain memory, would then never steer while a goal is held.
- **Goal vector on in the core engine.** `test_memory_navigation` and `test_replay_geometry` pass, but the steering guards fail with pacing off at gain 1.5: foraging 28 vs 39 items, hazard_field 15 vs 20.
- **Pacing at the old `pace_low` 0.4.** It is below the gate threshold and does not stop the drift.

**Costs and limits:**
- **The rest-off demo changed.** With the inter-trial rest off, recall no longer fails: the rate is 1.00, though with 29-30 recalls instead of 147 (median 23-62 ticks, 0 microsleep ticks; seeds 1-4 at noise 0 and 0.03, re-measured in G21). The rest-off numbers in DEC-3 and G16 (rate 0.69-0.75) now also need fatigue pacing set to 0. That gives 8-9 recalls at rate 0.67-0.68, with 626-725 microsleep ticks. The console watch text says so.
- **Recalls vary by heading** (10-197 per heading at gain 1.5). Where a 30-50 tick demonstration leaves the map weak but not flat (e.g. heading 5.11), the agent retraces the meandering demonstration.
- **Search on the visible trial is not addressed** (seed 3, heading 3.53, above).
- **Gain 0.4.** The vector's turn scales with `value_gain` and barely beats FORWARD there. So the full-circle maze's worst fraction at 0.4 is 0.85 of its own best (0.78 under the one-miss rule), and the absolute score doubles (38.1 → 76.8).
- **Hard-coded TRN threshold.** `GATE_SAFE_PACE_LOW` relies on the threshold of 0.55 hard-coded in `TRNGate.trn_state`. The beacon, foraging and hazard_field scenarios still pace at 0.4, below that threshold, so their path integration can drift on long runs. This is not addressed.

**Tests:**
- `tests/engine/test_goal_vector.py`.
- `tests/experiments/test_off_axis_maze.py`: at 1000 ticks, at least 15 of 16 headings recall and the mean recall rate is >= 0.95 (since G21; measured 16 of 16 and 0.996, tightest heading 2.75 at 14 of 15). Removing the goal vector, lowering `pace_low` to 0.4 or turning pacing off fails both (measured 11 / 9 / 7 of 16 recalling, mean rate 0.80 / 0.64 / 0.57).
- Harness tests (`--maze-headings default|full|N`, row keys `train_ticks` and `timeouts`, summary key `recall_ok`) and console tests.
- `ALL_OFF` pins `goal_vector=False` and `pace_low=0.4`; the legacy digests are bit-identical.
- The steering-guard docstrings were re-measured on the merge. Low-gain maze recalls at gains 0.4 / 0.6, as a share of those at 1.5:
  - stock-like steering, gates off: 0.57 / 0.62 (0.53 / 0.56 under the one-miss rule);
  - stock-like steering, gates on: 0.51 / 0.86 (0.49 / 0.82);
  - max-norm alone: 0.59 / 0.92 (0.54 / 0.92).

  Each fails at least the gain-0.4 guard.

**Impact:** `core/config.py`, `core/engine.py`, `brain/systems/basal_ganglia.py`, `brain/systems/value_memory.py`, `ui/scenarios.py`, `ui/sim_session.py`, `ui/static/js/{arena,brain,live}.js`, `experiments/steering_sensitivity.py`.

## G19 — Hidden food: an open task where place memory pays off
**Date:** 2026-10-02  
**Why:** Under the G16 defaults, memory buys about nothing in foraging and hazard_field and slightly hurts in beacon. Those targets are visible (so the cue gate mutes memory) or they move (so the map is stale). Only the memory maze showed memory doing anything, and it resets the agent to the start every trial. We needed an open task where remembering a place clearly pays.  
**Change:** a new console scenario, `hidden_food` (`ui.scenarios.HiddenFood`). No engine change.
- Six food sites of radius 1.25 sit at fixed, asymmetric places about 2.5 m in from the walls.
- The food is kind "hidden": touching it gives the contact reward, but vision never reports it as food, so neither the vision drive nor the cue gate sees it.
- An eaten site regrows in place 150 ticks later. **Corrected in G21:** regrowth was checked before collection, so a site regrowing under the agent was counted as a find with no reward and no map write (3 of 52 finds). A regrown site is now collectable only after an engine step has seen it.
- The config is set by the scenario only: pacing with `pace_low` 0.6 (`GATE_SAFE_PACE_LOW`, shared with the maze since G18), and `generalization_radius` 2 (as in the maze).
- The scenario is registered in the console and in `experiments/steering_sensitivity.py` (3000 ticks). Its rows report score, `sites_found` and `blocks` (finds per 500-tick block). The harness default now runs five scenarios.
- The console labels hidden items "hidden food" and adds a "Forget the map" action.

**Why pace_low 0.6:** the TRN gate narrows to 0.4 once ATP falls below 0.55, and a narrowed gate under-counts turns and motion. Nothing in an open task resets the path-integration frame, so the errors accumulate.
- With the usual `pace_low` 0.4, after 3000 ticks the estimated position is 16 m (memory off) to 39 m (memory on) from the truth, and memory costs 41% (14.5 vs 24.4 finds, 0 wins of 8; re-measured in G21).
- With 0.6 the drift is at most 1.2 m, which comes from wall contact while turning.

**Result** (re-measured in G21 on `fix/three-final`, after the regrow fix; gain 1.5 against 0, 3000 ticks, paired):

| block | memory | no memory | ratio | wins / losses |
|---|---|---|---|---|
| seeds 1-8, noise 0.03 | 6.75 | 2.38 | x2.84 | 8 / 0 |
| held-out seeds 9-16, noise 0.03 | 12.12 | 4.25 | x2.85 | 8 / 0 |
| seed 1, 8 headings, noise 0 | 12.25 | 3.00 | x4.08 | 8 / 0 |
| pacing off, noise 0.03 | 3.62 | 1.38 | x2.64 | 7 / 0 |
| pacing off, noise 0 | 3.12 | 1.62 | x1.92 | 6 / 0 |

(On `fix/three`, before the regrow fix: x2.74 / x2.74 / x4.08 / x2.36 / x2.31.)

- **Every gain from 0.4 to 3.0 beats gain 0 in every block:** x2.4-3.4 at noise 0.03, x3.7-4.3 at noise 0, x2.8-3.1 on held-out seeds, and x1.8-3.0 with pacing off.
- **Learning curve**, as per-block ratios (finds per 500-tick block, memory / memory off, seeds 1-8, noise 0.03): 0.25/0.12, 0.38/0.12, 0.75/0.38, 1.62/0.62, 1.75/0.62, 2.00/0.50, i.e. x2.0, 3.0, 2.0, 2.6, 2.8, 4.0. Memory-off finds change over time too (here they rise from 0.12 to 0.5-0.62 per block; at noise 0 they fall from 1.0 to 0.25-0.5), so this is not a pure learning curve.
- **No interaction with G17 at console defaults.** Microsleep is 0 with pacing on, so G17's replay rule changes no hidden_food row. With pacing off it changes them a little (3.62 vs 4.62 under the legacy rule at noise 0.03, 3.12 vs 4.12 at noise 0).

**Its gain profile is not flat**, and this is what changes the harness band (see G20, G21).
- Per-seed finds at gains 0.4-3.0 range from 1 to 22 (pacing on).
- The best gain differs by block: 1.0 (8.1 finds) at noise 0.03 on seeds 1-8, 0.4 or 1.0 (12.9) at noise 0. On held-out seeds it is nearly flat (11.8-13.4 at gains 0.4-3.0).
- **Corrected in G21:** before the regrow fix, held-out gains 0.4-0.8 gave 12.6-13.8 and 1.0-3.0 gave 10.0-11.6, and this entry called that preference for lower gains real. The fix changed 43 of 72 held-out rows and the preference vanished, so it was run-to-run variation.
- With pacing off, the counts (1-11 finds per run) are too small to locate a best gain.

**What the benefit is, and its limits** (corrected in G21, which has the controls):
- **It is memory-driven area-restricted search near recent finds, not accurate site memory and not route planning.**
  - A map read rotated 22° (every phantom peak >= 2.8 m from a real site) keeps most of the benefit (x2.74 / x1.91 / x2.67).
  - A map read at 2x scale gives none (x1.00).
  - Wiping the map every 150 or 500 ticks leaves x1.24-2.17.
  - With every site jumping to a random place in the food band every 150 ticks, memory still gives x1.08-1.47.

  So it needs a real map but not precise sites, it tolerates ~3 m of map error, and part of it survives without fixed sites.
- **Memory only pulls nearby.** Positive value lies within a few metres of a site (90th percentile 2.6-4.3 m per run), so memory only pulls an agent that passes nearby. The memory agent then circles a known site and makes about 70% of its finds at one site; it does not tour the six.
- **Memory costs when exploration alone already finds the food.** So this is not evidence that memory makes the agent a better forager in general:
  - with the sites on the wall loop (2 m inset): x0.55, 0 wins of 8;
  - an interior explorer (`forward_bias` 0.5) finds 37.2 without memory against 19.1 with it;
  - the tired agent at `pace_low` 0.4 finds 24.4 without memory, more than the paced memory agent here (6.75).
- **Sensitivities** (gains 0 vs 1.5, seeds 1-8, noise 0.03; re-measured in G21): REGROW 75 gives x5.16, REGROW 300 x2.21 (6 wins, 2 ties), RADIUS 1.0 x2.81, and `generalization_radius` 0 x1.58.
- **Rays still hit hidden objects** and report kind "hidden" at their distance. The policy ignores the kind; the maze already relies on this.

**Tests:** `tests/experiments/test_hidden_food.py` (about 8 s).
- Memory beats no memory over headings 0, π/2, π and 3π/2 at noise 0: 47 vs 12 finds (45 vs 12 before the regrow fix), against a bound of x2 and 3 of 4 pairs.
- Since G21, a reshuffled-sites control replaces the frozen-map test, which could not fail (a learning rate of 0 gives zero value signals). With sites re-drawn every 150 ticks the same bound fails (37 vs 42), and the fixed-site benefit is 4.5x the reshuffled one (bound 1.5x).
- Two tests cover the hidden/regrow mechanics, including a site regrowing under the agent.

**Impact:** `ui/scenarios.py`, `experiments/steering_sensitivity.py`, `ui/static/js/{arena,live,replay}.js`, `tests/experiments/test_hidden_food.py`.

## G20 — Joint acceptance of G17-G19
**Date:** 2026-10-02  
Measured on the merged branch (`fix/three`) against 235cfdc, with the G16 protocol. **G21 re-ran all of it on `fix/three-final`. The four-scenario tables below are unchanged except held-out gain 0.4 (0.946). The five-scenario table, the hidden_food floors and the vREST line are replaced with the re-measured values.** The protocol is `steering_sensitivity` on gains {0, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0}, in three runs:
- (a) `--noise-both --seeds 8`;
- (b) `--seed-start 9 --seeds 8 --noise 0.03`;
- (c) as (a) with `--set basal_ganglia.pace_rest_bonus=0`.

Re-running 235cfdc with the same harness reproduces the G16 tables exactly.

**Worst-scenario fraction for the four G16 scenarios** (beacon, foraging, hazard_field, memory_maze; directly comparable with G16):

| gain | 0.4 | 0.6 | 0.8 | 1.0 | 1.2 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|---|
| (a) noise 0.03 | 0.900 | 0.980 | 0.963 | 0.959 | 0.959 | 0.956 | 0.955 | 0.963 |
| (a) noise 0 | 0.864 | 0.902 | 0.944 | 0.936 | 0.936 | 0.936 | 0.940 | 0.929 |
| (b) held-out | 0.948 | 0.943 | 0.915 | 0.919 | 0.924 | 0.919 | 0.905 | 0.905 |
| (c) noise 0.03, pacing off | 0.895 | 0.988 | 0.963 | 0.953 | 0.959 | 0.938 | 0.938 | 0.899 |
| (c) noise 0, pacing off | 0.864 | 0.902 | 0.976 | 0.929 | 0.921 | 0.889 | 0.937 | 0.913 |

The good band (>= 0.80 and >= 0.85) is 0.4-3.0 in all five blocks, as in G16. Changes from G16:
- (a) at noise 0.03, gain 0.4: 0.860 → 0.900 (G18's maze);
- (b) up at every gain from 0.4 to 1.5, because held-out seed 13 no longer collapses (G18);
- (c) at noise 0.03: up at every gain (G17's beacon gain, G18's maze at 0.4);
- (c) at noise 0: down at gain 1.5 (0.951 → 0.889, G17's hazard_field) and up at 2.0-3.0.

**With hidden_food included** (all five scenarios, the harness default since G19; re-measured in G21 after the regrow fix):

| gain | 0.4 | 0.6 | 0.8 | 1.0 | 1.2 | 1.5 | 2.0 | 3.0 | band >= 0.80 | band >= 0.85 |
|---|---|---|---|---|---|---|---|---|---|---|
| (a) noise 0.03 | 0.800 | 0.862 | 0.908 | 0.959 | 0.815 | 0.831 | 0.692 | 0.754 | 0.4-1.5 | 0.6-1.0 |
| (a) noise 0 | 0.864 | 0.902 | 0.854 | 0.936 | 0.874 | 0.936 | 0.893 | 0.893 | 0.4-3.0 | 0.4-3.0 |
| (b) held-out | 0.946 | 0.943 | 0.915 | 0.919 | 0.879 | 0.907 | 0.897 | 0.905 | 0.4-3.0 | 0.4-3.0 |
| (c) noise 0.03, pacing off | 0.818 | 0.988 | 0.939 | 0.848 | 0.758 | 0.879 | 0.938 | 0.899 | 0.4-1.0 | 1.5-3.0 |
| (c) noise 0, pacing off | 0.864 | 0.818 | 0.970 | 0.788 | 0.921 | 0.758 | 0.727 | 0.913 | 0.4-0.8 | 0.8 |

**Reporting both bands.** Both are reported, because the harness default includes hidden_food and the five-scenario band is narrower than G16's four-scenario band. The four-scenario band (continuity with G16) is 0.4-3.0 in every block. The five-scenario band is limited by hidden_food's own gain profile; hidden_food is not excluded to make a number look better.
- **Worst fraction at the default gain.** Next to each five-scenario band, the worst fraction at gain 1.5 is 0.831 / 0.936 / 0.907 / 0.879 / 0.758 in the five blocks.
- **hidden_food sets the narrower band.** Wherever the five-scenario figure is below the four-scenario one, hidden_food is the limiting scenario.
- **It is not a regression of the other scenarios.** Memory beats memory-off at every gain >= 0.4 in every block, but hidden_food's level varies between gains: up to ~30% at noise 0.03 with pacing on (5.6 vs 8.1 finds), and 24-27% with pacing off, where it scores 1-11 finds per run.
- **Corrected in G21.** This entry first quoted a held-out five-scenario band of 0.4-0.8, from a held-out preference of hidden_food for low gains. After the regrow fix the held-out band is 0.4-3.0 and that preference is gone (see G19).
- **G16's claim does not hold for hidden_food.** "Every scenario within 20% of its own best at 0.4-3.0" holds for the four G16 scenarios only. It fails for hidden_food at noise 0.03 (gains 2.0-3.0) and with pacing off.

**Floors at the default gain 1.5** (G16 values in brackets where they differ; hidden_food re-measured in G21):

| scenario | (a) noise 0.03 | (a) noise 0 | (b) held-out | (c) noise 0.03 | (c) noise 0 |
|---|---|---|---|---|---|
| beacon | 24.6 | 23.4 | 24.2 | 10.4 (9.4) | 9.9 (9.6) |
| foraging | 48.4 | 48.6 | 47.0 | 36.0 (35.2) | 32.0 (31.4) |
| hazard_field | 31.8 | 31.2 | 34.0 | 15.1 (14.9) | 14.0 (15.4) |
| memory_maze | 147.1 | 157.8 | 145.8 (130.4) | 147.1 | 157.8 |
| hidden_food | 6.75 | 12.25 | 12.12 | 3.62 | 3.12 |

vREST is 0.000 in every cell of every block, except hidden_food runs with pacing off at noise 0: three runs (each <= 0.003 of ticks) on `fix/three`, and four (gains 0.4, 1.5, 1.5 and 2.0, each <= 0.0033) after G21. The maze recall rate is >= 0.99 at gains 0.4-3.0 in every block.

**Interactions between the three changes (measured):**
- **G17 x G18: none at console defaults.**
  - With pacing at 0.6 the maze never microsleeps, so the replay rule changes no maze row (default headings and full circle, both noise levels).
  - The goal memory is written by `replay_backup`, which both replay rules share. In the maze it is the 60-pass sleep consolidation that writes it.
  - Only the rest-off, pacing-0 demo still microsleeps, and there the replay rule is neutral (8-9 recalls either way).
- **G17 x G19: none at console defaults.** With pacing on, hidden_food never microsleeps, and its rows are identical under both rules.
  - With pacing off, recent replay gives fewer hidden-food finds: 3.62 vs 4.62 at noise 0.03 and 3.12 vs 4.12 at noise 0 (re-measured in G21; 2 seeds better and 4 worse at each noise level).
  - G19 hoped a replay fix would help hidden food; it does not, because recent replay mostly backs up the cell the agent sleeps in (G17).
- **G18 x G19:** they share `GATE_SAFE_PACE_LOW`. The goal vector is off in hidden_food, as in every scenario but the maze; turning it on globally fails the pacing-off steering guards (G18).
- **Effect on the band:** G18 changes it only through the maze (gain 0.4 at noise 0.03, and the held-out block), and G17 only with pacing off. G19 changes the five-scenario band as shown above.

**Guards on the merge:** all steering guards pass. The tightest is foraging with pacing off at gain 3.0, 35 vs 39. The regression checks behave as documented in `test_steering_guards.py`:
- stock-like steering fails 6 of 13 guards with the gates on, and 9 of 13 with them off;
- `wall_gate_gain=0` alone fails the pacing-off foraging guard (29 vs 39);
- `dwell_extinction=0` alone passes.

**Scope:**
- `python -m pytest -q` passes (228 tests; 241 after G21).
- The determinism and regression baselines and `tests/experiments/test_memory_navigation.py` are unchanged against 235cfdc.
- The legacy all-off digests are bit-identical. `ALL_OFF` now also pins `replay_recent=False`, `goal_vector=False` and `pace_low=0.4`.
- The console starts and lists `hidden_food` in `/api/meta`, and a `SimSession` of each of the six scenarios steps 300 ticks and serialises its frame.

**Integration changes:**
- The merge conflicts were additive: config fields, EngineContext fields, ALL_OFF entries and guard docstrings.
- `MAZE_PACE_LOW` and `HiddenFood.PACE_LOW` now alias one constant, `GATE_SAFE_PACE_LOW`, with the same value.
- G18 supersedes the rest-off figures in DEC-3 and G16, and G16's statement that pacing is off in the maze.

## G21 — Review fixes for G17-G20: goal extinction, phantom hidden-food finds, replay across resets, discriminating tests
**Date:** 2026-10-02  
**Why:** A correctness review and a science review of `fix/three` (G17-G20) reproduced three bugs, found tests that passed by construction or on a knife edge, and found claims that the controls do not support. Everything below is measured on `fix/three-final`. The scripts and data are in the session scratchpad (`fix3/final-round/`).

### A. Goal-vector extinction (G18)
The goal memory is the place cell the estimate was in at first contact, so it straddles the 1.5 m contact circle. Depending on the start heading, 0-88% of the 0.5 m cell lies outside the circle. Two reproduced bugs erased a goal that had never moved:
- **Contact from the next cell was ignored.** Contact reached from the neighbouring cell, on the tick the agent leaves the goal cell, did not count. Maze heading 1.96, seed 1, noise 0, gain 1.5: 10 recalls. With the leaving tick counted: 89 of 89.
- **One pass outside the circle erased the goal.** A single pass through the part of the cell outside the contact circle, without contact, was enough. Seed 2, heading 3.93, noise 0.03: 2 of 5 hidden trials recalled. With extinction off: 34 of 34.

**New rule** (`value_memory.goal_extinction_misses`, default 2):
- The goal is erased after that many visits in a row to its place cell that end without target contact.
- Contact on the leaving tick counts for the visit, and any target contact resets the count.
- The count persists across episodes, like the goal, and restarts when a new goal is written.
- 0 disables extinction.

The rationale is the same as for extinction in animals: it needs repeated non-reinforced trials, and one miss is weak evidence when the remembered place is only accurate to a cell.

**Candidates measured** (scratch monkeypatches):
- *Full circle:* 16 headings at noise 0 with gains 0.4 / 0.8 / 1.5 / 3.0, plus seeds 1-4 at noise 0.03 and gain 1.5; 1500 ticks.
- *Moved goal:* train at (6, 3); after three hidden trials move the goal to (-4, 6). 4500 ticks; 16 headings at noise 0 and seeds 1-2 at noise 0.03.
- *Homing:* the share of trials 7-14 in which the agent reaches the old place within 60 ticks.

| rule | runs recalling, noise 0 (per gain) | noise 0.03 | moved goal erased (median ticks after the move, noise 0 / 0.03) | homing, noise 0 / 0.03 |
|---|---|---|---|---|
| one miss (fix/three) | 16 / 15 / 16 / 16 | 62/64 (77.3 recalls) | 56 / 58 | 0.25 / 0.18 |
| one miss + leaving-tick contact | 16 / 15 / 16 / 16 | 62/64 (78.5) | 56 / 59 | 0.25 / 0.18 |
| two misses, contact in the visit resets | 16 / 16 / 16 / 16 | 62/64 (79.7) | 157 / 176 | 0.27 / 0.18 |
| **two misses, any contact resets (adopted)** | **16 / 16 / 16 / 16** | **63/64 (80.2)** | **157 / 187** | **0.27 / 0.18** |
| three misses, any contact resets | 16 / 16 / 16 / 16 | 63/64 (80.2) | 720 / 759 (2 of 32 noisy runs never) | 0.27 / 0.24 |
| radius 0.25 m around the cell centre, one miss | 16 / 15 / 16 / 16 | 62/64 (78.5) | 68 (pooled, 3000 ticks) | — |
| radius 0.15 m, one miss | 16 / 16 / 16 / 16 | 62/64 (79.7) | 154 (pooled, 3000 ticks) | — |
| no extinction | 16 / 16 / 16 / 16 | 63/64 (80.2) | never | 0.46 / 0.36 |

What the measurements show:
- **The adopted rule keeps a goal that is still there.** It gives exactly the rows of extinction off on all 128 full-circle runs.
- **It still forgets a moved goal.** The goal is erased in all 48 moved-goal runs (median 157-187 ticks after the move, max 3950).
- **The agent then finds the new goal more often.** Mean trials per run reaching the new goal: 34.9 vs 16.3 with extinction off at noise 0, and 51.5 vs 25.1 at noise 0.03.
- **A contact radius around the cell centre is not principled and was no better.** The centre itself can lie outside the contact circle.

**Cost.** One held-out maze run does worse: seed 13 at gain 0.4, noise 0.03, a run that tires and drifts. It gets 78 recalls instead of 100 (rate 0.99 both), because a single miss used to erase its drifted goal. The held-out gain-0.4 cell drops from 143.8 to 141.0.

**Tests:**
- Unit tests of the rule in `tests/engine/test_goal_vector.py`:
  - contact on the leaving tick counts;
  - one miss keeps the goal and two erase it;
  - any contact resets the count;
  - the count survives a teleport and restarts for a new goal;
  - 0 disables extinction.
- `tests/experiments/test_goal_extinction.py`:
  - the two reproduced runs, now 89/89 and 34/34. The second gives 2/5 with a single miss, so the test discriminates;
  - a moved-goal test at the five headings facing away from the goal (π to 3π/2), where the goal vector does the homing. The goal is erased 72-421 ticks after the move. 0 of 60 later trials home on the old place, against 30 of 60 with extinction off (bound: at most 6).

### B. Hidden food: phantom finds
`HiddenFood.on_tick` checked regrowth before collection, so a site that regrew under the agent was counted as a find in the same call. That find came with no contact reward and no map write (3 of 52 finds at gain 1.5, seeds 1-8, noise 0.03).
- **The fix.** A regrown site can be collected from the next `on_tick` on, after an engine step has seen it as food. Every find now falls on a tick with engine contact, in every run of the sweeps and controls below.
- **Every hidden-food number is re-measured.** Runs are chaotic, so the fix changes 43-54 hidden-food rows per sweep.

| block (gain 1.5 vs 0, 3000 ticks) | memory | no memory | ratio | wins / losses |
|---|---|---|---|---|
| seeds 1-8, noise 0.03 | 6.75 | 2.38 | x2.84 | 8 / 0 |
| held-out seeds 9-16, noise 0.03 | 12.12 | 4.25 | x2.85 | 8 / 0 |
| seed 1, 8 headings, noise 0 | 12.25 | 3.00 | x4.08 | 8 / 0 |
| pacing off, noise 0.03 | 3.62 | 1.38 | x2.64 | 7 / 0 |
| pacing off, noise 0 | 3.12 | 1.62 | x1.92 | 6 / 0 |

Every gain from 0.4 to 3.0 beats gain 0 in every block:

| block | ratio over gains 0.4-3.0 |
|---|---|
| seeds 1-8, noise 0.03 | x2.4-3.4 |
| seed 1, 8 headings, noise 0 | x3.7-4.3 |
| held-out seeds 9-16 | x2.8-3.1 |
| pacing off, noise 0.03 | x2.3-3.0 |
| pacing off, noise 0 | x1.8-2.5 |

**What the benefit is.** These are the science review's controls, re-run after B. Site moves happen before the engine step, so no control has phantom finds. Each cell gives gain 1.5 against gain 0 for seeds 1-8 / held-out seeds 9-16 at noise 0.03 / 8 headings at noise 0:

| control | ratio | memory finds |
|---|---|---|
| the scenario (fixed sites) | x2.84 / x2.85 / x4.08 | 6.75 / 12.12 / 12.25 |
| steering reads the map rotated 22° (every phantom peak >= 2.8 m from a real site) | x2.74 / x1.91 / x2.67 | 6.50 / 8.12 / 8.00 |
| every site jumps to a random place in the food band (2-3 m from the walls) every 150 ticks | x1.08 / x1.47 / x1.25 | 9.75 / 13.75 / 12.00 |
| steering reads the map at 2x scale (phantom peaks off the band) | x1.00 / x1.00 / x1.00 | identical to memory off |
| the map is wiped every 150 ticks | x1.47 / x1.24 / x1.83 | 3.50 / 5.25 / 5.50 |
| the map is wiped every 500 ticks | x1.53 / x1.32 / x2.17 | 3.62 / 5.62 / 6.50 |

So hidden food is **not accurate site memory**. It is memory-driven area-restricted search near recent finds:
- it needs a real map: the 2x-scale map gives nothing;
- it does not need precise sites: a map about 3 m off keeps most of the benefit;
- part of the benefit survives without fixed sites at all.

With reshuffled sites, memory-off finds rise to 9.0-9.6, because sites land on the agent's loop. Absolute finds are therefore not comparable across controls; the ratios are.

**Learning curve.** Finds per 500-tick block, seeds 1-8, noise 0.03:

| block | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| memory | 0.25 | 0.38 | 0.75 | 1.62 | 1.75 | 2.00 |
| memory off | 0.12 | 0.12 | 0.38 | 0.62 | 0.62 | 0.50 |
| ratio | x2.0 | x3.0 | x2.0 | x2.6 | x2.8 | x4.0 |

- **Memory-off finds change over time too.** They rise from 0.12 to 0.5-0.62 per block here, fall from 1.0 to 0.25-0.5 at noise 0, and fall from 1.38 to 0.38-0.75 on held-out seeds. So the curve is not a pure learning effect.
- **First half against second half:** x2.2 → x3.1 (seeds 1-8), x2.1 → x3.9 (held-out), x3.0 → x5.9 (noise 0).

**Sensitivities, re-measured** (gains 0 vs 1.5, seeds 1-8, noise 0.03):

| change | memory vs no memory | ratio |
|---|---|---|
| `pace_low` 0.4 | 14.5 vs 24.4 (0 wins) | x0.59 |
| sites on the wall loop (2 m inset) | 0 wins of 8 | x0.55 |
| `forward_bias` 0.5 | 19.1 vs 37.2 | x0.51 |
| `generalization_radius` 0 | | x1.58 |
| REGROW 75 | | x5.16 |
| REGROW 300 | | x2.21 |
| RADIUS 1.0 | | x2.81 |

- At `pace_low` 0.4 the gate is narrowed on 33-36% of ticks, and the final drift is 39 m with memory and 16 m without.
- Favourite-site share of memory finds: 0.70 (0.56 on held-out seeds, 0.68 at noise 0).
- Positive value lies within 2.6-4.3 m of a site (90th percentile per run).

### C. Replay plan across resets (G17)
**The bug.** The plan snapshotted at sleep onset survived `begin_episode()` and `run(reset=True)`. After a teleport mid-sleep, replay kept backing up the previous episode. This happened in the maze with rest and fatigue pacing off, where trials time out during sleep.

**The fix.** `begin_episode` now empties the plan and resets the step. The agent sleeps on but replays nothing more, and the next sleep takes a fresh snapshot.

**Effect:**
- In that demo, over seeds 1-8 at noise 0 and 0.03, there are 38 mid-sleep teleports and 0 replay ticks on an old snapshot.
- No sweep row changes. The only scored setting that microsleeps across a reset is that demo, and its recalls are unchanged: 8.0 at noise 0, 8.5 at noise 0.03.

**Test:** `test_a_teleport_during_microsleep_ends_the_replay_of_the_previous_episode` (open field, with and without clearing the trajectory). It fails without the fix.

### D. Tests that discriminate
- **`test_hidden_food.py`.** The frozen-map test could not fail: a learning rate of 0 means zero value signals. It is replaced by the reshuffle control, on the guard's own runs (seed 1, noise 0, four headings):
  - fixed sites: 47 vs 12 finds (x3.92);
  - reshuffled sites: 37 vs 42 (x0.88, 1 of 4 pairs won), so the main guard fails;
  - the fixed-site benefit is 4.5x the reshuffled one (bound 1.5x; 1.9-3.3x over the wider blocks).

  A new regrow-under-the-agent test fails on the old order.
- **`test_off_axis_maze.py`.** After A, heading 2.75 is still 14 of 15 at 1000 ticks (0.93 against 0.9). The miss is a timed-out trial, not extinction: one miss, two misses or none give the same rows.
  - The guard is now: at least 15 of 16 headings recall, and the mean recall rate is >= 0.95.
  - Measured: 16 of 16, mean 0.996 (936 of 937 trials).
  - The ablations fail both criteria: 11 / 9 / 7 of 16 headings, mean 0.80 / 0.64 / 0.57, without the goal vector / with `pace_low` 0.4 / with no pacing.
  - At noise 0.03 (not in the test), seeds 1-4 give 16, 16, 15 and 16 of 16, mean 0.94-1.00.
- **`test_steering_robustness.py`.** The wall-gate test runs seeds 13 and 15, the two of seeds 1-16 that pin without the gate (12 → 34 and 14 → 28 items). The other 14 seeds collect 29-39 items either way. Bound: pinned <= 20, and gated >= 25 and >= 1.5x pinned.
- **`test_steering_guards.py`.** With A, the regressed configurations' low-gain maze ratios change; the fail counts do not:

| configuration | ratio at gains 0.4 / 0.6 (one-miss rule before) |
|---|---|
| stock-like, gates off | 0.57 / 0.62 (0.53 / 0.56) |
| stock-like, gates on | 0.51 / 0.86 (0.49 / 0.82) |
| max-norm alone | 0.59 / 0.92 (0.54 / 0.92) |

  - Stock-like steering still fails 6 of 13 guards with the gates on and 9 of 13 with them off.
  - `wall_gate_gain=0` alone still fails the pacing-off foraging guard (29 vs 39).
  - `dwell_extinction=0` alone still passes.

### E. Acceptance: the G20 protocol re-run on this branch
**Four G16 scenarios.** The worst-fraction tables are identical to G20's, except held-out gain 0.4 (0.948 → 0.946, the seed-13 run above). The four-scenario band is 0.4-3.0 at >= 0.80 and at >= 0.85 in all five blocks.

**Five scenarios** (with hidden_food, the harness default):

| gain | 0.4 | 0.6 | 0.8 | 1.0 | 1.2 | 1.5 | 2.0 | 3.0 | band >= 0.80 | band >= 0.85 |
|---|---|---|---|---|---|---|---|---|---|---|
| (a) noise 0.03 | 0.800 | 0.862 | 0.908 | 0.959 | 0.815 | 0.831 | 0.692 | 0.754 | 0.4-1.5 | 0.6-1.0 |
| (a) noise 0 | 0.864 | 0.902 | 0.854 | 0.936 | 0.874 | 0.936 | 0.893 | 0.893 | 0.4-3.0 | 0.4-3.0 |
| (b) held-out | 0.946 | 0.943 | 0.915 | 0.919 | 0.879 | 0.907 | 0.897 | 0.905 | 0.4-3.0 | 0.4-3.0 |
| (c) noise 0.03, pacing off | 0.818 | 0.988 | 0.939 | 0.848 | 0.758 | 0.879 | 0.938 | 0.899 | 0.4-1.0 | 1.5-3.0 |
| (c) noise 0, pacing off | 0.864 | 0.818 | 0.970 | 0.788 | 0.921 | 0.758 | 0.727 | 0.913 | 0.4-0.8 | 0.8 |

- **Default gain.** The worst fraction at gain 1.5 is 0.831 / 0.936 / 0.907 / 0.879 / 0.758 in the five blocks.
- **hidden_food is the limit.** It limits every five-scenario cell that is below its four-scenario value.
- **hidden_food's own gain profile:**
  - at noise 0.03 its best gain is 1.0 (8.1 finds), and it gets 5.6 at 2.0, up to about 30% below its best;
  - at noise 0 its best gain is 0.4 or 1.0 (12.9 finds), and it gets 11.0 at 0.8;
  - on held-out seeds it is nearly flat (11.8-13.4 over 0.4-3.0);
  - with pacing off it scores 1-11 finds per run and varies by up to 24-27% between gains, too few finds to locate a best gain.
- **The held-out preference for gains 0.4-0.8 reported in G19/G20 does not survive B.** B changed 43 of 72 held-out hidden-food rows. The held-out block's five-scenario band is now 0.4-3.0, and the bootstrap P(>= 0.8 of own best) is 0.72-1.00 at every gain. The earlier preference was within run-to-run variation.
- **Floors at gain 1.5.** hidden_food: 6.75 / 12.25 / 12.12 / 3.62 / 3.12. The other scenarios are as in G20.
- **vREST** is 0 in every run except four hidden_food runs with pacing off at noise 0 (gains 0.4, 1.5, 1.5 and 2.0), each <= 0.0033 of ticks.
- **Maze recall rate** is >= 0.998 in every cell from gain 0.4 to 3.0.

**Full-circle maze** (G18 protocol):

| gain (noise 0) | 0.4 | 0.8 | 1.5 | 3.0 |
|---|---|---|---|---|
| headings recalling | 16 / 16 | 16 / 16 | 16 / 16 | 16 / 16 |
| recalls | 76.8 | 88.9 | 90.8 | 90.2 |
| mean rate | 1.000 | 1.000 | 0.998 | 1.000 |
| fix/three recalls | 70.1 | 85.1 (15 of 16 recalling) | 85.9 | 90.2 |

- **Per heading** at gain 1.5: 13 recalls (heading 5.11) to 197 (heading 0.39). The lowest rate is 0.97 (heading 2.75).
- **Noise 0.03, seeds 1-4:** 63 of 64 runs recall (80.2 recalls, mean rate 0.982). The one failure is seed 3 at heading 3.53, which never finds the visible goal (300-tick timeout).
- **Gain 0.4:** the full-circle worst fraction is 0.85 of its own best (was 0.78).
- **Replay on / off** over the full circle: 90.8 / 32.4 recalls, rate 1.00 / 0.67, 16 / 7 of 16 headings recalling.

**Scope:**
- `python -m pytest -q`: 241 passed.
- The determinism and regression baselines and `tests/experiments/test_memory_navigation.py` are unchanged against 235cfdc.
- The legacy all-off digests are bit-identical. `goal_vector` is off there, so the new extinction setting is inert.
- The console serves `/api/meta`, and every scenario's `SimSession` steps 300 ticks and serialises.

**Impact:** `core/engine.py`, `core/config.py`, `ui/scenarios.py`, the tests above, `docs/decisions.md` (G17-G20 corrected in place where they were wrong), README, RECOMMENDATIONS.
