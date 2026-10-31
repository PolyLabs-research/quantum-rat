# Preregistration draft: the whole, part 1 — resource management

**Written:** 2026-10-31, before any build or run of what it describes. A draft for the owner: the parts are built
opt-in, the task is calibrated by the rule in §3, and a pilot on its own seeds runs the bracketing design of §5; the
owner registers the confirmatory run. The decisions entry for the pilot will be G56.

## 1. Why

The owner's working hypothesis (2026-10-31): mammalian behaviour emerges from the interaction of many systems, so
studying the parts one at a time may fail, because it is the whole that produces the spark. The owner's decisions:
**upgrade every cartoon part, and use all of them in the combined agent; start with the most basic function of life,
resource management: identifying that energy is needed, finding it and consuming it.**

The project's own history is the reason for the design below. The legacy profile was the everything-interacting
version, and the audit found its best behaviour came from interactions that were faults (`docs/research_plan.md` §1);
since then three artefacts made the agent look smarter than it was and a fourth produced a false mechanism (G46–G52).
So emergence here is the thing the experiment tests, not the thing it assumes: the spark is named before any run (§4),
and the whole is bracketed by removing each part from it and adding each part alone to the base (§5).

## 2. The parts

Every part below is opt-in; the legacy and research profiles do not change; both determinism baselines must stay
bit-identical. Each part is upgraded from what the audit found (`docs/research_plan.md` §1, the grade "cartoon") to a
role with a stated reference, and coupled to the others through named signals. Every number is set here, from the
stated reason, before any run. Time: a tick is 0.2 s (300 ticks a minute).

### 2.1 Metabolism (the body's physics; part of the task, on in every configuration)

The audit's astrocyte was an ATP store whose only effect was to throttle movement and close the sensory gate. It is
replaced, in the task, by a body energy balance that the agent has to manage, and that never throttles movement:

- a **reserve** E in [0, 1] (a compressed store: at rest, full to empty in 30 minutes, `basal_cost` 1/9000 a tick;
  the compression is declared, a rat's reserves last days); the run starts at E = 0.6;
- **locomotion** adds twice the basal cost at full speed (the whole cost about three times resting, the order of the
  rise in a rat's oxygen uptake from rest to a steady run), in proportion to speed (the discrete body: the action's
  thrust; the rodent body: its speed over its run speed);
- **sleep** costs 0.8 of the basal rate (metabolic rate falls in sleep; Berger & Phillips 1995);
- **eating**: food enters a **gut** G and is absorbed into E with a time constant of 300 ticks (1 minute; compressed);
  a meal takes 5 ticks (1 s), during which the body rests; E cannot exceed 1 (the excess is lost);
- **starvation**: E reaching 0 ends the run.

### 2.2 The upgraded parts (each one can be removed from the whole and added alone to the base)

| part | the audit's cartoon | becomes | couples to | reason |
|---|---|---|---|---|
| **interoception** | (none: the agent never sensed its own state) | reads E_eff = E + G against a setpoint E\* = 0.8. Drive D(x) = ((x − E\*)/E\*)². **Reward is drive reduction**: a meal brings r = [D(E_eff) − D(E_eff + K)] / [D(0) − D(K)] (1 for the hungriest meal; negative past the setpoint). The **consummatory reflex** eats on contact only when r > 0. **Hunger** h = clamp((E\* − E_eff)/(E\* − 0.4), 0, 1). **Incentive** ι = clamp(r a meal would bring now, 0, 1) scales the memory term and vision's pull to food. The SR's reward weights learn the **outcome** (a meal: 1), so its value is revalued at once by ι; the action value learns r and is not | motivation (hunger), serotonin (satiety), sleep (hunger keeps awake), dopamine (reward) | homeostatic reinforcement learning (Keramati & Gutkin 2014); incentive salience depends on the physiological state at the moment of the cue (Toates 1986; Zhang, Berridge, Tindell, Smith & Aldridge 2009); the SR's revaluation (Dayan 1993; Momennejad et al. 2017); habits are not revalued (Daw, Niv & Dayan 2005); the consummatory act is a brainstem reflex terminated by satiety signals (Grill & Norgren 1978) |
| **motivation** | (G52–G53, built) | the drive to move is a soft OR of the reasons: **forage = hunger** (interoception's h; without interoception, G53's meal-count estimate) and **explore = curiosity** (novelty); REST's idle term for what is missing. Its own vigour is off (vigour floor 1): vigour belongs to dopamine | interoception, acetylcholine's novelty | a rat moves because it is hungry or curious (G52) |
| **dopamine** | reward minus a running mean (not a prediction error) | **phasic** δ = r + γ ι_t V(s_t) − ι_{t−1} V(s_{t−1}) with V the SR value and γ = 0.95, the SR's discount; **tonic** = the reward trace (up at once with a meal's r, down over 600 ticks); **vigour** = 0.5 + 0.5 × tonic scales the forward bias; the **replay budget** at a meal is round(20 × min(1, \|δ\| / 0.5)) | interoception (r, ι), replay, the arbiter | the TD error (Schultz, Dayan & Montague 1997); tonic dopamine as the average reward rate setting vigour (Niv, Daw, Joel & Dayan 2007); reward magnitude modulates awake replay (Ambrose, Pfeiffer & Foster 2016) |
| **serotonin** | a lagged copy of dopamine's input | 5HT = 0.5 + 0.5 × satiety, satiety = clamp((E_eff − 0.6)/0.2, 0, 1); REST gains 1.0 × (5HT − 0.5): post-ingestive rest | interoception | serotonin as a satiety signal (Blundell 1977; Halford & Blundell 2000); the behavioural satiety sequence, eating then grooming then rest (Antin, Gibbs, Holt, Young & Smith 1975) |
| **noradrenaline** | half pain plus half the checksum bit | NE follows \|δ\| (up at once, down over 50 ticks, 10 s) plus pain; the softmax temperature × (1 + 2 NE): after a surprise, more exploration; pain avoidance × (1 + 0.5 NE) | dopamine's δ, the arbiter | unexpected uncertainty (Yu & Dayan 2005); the locus coeruleus's adaptive gain, its tonic mode driving exploration (Aston-Jones & Cohen 2005) |
| **acetylcholine** | the checksum bit (1 on every tick under noise) | ACh = 0.5 × novelty + 0.5 × moving while awake, 0 asleep; **novelty** = 1 − familiarity (history's visit channel) replaces the checksum bit; the SR's learning rate × (0.5 + ACh) (encoding); awake replay only when ACh ≤ 0.3 (consolidation); vision's weight × (1 + 0.5 ACh) (sensory precision) | history (familiarity), replay, sleep | high acetylcholine sets encoding, low sets consolidation and replay (Hasselmo 1999, 2006); expected uncertainty and the weight of sensory evidence (Yu & Dayan 2005) |
| **sleep** | microsleep as an ATP alarm, fixed 25-tick bouts | **sleep pressure** S rises in wake (S += (1 − S)(1 − e^(−1/3000)) a tick) and falls in sleep (S × e^(−1/600)); sleep starts when S ≥ 0.6, h < 0.25 and no pain, and ends when S ≤ 0.2, h ≥ 0.5 or pain. Asleep: the thalamic gate is closed (no sensory input reaches selection; the body rests), metabolism × 0.8, ACh 0, and two replay backups a tick. Polyphasic and compressed: wake bouts of about 10 minutes, sleep bouts of about 2 | interoception (hunger keeps awake), acetylcholine, replay, criticality, metabolism | the two-process model's homeostatic process (Borbély 1982); hunger keeps an animal awake through the orexin neurons (Yamanaka et al. 2003); the thalamic reticular nucleus gates sensory transmission in sleep (Steriade, McCormick & Sejnowski 1993); sleep conserves energy (Berger & Phillips 1995); replay in sleep (Wilson & McNaughton 1994) |
| **criticality** | a lattice whose statistic never located criticality, dead at the defaults | the lattice's coupling is a state variable: p = 0.5 m (0.5 is this lattice's bond-percolation critical point, so m is the distance from criticality); m = m₀ + 0.3 S, with m₀ tuned homeostatically toward m = 1 (m₀ += (1 − m)/3000 a tick): wakefulness pushes the network supercritical and sleep restores it. Sensory gain = exp(−((m − 1)/0.3)²) on vision's terms and on wall avoidance | sleep | dynamic range peaks at criticality (Kinouchi & Copelli 2006; Shew, Yang, Petermann, Roy & Plenz 2009); cortical circuits are tuned homeostatically to criticality (Ma, Turrigiano, Wessel & Hengen 2019); wake potentiates and sleep downscales (Tononi & Cirelli 2006), sleep as a return to criticality (Pearlmutter & Houghton 2009; Meisel et al. 2013) |
| **action value** | (G55, built) | M3 step 3's learner with history among its features and the read floor (G55 A1), learning interoception's r, read beside the SR (the memory term is the SR's split signals × ι plus the action value's) | interoception, the arbiter | a model-free learner beside the model-based one (Daw, Niv & Dayan 2005) |
| **replay** | (G55: built over the action value, where it hurt) | replay updates the **successor map** only (SR-Dyna): at a meal, the current episode's last transitions in reverse, the budget set by dopamine (20 without it), when ACh allows; asleep, two transitions a tick drawn uniformly from the last 3,000. The action value is not replayed (G55 C3: its backups eroded the learned advantages) | dopamine, acetylcholine, sleep | replay as offline learning of a predictive map (Russek, Momennejad, Botvinick, Gershman & Daw 2017); reverse replay at reward (Foster & Wilson 2006) |
| **body** | the discrete body | the rodent body with RatInABox's noise (G44's preset `rodent`) | metabolism (speed sets the locomotor cost) | George et al. 2024; Sargolini et al. 2006 |
| **orienting** | (G51, built) | the orienting response to a seen target (`orient_gain` 1.0) | vision | the orienting reflex |

**Kept as they are:** the action-selection arbiter (a documented competition between channels: the basal ganglia as
a selection device, Redgrave, Prescott & Gurney 1999), and the research profile's instrument as G54 left it (heading
oracle, wall reset, the place population and SR, the cue map, reachable probes, history with the fixed schema, the
capped step).

## 3. The task

A 2 m square arena (half-extent 10 units) with the gate's four distal cues; **four food patches**, visible (kind
`target`), radius 0.75 units, at (±5, ±5); an eaten patch **regrows** 600 ticks (2 minutes) later. The agent starts at
the centre with E = 0.6 and an empty gut. A run is **9,000 ticks** (30 minutes). Metabolism (§2.1) is on in every
configuration.

**Calibration of the food's energy K, before any configuration runs.** The base's behaviour does not depend on K (it
does not sense its energy; it eats on every contact; its reward is the contact bonus). The base runs on calibration
seeds 1001–1004 (never used again) with starvation off; K is set to its mean expenditure per tick divided by its mean
meals per tick, rounded to 0.005: **the task is set where the base breaks even**, so that whatever keeps an agent near
its setpoint has to come from what the other parts add.

## 4. The spark: resource management

Measured from the physics in every configuration (h computed from E and G by the formula of §2.2, whether or not the
agent senses it):

- **R1, homeostasis (the target).** (a) Survival: no starvation in 9,000 ticks on at least 11 of 12 seeds; (b) the
  mean over seeds of the mean |E − 0.8| over the run's second half is at most 0.15 (a starved run counts 0.8 for its
  dead ticks).
- **R2, need-contingent activity.** The share of awake ticks spent moving when hungry (h ≥ 0.5) less the share when
  sated (h ≤ 0.1), averaged over the seeds with at least 5% of ticks in each state, is at least 0.3; fewer than 8 such
  seeds is a failure.
- **R3, memory (the whole only).** Energy eaten per unit of locomotor energy spent is at least 1.25 times the whole's
  with memory unread (`value_gain` 0), and the whole survives at least as often.

**The spark is R1 and R2.** What is wired and what is not: R2 is wired by design (interoception's hunger is
motivation's forage reason), so it is a check that the wiring works. R1 is the system-level outcome. Interoception and
motivation were built with it in mind, so R1 needing those two is expected and is not the hypothesis. The hypothesis's
strong form is that R1 needs most of the parts, including those built for other reasons.

Reported, no bound: meals, intake, expenditure, efficiency, time below E = 0.2, the moving shares, rest in the 150
ticks after a meal, sleep share and bouts, the replay events, the temperature and the sensory gain over the run.

## 5. The configurations and the emergence test

The **base** is the research profile as G54 left it (with the capped step) on the task. The **whole** is the base
with all twelve parts of §2.2. Then: **the whole minus each part** (12), **the base plus each part** (12), and **the
whole with memory unread** (R3's control): 27 configurations, every one on pilot seeds 1–12.

**The emergence verdict,** written before any run:

1. the whole shows the spark;
2. no single addition to the base shows it;
3. removing a single part breaks it for at least 6 of the 12 parts.

All three: the strong form is supported on this task. Reported beside it, no bound: **synergy** on the homeostasis
score, the whole's improvement over the base in mean |E − 0.8| against the sum of the single additions'
improvements.

## 6. Seeds and runs

Calibration 1001–1004; pilot 1–12; reserved for the confirmatory run 13–42, and a held-out environment (half the
patches, moved) that the pilot never sees. Every run from a clean tree with numerical warnings as errors (G52 C5).
`experiments/whole_resource.py` (to build): `--phase calibrate`, `--phase pilot`.

## 7. Predictions (written before any run)

- **Calibration**: K between 0.05 and 0.10.
- **The base** survives on most seeds (it breaks even by construction) but fails R1(b): it never rests and eats only
  what it meets, so E wanders below the setpoint. It fails R2 (it has no need signal).
- **The whole** passes R1 and R2; R3 passes narrowly or fails (the food is visible, so memory matters less than in
  hidden food).
- **No single addition** passes R1: interoception alone eats less and never rests; motivation alone falls back on
  G53's meal count, whose hunger saturates, so it never rests either.
- **Removing interoception or motivation** breaks R1 and R2. **Removing dopamine** may break R1 (without the reward
  trace, vigour is constant). **Removing any of the other nine does not.** So I predict the verdict's third condition
  fails: the spark needs a few parts working together, not most of them. That would support the hypothesis's weak
  form (more than one part) and not its strong form.

## 8. Decision table (pilot)

| result | reading | what follows |
|---|---|---|
| all three conditions | the strong form, on this task | the owner registers the confirmatory run (seeds 13–42) and the held-out environment |
| 1 and 2, not 3 | the weak form: the spark needs a few parts, named by the leave-one-out rows | recorded; the next spark behaviour, the owner's choice, tests whether the other parts matter there |
| a single addition shows the spark | it is one mechanism | recorded, with which |
| the whole fails | the parts, as set, do not combine into it | a joint-tuning phase on the pilot seeds under a tuning rule recorded here first, then a second pilot |
| the base passes R1 | the task is too easy | the calibration is revisited, recorded here first |

## 9. What would change this document

Nothing after the pilot's configurations have run. A pre-run amendment (a parameter that must change for the build to
run at all, or the calibration's outcome) is recorded here, dated, before the pilot.
