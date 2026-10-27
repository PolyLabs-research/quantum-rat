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
- **Pacing off (the core-engine energy policy): small, mostly positive at noise 0.03, mixed at noise 0.** Worst fraction at gains 0.4-3.0 is 0.895-0.988 (235cfdc: 0.860-0.952) at noise 0.03 and 0.864-0.976 (0.864-0.975) at noise 0. Part of the noise-0.03 rise at gain 0.4 is G18's maze change (132.4 → 138.5 recalls), not replay. At the default gain 1.5, recent vs legacy:
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
  - The 0.6 and 0.8 cells drop by 6-8 recalls (143.9, 141.0), because pacing rests take time. Seed 13 gets 78-108 at gains 0.4-0.8 (78 at 0.4 under G21's two-miss rule).
- **Replay now matters off axis.** On the full circle at gain 1.5 and noise 0, replay on / off gives 90.8 / 32.4 recalls at rate 1.00 / 0.67 (G21), and only 7 of 16 headings recall without replay. At the default heading the comparison is unchanged: 147 / 91 recalls, median 10 / 16 ticks.
- **No interaction with G17's replay rule.** With pacing at 0.6 the maze never microsleeps at console defaults, and full-circle and default-heading rows are identical under `replay_recent` true and false.

**Rejected or not defaulted:**
- **Storing the goal online on contact** (`goal_vector_source="online"`). It does slightly better in the maze (92.2 recalls, 100% of runs). But in `memory_nav_config` it lets the one-demonstration online agent beat the replay agent (prototype: 108 vs 138 total probe ticks over six goals), which fails `test_replay_geometry`. Tying the goal to replay keeps replay's role.
- **Vector precedence** (`goal_vector_flat` huge). It is clearly better at recall: 126.6 vs 85.9 on the full circle, and 186 vs 147 at the default heading with noise 0.03. But the value map, including its pain memory, would then never steer while a goal is held.
- **Goal vector on in the core engine.** `test_memory_navigation` and `test_replay_geometry` pass, but the steering guards fail with pacing off at gain 1.5: foraging 28 vs 39 items, hazard_field 15 vs 20.
- **Pacing at the old `pace_low` 0.4.** It is below the gate threshold and does not stop the drift.

**Costs and limits:**
- **The rest-off demo changed.** With the inter-trial rest off, recall no longer fails: the rate is 1.00, though with 29-30 recalls instead of 147 (median 23-62 ticks, 0 microsleep ticks; seeds 1-4 at noise 0 and 0.03, re-measured in G21). The rest-off numbers in DEC-3 and G16 (rate 0.69-0.75) now also need fatigue pacing set to 0. That gives 8-9 recalls at rate 0.67-0.68, with 626-725 microsleep ticks. The console watch text says so.
- **Recalls vary by heading** (13-197 per heading at gain 1.5, after G21's fix; 10 was the heading hit by the erase-on-contact bug). Where a 30-50 tick demonstration leaves the map weak but not flat (e.g. heading 5.11), the agent retraces the meandering demonstration.
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

> **Note (G46, 2026-10-27):** measured while the vision rays sensed the hidden sites as obstacles (and, on this profile, with a hot/cold shaping signal toward them). Without that, memory steering finds about half as much food as memory off, on every seed; the benefit below is withdrawn (G46 D1).

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
  - A map read rotated 22° (every phantom peak >= 2.8 m from a real site) keeps about half to nearly all of the extra finds over memory off, depending on the block (x2.74 / x1.91 / x2.67 against x2.84 / x2.85 / x4.08: 94% / 49% / 54% of the extra finds).
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
| (b) held-out | 0.946 | 0.943 | 0.915 | 0.919 | 0.924 | 0.919 | 0.905 | 0.905 |
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

> **Note (G46, 2026-10-27):** the hidden-food numbers here were measured with the hidden sites sensed by the rays; the memory benefit is withdrawn (G46 D1).

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
- **It still forgets a moved goal.** The goal is erased in all 48 moved-goal runs of this set-up (new goal at (-4, 6); median 157-187 ticks after the move, max 3950). Erasure needs two unrewarded revisits of the old place, so a goal the agent never revisits stays in memory: in an independent check with the new goal at (5, -6), two runs (heading 5.11, seeds 3 and 4) kept the old goal for all 4500 ticks, harmlessly, reaching the new goal on 209/212 and 359/359 trials. Only the stored goal place is forgotten; the replayed value gradient can still lead the agent back to the old place (at heading 0, 5-9 of 12 post-move trials, about the same as with extinction off) until it extinguishes.
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
- it does not need precise sites: a map about 3 m off keeps about half to nearly all of the extra finds;
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

## G22 — Legacy and research profiles: the split that Milestone 0a makes
**Date:** 2026-10-03  
**Why:** The research-readiness audit (docs/research_plan.md §1; probes in `tools/probes/`, outputs recorded in `tools/probes/README.md`) found that two pieces of physiology rewrite every behavioural number in this log. M0a does not delete anything: it names today's defaults the **legacy profile**, adds a **research profile** in which those couplings are off, and makes the difference a printable list. Commits 95667ce (flags, profiles, tests) and dcf28b8 (honesty pass), merged as 27946b6, plus this entry's commit.

### A. Why
The TRN gate multiplies egomotion before path integration, and the astrocyte's energy scale multiplies thrust and turn in `World.step`. Measured at `eea946f`, engine defaults, pacing off, 3,000 open-field ticks:
- `path_integration_capture` (seed 1): the gate is CLOSED on 2,542 ticks (85%) and NARROW on 399 (OPEN on 59), driven by ATP < 0.55 alone (κ never exceeds 1.1). The estimate captures 71.6 of 264.3 units of true path (27%) and ends 22.8 units from the body with a 2.17 rad heading error. Seeds 1-4 give the same numbers.
- `open_field_motion` (seed 1337): the mean step is 0.088 of the nominal 1.0 (max 0.985), 42.6% of steps are zero, and 1,270 of 3,000 ticks are microsleep.
- `microsleep_bout_length`: all 50 complete bouts last exactly 25 ticks; the recovery rule never fires. `glycogen_pinning`: glycogen sits at 0.03 from tick 148 on.

So the maze, steering and hidden-food results of G14-G21 measure a configuration (gate-safe pacing, teleports to the start, a throttled or frozen body), not a mechanism.

### B. What changed
Four flags, each at its legacy value by default, so `EngineConfig()` is bit-identical to `eea946f`:

| Flag | Legacy | Research | Where it acts |
|---|---|---|---|
| `SpatialConfig.gate_scales_egomotion` | True | False | `Engine._spatial_step` passes `sensory_gain = 1.0` when False, so the gate never scales the egomotion deltas |
| `AstrocyteConfig.scales_motion` | True | False | the `energy_scale` handed to `World.step` is 1.0 when False |
| `AstrocyteConfig.frozen` | False | True | the astrocyte does not tick: ATP stays 1.0 and glycogen 3.0, both still logged |
| `TRNConfig.microsleep_enabled` | True | False | `TRNGate` never starts a bout, so microsleep-gated replay never fires |

The thresholds hard-coded in `TRNGate.trn_state` are now `TRNConfig.closed_below_atp` 0.35, `open_at_atp` 0.55, `narrow_above_kappa` 1.1 and `narrow_gain` 0.4: same values, same branch order, checked against the old table on a 12 × 9 ATP × κ grid that includes the boundaries, with microsleep on and off. `EngineConfig.profile` is a label (not logged, so in no hash); `EngineConfig.legacy()` returns the defaults, `EngineConfig.research()` the research settings, and `a.diff(b)` lists every differing field as `(name, a_value, b_value)`. `EngineConfig.research().diff(EngineConfig.legacy())` prints:

```
('profile', 'research', 'legacy')
('astrocyte.scales_motion', False, True)
('astrocyte.frozen', True, False)
('value_memory.dwell_extinction', 0.0, 0.02)
('spatial.gate_scales_egomotion', False, True)
('trn.narrow_above_kappa', inf, 1.1)
('trn.microsleep_enabled', False, True)
('basal_ganglia.dopamine_explore_gain', 0.0, 0.6)
('basal_ganglia.ach_precision_gain', 0.0, 0.5)
('basal_ganglia.ne_threat_gain', 0.0, 0.5)
('basal_ganglia.fiveht_patience_gain', 0.0, 0.4)
```

*`trn.narrow_above_kappa = inf` was added by the verification pass on this entry (same day). With ATP frozen, the κ branch was the one way the gate could leave OPEN in the research profile, and at the legacy 1.1 it did at 2 of 41 seeds scanned (seed 13, ticks 105–112; seed 27, ticks 196–197), cutting the FORWARD drive to `forward_bias` × 0.4 on those ticks: a second criticality-to-behaviour coupling that `criticality_gain = 0` does not cover. The research baseline (seed 1337, 200 ticks) is unchanged by it; docs/profiles.md has the row.*

`research()` also sets `value_memory.generalization_radius = 0`, `value_memory.goal_vector = False` and `basal_ganglia.criticality_gain = 0.0`; these are already the legacy defaults (the console scenarios that use them set the radius and the goal vector themselves), so they do not appear in the diff. Kappa, avalanche sizes and the four modulator traces are logged in both profiles. Noisy odometry, a wall-contact reset, physical units, a place population and replay as an event stream are not in the research profile yet (docs/profiles.md).

*As of M0a. M0b adds three rows to the diff (`sensors.odometry_speed_noise` 0.05, `sensors.odometry_turn_noise` 0.01, `basal_ganglia.softmax_temperature` 0.1) and declares units identically in both profiles; docs/profiles.md has the current table (G24).*

### C. Acceptance, measured (`tests/engine/test_profiles.py`, 9 tests, re-run for this entry)
- **Research profile**, open field, seed 1337, 3,000 ticks: 0 microsleep ticks and 0 replay ticks; `trn_state` OPEN on all 3,000 ticks; `energy_scale` 1.0 and ATP 1.0 on every tick; the realised step equals the commanded thrust on all 2,999 steps (1.0 for FORWARD, 0.3 for a TURN, both exercised; the run never touches a wall); the path-integration estimate equals the true position and heading within 1e-9 (sensor noise 0, so odometry is exact; the difference is rounding, below 1e-12). The legacy profile at the same seed: 1,270 microsleep ticks, mean step 0.088.
- **Gate flag alone** (`gate_scales_egomotion = False`, everything else legacy), seed 1, 3,000 barren-world ticks, pacing off: the gate is still not OPEN on 2,941 ticks, but the estimate error stays below 1e-14 until the body is first clamped at a wall of the box at tick 276, and between clamps it does not move; 48 clamp ticks leave a final error of 0.471 units against 22.821 with the flag on. The residual is the wall clamp, which the heading-projected egomotion does not see; the wall-contact reset of M2b addresses it.
- **Each energy flag alone:** `frozen` holds ATP at 1.0 and glycogen at 3.0 with no bout and full steps; `microsleep_enabled = False` starts no bout although ATP crosses the trigger, and the gate still closes on low ATP; `scales_motion = False` leaves the astrocyte rule unchanged (replaying the commanded thrusts through a bare `Astrocyte` reproduces the logged ATP exactly) and unties the step from ATP.
- **Legacy unchanged:** `EngineConfig().diff(EngineConfig.legacy()) == []`; the determinism gate (`tests/determinism/baseline_hashes.json`, seed 1337, 200 ticks) is green by its own path, through `--profile legacy` and through the labelled config; `tests/engine/steering_legacy_hashes.json` and `baseline_hashes.json` are byte-identical to `eea946f` (`git diff` empty); `python -m tools.probes.open_field_motion` and `path_integration_capture` print the blocks recorded in `tools/probes/README.md` byte for byte.

### D. Tests
No test is retired. The impact analysis counted 85 of the 264 tests at the merge base as pinning legacy mechanisms or the toy protocols. The 74 that pin **mechanisms** keep running as they are and now carry one module-docstring line, "These tests pin the legacy profile (EngineConfig() defaults); see docs/decisions.md G22 and docs/profiles.md":

| file | tests | what they pin |
|---|---|---|
| `tests/engine/test_steering_robustness.py` | 20 | the all-off legacy digests, dwell extinction, wall-gate seeds 13 and 15, one habituation sample |
| `tests/engine/test_goal_vector.py` | 17 | goal-vector arbitration, writing and extinction |
| `tests/experiments/test_steering_guards.py` | 13 | seed-1, noise-0 outcome bounds of the steering stack |
| `tests/experiments/test_off_axis_maze.py` | 4 | goal vector and gate-safe pacing needed for 16-heading recall |
| `tests/experiments/test_goal_extinction.py` | 4 | `goal_extinction_misses` samples in the maze |
| `tests/characterisation/test_probes_run.py` | 4 | probes that read `generalization_radius`, `goal_vector`, `dwell_extinction` |
| `tests/engine/test_split_steering.py` | 3 | seed-1 maze scores, one seed-1337 replay comparison |
| `tests/ui/test_sim_session.py` | 3 | the maze's goal memory, the `dwell_extinction` console param |
| `tests/experiments/test_hidden_food.py` | 2 | the ×3.92 / ×0.88 single samples |
| `tests/experiments/test_memory_navigation.py` | 2 | seed-1337 ticks-to-goal pins of the replay effect |
| `tests/experiments/test_replay_geometry.py` | 1 | the six-goal replay-vs-online sample |
| `tests/engine/test_value_memory.py` | 1 | the generalization kernel |

The other 11 (in `test_protocol_lifecycle`, `test_protocol_summaries`, `test_runner_determinism`, the two regression tests and the two tournament tests; the plan estimated ten) edit a protocol list: `morris_water_maze`, `t_maze` and `survival_arena` are renamed `morris_water_maze_toy`, `t_maze_toy` and `survival_arena_toy` (module files and registry keys; the old keys are gone, so a stale name fails loudly), and the regression harness, its two tests and the two tournament tests run `open_field,beacon,foraging` instead of `open_field,morris_water_maze`, with `regression/baseline/` regenerated by the harness's own command. Two determinism baselines: legacy (`baseline_hashes.json`, unchanged) and research (`baseline_hashes_research.json` + `baseline_meta_research.json`, seed 1337, 200 ticks, schema 2.1.6, `python -m tools.update_determinism_baseline --profile research --i-know-what-im-doing`), each with its own test in `tests/determinism/test_trace_hash.py`. Suite: 274 tests (264 + 9 profile tests + 1 research baseline), all passing.

### E. Honesty pass (dcf28b8, plus two console tooltips in this entry's commit)
README, the console labels (`ui/static`, `ui/sim_session.py`), `ui/scenarios.py`, CHECKLIST_V2.md and RECOMMENDATIONS.md now say what the probes support. The criticality lattice is bond percolation on a 16 × 16 torus, subcritical at the default coupling 0.25 (spanning avalanches from 0.35) and critical at 0.5, above the slider's 0.45; κ stays within 0.89–1.09 at seeds 1–4 and 1337 and settles near 0.91; over 41 seeds it exceeds the 1.1 the TRN κ branch needs at two (seed 13, 8 ticks; seed 27, 2 ticks), see the research-profile note in docs/profiles.md; `criticality_gain` is 0 by default and at 1.0 is a 0.93–1.0 multiplier after warm-up (0.92 at the long-run κ) that changes no position in the barren, beacon or foraging worlds. The whiskers are computed but not read by action selection. The four neuromodulators are stated as their formulas: DA = reward − its running mean; ACh = the novelty bit; NE = ½ pain + ½ that bit; 5HT = the running mean itself. "Novelty" is labelled as a checksum-changed bit at its source (`brain/systems/working_memory.py`, `metrics/schema.py`) and in both readouts (1 on every tick at sensor noise 0.03). The toy assays say what they are: the water maze has no pool, cue or platform object and is reached in 5 ticks on-axis, 1,804 from heading π, and never within 2,000 ticks from 2 of 5 placements; the T-maze has no T and is reached in 6 ticks (84 from π/2, 40 from π); the survival arena's hazard is unsensed, so DA and 5HT sit at exactly 0.5 for the whole run at noise 0. The `neuromod_traces` block in `tools/probes/README.md` is re-recorded under the new key; every number is unchanged.

### F. Acceptance statement
G14–G21 are results of the legacy profile, measured as single deterministic samples at sensor noise 0 unless the entry states otherwise. They stay in this log as the record of that profile, their tests stay, and they are re-measured with confidence intervals over seeds in G23 (docs/research_plan.md §5, M0b item 15), once odometry noise and the softmax temperature make seeds samples. The research profile has no behavioural assertion of its own yet; the barren-world gates pass whatever the science does.

**Impact:** `core/config.py`, `core/engine.py`, `brain/systems/trn_microsleep_replay.py`, `tools/update_determinism_baseline.py`, `tests/determinism/`, `tests/engine/test_profiles.py`, `experiments/protocols/`, `regression/`, README, `ui/`, `docs/profiles.md`, `docs/research_plan.md` (status and the §5 / §10 marks), the twelve test docstrings above.

## G23 — What survives 30 seeds

> **Note (G46, 2026-10-27):** claim 1 (hidden food, × 2.91) was measured with the hidden sites sensed by the rays and a hot/cold shaping signal; without them memory steering scores × 0.47 (G46 C, D1). Claim 3 (the maze) barely moves without the leak (G46 C, exploratory).

**Date:** 2026-10-03  
**Why:** G22 accepted that G14–G21 are legacy-profile results measured as single deterministic samples, or as eight seeds at sensor noise 0.03, and docs/research_plan.md §1.1 says what they are read to mean. M0b item 15 asks for the first table with a confidence interval in the repository: the three headline numbers of G16 (the steering band), G19 (hidden food) and G18 / G21 (off-axis maze recall), each over thirty seeds, with the seeds made samples through every stochastic element the engine has (M0b item 8) and the statistics of M0b item 10. The script is `experiments/g23_remeasure.py`; every number below is read from `docs/data/g23/` (`summary.csv` has each statistic with its interval, the three tidy tables and `maze_recall_by_heading.csv` have every run).

**Design** (the script's docstring has the full version):
- Profile: legacy, `EngineConfig()` plus each console scenario's own config, run through `experiments.steering_sensitivity.run_jobs`. Two stochastic settings, both at sensor noise 0.03, both run in full: **A** adds odometry speed noise 0.05, odometry turn noise 0.01 rad and a softmax temperature of 0.05 on action selection (the seed reaches every stochastic element); **B** is sensor noise alone (what the G-entries ran when they wrote "noise 0.03", so their numbers and B's are like for like). Seeds 1–30 in every arm.
- Claim 1 (G19 / G21): hidden food over 3,000 ticks, memory on (the scenario's `value_gain` 1.5) against off (0), paired by seed, plus the moved-sites control of `tests/experiments/test_hidden_food.py` (every site jumps to a random place in the food band every 150 ticks, before the engine step; the same jumps for every seed and gain, drawn from one named `core.rng` stream).
- Claim 2 (G16 / G20): the four G16 scenarios (beacon, foraging, hazard_field, memory_maze; pacing on, as their configs say) over the harness's ten default gains, 0 to 3.0. Per gain: the steering guard's memory-cost statistic (mean score at the gain over mean score at gain 0, paired by seed) for foraging and hazard_field, vrest for all four, the maze recall rate, and G16's own band statistic, the worst-scenario fraction (min over the four of mean / own best mean). The *guard band* is the run of gains whose 95% intervals stay inside the guard's bounds (ratio ≥ 0.8 for foraging and hazard_field, vrest ≤ 0.15 everywhere); the *G16 band* is the run whose worst-fraction interval stays ≥ 0.8.
- Claim 3 (G18 / G21): the maze over the harness's full 16-heading set at gains 0.8 and 1.5, 1,500 ticks per run. Per seed: the recall rate pooled over the 16 headings (recalled hidden trials / hidden trials) and the number of headings whose run recalls (its own rate ≥ 0.9, the harness's `recall_ok`).
- Statistics: `analysis.stats`, BCa bootstrap with 10,000 replicates and one hashed seed per statistic. Ratios of means and the worst fraction resample seeds, so both sides of a ratio come from the same seeds in every replicate; Cliff's δ resamples the two samples independently.
- Guards: `core.seeds.require_seeds_are_samples` on every config (inside `run_jobs`, once per distinct set of stochastic elements, the moved-sites control included since the verification fixes routed it through the harness's `before_tick` hook); `analysis.stats.pseudo_replication_guard` on every per-seed outcome vector (the harness row's outcome fields, the run's trace hash included, the seed excluded; section D), with the counts in `guard.csv`.
- Verdict rules, written into the script before it ran: *survives* when the intervals are consistent with the entry's claim (claim 1: the ratio interval overlaps 2.8–4.1× and no seed loses; claim 2: both bands, read from the intervals, cover 0.4–3.0; claim 3: at both gains the recall-rate interval's lower end is ≥ 0.9 and the headings-recalling interval's lower end is ≥ 15 of 16, the off-axis guard's own bound); *weakened* when the effect is there but the claim's number is not; *does not survive* when the interval includes no effect. The entry's verdict is the weaker of A and B.

### A. Claim 1, hidden food: "memory finds 2.8–4.1× as much food and loses no paired run" (G19, G21)

| setting | n | memory on, finds [95% CI] | memory off | ratio of means [CI] | paired on − off [CI] | on > off / ties / on < off | Cliff's δ [CI] | from | verdict |
|---|---|---|---|---|---|---|---|---|---|
| B, fixed sites | 30 | 10.10 [8.50, 11.58] | 3.47 [2.97, 4.20] | **2.91 [2.43, 3.59]** | 6.63 [5.23, 8.13] | 97% / 0% / 3% | 0.84 [0.63, 0.95], large | G19 ×2.84 / ×2.85 / ×4.08, 8 / 0 | weakened |
| A, fixed sites | 30 | 12.60 [11.60, 13.60] | 9.40 [8.53, 10.33] | **1.34 [1.15, 1.52]** | 3.20 [1.57, 4.60] | 73% / 7% / 20% | 0.58 [0.31, 0.78], large | same | weakened |
| B, moved sites | 30 | 11.97 [10.73, 13.23] | 8.20 [7.30, 9.20] | 1.46 [1.28, 1.65] | 3.77 [2.43, 5.00] | 77% / 3% / 20% | 0.60 [0.33, 0.78], large | G21 control ×1.08–1.47 | — |
| A, moved sites | 30 | 13.27 [11.83, 14.77] | 12.00 [10.80, 13.30] | 1.11 [0.95, 1.26] | 1.27 [−0.63, 3.07] | 60% / 3% / 37% | 0.16 [−0.14, 0.43], small | same | — |

- Fixed-over-moved benefit factor (the ratio of the two ratios; the test's bound is 1.5): B 2.00 [1.62, 2.56], A 1.21 [1.00, 1.54].
- **Verdict: weakened.** Under B the multiplier itself survives (2.91 [2.43, 3.59] overlaps 2.8–4.1, and 29 of 30 seeds win), but "loses no paired run" does not: 1 of 30 seeds finds less with memory on. Under A the multiplier is 1.34 [1.15, 1.52]: memory still beats no memory (the paired interval excludes 0, δ is large), but by a third, not by three times, and 6 of 30 seeds lose.
- **A against B.** What A changes is the memory-off agent: 9.40 finds instead of 3.47. With `value_gain` 0 nothing in hidden food reads the place estimate, so the odometry noise cannot act there; checked: the thirty memory-off rows are byte-identical with and without it, and identical to runs with the softmax temperature alone. The rise is the 0.05 softmax temperature: a few sampled off-argmax actions break the wall loop, the agent wanders the interior and brushes the sites, which is exactly the regime G19 described as "memory costs when exploration alone already finds the food" (`forward_bias` 0.5: 37.2 without memory against 19.1 with it). Memory-on finds also rise (10.10 → 12.60), so memory is not harmful in A; it just has far less to add.
- **The moved-sites control** (G21: ×1.08–1.47 on eight seeds) is 1.46 [1.28, 1.65] in B and 1.11 [0.95, 1.26] in A. Of the extra finds with fixed sites, (1.46 − 1) / (2.91 − 1) = 24% survive without fixed sites in B and (1.11 − 1) / (1.34 − 1) = 32% in A; the plan's "between a twentieth and a quarter" was read from the same control at n = 8.

### B. Claim 2, steering band: "0.4–3.0 without value-induced resting" (G16, G20)

Each ratio is mean score at the gain over mean score at gain 0, paired by seed, with its BCa interval; the worst fraction is G16's statistic over the four scenarios, with the scenario that sets it. "max vrest" is the largest share of value-induced REST in any of the 120 runs at that gain. Setting A:

| gain | foraging ratio | hazard_field ratio | beacon ratio | worst fraction [CI] (limiting) | max vrest | maze recall rate | in guard band / G16 band |
|---|---|---|---|---|---|---|---|
| 0.2 | 1.02 [0.96, 1.08] | 0.99 [0.96, 1.01] | 1.01 [0.97, 1.07] | 0.211 [0.188, 0.240] (memory_maze) | 0.0007 | 0.978 [0.953, 0.989] | yes / no |
| 0.4 | 0.99 [0.94, 1.04] | 0.96 [0.92, 1.00] | 1.00 [0.93, 1.07] | 0.889 [0.856, 0.917] (memory_maze) | 0.0010 | 1.000 | yes / yes |
| 0.6 | 1.00 [0.94, 1.07] | 0.96 [0.92, 1.00] | 1.00 [0.93, 1.07] | 0.933 [0.911, 0.955] (memory_maze) | 0.0007 | 1.000 | yes / yes |
| 0.8 | 1.00 [0.94, 1.06] | 0.94 [0.91, 0.98] | 1.00 [0.93, 1.08] | 0.944 [0.917, 0.971] (hazard_field) | 0.0007 | 1.000 | yes / yes |
| 1.0 | 1.00 [0.94, 1.05] | 0.92 [0.88, 0.96] | 1.02 [0.94, 1.11] | 0.922 [0.884, 0.957] (hazard_field) | 0.0007 | 1.000 | yes / yes |
| 1.2 | 0.99 [0.93, 1.05] | 0.94 [0.91, 0.97] | 1.01 [0.93, 1.09] | 0.938 [0.913, 0.969] (hazard_field) | 0.0007 | 1.000 | yes / yes |
| 1.5 | 0.99 [0.94, 1.05] | 0.95 [0.92, 0.98] | 1.01 [0.94, 1.09] | 0.945 [0.921, 0.977] (hazard_field) | 0.0007 | 1.000 | yes / yes |
| 2.0 | 0.97 [0.92, 1.03] | 0.95 [0.91, 0.98] | 1.01 [0.95, 1.09] | 0.945 [0.927, 0.979] (hazard_field) | 0.0007 | 1.000 | yes / yes |
| 3.0 | 0.96 [0.90, 1.02] | 0.94 [0.91, 0.97] | 1.01 [0.93, 1.08] | 0.940 [0.925, 0.978] (hazard_field) | 0.0007 | 1.000 | yes / yes |

Setting B:

| gain | foraging ratio | hazard_field ratio | beacon ratio | worst fraction [CI] (limiting) | max vrest | maze recall rate | in guard band / G16 band |
|---|---|---|---|---|---|---|---|
| 0.2 | 0.99 [0.96, 1.03] | 1.07 [1.04, 1.11] | 0.97 [0.94, 0.99] | 0.194 [0.174, 0.211] (memory_maze) | 0 | 0.998 [0.993, 1.000] | yes / no |
| 0.4 | 1.00 [0.97, 1.03] | 1.01 [0.95, 1.05] | 0.97 [0.94, 0.99] | 0.942 [0.917, 0.975] (hazard_field) | 0 | 1.000 [0.998, 1.000] | yes / yes |
| 0.6 | 0.98 [0.95, 1.01] | 1.04 [1.00, 1.08] | 0.96 [0.93, 0.99] | 0.964 [0.952, 0.982] (beacon) | 0 | 1.000 | yes / yes |
| 0.8 | 0.98 [0.95, 1.01] | 1.05 [1.02, 1.09] | 0.95 [0.91, 0.97] | 0.948 [0.919, 0.966] (beacon) | 0 | 1.000 | yes / yes |
| 1.0 | 0.96 [0.93, 1.00] | 1.05 [1.01, 1.09] | 0.95 [0.91, 0.97] | 0.947 [0.926, 0.967] (beacon) | 0 | 1.000 | yes / yes |
| 1.2 | 0.97 [0.94, 1.01] | 1.04 [1.00, 1.08] | 0.94 [0.91, 0.97] | 0.941 [0.911, 0.963] (beacon) | 0 | 1.000 | yes / yes |
| 1.5 | 0.97 [0.93, 1.00] | 1.04 [1.00, 1.08] | 0.94 [0.91, 0.97] | 0.942 [0.917, 0.962] (beacon) | 0 | 1.000 | yes / yes |
| 2.0 | 0.96 [0.92, 0.99] | 1.04 [1.01, 1.08] | 0.94 [0.90, 0.97] | 0.938 [0.910, 0.961] (beacon) | 0 | 1.000 | yes / yes |
| 3.0 | 0.96 [0.92, 1.00] | 1.04 [1.01, 1.08] | 0.93 [0.89, 0.97] | 0.934 [0.902, 0.961] (beacon) | 0 | 1.000 | yes / yes |

| setting | n per cell | guard band (from CIs; point estimates) | G16 band (from CIs; point estimates) | tightest cost cell at 1.5: ratio, δ, seeds within a fifth | from | verdict |
|---|---|---|---|---|---|---|
| A | 30 | 0.2–3.0; 0.2–3.0 | 0.4–3.0; 0.4–3.0 | hazard_field 0.95 [0.92, 0.98], δ −0.41 [−0.65, −0.13] medium, 100% | G16 0.4–3.0 in five blocks, vREST 0.000 | survives |
| B | 30 | 0.2–3.0; 0.2–3.0 | 0.4–3.0; 0.4–3.0 | foraging 0.97 [0.93, 1.00], δ −0.24 [−0.51, 0.06] small, 100% | same | survives |

- **Verdict: survives.** Both bands cover 0.4–3.0 in both settings, with every interval inside the bounds. Gain 0.2, which G16 never ran, passes the guard's bounds but fails G16's: the maze recalls at 0.2 (rate 0.978 / 0.998) but on 29–31 trials instead of 143–151, so its own-best fraction is 0.19–0.21.
- **Resting.** The largest vrest in any of the 2,400 runs is 0.0010 of ticks (3 of 3,000), in A; 118 of the 1,800 open-scenario runs have any at all, every one of them in A, and in B it is 0 in all 1,200 runs. Under a softmax temperature the harness's `is_value_rest` also counts a sampled REST that the argmax would not have chosen, so A's figure is an upper bound and is non-zero even at gain 0 (hazard_field mean 0.0002 [0.0001, 0.0004]). Either way it is two orders of magnitude under the 0.15 bound.
- **Floors at gain 1.5** (mean score [CI]): A beacon 18.7 [17.1, 20.3], foraging 45.8 [44.2, 47.4], hazard_field 32.3 [31.5, 33.4], memory_maze 144.3 [142.3, 146.1]; B 24.3 [23.5, 25.0], 47.2 [45.5, 49.2], 33.2 [32.1, 33.9], 146.8 [145.2, 147.2]. B reproduces G20's eight-seed floors (24.6 / 48.4 / 31.8 / 147.1) within their intervals. At gain 0: A 18.5 / 46.3 / 34.2 / 0, B 25.8 / 48.8 / 31.9 / 0.
- **What memory buys outside the maze, with intervals** (paired difference at gain 1.5, items per 3,000 ticks): B beacon −1.5 [−2.4, −0.8] (δ −0.41, medium), foraging −1.7 [−3.3, 0.1] (δ −0.24, small), hazard_field +1.3 [0.0, 2.5] (δ +0.39, medium); A beacon +0.3 [−1.0, 1.6], foraging −0.5 [−2.9, 2.0] (both negligible), hazard_field −1.9 [−2.8, −0.7] (δ −0.41, medium). G16's "slightly negative in beacon, neutral in foraging, only the held-out block positive in hazard_field" is what B shows; A turns the beacon cost to nothing and the hazard_field gain into a 6% cost.
- **A against B.** The band is the same; the small effects change sign (hazard_field +4% → −6%, beacon −6% → 0 at gain 1.5), and the beacon's floor falls from 25.8 to 18.5 with memory off because the softmax agent chases a visible beacon less directly.

### C. Claim 3, maze recall: "16 of 16 headings recall" and "≥ 0.9 across gains" (G18, G21)

| setting | gain | n | recall rate, pooled over 16 headings [CI] | seeds ≥ 0.9 | headings recalling per seed [CI] | seeds at 16 of 16 | runs recalling (of 480) | recalls per seed | from | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| B | 0.8 | 30 | 0.999 [0.998, 0.999] | 100% | 15.70 [15.43, 15.87] | 77% | 98% (471) | 1,325 | G21: 16 / 16 at noise 0; 63 of 64 runs at 0.03 | survives |
| B | 1.5 | 30 | 0.999 [0.998, 0.999] | 100% | 15.70 [15.37, 15.87] | 77% | 98% (471) | 1,349 | same | survives |
| A | 0.8 | 30 | 0.989 [0.987, 0.991] | 100% | 12.67 [11.97, 13.30] | 0% | 79% (380) | 1,024 | same | weakened |
| A | 1.5 | 30 | 0.988 [0.986, 0.990] | 100% | 12.37 [11.73, 12.97] | 3% | 77% (371) | 1,018 | same | weakened |

- Gain 0.8 against 1.5, paired by seed: δ −0.09 [−0.39, 0.20] (A) and −0.11 [−0.39, 0.20] (B), both negligible; the paired difference in pooled rate is within ±0.002. "Across gains" holds at these two.
- **Verdict: weakened.** Under B the result is G21's: 98% of the 480 runs recall (G21: 63 of 64), 15.7 of 16 headings per seed, 23 of 30 seeds at 16 of 16; the hardest headings are 5.11 (87–90% of seeds) and 3.53 (93–97%). Under A, 21–23% of the runs fail: headings 0, 0.39 and 0.79 recall for every seed and 1.18 for 93%, but the twelve headings from 1.57 to 5.89 recall for only 60–83% of seeds. The pooled rate stays at 0.99 because a failing run times out at 300 ticks and so contributes 3–5 hidden trials where a recalling run contributes about 100: the pooled rate is the wrong statistic for this claim, and the per-run criterion is the one reported.
- **A against B.** A adds three elements at once, and which of them breaks off-axis recall is not separated here. The mechanism G18 describes is sensitive to all three: the goal vector steers by path integration from the start pose, a long visible-trial search accumulates odometry error that the teleport does not undo until the next trial, and a sampled off-argmax action during that search lengthens it.

### D. Guards
Every run had sensor noise 0.03 on, so `require_seeds_are_samples` passed on each of the 92 configs (B: `sensors.noise=0.03`; A: the four elements). `pseudo_replication_guard` runs on each of the 92 per-seed outcome vectors (`guard.csv`); since the verification fixes (same day) its vector is the outcome fields of the harness row, with the seed and the job's own description excluded and the run's trace hash (the gate's full `RunHash` over the run's ticks, now on every harness row; for claim 3, the hash of the seed's 16 run hashes) included, and it finds 30 distinct outcomes in every vector because the 30 trace hashes differ in every vector (`distinct_traces`). *Until those fixes the guard compared whole rows, seed included, so the "30 distinct outcomes in every vector" this section first reported was true by construction and said nothing; the runs are distinct, as the trace hashes now show, so no number in this entry changes.* The coarse outcome without the hash (`distinct_outcomes`: score and the task's counters, vrest, hidden food's six per-500-tick block counts, the maze's 16 per-heading pairs) repeats across seeds in 81 of the 92 vectors, as integer scores over 3,000 ticks make likely: down to 2 of 30 for the maze at gain 0 (0 recalls for every seed, the rows differing only in vrest) and 3 of 30 for B's maze at gains 1–3 (recall counts within a few of each other), 28 and 29 of 30 for hidden food in B (seeds 25 and 29, and 13 and 23, with memory off and 9 and 19 with memory on end on the same finds, sites and block counts), 30 of 30 in 11 vectors. The tidy tables show the coarse outcome: hidden_food.csv now carries the block counts next to score and sites_found (the (score, sites_found) pairs alone repeat down to 12 of 30 in B/memory_off). The reported metric alone has 1 to 30 distinct values per vector (the integer scores 1 to 21); the 1s are the maze at gain 0.

### E. Reproduce
`python3 -m experiments.g23_remeasure --workers 4` (the defaults: seeds 1–30, settings A and B, output `docs/data/g23/`). Measured: 4,560 runs in 516 s on the 4-core development box, including the bootstraps and, since the verification fixes, the per-tick trace hash of every run (429 s without it); `meta.json` records the runtime of the run that wrote the committed tables. `--quick --seeds 2 --out DIR` is the smoke test (`tests/experiments/test_g23_remeasure.py`, which also checks that two runs give byte-identical CSVs; `--quick` refuses the committed directory). The A / B files are 361 KB.

### F. What this changes in docs/research_plan.md §1.1 (not edited here)
The five readings of G14–G21 stand, and two of them now carry intervals that should replace the single samples:
- The hidden-food line should read: the multiplier is 2.91 [2.43, 3.59] over 30 seeds under sensor noise alone (one seed of 30 loses), and 1.34 [1.15, 1.52] once action selection has a 0.05 softmax temperature, because the exploring agent finds 9.4 items on its own instead of 3.5. That is the strongest form of G19's own finding, "place memory pays only where the agent's own exploration would not find the food": the margin is set by the exploration policy, not by the memory. The moved-sites control keeps 24% (B) to 32% (A) of the extra finds, against the plan's "a twentieth to a quarter" from eight seeds; the fixed-over-moved factor is 2.00 [1.62, 2.56] in B and 1.21 [1.00, 1.54] in A, not the 4.5× the test's single sample gives.
- The maze line ("works only because `pace_low` 0.6 keeps the TRN gate from freezing path integration, and `teleport_to_start` hands the agent an oracle re-anchoring every trial") should add a third condition: exact odometry. With 5% speed noise, 0.01 rad turn noise and the softmax on, off-axis recall drops from 98% to 77–79% of runs while the three headings nearest the axis (0, 0.39 and 0.79 rad) still recall for every seed and 1.18 rad for 28 of 30. The research profile's odometry placeholders (0.05 / 0.01 rad) are therefore already large enough to change this result, which M1's characterisation of those values has to take into account.
- The steering band is the one G-number that survives unchanged in both settings: 0.4–3.0 with every interval inside the bounds, and value-induced REST at most 0.001 of ticks (3 ticks of 3,000) in any run. It is also the least informative of the three, because memory changes the open scenarios' scores by at most about 8% at any gain in the band (the largest point estimate is hazard_field 0.92 [0.88, 0.96] at gain 1.0 in setting A); the band says memory is harmless there, not that it helps.
- §1.1's framing, "measured honestly, but they measure a particular configuration, not a brain mechanism", is what the A-against-B comparison shows directly: the two results that moved are the two that depend on the exploration policy and on exact self-motion, and the plan's M2b wall-contact reset and M1 odometry characterisation are the items that decide whether the maze result has any research-profile counterpart.

### G. Addendum (2026-10-03): which of A's three elements breaks off-axis recall
Section C left open which of A's three added elements (odometry speed noise 0.05, odometry turn noise 0.01 rad, softmax temperature 0.05) takes full-circle recall from 98% of runs to 77–79%. Three more settings add one element each to sensor noise 0.03: **A_speed**, **A_turn** and **A_softmax** (the script's `--setting separation`), run on claim 3 at gain 1.5 only (`--maze-gains 1.5`): 16 headings, seeds 1–30, 1,500 ticks per run, 480 runs per setting. The B and A rows are section C's gain-1.5 rows, from the same files. "Off-axis" is the twelve headings 1.57–5.89 rad (index 4–15 of the 16-heading set), the ones section C found failing under A; a run recalls when its own rate is ≥ 0.9 (the harness's `recall_ok`). The off-axis column counts recalling (seed, heading) runs over those twelve headings, read from `maze_recall_by_heading.csv` and `maze_recall_by_heading_separation.csv`; the other columns are the `fraction_runs_recalling`, `headings_recalling_mean`, `fraction_seeds_all_headings` and verdict rows of `summary.csv` and `summary_separation.csv`.

| setting | on top of sensor noise 0.03 | runs recalling (of 480) | headings recalling per seed, of 16 [BCa 95% CI] | seeds at 16 of 16 | off-axis runs recalling (of 360) | per-heading range, off-axis | verdict |
|---|---|---|---|---|---|---|---|
| B | nothing | 471 (98%) | 15.70 [15.37, 15.87] | 23 (77%) | 351 (0.975) | 0.90–1.00 | survives |
| A | speed 0.05 + turn 0.01 rad + softmax 0.05 | 371 (77%) | 12.37 [11.73, 12.97] | 1 (3%) | 253 (0.703) | 0.60–0.80 | weakened |
| A_speed | speed 0.05 | 469 (98%) | 15.63 [15.17, 15.83] | 23 (77%) | 349 (0.969) | 0.93–1.00 | survives |
| A_turn | turn 0.01 rad | 424 (88%) | 14.13 [13.53, 14.67] | 7 (23%) | 304 (0.844) | 0.73–0.93 | weakened |
| A_softmax | softmax 0.05 | 430 (90%) | 14.33 [13.90, 14.73] | 5 (17%) | 311 (0.864) | 0.73–0.97 | weakened |

The four near-axis headings (0 to 1.18 rad) recall in 120 of 120 runs in B, A_speed and A_turn, 119 in A_softmax and 118 in A, and the pooled recall rate is ≥ 0.994 in B and the three separation settings (0.9990, 0.9987, 0.9946, 0.9956) and 0.988 in A, for the reason section C gives.

- **Which element.** Two of the three, about equally: odometry turn noise alone loses 47 of B's 471 recalling runs (off-axis 0.975 → 0.844) and the softmax temperature alone loses 41 (→ 0.864), their headings-per-seed intervals overlap each other and neither overlaps B's or A's, while odometry speed noise alone loses 2 (469 against 471; 15.63 [15.17, 15.83] sits inside B's interval). A's loss of 100 runs is about the sum of the three (47 + 41 + 2 = 90), so the two elements add rather than one of them doing it alone.
- **What it implies.** For the research profile's placeholders (docs/profiles.md: 0.05 / 0.01 rad / 0.1, "characterised in M1"), the speed value is harmless to this result, the turn value is already past the point where it changes it (0.01 rad per tick alone costs 47 of the 480 runs), and the research profile's temperature of 0.1 is twice what was run here (0.05 alone costs 41 of 480; 0.1 was not measured). M1's characterisation of these values (docs/research_plan.md §5, M1) therefore has to treat the turn noise and the temperature as the two that set the off-axis result, separately and together since their effects add, with a speed-noise sweep the least urgent of the three; no setting with either of them on at these values keeps G21's 98%.

Command and runtime: `python3 -m experiments.g23_remeasure --setting separation --claims 3 --maze-gains 1.5 --workers 4 --tag separation`, 1,440 runs in 117 s on the 4-core development box (`meta_separation.json`; 10,000 bootstrap replicates; 99 s before the verification fixes added the per-run trace hash). The five `_separation` files add 65 KB to `docs/data/g23/`; the A / B files, `meta.json` included, were untouched by this run. Guards: `require_seeds_are_samples` passed on each of the three configs (sensor noise 0.03 plus the one element), and `pseudo_replication_guard` found 30 distinct outcomes, with 30 distinct trace hashes, in each of the three per-seed vectors (`guard_separation.csv`: 18, 28 and 28 distinct recall rates; section D on what the vector holds). `tests/experiments/test_g23_remeasure.py` grows to 13 tests: the three settings' one-element lists at the config level, and a tagged `--quick` run of claim 3 at gain 1.5 for each (under a second apiece).

**Impact:** `experiments/g23_remeasure.py` (new), `docs/data/g23/` (new, seven files), `tests/experiments/test_g23_remeasure.py` (new, 9 tests; suite 321), `docs/references.bib` (five entries: Efron & Tibshirani 1993, Cliff 1993, Romano et al. 2006 (unverified), Schuirmann 1987, Wichura 1988), this entry. No engine, harness, console or baseline file changed; `tests/engine/steering_legacy_hashes.json` and both determinism baselines are untouched. Addendum G (same day): `experiments/g23_remeasure.py` (settings A_speed / A_turn / A_softmax, `--setting separation`, `--maze-gains`, `--tag`), `docs/data/g23/` (five `_separation` files), `tests/experiments/test_g23_remeasure.py` (13 tests; suite 404).

## G24 — Milestone 0b: the instrument base
**Date:** 2026-10-03  
**Why:** docs/research_plan.md §5 lists ten items (6–15) that give the engine declared units, a split trace hash, seeds that are samples, numpy rules, a statistics module, provenance, the probes, packaging, a bibliography and the first interval-bearing result. They landed on the session branch in three waves: items 8, 10 and 13 as 3dc1392, db563f1 and e033b99 under 93e4aab (87f824e lowered the research odometry placeholders and regenerated the research baseline); items 6, 7, 9, 11 and 15 as 2eccbe5, 4b2c8d9, 8b5e700 and 3a5ece5, merged as f688183; the G23 addendum 1a50079; and this entry's commit. No science changed: every number below is an instrument measurement, and the legacy profile is bit-identical to `eea946f` throughout (section E).

### A. What landed

| item | where | one measured number |
|---|---|---|
| 6, units | `core/config.py` (`UnitsConfig(dt_s=0.2, metres_per_unit=0.1)`, `EngineConfig.to_dict()` / `from_dict()`), `tools/probes/realised_speed.py`, docs/units.md, `tests/engine/test_units.py` (24 tests) | research profile, open field, seeds 1–4, 3,000 ticks: 0.317 m/s on moving ticks (per seed 0.311–0.322; rats run tracks at 0.2–0.6 m/s), 13.7% immobile ticks, 28.9% of ticks with the body clamped at a wall; legacy 0.077 m/s, seeds identical |
| 7, physics / behaviour split | `metrics/hash.py` (kinds `full`, `behaviour`, `physics`), `core/determinism.py`, `tests/determinism/baseline_{behaviour,physics}_{legacy,research}.json`, `test_physics_split.py` (6), `test_trace_hash_split.py` (8), docs/determinism.md | criticality coupling 0.30 at the legacy defaults parts the physics hash at tick 7 and no behaviour tick in 200; `forward_bias` 0.7 parts the behaviour hash; both profiles' regenerated full files byte-identical to the committed ones |
| 8, seeds as samples | `core/sensors.py` (odometry speed and turn noise, stream `sensors_odometry`), `brain/systems/basal_ganglia.py` (`softmax_sample`, stream `action_softmax`), `core/seeds.py` (`require_seeds_are_samples`), `tests/engine/test_seeds_as_samples.py` (8), docs/profiles.md | research defaults, seeds 1–4: four trajectories, each pair first differing at tick 3–5; the sampler within 0.008 of the softmax probabilities over 20,000 draws; placeholders 0.05 / 0.01 rad / 0.1 (the odometry pair was 0.1 / 0.05 rad until 87f824e) |
| 9, numpy rules | `core/determinism.py` (`pin_blas_threads`, `numpy_generator`, `blas_info`), `core/__init__.py`, `tests/conftest.py` (this commit), `tools/compare_traces.py`, `tests/determinism/reference_trace_{legacy,research}.jsonl`, `test_cross_platform_tolerance.py` (5), `test_numpy_rules.py` (8), `.github/workflows/ci.yml` | tolerance gate 1e-9 absolute on floats, exact otherwise: worst difference 0 on the machine that wrote the references, a 1e-6 perturbation flagged with its tick and field; numpy 2.4.6 / OpenBLAS 0.3.31: `Generator` draws, `exp` and pairwise `sum` bit-identical across 1, 2 and 4 threads, `np.dot` over 2 M elements not |
| 10, statistics | `analysis/stats.py`, docs/stats.md, `tests/analysis/test_stats.py` (27) | the 95% BCa interval on a normal mean covers the truth 0.93 of the time at n = 30 (0.865–0.905 at n = 8, 200 replications per seed); a medium Cliff's δ has an interval excluding 0 in 80 of 100 replications at n = 30 against 15 at n = 8 |
| 11, provenance | `metrics/manifest.py` (manifest version 1), `experiments/runner.py` (`--profile`), `experiments/protocols/console.py` (`console_*`), `tournaments/manager.py`, `ui/sim_session.py`, `tests/metrics/test_manifest.py` (10), `tests/experiments/test_console_protocols.py` (19) | 300 ticks of `open_field`, `hidden_food` and `memory_maze` at seed 7: `ticks.jsonl` and the run hash byte-identical between the live session and the headless `console_*` run; the manifest enters no hash |
| 12, probes | `tools/probes/` (18 probes; `realised_speed` added by item 6), `tests/characterisation/test_probes_run.py` (19) | `open_field_motion` and `path_integration_capture` print their 9 and 7 recorded result lines verbatim at this commit |
| 13, packaging | `pyproject.toml` (quantum-rat 1.0.0, `requires-python >= 3.11`, SPDX `MIT`), `requirements.lock` (25 pinned versions), `LICENSE`, `LICENSE-docs` (CC BY 4.0), `CITATION.cff` (1.2.0), `.github/workflows/ci.yml` | the macOS job deselects five exact-hash gates (three files, two single tests) and runs the tolerance gate; a fresh venv from the lock passes `pip check` |
| 14, bibliography | `docs/references.bib` | 115 entries: 104 verified, 8 verified with a correction, 3 unverified (Sorscher 2023, Cheng & Frank 2008, Romano 2006) (121 at G25, section A7) |
| 15, G23 | `experiments/g23_remeasure.py`, `docs/data/g23/` (12 files, 427 KB), `tests/experiments/test_g23_remeasure.py` (13; 16 after section F) | 4,560 runs in 516 s (`meta.json`) plus 1,440 in 117 s for section G (429 and 99 s before the per-run trace hash of section F); hidden food 2.91 [2.43, 3.59] under sensor noise alone and 1.34 [1.15, 1.52] with all elements; the steering band 0.4–3.0 in both settings; the maze recalling in 471 of 480 runs under sensor noise alone, 371–380 with all elements |

Suite: 406 tests (276 at `v1.0-honest`), about 70 s on the 4-core development box.

### B. Decisions this surfaces (recommended default in bold)
1. **Unit calibration.** `dt_s = 0.2`, `metres_per_unit = 0.1` are a declaration no engine constant reads. **Freeze them as declared** (docs/units.md): the realised research moving speed, 0.317 m/s, sits inside the rat band, the 20-unit arena is the 2 m open field RQ4 asks for, and the 300-tick timeout is the standard 60 s trial. A 0.1 s tick or a 0.2 m unit both make FORWARD 1 m/s and move every duration in plan §2; the cost of changing later is an edit to docs/units.md, a probe re-run and a re-read of §2, not a baseline regeneration.
2. **Copyright holder.** `LICENSE` says "Copyright (c) 2025-2026 quantum-rat contributors"; `pyproject.toml` and `CITATION.cff` name "PolyLabs Research", and the citation file carries a placeholder person entry (`Family-name` / `Given-name`). **Keep "quantum-rat contributors" in LICENSE** (MIT needs no single holder) and fill in or delete the placeholder person before the first tagged release that gets a DOI (`v1.3-track-replay`); until then "Cite this repository" renders a placeholder author.
3. **The `pytest<9` cap.** The `dev` extra pins `pytest>=8,<9`; CI installs 8.x. The development box runs pytest 9.1.1 and the suite is green on it (406 passed). **Lift the cap to `pytest>=8`** at the next packaging touch; nothing in the suite depends on an 8-only behaviour.
4. **threadpoolctl.** The manifest's `platform.blas_runtime` was `null` unless `threadpoolctl` was installed; it was not a dependency and not installed here, so every manifest written up to `v1.1-base` records numpy's build-time BLAS string (`scipy-openblas 0.3.31 ... Haswell`), not the kernel the loaded library chose. **Taken by the verification fixes (section F, same day), ahead of the recommendation to add it before M2b**: `threadpoolctl` is a base dependency, `blas_runtime` is always filled (here: OpenBLAS 0.3.31.188.0, kernel `SkylakeX`, 1 thread), and the manifest also records `numpy_loaded_before_pin`, because the verification found that a process importing numpy before `core` (as `experiments/g23_remeasure.py` and anything importing `analysis.stats` first did) carried a manifest claiming a one-thread pin while OpenBLAS ran 4; the G23 tables are unaffected (the engine uses no BLAS product yet, docs/determinism.md rule 6), and `analysis/__init__.py` now imports `core` first.
5. **The research profile's placeholders after G23 section G.** Turn noise 0.01 rad alone costs 47 of 480 off-axis maze runs in the legacy profile, a 0.05 softmax temperature alone 41, speed noise 0.05 two; the research temperature 0.1 was not run. **Keep the three values until M1 characterises them**: the research profile has no behavioural assertion to tune them against, and the result they move is a legacy-profile one whose research counterpart needs M2b's wall-contact reset. M1 sweeps turn noise and temperature separately and together (their effects add), speed noise last.
6. **Package version.** `pyproject.toml` and `CITATION.cff` said 1.0.0 at tag `v1.1-base`, so a citation could not tell the two milestones apart. **Keep version = milestone tag**: 1.1.0 from the verification fixes on (section F), bumped at each milestone tag so the citation names the release.

### C. What G23 changes about the record
Two of §1.1's five readings now carry intervals in place of single samples: the hidden-food multiplier is 2.91 [2.43, 3.59] under sensor noise alone and 1.34 [1.15, 1.52] with every element on, and the maze line gains exact odometry as its third condition, with turn noise and the softmax temperature named as the elements that break off-axis recall (docs/research_plan.md §1.1 says so now). The steering band is the one G-number that survives unchanged, and §1.1's framing, that G14–G21 measure a configuration rather than a mechanism, is what the A-against-B comparison shows directly: the two results that moved are the two that depend on the exploration policy and on exact self-motion.

### D. Residuals carried into M1
- The harness's `is_value_rest` counts a sampled REST the argmax would not have chosen, so under a softmax temperature vrest is an upper bound and is non-zero at gain 0 (hazard_field 0.0002 [0.0001, 0.0004] in setting A); the largest value in any of the 2,400 band runs is 0.0010. Attributing a REST to the value drive per draw is a harness change for M1 or M2a.
- 28.9% of research-profile open-field ticks (25.2–32.3% per seed) have the body clamped at a wall: the box clamp holding a softmax-driven agent, not wall following. Every research-profile open-field statistic carries it until M2b's wall-contact reset and M4a's walls and body radius change what a wall contact is.
- The heading estimate random-walks at sd 0.01 rad per tick (about 0.5 rad over 3,000 ticks) with nothing to reset it until M2b: at seed 1337 the estimate's error first exceeds 0.5 units at tick 37, is 9.2 units at tick 3,000 and 11.6 at most.
- The macOS tolerance gate is in `.github/workflows/ci.yml` but has not run: nothing on this branch has been pushed, so the 1e-9 agreement is measured on Linux only (where it is exact) until the first macOS CI run reports.
- Unchanged from G22 (docs/profiles.md): no replay in the research profile until M1 turns it into an event stream, and the checksum "novelty" bit still enters action selection in both profiles.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 406 passed (404 at 1a50079 plus the two thread-pin tests), about 70 s.
- Legacy identity: `git diff eea946f -- tests/engine/steering_legacy_hashes.json tests/determinism/baseline_hashes.json` is empty; `test_trace_hash.py`, `test_trace_hash_split.py` and `test_profiles.py`'s legacy test are green against the committed files; `python3 -m tools.probes.open_field_motion` and `path_integration_capture` print every recorded result line of `tools/probes/README.md` verbatim, and the only M0b change to that file is the `realised_speed` block (2eccbe5).
- Three baselines per profile (full, behaviour, physics) plus a reference trace, each at seed 1337 over 200 ticks, schema 2.1.6, described by `baseline_meta.json` and `baseline_meta_research.json` (generated 2026-10-03T15:06 UTC, the same engine run per profile); the legacy full file is the one from `eea946f`.
- Tag `v1.1-base` at this entry's commit, closing Milestone 0b.

### F. Verification fixes (same day, the commit after `v1.1-base`)
A five-lens verification of M0b (determinism and manifests, G23 reproduction, code review and packaging, docs) returned 29 findings; the commit "M0b: verification fixes" applies all 7 majors and 22 minors and lists each. What changed in substance, with the measured facts:
- **Provenance was wrong where numpy loaded before `core`.** `experiments/g23_remeasure.py` imported numpy first (as does anything importing `analysis.stats` first), so its process carried the four `*_NUM_THREADS = 1` variables while OpenBLAS ran 4 threads, and a manifest from such a process claimed a pin not in force. `pin_blas_threads()` now records `core.determinism.NUMPY_LOADED_BEFORE_PIN` on its first call and warns; `threadpoolctl` is a base dependency (section B4, taken early) and `blas_info()` reports the loaded libraries' kernel and thread count (`blas_runtime`: here OpenBLAS 0.3.31.188.0, kernel `SkylakeX` at run time against the build string's `Haswell`, 1 thread); the manifest's platform block is built from `blas_info()` and carries `numpy_loaded_before_pin`; `analysis/__init__.py` and the G23 script import `core` first; the suite's thread-pin test now asserts the conftest's flag, the module's flag and the live OpenBLAS count, and a new test shows a late pin is recorded and warned about. The G23 tables are unaffected: the engine uses no BLAS product (rule 6).
- **G23's pseudo-replication guard was vacuous.** `record_guard` handed `pseudo_replication_guard` whole harness rows, seed included, so "30 distinct outcomes in every vector" (section D) was true by construction. Every harness row now carries `trace_hash` (the gate's full `RunHash` over the run's ticks), the guard compares the outcome fields only (seed and job description excluded), and `guard.csv` reports `distinct_outcomes` (coarse, without the hash) and `distinct_traces` beside `distinct_values`: 30 distinct traces in every one of the 95 vectors, coarse outcomes repeating in 81 of 92 (section D, rewritten). `docs/data/g23/` was regenerated twice (once for the block counts, once with the hash): every statistic in `summary.csv`, `summary_separation.csv`, `steering_band.csv`, `maze_recall*.csv` and the score / sites_found rows of `hidden_food.csv` is byte-identical to the `v1.1-base` files; `hidden_food.csv` adds the six block counts per run, the two guard files change as described, and the two meta files record the new runtimes (516 s and 117 s, the per-tick hash costing about a quarter).
- **The moved-sites control is the harness's own loop**: `Job.before_tick` (a per-run hook factory) and `HiddenFood.band_point` / `jump_sites` replace the script's copy of `run_job` and the test's copy of the band construction; `set_field` is the harness's public dotted setter. The claim-1 rows reproduced byte for byte through the hook.
- **The baseline tool cannot overwrite the legacy set**: `--profile legacy` in place exits 2 with the rule, the default profile is research, and `--out-dir` needs no flag (`tests/determinism/test_update_tool.py`, 5 tests). The committed `baseline_meta.json` had been regenerated by the tool in M0b (byte-identical hashes; the meta file gained the split's keys), which this rule now prevents by accident.
- **The macOS job selects by marker**: every test that compares against a committed hash file is marked `exact_hash` (26 tests, `pytest.ini`), the macOS step runs `-m "not exact_hash"`, and `test_exact_hash_marker.py` fails when a reader of a committed hash file is unmarked; the seeds-as-samples legacy gate, missing from the old file list, is marked.
- **Strict JSON and validation**: `EngineConfig.to_dict()` writes non-finite floats as `"inf"` / `"-inf"` / `"nan"` and `from_dict` reads them back and runs each section's `__post_init__` (a negative `dt_s` is refused); the manifest's `config` is `to_dict()`, written with `allow_nan=False`; `git_info` reports only this repository (top-level must be the package's root) and keeps the SHA when the status lookup alone fails.
- **Packaging**: version 1.1.0 in `pyproject.toml` and `CITATION.cff` (section B6), `threadpoolctl>=3` in the dependencies and `threadpoolctl==3.7.0` in the lock; `--quick` in the G23 script refuses the committed output directory.
- **Docs**: the corrections the docs lens found (G23 E's runtime, the near-axis heading 1.18 at 28 of 30, the 8% hazard_field cost, vrest "at most 0.001", speed noise costing two runs, README's source line, the plan's §1 column header, §5 items 9/11/13, §6, §7's bibliography count, §8's calibration risk, §9 item 10, G22 B's dated note, G23 G's pooled rate, docs/determinism.md on `--out-dir`, rule 2, rule 6 and the unmeasured macOS tolerance).

Measured after the fixes: `python3 -m pytest -q` 423 passed, about 80 s; `git diff eea946f -- tests/engine/steering_legacy_hashes.json tests/determinism/baseline_hashes.json` empty; `pytest -m "not exact_hash"` collects 397 of 423; the two determinism baseline sets unchanged. Declined: no finding; the 15 nits were not applied (information only). The tag `v1.1-base` stays at section E's commit.

**Impact:** `tests/conftest.py` (imports `core` before any test module), `tests/determinism/test_numpy_rules.py` (two tests), docs/profiles.md (baseline file set, the placeholders after G23 G), docs/determinism.md (the conftest), README (G23's numbers, the research profile's M0b additions, the stats module, the tag), docs/research_plan.md (status, §1.1, §4, §5 items 6–15, §10), this entry. No engine, harness, console or baseline file changed. Section F: `core/determinism.py`, `core/config.py`, `metrics/manifest.py`, `analysis/__init__.py`, `experiments/steering_sensitivity.py`, `experiments/g23_remeasure.py`, `ui/scenarios.py`, `tools/update_determinism_baseline.py`, `pyproject.toml`, `requirements.lock`, `CITATION.cff`, `pytest.ini`, `.github/workflows/ci.yml`, `docs/data/g23/` (five files), the tests named above, README, docs/research_plan.md, docs/determinism.md, docs/profiles.md, G22 B, G23 D–G and this entry.

## G25 — Milestone 1: value rule and odometry
**Date:** 2026-10-03  
**Why:** docs/research_plan.md §4 row M1 asks for five things: kernel smoothing and dwell extinction off in the research profile, tabular TD(0) and linear TD(λ) over Gaussian place features, the odometry noise of M0b item 8 characterised, replay refactored into an event object with no new rule, and the goal-vector slot relabelled `oracle_homing`. They landed on the session branch as three commits on top of `v1.1-base` (48c5817): c9c8867 (the learners), 1d1e25e (replay events, `oracle_homing`) and b752a4c (odometry, the ATP decorrelation, the harness's vrest reading), merged as 61dea6d and eac87a7, plus this entry's commit. No science changed and no behaviour moved in either profile: the learners are not wired into the engine, the events are bookkeeping beside the backups, and the legacy profile is bit-identical to `eea946f` (section E).

### A. What landed, against the §4 M1 row
1. **Kernel and dwell extinction off in research.** Already so since G22: `research()` sets `generalization_radius = 0` and `dwell_extinction = 0.0` (docs/profiles.md). M1 adds nothing here but the proof in item 2 that at radius 0 `ValueMemory` is tabular TD(0).
2. **Tabular TD(0) and linear TD(λ)** (`brain/systems/value_learners.py`; docs/value_learners.md; `tests/brain/test_value_learners.py`, 29 tests; `docs/data/m1/value_learners_chain.csv`). One `ValueFunction` interface (`value`, `update` returning the TD error, `reset_episode`, `parameters`); `TabularTD0` over 0.5-unit bins with V(terminal) = 0, the same arithmetic as `ValueMemory` at radius 0 (the two agree to 0.0 after 300 chain episodes, asserted at 1e-12); `GaussianPlaceFeatures` normalised to a partition of unity, so V is a convex combination of the weights and never reads above the largest one; `LinearTDLambda` with replacing or accumulating traces. On the 12-cell chain (lr 0.2, γ 0.9, reward 1.0 on arriving at the terminal cell 11, exact V(d) = γ^d, convergence when no cell moves more than 1e-9 in a pass, capped at 2,000 passes): tabular converges in 185 passes with max |V − γ^d| 5.1e-9; linear at widths 0.125, 0.25 and 0.5 cell converges at the same floor (4.1e-9 to 1.1e-8 in 113–206 passes over λ ∈ {0, 0.5, 0.9} and both trace kinds); at 1.0 cell the error after the 2,000-pass cap is 1.6e-3 (λ 0; 1.1e-3 and 2.9e-3 at λ 0.9) and at 2.0 cells 7.1e-3 (λ 0; 8.3e-3 and 7.5e-3 at λ 0.9), while the batch TD(0) fixed point of the same features is γ^d to 4e-13 at every width (twelve features over eleven states represent any value vector), so the wide-width residual is slow convergence through an alternating-weight mode, not a representation bias (still falling at 40,000 passes: 1.2e-6 at 1.0 cell, 1.5e-3 at 2.0). max V is 1.000 at every row (the largest table value is 1 + 7.6e-12, at 0.5 cell, λ 0.5, replacing traces) and the largest weight 1.23, against the bound 1/(1 − γ) = 10; V(d) is monotone in d at every width. The legacy kernel at radius 1 on the same chain converges to V(goal) = max V = 10.0 (6.07 at radius 2, the probe), pinned as a legacy property within 1e-2, not fixed. Elementwise numpy and `numpy.sum` only, no BLAS product, no RNG; two runs give identical floats.
3. **Odometry characterised** (`experiments/odometry_characterisation.py`; docs/odometry.md; `docs/data/m1/odometry_{slopes,curves,seeds,atp}.csv` and `odometry_meta.json`, 57 s with 4 workers at 48c5817; `tools/probes/odometry_growth.py`, the 19th probe, its README block recorded; `tests/experiments/test_odometry_characterisation.py`, 10 tests; `tests/characterisation/test_probes_run.py` gains one for the probe). The research profile in a 5,000-unit barren box, 30 seeds per condition, 2,000 units (200 m) of travel, the error against the body recorded every 25 units, the log-log slope of the mean error against distance fitted over [50, 2000] with a seed-bootstrap BCa 95% interval. In an open barren world the research walk is a straight line (99.8% FORWARD: a TURN is a 1-in-500 softmax draw at temperature 0.1 when nothing is in view), so the three named conditions were also run on a turning-walk control (`forward_bias` 0.15: 45% FORWARD, 52–54% TURN). Straight walk: speed noise 0.05 alone 0.987 [0.970, 1.003], turn noise 0.01 rad alone 1.472 [1.310, 1.623], both (the research defaults) 1.386 [1.263, 1.498]; turning walk 0.519 [0.435, 0.596], 1.041 [0.922, 1.159] and 0.941 [0.814, 1.064]. The slopes are the laws written before the runs. The speed error is not zero-mean, because the noise is added before the Observation's forward clamp and a FORWARD step of 1.0 sits at its top, so a full-thrust tick's estimate falls short by 0.05/√(2π): measured −0.0198 per unit at speed 0.05 (analytic −0.01995; −0.0394 at 0.1; −0.0147 on the turning walk, the FORWARD share of its distance), which is the whole speed-only error (38.4 ± 1.9 units at 200 m against a random sd of 1.9) and reads as slope 1.0 on a straight walk and 0.5 once turns cancel the shortfall vectors. The heading error is a random walk whose sd follows σ√t within sampling error (0.425 rad measured against 0.448 at 0.01 rad), integrated along a straight line into a t^1.5 law (394 ± 297 units at 200 m, per-seed slopes 0.23–2.49) and decorrelated by turns into a t^1.0 one. The grid over turn {0.0025, 0.005, 0.01, 0.02} rad × speed {0, 0.05, 0.1} on the straight walk shows the turn value setting the error's size linearly and the speed value lowering the slope by mixing in the linear clamp term. ATP decorrelation (legacy profile, default box, research odometry, 3,000 ticks, seeds 1–4): with `gate_scales_egomotion` on, the relative step error on moving ticks (|estimated step| / |true step| − 1) tracks ATP at r 0.872–0.875; with it off r is −0.072 to −0.038 (|r| < 0.08); the error at tick 3,000 is 21.3 with the gate and 1.79 without (means of the four seeds). The raw position error correlates with ATP at −0.13 to −0.31 under both flags (ATP decays from 1.0 over its first ~100 ticks while any error grows: a shared time trend) and within ±0.08 from tick 200 on under both. The legacy body walk and the ATP series are the same in all eight runs (the body does not read the odometry draw), so the four seeds vary only the odometry realisation; the flag-off residual is not the speed noise but 14 wall-contact TURN ticks whose steps the heading projection under-reads (section F, the verification fixes: a zero-noise control gives the same r).
4. **Replay as an event object** (`brain/systems/replay_events.py`; `Engine._replay`; `tests/engine/test_replay_events.py`, 16 tests). Each microsleep replay is one frozen `ReplayEvent` (`tick_start`, `tick_end`, `trigger`, `rule`, `cells` in backup order, `direction`, `start_cell`, `n_backups`, `span`) in `engine.replay_log`, a `ReplayLog` bounded at 256 with `latest(n)` and `drain()`. Lifecycle: an `OpenReplayEvent` is opened on a bout's first replay tick, fed the start cell of every transition it backs up, and closed into the log when the sleep ends or `begin_episode` cuts it; a replay that backs up nothing is no event. One trigger, `microsleep`, and the two rules that existed: `reverse_trajectory` (direction `reverse`, span the snapshot's length; `value_memory.replay_recent`, the default) and `trn_index` (direction `forward`, span the TRN buffer's length; the legacy indexing). Measured at the legacy defaults, seed 1337, 3,000 barren-world ticks: 51 bouts (1,270 replay ticks), the last still in progress at tick 2,999, and 50 events, one per completed bout, each carrying the bout's ticks and its tick-by-tick cells; a teleport three backups into a sleep closes the event with those three and the rest of the sleep adds none; the research profile produces no event (no microsleep). `experiments/runner.py` and the console's recording write `replay_events.jsonl` and `n_replay_events` in `summary.json`, the console frame carries the last five events, and the headless `console_open_field` logs the same events as the live session at one seed. The backups, the context fields the console reads and TickData are exactly as they were: the legacy trace hash is unchanged (the determinism gate, `tests/determinism/test_trace_hash.py`; the copy of it this test file carried was removed by the verification fixes, section F).
5. **`oracle_homing`.** `ValueMemoryConfig.goal_vector` is now the field `oracle_homing` (default False, same meaning: an explicit oracle control condition that, where the sampled map is flat, turns toward the remembered goal by path integration), with `goal_vector` a read/write property alias, so every call site and `--set value_memory.goal_vector=...` keep working; `to_dict`, `diff` and the manifest write `oracle_homing`, `from_dict` accepts either name and refuses both with different values; the `goal_vector_*` fields and `ctx.goal_vector_active` keep their names (they name the mechanism). `research()` sets it False, as it did under the old name.
6. **The harness's vrest** (`experiments/steering_sensitivity.py`; G24 D's first residual). `is_value_rest` attributes a REST on the argmax of the scores, not on the sampled action, so a REST the softmax sampler drew while the argmax was a move no longer counts. At temperature 0 the reading is unchanged (the pinned `--json` outputs pass); under a temperature the new reading implies the old per tick, so vrest can only fall, and at temperature 0.3 sampled RESTs occur and none counts (4 tests added to `tests/experiments/test_steering_sensitivity.py`).
7. **References.** Valerio & Taube 2012, Cheung et al. 2012, Cheung & Vickerstaff 2010 and Souman et al. 2009 (section H, b752a4c), Sutton & Barto 2018 and Tsitsiklis & Van Roy 1997 (section I, this commit), all six verified by search: 121 entries, 110 verified, 8 with a correction, 3 unverified.

Suite: 483 tests (423 at the verification fixes after `v1.1-base`), about 100 s on the 4-core development box.

### B. Acceptance against the §4 M1 row, line by line
| acceptance | measured | verdict |
|---|---|---|
| tabular V(d) = γ^d within 1e-2 (today 10.0 at radius 1 after convergence) | 5.1e-9 after 185 passes (87 passes to within 1e-2); the 10.0 at radius 1 reproduced and pinned as legacy | met |
| linear features of width ≤ 0.5 cell: V(d) = γ^d within 1e-2 | 0.125, 0.25 and 0.5 cell at the convergence floor (7.1e-9 at 0.5 cell, λ 0; 1.1e-8 at λ 0.9); 92 passes to 1e-2 at 0.5 cell, λ 0, and 38 at λ 0.9 | met |
| at every width V ≤ 1/(1 − γ) | max V 1.000 (1 + 7.6e-12 at most) and max weight 1.23 against 10, at every width from 0.125 to 2.0 cells | met |
| V(d) monotone in d | asserted at every row of the table | met |
| the maximum error against γ^d falls monotonically as the width shrinks | strictly above the floor: 7.1e-3 > 1.6e-3 > 7.1e-9 at 2.0 > 1.0 > 0.5 cells (λ 0; 8.3e-3 > 1.1e-3 > 1.1e-8 at λ 0.9, replacing traces); below 0.5 cell the three narrow widths all sit at the 1e-9 floor (4.1e-9 to 1.1e-8), where the order is the tolerance's, not the width's | met with a stated reading: monotone above the floor, "all at the floor" below it (the test asserts exactly that) |
| wider widths report their bias | 1.6e-3 at 1.0 cell and 7.1e-3 at 2.0 after the cap, reported with the batch fixed point γ^d to 4e-13 beside them: a finite-budget residual, not a representation bias (A2) | met |
| path-integration error vs distance: log-log slope in 0.5–1.5 over 200 m | every point estimate inside on both walks (straight 0.987 / 1.472 / 1.386, turning 0.519 / 1.041 / 0.941); on the turning walk every interval is inside (0.435 to 1.159); on the straight walk the turn-only interval reaches 1.623 and the both-noises interval 1.498 | met with a stated reading: the acceptance is read on the turning-walk control (C3). The straight walk's turn-only interval crosses 1.5 because a heading random walk integrated along a straight line is a t^1.5 law, a property of the barren world's walk rather than of the odometry; both walks are recorded |
| legacy profile with the gate flag off: \|r(error, ATP)\| < 0.1 | on the relative step error on moving ticks: \|r\| 0.038–0.072 with the flag off, against 0.872–0.875 with it on; the raw position error reads −0.13 to −0.31 under both flags over all ticks and within ±0.08 from tick 200 on under both | met with a stated reading: the statistic is the relative step error on moving ticks, because that is the quantity the gate acts on (gate − 1 plus noise with the flag on) and the one that separates the two flags; the raw error's −0.2 is there with and without the coupling, a shared time trend of ATP's initial decay and a growing error, and so measures nothing about the coupling. The flag-off residual (−0.12 to −0.16 from tick 200 on, against +0.83 with the gate) is not the speed noise: a zero-noise control run gives the same r (−0.064 all moving ticks, −0.19 from tick 200), from 14 wall-contact TURN ticks whose sliding step the heading projection under-reads by a third; the speed noise's own contribution (off-wall ticks) is \|r\| ≤ 0.04 (docs/odometry.md, the ATP table's added columns and control row; section F) |

### C. Decisions this surfaces (recommended default in bold)
1. **The research odometry placeholders.** **Keep speed noise 0.05 and turn noise 0.01 rad** (docs/odometry.md). At 0.01 rad the heading estimate spreads to 0.3 rad in three minutes and 0.95 rad in thirty, the time scale on which Cheung et al. 2012 read the rodent head-direction system as unstable without vision, and the error it produces is what M2b's boundary reset exists to correct; it is also the value G23 G measured the maze against (47 of 480 off-axis runs lost), so that comparison stands. Speed noise 0.05 costs two runs of 480 (G23 G) and its only visible effect here is the clamp's 2% shortfall, which item 2 removes. The alternative is 0.005 rad: half the error (199 against 394 units at 200 m) at the same slope, drift still on the darkness time scale (0.15 rad at three minutes), if the owner wants the straight-walk interval inside the band as well.
2. **The forward clamp.** The −0.0198 per unit shortfall is M0b's choice to add the noise before the clamp, not the value 0.05. **Widen the Observation's forward range in M2b** (to ±2 units, or to 1 + 4σ) when the wall-contact reset is built, so that a full-thrust tick's estimate is zero-mean; the research baselines are regenerated then anyway. Lowering the noise would hide the defect, not fix it.
3. **Which walk the slope acceptance is read on.** The plan's 0.5–1.5 band brackets the two growth laws on a walk with turns; the straight walk is what the research profile does in a barren world with nothing in view, not a property of the odometry. **Read the acceptance on the turning-walk control** (every interval inside) and record both walks whenever the odometry is re-characterised, as docs/odometry.md does; every protocol from M2a on has walls or cues and so a turning walk without the control's `forward_bias`.
4. **λ for M2b.** The chain cannot choose: λ 0.9 reaches 1e-2 in 38 passes against 92 at λ 0 at 0.5 cell, both trace kinds converge, and no width separates them beyond the cap's finite-budget residual. **Defer** to M2b, where the place population and the trial structure give traces something to span; λ = 0 (TD(0), the tabular baseline's rule) is the default until then.

### D. Residuals carried into M2a and M2b
- Replay events have no trigger without microsleep, so the research profile produces none (docs/profiles.md); M2a adds the first rule of §2 and the protocol-driven triggers, and the event's `start_dist_m` waits for the place population.
- The offline consolidation sweep (`ValueMemory.consolidate`: the console maze's sleep after the visible trial, `ui/scenarios.py`, and `experiments.memory_navigation`'s sleep phase) is still a replay without an event: a headless `console_memory_maze` run never microsleeps under its pacing (0 replay ticks in 1,500 at seed 1337) and writes no `replay_events.jsonl` although its status says "Replay after training: on" and its `events.jsonl` logs "Sleep: replayed a n-step trajectory 60×". The replay that G16, G21 and G23's maze results rest on is therefore outside the event object. M2a's rule and triggers replace that sweep, or wrap it as an event with trigger `trial_end` and rule `exhaustive_reverse`.
- The linear learner is not wired into the engine: `ValueMemory` is still what the tick and the replay backups call, and it does not implement `ValueFunction` yet. M2b adapts it, with `TabularTD0` over the 0.5-unit bins as the ablation baseline.
- G24 B5 planned the temperature sweep for M1; it was not done: the softmax temperature 0.1 is uncharacterised beyond G23 G (0.05 alone costs 41 of 480 off-axis maze runs; 0.1 was not run) and has no research-profile assertion to be tuned against until M2a's track; docs/odometry.md says so.
- `tests/determinism/test_numpy_rules.py::test_importing_the_engine_does_not_import_numpy` pins that `core.engine` loads without numpy; when the learner enters the engine in M2b that claim becomes "the thread pin is in force before numpy loads", which the conftest and the manifest's `numpy_loaded_before_pin` already cover, and the test is rewritten then.
- Unchanged from G24 D: 28.9% of research open-field ticks clamped at a wall until M2b's reset; the heading estimate's random walk unreset; the macOS tolerance gate unrun (nothing pushed); the novelty bit in action selection in both profiles.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 483 passed (423 at the verification fixes after `v1.1-base`: +29 value learners, +16 replay events, +10 odometry, +1 probe characterisation, +4 vrest), about 100 s.
- Legacy identity: `git diff eea946f -- tests/engine/steering_legacy_hashes.json tests/determinism/baseline_hashes.json` is empty; `tests/determinism/` is byte-identical to `v1.1-base` (no baseline was regenerated in M1, because no behaviour moved in either profile); `test_the_event_log_leaves_the_legacy_trace_hash_unchanged` (a copy of the determinism gate, removed in section F), the harness's pinned `--json` outputs and the 20 probe characterisation tests are green.
- Package version 1.2.0 in `pyproject.toml` and `CITATION.cff` (G24 B6: version = milestone tag).
- Tag `v1.2-value` at this entry's commit, closing Milestone 1.

**Impact:** this entry; docs/research_plan.md (status, §4 M1 row, §5 items 8 and 14, §7, §9 item 11, §10); docs/references.bib (section I, two entries); README and run_instructions.md (`replay_events.jsonl` and `n_replay_events` in the run-directory lists; README's research-profile paragraph); `brain/systems/value_memory.py` (one comment, `oracle_homing`); `pyproject.toml` and `CITATION.cff` (1.2.0); G24 A14 (the bibliography count, in brackets). No engine, harness, console, test or baseline file changed.

### F. Verification fixes (same day, the commit after `v1.2-value`)
A four-lens verification of M1 (value-learner maths, replay events, odometry reproduction, code and docs) returned 20 findings (1 blocker, 8 majors, 11 minors) and 19 nits; the commit "M1: verification fixes" applies the blocker, every major and every minor and lists each. What changed in substance, with the measured facts:
- **The temperature was never characterised.** docs/profiles.md and README said the research softmax temperature was a "placeholder value, characterised in M1"; only the odometry was (A3, D). Both now say so, the odometry rows point at docs/odometry.md, and D records that G24 B5's sweep was planned for M1 and not done. README and docs/profiles.md also said "every replay is an event object"; only microsleep replay is (A4), and D now records the offline consolidation sweep (`ValueMemory.consolidate`) as a replay without an event, measured: `console_memory_maze` at 1,500 ticks, 0 replay ticks, no `replay_events.jsonl`, status "Replay after training: on".
- **The flag-off ATP residual was misattributed.** docs/odometry.md, the script docstring and the test said the step error with the gate off "is the speed noise, which cannot" track ATP. Measured with the characterisation script extended (three ATP columns, `r_step_error_after_transient`, `r_step_error_off_wall`, `body_walk`, plus `n_wall_moving`, `wall_step_error_mean` and the noise values, and one zero-noise control row; `docs/data/m1/odometry_atp.csv` regenerated, the other three tables byte-identical): a zero-noise run gives the same r (−0.064 on all moving ticks, −0.192 from tick 200) from 14 wall-contact TURN ticks (ticks 276 and 311–323) whose sliding step the heading projection under-reads by a third; the speed noise's own contribution is \|r\| ≤ 0.04; from tick 200 on the flag-off step error is −0.12 to −0.16 against +0.83 with the gate. The acceptance stands on all moving ticks; the residual is for M2b's wall reset. The same table shows the eight research-noise runs share one body walk and one ATP series (the legacy body does not read the odometry draw: one `body_walk` digest for all eight rows; exact heading odometry flips one action at tick 1,638), so A3's "seeds 1–4" are four odometry realisations, not four behavioural replicates; the test now asserts the body digests equal and a new test pins the control.
- **Two learner properties were untested.** A `TabularTD0.update` that ignored the `terminal` flag passed every test (fresh weights read 0 at the goal anyway), and the TD(λ) trace forms were pinned only by the self-generated CSV (every trace variant converges to γ^d on the chain). `test_update_returns_the_td_error_and_a_terminal_bootstraps_on_zero` now pre-sets a value of 5 at the goal and asserts a terminal update returns 1.0 (not 5.5) and a non-terminal one into the same place 5.5, for both learners; a three-update hand computation at width 0.125 cell (lr 0.2, γ 0.9, λ 0.5) asserts V(9) = 0.1305 with accumulating traces and 0.09 with replacing (a λ-only decay would give 0.15 and 0.1; replacing computed as accumulating 0.1305 for both). The constructors now refuse a non-positive or non-finite learning rate, a discount outside [0, 1] and a non-finite width, bin size or centre (a divergent learning rate is left to the caller, said in the docstring).
- **Docs of the learners corrected**: the convex-combination bound holds wherever a feature is nonzero, and more than 38.6 widths from the nearest centre (19.3 units at a width of 0.5) every feature underflows and V reads 0 (outside [min w, max w]); the wide-width rows converge at the slowest eigenvalue of the per-pass map, 0.898 per pass at 0.5 cell, 0.99983 at 1.0 (an e-fold every 5,960 passes) and 1 − 6e-12 for the slowest mode at 2.0 cells, so the 2.0-cell row (about 3e-4 after a million passes) reaches the floor at no practical budget, where the doc said "still falling".
- **Replay-event plumbing**: `experiments.runner`'s writer removes a previous run's `replay_events.jsonl` from a reused directory (a legacy run then a research run of the same protocol and seed left a 7-line file beside `n_replay_events: 0`); the console recording writes only the kept events that end inside the recorded ticks (the 50,000-tick history and the 4,096-event keep were not tied) and the summary carries `n_replay_events` (the lines written) and `n_replay_events_total` (a running count); both writers go through `write_replay_events` in `brain/systems/replay_events.py`; the copy of the determinism gate that `tests/engine/test_replay_events.py` carried is removed (it could not fail without the gate failing) and the module docstring cites the gate.
- **One dotted config setter**: `EngineConfig.set_field` / `get_field` in `core/config.py` (an unknown field is an `AttributeError`, the alias property works); the harness's `set_field`, `g23_remeasure.apply_overrides` and the console's live parameters call it, and the replay-events test no longer imports the harness for it.
- **Docs**: the probe docstring's drifted numbers (`odometry_growth.py`: 1.70 at 4 seeds, \|r\| < 0.08, ±0.08); docs/odometry.md's walk figures given per run (straight 2,002–2,007 ticks, net displacement 1,728–1,995; turning 3,206–3,355 ticks, 82–854) beside the condition means it had quoted as ranges; the plan's §6 novelty-bit row no longer assigns the decoupling to M1 (not done; §9 item 12 asks the owner which milestone); A3's "11 tests" is 10 plus one in the probe characterisation and E's sum is corrected; run_instructions.md states the console recording's keeps.

Measured after the fixes: `python3 -m pytest -q` 487 passed (483 − 1 + 5), about 100 s; `git diff eea946f -- tests/engine/steering_legacy_hashes.json tests/determinism/baseline_hashes.json` empty; `pytest -m "not exact_hash"` collects 461 of 487; the two determinism baseline sets unchanged (no behaviour moved in either profile: every code change is validation, bookkeeping or plumbing). Declined: no finding; the 19 nits were not applied (information only). The tag `v1.2-value` stays at section E's commit.

**Impact:** this entry (A3, A4, B, D, E, this section); docs/profiles.md, README, run_instructions.md, docs/research_plan.md (§6, §9 item 12), docs/value_learners.md, docs/odometry.md; `brain/systems/value_learners.py`, `brain/systems/replay_events.py`, `core/config.py`, `experiments/runner.py`, `experiments/steering_sensitivity.py`, `experiments/g23_remeasure.py`, `experiments/odometry_characterisation.py`, `ui/sim_session.py`, `tools/probes/odometry_growth.py`; `docs/data/m1/odometry_atp.csv` and `odometry_meta.json`; the four test files named above.

## G26 — Milestone 2a, first subset: the macOS gate repaired, two research confounds removed, four replay rules on the tabular track
**Date:** 2026-10-24  
**Why:** The first macOS CI run of the branch (commit `ab262e0`, 2026-10-03) failed four tests that the Linux suite passed: the cross-platform tolerance gate compared `obs_checksum`, a SHA-256 of the Observation's float `repr`s, as an exact string, so last-bit float differences the 1e-9 tolerance accepts (worst 9e-16) failed it on 29 legacy and 15 research ticks of 200; a subprocess test demanded "1 passed" from a test that legitimately skips where numpy is not linked against OpenBLAS; and a manifest test assumed `threadpoolctl` always finds a BLAS, which it does not for Apple's Accelerate. Two confounds sat in the research profile that the first replay experiment should not carry: the odometry speed error was applied before a forward clamp at 1.0, so a full-speed step's estimate averaged 0.980 rather than 1.0 (G25 C2 had recommended the widening for M2b), and the checksum "novelty" bit still entered action selection (plan §9 item 12 recommended decoupling it at M2a). With those three in order, the smallest defensible step toward the plan's M2a row is a bounded replay comparison on a tabular linear track: four of the nine rules, fixed budget, 30 paired seeds, every number with an interval. All of it on the branch `m2a-replay-linear-track` from `ab262e0`; nothing merged.

### A. What landed
1. **The cross-platform gate reads the numbers behind the hash** (`core/determinism.py`: `observation_record`, `generate_profile_trace_with_observations`, `write_observation_trace`, `reference_observations_path`; `tools/compare_traces.py`: `--observations`, `HASH_DERIVED_FIELDS = ("obs_checksum",)`, `Comparison.tolerated_hashes`; `tests/determinism/reference_observations_{legacy,research}.jsonl`, about 60 KB each, one record per tick from the same engine run as the reference trace: the tick, forward and turn deltas, pain, the two whisker bits and every ray's distance, label and angle; `tools/update_determinism_baseline.py` writes the sidecar with the research set, the legacy one was written once from the function form and falls under the legacy rule from now on; docs/determinism.md). Given both sidecars the tool compares every tick's two observation records as it compares the trace (floats within the tolerance, labels and bits exactly, a disagreement reported under `observation.`) and tolerates a differing `obs_checksum` only on a tick whose records agree, counting and reporting it; without sidecars, or with disagreeing ones, a differing checksum is the mismatch it was. `wm_novelty` stays exact (a disagreement about whether the observation changed is a real one). Same-platform bit identity is untouched: the hash baselines are the same files, and a new `exact_hash` test pins the current observations to the sidecar bit for bit. `tests/determinism/test_cross_platform_tolerance.py` grew from 5 to 11 tests.
2. **BLAS detection is explicit** (`core/determinism.py`: `blas_runtime_status` ∈ {`detected`, `none_detected`, `unavailable`}, `blas_threads_verified`; `metrics/manifest.py` platform block carries both). A manifest from a platform where `threadpoolctl` knows no BLAS says `none_detected` and `blas_threads_verified: false`, never a confirmed pin. The suite's thread-pin test is split: the variables and the import order on every platform (the subprocess test targets this one and now also refuses "skipped"), the live OpenBLAS count only where OpenBLAS is loaded; the manifest test accepts an empty runtime list when the status says so. `test_numpy_rules.py` 8 → 10 tests, `test_manifest.py` 12 → 13.
3. **The forward clamp** (`SensorConfig.forward_delta_limit`, 1.0 by default and in `legacy()`, 2.0 in `research()`; `Observation.validate(forward_limit=1.0)`; `core/sensors.py` clamps to the limit after the noise). Measured (`tests/engine/test_research_confounds.py`, straight walk, 3,000 ticks, seed 1337): the full-thrust estimate averages 0.998 ± 0.05 with 48% of readings above 1.0 under the research limit, 0.980 with none above 1.0 under the legacy limit on the same draws, and the two agree reading for reading wherever the legacy one was not clamped; the body walks the same path under both limits (nothing in a barren box feeds the estimate back). The odometry re-characterisation (docs/odometry.md, the M2a section; `docs/data/m2a/odometry/`, the script's default output now; the M1 tables stay as the record of the clamped contract): speed-only straight-walk slope 0.480 [0.356, 0.615] (was 0.987 [0.970, 1.003]), error at 200 m 1.7 ± 1.3 units (was 38.4 ± 1.9), along-track bias +0.0003 per unit (was −0.0198); the heading rows within a hundredth of M1's; `both` 1.422 [1.286, 1.548] straight and 0.921 [0.813, 1.092] turning. The speed-only turning row reads 0.393 [0.294, 0.485], below the plan's 0.5–1.5 band: the √distance law of a zero-mean error with sampling error on a walk with 0.3-unit turn steps and rests (per-seed slopes −0.38 to 0.98), not a defect. The ATP table is a legacy measurement and is byte-identical to M1's.
4. **The novelty bit decoupled** (`BasalGangliaConfig.novelty_turn_gain = 0.3`, the literal `_channel_scores` carried on each TURN channel, now a field; `research()` sets `novelty_gain` and `novelty_turn_gain` to 0). Measured: under the research gains the channel scores are identical with the bit at 0 and at 1 on open, wall, target and pain observations and under low dopamine; under legacy the bit adds exactly 0.2 to FORWARD and 0.3 to each TURN; the bit is still logged (`wm_novelty` reads 0 and 1 in a deterministic research run, 1 on every tick with odometry noise on, as under legacy noise), ACh still equals it and NE still carries half of it; re-scoring every tick of a research run with the bit flipped changes no action. In an empty arena the TURN channels drop from 0.3 to 0 against FORWARD's 0.8, so a TURN is an exp(−8) draw per channel instead of a 1-in-500 one: the research open-field walk at seed 1337 over 3,000 ticks now first drifts past 0.5 units at tick 20 (was 37), ends 11.8 units off (9.2), is clamped at a wall on 1,230 ticks (753), mean step 0.52 (0.57), 28 REST ticks (3); the turning-walk control of the characterisation is 60% / 27% / 13% FORWARD / TURN / REST (was 46 / 51 / 2). The profile diff gains three rows (`sensors.forward_delta_limit`, `basal_ganglia.novelty_gain`, `basal_ganglia.novelty_turn_gain`; docs/profiles.md).
5. **The research baselines regenerated once** (`python3 tools/update_determinism_baseline.py --profile research --i-know-what-im-doing`, after both confounds): the full and behaviour hashes and the reference trace moved, the physics hash did not (no microsleep, the lattice on its own stream), and the sidecar was written with them. The legacy set is byte-identical to `ab262e0` (section E).
6. **Replay rules outside the engine** (`brain/systems/replay_rules.py`; constants `TRIGGER_REWARD`, `RULE_UNIFORM`, `RULE_PRIORITISED_TD`, `RULE_NONE`, `DIRECTION_NEITHER` in `replay_events.py`; `ValueFunction.td_error` on both learners, `update` now being `td_error` plus the write; `tests/brain/test_replay_rules.py`, 7 tests). A `TransitionMemory` of `StoredTransition`s (each with its own successor, terminal flag, episode and index, so no backup can link two episodes); three rules behind one protocol, `UniformReplay`, `ReverseTrajectoryReplay` (the just-finished episode newest first, cycling, no draw) and `PrioritisedTDReplay` (∝ |TD error| + ε, the error recomputed under the current values before every draw: prioritised sweeping with proportional sampling, no stale priorities); `replay()` runs exactly `n_backups` backups whatever the rule, from the one stream handed in, and returns a `ReplayEvent` (trigger `reward`, the cells in backup order, the direction by the plan's position–time slope sign against the travel direction) with the transitions and TD errors behind it and the signed correlation `sequence_r`. Reuses `TabularTD0`, `softmax_sample`, `core.rng` and `ReplayEvent`; wiring the rules into the engine's tick is M3's.
7. **The track experiment** (`experiments/linear_track_replay.py`; docs/m2a_linear_track.md, the specification written before the run; `docs/data/m2a/track/`, 1.1 MB: `track_laps.csv`, `track_per_seed.csv`, `track_summary.csv`, `track_learning_curve.csv`, `track_effects.csv`, `track_replay_events.jsonl.gz`, `track_manifest.json`; `tests/experiments/test_linear_track_replay.py`, 11 tests). The specification: a 40-cell track (2.0 m), tabular state (cell, heading, goal end) handed to `TabularTD0` as a position, 160 states, the true cell (oracle); FORWARD and TURN; a lap from one end to the other with a terminal consume transition carrying the reward 1.0, the goal flipping after a rewarded lap, a cap of 2,000 steps, 40 laps; TD(0) at learning rate 0.2 and discount 0.95; a softmax at temperature 0.1 over FORWARD 0.1386 + 10 V(s′) and TURN 10 V(s′) (an untrained turn probability of 0.2, a value difference of 0.01 one temperature unit); replay at every rewarded lap end, exactly 20 backups per trigger in the three replay conditions, a memory of 2,000 transitions, streams `track_action` and `replay`; seeds 1–30; the primary outcome the total steps over the 40 laps, paired by seed. A pilot on the `none` condition at seeds 1–3 against three criteria stated first (untrained lap ≥ 5× the optimal 39 steps; learning visible within 40 laps; no caps) was met by the a-priori values, so nothing was tuned; a 3-seed mechanics check of all four conditions followed; the 30-seed run is the only one reported.

Suite: 522 tests (487 at `ab262e0`), 45 s on the 4-core development box; `-m "not exact_hash"` collects 494 (28 deselected; the two sidecar bit-identity tests join the marker).

### B. The result (docs/m2a_linear_track.md; `docs/data/m2a/track/track_effects.csv`)
Total steps over 40 laps, n = 30 seeds, means with BCa 95% intervals: `none` 14,490 [13,980, 15,160]; `uniform` 14,260 [13,720, 14,900]; `reverse_trajectory` 11,660 [11,260, 12,090]; `prioritised_td` 10,470 [10,040, 10,840]. Paired by seed: uniform − none −224 [−820, +112], faster on 11 of 30 seeds with 8 exact ties, Cliff's δ −0.03 [−0.32, +0.26] (a null, the plan's "random" floor reading as one); reverse − none −2,825 [−3,497, −2,147], faster on 27 of 30, δ −0.88 [−0.95, −0.71]; prioritised − none −4,016 [−4,813, −3,310], faster on 30 of 30, δ −1.00 [−1.00, −0.95]; prioritised − reverse −1,191 [−1,626, −802], faster on 25 of 30, δ −0.50 [−0.71, −0.22]. Over the last ten laps the differences against `none` are −113 [−430, +90], −1,024 [−1,347, −706] and −1,413 [−1,734, −1,059]. Every replay condition made 20 backups per rewarded lap, 800 per seed (799.3 for uniform: seed 22 capped lap 8 under `none` and `uniform` alike, their walks being identical until uniform's first effective backup), 5.7–7.7% of the online updates (14,530 / 14,300 / 11,700 / 10,510 per seed). Content: reverse replay is reverse on every event (sequence_r −0.976; turns and cycling keep it from −1), all of it from the lap just run, 8.9 cells from the goal on average; uniform and prioritised are at chance on the slope-sign label (0.48 and 0.51 reverse; mean |r| 0.19, what 20 scattered states give), 21% and 16% from the lap just run, 20.4 and 18.2 cells from the goal, 73% and 60% more than 0.5 m from it; what separates them is the learning signal per backup, a mean |TD error| of 0.0029 for uniform against 0.097 for prioritised. Guards: 30 distinct lap-length vectors in every condition; lap 1 identical across the four conditions at every seed (351 steps on average, median 300); 2 capped laps in 4,800. The no-replay curve is far from converged after 40 laps (mean lap 341, optimum 39), so the comparison is of learning speed over a fixed budget, not of asymptotes.

### C. Decisions this surfaces (recommended default in bold)
1. **The ranking is the textbook one and is not the RQ1 test.** Prioritised sweeping and reverse replay propagate the reward's TD error back along the lap in one pause; uniform replay spends its budget on transitions at their fixed point. The result is the instrument working with intervals, as the plan asked of the first pass, and nothing about rodents. **Report it as such** (docs/m2a_linear_track.md does) and keep the M2a row open: the other five rules, thresholded mode, the reward-change schedule, the pre-run window and the plan's event definition (≥ 4 distinct states over ≥ 0.3 m) are what RQ1 (a)–(d) need.
2. **Direction by slope sign is a coin for sampling rules.** On 20 scattered states the sign of the position–time slope is at chance, so the plan's label distinguishes only sequence rules. **Keep the label (it is the plan's definition) and report `sequence_r` and the content measures beside it**; when the event definition arrives, compute direction on the plan's sequences, not on raw backup lists.
3. **The pilot's three criteria as the protocol's calibration rule.** The policy's prior and gain were fixed by criteria stated before the pilot and checked on the no-replay arm alone. **Keep that rule for every later protocol**: calibration on the control arm against written criteria, the replay arms untouched until the evaluation.
4. **The speed-only turning slope below the band.** 0.393 [0.294, 0.485] against 0.5–1.5: the zero-mean law with sampling error on a walk that turns and rests. **Read the band as a check on the heading term and on `both`** (both inside on the turning walk), not on the speed term alone, whose law sits at the band's lower edge by construction; or widen the band's lower edge to 0.25 when the plan is next revised.
5. **Version and tag.** The M2a row is not closed, so no `v1.3-track-replay` tag and `pyproject.toml` / `CITATION.cff` stay at 1.2.0 (G24 B6: version = milestone tag). **Tag when the row closes.**

### D. Residuals carried forward
- **The macOS job on this branch** (run 40131496324, commit 106d1e3, `macos-latest`, arm64): the full-suite step `-m "not exact_hash"` passed, 493 passed, 1 skipped (the OpenBLAS live-count test, where numpy is not linked against OpenBLAS: `blas_runtime_status` reads `none_detected` there and the manifest claims no verified pin), 28 deselected, against 4 failed at `ab262e0`; both profiles' tolerance comparisons passed with the sidecars, so the checksum differences the first run failed on are now accounted for by observations that agree within 1e-9. The separate tolerance-gate step failed on that run because it ran the file without the marker filter and so included the two same-platform sidecar bit-identity tests, which differ across platforms by design; the step now carries `-m "not exact_hash"` like the one before it (95d474d), and on that commit both CI jobs are green (run 40131750580: Ubuntu 2m10s, macOS 1m23s), the first green macOS job on any branch of this repository. The local suite is Linux (Python 3.11.15, numpy 2.4.6, OpenBLAS 0.3.31 on the SkylakeX kernel); macOS is validated only to the extent CI reports it.
- The replay rules run outside the engine; the engine's own replay is still microsleep-triggered, and the research profile's engine produces no replay events. M3 wires `replay()` into the tick and the console's arena.
- Oracle state, four rules of nine, fixed budget, no reward change, no event-definition metrics (section C1). RQ1 (a)–(d) untested.
- One parameter set for the track; the ranking's robustness to learning rate, discount, temperature, prior and gain is untested.
- The research open-field walk spends 41% of its ticks clamped at a wall (28.9% at G24, 25% at seed 1337 before the novelty bit left the TURN channels): M2b's wall-contact reset and M4a's walls and body radius are what change this.
- The RMSE of V against V* over all 160 states is dominated by rarely visited states and moves almost identically across seeds (its paired intervals collapsed to the estimate); a visit-weighted error would be the sensitive measure.
- Unchanged from G25 D: the softmax temperature uncharacterised; the offline consolidation sweep a replay without an event; the linear learner not wired into the engine; the heading estimate's random walk unreset.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 522 passed, 45 s (487 at `ab262e0`: +6 cross-platform gate, +2 numpy rules, +1 manifest, +8 research confounds, +7 replay rules, +11 linear track).
- Legacy identity: `git diff ab262e0 -- tests/engine/steering_legacy_hashes.json tests/determinism/baseline_hashes.json tests/determinism/baseline_behaviour_legacy.json tests/determinism/baseline_physics_legacy.json tests/determinism/baseline_meta.json tests/determinism/reference_trace_legacy.jsonl` is empty; `tools/update_determinism_baseline.py --profile legacy --out-dir /tmp/x` reproduces the five committed legacy files and the new sidecar byte for byte; `tests/determinism/baseline_physics_research.json` is unchanged.
- The research set regenerated once (section A5); `tests/determinism/test_cross_platform_tolerance.py` passes with 0 tolerated hashes on this machine and 200 observation ticks compared per profile.
- `python3 -m experiments.linear_track_replay --workers 4` writes `docs/data/m2a/track/` in 7 s; a second run with `--workers 1` gives byte-identical tables (the manifest's wall-clock aside). `python3 -m experiments.odometry_characterisation --workers 4` writes `docs/data/m2a/odometry/` in 25 s.
- No tag; version 1.2.0 (section C5).

**Impact:** this entry; docs/m2a_linear_track.md (new); docs/determinism.md, docs/profiles.md, docs/odometry.md, docs/value_learners.md, docs/research_plan.md (status, §4 M2a row, §6, §9 items 11–12, §10), README, run_instructions.md, tools/probes/README.md (the `odometry_growth` block re-recorded); `brain/contracts.py`, `brain/systems/basal_ganglia.py`, `brain/systems/replay_events.py`, `brain/systems/replay_rules.py` (new), `brain/systems/value_learners.py`, `core/config.py`, `core/determinism.py`, `core/sensors.py`, `metrics/manifest.py`, `metrics/schema.py` (a comment), `tools/compare_traces.py`, `tools/update_determinism_baseline.py`, `tools/probes/odometry_growth.py`, `experiments/odometry_characterisation.py`, `experiments/linear_track_replay.py` (new); `tests/determinism/` (the research set, the two sidecars, four test files), `tests/engine/test_profiles.py`, `tests/engine/test_seeds_as_samples.py`, `tests/engine/test_research_confounds.py` (new), `tests/brain/test_replay_rules.py` (new), `tests/experiments/test_linear_track_replay.py` (new), `tests/experiments/test_odometry_characterisation.py`, `tests/metrics/test_manifest.py`; `docs/data/m2a/` (new: `track/`, `odometry/`). No console, tournament or legacy baseline file changed.

## G27 — M2a remainder, step 1: replay events by the plan's definition, a visit-weighted value error, a sensitivity sweep
**Date:** 2026-10-24  
**Why:** G26 left three loose ends on the track result: its replay direction was the sign of a slope over 20 scattered backups, a coin for the two sampling rules; its value error was an RMSE over all 160 states, dominated by states the policy never visits, whose paired intervals collapsed; and its ranking rested on one parameter set, fixed before the run and never tested around. The plan's own event definition (§2: a sampled sequence of ≥ 4 distinct states spanning ≥ 0.3 m, with a start state, a direction and a trigger; a remote event starts > 0.5 m from the agent; the rate is events per stop) is what step 2's reward-schedule test needs, so it is built first, applied to the committed events without re-running them. On the branch `m2a-replay-metrics` from `a8e0b47` (the development branch after the M2a merge).

### A. What landed
1. **`analysis/replay_metrics.py`** (`tests/analysis/test_replay_metrics.py`, 7 tests; `python3 -m analysis.replay_metrics docs/data/m2a/track/track_replay_events.jsonl.gz`, 0.3 s; tables `track_sequence_events.csv`, `track_sequence_metrics.csv`, `track_sequence_rate_by_lap.csv` in `docs/data/m2a/track/`). Consecutive backups link when their start cells are the same or adjacent (`NEIGHBOUR_CELLS` 1; a TURN keeps the cell, heading and goal rows are not distinguished: a sequence is spatial); a maximal linked run is a segment; a segment with ≥ `MIN_DISTINCT_CELLS` (4) distinct cells spanning ≥ `MIN_SPAN_CELLS` (6 = 0.3 m) is an event, with `brain.systems.replay_rules.sequence_direction` over its own cells against the lap's travel, its start cell, and `remote` when the start is > `REMOTE_CELLS` (10 = 0.5 m) from the agent's cell at the pause (the goal cell just reached). One row per pause (`per_stop_rows`), pooled per seed (`per_seed_rows`: events per stop, stops with an event, direction and remote shares among the seed's events, mean span and length), BCa intervals over seeds through `analysis.stats` with every (condition, metric) row present and `n` 0 where a condition made no event, and events per stop by lap. `--neighbour`, `--min-distinct`, `--min-span`, `--remote-cells` expose the definition.
2. **Measured on the committed 3,599 replays.** `reverse_trajectory`: an event at 1,199 of 1,200 pauses (0.999 [0.997, 1.000] per stop), all reverse, mean span 16.9 cells [16.8, 17.0], mean |r| 0.977, none remote (every sweep starts at the goal); the one pause without an event is a lap whose last 20 steps wandered within five cells. `uniform` and `prioritised_td`: **no event at any pause** under the plan's definition; their backups jump between transitions near the two ends and never chain through four adjacent cells, so their direction is not a quantity (G26's 0.48 and 0.51 "reverse" shares were the coin). Relaxing the extraction on the same events: cells two apart linked, uniform 0.0025 and prioritised 0.0008 events per stop; two apart over a span of four, 0.005 and 0.029; three apart, three distinct cells over four, 0.13 and 0.30 (reverse share 0.46, remote 0.55), still an order of magnitude below the sequence rule.
3. **`value_rmse_visited`** (`experiments/linear_track_replay.py`: `TrackAgent.visits`, one count per occupancy, the lap start and every arrival; a new last column of `track_laps.csv`, the metric `final_value_rmse_visited` in the per-seed, summary and effects tables). Final values: `none` 0.289 [0.286, 0.293], `uniform` 0.287 [0.284, 0.290], `reverse_trajectory` 0.249 [0.246, 0.251], `prioritised_td` 0.226 [0.224, 0.229]; paired against `none`: −0.0027 [−0.0039, −0.0014] (uniform lower on 28 of 30 seeds), −0.040 [−0.045, −0.037], −0.063 [−0.066, −0.059]; prioritised against reverse −0.022 [−0.025, −0.020]. The tables were regenerated for the column; every pre-existing row and column is byte-identical, the event file and the learning curve too.
4. **`experiments/linear_track_sensitivity.py`** (`tests/experiments/test_linear_track_sensitivity.py`, 2 tests; `python3 -m experiments.linear_track_sensitivity --workers 4`, 79 s; `sensitivity_effects.csv`, `sensitivity_summary.csv`, `sensitivity_manifest.json`). Eleven variants, one parameter each from the fixed set: learning rate 0.1 / 0.5, discount 0.9 / 0.98, temperature 0.05 / 0.2 with the prior rescaled to hold the untrained turn probability at 0.2, untrained turn probability 0.1 / 0.3, value gain 5 / 20; all four conditions at seeds 1–30 per variant, the paired comparisons of `analyse` on total steps. Both sequence rules beat `none` with intervals excluding zero in 11 of 11 variants; prioritised beats reverse in 10 of 11 (at learning rate 0.5 reverse wins, 6,774 against 7,003, +229 [+9, +496]); uniform is a null in 9 of 11 and a small gain in two (learning rate 0.5, −233 [−398, −73]; turn probability 0.1, −133 [−259, −58]). The temperature and gain axes are one axis (the softmax reads scores / temperature; with the prior rescaled, τ 0.05 at gain 10 is gain 20 at τ 0.1, and τ 0.2 is gain 5), identical to the digit, so the design has nine distinct variants. The turn probability moves the baseline most (8,340 to 23,148 steps; 63 of 4,800 laps capped at 0.3).

Suite: 531 tests (522 at `a8e0b47`), about 50 s on the 4-core development box.

### B. Decisions this surfaces (recommended default in bold)
1. **The event definition's one free choice**, what links two consecutive backups into a sequence, is set to adjacent-or-same cell. **Keep it** (it is the plan's "sequence" read spatially, and the relaxed readings in A2 are reported beside it); revisit only when the plan's decoding emulation (M7 step 0) gives a data-side definition to match.
2. **Direction for sampling rules.** Under the plan's definition it is undefined here, not "chance". **Report it as undefined with the event count**, and never from a slope over unlinked backups; the earlier content measures (share from the lap just run, distance from the goal, |TD error| per backup) remain the informative description of what those rules replay.
3. **The visit-weighted error replaces the all-states RMSE as the value-learning measure** in the report's tables (**yes**); the all-states one stays in the data for continuity.
4. **The ranking's robustness statement.** Prioritised over reverse holds except at a large learning rate, where one reverse sweep already carries the error the length of the lap tail; the sequence rules over no replay holds everywhere tried. **State both**, and run step 2's protocol at the fixed set only, with this sweep as its context.

### C. Residuals carried forward
- The plan's reward-window and pre-run-window rates, and the rate's fall with familiarity in thresholded mode, need step 2's pre-run pause, reward schedule and thresholded budget; here every pause is a reward pause in fixed-budget mode, and the per-lap rate of the sequence rule is flat at 1.
- **Step 2 also runs a dose-response check** (owner's addition, 2026-10-24): the fixed-budget comparison at 5, 10, 20 and 40 backups per pause, same seeds, so that the causal reading of A3 and A4 (the effect tracks error-carrying backups) is tested directly: if replay does the work, each rule's effect against `none` should grow with the dose and uniform's should stay at its floor. Each level is a 7 s run; preregistered with the rest of step 2.
- Uniform and prioritised replay produce no sequence events in this protocol; whether a sampling rule can under a reward change (where the error concentrates at one end) is step 2's question, not assumed.
- The sensitivity sweep varies one parameter at a time at 40 laps; interactions and longer runs are untested.
- Unchanged from G26 D: oracle state, four rules of nine, the rules outside the engine tick, one platform validated locally (CI covers macOS).

### D. Acceptance, measured at this commit
- `python3 -m pytest -q`: 531 passed (+7 replay metrics, +2 sensitivity).
- The fixed evaluation re-run with the new column: `track_laps.csv`'s 21 pre-existing columns, `track_learning_curve.csv`, `track_replay_events.jsonl.gz` and every pre-existing row of the per-seed, summary and effects tables byte-identical to `106d1e3`'s; the sensitivity sweep's `base` row reproduces the fixed evaluation's effects to the digit.
- Legacy and research determinism baselines untouched (no engine change).
- No tag; version 1.2.0 (the M2a row stays open).

**Impact:** this entry; docs/m2a_linear_track.md (a "step 1" section, the file list), docs/research_plan.md (status), README, run_instructions.md; `analysis/replay_metrics.py` (new), `experiments/linear_track_sensitivity.py` (new), `experiments/linear_track_replay.py` (visit counts, the column and metric); `tests/analysis/test_replay_metrics.py` (new), `tests/experiments/test_linear_track_sensitivity.py` (new), `tests/experiments/test_linear_track_replay.py`; `docs/data/m2a/track/` (the track tables regenerated with the column, `track_sequence_*.csv` and `sensitivity_*` new). No engine, console or baseline file changed.

## G28 — M2a remainder, step 2: the RQ1 protocol on the floors, thresholded mode, a dose-response
**Date:** 2026-10-25  
**Why:** The plan's RQ1 needs the Ambrose reward schedule, a pre-run window beside the reward window and the thresholded budget mode (§2, §3), none of which the track had; G26 and G27 left the question whether the replay effect is the error-carrying backups to a dose-response check (owner's addition, G27 C). All of it was preregistered first (`docs/prereg/rq1_track_tabular.md`, with per-rule predictions of which RQ1 bounds the three floors would fail), then built and run. On the branch `m2a-track-rq1` from `9f15f61` (step 1, unmerged).

### A. What landed
1. **The protocol as configuration** (`experiments/linear_track_replay.py`: `TrackConfig.reward_blocks`, `pre_run_pause`, `budget_mode`, `threshold`, `backup_cap`, with `blocks()` and `block_of()`; `LinearTrack.set_rewards`; `LapRecord` gains the block, its rewards and the pre-run pause's backups, event, direction and correlation; every event row carries `agent_cell` and `block`). The defaults are the fixed evaluation's protocol, and `run_seed` reproduces the committed per-lap rows to the digit at every condition.
2. **Thresholded replay** (`brain/systems/replay_rules.py`: `ReplayRule.priority`, `replay_thresholded`; `TRIGGER_PRE_RUN` in `replay_events.py`). Priorities, as preregistered: reverse-trajectory the |TD error| of the next transition of its one-pass sweep, prioritised the largest in memory, uniform the mean in memory; `replay_thresholded` backs up while the priority exceeds θ, at most `cap` times, and returns no event when the first priority is already below θ. `tests/brain/test_replay_rules.py` 7 → 9, `tests/experiments/test_linear_track_replay.py` 11 → 14.
3. **Direction against the replayed lap** (`analysis/replay_metrics.py`: `goal_sign_of_row`, `segment_travel_sign`; `agent_cell_for` reads the record's cell). A replayed segment is read against the travel direction of the lap its states belong to (their goal row), the majority row for a mixed segment, so a replay is forward when it runs the way the body ran on that lap whatever lap the body is about to run; the step-1 tables are unchanged by it (every state of the fixed evaluation's reverse sweeps belongs to the lap just run).
4. **The runners** (`experiments/linear_track_rq1.py`, `tests/experiments/test_linear_track_rq1.py`, 5 tests covering the dose script too; `experiments/linear_track_dose_response.py`). The RQ1 runner builds the per-pause table (`rq1_pauses.csv.gz`, one row per pause with backups, events, directions, remote count), pools it per seed, block, end and pause kind (`rq1_seed_blocks.csv`), computes the preregistered tests (a)–(d) with intervals and verdicts (`rq1_tests.csv`), steps per lap by block (`rq1_adaptation.csv`) and a manifest; `--write-events` adds every replay with its cells (6 MB, not committed). The dose script runs the 40-lap stable protocol at 5, 10, 20 and 40 backups per pause.
5. **The pilot, by its rule.** θ = 0.02 gave 1.80 backups per late reward pause (outside the preregistered (2, 50): once V(goal) exceeds 1 − θ the sweep never starts), so θ was set once to the median online |TD error| of laps 11–20 of the no-replay pilot, 0.0035, read as the median over laps of each lap's mean (the recorded quantity), and the prereg records it. Nothing else was touched.

Suite: 541 tests (531 at step 1), about 60 s.

### B. Measured (docs/m2a_linear_track.md, the step 2 section; `docs/data/m2a/rq1/`)
- **Dose-response** (30 seeds, paired against `none`, total steps over 40 laps): prioritised −1,564 / −2,560 / −4,016 / −5,891 at 5 / 10 / 20 / 40 backups per pause, slope −1,444 [−1,628, −1,252] per doubling, negative on 30 of 30 seeds; reverse −1,511 / −2,232 / −2,825 / −2,815, slope −450 [−604, −322], 28 of 30, saturating at 20 because a one-pass sweep's backups beyond the error-carrying tail change nothing; uniform −23 / −7 / −224 / −283, every interval including zero, slope −100 [−219, −13]. The preregistered predictions hold for prioritised, for reverse up to saturation, and for uniform's nulls; uniform's small trend was not predicted.
- **RQ1 on the floors** (30 seeds, four blocks, both pauses): reverse-trajectory passes (a) at reward pauses (reverse share 1.00) and fails (a) at pre-run pauses (forward share 0: it replays the completed lap backward) and (d) (0 remote), as predicted. Thresholded: its rate is a step function of the goal's surprise (the priority is read at the consume first): backups per stop at the east end 8.6 → 18.9 after the ×4 increase (passes), 24.8 → 26.4 after the ×0.25 decrease (**rises: fails "down"**, the unsigned-rule prediction), reverse events per stop 0.70 → 1.00 and 1.00 → 0.80 (the latter meets the "down" criterion, because the surprise of a 0.75 change decays below θ two pauses before the block ends, identical at every seed; the backups row is the honest reading); the west control end fell to 0 backups in blocks 2–4 (not equivalent to baseline: the end went quiet); within block 1 the rate rose lap by lap (slope +0.18 [+0.17, +0.18] backups per lap) and collapsed to 0 at lap 19, so (c) **fails**, the decline the pilot saw at θ = 0.02 (from lap 13) having moved past the block's end at 0.0035. Uniform and prioritised: no sequence event at any pause in either mode (G27 C's open question: no), and in thresholded mode both run to the cap of 100 at (almost) every pause (prioritised from lap 1, uniform from the first reward change), the deviation case the prereg named: their (b) and (c) rows are exploratory and degenerate. Fixed mode across the schedule: the reverse rule made an event at 1,199 of 1,200 reward pauses and 1,184 of 1,200 pre-run pauses, all reverse relative to the replayed lap; no condition showed a transient in steps per lap at a block change (the policy is the same at any reward size).
- Guards: 30 distinct lap-length vectors in every condition and mode. Run times: 258 s (RQ1, both modes; the prioritised rule's fresh priorities over 2,000 memories at up to 200 backups per lap are the cost) and 28 s (dose), 4 workers.

### C. Decisions this surfaces (recommended default in bold)
1. **The thresholded priority of the trajectory rule.** Reading it at the consume first makes the rate a step function of the goal's surprise and blind to error deeper in the lap. **Keep as preregistered for this entry**; for step 3, define the trajectory rule's priority as the largest |TD error| along the stored lap (so a sweep can start where the error is), and preregister it as a change.
2. **θ and the cap for the sampling rules.** A memory-wide maximum or mean exceeds any small θ, so prioritised and uniform run to the cap and their thresholded rate is the cap. **Set θ per rule relative to its own priority's scale in step 3** (or report the sampling rules in fixed mode only), and record it in the prereg.
3. **The familiarity test.** A step-function rate cannot decline inside a block unless the goal's value crosses 1 − θ inside it. **Keep (c) but read it over blocks 1 and 3 together and report the lap at which the rate reaches 0**, beside the slope.
4. **The reward schedule does not change the policy**, only the scale of V, so it cannot show adaptation in steps per lap. **Keep it** (it is Ambrose's manipulation and the rate test needs it), and add a goal-moving block to step 3's protocol if a behavioural adaptation measure is wanted.
5. **Data footprint.** The pause table is 2.8 MB uncompressed and the events 6 MB. **Commit the pause table gzip-compressed and not the events** (reproducible in 258 s with `--write-events`).

### D. Residuals carried forward
- Step 3: tabular SR gain × need and its two ablations, the signed rule the RQ1 bounds were written for, with the three changes of C1–C3 preregistered; then the M2a row closes or is reported as not met.
- Uniform and prioritised produce no sequence events in any protocol tried; whether a gain × need rule does is step 3's.
- One θ and one cap, chosen by the preregistered rule; the thresholded results' dependence on them is shown only by the pilot's θ = 0.02 (decline at lap 13) against 0.0035 (none inside the block).
- Unchanged from G27 C: oracle state, four rules of nine, the rules outside the engine tick, Linux locally with CI on macOS.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 541 passed (+2 replay rules, +3 track, +5 RQ1 and dose).
- The fixed evaluation's committed tables unchanged by the protocol extension (`run_seed` at the defaults reproduces every committed per-lap row); the step-1 sequence tables byte-identical under the new direction reading.
- `python3 -m experiments.linear_track_rq1 --workers 4` and `python3 -m experiments.linear_track_dose_response --workers 4` write `docs/data/m2a/rq1/`; a second run gives byte-identical tables (the manifests' wall-clock aside).
- No tag; version 1.2.0.

**Impact:** this entry; docs/prereg/rq1_track_tabular.md (new); docs/m2a_linear_track.md (a step 2 section, the heading of "Reading" restored); docs/research_plan.md (status); README, run_instructions.md; `brain/systems/replay_rules.py`, `brain/systems/replay_events.py`, `analysis/replay_metrics.py`, `experiments/linear_track_replay.py`, `experiments/linear_track_rq1.py` (new), `experiments/linear_track_dose_response.py` (new); `tests/brain/test_replay_rules.py`, `tests/analysis/test_replay_metrics.py`, `tests/experiments/test_linear_track_replay.py`, `tests/experiments/test_linear_track_rq1.py` (new); `docs/data/m2a/rq1/` (new). No engine, console or baseline file changed.

## G29 — M2a remainder, step 3: gain × need and its ablations on the preregistered track protocol
**Date:** 2026-10-25  
**Why:** The RQ1 bounds of the plan's M2a row were written for gain × need (Mattar & Daw 2018); steps 1 and 2 built the track, the metrics, the protocol and measured the floors. This step adds the reference rule and its two ablations, with the three changes G28 C recommended, preregistered first (`docs/prereg/rq1_track_gain_need.md`), and runs the protocol over seven conditions. On the branch `m2a-gain-need` from the merge `aaaf133`.

### A. What landed
1. **`brain/systems/successor.py`**: a tabular successor representation learned by TD, with `initialise_from` a known transition structure (elementwise row sums, no matrix product; `tests/brain/test_successor.py`, 3 tests).
2. **`brain/systems/replay_gain_need.py`**: `gain_of` (the expected improvement of the decisions at the backed-up state's predecessors under the model's softmax, evaluated with the updated values; non-negative), `GainNeedReplay` with modes `gain_need`, `gain_only`, `need_only`, argmax over the distinct stored transitions (ties to the most recent), recomputed after every backup, no draw; the `ReplayModel` protocol the environment supplies (`tests/brain/test_replay_gain_need.py`, 5 tests).
3. **The track as the model** (`experiments/linear_track_replay.py`: integer state indices, `cyclic_transitions`, `TrackModel`; `TrackAgent.sr` learned in every condition from every state change including the inter-lap placements, started from the cyclic structure's SR under a uniform-random policy; `reward_priority_before` and `pre_run_priority_before` on the lap record; `trajectory_priority` for the reverse rule's "remaining_max" (G28 C1)). The defaults reproduce the committed fixed evaluation to the digit.
4. **The runner in two versions** (`experiments/linear_track_rq1.py`: `--version step2` reproduces step 2's protocol into its directory; the default `step3` runs seven conditions with θ per rule into `docs/data/m2a/rq1_step3/`; `rq1_learning.csv` with per-seed total steps paired against `none` and `prioritised_td`; the `from_this_lap` share of a reward pause's backups; (c) over blocks 1 and 3 with the first lap at 0 (G28 C3); a relative-TOST guard for a zero baseline; explicitly exploratory rows comparing the decrease block with the baseline block; `tests/experiments/test_linear_track_rq1.py`, 5 tests).
5. **Two pre-run amendments to the prereg, recorded with their reasons** (its "Pre-run amendment" section): the need as first written was exactly zero for every candidate at every reward pause (the next lap's start lies in the other goal row and the SR never linked the rows), so the SR learns the placements; and learning alone leaves that need at zero for laps, so the SR starts from the known cyclic structure (Mattar & Daw's agent has the transition structure). **θ per rule from the preregistered pilot** (G28 C2): uniform 0.0027, reverse 0.137, prioritised 0.156, gain_need 1.6 × 10⁻⁷, gain_only 2.7 × 10⁻⁴, need_only 2.7, five orders of magnitude apart.

Suite: 549 tests (541 at step 2), about 2 min with the gain rules' tests.

### B. Measured (docs/m2a_linear_track.md, the step 3 section; `docs/data/m2a/rq1_step3/`; 30 seeds)
- **Fixed mode.** gain_need: 0.63 events per reward pause and 1.07 per pre-run pause, every one reverse, 99.9% and 100% remote: sweeps of the lap *ahead* backward from its far goal (need from the next start weights the upcoming lap; the lap just run lies a lap further round the cycle). gain_only: 1.0 / 1.2 events, reverse 0.998 / 0.997, remote 0.65 / 0.78. need_only: no sequence (it replays the acting state's own transitions). Share of a reward pause's backups from the lap just run (`from_this_lap_share`): gain_need 0.013, gain_only 0.69, reverse 1.00, uniform 0.17, prioritised 0.10. The floors as in step 2.
- **Verdicts for gain_need**: (a) reward pauses 1.00 passes; (a) pre-run forward 0.00 **fails** (predicted pass); (d) passes; (b) ×4 up: events per stop +3.52 [+3.21, +3.78] passes, backups 19 → 99 (the cap); (b) ×0.25 down vs washout: events −0.36 [−0.68, −0.05], δ −0.31 [−0.57, −0.02], passes the criterion while backups stay at the cap; **exploratory** ×0.25 vs baseline: events **+2.64** [+2.33, +2.91], backups +81; west control end +2.87 events after the east ×4 (not equivalent); (c) block 1 slope +4.6 backups per lap to the cap, **fails**, first pause at 0 (EVB below θ); block 3 events −0.030 [−0.056, −0.001] passes. **gain_only**: (a) 0.997 / 0.002, (d) 0.65 / 0.78 passes (predicted fail), (b) ×4 **falls** (events −0.20 [−0.28, −0.13], backups 19.4 → 7.9), ×0.25 vs washout +0.07 [−0.01, +0.14], vs baseline −0.24 [−0.32, −0.17]; (c) block 1 passes (−2.31 [−2.37, −2.24]). **need_only**: no events; backups 52 → 69 → 72 → 75 around its θ; learning identical to none.
- **Floors with the step-3 changes**: reverse (remaining-sweep priority): ×4 up (events 0.20 → 0.90, backups 4.0 → 10.5), washout → decrease down on backups (17.6 → 14.7, passes), decrease vs baseline up (+10.7), west end 4.0 → 0, (c) block 1 passes (−0.038 [−0.040, −0.037], 0 from lap 17); prioritised and uniform to the cap from the first change, no events.
- **Learning** (mean total steps, 80 laps, fixed): none 25,627; uniform 24,343; reverse 14,633; prioritised 13,134; gain_need 11,945; gain_only 11,121; need_only 25,627 (= none). Paired by seed: gain_need − prioritised −1,189 [−1,557, −780], faster on 26 of 30, δ −0.63 [−0.80, −0.36]; gain_only − prioritised −2,013 [−2,385, −1,679], faster on 30 of 30, δ −0.81 [−0.93, −0.60]; both against none faster on every seed (−13,682 [−14,470, −12,950], −14,506 [−15,233, −13,785]); need_only − none 0 on every seed; uniform − none −1,284 [−1,825, −766], faster on 25 of 30, δ −0.35 [−0.60, −0.06] (no longer the null of G28's 40-lap fixed evaluation; length and reward scale both differ, not separated here). Thresholded: prioritised 9,360 (at the cap; −16,267 [−17,052, −15,508] against none), gain_need 12,550, gain_only 14,533, reverse 19,944, uniform 21,278 (`rq1_learning.csv`).
- Guards: 30 distinct lap-length vectors in every condition and mode. Run time about 17–20 min on 4 cores (the gain rules' argmax over up to 320 distinct transitions per backup).

### C. Decisions this surfaces (recommended default in bold)
1. **The M2a acceptance is not met, and the result is informative.** In this tabular afterstate variant gain × need keeps reverse remote sequences after reward and a rise after a bigger reward, and loses forward pre-run replay, the decline with familiarity (its thresholded rate climbs to the cap) and a signed response to a decrease. **Report the row as "first pass complete, acceptance not met, reasons structural"** (docs/m2a_linear_track.md), and **do not tag `v1.3-track-replay`** until the owner decides whether the row closes on this reading or after step 4.
2. **The decrease test's reference.** The washout block carries a surprise of 3.0 against the decrease's 0.75, so an unsigned rule passes "down" against it for a magnitude reason; the exploratory comparison against the baseline block shows every responsive rule *rising* at the decrease. **Preregister the decrease against a baseline block** (baseline → decrease → baseline → increase, or two sessions) in any later protocol.
3. **θ for scale-dependent priorities.** An EVB of order 10⁻⁷ at baseline is exceeded everywhere once V's scale changes, so the cap binds for the whole protocol. **Normalise the gain term by the reward scale (or set θ as a fraction of the current block's largest EVB) before the thresholded mode is used again for gain × need**; keep the fixed mode as the content test.
4. **Forward replay needs a forward mechanism.** Afterstate gain chains backward by construction; Mattar & Daw's forward pre-run replay needs need to dominate a flat gain with a rule that can move forward (their Q-based gain at the state itself). **If forward pre-run replay is to be tested, implement the Q-based variant (gain at the acted-from state) as a further rule**, preregistered, rather than retuning this one.
5. **Direction labels and content.** "Reverse at the reward window" is met by a sweep of the lap ahead, which the label cannot distinguish from a sweep of the lap just run. **Report `from_this_lap_share` beside the direction share** whenever a reward-window claim is made.

### D. Residuals carried forward
- Four of the nine rules (the goal-uncertainty need variant and Diekmann–Cheng) remain unimplemented; the Q-based gain variant of C4 is a fifth candidate.
- The thresholded mode is degenerate (cap-bound) for gain × need, prioritised and uniform under the per-rule θ; the fixed mode carries the content results.
- Oracle tabular state; the rules outside the engine tick; Linux locally with CI on macOS. Unchanged from G28 D otherwise.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 549 passed (+3 successor, +5 gain × need; the runner tests extended in place).
- The fixed evaluation's committed tables unchanged (`run_seed` at the defaults reproduces every committed per-lap row); step 2's protocol reproduced by `--version step2` (the pause table gains two columns and the test table the (c) block-3 and exploratory rows).
- `python3 -m experiments.linear_track_rq1 --workers 4` writes `docs/data/m2a/rq1_step3/` (manifest cites the clean code commit); the temporary pre-commit run gave identical seed-block and test tables.
- No tag; version 1.2.0 (C1).

**Impact:** this entry; docs/prereg/rq1_track_gain_need.md (new); docs/m2a_linear_track.md (a step 3 section); docs/research_plan.md (status, §4 M2a row); README, run_instructions.md; `brain/systems/successor.py` (new), `brain/systems/replay_gain_need.py` (new), `brain/systems/replay_rules.py`, `experiments/linear_track_replay.py`, `experiments/linear_track_rq1.py`; `tests/brain/test_successor.py` (new), `tests/brain/test_replay_gain_need.py` (new), `tests/brain/test_replay_rules.py`, `tests/experiments/test_linear_track_rq1.py`; `docs/data/m2a/rq1_step3/` (new). No engine, console or baseline file changed.

## G30 — M2a remainder, step 4: each change against its baseline, θ in value units, the lap of origin

**Date:** 2026-10-25  
**Why:** G29 C named two confounds in step 3's thresholded results (the decrease read against a washout block with a surprise of its own, C2; a θ in value units that the first reward change pushed every priority past, so the cap bound, C3) and one reporting gap (a "reverse" label that a sweep of the lap ahead satisfies, C5). This step removes the three with no change to any rule, preregistered first (`docs/prereg/rq1_track_step4.md`), and asks whether step 3's two unreadable failures, the signed response to a decrease and the decline with familiarity, were the confounds or the rules. On the branch `m2a-step4` from the step-3 tip `44f1609`.

### A. What landed
1. **Two sessions per seed** (`experiments/linear_track_rq1.py`, version `step4`, the default): *increase* (20 laps at east 1.0, then 20 at 4.0) and *decrease* (20 at 1.0, then 20 at 0.25) from the same seed, so the baseline blocks are the same 20 laps (a test pins it) and each change is read against the baseline that precedes it; (a) on the baseline block counted once, (d) over the three distinct blocks, (b) per session, (c) within the baseline block (`c_familiarity`) and within each changed block (`c_after_change`, secondary); the learning table per session; `--sessions`; a `session` column in every table. `--version step2` and `--version step3` reproduce the earlier protocols' pause and seed-block rows on every shared column.
2. **θ scaled by the value scale** (`TrackConfig.threshold_scale = "mean_abs_value"`, `TrackAgent.value_scale()`): for a rule whose priority is in value units (`ReplayRule.value_scaled`, True for the |TD error| and gain rules, False for need_only) the thresholded comparison is priority > θ × the mean |V| over the distinct states occupied so far, read before the pause and held through it, floored at 10⁻⁹; `reward_value_scale` / `pre_run_value_scale` on the lap record. θ per rule from the step-3 pilot rule on the normalised priority (`--pilot`, 6 s; `docs/data/m2a/rq1_step4/rq1_pilot.csv`): uniform 0.131, reverse 2.26, prioritised 1.59, gain_need 6.13 × 10⁻⁶, gain_only 0.0102; need_only keeps 2.71, step 3's value to the digit. The value scale is a property of the run, not of the rule (0.021 under uniform, 0.099 under prioritised at the same pauses).
3. **`from_this_lap_share`** as a stop and seed metric of `analysis.replay_metrics` (`from_this_lap_share(record)`); the fixed evaluation's `track_sequence_metrics.csv` gains its rows (reverse 1.00, uniform 0.21, prioritised 0.16); the report's direction tables carry it.
4. Tests: 554 (+5: the rule flag, the gain/need flag, the scaled threshold, the lap-of-origin metric, the pilot; the runner tests rewritten for three versions). Code commit `037c9bf`, data `89cfa25` (manifest clean at `037c9bf`, 738 s on 4 cores).

### B. Measured (docs/m2a_linear_track.md, the step 4 section; `docs/data/m2a/rq1_step4/`; 30 seeds)
- **Content (fixed) as in step 3.** gain_need: 0.52 events per reward pause and 0.66 per pre-run pause at baseline (0.54, 1.05 after a change), every one reverse and remote, `from_this_lap` 0.05 → 0.00; gain_only 0.75 → 1.16 and 0.78 → 1.42, reverse, remote 0.24 → 0.57, `from_this_lap` 0.71; reverse_trajectory 1.00, `from_this_lap` 1.00; no events for uniform, prioritised, need_only.
- **The decrease, clean, is unsigned for gain × need**: east block 2 − block 1 of the decrease session, thresholded, backups per stop **+78.1** [+72.1, +82.0] (19.6 → 97.7), events +3.50 [+3.16, +3.73], δ = +1.00 (every seed), **fails "down"**; the increase +59.2 [+48.8, +66.5] backups and +2.80 events, passes "up"; the west end rises by as much after either change (+59.1, +71.7: the lap ahead at a west pause is the changed east-bound lap). The cap binds for gain × need at the decrease (97.7 of 100) and nowhere else.
- **Familiarity under the scaled θ**: within the baseline block uniform, prioritised, reverse and gain_only fall to zero backups at every seed (slopes −6.1, −6.7, −0.41, −5.25 per lap; first zero at laps 10.6, 11.2, 17, 7.6), passes; gain × need **rises**, +1.70 [+1.18, +2.22] backups per lap (events +0.088), **fails**, and rises after both changes (+2.26, +0.61); need_only −0.21 [−1.13, +0.60], fails.
- **The time trend**: the "down" passes of reverse_trajectory (−4.1 east, −5.6 west), gain_only (−25.3, −20.6) and uniform (−50, −49) coincide with equal falls at the unchanged end. **Exploratory (not preregistered), east change minus west change, backups per stop**: reverse +5.1 [+3.8, +6.7] at the increase and +1.5 [+0.2, +3.0] at the decrease (up at both, |Δr|); gain_only −4.7 [−6.1, −3.5] at both; uniform +9.6 [+4.4, +15.1] and −1.0 [−4.6, +2.9]; prioritised +0.3 and −1.1; gain_need +0.1 [−12.6, +11.8] and +6.3 [−0.9, +13.6]; need_only +7 [−5, +19] at both. No rule shows a signed response on this statistic.
- **Gain alone stops at a magnitude change**: gain_only's thresholded rate is 0.0 backups per stop after the ×4 increase and 0.3 after the decrease, and its thresholded total steps are identical in the two sessions (7,015): once the policy is deterministic along the lap, a scalar reward change moves no decision and the gain of every backup is near zero.
- **Learning per session (fixed, 40 laps)**: none 14,488; uniform 14,204 (−283 [−714, +48], 13 of 30: the 40-lap null of G28 again); reverse 9,884; prioritised 9,161 / 8,807; gain_need 7,866 (faster than prioritised by 1,295 [916, 1,670] on 27 of 30, δ −0.68; 941 [594, 1,301] on 24 of 30); gain_only 7,940 / 7,946 (28 and 26 of 30); need_only = none. Thresholded: prioritised fastest (7,186 / 6,824), gain_only level with it, gain_need slower by about 1,500.
- **Predictions**: held for gain × need's (a), (d), both (b) rows and the west end; gain_only throughout; the floors' (c); the learning ordering. Failed: gain × need's (c) in the baseline (predicted pass; rose), reverse's decrease (predicted rise; fell with time), need_only's "up" at the increase (predicted fail; passes on the shared trend). Guards: 30 distinct lap-length vectors everywhere.

### C. Decisions this surfaces (recommended default in bold)
1. **The M2a acceptance is not met, and both step-3 failures now read cleanly.** The decrease response of gain × need is unsigned (a rise on every seed against its own baseline), and its rate rises with familiarity because the need term grows as the successor representation concentrates on the lap ahead faster than gain shrinks; neither is a confound. **Keep the row "first pass complete, acceptance not met, reasons structural"; the forward pre-run bound remains the one bound no afterstate rule can meet (G29 C4), so the acceptance cannot change before step 5.**
2. **A baseline-referenced rate test needs a time control.** Block 2 is always later, four rules decline over laps, and the preregistered "down" passed for three of them for that reason. **Preregister the rate tests of any later protocol as the east change minus the west change (difference in differences, paired by seed) or as an interleaved design**, with the single-end comparison reported beside it; the west end is no control for a rule whose sweep covers the changed lap from either pause (gain × need), which the prereg must say.
3. **RQ1 (b) is a |TD error| bound.** The rise-after-a-bigger-reward finding (Ambrose et al. 2016) is reproduced here by the |δ| rules and by need × gain through need, not by gain alone, which cannot respond to a magnitude change once the policy is decided. **Record in the plan that (b) discriminates the |δ| family from the pure-gain family, and that a gain rule's signature is a response to a change of *decision* (a moved goal, a new barrier: RQ2's 8-arm task), not of magnitude.**
4. **The scaled θ did what it was for, with one residual.** The cap no longer binds for prioritised and uniform (66–75 and 6–37 backups per stop after a change against 100 in step 3), and the decline with familiarity is visible for every |δ| rule. It still binds for gain × need at the decrease (97.7). **Leave θ's definition as it is** (changing it again would be tuning on the result) **and report the cap-bound cell as such**; if a later step needs the rate unbounded there, raise the cap, do not move θ.
5. **Step 5 as planned (G29 C4)**: the Mattar & Daw rule as published (a tabular Q learner driving the decisions, gain at the acted-from state over its actions, need from the SR, the n-step extension), preregistered, with all floors rerun under the Q learner for paired comparison and the difference-in-differences of C2 as the rate statistic. **Its prereg should also state what "forward pre-run replay" requires of the mechanism, so a null is read as a finding about the design and not as a failed replication.**

### D. Residuals carried forward
- Four of the nine rules remain unimplemented (the goal-uncertainty need variant and Diekmann–Cheng among them); the plan's row still names nine, and the owner's decision on its scope (G29 handoff) is open.
- The two sessions share their baseline laps: the baseline is one sample per seed, counted once; the sessions are not independent replicates of it.
- Oracle tabular state; the rules outside the engine tick; Linux locally with CI on macOS. Unchanged from G29 D otherwise.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 554 passed.
- The fixed evaluation's committed tables reproduced on every shared column (the per-lap table gains two value-scale columns; the summary table's two pre-run rows predate this step); step 3's pause and seed-block rows reproduced by `--version step3` on seeds 1–2 of three conditions.
- `python3 -m experiments.linear_track_rq1 --workers 4` writes `docs/data/m2a/rq1_step4/` (manifest clean at `037c9bf`, 738 s).
- No tag; version 1.2.0 (C1).

**Impact:** this entry; docs/prereg/rq1_track_step4.md (new); docs/m2a_linear_track.md (a step 4 section, limitations); docs/research_plan.md (status, §4 M2a row); README, run_instructions.md; `experiments/linear_track_rq1.py`, `experiments/linear_track_replay.py`, `brain/systems/replay_rules.py`, `brain/systems/replay_gain_need.py`, `analysis/replay_metrics.py`; tests in `tests/experiments/`, `tests/brain/`, `tests/analysis/`; `docs/data/m2a/rq1_step4/` (new), `docs/data/m2a/track/track_sequence_metrics.csv` (three rows). No engine, console or baseline change; the legacy and research determinism baselines are untouched.

## G31 — M2a remainder, step 5: the Mattar & Daw rule on a Q learner

**Date:** 2026-10-25  
**Why:** G29 C4 said forward pre-run replay, the one RQ1 bound no afterstate rule can meet, needs a forward mechanism: Mattar & Daw's gain at the acted-from state over its actions and their n-step backups. This step implements the rule as published on a tabular Q learner, with a one-step ablation to isolate the extension and the floors rerun on the same learner for paired comparison, on step 4's protocol with the time control G30 C2 asked for, preregistered first (`docs/prereg/rq1_track_mattar_daw.md`). On the branch `m2a-step5` from the step-4 tip `d1f5fc5`.

### A. What landed
1. **`brain/systems/value_learners.TabularQ`**: Q-learning over the same cells in the `ValueFunction` form (the action read off each transition's geometry by `action_of`, a change of the y row a TURN; `value` = max_a Q; `update_target` for a backup toward a caller's target).
2. **`brain/systems/replay_mattar_daw.py`**: `gain_q` (the expected improvement of the decision at the acted-from state when Q(s, a) moves by α δ, read with the updated values); `MattarDawReplay`, the argmax of need × max(gain, 10⁻¹⁰) over the distinct stored transitions and, with `extension=True`, the forward n-step extensions of the running chain (`ExtendedBackup`: the n-step backup of the chain's first transition through the transitions that continue it, walking as the appended transition for the replay record); ties to the extension, then recency; no draw; `mattar_daw_1step` without extensions. `tests/brain/test_replay_mattar_daw.py` (5) pins the gain, the candidate, the target, the chain, the ablation and the forward-sequence mechanism when gains are flat.
3. **The track** (`experiments/linear_track_replay.py`): `TrackConfig.learner` ("v" | "q"), the agent's softmax over Q(s, ·) under "q", `QTrackModel`; the gain × need rules need "v", the Mattar & Daw rules "q", the floors run on either.
4. **The runner** (`experiments/linear_track_rq1.py`, version `step5`, the default): step 4's two sessions on the Q learner, θ per rule from the pilot (`docs/data/m2a/rq1_step5/rq1_pilot.csv`), the (b) rate tests also as the east change minus the west change (`b_rate_*_vs_control`) and the direction shares of the changed blocks (`a_direction_after_change`); `version_conditions` per version (steps 3 and 4 keep their seven); `learner` in the manifest. Tests: 561 (+7). Code commit `515ba49`, data `7b13695` (manifest clean at `515ba49`, 661 s on 4 cores).

### B. Measured (docs/m2a_linear_track.md, the step 5 section; `docs/data/m2a/rq1_step5/`; 30 seeds)
- **The primary pair.** Fixed mode, baseline block, pre-run pauses: mattar_daw forward share **1.00** [1.00, 1.00] (passes the 0.6 bound), mattar_daw_1step 0.00 (fails): the forward n-step extension is the mechanism. Reward pauses: mattar_daw forward too (reverse share 0.00, fails; 0.00 after both changes), mattar_daw_1step reverse 1.00 (passes). Remote: 0.40 / 0.39 and 1.00 / 1.00, both pass. `from_this_lap` 0.05 → 0.00 for both: neither replays the lap just run at the reward pause (need from the next lap's start weights the lap ahead by a factor of about γ^(−lap) over the lap just run, and a magnitude change's gain at a saturated softmax cannot close it).
- **Thresholded.** mattar_daw made no backup at any pause: its θ came from a fixed-budget pilot whose Q the extension had shaped, and the priority before a pause reads one-step candidates only (the chain is empty); the prereg's deviation clause applies, its rows are undefined, and an exploratory run at the ablation's θ is reported as such (at the ablation's θ the rule runs at the cap, forward at every pause, 5,132 steps per session; two θ values forty-fold apart give no replay and the cap, so the first-backup priority does not read this rule's rate). mattar_daw_1step mirrors gain × need: 18.0 → 69.6 backups per stop after the increase (+51.7 [+42.4, +59.9], passes "up") and 94.3 after the decrease (+76.4 [+70.5, +81.0], fails "down"), both ends alike (east − west −3.2 [−14.6, +8.4] and +5.7 [−3.4, +14.6]); (c) baseline +1.54 [+0.91, +2.12] backups per lap, fails.
- **The time control.** reverse_trajectory east − west: +5.0 [+3.7, +6.6] backups and +0.397 [+0.363, +0.420] reverse events at the increase (passes "up"), +1.31 [+0.06, +2.95] backups at the decrease (fails "down": up); prioritised_td +3.4 [+0.7, +6.1] (δ 0.08) and +0.2 [−2.7, +3.4]: both ends alike. No rule shows a signed response on the difference.
- **Learning (fixed, 40 laps, the Q learner)**: none 15,567; uniform 15,213 (−354 [−610, −182], 15 of 30); reverse 10,133; prioritised 9,076 / 8,849; **mattar_daw 5,875 / 5,863**, faster than prioritised by 3,201 [2,773, 3,595] and 2,986 [2,563, 3,392] on every seed (δ −0.98); mattar_daw_1step 9,599, slower than prioritised (+523 [+105, +965]). Steps per lap at laps 3 / 5 / 10: mattar_daw 264 / 171 / 111, prioritised 407 / 348 / 327, the ablation 391 / 373 / 214. Thresholded: prioritised fastest (6,949 / 6,330); mattar_daw = none (the deviation).
- **Predictions**: held for the primary pair, the full rule's forward reward-pause replay at baseline, (d), its learning speed, the ablation's (a)/(d)/(b)/(c), the floors, the runner checks and the east − west reading of the trajectory rule; failed for reverse replay at the reward pause after a change (full rule, stated as less confident), the ablation's learning speed (close to the full rule predicted; slower than prioritised), and the full rule's thresholded condition. Guards: 30 distinct lap-length vectors everywhere.

### C. Decisions this surfaces (recommended default in bold)
1. **Forward pre-run replay exists in this family and is the n-step extension's.** The M2a row's one unmet-by-construction bound is met by the published mechanism on every seed, and the ablation shows the mechanism is necessary. **Record the row as "first pass complete; (a) pre-run forward, (d) remote and the learning bound met by the Mattar & Daw rule; (a) reverse at reward, (b) signed and (c) familiarity not met by any rule, for structural reasons recorded in G29–G31"**; the acceptance as written (all bounds by one rule) is not met, and no rule in the plan's §2 table is expected to meet it on a track whose states carry heading and goal (C2).
2. **Why no rule replays the lap just run at the reward pause.** The state is (cell, heading, goal), so the lap just run and the lap ahead are different states, and need from the state the agent acts from next (the turned-around start) weights the lap ahead by γ^(−lap) over the lap just run; in Mattar & Daw's track the states are positions, the two laps share them, and need from the goal end is highest for the cells just run. **If reverse replay of the just-run lap at the reward pause is to be tested, preregister a variant in which need is read over positions (heading and goal marginalised) or from the goal state before the turn-around**, and say which the plan's bound means; do not retune θ or the gain for it.
3. **The thresholded θ of a rule whose first-backup priority differs from its later ones.** The extension rule's priority before a pause is one-step only. **Define the pilot statistic for such a rule as the largest EVB over its first backup's candidates *and* the extension of a one-element chain at the acting state, or set θ from a thresholded pilot**, preregistered; report the exploratory run as exploratory and nothing more.
4. **The time control stays.** It cost two rows per metric and read the trajectory rule's decrease correctly where the single-end row did not. **Keep the east − west row as the rate statistic in every later protocol**, with the single-end row beside it, and state per rule whether the west end is a control (not for need-weighted rules).
5. **Learning speed is the extension's.** The full rule is the fastest learner of the series by a wide margin and the ablation is slower than prioritised |δ| replay. **Report the learning bound as met by mattar_daw, and carry the n-step return as a candidate mechanism for M3's embodied rules.**
6. **Scope of the row (owner's decision, carried from G29/G30).** Seven rules of nine run on this track; the remaining two (the goal-uncertainty need variant, Diekmann–Cheng) make their distinguishing predictions on RQ2's 8-arm task. **Amend the row to the rules that make RQ1 predictions and move the rest to RQ2**, or run them here knowing they add no RQ1 discrimination.

### D. Residuals carried forward
- The full rule's thresholded condition is undefined under the preregistered θ (C3); the exploratory run is not a preregistered result.
- The V-learner rules (steps 3 and 4) and the Q-learner rules (this step) are not paired comparisons; each has its own floors.
- Two of nine rules unimplemented; oracle tabular state; the rules outside the engine tick; Linux locally with CI on macOS. Unchanged from G30 D otherwise.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 561 passed.
- The fixed evaluation's committed tables reproduced on every shared column (defaults unchanged: the v learner); step 4's and step 3's protocols reproduced by `--version` (their tables are not re-recorded).
- `python3 -m experiments.linear_track_rq1 --workers 4` writes `docs/data/m2a/rq1_step5/` (manifest clean at `515ba49`, 661 s).
- No tag; version 1.2.0 (C1, C6).

**Impact:** this entry; docs/prereg/rq1_track_mattar_daw.md (new); docs/m2a_linear_track.md (a step 5 section, limitations); docs/research_plan.md (status, §4 M2a row); README, run_instructions.md; `brain/systems/value_learners.py`, `brain/systems/replay_mattar_daw.py` (new), `experiments/linear_track_replay.py`, `experiments/linear_track_rq1.py`; tests in `tests/brain/` (new `test_replay_mattar_daw.py`), `tests/experiments/`; `docs/data/m2a/rq1_step5/` (new). No engine, console or baseline change; the legacy and research determinism baselines are untouched.

**Owner's decisions on G29–G31 (2026-10-25).** The three stacked branches were merged in order into `ccr-6640f39d-7ve1oz` (`6d45678`, `038a7ef`, `be287a7`; CI green). G31 C6 accepted: the M2a row is amended to the seven rules that make RQ1 predictions, and the goal-uncertainty need variant and Diekmann & Cheng move to RQ2 (docs/research_plan.md §4). The tag `v1.3-track-replay` waits for step 6 (G31 C2 and C3: need over positions, a chain-aware θ for the extension rule), after which the track is left for the place-code milestone.

## G32 — M2a remainder, step 6: need over positions, a seeded priority, a θ pilot on the no-replay agent

**Date:** 2026-10-25  
**Why:** G31 C2 and C3, the last two bounded items on the track, accepted by the owner with the merge of steps 3–5 and the amendment of the row to the seven RQ1 rules: whether reverse replay of the lap just run appears at the reward pause when need is read over positions (Mattar & Daw's state space), and whether the extension rule's thresholded mode can be read at all. Preregistered first (`docs/prereg/rq1_track_step6.md`), with a disclosed smoke, a pre-run amendment and its diagnostic. On the branch `m2a-step6` from the merge `be287a7`.

### A. What landed
1. **Need over positions** (`experiments/linear_track_replay.QTrackModel(need_over="positions")`): the need of a state is the summed need of the four heading × goal states of its cell; conditions `mattar_daw_pos` and `mattar_daw_1step_pos` (the step-5 rules on it, `name` overridden); the state-based and positional conditions refuse each other's model.
2. **A seeded first-backup priority** (`brain/systems/replay_mattar_daw.MattarDawReplay(priority_mode="seeded")`, `TrackConfig.mattar_daw_priority`): before a pause's first backup the priority also reads the extensions of a chain seeded with the acting state's most recent outgoing transition; `choose` is unchanged, so the fixed mode reproduces step 5 exactly. The pilot showed it inert at the no-replay agent's late-baseline pauses (the one-step and extension rules share a θ).
3. **An observe budget mode** (`TrackConfig.budget_mode="observe"`, `EVALUATION_MODES` for the runner): the rule's priority and the value scale recorded at every pause, nothing backed up. **The pre-run amendment**: the four Mattar & Daw conditions' θ is read in observe mode, on the no-replay agent the thresholded run starts from, after the fixed-mode pilot returned step 5's θ to the digit and a 40-lap diagnostic showed the seeded priority never exceeding it (ratio ≤ 0.67). The floors keep the fixed-mode pilot (their values are step 5's).
4. **The runner** (version `step6`, the default): eight conditions, `THRESHOLDS_STEP6`, the pilot table records the mode, `--version step5` reproduces step 5 (a test pins seed 1's per-pause rows of both Mattar & Daw rules). Tests: 564 (+3). Code commit `8fd3e8a`, data `cc57939` (manifest clean at `8fd3e8a`, 721 s on 4 cores). The owner's decisions on G29–G31 are recorded above and the M2a row amended in the same commit.

### B. Measured (docs/m2a_linear_track.md, the step 6 section; `docs/data/m2a/rq1_step6/`; 30 seeds)
- **Reproduction**: the floors' rows (both modes) and the step-5 rules' fixed-mode rows are identical to step 5's on every seed-block row and learning row.
- **The reverse-at-reward bound is met with the lap just run**: `mattar_daw_1step_pos`, fixed mode, baseline block, reverse share **1.00** [1.00, 1.00], `from_this_lap_share` **0.68** (0.58 after a change); every state-based rule of steps 3–5 sat at 0.00–0.05. Remote 0.12 [0.09, 0.15] pooled (0.00 at baseline, 0.14 after a change), passes the bound narrowly where a fail was predicted. Pre-run: reverse (forward share 0.00).
- **The extension rule with positional need is forward at both pauses**: `mattar_daw_pos` reverse share 0.006 at baseline and 0.004 after a change (predicted mixed, then reverse: failed), forward 1.00 at pre-run; 61% of its baseline reward-pause backups are of the lap just run but do not chain into sequences; the sequences are the extension's forward chains of the lap ahead. Remote 0.41 / 0.43. Learning 6,062 / 6,061, within 190 of mattar_daw (5,875), faster than prioritised_td on every seed.
- **The extension rule's thresholded mode runs under the observe θ** (5.2 × 10⁻⁶): 10.4 backups per stop at baseline, 47.7 after the increase (+37.3 [+25.6, +49.1], passes "up"), 76.1 after the decrease (+65.7 [+57.0, +73.2], fails "down": unsigned), both ends alike (east − west +4.5 [−12.8, +22.0], +15.4 [+2.9, +28.8], δ 0.28); (c) baseline +1.97 [+1.23, +2.68], fails; thresholded learning 11,176 / 10,435. The same θ leaves the one-step rule nearly silent (0.3 backups per stop at baseline; learning within 355 of none). The positional rules replay for three laps and then stop for good (3.7 and 4.9 at baseline, 0 from laps 3.1 and 3.7, 0.0 through both changes); their "down" passes (−3.6, −4.9, east − west −1.6, −1.8) are the same fall as at the increase.
- **Predictions**: held for the primary (1.00 and 0.68), the pre-run fails of the one-step rules, the extension rule's forward pre-run replay under positional need, its thresholded run at neither 0 nor the cap with an unsigned (b) and no (c) decline, the learning ordering, the identical step-5 rows; failed for reverse replay after a change by `mattar_daw_pos` and for the one-step positional rule's remote share; unpredicted: the thresholded silence of the positional rules after lap 3 and of the one-step state-based rule under the observe θ. Guards: 30 distinct lap-length vectors everywhere.

### C. Decisions this surfaces (recommended default in bold)
1. **The row closes on this reading, and the tag follows.** Every RQ1 bound has now been met by some rule in the family except the two that are structural for the whole family on this track: a signed response to a reward change (no rule, on either statistic) and a decline with familiarity (no need-weighted rule). The two directional bounds are met by two rules that differ in one mechanism: the forward n-step extension gives the pre-run forward replay and takes the reward pause's sequences with it; without it, one-step gain chaining with positional need gives reverse replay of the lap just run. **Record the row as "first pass complete; bounds met per rule as in the step 6 section; the acceptance as written (every bound by one rule) not met, reasons structural (G29–G32)", tag `v1.3-track-replay` on the merge, and leave the track**, as the owner decided.
2. **What the place-code milestone carries from here.** (i) The Q learner with the n-step extension: the fastest learner of the series by a wide margin, and the only source of forward pre-run replay. (ii) Need over positions: the only source of reverse replay of the lap just run; in a continuous place code, need is positional by construction, so the two directions may coexist there as in Mattar & Daw's model, which is the first question to preregister. (iii) The east − west difference as the rate statistic, with the per-rule statement of whether the unchanged end is a control. (iv) `from_this_lap_share` beside every direction share.
3. **The thresholded mode as specified does not read need-weighted rules.** Six pilots over four steps have given, for every need-weighted rule, either no replay, the cap, or silence after a few laps; the rate a need-weighted rule produces depends on the agent its θ was read on far more than on the reward change. **Do not carry the per-rule θ pilot into the place-code milestone as it stands.** Preregister one of: a rate read in fixed mode (the number of backups whose EVB exceeds a θ set once on the no-replay agent, with no replay actually gated by it), or a thresholded mode whose θ is re-read from the agent at each block's first pause and reported as such. State the choice before any run.
4. **Positional need and the extension are not additive.** The extension wins the reward pause's sequences whenever it is available, so a rule that shows both directions on this track would need a mechanism that lets gain-driven backward chains outrank need-driven forward extension when the error at the consume is fresh (a recency weight on gain, or the extension restricted to pre-run pauses, both of which Mattar & Daw do not do). **Record as a candidate for the place-code preregistration, not as further track work.**

### D. Residuals carried forward
- The two remaining rules of the original nine (the goal-uncertainty need variant, Diekmann–Cheng) are RQ2's, by the owner's decision; nothing on this track tests them.
- The thresholded mode's readings for the need-weighted rules are degenerate in one direction or another at every θ tried (C3); the fixed-mode content and the learning tables carry the series' results.
- Oracle tabular state; the rules outside the engine tick; V- and Q-learner conditions not paired across learners; Linux locally with CI on macOS. Unchanged from G31 D otherwise.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 564 passed.
- The fixed evaluation's committed tables reproduced on every shared column; steps 2–5 by `--version`; step 5's fixed-mode rows identical inside the step-6 tables.
- `python3 -m experiments.linear_track_rq1 --workers 4` writes `docs/data/m2a/rq1_step6/` (manifest clean at `8fd3e8a`, 721 s).
- Tag `v1.3-track-replay` on the merge into the dev branch (C1), version 1.2.0 unchanged in `pyproject.toml` until the owner bumps it.

**Impact:** this entry; docs/prereg/rq1_track_step6.md (new); docs/m2a_linear_track.md (a step 6 section, limitations, the row's standing); docs/research_plan.md (status, §4 M2a row); README, run_instructions.md; `brain/systems/replay_mattar_daw.py`, `experiments/linear_track_replay.py`, `experiments/linear_track_rq1.py`; tests in `tests/brain/`, `tests/experiments/`; `docs/data/m2a/rq1_step6/` (new). No engine, console or baseline change; the legacy and research determinism baselines are untouched.

## G33 — M2b step 1: the corrected position estimate

**Date:** 2026-10-25  
**Why:** The plan's row 2b puts a place population over "the corrected estimate", and docs/odometry.md recorded that nothing corrects the estimate until M2b's wall-contact reset; plan §2 item 1 declares a heading oracle so that multi-start tasks can localise. This step builds both, off by default, and characterises them in the 2 m open field before anything sits on them, preregistered first (`docs/prereg/m2b_estimate.md`, with a five-seed probe and a smoke disclosed). On the branch `m2b-estimate` from the `v1.3-track-replay` merge `04f80b6`.

### A. What landed
1. **Two optional Observation fields** (`brain/contracts.py`): `heading` (the declared oracle) and `wall_contacts` (the egocentric normals of the walls touched), None unless turned on, validated when present; `observation_fields()` leaves them out while None, and both the checksum and the determinism record go through it, so the legacy and research baselines and the observation sidecar are byte-identical.
2. **The sensors** (`core/sensors.py`, `SensorConfig.heading_oracle`, `heading_oracle_noise`, `wall_contact_sensing`): the oracle reads the body's heading plus N(0, σ) from a new named stream, `sensors_heading` (no draw at 0); the touch reads the walls whose line the body sits on.
3. **The estimate** (`brain/systems/spatial.py`, `SpatialConfig.heading_source`, `wall_reset`, `reset_bounds`): the oracle heading in place of the summed turn; the reset snaps the allocentric contact normal to the nearest axis and writes that wall's coordinate; `SpatialState.resets` records the walls written. The engine refuses either option without its channel and gives the reset the world's bounds as the agent's declared map.
4. **The experiment** (`experiments/estimate_correction.py`): 8 cells × 30 seeds × 3,000 ticks, the same body walk in every cell of a seed. Tests: 580 (+16). Code commit `0f563b7`, data `8443f55` (manifest clean at `0f563b7`, 14 s on 4 cores).

### B. Measured (docs/m2b_place_code.md, step 1; `docs/data/m2b/estimate/`; 30 seeds)
- **All four preregistered tests pass.** The M2b estimate's per-seed late median error 0.70 [0.65, 0.76] units (7 cm, bound 2); against the research estimate −9.2 [−10.8, −7.7] units, δ −1.00, every seed; the drop at contact −0.56 [−0.60, −0.52] units, the normal error 0 at all 1,044 onsets; no wrong-wall write.
- **Levels**: late mean error 10.1 units (integrated), 8.3 (oracle, no reset), 3.6 (integrated, reset; wrong-wall writes 2.5% at 9 of 30 seeds), 0.92 (the M2b estimate, flat from the first contacts; 90% of late ticks within 0.2 m). The body is at a wall on 41% of ticks, 35 contacts per run.
- **Mechanisms**: the reset removes 7.4 units under the oracle and 6.6 under integration; the oracle alone removes 1.85 [0.73, 3.16] (δ −0.23); with the reset on it removes a further 2.6 (δ −1.00) and every wrong-wall write.
- **The residual is the wall-slide under-read**: the egomotion reports a slide's projection on the heading (cos² φ of the thrust instead of cos φ), so the estimate under-reads every slide along a wall; it dominates the error without a reset and sets the floor with one (0.65 units at oracle error 0).
- **Sensitivity**: late median 0.65, 0.66, 0.70, 0.81, 1.11 units at σ 0, 0.02, 0.05, 0.1, 0.2 rad; wrong-wall writes only at 0.2 rad (0.01%, 5 of 30 seeds), predicted none: one failed prediction, of the size a 3.9-sd heading error gives.

### C. Decisions this surfaces (recommended default in bold)
1. **The corrected estimate for M2b is the oracle heading at σ 0.05 with the reset.** It meets the 0.2 m level with an order of magnitude to spare in the open field. **Use it as the estimate the place population sits on (step 2)**, configured explicitly by each M2b experiment, not yet the research profile's default: changing the profile moves the research baselines, which happens once per milestone, at M2b's exit.
2. **The wall-slide under-read stays, recorded.** Reading lateral motion would change the egomotion contract the whole engine uses. **Keep the contract; report the under-read's share wherever estimate error matters**, and revisit only if step 4's arrival error approaches the bound.
3. **The heading oracle is necessary but not sufficient.** Without the reset it buys 1.85 units; with it, it is what makes the reset safe. **Keep both declared as limitations** in every write-up (plan §2 item 1).

### D. Residuals carried forward
- A convex box with known walls; an exact touch; a known start pose. Localisation from an unknown start, non-box arenas and a noisy boundary sensor are untested.
- Linux locally with CI on macOS; no second machine.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 580 passed; the legacy and research determinism baselines unchanged.
- `python3 -m experiments.estimate_correction --workers 4` writes `docs/data/m2b/estimate/` (manifest clean at `0f563b7`, 14 s).

**Impact:** this entry; docs/prereg/m2b_estimate.md (new); docs/m2b_place_code.md (new); docs/spec.md (the Observation contract); docs/research_plan.md (§4 row 2b status); docs/odometry.md (a pointer); README, run_instructions.md; `brain/contracts.py`, `brain/systems/spatial.py`, `core/config.py`, `core/sensors.py`, `core/determinism.py`, `core/engine.py`; `experiments/estimate_correction.py` (new); tests in `tests/sensors/`, `tests/brain/`, `tests/experiments/`; `docs/data/m2b/estimate/` (new). No profile default, engine behaviour or baseline changes.

## G34 — M2b step 2: the place population over the corrected estimate

**Date:** 2026-10-25  
**Why:** The plan's row 2b puts a Gaussian place population over the corrected estimate and asks for rate-map metrics, decoding error that drops at wall contact, and ≥ 1,000 ticks/s with a 400-cell population. This step builds the population, off by default, and measures those against a reference population read at the body's true position on the same walks, preregistered first (`docs/prereg/m2b_place_population.md`). On the branch `m2b-place`, stacked on step 1's `m2b-estimate`.

### A. What landed
1. **`EngineConfig.place`** (`PlaceConfig`: enabled, spacing 1 unit, width 1 unit, max rate, extent) and **`brain/systems/place_population.py`**: cells on a grid over the arena (`GaussianPlaceFeatures.grid`, unnormalised), rates at the estimate; `decode()` inverts the code by least squares on the log-rates of the most active cell's 3 × 3 grid neighbourhood. The engine builds the population lazily (importing `core.engine` still imports no numpy) and computes the rates in the spatial step; no TickData field, no hash moves.
2. **`analysis/place_metrics.py`**: rate maps over bins of the true position; per-cell comparison with a reference on the same walk (correlation, centroid shift, Skaggs information).
3. **`experiments/place_population.py`**: per seed, the research and M2b estimates' populations on the same walk and the reference; the decoder checked every tick with undefined decodes counted; a throughput benchmark. Tests: 587 (+7). Code commits `a37aef9` and `cab16db` (the correction below), data `2beb8c0` (manifest clean at `cab16db`, 7 s on 4 cores).

### B. Measured (docs/m2b_place_code.md, step 2; `docs/data/m2b/place/`; 30 seeds)
- **All four preregistered tests pass.** Throughput 16,200 ticks/s with 400 cells (17,600 off; bound 1,000); the decoder within 6 × 10⁻¹⁴ units of the estimate at every tick, none undefined; decoding error at contact −0.56 [−0.60, −0.52] units; map correlation +0.59 [+0.54, +0.63] higher under the M2b estimate than the research estimate, δ 1.00, every seed.
- **Maps**: correlation with the reference 0.91 [0.90, 0.92] (M2b) and 0.33 [0.28, 0.37] (research); centroid shift 0.35 and 3.7 units; information ratio 0.91 and 0.84. Wall and interior cells alike under M2b (0.913, 0.915); the innermost ring lowest (0.87), where sampling is thinnest. 224 of 400 cells have a sampled field in 10 minutes (170 of 400 bins visited five times or more).
- **Decoding error is the estimate's**: 0.70 units (M2b), 10.2 (research), step 1's numbers to 10⁻¹³, since the rates are noiseless.
- **One failed prediction**: the research estimate's information ratio was predicted below 0.6 and is 0.84; a displaced map is still a sharp map.
- **Post-run correction**: the first run's decoder solved over the nine most active cells, collinear when the estimate is more than about ten units beyond an edge, and returned NaN there (117 and 295 ticks at seeds 1, 2); the experiment's `max()` skipped NaN, so the decoder test read as exact and the decoding level (4.2 units) was a selection of the least-drifting seeds. Fixed before any result was reported (the 3 × 3 neighbourhood; undefined decodes counted and failing); tests and bounds unchanged; the first run's tables not committed; only the decoding statistics moved.

### C. Decisions this surfaces (recommended default in bold)
1. **The population for M2b is 400 cells at 0.1 m spacing and width over the M2b estimate.** It carries the true position to a map correlation of 0.91 and runs at sixteen times the plan's throughput bound. **Use it as the SR's state space in step 3**, configured explicitly by each experiment, as step 1's estimate is.
2. **Report map correlation and centroid shift, not spatial information, wherever estimate error matters.** Information measures selectivity, and a displaced field keeps it.
3. **A NaN-skipping aggregate is a defect class, not a one-off.** Python's `max()` and a mean over `isnan`-filtered values each hid a failure here. **Every later experiment counts undefined values explicitly and fails a test on them rather than filtering them out.**
4. **Sampling, not the estimate, limits the interior maps.** Ten minutes visits under half the bins five times. **Step 3's open-field SR maps should run long enough to sample the interior** (or report coverage beside every map statistic).

### D. Residuals carried forward
- Noiseless rates: the decoder checks consistency; decoding noisy activity is M7 step 0.
- A regular grid of centres, not random placement; one width; no wall geometry in the fields (the walls are the box's own).
- Linux locally with CI on macOS.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 587 passed; the legacy and research determinism baselines unchanged.
- `python3 -m experiments.place_population --workers 4` writes `docs/data/m2b/place/` (manifest clean at `cab16db`, 7 s).

**Impact:** this entry; docs/prereg/m2b_place_population.md (new, with the post-run correction); docs/m2b_place_code.md (step 2); docs/research_plan.md (row 2b status); README, run_instructions.md; `core/config.py`, `core/engine.py`; `brain/systems/place_population.py`, `analysis/place_metrics.py`, `experiments/place_population.py` (new); tests in `tests/brain/`, `tests/experiments/`; `docs/data/m2b/place/` (new). No profile default, behaviour or baseline changes.

## G35 — M2b step 3: successor features over the place code

**Date:** 2026-10-25  
**Why:** The plan's row 2b asks for an SR learned by TD from the agent's own trajectories over the place code, with two signatures: "after 50 laps on the track, SR fields skew backward against the running direction (Stachenfeld 2017)" and "near walls, fields elongate along the wall", and warns that the skew may fail for kinematic reasons on a short track. This step builds the learner and measures both, preregistered first (`docs/prereg/m2b_sr_fields.md`). On the branch `m2b-sr`, stacked on step 2's `m2b-place`.

### A. What landed
1. **`brain/systems/successor_features.py`**: ψ(s) = M φ(s) over the normalised population rates, M from the identity by TD(0), no bootstrap across an episode boundary; element-wise numpy only (no BLAS product), so its tables reproduce across platforms. A test pins its convergence to the closed-form SR of a three-state loop.
2. **`experiments/sr_fields.py`**: a 2 m × 0.1 m track with 50 laps imposed by a protocol (`one_way` with a carry back and an episode boundary, `two_way` with a turn in place), and the agent's own 12,000-tick walk in the 2 m box. Tests: 592 (+5; the code commit's message says 594 and +7, a miscount). Code commit `ab5c594`, data `42df820` (manifest clean at `ab5c594`, 38 s on 4 cores).

### B. Measured (docs/m2b_place_code.md, step 3; `docs/data/m2b/sr/`; 30 seeds)
- **All three preregistered tests pass.** One-way centre-of-mass shift −2.13 [−2.134, −2.130] units (0.21 m backward); one-way minus two-way −2.17, δ −1.00; wall elongation +0.54 [+0.54, +0.55] in log(along/across) beyond the raw field's 0.80.
- **Track**: the shift grows from about 0 at the start to −2.4 units from mid-track; skewness −0.57; the peak moves back 0.77 units (predicted not to move: failed); two-way fields centred (+0.04 in the interior; the end cells pushed inward). The seeds vary only speed and sensor noise, so the intervals are narrow by construction.
- **Open field**: 64 of 72 wall cells elongate; interior fields isotropic (log ratio −0.003) and 24% larger than the raw fields; wall fields 59% larger.
- **Estimate**: one-way 0.17 units, open field 0.67; two-way 0.83, against a prediction of under 0.5 (failed): without re-anchoring, the across-track coordinate drifts with the oracle's heading error since the side walls are never touched. The one-row population is blind to it.

### C. Decisions this surfaces (recommended default in bold)
1. **The backward skew is a property of directional running.** With position-only features, two-way running cancels it. **State the plan's bound as "on one-way laps" (or with direction-specific cells) wherever it is used**, and do not expect it on a two-way track.
2. **The kinematic caveat is sidestepped, not answered.** The agent's own policy cannot run laps in a 0.1 m corridor. **If the skew is needed under the agent's own policy, widen the track** (to at least its 0.2 m turning diameter) rather than change the turning kinematics, and record that it is a different track from the plan's.
3. **The SR is ready to be read.** **Step 4 builds V = M·R, lets it steer the agent, and runs the RQ4(a) gate**, with the tabular value memory over the same estimate as the plan's ablation.

### D. Residuals carried forward
- Imposed running on the track; one learning rate and discount; the SR learned outside the engine.
- Linux locally with CI on macOS.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 592 passed; the determinism baselines unchanged.
- `python3 -m experiments.sr_fields --workers 4` writes `docs/data/m2b/sr/` (manifest clean at `ab5c594`, 38 s).

**Impact:** this entry; docs/prereg/m2b_sr_fields.md (new); docs/m2b_place_code.md (step 3); docs/research_plan.md (row 2b status); README, run_instructions.md; `brain/systems/successor_features.py`, `experiments/sr_fields.py` (new); tests in `tests/brain/`, `tests/experiments/`; `docs/data/m2b/sr/` (new). No profile, behaviour or baseline changes.

## G36 — M2b step 4: the RQ4(a) gate, relative to the visible-goal ceiling

**Date:** 2026-10-25  
**Why:** RQ4(a) gates M2b: if the embodied agent cannot reach a learned goal, no later replay result is interpretable. A probe (docs/m2b_place_code.md) found the research agent reaching even a visible off-centre goal on 13 of 20 trials, so the plan's absolute 80% measures the motor policy. **The owner's decision (2026-10-25): gate on hidden-goal success after 20 trials as a share of the same agent's visible-goal success from the same starts, ≥ 0.8, both absolute rates reported, the arrival-error bound unchanged** (docs/research_plan.md's RQ4(a) amended). Preregistered (`docs/prereg/m2b_gate.md`); after its failure, a confirmatory run preregistered on fresh seeds (`docs/prereg/m2b_gate_confirmatory.md`). On the branch `m2b-gate`, stacked on step 3's `m2b-sr`.

### A. What landed
1. **`ValueMemoryConfig.source`** ("tabular", the default and unchanged path; "sr"; "none") and **`PlaceConfig.sr_learning_rate`, `sr_discount`, `reward_learning_rate`, `reward_rule`** ("nlms", the preregistered rule and default; "per_feature"). With "sr" the engine learns online successor features over the normalised place rates and reward weights R, and the steering reads V(p) = φ(p)·(Mᵀ R) where it read the map (`Engine._value_at`); `Engine.reset_value_episode()` cuts every learner at a protocol's trial start. Element-wise numpy, imported lazily; no hash moves.
2. **`experiments/rq4a_gate.py`**: four wall-midpoint starts shuffled per block from a protocol stream, a 0.1 m goal at (0.5 m, 0.5 m), 40 trials of 60 s, hidden sessions with visible guidance after a miss and visible sessions, three value sources; the ratio bootstrapped by resampling seeds; `--prereg` ties a run to the preregistration whose seeds and rule it uses, and marks any other run exploratory.
3. Tests: 600 passed (+8). Commits: code `717792a`, data `5edb6b1` (the preregistered run); the per-feature rule `7023bc2`; the confirmatory preregistration `71ae396`; data `2b9ab26` (the exploratory and confirmatory runs, manifests clean at `7023bc2` and `71ae396`).

### B. Measured (docs/m2b_place_code.md, step 4; 30 seeds per run; trials 21–40)
- **The preregistered gate fails for the SR source**: hidden 13%, visible 46%, ratio **0.29 [0.23, 0.35]**; arrival error 0.25 units (passes). The tabular ablation: hidden 84%, visible 82%, ratio 1.03; no value steering: 5.5%, 62.5%, 0.09.
- **Cause** (seed 1): the NLMS reward rule rings the goal with negative weights (R 2.2 at the goal, −1.0 beside it), so V has a trough around the goal (−0.37) and a flat far field (3 × 10⁻⁵); the SR source's hidden success fell from 0.53 in the first block to about 0.12 as the ring formed, and its visible success from 0.75 to 0.45.
- **Exploratory** (seeds 1–30, not preregistered): the per-feature rule R += 0.5 φ (r − R) gives hidden 99.5%, visible 100%.
- **Confirmatory** (seeds 31–60, preregistered): the SR source with the per-feature rule: hidden **98.7%**, visible 100%, ratio **0.987 [0.973, 0.993]: passes**; arrival error **0.20 [0.19, 0.21] units: passes**; median latency 14 ticks; ≥ 80% at all 30 seeds. Tabular: 85.5%, 78.7%, ratio 1.09, median latency 81 ticks, ≥ 80% at 25 of 30 seeds. None: 5.0%, 65.2%.
- **Predictions**: the first run's g1 fail and g2 pass held (g1 for a different reason than predicted), its "SR beats tabular" and "visible ceiling about two thirds" failed; every confirmatory prediction held.

### C. Decisions this surfaces (recommended default in bold)
1. **RQ4(a) passes, and with it the plan's row 2b acceptance** (docs/m2b_place_code.md, "Where M2b stands"), the gate in the owner's amended form; the SR source with the per-feature rule also clears the original absolute 80%. **Carry the per-feature reward rule forward as the SR's rule** and keep NLMS only to reproduce the first run.
2. **M2b's exit, for the owner.** (a) **Merge the four stacked branches in order** (`m2b-estimate`, `m2b-place`, `m2b-sr`, `m2b-gate`) and **tag `v1.4-place-code`**. (b) Whether the research profile adopts the M2b configuration (heading oracle σ 0.05, wall-contact sensing and reset, the place population, the SR value source with the per-feature rule) as its defaults: **recommended yes, at the merge**, regenerating the research baselines once as the plan allows per milestone (the legacy set untouched), so M3 starts from the instrument the gate passed; the alternative keeps every M3 experiment configuring it explicitly. (c) The console panels stay deferred.
3. **A reward model over overlapping features is a design choice with behavioural consequences.** The negative ring is general to regressing point rewards on overlapping bases. **Any later learner that fits rewards on place features states its rule and checks the sign structure of its weights** before a behavioural run.
4. **The tabular map is a legitimate ablation that also navigates.** It passes the gate more slowly (median 81 ticks against 14). **Keep it as M3's ablation baseline**, as the plan says.

### D. Residuals carried forward
- One goal location, known start poses with a re-anchored estimate, no replay; the motor policy unchanged.
- The reward rule was changed after a failure; confirmed on fresh seeds, but one change chosen after seeing the problem.
- Linux locally with CI on macOS.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 600 passed; the determinism baselines unchanged.
- `python3 -m experiments.rq4a_gate --workers 4` writes `docs/data/m2b/gate/` (the preregistered run); the confirmatory command in `docs/prereg/m2b_gate_confirmatory.md` writes `docs/data/m2b/gate_confirmatory/`.

**Impact:** this entry; docs/prereg/m2b_gate.md and m2b_gate_confirmatory.md (new); docs/m2b_place_code.md (step 4, where M2b stands); docs/research_plan.md (RQ4(a) amended, row 2b status); README, run_instructions.md; `core/config.py`, `core/engine.py`; `experiments/rq4a_gate.py` (new); tests in `tests/engine/`, `tests/experiments/`; `docs/data/m2b/gate/`, `docs/data/m2b/gate_confirmatory/` (new). No profile default or baseline changes.

## G37 — M2b's exit: merged, tagged `v1.4-place-code`, and the research profile adopts the M2b instrument

**Date:** 2026-10-26  
**Why:** G36 C2 put M2b's exit to the owner. **The owner's decisions (2026-10-26): all three as recommended.** (a) The four stacked branches merged in order into `ccr-6640f39d-7ve1oz` (`7efccaf` m2b-estimate, `f9d6c43` m2b-place, `c8a0035` m2b-sr, `4893c69` m2b-gate; 600 tests; CI green on Ubuntu and macOS). (b) The research profile adopts the configuration the RQ4(a) gate passed with, so M3 starts from the instrument the gate passed instead of every experiment configuring it; the research baselines regenerated once, as the plan allows per milestone (§5 item 9), the legacy set untouched. (c) The console panels stay deferred. The tag `v1.4-place-code` is on the commit carrying this entry, so the tag carries the defaults.

### A. What landed
1. **`EngineConfig.research()`** sets `sensors.heading_oracle = True`, `heading_oracle_noise = 0.05`, `wall_contact_sensing = True`, `spatial.heading_source = "oracle"`, `spatial.wall_reset = True`, `place.enabled = True`, `place.reward_rule = "per_feature"` and `value_memory.source = "sr"`. The profile diff gains eight rows, 25 in all (docs/profiles.md's table; `tests/engine/test_profiles.py` pins it); `stochastic_elements()` lists four at the defaults, the oracle's sd last. Nothing else in the profile moved; the legacy profile is untouched (`EngineConfig().diff(EngineConfig.legacy()) == []`, its hashes bit-identical).
2. **The research determinism set regenerated** (`tools/update_determinism_baseline.py --profile research --i-know-what-im-doing`; seed 1337, 200 ticks): the behaviour and full hashes, the reference trace, its observation sidecar (which now carries `heading` and `wall_contacts`) and the meta file moved; **the physics hash did not**: the body's walk at the gate seed is the M2a one to the tick (B). The legacy files are unchanged.
3. **Experiments inherit the profile.** Each recorded run reproduces at its recorded commit (every manifest carries the full config and git sha; the M2b data are at `127765e`–`0efb4f6`, M2a's at `v1.3-track-replay`). At this commit: `experiments/odometry_characterisation.py` pins M1's instrument (the integrated heading, no reset, no population, the map), because its cells characterise the integrated estimate and would otherwise measure the oracle; the M2b experiments already set their estimate fields explicitly, so `estimate_correction`'s `oracle_reset` cell and `place_population`'s `m2b` cell are now the profile itself and the other cells differ from it in their estimate alone (their tests state the diffs); `rq4a_gate`'s SR cell with the per-feature rule differs from the profile in nothing; `place_population`'s throughput measurement keeps the map in both arms, so it still measures the population's own cost. In a reward-free walk the population and the SR source leave the body's trajectory unchanged (B), so these experiments' walks are what they were, at the SR's cost in speed.
4. **Tests:** the eight files that pinned the old defaults updated (profiles, seeds as samples, heading oracle and contacts, place population, value source, spatial reset, research confounds, the cross-platform sidecar's key set); the confound tests switch the population off in their 5,000-unit box (a population over that arena would be 10⁸ cells, C2). Suite 600 passed, the count unchanged; the research exact-hash gates pass against the regenerated set.
5. Version: `pyproject.toml` and `CITATION.cff` stay at 1.2.0 (the owner bumps; G24 B6, G32).

### B. Measured (open field, seed 1337, 3,000 ticks; `tests/engine/test_profiles.py`, docs/profiles.md)
- **The body's walk is unchanged by the adoption**: 1,230 wall-clamped ticks, mean step 0.52, 28 REST ticks, as at M2a, to the tick. Without reward the SR value is 0 everywhere (the steering reads 0 as it read the empty map) and the oracle draws on its own stream, so the M2b fields move the estimate and not the body. Checked directly on `estimate_correction`'s integrated cell too: 600 ticks at seed 1, identical positions and estimates with and without the population and the SR source.
- **The estimate**: error first above 0.5 units at tick 82 (M2a: 20), 0.88 units at the end (11.8), 3.5 at most (15.8), median 0.63; the heading error is the oracle's own, 0.18 rad at most. With the four seeded elements at 0 the estimate is exact (2 × 10⁻¹³) and the body never touches a wall, so the M0a statements hold as before.
- **Throughput**: about 2,400 ticks/s at the research defaults in the open field (the SR learner; the population alone 16,200; the M2a profile 8,300–8,800), above the plan's floor of 1,000. The plan's RQ1 confirmatory grid (5.4 M ticks) is then about 40 minutes serial, 12 on four cores.

### C. Decisions this surfaces (recommended default in bold)
1. **M3 starts from this profile.** Its experiments configure the replay rules and the trial structure on top of it and state their diff from `research()` in their manifests, as the M2b experiments do; **the tabular map stays the ablation** (G36 C4), by `value_memory.source = "tabular"`.
2. **`place.extent` follows the arena.** A research run in a much larger arena must set `place.extent` (or switch the population off): the cell count grows with the area, and the confound tests' 5,000-unit box would ask for 10⁸ cells. **Leave the default** (the arena is the place field's natural extent) and **state the rule in docs/profiles.md** (done); a guard that refuses more than some thousands of cells without an explicit extent is a one-line addition if it bites again.
3. **The heading oracle is now a default limitation.** Every research-profile result from here on uses a declared heading; plan section 2 item 1 says so and each M2b report said so (G33 C). **Keep the declaration in every M3 report's limitations.**

### D. Residuals carried forward
- The oracle's sd (0.05 rad) and the softmax temperature (0.1) are placeholders characterised once (M2b step 1, M1), not tuned to data.
- One goal location and known start poses in the gate; no replay yet; the motor policy unchanged (G36 D).
- The reward rule was changed after a failure and confirmed on fresh seeds (G36 D).
- Linux locally; the macOS CI job runs the tolerance gate against the regenerated research reference, with the sidecar's two new fields.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 600 passed; the legacy baselines unchanged, the research set regenerated once.
- `EngineConfig.legacy().diff(EngineConfig.research())`: 25 rows, as docs/profiles.md's table.

**Impact:** this entry; `core/config.py` (`research()`); `tests/determinism/` (the research set); `experiments/odometry_characterisation.py` (M1's instrument pinned), `experiments/place_population.py` (throughput arms); tests in `tests/engine/`, `tests/brain/`, `tests/sensors/`, `tests/determinism/`, `tests/experiments/`; docs/profiles.md (table, seeds, measurements, baselines history), README, docs/research_plan.md (row 2b, status), docs/m2b_place_code.md (where M2b stands). Tag `v1.4-place-code`.

## G38 — The console shows the research instrument: a profile switch, the place code and SR on the arena, replay-event trails

**Date:** 2026-10-26  
**Why:** The console ran the legacy profile only, so nothing of M2a or M2b was visible in it, and the plan's console panels (row 2a's replay-event panel, row 2b's population and SR-field panels) had been deferred twice. The owner asked for the console first (2026-10-26), before M3, so that M3's instrument can be watched as it is built.

### A. What landed
1. **A profile switch in the Live tab** (`ui.scenarios.PROFILES`, `profile_config`). A scenario's `config()` stays its own settings on the legacy base; `profile_config(scenario, profile)` applies the same settings (the scenario's diff from `EngineConfig()`) on `EngineConfig.research()` and returns the fields they move away from the profile, which the switch lists ("This scenario keeps its own settings on top of the profile: …"). `SimSession(..., profile=)`, `POST /api/sim {profile}`, `/api/meta` lists the profiles; `reset` keeps the profile; a recording's run id (`live_<scenario>_research_…`), summary (`profile`, `profile_overrides`) and manifest (`profile_requested`, `profile_overrides`; the config already carried the label) record it. Deep link `/live?profile=research`.
2. **The place code in the frame and on the arena** (research profile; `None` without a population): the population's rates at the estimate, the decoded position and the active-cell count; the SR value V = φ·MᵀR at every cell centre (as the engine computes it, element-wise, from a cached matrix of the population's normalised rates at its own centres), the successor field from here (Mφ), the reward weights R, V here, the update count and the reward rule. Arena layers **Place cells** (activity bubbles), **SR value** (the value map's diverging ramp: what steers there) and **SR field from here** (off by default), all in the estimate's coordinates like the value map; hover reads all three. A **Place code** panel draws the activity and the successor field on the population's own 20 × 20 grid, with the decode error against the estimate and against the body, V here, max |R|, the SR update count and the rule; on the legacy profile it says there is no population.
3. **Replay-event trails** (row 2a's panel, both profiles): the latest finished replay events (`engine.replay_log`) as trails of the cells they backed up, in backup order, a ring on the first cell, fading over 600 ticks, the newest labelled with its backup count and direction. The research profile produces none until M3 wires replay into its engine; the arena's legend says what the trail is.
4. **Live parameters** for the research profile's seeded elements and the SR, in a new "Estimate & sampling" group: odometry speed and turn noise, the heading oracle's noise (refused on the legacy profile, which has no oracle: the config's own rule, kept at the slider), the softmax temperature and the SR reward learning rate. Every one is read by the engine each tick.
5. **Headless parity on a profile.** `Protocol.use_profile` (a no-op by default); `ConsoleProtocol` builds its scenario on the runner's `--profile`, so `python -m experiments.runner --protocol console_<scenario> --profile research` writes the ticks a live research session records (tested on open_field and memory_maze, 200 ticks). The runner refuses an unknown profile before anything runs. Before this the option did not apply to the console protocols; the test that pinned that now pins the new behaviour.
6. Tests +14 (suite 614). Checked in a headless Chromium (Playwright) on both profiles: the page loads, the switch, the research layers and the panel render, switching the profile restarts the session on it, no page errors.

### B. Measured
- A research-profile frame costs about 3 ms and 10 KB with the place-code and SR blocks (400 cells; one frame per step request).
- The scenarios' overrides on the research profile: open_field none; beacon the pacing; foraging and hazard_field the senses and the pacing; hidden_food the value-map radius and the pacing; memory_maze `reward.approach_weight`, the radius, `oracle_homing` and the pacing. The pacing fields are inert there (ATP frozen) and listed anyway.

### C. Decisions this surfaces (recommended default in bold)
1. **What the maze shows on the research profile.** Its sleep action still consolidates the tabular map, but the steering reads the SR value there, so consolidation does not reach behaviour until M3 wires replay to the place code. **Leave it**: it is M3's question made visible, and the switch's note names the profile and the scenario's overrides.
2. **The replay viewer** does not draw the place code or the trails yet (recordings carry the profile and `replay_events.jsonl`). **Defer** to M3's trial structure, when the replay tab gains phases.
3. **The scenarios' "what to watch" text** describes the legacy mechanics. **Leave it**; M3's protocols bring their own.

### D. Residuals carried forward
- The population is drawn where the estimate puts it, like the value map; with the oracle and the reset it sits within centimetres of the body in the open field. A protocol that re-anchors the estimate at known starts (the gate's) is not in the console yet.
- No browser tests in CI (the repository has no JavaScript test runner); the headless check above is a manual step.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 614 passed; no engine, profile or baseline change.

**Impact:** this entry; `ui/scenarios.py`, `ui/sim_session.py`, `ui/server.py`, `ui/static/index.html`, `ui/static/js/arena.js`, `live.js`, `brain.js`, `ui/static/css/console.css`; `experiments/protocols/base.py`, `experiments/protocols/console.py`, `experiments/runner.py`; tests in `tests/ui/` and `tests/experiments/test_console_protocols.py`; README (Live tab, console protocols, lab console), run_instructions.md, docs/profiles.md (selecting a profile), docs/research_plan.md (rows 2a and 2b).

## G39 — The console explains the active mechanisms: terms of the decision, mechanisms in force, behaviour readouts, memory controls that name their learner

**Date:** 2026-10-26  
**Why:** A review of an 81-second recording of the G38 console found the simulation working but harder to read than it need be: scenario text and the neuromodulator roles described the legacy mechanics whatever the profile; the value map and the SR value overlapped in one palette with separate scales while the decision panel named the map; the maze's glycogen fell to zero under frozen physiology; "Forget the map" and the maze's consolidation touched the tabular map while the research profile steers from the SR; and the recurrent circling (a TURN moves the body 0.3 units while it rotates 0.3 rad, a sustained-turn radius of about 1.0 unit) could not be traced to a score. The review cited a commit that does not exist in this repository; its claims were checked against the code and held. All of it is console and scenario work; the engine's decision path is untouched.

### A. What landed
1. **The decision as its terms.** `brain.systems.basal_ganglia.channel_terms` returns every channel's score as named terms (bias, vision, memory, wall, pain, novelty; REST's gate, patience and pacing; `microsleep` alone when asleep) with the same arithmetic as `_channel_scores`, and `selection_probabilities` the softmax weights at the profile's temperature (1 on the argmax at 0). Readouts only: nothing in the engine reads them. `tests/brain/test_decision_terms.py` pins the terms to the engine's own scores over 2,500 ticks on the legacy, research and paced configurations, asleep and paced ticks included (they agree to the last bit). The frame carries `action.terms`, `action.probs`, `temperature`, `source` and `value_gain`; the Decision panel shows a table of the terms that are non-zero for some channel, the total and the probability, says "softmax τ 0.10: the highest score need not win" or "argmax", and names the value source the memory steer reads ("Memory steer (SR value × 1.50)").
2. **Mechanisms in force** (`SimSession.mechanisms`): seventeen entries derived from the effective configuration, each `active`, `readout` (computed and shown, gain 0) or `off`, with a one-line detail; sent with the session and again after a parameter change or a scenario action, so a slider that raises a gain turns its entry on. The card replaces "What to watch"; the scenario notes sit beneath it, now written per profile (`Scenario.watch_research`, three notes per scenario on what the research profile changes: no fatigue, the SR as the steering source, the oracle estimate, the turn radius, what the memory controls touch). The neuromodulator panel says when every gain is 0 and its role texts describe a gain above 0.
3. **The arena's default layers follow the steering source.** With the SR source the SR value is on and the value map is off and labelled "(tabular, diagnostic)"; with the map it is the reverse; the place cells and the successor field sit behind a "diagnostics" label, off by default; the colour scale of each visible map is printed beside the arena title ("colour scale, per map: SR value ±0.077"). A fresh session or a change of source reapplies the defaults; a reset of the same session keeps the user's toggles.
4. **Behaviour readouts** (`SimSession.behaviour`, in the Experiment card): distance walked (a scenario's teleport is not walking), the wall-contact share of ticks, finds (ticks that touched a target: the primary contact reward; one per collection), ticks since the last find, distance per find and total reward. They are what tells exploitation of a regrowing site from a loop that finds nothing.
5. **Memory controls name their learner.** `Engine.forget_rewards` clears the tabular map and, with the SR source, the SR's reward weights (M, the agent's knowledge of the space, is kept); hidden food's action is "Forget the rewards" and says what it erased. The maze's consolidation says when it changes the tabular map only ("the steering reads the SR value on this profile, so behaviour is unchanged") and its help says replay over the place code is M3's.
6. **The maze's inter-trial rest respects the physiology configuration.** `MemoryMaze._rest` ticked the astrocyte 40 times whatever `astrocyte.frozen` said, so on the research profile glycogen fell while ATP read 1.0; it now does nothing when frozen, and its event names the 40 physiology updates as such (no brain ticks, the trial clock does not advance). Legacy behaviour is unchanged.
7. Tests +7 (suite 621). Checked in a headless Chromium on both profiles: the mechanisms list, the terms table, the behaviour readouts, the layer defaults and the colour scale render; no page errors.

### B. Measured
- Research hidden food at seed 7 after 1,470 ticks: wall contact 29% of ticks, 10 finds, 51.7 units per find; the terms table has Bias, Memory and Wall columns (nothing else is non-zero there) and the softmax note. Legacy hazard field: Bias, Wall, Novelty, Patience; argmax.
- The terms agree with the engine's scores to 0.0 on 2,500 ticks (575 of them asleep, 350 paced).

### C. Decisions this surfaces (recommended default in bold)
1. **The circling is now attributable but not yet explained per scenario.** The terms show which contribution carries a run of turns; whether an orbit is memory (an old reward value pulling from outside the field of view) or geometry (forward bias meeting wall avoidance) is read case by case. **Leave the diagnosis to the reader with the tools in place**; a logged per-tick terms stream would be the next step if a quantitative answer is wanted.
2. **Scenario notes are now per profile, by hand.** Two texts per scenario is a maintenance cost. **Keep it**: the mechanisms list is the generated part, the notes are the narrative, and M3's protocols will bring their own.
3. **The replay viewer** shows none of this for a recording. **Defer** to M3's trial structure (G38 C2).

### D. Residuals carried forward
- The research profile's goal memory in the maze (the scenario's own setting) means a recall there does not isolate learned navigation; the note says so, and the gate experiment, not the console, is where that claim is tested.
- Browser checks remain a manual step.

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 621 passed; no engine behaviour, profile or baseline change (the determinism gates are untouched).

**Impact:** this entry; `brain/systems/basal_ganglia.py` (`channel_terms`, `selection_probabilities`), `core/engine.py` (`forget_rewards`); `ui/scenarios.py` (research notes, rest, consolidation, forget, action help), `ui/sim_session.py` (terms, probabilities, behaviour, mechanisms), `ui/server.py`; `ui/static/index.html`, `ui/static/js/live.js`, `brain.js`, `ui/static/css/console.css`; tests `tests/brain/test_decision_terms.py` (new), `tests/ui/`; README, run_instructions.md.

## G40 — Measuring the circling: the decision log, orbit summaries, counterfactual readouts and matched-seed ablations

**Date:** 2026-10-26  
**Why:** The G39 decision breakdown made a turn's contributions visible, but a large memory contribution alone does not establish that memory causes an orbit, and the review of the recording asked for the measurement before any movement rule changes: per-tick logging, orbit summaries, counterfactual probabilities and matched-seed ablations, logged now so recordings made before M3 stay useful. All of it is readouts and analysis; the engine's decision path is untouched and the determinism gates are unchanged.

### A. What landed
1. **The decision log** (`metrics/decisions.py`): one record per tick, read from the engine after its step and before the scenario acts on it: body position and heading, the estimate, the action, the scores and their terms, the selection probabilities, the **counterfactual** probabilities with the memory, vision or wall term removed from every score (the same softmax, no draw) and each family's **immediate influence** as the total-variation shift it makes, the softmax temperature and value source, target visibility and distance, contacts, reward, the gates, pacing, microsleep, replay, the goal vector, and two **episode counters** (`Engine.episode`, incremented by `begin_episode`: a reset or a teleport; `Engine.value_episode`, by `reset_value_episode`). A live session keeps the records (the newest 50,000, like the tick history) and a recording writes them as `decisions.jsonl`; the headless runner writes the same file with `--log-decisions` (`n_decision_records` in the summary, `log_decisions` in the manifest). A test pins that a headless console run's records equal the live session's line for line. `RECORD_KEYS` is the schema; a test pins it.
2. **Orbit summaries** (`analysis/orbits.py`): a *loop* is the shortest run of ticks over which the accumulated signed heading change reaches 2π, restarting at an episode boundary or where the running sum crosses zero (a single opposite tick does not break a loop; a net reversal does); an *orbit* is a loop with closure (net displacement over distance) ≤ 0.25; a *bout* is consecutive same-direction orbits, with duration, loops, mean radius, centre, contacts, reward, the share of ticks with a target in view, the mean of each term's contribution to the bout's turn over the turn ticks (the largest is the dominant term), memory's mean immediate influence and the turn's probability with and without memory. Categories, in order: **productive** (a target was touched), **memory** (memory dominant with influence ≥ 0.05), **wall** (wall avoidance dominant), **other**. `python -m analysis.orbits <run>` prints the table. Synthetic tests: a sustained turn is a loop every 21 ticks at radius 1.00 (0.3 / 2 sin 0.15), a straight walk, a meander and a teleport make none, a drifting spiral makes loops that are not orbits.
3. **Counterfactual readouts in the console**: the Decision table gains a "P −mem" column and a line with the three influences; the Behaviour readouts gain the signed turning (revolutions) and the closure of the last 300 ticks.
4. **Matched-seed ablations** (`experiments/console_ablation.py`): `steer` against `no_steer` (`value_gain` 0, the learners still running and the RNG streams consumed alike) on the same seeds, each run logged and summarised; finds, unique sites, distance, distance per find, wall-contact share, loops, orbits, orbit share, orbit ticks by category, mean memory influence and reward, paired by seed with `analysis.stats.paired_effect` (BCa) after `pseudo_replication_guard` on the steer arm's trajectories (the legacy profile at sensor noise 0 is refused with the remedy named). `--quick`, `--set`, `--workers`, `--keep-records`.
5. Tests +14 (suite 635; the manifest test now expects `decisions.jsonl` in a recording). Checked in a headless Chromium: the column, the influence line and the turning readouts render.

### B. Measured (eight seeds × 3,000 ticks; `docs/data/console_ablation/`; steer − no_steer, BCa 95%)
- **Hidden food on the research profile: memory steering costs a third of the finds.** Finds 17.6 against 26.5 (−8.9 [−11.9, −6.1], worse on every seed), reward 122.7 against 195.2, distance per find 66.6 against 56.4 (+10.2 [+3.2, +17.4]); unique sites the same (5.75 against 5.88). Loops 63.6 against 16.3 and orbits 55.3 against 8.4; orbit ticks by category per run: **memory 1,254 against 0**, productive 38 against 691, wall 10 against 198; mean memory influence 0.44. The 147 memory bouts over the eight runs: median 66 ticks (longest 247), 2.9 loops, mean radius 1.24 units, centre 1.0 unit from the nearest site (median 0.93), the turn taken with probability 0.92 and 0.13 without the memory term (influence 0.79), the target never in view (it is invisible there), and **every one of them starting a median 10 ticks (IQR 5–17) after a contact**, the next contact a median 68 ticks after the bout ends. The agent eats, the SR value peak at the place outlasts the food (regrowth takes 150 ticks), the steering turns toward the peak and the turn's 1-unit radius makes an orbit beside the emptied site: persistence at an obsolete reward, not search and not exploitation.
- **Beacon on the research profile: the same, as expected where the reward moves.** Beacons reached 12.0 against 21.5 (−9.5 [−13.3, −6.5]), distance per beacon 114.9 against 76.5; memory orbit ticks 884 against 0, productive 161 against 784; 101 memory bouts, median 66 ticks (longest 365), radius 1.30, centre 1.16 from the nearest spot, 100 of 101 starting within 150 ticks of a contact (median 15), the turn at 0.92 against 0.17 without memory; the beacon in view on 7% of bout ticks (the cue gate mutes memory only then).
- **Hidden food on the legacy profile (sensor noise 0.03): memory steering helps, as G21 found.** Finds 6.75 against 2.38 (+4.4 [+2.4, +9.3], better on every seed), distance per find 108 against 258, memory orbit ticks 137 (20 bouts, median 62 ticks, radius 1.25), productive 932 against 2,095 (the no-steer agent's wall loop brushes sites), orbit share 0.68 against 0.94, mean memory influence 0.12.
- **Open field on the research profile: the arms are identical** (no reward, so the SR value is 0 everywhere): 15.3 loops, 9.5 orbits, 1,005 orbit ticks per run (33% of ticks), all wall category, wall contact 42% of ticks. The perimeter circuits are wall avoidance meeting the forward bias; memory has no part in them.

### C. Decisions this surfaces (recommended default in bold)
1. **The three circlings are now told apart, and they want different interventions.** Wall-driven perimeter loops are geometry (the body's turn radius against wall avoidance and the forward bias) and cost nothing where the task's sites sit off the loop; productive circling at a regrowing site is exploitation; persistence at an emptied place is the research profile's SR steering reading a value that outlasts the reward, and it is what costs finds. **Make no movement-rule change here**: M3 is next, and this instrument is what any change would be measured with.
2. **The candidate interventions for the persistence, for a preregistered A/B when one is wanted** (hidden food, research, this ablation's metrics): an unlearning rate for the per-feature rule separate from its learning rate (R falls at the cells the orbit passes through when no reward is seen); an extinction for the SR source akin to the legacy map's `dwell_extinction` (0.02 there, 0 in research by design, G22); or a steering that reads the value's change rather than its level. **Recommended: the first**, as the smallest change to a rule already in force, measured against this baseline (17.6 finds, 1,254 memory-orbit ticks).
3. **The legacy and research profiles now differ in sign on hidden food** (memory helps on legacy, costs on research). The difference is the value source and its read (a tabular map with dwell extinction on a 0.5-unit grid against the SR over the place code), not the scenario. **Record it, do not reconcile it**: the research profile is the instrument under study.
4. **The replay viewer** still shows none of this for a recording, but every recording now carries the log. **Defer** to M3's trial structure (G38 C2).

### D. Residuals carried forward
- The orbit definition (2π of accumulated turning, closure ≤ 0.25, memory influence ≥ 0.05) is a measurement convention, stated in `analysis/orbits.py`; a bout's "centre" is the mean position of its ticks.
- `target_contact` is the engine's primary contact; a scenario that counts collections differently (the maze's goal radius) reports its own count in `status`.
- The ablation's `no_steer` arm sets `value_gain` to 0; the learners still write, so the arm is "memory not read", not "no memory".

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 635 passed; no engine behaviour, profile or baseline change.
- The four ablation directories under `docs/data/console_ablation/` regenerate from the commands in their README (seconds each).

**Impact:** this entry; `metrics/decisions.py` (new), `analysis/orbits.py` (new), `experiments/console_ablation.py` (new); `core/engine.py` (episode counters); `experiments/runner.py` (`--log-decisions`); `ui/sim_session.py` (the log, the counterfactuals, the turning readouts), `ui/static/js/brain.js`, `live.js`, `index.html`; tests `tests/metrics/test_decisions.py`, `tests/analysis/test_orbits.py`, `tests/experiments/test_console_ablation.py` (new) and in `tests/experiments/`, `tests/ui/`, `tests/metrics/`; README, run_instructions.md; `docs/data/console_ablation/` (README now, the data in the following commit).

## G41 — The SR's unlearning rate: the persistence goes and the finds come back (preregistered; the default is the owner's)

> **Note (G46, 2026-10-27):** run with the hidden sites sensed by the rays, which held the no-steering arm down; without that, U = 4 steering is 11.8 finds below no steering (G46 C, D2). D below is wrong that hidden food's `approach_weight` is 0: it is 1.0 (G46 D4).

**Date:** 2026-10-26  
**Why:** G40 C2 named the smallest change to a rule already in force as the candidate intervention for the research profile's persistence beside an emptied site, to be tried only as a preregistered A/B measured with the circling instrument; the owner chose it ("go with your recommendations", 2026-10-26). Preregistered in `docs/prereg/sr_unlearning_rate.md` at `72be077`, before any run; the pilot's data at `539b113`, the confirmatory's at `c5101b9`, each from a clean tree.

### A. What landed
1. **`PlaceConfig.reward_unlearning_rate`**: with the per-feature rule, the rate at which R falls toward 0 at the active cells on a tick that sees no reward. `None`, the default and the research profile's, uses the learning rate: the G36 rule bit for bit (the determinism gates pass unchanged). Read by the per-feature rule only; nothing else in the engine changed.
2. **`experiments/sr_unlearning.py`**: the arms `no_steer` (`value_gain` 0), `u0.5` (the rule as it stands) and `u<U>` on matched seeds, run and summarised by the G40 instrument (`experiments/console_ablation.py` now takes an arm table; `write_tables`, `arm_means` and `effects` are shared), the pilot's rule for choosing U, the three bounds scored as the preregistration states them, `--prereg` in the manifest.
3. **A live slider**, "SR reward unlearning rate" under Estimate & sampling (shown as the learning rate when the field is None), so the effect can be watched in the console.
4. Tests +4 (suite 639).

### B. Measured (hidden food, research profile, 3,000 ticks; `docs/data/console_ablation/sr_unlearning_*`)
- **Pilot, seeds 1–8 (exploratory; it chose U and nothing else).** Finds 17.6 / 19.6 / 23.4 / 27.3 at U = 0.5 / 1 / 2 / 4 against 26.5 without steering; memory-category orbit ticks per run 1,254 / 574 / 221 / 65; orbit share 0.43 / 0.28 / 0.12 / 0.11; distance per find 66.6 / 65.2 / 57.7 / 54.9; unique sites 5.6–5.9 throughout. A dose curve in the predicted direction; the rule picked **U = 4** (highest mean finds).
- **Confirmatory, seeds 9–16 (fresh), U = 4: every bound passes.**
  - **K1, finds against the rule as it stands:** 28.4 against 16.3, **+12.1 [+10.3, +14.3]** (BCa 95%, paired by seed), better on every seed.
  - **K2, the persistence:** memory-category orbit ticks 66.8 against 1,157, a ratio of **0.06** (bound 0.5); −1,090 [−1,174, −971] per run. Orbits 1.4 against 51.3; orbit share 0.05 against 0.44; mean memory influence 0.14 against 0.41.
  - **K3, against no steering:** 28.4 against 27.3, **+1.1 [−1.5, +3.9]**; the bound was a lower end above −2.7 (a tenth of the floor). Distance per find 50.7 against 53.2; reward 198 against 201; unique sites 5.88 against 5.88; wall contact 0.36 against 0.44.
  - **Predictions:** the pilot's direction and the choice of U = 4 held; K1 passed above the predicted 3–8 finds; K2 passed (67 against the predicted "under 600"); **K3 was predicted to fail narrowly and passed**: with U = 4 the steering matches no steering on this task instead of falling short of it. It does not beat it: the interval includes 0.
- **Adopting U = 4 would not move the research baselines.** The gate's 200-tick open-field run and the 3,000-tick walk at seed 1337 see no reward, so R stays 0 and the unlearning rate never acts: the trace hash is identical with U = 4 (checked at this commit). The field would appear in the profile diff and the manifests, nothing else.
- **Exploratory, not preregistered: the beacon on the research profile at U = 4** (`experiments/console_ablation.py --set place.reward_unlearning_rate=4`, seeds 1–8, in `runs/`, not committed). Memory-orbit ticks 57 against 884 at U = 0.5: the persistence goes there too. Beacons reached 15.6 against 12.0 at U = 0.5, still below no steering's 21.5 (−5.9 [−9.6, −2.6]), distance per beacon 96.6 against 76.5. Where the reward always moves on, a spatial memory that is not revisited is not unlearned, and the remaining cost is not persistence (memory influence 0.07); the legacy notes already say memory does not help this chase.

### C. Decisions this surfaces (recommended default in bold)
1. **Decision table, first row: K1, K2 and K3 pass.** **G41 recommends `place.reward_unlearning_rate = 4.0` as the research profile's default**; adopting it is the owner's call. It costs no baseline regeneration (B), adds one row to the profile diff and one field to every manifest, and the G36 gate's result stands (the gate rewards at a goal the agent arrives at; an unlearning rate changes nothing on a rewarded tick and the gate's trials are short). Until adopted, the knob is explicit configuration, as the M2b features were before G37.
2. **What this does and does not show.** It removes the persistence and restores the finds to the no-steer level on hidden food; it does not show the SR steering beating no steering there, and on the beacon the steering still costs. Hidden food on the research profile is a task the perimeter loop solves (27 finds without memory); the value source's benefit was shown where the loop does not solve the task (the gate: 98.7% against 5%). **M3's protocols should be of the second kind**, and the circling instrument runs on every one of them.
3. **The pilot's seeds 1–8 are now spent for this question**; a later change to the rule is tested on seeds the pilot and the confirmatory did not use (17 onward), as here.

### D. Residuals carried forward
- U = 4 was the top of the pilot's range; the dose curve had not turned over (finds still rising, memory-orbit ticks 65). A higher rate may be better still or may start to erase value the agent needs; not measured.
- One task and one profile. The legacy profile does not read the SR, so it is untouched by the knob.
- The unlearning rate applies to ticks with reward exactly 0; a shaped (approach) reward on the research profile would keep the learning rate in force (hidden food's and the maze's `approach_weight` are 0 under the scenarios' own settings where it matters; a task with shaping should say which rate it wants).

### E. Acceptance, measured at this commit
- `python3 -m pytest -q`: 639 passed; the determinism baselines unchanged (default None).
- `docs/data/console_ablation/sr_unlearning_pilot/` and `sr_unlearning_confirmatory/` regenerate from the commands in the preregistration (17 s and 10 s on four workers).

**Impact:** this entry; `docs/prereg/sr_unlearning_rate.md` (new); `core/config.py` (`PlaceConfig.reward_unlearning_rate`), `core/engine.py` (`_sr_learn`); `experiments/sr_unlearning.py` (new), `experiments/console_ablation.py` (arm tables); `ui/sim_session.py` (the slider); tests in `tests/engine/`, `tests/experiments/`; docs/profiles.md (the reward-rule row), `docs/data/console_ablation/README.md`, README. No profile default change: the recommendation is C1.

## G42 — Before adopting G41's default: the gate does not stand unchanged; the unlearning rate is a stability–plasticity tradeoff

**Date:** 2026-10-26  
**Why:** The owner accepted G41's recommendations (2026-10-26). C1, adopting `place.reward_unlearning_rate = 4.0` as the research default, rested on a claim G41 did not measure: that the RQ4(a) gate's result stands under U = 4 because "an unlearning rate changes nothing on a rewarded tick and the gate's trials are short". The gate builds on the research profile, so it was measured first.

### A. What landed
1. **The gate reproduces as registered whatever the profile's default** (`31d10d7`): `gate_config` sets `reward_unlearning_rate` explicitly (None, one rate, as both gate preregistrations ran), the preregistration table records it, and `--reward-unlearning-rate` runs an exploratory variant (marked exploratory in its manifest). Seed 31's hidden SR session reproduces the committed confirmatory trial by trial.
2. **The gate at U = 1, 2 and 4** on the confirmatory seeds 31–60, SR source, per-feature rule, exploratory, from the clean tree at `31d10d7`: `docs/data/m2b/gate_confirmatory/exploratory_unlearning_u{1,2,4}/`.

### B. Measured (trials 21–40; paired by seed against the committed confirmatory, BCa 95%)

| U | hidden | visible | hidden ÷ visible | hidden − registered | worse on | learning-half hidden | hidden-food finds (G41 pilot, seeds 1–8) | memory-orbit ticks |
|---|---|---|---|---|---|---|---|---|
| 0.5 (registered) | 98.7% | 100% | 0.987 | — | — | 0.91 | 17.6 | 1,254 |
| 1 | 98.5% | 99.3% | 0.992 | −0.002 [−0.010, +0.007] | 13% | 0.91 | 19.6 | 574 |
| 2 | 96.7% | 96.7% | 1.000 | −0.020 [−0.042, −0.003] | 27% | 0.89 | 23.4 | 221 |
| 4 | 85.8% | 93.7% | 0.916 [0.865, 0.967] | −0.128 [−0.167, −0.093] | 83% | 0.76 | 27.3 | 65 |

- **G41 C1's claim was wrong.** At U = 4 the gate still passes its bound (0.916 ≥ 0.8; hidden success also clears the plan's original absolute 80%) and the arrival error is unchanged (0.198 units), but hidden-goal success falls 12.8 points, worse on 25 of 30 seeds, and learning is slower (0.76 against 0.91 over trials 1–20). An unlearning rate acts on every unrewarded tick, and in the gate those are most of the ticks the value has to carry the agent through. Median latency is unchanged (14–15 ticks): the successes are as direct, there are fewer of them. The mechanism is not diagnosed further here.
- **The rate trades one task against the other, monotonically.** A stable goal (the gate) wants slow unlearning; a reward that empties and regrows (hidden food) wants fast unlearning. U = 1 costs the gate nothing measurable and removes over half of the persistence; U = 2 costs the gate 2 points and removes 82% of it; U = 4 removes 95% of it and costs the gate 13 points.

### C. Decisions
1. **The research default is not changed by this entry**: the premise the owner accepted it on was wrong, so the choice goes back to the owner with the table above (recorded in the next entry).
2. **G41 C2, accepted by the owner:** M3's protocols are of the gate's kind (a task the perimeter loop does not solve, with the value source's benefit measurable against no steering), and the circling instrument (G40) runs on every one of them. Recorded in docs/research_plan.md's row 3.
3. **G41 C3, accepted by the owner:** a later change to the SR's reward rule is tested on hidden-food seeds from 17 onward (1–16 are spent on G41), and on gate seeds from 61 onward (1–60 are spent on G36 and on this entry).

**Impact:** this entry; `experiments/rq4a_gate.py` (`31d10d7`); `docs/data/m2b/gate_confirmatory/exploratory_unlearning_u{1,2,4}/`; docs/research_plan.md (row 3).

## G43 — The owner's choice: the instrument keeps one rate; hidden food and beacon carry U = 4 as their own setting

> **Note (G46, 2026-10-27):** "level with no steering" held only with the hidden sites sensed (G46 D2).

**Date:** 2026-10-26  
**Why:** G42 measured the tradeoff G41's recommendation had missed (the gate's hidden success at U = 4: 85.8% against 98.7%) and put the default back to the owner with three options: keep the instrument and give the console's renewable-reward scenarios U = 4 (recommended), U = 2 as the research default, or U = 4 as the research default. **The owner chose the first** (2026-10-26).

### A. What landed
1. **`EngineConfig.research()` is unchanged**: `place.reward_unlearning_rate` stays None (one rate), the instrument the RQ4(a) gate passed with and M3 builds on. The research baselines and every committed result are untouched.
2. **`ui.scenarios.RENEWABLE_REWARD_UNLEARNING_RATE = 4.0`**, set by `HiddenFood.config()` and `Beacon.config()` as the scenarios' own setting, alongside their pacing and senses. On the research profile `profile_config` carries it over and the switch lists it ("place.reward_unlearning_rate None → 4"); the Mechanisms list's place entry names the learning and unlearning rates and marks the scenario's own setting; the slider starts at 4. On the legacy profile it is inert (no population, no SR): hidden food and beacon at seed 7 walk the same 800 ticks with and without it (checked). The other four scenarios keep the instrument's rate.
3. **Research notes** for the two scenarios say what the rate does, with the measured numbers, and how to see the difference (drag the slider to 0.5).
4. `docs/data/console_ablation/README.md` says how to reproduce the G40 numbers at a later commit (`--set place.reward_unlearning_rate=0.5`); G40's own data were made before this setting existed. Tests +1 (suite 640).

### B. Measured
- Hidden food on the research profile at U = 4: G41's confirmatory (seeds 9–16): 28.4 finds against 27.3 without steering, memory-category orbit ticks 67 against 1,157 at one rate.
- **The two scenarios as the console now runs them** (seeds 1–8, 3,000 ticks, from the clean tree at `2de623c`; `docs/data/console_ablation/{hidden_food,beacon}_research_scenario_u4/`), steer against no steering, paired, BCa 95%:
  - Hidden food: finds 27.3 against 26.5, +0.8 [−1.9, +5.3]; memory-category orbit ticks 65 a run (1,254 at one rate, G40); mean memory influence 0.13 (0.44). The same numbers as G41's pilot U = 4 arm on these seeds, as they must be.
  - Beacon: beacons 15.6 against 21.5, −5.9 [−9.6, −2.6]; memory-category orbit ticks 57 (884 at one rate); influence 0.07 (0.31). The circling goes; the steering still costs where the beacon has always moved on, and that cost is not persistence.

### C. What follows
- M3 runs on the instrument (one rate), on protocols of the gate's kind (G42 C2). Whether replay over the place code resolves the persistence that the unlearning rate removes in the console is a question M3 can ask with the G40 instrument, against these scenario settings.

**Impact:** this entry; `ui/scenarios.py` (the constant, two configs, two notes), `ui/sim_session.py` (the mechanisms detail); `tests/ui/test_sim_session.py`; README, docs/profiles.md, `docs/data/console_ablation/README.md`.

## G44 — M3 step 1: a rodent-like body; it does not run the corridor, the gate holds under it, and the cause is the brain's wall response

**Date:** 2026-10-27  
**Why:** M3 started at the owner's request, with the instruction to close the gaps against RatInABox and RL frameworks (`docs/m3_place_replay.md`). RQ1's track needs the agent to run its own laps; a probe found it crawls (74% TURN, 81% against a wall, 97 ticks a lap against 18). Preregistered (`docs/prereg/m3_body.md`, `4a552c1`; Amendment 1, `461a9dd`, before the run), on the branch `m3-body` from the dev branch's `6b89bb7`.

### A. What landed
1. **`core/body.py`, `BodyConfig`** (`body.model`: `"discrete"`, the default in both profiles, today's body; `"rodent"`): speed and angular velocity as exactly discretised Ornstein–Uhlenbeck processes drifted to the chosen action's targets (RatInABox's coherence times; noise optional, RatInABox's 120°/s and 0.08 m/s in the `rodent` preset), turns in place, wall following, a new `body_motion` stream drawn only when on; `BODY_PRESETS` and `apply_body_preset`. The engine moves its agent with it when set and stills it at `begin_episode`. Both baselines bit-identical (tested).
2. **`experiments/body_characterisation.py`**: the registered track and open-field measures, T1 with BCa intervals. **`experiments/rq4a_gate.py --body`**, the body put down still at each trial start, one committed directory per body; the registered gates reproduce trial by trial.
3. Tests +9 (suite 649). A coverage-binning bug (a body on the +x or +y bound counted in a bin outside the arena) was found in the first registered run and fixed (`015c96d`); the run was repeated from the clean tree and only the coverage rows changed (90 of 1,260).

### B. Measured (`docs/m3_place_replay.md`, step 1)
- **T1 fails for every body**: 101.6 (discrete), 112.9 (rodent_quiet), 150.6 (rodent) ticks per lap against 36. **The registered decision: the body is not adopted.**
- **The gate holds under both rodent bodies** on fresh seeds 61–90: SR hidden 99.8%, ratio 0.998; but under RatInABox's noise the no-steering control finds the hidden goal on 66.5% of trials (9.3% quiet, 5% discrete): the noise turns the gate's control into a near-pass.
- **The cause is the brain** (exploratory, seeds 101–104, disclosed): the agent dithers between left and right turns at the track's ends, and reads side walls as ahead out to 1.2 m. A 0.2 m wall range with a turn commitment of 0.3 runs the corridor in 33 ticks a lap with the discrete body.

### C. Decisions this surfaces (recommended default in bold)
1. **Step 1b, before falling back to forced laps**: preregister the two brain-side changes (`basal_ganglia.wall_avoid_range`, `basal_ganglia.turn_commitment`) on fresh seeds, with every body, and the gate under them. The registered row's fallback (forced laps) stays the fallback.
2. **RatInABox's noise statistics are not a free realism upgrade.** They fit open-field foraging; at this tick length they put about 0.4 rad of heading noise on every tick, which a corridor cannot absorb and which lets an agent without value steering find a hidden goal by coverage. **Keep the `rodent` preset as an option, not a candidate default**, and if noise is wanted, characterise it against running (not foraging) statistics first.
3. **The quiet rodent body earns its place on its merits only if step 1b shows it**: it removes the turning circle and smooths speed, but on the track it was no better than the discrete body, with or without the brain fix.

**Impact:** this entry; `docs/m3_place_replay.md` (new), `docs/prereg/m3_body.md` (new); `core/body.py` (new), `core/config.py` (`BodyConfig`), `core/engine.py`; `experiments/body_characterisation.py` (new), `experiments/rq4a_gate.py`; tests `tests/engine/test_body.py`, `tests/experiments/test_body_characterisation.py` (new), `tests/experiments/test_rq4a_gate.py`; `docs/data/m3/body/` (new).

## G45 — M3 step 1b: the corridor options run the track and break the approach to a visible target

**Date:** 2026-10-27  
**Why:** G44 traced the crawl on the track to the action selection (left/right dithering at the ends, a wall signal reaching 1.2 m). Preregistered (`docs/prereg/m3_corridor.md`, `a64bef1`; Amendment 1, `0a41a53`), values from G44's disclosed probe, on fresh seeds.

### A. What landed
1. **`basal_ganglia.wall_avoid_range`** (the fraction of the vision range within which a wall on the centre ray counts as ahead; 1.0 is every result to date) and **`basal_ganglia.turn_commitment`** (added to the previous tick's turn while a wall is ahead; 0 off), threaded through selection, the engine (`previous_action`), the decision log and the console (a `commit` term; the terms still sum to the scores, pinned on a run where it fires). Both baselines bit-identical.
2. `body_characterisation --condition-set corridor`; `rq4a_gate --corridor` and its preregistration entry.
3. **The Observation contract** allowed ±3.14159 for a one-tick turn while the sensor clamps to ±π: aligned to ±π (as the heading), after the first attempt crashed on it. The cause was **a fault in G44's body**: at a corner its wall following takes the walls one after the other, so their turns add (2.6 rad in one tick at seed 54). Not fixed here (the registered conditions run as built); recorded for the next body step.
4. Tests +2 (suite 651).

### B. Measured (`docs/m3_place_replay.md`, step 1b)
- **T1 passes**: the discrete body with the options runs the track in 33.3 [32.9, 33.8] ticks a lap, stalls 0.2%. The quiet rodent body misses narrowly (38.3), the noisy one does not come close (62.4).
- **G1 passes by its letter and fails in substance**: SR hidden 98.2% (discrete) and 100% (quiet rodent), but visible success 11.8% and 26.2% (100% at the registered gate), so the relative ratio (8.3, 3.8) is meaningless. The no-steering control stays under 20% (9.8%, 15.7%).

### C. Decisions this surfaces (recommended default in bold)
1. **The registered reading is the table's second row**: the options cost navigation; **diagnose before step 2**. The relative gate cannot see a collapse of its own denominator; **a later gate preregistration bounds the visible success as well** (e.g. at least 80% of the registered gate's).
2. **Where the options belong** is the owner's call after the diagnosis. Candidates: (a) a protocol setting of the track only, declared like a scenario's own settings, with the research profile unchanged for open-field tasks; (b) a fix that keeps the corridor and restores the visible approach, preregistered; (c) forced laps (G35), step 1's fallback.
3. **The body's corner fault** is fixed before any rodent body is offered as a default.

**Impact:** this entry; `docs/prereg/m3_corridor.md` (new); `brain/systems/basal_ganglia.py`, `brain/contracts.py`, `core/config.py`, `core/engine.py`, `metrics/decisions.py`, `ui/sim_session.py`, `ui/static/js/brain.js`; `experiments/body_characterisation.py`, `experiments/rq4a_gate.py`; tests in `tests/engine/`, `tests/brain/`, `tests/experiments/`; `docs/data/m3/corridor/` (new).

## G46 — The audit: nothing hidden is sensed any more; the hidden-food memory benefit was the leak's; the gate needs its start anchor

**Date:** 2026-10-27  
**Why:** Before choosing G45's route for step 2, the owner asked whether the agent is allowed to cheat ("I want the behaviours to be emergent, not programmed"). An independent read of the code traced every input of the brain to its source; every finding was re-measured (`tools/g46_audit.py`, exploratory, spent seeds); the fixes and a retest were preregistered (`docs/prereg/g46_retest.md`, `68d5461`) and run on fresh seeds (`docs/data/g46/`).

### A. What the audit found
1. **Clean.** The brain never reads the true position, the goal's position, the trial number or its phase. On the research profile DA and 5HT reach nothing (hidden-food runs are byte-identical with approach shaping off). The gate's success test is the engine's contact rule. Withholding the trial boundaries from the learners changes nothing (0.988 against 0.979, seeds 31–42).
2. **Leak 1 (both profiles): hidden food was sensed.** A vision ray stopped at a "hidden" or eaten ("collected") object and reported its kind; the action selection ignores the kind but reads each side's openness from any ray's distance, so a hidden site on a side ray read as an obstacle and the wall-escape turn went away from it. G19 says the rays hit hidden objects and "the policy ignores the kind": true of the label, not of the distance. `experiments/protocols/foraging.py` calls an eaten item "invisible to vision"; it was not.
3. **Leak 2 (legacy only): a hot/cold signal.** Approach shaping rewarded closing the true distance to hidden food, and on the legacy profile the shaped reward reaches action selection through DA and 5HT. **G41 D is wrong** that hidden food's `approach_weight` is 0 under the scenario's settings: it is 1.0.
4. **Declared but never weighed: the gate tells the agent where it is put down** (the true start pose is written into the estimate at every trial start; `docs/prereg/m2b_gate.md`, G36 D).
5. **Built in, task-blind, declared; kept and recorded here.** The approach to anything labelled "target" is a reflex, and the cue gate mutes memory while one is in view, so the gate's visible session measures that reflex, and after a missed hidden trial the goal is shown and the reflex brings the agent in. Vision hands the agent object labels. The place population and the wall reset know the arena's extent (G33, G37). The rodent body's wall following and the corridor options are motor rules (G44, G45). Each gate trial's first tick repeated the previous trial's last action from the new start (one tick; `still_start` from here).

### B. What landed
1. **`sensors.unseen_block_rays`** (a hidden or eaten object is not seen: rays and whiskers pass through it) and **`reward.shape_hidden`** (shaping reads visible targets only; a hidden goal still rewards on contact): **False on the research profile, True on legacy**, which keeps its recorded behaviour. `docs/profiles.md`, the profile-diff test.
2. Every registration before G46 pins the old sensing (`rq4a_gate.PREREGS[...]["pre_g46"]`, `sr_unlearning.PRE_G46`): the confirmatory gate's committed rows regenerate exactly (0 of 960 rows differ; 426 differ with the fix). `docs/data/console_ablation/README.md` says how to regenerate its research hidden-food tables.
3. `rq4a_gate`: `start_estimate` (`anchor`, `centre`, `carry`), `estimate` and `still_start`. `experiments/g46_retest.py`; `tools/g46_audit.py`. Tests +15 (suite 666); both determinism baselines unchanged (they hold no hidden object).

### C. Measured (preregistered, fresh seeds)
**Hidden food**, seeds 17–46, finds per 3,000 ticks (memory steering on the research profile is the scenario's U = 4; legacy at sensor noise 0.03, G23's setting B):

| profile, sensing | no memory steering | memory steering | steering − none [95% CI] | seeds steering wins |
|---|---|---|---|---|
| research, sites sensed (as before) | 28.8 | 28.2 | −0.6 [−2.6, +1.0] | 12 / 30 |
| **research, G46** | **53.0** | **41.2** | **−11.8 [−13.7, −9.8]** | **0 / 30** |
| research, G46, one rate | 53.0 | 21.4 | −31.6 [−33.5, −29.6] | 0 / 30 |
| legacy, as recorded | 3.8 | 10.6 | +6.8 [+5.2, +8.2] (× 2.81 [2.27, 3.49]) | 28 / 30 |
| legacy, rays fixed | 42.2 | 20.1 | −22.1 [−23.3, −20.9] (× 0.48) | 0 / 30 |
| **legacy, both fixed** | **40.8** | **19.4** | **−21.5 [−22.5, −20.5] (× 0.47)** | **0 / 30** |

H1–H5 hold. **The leak held the agent away from food**: with nothing sensed, the agent without memory finds 24 (research) and 37 (legacy) more items per run, and memory steering, which takes it back to sites it has just emptied, loses on every seed. The rays carry the reversal; the shaping only added finds to both legacy arms.

**The gate**, seeds 125–154, the confirmatory settings with the sensing fixed and trials started still; success over trials 21–40:

| told at each trial start | SR hidden | SR visible | tabular hidden | no steering, hidden | SR − no steering [95% CI] |
|---|---|---|---|---|---|
| **the true start (registered)** | **99.8%** | 100% | 84% | 3.5% | +0.96 [+0.95, +0.97] |
| the arena's centre | 37.3% | 86% | 70% | 3.5% | +0.34 [+0.30, +0.38] |
| nothing (carry) | 37.7% | 95% | 63% | 3.5% | +0.34 [+0.29, +0.39] |
| nothing, no heading oracle, no wall reset | 6.2% | 60% | 5.2% | 3.5% | +0.03 [+0.00, +0.06] |

G1 holds (hidden ÷ visible 0.998 [0.990, 1.0], arrival error 0.18 units). G2 holds. **G3 fails as written**: with no aid at all the SR still beats no steering, by 2.7 points [0.3, 5.5] (predicted: not above), near the floor; the estimate there ends 52 units from the body on arrival (it leaves the arena: the integrated heading drifts and nothing resets it). Without the anchor the tabular map degrades less (84% to 63–70%) than the SR (99.8% to 37%), not analysed here.

**Memory maze, exploratory** (G23's claim 3 at setting B, seeds 1–8, the legacy maze with the hidden goal not sensed, by patching the ray): headings recalling 15.75 to 15.5 (gain 0.8) and 15.75 to 15.4 (gain 1.5) of 16; recall rate 0.999 both ways. The maze's recall does not rest on the leak (it rests on the goal vector, declared, G18).

### D. What this changes in the record
1. **Withdrawn: the hidden-food memory benefit** (README; G19, G21; G23 claim 1's × 2.91), a product of leak 1 (and, on legacy, leak 2). Replaced by C: **on hidden food, memory steering costs finds on both profiles.**
2. **Withdrawn: G41 K3 and G43's "at U = 4 steering is level with no steering"**: level only because the leak held no steering down; without it U = 4 steering is 11.8 finds below. The scenario keeps U = 4 for now; re-choosing it is a separate question.
3. **Qualified: the RQ4(a) gate** (G36, G37, G44, G45) tests the use of a place memory *given the start*. Its 98–100% needs the start anchor (62 points of it); without the anchor and the declared aids the place memory barely helps. From here **every M3 result is reported with and without the anchor**, and something the agent can sense and localise from is the route to removing it.
4. **Corrected: G41 D's `approach_weight`** (1.0 for hidden food, not 0).

### E. Decisions
1. **The owner's choice on G45 C2: (b)**, one wall response for every task, preregistered under four rules: one configuration for every task (nothing knows which task it is in); reflex settings fixed before the run from outside the results; all tasks pass together (track, visible goal, hidden goal, open field); a no-learning control in every task, a behaviour counting as emergent only by its margin over it. The audit came first, at the owner's request.
2. **The legacy profile keeps both leaks** as its recorded behaviour (so every legacy result regenerates); its claims are read through D. Fixing legacy too is the owner's call.
3. **Next, at the owner's request: obstacles in the arena, then a retest.** The world has no solid object today (the agent walks through every object; only the arena bounds stop it), so obstacles need collision, a sensed solid kind and a task-blind response to it.

**Impact:** this entry; `docs/prereg/g46_retest.md` (new); `core/config.py`, `core/sensors.py`, `core/engine.py`; `experiments/rq4a_gate.py`, `experiments/sr_unlearning.py`, `experiments/g46_retest.py` (new); `tools/g46_audit.py` (new); `docs/profiles.md`, `docs/data/console_ablation/README.md`, `docs/data/g46/` (new), `docs/m3_place_replay.md`, README; notes under G19, G21, G23, G41, G43; tests in `tests/engine/`, `tests/experiments/`.

## G47 — Obstacles, part 1: solid barriers; the learned memory gets round a wall it was never told about, by following it

> **Note (G48, 2026-10-27):** the 82% below leaned on a slide the agent could not feel, which carried its estimate through the wall toward the goal; with sideways odometry the same agent gets round from the blocked starts on 33% (G48 C4). The headline is withdrawn as stated.

**Date:** 2026-10-27  
**Why:** The owner's next step after G46, "bring in obstacles and retest", scoped with the owner as barriers first, then the agent learning to locate itself from what it sees. The world had no solid object (the agent walked through every object; only the arena bounds stopped it). Preregistered (`docs/prereg/g47_barrier_gate.md`, `95eb7c9`) after a disclosed pilot on spent seeds (`docs/data/g47/pilot/`); run on fresh seeds 155–184 (`docs/data/g47/confirmatory/`).

### A. What landed (`fb6589f`)
1. **`core.world.Barrier`**, a solid axis-aligned rectangle: a move stops just short of the first face it would cross, x leg then y leg, so a move at an angle slides along it and no step tunnels through (`World.constrain`, applied after either body). **Rays and whiskers see it as `"wall"`**: by sight an interior wall is a wall. **The touch sense reports the arena's walls only**, so the declared wall-contact reset never fires against a barrier; that touch tells the two apart is part of that declared aid (G33). Odometry is the true displacement, so a blocked body feels it did not move. With no barrier nothing changes (both determinism baselines bit-identical).
2. `rq4a_gate`: `LAYOUTS` (`open`; `L`, two walls shielding the goal's south and west sides with a 3-unit gap at each free end), `blocked_starts` (the west and south starts' straight lines meet a wall), `run_session(layout=...)`. `experiments/g47_barrier_gate.py` (pilot and confirmatory phases). Tests +12 (suite 677).
3. Nothing in the agent was changed or tuned for the task: the research profile as G46 left it, its wall reflex treating a barrier as any wall (G46 E1's rules).

### B. Measured (preregistered, fresh seeds; hidden success over trials 21–40, blocked / direct starts)

| arena, start estimate | SR | tabular | no steering | visible, SR | visible, no steering |
|---|---|---|---|---|---|
| open, told the start | 1.00 / 1.00 | 0.87 / 0.81 | 0.03 / 0.02 | 1.00 / 1.00 | 0.55 / 0.68 |
| **L, told the start** | **0.82 / 0.89** | 0.81 / 0.85 | 0.03 / 0.02 | 0.94 / 0.94 | 0.52 / 0.64 |
| open, told nothing | 0.39 / 0.25 | 0.66 / 0.60 | 0.03 / 0.02 | 0.92 / 0.99 | 0.55 / 0.68 |
| L, told nothing | 0.41 / 0.09 | 0.54 / 0.61 | 0.03 / 0.02 | 0.82 / 0.86 | 0.52 / 0.64 |

- **B1 holds**: the gaps are passable; the reflex alone reaches a visible goal from blocked starts on 52% of trials.
- **B2 holds (primary)**: with the start given, the SR gets round the wall from the blocked starts on 82.3% of trials; SR − no steering **+0.79 [+0.72, +0.85]**, 30 of 30 seeds.
- **B3 holds**: the wall costs 17.7 points [−24.0, −12.3] from blocked starts (and 10.7 from direct ones, which pass close to its ends). **The median latency from blocked starts is 139.5 ticks against 20 in the open arena (× 7)**: the way round is found by following the wall, not planned (a straight detour is about 20 ticks).
- **B4 holds**: told nothing, the SR still gets round from blocked starts on 41.3% (+0.38 [+0.32, +0.44] over no steering). From direct starts it reaches only 9.3% (in the open arena told nothing, 25%): without the anchor the starts differ, which the open arena shows too (39% / 25%).
- **B5 (reported)**: the tabular map is barely hurt by the wall (−0.06 [−0.11, 0.00] blocked, +0.04 direct) and, as in G46, holds up better without the anchor (0.54 / 0.61). The wall costs the visible approach 6 points with the anchor and 10–13 without.

### C. Reading
The agent's learned memory gets it to a hidden goal behind a wall nothing in it knows about, with the control at the floor: under G46 E1's rules that way round is the agent's own. It is found by following the wall (latency × 7), the wall reflex doing the turning and the memory the pulling; a route planned round the wall would show in a path-efficiency measure and in a shortcut test (the wall removed after learning), neither run here. The anchor still carries most of the success (41% told nothing, 82% told the start).

### D. Decisions this surfaces
1. **Next, the owner's second part: the agent locating itself from what it sees**, learned, not given (a preregistered step), measured against this table's "told nothing" rows.
2. A path-efficiency measure and a shortcut test are candidates after it.
3. The console does not draw barriers yet (they are an experiment's arena only).

**Impact:** this entry; `docs/prereg/g47_barrier_gate.md` (new); `core/world.py`, `core/sensors.py`, `core/engine.py`; `experiments/rq4a_gate.py`, `experiments/g47_barrier_gate.py` (new); `docs/data/g47/` (new); README, `docs/m3_place_replay.md`; tests in `tests/engine/test_barriers.py` (new), `tests/experiments/`.

## G48 — Obstacles, part 2: a cue map the agent builds itself gives back what the start anchor gave; G47's way round the wall leaned on a slide it could not feel

**Date:** 2026-10-27  
**Why:** The owner's second part, scoped with the owner as *position from cues* (the heading oracle stays declared): can a map of distal cues the agent learns replace the start anchor G46 found the gate leaning on? Preregistered (`docs/prereg/g48_landmark_gate.md`, `7fd3160`) after three disclosed pilots on spent seeds; run on fresh seeds 185–214 (`docs/data/g48/confirmatory/`).

### A. What landed
1. **Distal cues** (`core.world.Cue`; four in `rq4a_gate.CUES`, outside the arena, placed without symmetry), **seen** as a name, a bearing and a distance with seeded errors (`sensors.landmark_sensing`: 300° field, sd 0.05 rad, sd 10%; never a position), and **a learned cue map** in the spatial system (`spatial.landmark_gain` 0.1, `landmark_learning_rate` 0.01, `landmark_min_sightings` 20): each sighting places the cue where the estimate says it is; a learned cue pulls the estimate toward where it puts the agent. The map starts empty; learn it slowly and correct the self fast (cues stay put, the estimate drifts), set from that reason before any run.
2. **Sideways odometry** (`sensors.lateral_odometry`): the displacement perpendicular to the heading. The first pilot found the cue map drifting in the L arena (0.2 to 2.7 units over a session): a body sliding along a barrier it pushes into moves partly sideways, the egomotion carried only the part along the heading, and the estimate, and from it the map, took a bias it could not see. A rat feels its sideways motion; a missing sense, added and disclosed, not a setting tuned.
3. All opt-in; the Observation's new fields are out of the checksum while None; both determinism baselines bit-identical. `rq4a_gate`: `gate_config`/`run_session(landmarks=, lateral_odometry=)`, trial rows carry the estimate's error and offsets. `experiments/g48_landmark_gate.py`. Tests +15 (suite 692).

### B. Measured (preregistered, fresh seeds; SR hidden success over trials 21–40)

| condition | all starts | blocked / direct | median ticks, blocked | visible, SR |
|---|---|---|---|---|
| open, told the start, cues off / on | 1.00 / 1.00 | | 20 / 20 | 1.00 / 1.00 |
| open, told nothing, cues off | 0.29 | | 121 | 0.91 |
| **open, told nothing, cues on** | **0.95** | | **26** | 0.96 |
| L, told the start, cues off | 0.42 | 0.33 / 0.50 | 141 | **0.33** |
| L, told the start, cues on | 0.42 | 0.32 / 0.53 | 135 | 0.38 |
| L, told nothing, cues off | 0.22 | 0.34 / 0.09 | 121 | 0.82 |
| **L, told nothing, cues on** | **0.71** | 0.55 / 0.87 | 125 | 0.75 |
| L, told the start, G47's agent | 0.87 | 0.82 / 0.93 | 134 | 0.95 |
| L, told nothing, G47's agent | 0.24 | 0.38 / 0.10 | 117 | 0.85 |

- **C1 holds (primary)**: told nothing in the open arena, the cues lift SR hidden success from 0.29 to 0.95, **+0.66 [+0.62, +0.69], 30 of 30 seeds**, and the latency from 121 ticks to 26 (20 told the start).
- **C2 holds**: told nothing with the cues against told the start without them, −0.05 [−0.07, −0.04].
- **C3 holds**: in the L arena told nothing, the cues add +0.50 [+0.44, +0.55] (blocked starts +0.21, direct +0.79).
- **C4 holds**: in the L arena told the start, the agent that feels its sideways slide gets round the wall from the blocked starts on 0.33 against G47's agent's 0.82, **−0.48 [−0.55, −0.40]** (direct starts −0.42), its estimate error falling from 1.15 to 0.17 units.
- **C5 (reported)**: with the start told, the cues change nothing in either arena (they agree with an estimate already right). They hurt the tabular source in the L arena told nothing (blocked 0.62 to 0.28) and help it in the open (+0.15).
- **C6 (reported)**: told nothing, the cue map is built in the estimate's frame, which starts shifted by the first start's offset, so the error against the body rises with the cues (+2.8 units) while the frame holds better from trial to trial (spread −0.41 open, −0.60 in L): the agent navigates in a frame of its own.
- **Controls**: no steering at or below 0.04 in every condition.

### C. Reading
1. **In the open arena a cue map the agent builds from nothing gives back what the start anchor gave** (95% against 100%, nearly as fast). Nothing about the cues' positions is given; the map's frame is the agent's own.
2. **G47's headline is withdrawn as stated.** Its 82% round the wall leaned on a slide the agent could not feel, which carried its estimate through the wall toward the goal. With the slide felt, 33%.
3. **What remains is in the steering, and it is now plain**: with an accurate estimate in the L arena the agent fails even when it can see the goal (visible 33%, against 95% for G47's agent and 82% told nothing). The value steering reads the value of places ahead of the estimate without regard to walls, so a goal behind a wall pulls the agent into the wall. The tabular source (84% with the start told) does not show it to the same degree; why is not analysed here.

### D. Decisions this surfaces
1. **The start anchor can give way to cues in open-arena protocols** (the owner's call; the anchored rows stay as the reference).
2. **Next candidate: steering that respects walls**, e.g. reading value only where the agent can see it could go, or the successor representation's own transition structure instead of raw value across a wall; preregistered, under G46 E1's rules.
3. Sideways odometry becomes part of any protocol with barriers.

**Impact:** this entry; a note under G47; `docs/prereg/g48_landmark_gate.md` (new); `core/world.py`, `core/sensors.py`, `core/config.py`, `core/engine.py`, `brain/contracts.py`, `brain/systems/spatial.py`; `experiments/rq4a_gate.py`, `experiments/g48_landmark_gate.py` (new); `docs/data/g48/` (new); README, `docs/m3_place_replay.md`; tests in `tests/engine/test_landmarks.py` (new), `tests/sensors/`, `tests/experiments/`.

## G49 — M3 step 2, Part 1: steering that reads only where the agent could go takes it round a wall nearly directly

**Date:** 2026-10-27  
**Why:** G48 D2: in the L arena with an accurate estimate the value steering pulled the agent into the wall, even toward a visible goal, because it reads the value of places one unit ahead whatever lies between. The owner's step 2 (one action selection for every task, G46 E1's rules) with this folded in; an exploration on spent seeds (`tools/m3_step2_probes/`, disclosed) split it in two, and the owner had Part 1 registered and run (`docs/prereg/m3_step2.md`, `b3bc4fe`), with Part 2 kept as a design. Fresh seeds 215–244 (`docs/data/m3/reachable/`).

### A. What landed (`cd298c1`)
1. **`sensors.free_space_sensing`**: the Observation carries `free_space`, the distance to the nearest solid (arena wall or barrier) along each direction of the value fan (`core.sensors.FREE_SPACE_ANGLES`, which the engine checks against `VALUE_FAN_OFFSETS`), exact as the wall rangefinder is.
2. **`value_memory.reachable_probes`**: each direction's probe point is pulled back to 0.05 units short of what the agent sees in that direction, so a place behind a wall is not read as one step away; against a wall a probe reads the place the agent is in. Task-blind; inert without a solid within a unit and without a value source. Both opt-in; both determinism baselines bit-identical.
3. `rq4a_gate.gate_config(overrides=...)`; `experiments/m3_reachable.py`; tests +5 (suite 697).

### B. Measured (preregistered; every condition with sideways odometry, G48; probes off / on)

| task | probes off | probes on |
|---|---|---|
| L arena, told the start, SR hidden, blocked / direct starts | 0.35 / 0.48 | **1.00 / 1.00** |
| median ticks from the blocked starts (open arena: 20) | 134.5 | **39.8** |
| L arena, told the start, SR visible | 0.35 | **1.00** |
| L arena, told nothing with cues, SR hidden (tabular) | 0.68 (0.46) | **0.97** (0.82) |
| open arena, told the start / told nothing with cues, SR hidden | 1.00 / 0.95 | 1.00 / 0.96 |
| hidden food, memory steering / none (finds) | 40.4 / 52.4 | 40.4 / 52.4 |
| track and open field, the reflex alone | | identical |
| no steering, hidden, every condition | ≤ 0.032 | unchanged |

- **R1 holds**: +0.65 [+0.60, +0.71] from the blocked starts. **R2 holds**: × 1.99 the open arena's latency (G47's wall following took × 7). **R3 holds**. **R4 holds**: the open arena moves by 0.017 at most; hidden food, the track and the open field are identical. **R5 holds**.

### C. Reading
The agent's learned memory takes it round a wall nothing in it knows about, nearly directly, from every walled-off start, with no steering at the floor: under G46 E1's rules, an emergent detour. The successor features had learned the way round from experience all along; what the probes change is only that the steering no longer reads the value of a place on the far side of a wall as one step away. Nothing else moved. A shortcut test (the wall removed after learning) is the natural next measurement of whether this is a map or a habit.

### D. Decisions this surfaces
1. **Adopting the instrument** (G49 B's reading rule; the owner's call): sideways odometry, the free-space sense and reachable probes, and with them G48's landmark sense and cue map (inert without cues), into the research profile; the research baselines regenerate once. With it, the four stacked branches (`g46-leaks`, `g47-barriers`, `g48-landmarks`, `m3-step2-draft`) are ready to merge on the owner's say-so.
2. **Part 2** (the wall response and the track) proceeds as the draft lays out, under the owner's decisions: the strict track bound (the reflex alone must not run laps) and a 300° field of view as sensing.

**Impact:** this entry; `docs/prereg/m3_step2.md` (new); `core/config.py`, `core/sensors.py`, `core/engine.py`, `brain/contracts.py`; `experiments/rq4a_gate.py`, `experiments/m3_reachable.py` (new); `tools/m3_step2_probes/` (new); `docs/data/m3/reachable/` (new); README, `docs/m3_place_replay.md`; tests in `tests/engine/test_reachable_probes.py` (new), `tests/sensors/`, `tests/experiments/`.
