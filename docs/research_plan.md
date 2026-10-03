# From toy to instrument: a conversion plan for hippocampal replay and spatial-memory research

**Status:** revision 2. **M0a is implemented on this branch** (merge commit 27946b6 of its two items, plus decisions entry G22 in `docs/decisions.md`). **M0b has not started**, except items 12 and 14 (the probes and the bibliography), which were needed to write this plan.
**Date:** 2026-10-03
**Basis:** a 14-agent research-readiness audit of the repository at commit `eea946f` (8 subsystem audits against the literature, 3 competing research programs, 2 judges, 1 completeness critic), the owner's three choices (**spatial memory & replay** as the research line, a **rate-based core with spiking only where a question demands it**, **publishable results** as the goal), three independent reviews of revision 1 (a neuroscientist, an engineer, an owner's advocate), and the audit's probes re-run against this commit (`tools/probes/`, outputs recorded).

---

## In plain words

- **What we are building.** An agent that estimates where it is *with error* (like an animal, not like a GPS), learns from its own walking a map of "what usually comes next from here", and replays remembered paths by a rule we can swap out. Every replay is a logged event you can see on the arena in the console.
- **What the first result is.** Which replay rule reproduces a known rat result on a linear track (more backward replay after a bigger reward, Ambrose et al. 2016), with error bars over seeds. That comes after roughly 11–16 full-time weeks of work (§4).
- **What the first *number* is.** Earlier than that: the current memory-maze, steering and hidden-food claims re-measured with 30 seeds and confidence intervals, after M0a and the first two M0b items, roughly four full-time weeks in (§5, M0b item 15).
- **What happens to the console.** It keeps working. The six scenarios run under a profile labelled *legacy*; the *research* profile adds panels and switches the toy mechanisms off. Nothing is deleted.
- **What the first weekend is.** One flag that stops fatigue from freezing the agent's position estimate, a `research` config profile, an honest README, and a decisions-log entry. Tagged `v1.0-honest` (§10).
- **Glossary.** *Successor representation (SR)*: for each place, how often each other place follows it. *Gain × need*: replay first the memories that would change decisions most, weighted by where the agent is likely to be. *Dyna*: learn a small model of the world and rehearse from it. *BCa bootstrap / Cliff's δ*: error bars and effect sizes that do not assume a bell curve. *TOST*: a test that two things are equivalent, not merely "not significantly different". *ReScience*: a journal for careful, reproducible replications.

---

## 1. Where the project actually is

The audit's grades are unanimous. This is the orchestrator's one-sentence summary of them: the engineering (deterministic engine, named RNG streams, per-tick logging, sweep harness, console) is real and graded *simplified-but-real*; all seven brain subsystems are graded *cartoon*, meaning each is a deliberately simplified stand-in for the model it is named after; and several of them interact in ways that confound every behavioural result in the repository. The numbers below are from the probes re-run at `eea946f` (engine defaults, pacing off, 3000 ticks unless stated).

| Subsystem | Grade | What it actually is (measured) | In the research profile |
|---|---|---|---|
| Criticality | cartoon | Bond percolation on a 16×16 torus. At the default coupling 0.25, κ stays within 0.89–1.09 and settles near 0.91; it never exceeds the 1.1 the TRN branch needs, so that branch is dead. κ crosses 1 at coupling ≈ 0.32 with the code's exponent (≈ 0.24 with the 2-D exponent); spanning avalanches first appear at 0.35. `criticality_gain = 1` changes no position in the barren, beacon or foraging worlds (the three probed). | **Off** (gain 0, out of the behavioural hash). Legacy profile keeps it. |
| Neuromodulation | cartoon | DA = reward − running mean (not a TD error; in the open field it sits at exactly 0.5 on every tick at the default noise 0, and within 0.489–0.508 at sensor noise 0.03). ACh/NE come from a checksum "novelty" bit that is 1 on 100% of ticks at sensor noise 0.03. 5HT is a lagged copy of DA's input. | **Off** (coupling gains 0; traces still logged). Later, the real TD error feeds the DA channel (RQ5). |
| Spatial / path integration | cartoon | Exact odometry, scaled by the TRN gate: with pacing off the gate is CLOSED on 85% of ticks, the place estimate captures 27% of the true path and ends 22.8 units (2.3 m) from the body in a 20-unit box. No place fields, no boundary anchoring. | **Rebuilt** (noisy odometry, wall-contact reset, declared heading oracle, place population). |
| Value map / replay | cartoon | TD(0) over 0.5-unit bins with a kernel that inflates values: reward 1.0 gives V = 10.0 at radius 1 and 6.6 at radius 2 after ≥ 1,000 passes (4.6 and 4.3 at the scenarios' 60 passes; γ^d at radius 0). Replay is an experimenter-invoked exhaustive reverse sweep; the microsleep replay buffer is 98% one cell because the estimate is frozen for a median 29 ticks before sleep onset (the gate is CLOSED on a median 25 awake ticks before onset). | **Rebuilt** (SR + place features, explicit stochastic logged replay events). |
| Action selection | cartoon | Hand-coded four-channel salience arbiter with a deterministic argmax; left-turn chirality in the tie order; the G14–G21 "robustness" lives in gates that rewrite its inputs. | **Kept** as a documented arbiter, plus a seeded softmax temperature. |
| Sleep / energy / TRN | cartoon | Glycogen pinned at 0.03 from tick 148 onward; all 50 microsleep bouts exactly 25 ticks; `energy_scale` throttles thrust and turn, so the mean step is 0.088 of nominal and 42.6% of steps are zero. | **Frozen**: ATP at baseline, `energy_scale ≡ 1`, no microsleep; sleep is a protocol rest phase. |
| Sensors / world / tasks | cartoon | Oracle-labelled rangefinder; whiskers computed but never read; no body, no walls beyond a box; the headless water maze has no pool and is solved in 5 ticks at the default heading (1804 at heading π); the T-maze in 6. | **Built where assays need it** (walls, body radius, trial structure, standard protocols). Toy assays renamed, not deleted. |
| Infrastructure / stats | simplified-but-real | Same-platform bit identity; no CIs anywhere; at `sensors.noise = 0` four seeds give identical positions and action sequences; no provenance in outputs. | **Upgraded** (statistics module, manifests, packaging). |

### 1.1 What this means for the results already in the repository

The headline numbers of decision-log entries G14–G21 (the steering band, maze recalls, the hidden-food ×2.8, the replay advantage) were measured honestly, but they measure a particular configuration, not a brain mechanism:

- the memory maze works only because `pace_low = 0.6` keeps the TRN gate from freezing path integration, and `teleport_to_start` hands the agent an oracle re-anchoring every trial;
- the value map's "gradient" is kernel-inflated and lives in a drifting frame;
- the off-axis maze result is mostly the goal-vector slot, not the value map;
- the replay advantage is a single deterministic sample on a knife edge (with `experiments.memory_navigation` defaults the probe found no advantage at all: 13/17/17 ticks to goal with consolidation against 14/15/13 without);
- hidden-food "memory" is area-restricted search near recent finds, with between a twentieth and a quarter of the extra finds surviving when the sites are moved (×1.08 / ×1.47 / ×1.25 against ×2.84 / ×2.85 / ×4.08; on the guard's own runs the fixed-site benefit is 4.5× the reshuffled one).

**This plan does not delete those mechanisms.** They are already configuration flags; the plan gives them a home called the **legacy profile** (today's defaults, labelled) and a **research profile** in which they are off. The console's six scenarios keep running under the legacy profile. No test is retired at Milestone 0. The impact analysis measured what deleting the mechanisms would have cost: 85 of the 264 tests (the 246 at `eea946f` plus the 18 probe characterisation tests) pin those mechanisms or the three toy protocols, and 179 would have survived. Under the legacy profile all 85 keep passing as they are; the only edits are protocol-list rewrites in eleven tests when the toy assays are renamed, and one re-baseline when a hash field changes.

Two of these entries are nonetheless real findings of the "model as experiment" kind and are kept as such: **G19** (place memory pays only where the agent's own exploration would not find the food) and **G16** (value steering can induce resting, diagnosed and fixed). They are the first things to re-measure with confidence intervals (§5, M0b item 15).

### 1.2 Why "spatial memory & replay"

Both judges agree the first weeks are the same whatever the direction (§5). On what comes next they differ: the neuroscientist judge recommends this line; the engineer judge would start with criticality because its physics is cheapest. The owner chose this line, and the case for it is sound:

- it is the only direction whose phenomena the project has already spent five decision-log entries on, so the console, the scenarios and the owner's intuition carry over;
- the field has a decade of quantitative replay data (direction vs task phase, reward-magnitude modulation, past-goal enrichment, barrier rerouting) and a handful of normative models that explain subsets of it, almost all in tabular gridworlds with a perfect state signal;
- its first publishable unit is legitimate even if the embodiment adds nothing new: a head-to-head of replay prioritisation rules in a closed-loop agent with noisy, boundary-corrected odometry, with confidence intervals over seeds.

The honest weakness is novelty. George et al. (2023) learn successor representations in continuous space with RatInABox agents; de Cothi et al. (2022) compare model-free, model-based and SR agents to rat trajectories; Diekmann & Cheng (2023) already run their replay model in an embodied simulator (CoBeL-RL); Sagiv, Akam, Witten & Daw (2025) derive past-goal replay enrichment from gain × need. So the informative comparisons in this program are not "gain × need against random replay" (random and no-replay are floors, and gain × need is built to beat them) but:

1. **the embodiment contrast**: every rule run twice, once with an oracle state (the gridworld condition the published models assume) and once with the embodied estimate, so "what does embodiment change?" is a measured difference, not a claim;
2. **rule discrimination**: gain-only, need-only, full gain × need, its goal-uncertainty variant, |TD-error|-gain and Diekmann–Cheng make *different* pre-stated predictions on the 8-arm and barrier tasks (§3), so the data can rank them;
3. **the floors**: random, legacy reverse-trajectory and no replay, reported so that any "effect" is visible against them.

Every write-up says that cue identity and allocentric heading are oracle-given, and that "embodied" means noisy position odometry plus a body in a closed loop.

---

## 2. The instrument we are building

A continuous-space agent whose

1. **place estimate** is a noisy path integrator with wall-contact position reset (Hardcastle, Ganguli & Giocomo 2015 for the reset only) and a **declared heading oracle**: allocentric heading is given with a small seeded noise, not inferred from landmarks. Without it multi-start tasks (8-arm, water maze) cannot localise, and a visual or landmark front end is out of scope. It is a declared limitation in every write-up;
2. **state representation** is a Gaussian place-cell population over the corrected estimate, with a **successor representation** (SR) learned from its own trajectories by TD (Dayan 1993; Stachenfeld, Botvinick & Gershman 2017), with tabular TD(0) over 0.5-unit bins kept as the ablation baseline;
3. **replay** is an explicit, logged, stochastic **event stream** with a pluggable prioritisation rule, generated at reward-consumption pauses and in protocol rest phases, under a named `replay` RNG stream, decoupled from the ATP/microsleep machinery;
4. **behaviour** on the standard rodent paradigms is measured with the published metrics, over seeds, with confidence intervals.

Everything else (criticality, neuromodulator scalars, the salience arbiter, the energy model) is frozen as a documented part of the environment, in the research profile.

**The replay rules** (one interface, `priority(state, memory) -> weights`):

| Rule | What it prioritises | Role |
|---|---|---|
| gain × need (Mattar & Daw 2018) | expected improvement in the policy × expected future occupancy (an SR row) | the reference rule |
| gain-only | the gain term alone | ablation |
| need-only | the need term alone | ablation |
| gain × need, goal-uncertainty need (Sagiv et al. 2025 variant) | need computed under the agent's uncertainty about which goal is active | the variant that predicts past-goal enrichment |
| \|δ\|-gain | the magnitude of the TD error at each memory (prioritised sweeping; Schaul et al. 2016) | the rule RQ5 gates by dopamine |
| Diekmann & Cheng 2023 | experience strength × similarity × inhibition of return | the main published alternative |
| random | uniform over stored memories | floor |
| reverse-trajectory | the current `consolidate()` sweep (legacy mechanism) | floor and continuity with G-entries |
| none | no replay | floor |

**Event budget.** Each rule runs in two modes. *Fixed budget*: the number of events at each pause is Poisson(λ) with λ shared across rules, so rules differ in content only. *Thresholded*: events continue while the rule's priority exceeds θ, up to a cap, so rules may also differ in rate. Content questions (direction, remote starts, arm enrichment) are tested in fixed-budget mode; rate questions (RQ1(b), RQ1(c), RQ5) in thresholded mode. Both are preregistered.

**Metric definitions** (fixed now so that every later number means the same thing; durations in model seconds under §5 item 6):

| Term | Definition |
|---|---|
| replay event | a sampled sequence of ≥ 4 distinct states spanning ≥ 0.3 m, with a start state, direction (forward / reverse / neither, by the sign of the position–time slope along the track) and a trigger (reward, pause, rest) |
| reward window | the 2 s after reward receipt; events there are counted as "at reward" |
| pre-run window | the 2 s before run onset (speed crosses 0.05 m/s upward) |
| remote event | start state > 0.5 m from the agent's current estimate |
| rate | events per stop (per reward-consumption pause), not per minute, so that rates are comparable across rules and speeds |
| familiarity | lap index on a track; trial index elsewhere |

What a replay event looks like: a JSONL line `{"tick": t, "trigger": "reward", "rule": "gain_need", "states": [...], "direction": "reverse", "start_dist_m": 0.12}` and, in the console, the sequence drawn on the arena as it fires.

### 2.1 Where spiking fits

The owner chose "rate core, spiking where it matters." For this research line spiking does not matter in the first publishable unit: every comparison in §3 is at the level of replay *events* (direction, content, rate, timing relative to reward) and behaviour, which rate models express directly. Spiking becomes necessary only for comparisons at the level of ripples, theta sequences or spike-timing statistics, and those also need oscillations and decoders, which the audit identifies as a separate project. So:

- **Every milestone before M7:** rate-based throughout; no Brian2.
- **Milestone 7, step 0 (rate-level decoder emulation):** before any spiking, render logged replay events as place-population activity and pass them through a Bayesian decoder with the same bins and windows the papers use, so our event statistics carry the same pipeline biases as the data they are compared with (Takigawa et al. 2024 on evaluating replay without ground truth).
- **Milestone 7, step 1 (optional, after the first result):** a spiking CA3-like replay generator (Brian2 is pip-installable here) that consumes the same place population and emits spike-level sequences, so ripple-level statistics (sequence compression, event duration) can be compared with hc-11-style data. It plugs in behind the same replay-event interface, so nothing before it has to change.

---

## 3. Research questions

Each question names its prediction, what would count against it, and what it is compared with. RQ1 is a **replication** of a published phenomenon set under an embodied state estimate, framed as such; RQ2 and RQ3 are the rule-discrimination tests where the program can say something new; RQ4 is a validation gate, not a finding.

**RQ1 — Does the Mattar & Daw phenomenon set survive an embodied state estimate?** With gain × need and one parameter set, logged replay events should show (a) reverse sequences concentrated in the reward window and forward sequences in the pre-run window (Diba & Buzsáki 2007); (b) in thresholded mode, reverse rate per stop rising after a 4× reward increase and falling after a reduction, forward rate unaffected (Ambrose, Pfeiffer & Foster 2016; direction of effect, not absolute rates); (c) decline with familiarity (Cheng & Frank 2008); (d) a fraction of events starting remote at past-rewarded sites. *Positive control:* the same rule with an oracle state must pass (a)–(d), or the implementation is wrong. *Falsified if* the embodied arm loses (b) or (d) while the oracle arm keeps them with the same parameter set. *Informative outcome:* which of (a)–(d) the embodied estimate loses, and whether gain-only or need-only loses the same ones (expected from Mattar & Daw: need-only loses (b), gain-only loses (d) and the forward part of (a)). Random, reverse-trajectory and none are reported as floors; they are not the test.

**RQ2 — Which rule's replay content matches the 8-arm data?** On an 8-arm changing-goal task modelled on Gillespie et al. (2021), the data show replay enriched for the previously rewarded arm and for arms not recently visited, with the upcoming choice at chance. Pre-stated predictions: plain **gain × need** predicts enrichment for the *upcoming* choice (it replays what is about to be useful), so it should fail the data; the **goal-uncertainty variant** predicts past-goal enrichment with the upcoming choice at chance; **Diekmann–Cheng** predicts not-recently-visited enrichment through inhibition of return; **random** predicts nothing. The three indices (previous-goal, not-recently-visited and upcoming-choice arm) are computed from events in the reward window at the wells against a per-arm shuffle chance, as in Gillespie. *The result is the ranking*, reported with paired CIs, and it is informative whichever way it falls; if no rule is distinguished from any other on any index, the task lacks power and the block structure is revised before the confirmatory run.

**RQ3 — Non-local credit assignment and rerouting.** After a barrier is inserted into a learned route, replay should stop crossing the barrier and the first post-insertion detour should be shorter than for the floors (Widloski & Foster 2022; Gupta et al. 2010 for never-taken shortcuts), without the place population remapping. Two variants: **A, perception-updated**, the transition model is edited when the rangefinder sees the barrier; **B, experience-updated**, only a collision edits it. Control: a **virtual barrier** that the rangefinder sees but the body passes through, which separates "replay follows the model" from "replay follows the body". *Falsified if* rerouting needs remapping, or the detour is no better than the floors in both variants.

**RQ4 — Standard maze behaviour as a gate.** (a) At Milestone 2b's exit, from four start poses in a 2 m open field with the embodied estimate, the agent reaches a learned goal within 60 s on ≥ 80% of trials after 20 trials, with median estimate error at arrival < 0.2 m; if it cannot, no replay result that follows is interpretable. (b) Later, a real Morris water maze protocol (pool, 4 starts, 4 trials × 5 days, probe, reversal): escape latency falls monotonically to a floor, probe-trial target-quadrant occupancy exceeds chance, and search strategies shift toward directed and focal search (Vorhees & Williams 2006; Garthe, Behr & Kempermann 2009). Crowded and arbiter-sensitive; a gate, not a result. Deferred to M4b.

**RQ5 — Dopamine-gated replay rate (optional).** Under the |δ|-gain rule in thresholded mode, replay rate rises with the *magnitude* of the TD error, so a reward *decrease* also raises reverse replay; under signed gain × need a decrease lowers it, which is what Ambrose et al. (2016) saw. That is a pre-stated discriminating prediction between the two rules, and it is where the neuromodulator line re-enters: an RPE-gated agent should learn a reward change faster than a reward-biased or random one (Roscow et al. 2025), and removing the gate should produce aberrant replay at unchanged-reward sites (Kleinman & Foster 2025).

---

## 4. Milestones

Effort is in full-time-equivalent (FTE) weeks, using the engineer judge's estimates where they exceeded the program's own. The repository's own history is two bursts: 50 commits between 2025-11-30 and 2025-12-16, then nothing for nine and a half months, then 57 commits on 2026-10-01 to 03. So the honest planning unit is a **burst** (a long weekend to two weeks), not a weekly rate. Every milestone below is sized so that a burst ends with a tagged release and a green suite, and the plan survives a long gap after any of them. Console work is budgeted inside the milestone that needs it.

| # | Milestone | FTE weeks | Tag | Acceptance (checkable) |
|---|---|---|---|---|
| **0a** | **Honest base, first weekend** (§5) | 1–1.5 | `v1.0-honest` | Gate flag, research profile with the energy model frozen, honesty pass, decisions entry G22; suite green under both profiles; one baseline regeneration per profile. |
| **0b** | **Instrument base** (§5) | 4.5–6 | `v1.1-base` | Units, physics-trace split, seeds as samples, stats module, manifests, probes merged, packaging and licence, `docs/references.bib`; **G23, the first CI-bearing table** (§5 item 15). |
| **1** | **Value rule and odometry** — kernel and dwell extinction off in research; tabular TD(0) and linear TD(λ) over Gaussian place features; the odometry noise of M0b item 8 characterised; replay refactored into an event object (no rule yet); the goal-vector slot (already off by default) relabelled `oracle_homing` | 2–3 | `v1.2-value` | 12-cell chain, terminal reward 1.0: tabular V(d) = γ^d within 1e-2 (today 10.0 at radius 1 after convergence); linear features of width ≤ 0.5 cell: V(d) = γ^d within 1e-2; at every width V ≤ 1/(1−γ), V(d) monotone in d, and the maximum error against γ^d falls monotonically as the width shrinks; wider widths report their bias. Path-integration error vs distance has a log-log slope in 0.5–1.5 over 200 m; in the legacy profile with the gate flag off, \|r(error, ATP)\| < 0.1. |
| **2a** | **Tabular replay on the linear track (RQ1, first pass)** — the nine rules of §2 over the existing 0.5-unit bins on a track (box bounds 10 × 0.5, binary heading), both budget modes, the `replay` RNG stream; Ambrose 2016 track protocol with a protocol-local lap counter and a fixed reward-consumption pause; replay metrics module; the (rule, task, seed) variant runner writing one tidy table; **console: replay-event panel** drawn on the arena as each event fires (+0.5–1 wk, included) | 3.5–5 | `v1.3-track-replay` | RQ1 (a)–(d) bounds over ≥ 20 seeds in the tabular state: reverse fraction in the reward window > 0.6, forward fraction in the pre-run window > 0.6; reverse rate per stop up at the 4× end and down at the reduced end with Cliff's δ ≥ 0.3 and BCa 95% CIs excluding zero, forward-rate equivalence by TOST within ±20%; rate falling across laps (thresholded mode); ≥ 10% remote events. The 0.6 and 10% figures are preregistered model-side bounds, not data matches. **This is the first scientific result and the first release with a number in it.** |
| **2b** | **Place population + SR + boundary reset + heading oracle** — Gaussian place cells over the corrected estimate (RatInABox conventions); SR by TD with V = M·R; wall-contact position reset; declared heading oracle; rate-map and SR-field metrics; **console: population and SR-field panels** (+0.5–1 wk, included) | 3.5–5 | `v1.4-place-code` | After 50 laps on the track, SR fields skew backward against the running direction (Stachenfeld 2017); near walls, fields elongate along the wall; decoding error drops at wall contact; **RQ4(a) passes**. Throughput ≥ 1,000 ticks/s with a 400-cell population (today 8,300–8,800 in open worlds without one). *Caveat (engineer judge): the skew bound may fail for kinematic reasons on short tracks with 0.3 rad turns; measure before fixing the threshold.* |
| **3** | **Replay over the place code (RQ1, embodied)** — the same rules with need from an SR row, gain from a softmax place-to-neighbour policy, a Dyna model as an empirical place-to-place table (no heading factor); trial structure as an engine concept (start-pose lists; trial / probe / ITI / rest phases shared by console and headless runner, +1 wk, included, offset by the track protocol, metrics module and variant runner moving to M2a); every rule run with oracle state and with the embodied estimate | 4–6 | `v1.5-place-replay` | RQ1 re-run over the place population with the ablation expectations stated in §3; the tabular-vs-embodied and oracle-vs-embodied differences are themselves reported results with paired CIs. |
| **4a** | **Arena geometry + three protocols (RQ2, RQ3)** — polygon walls shared by ray casting and collisions; a body radius; 8-arm changing-goal (Gillespie 2021), open-field changing-goal (Pfeiffer & Foster 2013), barrier rerouting (Widloski & Foster 2022) with virtual-barrier control | 4–5 | `v1.6-arena` | Gillespie-style enrichment indices per rule with paired CIs and the pre-stated ranking test; post-insertion replay crossing fraction at the barrier line not different from the virtual-barrier control fraction (CI overlap), with the pre-insertion fraction reported, and pre/post field correlation > 0.8; detour shorter than the floors in variant A or B; on the open-field changing-goal protocol, the fraction of pre-run events ending within one field width of the current goal exceeds shuffle chance (Pfeiffer & Foster 2013). |
| **5** | **Model comparison and first results document** — ranking of the rules on every task with paired CIs; manifests shipped; a results document laid against the published numbers; a clean checkout on a second machine reproduces the tables within the reported CIs | 2 | `v2.0-results` | Every headline number carries n, a CI and the seed set; the second-machine reproduction is recorded. |
| **4b** | Morris water maze with pool, probe and reversal; Pathfinder-compatible export with the resampling Pathfinder expects, and a jittered, smoothed control classification to show the heading quantisation does not drive the strategy classes (RQ4(b)) | 2–3 | `v2.1-watermaze` | As RQ4(b). A gate; after the first result. |
| **6** | RPE-gated replay rate (RQ5) | 2 | `v2.2-rpe` | As RQ5. Optional. |
| **7** | Step 0 decoder emulation; step 1 spiking replay generator behind the same event interface (§2.1) | 4–6 | `v3.0-spiking` | Sequence compression and event-duration statistics in the range reported for rat ripples. Optional; only after a first result exists. |

**First scientific result:** M0a + M0b + M1 + M2a ≈ **11–15.5 FTE weeks** (440–620 hours): 7–14 months at 10–15 h/week, 5–7 months at 20 h/week. Nine replay rules on the linear track with CIs, in a tabular state.

**Minimum publishable unit:** + M2b + M3 + M4a + M5 ≈ **24.5–33.5 FTE weeks** (980–1,340 hours): 15–31 months at 10–15 h/week, 11–16 months at 20 h/week. Each tag above is a usable stopping point.

**Compute budget.** Measured on this 4-core box: 8,300–8,800 ticks/s in open worlds and 5,100–6,800 in the memory scenarios on one core, with a 3.3× speed-up from four processes. A comparison of 5 rules × 2 tasks × 30 seeds × 3,000 ticks (900,000 ticks) takes about 2.5 minutes serial today and 25 minutes if the place population slows the engine tenfold. The full RQ1 confirmatory grid (9 rules × 2 budget modes × 2 state conditions × 30 seeds × ~5,000 ticks = 5.4 M ticks) is a quarter of an hour today, and at M2b's acceptance floor of 1,000 ticks/s about 90 minutes serial or half an hour on four cores. Every confirmatory run in this plan fits in an afternoon at these rates (measured on the audit's container; re-measure on the owner's machine).

**First result it aims at:** a short paper or a Cosyne/CCN-style abstract: *"Prioritised replay under an embodied, noisy state estimate: which of the Mattar & Daw phenomena survive, and which rule's content matches the 8-arm data"*, plus the open, deterministic instrument itself, which is the part most likely to be used by others. If the embodied results equal the oracle ones, the fallback is a ReScience-style replication of the Mattar & Daw phenomenon set with the rule ranking, which is still publishable there.

---

## 5. Milestone 0: the honest base

Both judges and the critic independently list the same prerequisites. None carries scientific risk. It is split so that the biggest confound goes away in one weekend and something scientific is visible within the first burst.

### M0a, the first weekend

1. **Decouple the TRN gate from path integration**: `SpatialConfig.gate_scales_egomotion: bool = True` (legacy) and `Engine._spatial_step` passes `sensory_gain = 1.0` when it is False. The single largest confound every audit found. **Done (G22).**
2. **Freeze the energy model in the research profile**: `AstrocyteConfig.scales_motion: bool = True` (legacy) and `TRNConfig.microsleep_enabled: bool = True` (legacy); in `research` both are False, the astrocyte sits at `atp_baseline` so `energy_scale ≡ 1.0`, and sleep exists only as a protocol rest phase. The hard-coded 0.35/0.55/1.1 gate thresholds move into `TRNConfig`. *Acceptance:* over a 3,000-tick open-field run in the research profile, zero microsleep ticks and the realised step equals the commanded thrust on every tick. **Done (G22).**
3. **The `research` config profile** (`EngineConfig.research()`): the three flags above off (`gate_scales_egomotion`, `scales_motion`, `microsleep_enabled`), `generalization_radius = 0`, `goal_vector = False`, `dwell_extinction = 0.0`, criticality and neuromodulator coupling gains 0. The legacy profile is `EngineConfig()` unchanged, labelled. **Done (G22).**
4. **Honesty pass** on README (it still says the criticality statistics "behave correctly across sub-/critical/ super-critical regimes", that "vision/pain/whiskers come from real world geometry and drive behaviour", and that "All four neuromodulators are causal"), on the console panel labels and reference lines, and on the headless protocol names: `morris_water_maze`, `t_maze` and `survival_arena` are renamed with a `_toy` suffix and honest docstrings, and the regression harness is re-pointed to `beacon` and `foraging`. The checksum novelty bit is labelled as what it is. **Done (G22).**
5. **Decisions entry G22**: the legacy/research split, the list of tests that now run under the legacy profile explicitly, and the acceptance that G14–G21 are legacy-profile results. One baseline regeneration for each profile. **Done (G22).**

### M0b, the instrument base

6. **Declare physical units once** in `UnitsConfig(dt_s = 0.2, metres_per_unit = 0.1)`: the current 20-unit arena is a 2 m × 2 m open field, full thrust is 0.5 m/s (only true once energy scaling is pinned, item 2), a turn is 1.5 rad/s (heading is quantised in 0.3 rad steps, a kinematic constraint stated in every write-up), and the maze's 300-tick timeout is the standard 60 s. No constants change; they acquire meaning. Replay events (~100 ms in the animal) are shorter than a tick, which is why replay is an event object between ticks rather than per-tick dynamics. Freeze the calibration only after measuring, under the research profile on the open-field protocol, the realised mean moving-tick speed and the fraction of immobile ticks against rat track-running speeds (0.2–0.6 m/s while running) and stopping-period durations: item 2 removes the ATP cause of slow steps, but the arbiter's REST ticks still make realised speed differ from the nominal.
7. **Separate the physics trace from the behavioural hash**: κ, avalanche size, active cells and `replay_index` into their own hashed trace, so criticality and replay internals can change without invalidating behavioural baselines (the log records nine regenerations between B1 and G3 alone).
8. **Make seeds samples**: seeded multiplicative speed noise and additive angular noise on egomotion (`sensors.noise` already perturbs the rangefinder; this is the odometry counterpart, listed once here and characterised in M1), a seeded softmax temperature on the arbiter, and a guard that refuses multi-seed claims when no stochastic element is on.
9. **numpy enters, with rules**: one `numpy.random.Generator(PCG64(child_seed))` per named stream, child seeds from the existing `core/rng` tree; thread pinning (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS` = 1) set in `core/determinism.py`; float64 only; values cast to Python floats at the `TickData` boundary so logs and hashes keep their types; hashed scalars accumulated in fixed order; the one BLAS product that feeds behaviour (V = M·R) runs single-threaded with the kernel recorded. Measured on this machine (numpy 2.4.6, OpenBLAS 0.3.31): `Generator` draws, element-wise `exp` and numpy's pairwise `sum` are bit-identical across 1, 2 and 4 threads and across forced OpenBLAS kernels; `np.dot` over 2 M elements and a 1500 × 1500 matrix product are not (they differ between thread counts and between kernels) but are repeatable at a fixed thread count and kernel. So matrix products that feed behaviour (the SR read-out V = M·R) run with one BLAS thread and the manifest records the kernel: "same platform" means same CPU family and pinned threads. Two baselines (legacy, research) in `regression/baseline/`; a macOS CI job asserts agreement within a stated tolerance, not bit identity.
10. **Statistics module** (`analysis/stats.py`): BCa bootstrap CIs, paired per-seed effects, Cliff's δ, IQM and probability of improvement (Agarwal et al. 2021), TOST equivalence, and a pseudo-replication guard.
11. **Provenance**: every run writes a manifest (git SHA + dirty flag, full `EngineConfig`, profile name, seeds, dt, platform, Python and numpy versions, BLAS kernel and thread counts, wall-clock and ticks/s); console scenarios registered as headless protocols that write `ticks.jsonl` + `scene.json` + manifest.
12. **Commit the audit's probes** as `tools/probes/` with a characterisation test that they still run. **Done on this branch** (17 probes, their recorded outputs in `tools/probes/README.md`, 18 tests, suite at 264); the numbers in §1 are their output.
13. **Packaging**: `pyproject.toml`, lockfile, `LICENSE` (§9), `CITATION.cff`, CI on Ubuntu + macOS, with the determinism claim restated as same-platform bit identity plus a cross-platform tolerance.
14. **`docs/references.bib`** from the audit's verified list: 110 entries, 100 verified, 8 verified with a correction, 2 unverified (§7). **On this branch now**; later milestones add to it under the same verification rule.
15. **Re-measure G16 / G19 / G21 as the first CI-bearing result**: legacy profile, 30 seeds with odometry noise and softmax on, BCa CIs on the hidden-food multiplier, the steering band and the maze recall rate, written up as decisions entry **G23, "what survives 30 seeds"**. Two or three sessions once items 8 and 10 exist; the first table with a confidence interval in the repository.

Trial structure as an engine concept moves to M3, where the first protocol that needs it lives; M2a's track uses a protocol-local lap counter.

---

## 6. Legacy profile and research profile

Nothing is deleted. Every mechanism below is a configuration flag today or becomes one in M0a, except the two parts marked M1, which M0a leaves as they are; the legacy profile keeps today's behaviour and the research profile switches it off.

| Mechanism | Legacy profile | Research profile | Why it is off in research |
|---|---|---|---|
| Kernel smoothing in `ValueMemory` (`generalization_radius`) | 2 in the maze scenarios | 0 | Inflates values (V = 10 for reward 1); V is not an expected return. |
| Dwell extinction | 0.02 | 0.0 | A non-stationary reward penalty with no RL or biological reading. |
| TRN gate × egomotion | on | off | Freezes the place estimate while the body moves. |
| Goal-vector slot | available (`goal_vector`, default False) | off (`goal_vector = False`, M0a); relabelled `oracle_homing` as an explicit control condition in M1 | Did the off-axis maze work the value map was credited with. |
| Energy scaling of thrust and turn; microsleep | on | off (ATP at baseline) | Makes every latency and path length a physiology artefact; sleep becomes a protocol phase. |
| Microsleep as the replay trigger; pacing | on | off | Replay becomes a protocol-driven event stream; pacing is an environment setting the legacy scenarios declare. |
| Checksum "novelty" bit; TRN replay buffer; `wm_load` | on, labelled | logged, not coupled (M1: in M0a the bit still enters action selection in both profiles through `novelty_gain` 0.2 and a 0.3 turn term; the buffer and `wm_load` are logged only) | Not what their names say. |
| Criticality lattice; neuromodulator scalars | on at defaults (already dormant) | coupling gains 0; traces logged | Dead at defaults; kept as readouts. |
| Headless `morris_water_maze` / `t_maze` / `survival_arena` | renamed `*_toy`, honest docstrings | not used | No pool, no T, no sensed hazard; solved in 5 ticks. |

Tests: the 85 tests that pin legacy mechanisms or toy protocols run under the legacy profile explicitly and keep passing; eleven of them edit a protocol list when the toy assays are renamed. `tests/engine/steering_legacy_hashes.json` is never re-recorded. New research-profile tests sit beside them, and they must do what about sixteen of the existing gates cannot: the barren-world determinism and integration gates (reward 0, value map never written) pass whatever happens to the science, so a research-profile regression needs its own assertions on replay content, value learning and navigation. The determinism gate holds two baselines.

Kept and built on: the World → Observation → Brain boundary, named RNG streams, JSONL logging, the determinism gate (regenerated once per milestone, per profile), the sweep harness, the console (its scenarios under the legacy profile; new panels in M2a and M2b).

---

## 7. Publication path and rigor

- **Preregistration**: each RQ gets `docs/prereg/<claim>.md` with hypothesis, per-rule predictions, metric definitions (§2), budget mode, config, seed set and CI procedure fixed before the confirmatory run.
- **Comparison discipline**: compare directions and orderings of effects to published summary statistics (decoder outputs have their own biases, which M7 step 0 emulates); absolute rates only with declared units. Published figures first; raw datasets (Gillespie 2021 on DANDI 000115, CRCNS hc-3 / hc-11) only if a comparison needs them.
- **References**: `docs/references.bib` carries a `verification` field on every entry. Status at this revision: 110 entries, 100 verified, 8 verified with a correction, 2 unverified. The corrections already caught: Kleinman & Foster is eLife volume 14 (2025), not 12; Krause & Drugowitsch 2022 is Neuron 110(4):722–733; the Gillespie 2021 data are on DANDI, not the 72 GB Dryad release the program text named; "Evaluating hippocampal replay without a ground truth" is Takigawa et al. (UCL, 2024), not a Frank-lab preprint; the Zweifel 2021 article number, the Adapt-A-Maze author list and the author lists of the two George et al. eLife papers (RatInABox 2024 and the 2023 rapid predictive-map paper) were fixed. Sorscher et al. 2023 (Neuron) and Cheng & Frank 2008 (added at this revision from memory) are still unverified. The session's proxy blocked most publisher sites, so DOIs appear only where a search result carried them; nothing was invented.
- **Releases**: a tagged release per milestone (§4) and a Zenodo DOI per result, with the model-comparison table and manifests shipped.
- **Venue**: Cosyne / CCN abstract for the first unit; a ReScience-style or eLife Research Advance / PLOS Comp Bio short paper if the rule ranking holds up.
- **A collaborator or lab contact** is strongly recommended before M5: replay-decoding biases and estimator pitfalls are where a solo researcher is most likely to be caught.

---

## 8. Risks

- **Crowded modelling literature** (Mattar & Daw 2018; Diekmann & Cheng 2023 with CoBeL-RL already embodied; Antonov et al. 2022; Jensen et al. 2024; Sagiv et al. 2025). The reviewer's first question will be "what does embodiment add?" The answer is the measured oracle-vs-embodied difference (§3 RQ1) and the rule ranking (RQ2), not the floors.
- **Tautology**: building gain × need and finding reverse replay after reward is what the rule is designed to do. Only the preregistered bounds, the positive control, the embodiment contrast, the ablations and the effects not built in (rerouting, the RQ2 ranking, enrichment without next-choice prediction) are evidence.
- **Oracle senses remain**: cue identity and allocentric heading are given, not recognised; cue-rotation and landmark-conflict experiments are out of reach without a visual front end this plan deliberately does not build. Stated in every write-up.
- **M3 is finicky**: function approximation plus a learned SR under a stochastic policy in continuous space. M2a's tabular result exists before M3 starts, so a failing M3 still leaves a result; tabular TD(0) stays as the fallback state representation for the replay module.
- **The world layer is thin**: walls, collisions and three trial-structured protocols are 4–5 weeks, not 3.
- **Solo pace**: ~29 FTE weeks (1,160 h) is one and a half to two and a quarter years of evenings at 10–15 h/week (§4: 15–31 months). Every milestone ends in a tagged release; the plan survives a long gap after any of them.
- **numpy enters**: same-platform determinism holds; cross-platform bit identity will not. The claim is scoped (§5 item 9).
- **Calibration is nominal until M0a item 2 lands**: with `energy_scale` live, no latency or rate is in physical units.

---

## 9. Decisions the owner needs to make

Recommended defaults in bold; the plan assumes them unless told otherwise.

1. **Accept that G14–G21 are legacy-profile results?** They stay, their tests stay, and they are re-measured with CIs as G23. **Yes.**
2. **Must the console's six scenarios keep working throughout?** **Yes**: they run under the legacy profile, labelled; the research profile adds panels and never removes a scenario.
3. **Tabular linear-track replay (M2a) before the place code (M2b)?** It puts the first scientific number 11–15.5 FTE weeks in instead of 15–21.5 (M2b and M3 before any number), and makes "embodied vs tabular" a measured comparison. **Yes.**
4. **A declared heading oracle?** The alternative is a landmark or visual front end, which is a separate project. **Yes**, declared in every write-up.
5. **Hours per week and horizon?** The plan is written in bursts (§4); the calendar figures assume 10–15 h/week with M0a, M0b, M1 and M2a as early stopping points. Say if the cadence is different.
6. **Licence?** **MIT** for the code; **CC-BY-4.0** for docs and figures, which is what Zenodo and ReScience expect.
7. **Should eating feed the agent?** Today food is reward without nourishment and the agent cannot starve. The critic calls this "the single change that ties the subsystems to one variable." **Not in this program** (it would couple the energy model to every result); parked as a future direction (homeostatic foraging).
8. **Keep the rat framing?** **Yes**, with every claim phrased "in a 2-D point agent with labelled range sensors, a heading oracle and noisy position odometry."
9. **Tolerance for a null?** The most likely honest outcome of RQ1 is "the embodied results equal the oracle ones." Preregistration makes that reportable; the rule ranking in RQ2 and the instrument are still the contribution.

**Decisions already taken in this plan (say if you disagree):** numpy and later scipy as hard dependencies, with same-platform determinism as the claim; comparison at the behaviour and replay-event level first, neural level only at M7; published summary statistics first, raw datasets only when a comparison needs them; the energy model frozen in the research profile; the nine-rule set and the two budget modes of §2.

---

## 10. Immediately after approval

**First session (one evening), on a branch `research/m0` from `main`:** add `SpatialConfig.gate_scales_egomotion: bool = True` and pass `sensory_gain = 1.0` in `Engine._spatial_step` when it is False; add `AstrocyteConfig.scales_motion` and `TRNConfig.microsleep_enabled` the same way; add `EngineConfig.research()` with the flags of §5 item 3; run the suite under both profiles; regenerate the baselines once; write decisions entry G22 listing the legacy/research split.
*Note (2026-10-03): done, on the session branch `ccr-6640f39d-7ve1oz` rather than a `research/m0` branch (commit 95667ce).*

**First weekend:** the rest of M0a (honesty pass, toy-assay renames, regression harness re-pointed), tagged `v1.0-honest`.
*Note (2026-10-03): done, on the session branch `ccr-6640f39d-7ve1oz` rather than a `research/m0` branch (commit dcf28b8, merge 27946b6, entry G22); tagged `v1.0-honest` at the commit that closes M0a.*

**Then:** M0b items 8 and 10 (seeds as samples, stats module), the G23 re-measurement, the remaining M0b items, tagged `v1.1-base`. Then M1.
