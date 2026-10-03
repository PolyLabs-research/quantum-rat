# From toy to instrument: a conversion plan for hippocampal replay and spatial-memory research

**Status:** DRAFT for the owner's approval. Nothing in this plan has been implemented.
**Date:** 2026-10-03
**Basis:** a 14-agent research-readiness audit of the repository at commit `eea946f`
(8 subsystem audits against the literature, 3 competing research programs, 2 judges, 1 completeness critic),
plus the owner's three choices: **spatial memory & replay** as the research line, a **rate-based core with spiking only where a question demands it**, and **publishable results** as the goal.

---

## 1. Where the project actually is

The audit's verdict is unanimous and should be read before anything else:

> Good scaffold, decorative science. The engineering (deterministic engine, named RNG streams, per-tick logging, sweep harness, console) is real. Every brain subsystem is a cartoon of the model it is named after, and several of them interact in ways that confound every behavioural result in the repository.

| Subsystem | Grade | What it actually is | Fate in this plan |
|---|---|---|---|
| Criticality | cartoon | Bond percolation on a 16×16 torus (critical at p = 0.5, defaults at 0.25); κ uses the wrong exponent and never locates criticality; the gain test is tautological; coupling has no effect at defaults. | **Freeze.** Out of the behavioural hash; relabelled honestly. |
| Neuromodulation | cartoon | DA = reward − running mean (not a TD error, teaches nothing); ACh/NE derived from a checksum "novelty" bit that is 1 on every tick under any sensor noise; 5HT is a lagged copy of DA's input. | **Freeze as readouts**, couplings set to 0 in all research assays; later, route the real TD error to the DA channel. |
| Spatial / path integration | cartoon | Exact odometry, scaled by the TRN gate to 0.4 or 0 when ATP is low — so the place estimate freezes while the body moves (85% of core-engine ticks). No place fields, no boundary anchoring. | **Make real** (noisy odometry, boundary reset, place population). |
| Value map / replay | cartoon | TD(0) over 0.5 m bins with a kernel that inflates values (reward 1.0 → V = 10 at radius 1); replay = an experimenter-invoked exhaustive reverse sweep; microsleep replay is dead in every scored scenario. | **Make real** (SR + place features, explicit stochastic prioritized replay events). |
| Action selection | cartoon | Hand-coded four-channel salience arbiter with a deterministic argmax; left-turn chirality in the tie order; the G14–G21 "robustness" lives in gates that rewrite its inputs. | **Freeze** as a documented arbiter; add a seeded softmax temperature. |
| Sleep / energy / TRN | cartoon | Glycogen pinned at 0.03; every microsleep exactly 25 ticks; the gate corrupts path integration; "astrocyte" and "TRN" are names. | **Freeze as environment** after removing the gate–odometry coupling. |
| Sensors / world / tasks | cartoon | Oracle-labelled rangefinder; whiskers computed but never read; no body, no walls beyond a box; headless water maze has no pool and is solved in 5 ticks. | **Make real where the assays need it** (walls, trial structure, standard protocols). |
| Infrastructure / stats | simplified-but-real | Same-platform bit identity; no CIs anywhere; at noise 0, "8 seeds" are 8 copies of one run; no provenance in outputs. | **Upgrade** (statistics module, manifests, packaging). |

### 1.1 What this means for the results already in the repository

The headline numbers of decision-log entries G14–G21 (the steering band, maze recalls, the hidden-food ×2.8, the replay advantage) were measured honestly, but they measure a particular patch stack, not a brain mechanism:

- the memory maze works only because `pace_low = 0.6` keeps the TRN gate from freezing path integration, and `teleport_to_start` hands the agent an oracle re-anchoring every trial;
- the value map's "gradient" is kernel-inflated and lives in a drifting frame;
- the off-axis maze result is mostly the goal-vector slot, not the value map;
- the replay advantage is a single deterministic sample on a knife edge;
- hidden-food "memory" is area-restricted search near recent finds, with roughly a third of the benefit surviving when the sites are moved.

**This plan deletes those mechanisms and retires the tests that pin them.** The owner must accept that up front (see §9). Nothing is lost: the numbers stay in `docs/decisions.md` as the record of what the patch stack did.

### 1.2 Why "spatial memory & replay"

Both judges agree the first month is the same whatever the direction (§5). On what comes next they differ: the neuroscientist judge recommends this line; the engineer judge would start with criticality because its physics is cheapest. The owner chose this line, and the case for it is sound:

- it is the only direction whose phenomena the project has already spent five decision-log entries on, so the console, the scenarios and the owner's intuition carry over;
- the field has a decade of quantitative replay data (direction vs task phase, reward-magnitude modulation, past-goal enrichment, barrier rerouting) and a handful of normative models that explain subsets of it, almost all of them in tabular gridworlds with a perfect state signal;
- its first publishable unit is legitimate even if the embodiment adds nothing new: a head-to-head of replay prioritization rules in a closed-loop agent with noisy, boundary-corrected odometry, with confidence intervals over seeds.

The honest weakness is novelty. George et al. (2023) learn successor representations in continuous space with RatInABox agents; de Cothi et al. (2022) compare model-free/model-based/SR agents to rat trajectories; Sagiv, Akam, Witten & Daw (2025) already derive past-goal replay enrichment from gain × need. Every write-up must say that cue identity is oracle-given and that "embodied" means noisy odometry plus a body in a closed loop — and the informative results will be the **controls** (random replay, trajectory-only replay, no replay), not the effects the chosen rule is built to produce.

---

## 2. The instrument we are building

A continuous-space agent whose

1. **place estimate** is a noisy, boundary-corrected path integrator (not ground truth, not frozen by fatigue);
2. **state representation** is a Gaussian place-cell population with a **successor representation** (SR) learned from its own trajectories by TD (Dayan 1993; Stachenfeld, Botvinick & Gershman 2017), with tabular TD(0) kept as the ablation baseline;
3. **replay** is an explicit, logged, stochastic **event stream** with a pluggable prioritization rule — gain × need (Mattar & Daw 2018), Diekmann & Cheng (2023), random, reverse-trajectory-only (the current mechanism, as a control), none — generating awake events at reward and pauses and sleep events in protocol rest phases, decoupled from the ATP/microsleep machinery;
4. **behaviour** on the standard rodent paradigms is measured with the published metrics, over seeds, with confidence intervals.

Everything else (criticality, neuromodulator scalars, the salience arbiter, the energy model) is frozen as a documented part of the environment.

### 2.1 Where spiking fits

The owner chose "rate core, spiking where it matters." For this research line, spiking does not matter in the first publishable unit: every comparison in §3 is at the level of replay *events* (direction, content, rate, timing relative to reward) and behaviour, which rate models express directly. Spiking becomes necessary only for comparisons at the level of ripples, theta sequences or spike-timing statistics — and those also need oscillations and decoders, which the audit identifies as a separate project. So:

- **Milestones 0–5:** rate-based throughout; no Brian2.
- **Milestone 7 (optional, after the first result):** a spiking CA3-like replay generator (Brian2 is pip-installable here) that consumes the same place population and emits spike-level sequences, so ripple-level statistics (sequence compression, event duration) can be compared with hc-11-style data. It plugs in behind the same replay-event interface, so nothing before it has to change.

---

## 3. Research questions

Each question names its prediction, what would falsify it, and what it is compared against. RQ1 and RQ3 are where the embodiment can show something new; RQ2 is a **replication** of a published model result (Sagiv et al. 2025) and is framed as such; RQ4 is a validation gate, not a finding.

**RQ1 — Replay statistics in an embodied agent.** With gain × need over a learned SR and one parameter set across tasks, logged replay events should show (a) reverse sequences concentrated at reward receipt and forward sequences before runs (Diba & Buzsáki 2007); (b) reverse-replay rate rising with a 4× reward increase and falling with a decrease, forward rate unaffected (Ambrose, Pfeiffer & Foster 2016; direction of effect, not absolute rates); (c) decline with familiarity; (d) a fraction of events starting remote from the agent at past-rewarded sites. *Falsified if* the trajectory-only or random control passes all four, or gain × need fails (b) in the closed loop.

**RQ2 — Replay content vs next choice (replication).** On an 8-arm changing-goal task modelled on Gillespie et al. (2021), replay content should be enriched for the previously rewarded arm and for arms not recently visited, and should *not* predict the next choice; the enrichment should grow with goal uncertainty (Sagiv et al. 2025). *Falsified if* replay content predicts the next choice better than past reward.

**RQ3 — Non-local credit assignment and rerouting.** After a barrier is inserted into a learned route, SR/Dyna replay should reroute around it within a few events without the place population remapping, and the first post-insertion detour should be shorter than for the trajectory-replay or no-replay control (Widloski & Foster 2022; Gupta et al. 2010 for never-taken shortcuts). *Falsified if* rerouting needs remapping or the detour is no better than the controls.

**RQ4 — Standard maze behaviour as a gate.** On a real Morris water maze protocol (pool, 4 starts, 4 trials × 5 days, probe, reversal), escape latency falls monotonically to a floor, probe-trial target-quadrant occupancy exceeds chance, and search strategies shift toward directed/focal search (Vorhees & Williams 2006; Garthe, Behr & Kempermann 2009). *Crowded and arbiter-sensitive*; it is a gate the instrument must pass, not a result to publish. Deferred to after the first result (§4, M4b).

**RQ5 — Dopamine-gated replay rate (optional).** If replay rate is driven by |TD error|, an RPE-gated agent learns a reward change faster than reward-biased or random replay (Roscow et al. 2025), and removing the gate produces aberrant replay at unchanged-reward sites (Kleinman & Foster, eLife). The only place the neuromodulator line re-enters this program.

---

## 4. Milestones

Effort is given in full-time-equivalent (FTE) weeks, using the **engineer judge's** estimates where they exceeded the program's own (the judge found the program's totals ~50% optimistic, chiefly because the replay generator's need term must cover (place × heading) × actions, roughly 8× a gridworld's state space, and because the world layer is 57 lines with no walls or body). Calendar time at 10–15 h/week is roughly 3–4× the FTE figure; at 20 h/week, about 2×.

| # | Milestone | FTE weeks | Acceptance (checkable) |
|---|---|---|---|
| **0** | **Honest base** (§5) | 3–4 | All of §5 done; one baseline regeneration recorded as a decisions-log entry listing every retired test; README and console labels match the code. |
| **1** | **Value rule and odometry** — remove the kernel and dwell extinction; tabular TD(0) and linear TD(λ) over Gaussian place features; seeded multiplicative speed noise and additive angular noise on egomotion; the TRN gate no longer touches path integration; goal vector moved behind an explicit `oracle_homing` flag (off); replay refactored into an event object | 2–3 | On a 12-cell chain with terminal reward 1.0, V(d) = γ^d within 1e-2 for both learners at every feature width (today: 10.0 at radius 1, 4.27 at radius 2). Path-integration error grows ~√distance over 200 m of travel, independent of ATP. |
| **2** | **Place population + SR + boundary reset** — Gaussian place cells over the corrected estimate (RatInABox conventions); SR learned online by TD with V = M·R; wall-contact position reset and landmark heading reset (Hardcastle, Ganguli & Giocomo 2015); rate-map and SR-field metrics; console shows the population and the SR field | 3–4 | After 50 laps on a 1-D track, SR fields skew backward against the running direction (Stachenfeld 2017); near walls, fields elongate along the wall. Decoding error drops at wall contact. *Caveat (engineer judge): the skew bound may fail for kinematic reasons on short tracks with 0.3 rad turns; measure before fixing the threshold.* |
| **3** | **Prioritized replay generator + linear-track assay (RQ1)** — gain × need with SR-based need and a Dyna model over (place × heading) × action; Diekmann–Cheng; random; trajectory-only; none. Stochastic under a named `replay` RNG stream. Awake events at reward/pauses, sleep events in rest phases. Ambrose 2016 track protocol. Replay metrics module. | 7–9 (**the long pole**) | With one parameter set over ≥ 20 seeds: reverse fraction at reward > 0.6 and forward fraction before runs > 0.6; reverse rate up at the 4× end and down at the reduced end with bootstrap 95% CIs excluding zero, forward-rate CI including zero; replay rate falls across laps; ≥ 10% of events start remote. Random and trajectory-only controls fail at least the reward-magnitude and remote effects. |
| **4a** | **Arena geometry + two protocols (RQ2, RQ3)** — polygon walls shared by ray casting and collisions; a body radius; 8-arm changing-goal and barrier-rerouting protocols with trial/probe/ITI/rest phases | 4–5 | Gillespie-style enrichment indices of the right sign and ordering with the upcoming-choice index at chance; post-barrier replay crossing fraction < 0.1 with pre/post field correlation > 0.8; SR + replay detour shorter than controls with paired CIs. |
| **5** | **Statistics, model comparison, first results document** — `analysis/stats.py` (BCa bootstrap CIs, paired effects, Cliff's δ, probability of improvement; a pseudo-replication guard); one tidy (rule, task, seed, metric) table from one runner; run manifests; a results document laid against the published numbers | 2 | Every headline number carries n, a CI and the seed set; the five rules are ranked on every task with paired CIs; a clean checkout on a second machine reproduces the tables within the reported CIs. |
| **4b** | Morris water maze with pool, probe and reversal; Pathfinder-compatible export (RQ4) | 2–3 | As RQ4. Deferred until after the first result; it is a gate. |
| **6** | RPE-gated replay rate (RQ5) | 2 | As RQ5. Optional. |
| **7** | Spiking replay generator behind the same event interface (§2.1) | 4–6 | Sequence compression and event-duration statistics in the range reported for rat ripples. Optional; only after a first result exists. |

**Minimum publishable unit:** M0 + M1 + M2 + M3 + M4a + M5 ≈ **21–27 FTE weeks** → roughly 12–18 months at 10–15 h/week, 8–12 months at 20 h/week. Ship M0, M1 and M2 as tagged releases so each is a visible, usable stopping point; the program's own warning is that M3 is where motivation is most at risk.

**First result it aims at:** a short paper or a Cosyne/CCN-style abstract — *"Prioritized replay in an embodied agent with noisy, boundary-corrected path integration reproduces the reverse-replay reward-magnitude asymmetry (Ambrose et al. 2016) and the past-goal enrichment dissociation (Gillespie et al. 2021); trajectory-only and random replay do not"* — plus the open, deterministic instrument itself, which is the part most likely to be used by others. The fallback, if embodiment adds nothing, is a ReScience-style replication of the Mattar & Daw phenomenon set in an embodied setting, which is still publishable there.

---

## 5. Milestone 0: the honest base (do first, whatever happens later)

Both judges and the critic independently list the same prerequisites. None carries scientific risk; all are needed before any number can be reported with units and a confidence interval.

1. **Declare physical units once** in `EngineConfig`: proposed **1 arena unit = 0.1 m and dt = 0.2 s** (5 Hz). Under that calibration the current 20-unit arena is a 2 m × 2 m open field, full thrust is 0.5 m/s, a turn is 1.5 rad/s, and the maze's 300-tick timeout is the standard 60 s. No constants change; they acquire meaning. Replay events (~100 ms in the animal) are shorter than a tick, which is one reason replay becomes an event object between ticks rather than per-tick dynamics. Check the calibration against rat track-running speeds (0.2–0.6 m/s) before freezing it.
2. **Decouple the TRN gate from path integration** (`sensory_gain = 1.0` in `Engine._spatial_step`, behind a flag). The single largest confound every audit found.
3. **Separate the physics trace from the behavioural hash**: κ, avalanche size, active cells and `replay_index` into their own hashed trace, so criticality and replay internals can change without invalidating behavioural baselines (the log records nine regenerations between B1 and G3 alone).
4. **Make seeds samples**: seeded odometry noise, a seeded softmax temperature on the arbiter, and a guard that refuses multi-seed claims at `sensors.noise = 0` with no stochastic element.
5. **Statistics module** (`analysis/stats.py`): BCa bootstrap CIs, paired per-seed effects, Cliff's δ, IQM and probability of improvement (Agarwal et al. 2021).
6. **Provenance**: every run writes a manifest (git SHA + dirty flag, full `EngineConfig`, seeds, dt, platform, Python version); console scenarios registered as headless protocols that write `ticks.jsonl` + `scene.json` + manifest.
7. **Trial structure as an engine concept** (start-pose lists; trial/probe/ITI/rest phases) shared by the console and the headless runner, which today disagree about what an episode is.
8. **One energy model, not two**: the hard-coded 0.35/0.55/1.1 thresholds move into `TRNConfig`; every assay declares pacing on or off.
9. **Honesty pass** on README (it still says criticality "behaves correctly across regimes", "whiskers drive behaviour", "all four neuromodulators are causal"), console panel labels and reference lines, and the protocol names `morris_water_maze` / `t_maze` / `survival_arena` (retire or rename). Replace the checksum novelty bit.
10. **Commit the audit's probes** as `tools/probes/` with recorded outputs, so the pre-conversion state is reproducible (in progress on branch `research/probes`).
11. **Packaging**: `pyproject.toml`, lockfile, LICENSE, CITATION.cff, CI on Ubuntu + macOS, with the determinism claim restated as same-platform bit identity plus a cross-platform tolerance (numpy enters at M1; BLAS reductions are not bit-portable).
12. **A `research` config profile** distinct from the legacy defaults, so the current acceptance numbers can stay as regression guards while the research configuration evolves.
13. **A written acceptance** in `docs/decisions.md` that the G14–G21 numbers measured a patch stack, listing every retired test.

---

## 6. What gets deleted, frozen or retired

| Removed from the model | Why |
|---|---|
| Kernel smoothing in `ValueMemory` | Inflates values; V is not an expected return. |
| Dwell extinction | A non-stationary reward penalty with no RL or biological reading. |
| TRN gate × egomotion | Freezes the place estimate while the body moves. |
| Goal-vector slot (→ explicit `oracle_homing` control condition) | Did the off-axis maze work the value map was credited with. |
| Microsleep as the replay trigger; pacing as a memory crutch | Replay becomes a protocol-driven event stream; pacing is an environment setting declared per assay. |
| Checksum "novelty" bit; write-only TRN replay buffer; `wm_load` | Not what their names say. |
| Headless `morris_water_maze` / `t_maze` / `survival_arena` | No pool, no T, no sensed hazard; solved in 5 ticks. |
| Tests pinning the above (`test_replay_geometry`, `test_off_axis_maze`, `test_goal_vector`, `test_goal_extinction`, the hidden-food multipliers, parts of the steering guards) | They pin single deterministic samples of removed mechanisms. The count is being measured now; expect roughly a third of the 246. |

Frozen as environment, with honest labels: criticality lattice (coupling gain 0), neuromodulator scalars (coupling gains 0), the salience arbiter (plus softmax), the energy model.

Kept and built on: the World → Observation → Brain boundary, named RNG streams, JSONL logging, the determinism gate (regenerated once per milestone), the sweep harness, the console (re-pointed; the engineer judge budgets 1–2 weeks for the new place-population and replay-event panels).

---

## 7. Publication path and rigor

- **Preregistration**: each RQ gets `docs/prereg/<claim>.md` with hypothesis, metric, config, seed set and CI procedure fixed before the confirmatory run.
- **Comparison discipline**: compare directions and orderings of effects to published summary statistics (decoder outputs have their own biases); absolute rates only with declared units. Published figures first; raw datasets (Gillespie 2021 on Dryad, CRCNS hc-*) later and only if a comparison needs them.
- **References**: `docs/references.bib` with a verification-status field for every entry (being built now). The audit already caught one wrong volume (Kleinman & Foster) and two unverifiable code/data claims.
- **Releases**: a tagged release with a Zenodo DOI per result; the model-comparison table and manifests shipped with it.
- **Venue**: Cosyne / CCN abstract for the first unit; a ReScience-style or eLife Research Advance / PLOS Comp Bio short paper if the controls hold up.

---

## 8. Risks

- **Crowded modelling literature** (Mattar & Daw 2018; Diekmann & Cheng 2023; Antonov et al. 2022; Jensen et al. 2024; Sagiv et al. 2025). The reviewer's first question will be "what does embodiment add?" — the answer must come from the controls and from where the gridworld predictions break.
- **Tautology**: building gain × need and finding reverse replay after reward is what the rule is designed to do. Only the preregistered bounds, the controls and the effects not built in (reward-magnitude asymmetry, remote replay, rerouting) are evidence.
- **M3 is finicky**: function approximation plus a learned SR under a stochastic policy in continuous space, with a heading-dependent Dyna model. Keep tabular TD(0) as the fallback state representation for the replay module.
- **The world layer is thin**: walls, collisions and five trial-structured protocols are 5–6 weeks, not 3.
- **Oracle senses remain**: cue identity is given, not recognised; cue-rotation and landmark-conflict experiments are out of reach without a visual front end this plan deliberately does not build.
- **Solo pace**: ~24 FTE weeks is a year or more of evenings. Ship milestones as releases; M0–M2 are each useful on their own.
- **numpy enters**: same-platform determinism holds; cross-platform bit identity will not. State the scope.

---

## 9. Decisions the owner needs to make

Recommended defaults in bold; the plan assumes them unless told otherwise.

1. **Break the current results?** The plan requires it. **Yes**, with the numbers preserved in the decisions log as the record of the patch stack.
2. **Hours per week and horizon?** Sets which milestone is the first release. The plan is written for **10–15 h/week over 12–18 months**, with M0–M2 as early stopping points.
3. **numpy (and later scipy) as hard dependencies; same-platform determinism as the claim?** **Yes** to both.
4. **Level of comparison?** **Behaviour and replay-event level** first; neural level (ripples, spike timing) only at M7.
5. **Real datasets or published summary statistics?** **Published statistics first**; Dryad/CRCNS data only when a comparison needs them.
6. **Should eating feed the agent?** Today food is reward without nourishment and the agent cannot starve. The critic calls this "the single change that ties the subsystems to one variable." **Not in this program** (it would couple the energy model to every result); parked as a future direction (homeostatic foraging).
7. **Keep the rat framing?** **Yes**, with every claim phrased "in a 2-D point agent with labelled range sensors and noisy odometry."
8. **A collaborator or lab contact?** Strongly recommended before M5: replay-decoding biases and estimator pitfalls are where a solo researcher is most likely to be caught.
9. **Tolerance for a null?** The most likely honest outcome of RQ1–RQ3 is "the embodied results equal the gridworld ones." Preregistration makes that reportable; the instrument is still the contribution.

---

## 10. Immediately after approval

Milestone 0 as a single sprint on this branch, in this order: units → gate decoupling → physics-trace split → seeds-as-samples → stats module → manifests and headless scenarios → trial structure → energy thresholds into config → honesty pass → probes merged → packaging → research profile → the written acceptance entry. One baseline regeneration at the end. Then M1.
