# M2b: the place code (plan §4 row 2b)

The plan's row 2b builds the state representation the replay rules of M3 will run on: a place-cell population over
a corrected position estimate, a successor representation learned over it, and the gate RQ4(a) that says whether
the embodied agent can navigate at all. It is done in four preregistered steps (`docs/prereg/m2b_estimate.md`):

1. **The corrected estimate**: the declared heading oracle and the wall-contact position reset (this document,
   step 1; decisions entry G33).
2. **The place population**: Gaussian place cells over the corrected estimate, rate maps, a decoder, throughput.
3. **The SR over the place code**: successor features by TD; backward skew on a track, elongation near walls.
4. **The RQ4(a) gate**: four start poses, a learned goal within 60 s on ≥ 80% of trials, arrival error < 0.2 m.

The row's console panels are deferred, as M2a's replay panel was.

## Step 1: the corrected estimate

Preregistered in `docs/prereg/m2b_estimate.md` before the run, with a five-seed probe and a smoke disclosed there;
decisions entry G33. Runner: `experiments/estimate_correction.py`, 14 s on 4 cores; tables in `docs/data/m2b/estimate/`.

**What it adds.** Two optional Observation channels and two estimate options, all off in both profiles, so every
earlier hash, table and sidecar is unchanged. The *heading oracle* gives the body's allocentric heading with a seeded
per-tick error (σ 0.05 rad, 2.9°); the spatial system can take its heading from it instead of summing the egomotion
turn. *Wall-contact sensing* gives the egocentric normal of each wall the body touches; the *reset* snaps that
normal, rotated by the heading estimate, to the nearest arena axis and writes the wall's coordinate into the estimate,
leaving the along-wall coordinate alone. The agent knows the arena's extent in its own frame; that and the heading
oracle are declared limitations of every result that uses them.

**Protocol.** The research profile in the 2 m open field, no objects, 3,000 ticks (10 min), 30 seeds. Every run has
both channels on, so within a seed every cell walks the identical body path (checked by a digest: 30 distinct walks,
one per seed); only the estimate differs, and every comparison is paired on the same trajectory. Four cells cross the
heading source with the reset; the M2b estimate is also run at four further oracle errors.

**The error, by cell** (mean over seeds; the late window is ticks 1,001–3,000; 1 unit = 0.1 m):

| cell | late mean error | late median | share of late ticks within 0.2 m | error at 3,000 ticks | wrong-wall resets |
|---|---|---|---|---|---|
| integrated (the research estimate so far) | 10.1 units | 10.2 | 4% | 11.1 | — |
| oracle heading, no reset | 8.3 | 8.5 | 4% | 10.4 | — |
| integrated heading, reset | 3.6 | 2.9 | 47% | 4.8 | 2.5% of writes, at 9 of 30 seeds |
| **oracle heading, reset (the M2b estimate)** | **0.92** | **0.70** | **90%** | 0.83 | 0 |

The M2b estimate's error is flat from the first contacts on (mean 0.88, 0.79, 1.03, 1.10, 0.85, 0.71 and 0.83 units
at ticks 250 to 3,000), where the other three grow. The body touches a wall on 41% of ticks, in 35 separate contacts
per run on average.

**The preregistered tests** (`estimate_effects.csv`):

| test | estimate [BCa 95%] | bound | verdict |
|---|---|---|---|
| level: per-seed late median error, M2b estimate | 0.70 [0.65, 0.76] units (7 cm) | < 2 units, interval below | **passes** |
| against today's estimate, late mean, paired | −9.2 [−10.8, −7.7] units, δ −1.00, every seed | δ ≤ −0.3, interval below 0 | **passes** |
| drop at contact, error after − before | −0.56 [−0.60, −0.52] units | < 0, interval below | **passes** |
| wrong-wall resets | 0 of 1,664 writes per run on average | < 1% | **passes** |

**What each mechanism contributes** (paired by seed, late mean error, reported without a bound):

- **The reset does most of the work.** It removes 7.4 units under the oracle (δ −1.00) and 6.6 under the integrated
  heading (δ −0.85).
- **The oracle alone buys little.** Without the reset it lowers the error by 1.85 [0.73, 3.16] units, δ −0.23, and
  only 1 of 30 seeds reaches the 0.2 m level. Heading drift is not the main source of error in the 2 m field; the
  wall slides are (below).
- **The oracle matters once the reset is on.** It lowers the reset estimate by 2.6 units (δ −1.00) and removes the
  wrong-wall resets: the integrated heading drifts to an rms of 0.33 rad late in the run, and at 9 seeds it passes 45°
  at some contact, so the reset writes the wrong wall and the estimate jumps across the arena.

**The residual is along the wall.** At a contact onset the M2b estimate's error falls from 1.14 to 0.58 units on
average, and the error along the touched wall's normal falls to exactly 0 at every one of the 1,044 onsets. What
remains is the along-wall error. A body sliding along a wall at an angle φ to it moves cos φ per unit of thrust;
the egomotion reports that motion's projection on the heading, cos² φ, along the heading, so the estimate under-reads
every slide and drives into the wall, where the reset puts it back. With 41% of ticks at a wall, the under-read is the
largest single source of error without a reset and the floor of the error with one: at oracle error 0 the level is
still 0.65 units. A rat's odometry would read the slide itself; this agent's egomotion, by its contract, reads motion
along the body axis only. It is recorded, not fixed, here.

**Sensitivity to the oracle's error** (the M2b estimate; late median error, then wrong-wall writes):

| oracle σ | 0 | 0.02 | 0.05 | 0.1 | 0.2 rad |
|---|---|---|---|---|---|
| late median error (units) | 0.65 | 0.66 | 0.70 | 0.81 | 1.11 |
| wrong-wall writes | 0 | 0 | 0 | 0 | 0.01%, at 5 of 30 seeds |

**Predictions against outcomes.** Held: the integrated estimate grows to several units; the oracle without the reset
is lower but above the bound; the reset under the integrated heading lies between, with wrong-wall resets at some
seeds; the M2b estimate is bounded and passes all four tests; the level rises with the oracle's error and stays well
below the bound at 0.1 rad. Failed: "no wrong-wall reset up to 0.2 rad" (a handful at 0.2 rad, the 1-in-10⁴ rate a
3.9-sd heading error predicts at that σ; the preregistered σ of 0.05 has none).

**Limitations of step 1.** The arena is a convex box with straight walls the agent knows; the reset is exact on the
normal, so it measures the mechanism, not a noisy boundary sensor; the estimate starts at the body's start pose, so
localisation from an unknown start is not tested here (RQ4(a)'s four starts begin from known poses). The wall-slide
under-read is a property of the egomotion contract and remains. Linux locally; CI runs the suite on macOS.

## Step 2: the place population over the corrected estimate

Preregistered in `docs/prereg/m2b_place_population.md` before the run, with development measurements and a smoke
disclosed, and a post-run correction recorded there (below); decisions entry G34. Runner:
`experiments/place_population.py`, 7 s on 4 cores; tables in `docs/data/m2b/place/`.

**What it adds.** An opt-in engine section, `EngineConfig.place`, off in both profiles: 400 Gaussian place cells on a
20 × 20 grid at 0.1 m spacing over the 2 m box, width 0.1 m (full width at half maximum 0.24 m), rates computed every
tick at the spatial system's estimate. It is a rate model with no noise, so the code is a deterministic function of
the estimate. The engine imports numpy only when the population is on, and the rates enter no logged field, so no
hash moves. A decoder inverts the code exactly, and `analysis/place_metrics.py` builds rate maps over bins of the true
position.

**Protocol.** Step 1's sensors, 30 seeds, 3,000 ticks. Per seed, two engines walk the same body path: one with the
research estimate, one with step 1's M2b estimate. A third, reference population is the same cells read at the body's
true position on that walk: the code a perfect estimate gives. Each population's rate maps are compared cell by cell
with the reference's on the bins the body visited at least five times. In 10 minutes the body samples about 170 of
the 400 bins that often, mostly near the walls, so 224 of the 400 cells have a sampled field and enter the comparison.

**The preregistered tests** (`place_effects.csv`):

| test | result | bound | verdict |
|---|---|---|---|
| throughput, 400 cells, median of five 3,000-tick runs | 16,200 ticks/s (17,600 with the population off) | ≥ 1,000 | **passes** |
| decoder against the estimate, every tick | 6 × 10⁻¹⁴ units at worst, no undefined decode | < 10⁻⁶ | **passes** |
| decoding error drops at wall contact, M2b | −0.56 [−0.60, −0.52] units | < 0, interval below | **passes** |
| map fidelity, M2b minus research, paired | +0.59 [+0.54, +0.63] in correlation, δ 1.00, every seed | δ ≥ 0.3, interval above 0 | **passes** |

**The maps** (per-seed means over the compared cells; the reference is 1 by construction):

| estimate | map correlation with the reference | centroid shift | spatial information / reference | decoding error, late median |
|---|---|---|---|---|
| research (integrated) | 0.33 [0.28, 0.37] | 3.7 units | 0.84 | 10.2 units |
| M2b (oracle heading and reset) | **0.91** [0.90, 0.92] | **0.35** units | 0.91 | 0.70 units |

Under the M2b estimate the fields an experimenter would record are the cells' own fields, shifted by about a third of
a field width and slightly broadened. Under the research estimate they are displaced by about four widths and keep
little of their shape. Wall and interior cells do not differ under the M2b estimate (0.913 and 0.915). The innermost
ring is lowest, 0.87, where the body samples least.

**Information does not measure accuracy.** The research estimate's maps keep 84% of the reference's spatial
information, where I predicted below 60%. A map displaced across the arena is still a sharp map: Skaggs information
measures how selective a cell is, not whether it fires in the right place. Map correlation and centroid shift are the
statistics that see the error, and later steps should report those.

**The decoding error is the estimate's.** With noiseless rates the decoder returns the estimate itself, so the decoding
error with respect to the body equals step 1's estimate error to 10⁻¹³: 0.70 units for the M2b estimate, 10.2 for the
research estimate. The drop at contact is step 1's drop read through the code. A decoder of noisy population activity,
with the binning the replay papers use, is M7's step 0, not this one.

**Post-run correction.** The first evaluation run reported every test passing, but the research estimate's decoding
error read 4.2 units against step 1's 10.2 on identical walks. The decoder had solved over the nine most active cells,
and when the research estimate drifted more than about ten units beyond an arena edge those cells were one grid
column. The solve was then singular and returned no position, at 117 and 295 ticks at seeds 1 and 2. The experiment's
`max()` skipped those NaNs, so the decoder test read as exact, and the seed means dropped the seeds that drifted most.
Before any result was reported, the decoder was changed to solve over the most active cell's 3 × 3 grid neighbourhood,
which is never collinear. It is now exact at 20,000 random positions over a region nine times the arena's area, and
the experiment counts undefined decodes and fails the test on any. The tests and bounds are unchanged; the first
run's tables are not committed. Only the decoding statistics moved; the maps, throughput and drop at contact read the
same in both runs.

**Predictions against outcomes.** Held: all four tests; research maps with correlation below 0.5 and shifts of several
units; M2b maps with correlation above 0.85, shifts under one unit and information above 0.8. Failed: the research
estimate's information ratio below 0.6 (it is 0.84, for the reason above).

**Limitations of step 2.** Rates are noiseless, so decoding is a consistency check rather than a measurement. Ten
minutes samples only part of the field interior. The grid of centres is regular, not RatInABox's random placement.
Nothing reads the population yet; step 3's SR is its first reader.

## Step 3: successor features over the place code

Preregistered in `docs/prereg/m2b_sr_fields.md` before the run, with a sanity check of the learner and a smoke
disclosed there; decisions entry G35. Runner: `experiments/sr_fields.py`, 38 s on 4 cores; tables in `docs/data/m2b/sr/`.

**What it adds.** `brain/systems/successor_features.py`: successor features ψ(s) = M φ(s) over step 2's population,
with rates normalised to sum 1, and M learned from the identity by TD(0) from the agent's own transitions (α 0.1,
γ 0.95). No bootstrap is made across an episode boundary. The learner uses element-wise numpy only, so its tables
reproduce exactly across platforms. A feature's SR field is ψ_j as a function of position: how much of that cell's
firing the agent expects ahead of it from there. Nothing reads the SR yet.

**Protocol.** Both parts use step 1's M2b estimate and step 2's population, over 30 seeds.

- **The track.** A 2 m × 0.1 m corridor with 20 cells and 50 laps. The agent's own turning circle (0.1 m in radius)
  does not fit the corridor's 0.05 m half-width, which is the kinematic problem the plan's caveat names. So a
  protocol imposes the running: the body is driven along the track at a seeded random speed of 0.5 to 1.0 units per
  tick. In `one_way` laps the body runs east and is carried back to the start, an episode boundary with the estimate
  re-anchored there. In `two_way` laps it turns round in place at each wall and runs back.
- **The open field.** The 2 m box and the agent's own walk for 12,000 ticks (40 minutes). Each field is measured above
  half its maximum and compared with the raw place field, whose region the wall already truncates.

**The preregistered tests** (`sr_effects.csv`):

| test | result | bound | verdict |
|---|---|---|---|
| backward skew, one-way, mean centre-of-mass shift of 14 interior cells | −2.13 [−2.134, −2.130] units (0.21 m) | < 0, interval below | **passes** |
| direction-specific, one-way minus two-way, paired | −2.17 units, δ −1.00, every seed | δ ≤ −0.3, interval below 0 | **passes** |
| elongation along walls, open field, 72 wall cells | +0.54 [+0.54, +0.55] in log(along/across), beyond the raw field's | > 0, interval above | **passes** |

**The track.** One-way SR fields extend backward against the running, as Stachenfeld et al. predict from Mehta et
al.'s data:

- **The shift grows along the track.** It is near zero at the start, where there is no past to predict from, and
  plateaus at −2.4 units from mid-track on.
- **The fields are skewed and their peaks move.** Skewness is −0.57, a tail to the west. The peak moves back 0.77
  units, where I predicted it would stay at the cell's centre.
- **Two-way fields stay centred**, at +0.04 units in the interior. Only the end cells move, and inward, pushed by the
  walls.

With features of position alone, a policy that runs both ways predicts its own past in both directions, and the
backward tail cancels. The plan's bound is therefore a property of directional running. On a real track it would
need either one-way laps or direction-specific cells.

The intervals are narrow because the protocol fixes the path and the seeds vary only the speeds and the sensor
noise. They measure the learner's consistency, not variation between animals.

**The open field.** Near a wall, the SR stretches a cell's field along the wall:

- **The along/across variance ratio rises.** It goes from the raw field's log-ratio of 0.80, which is the wall's
  truncation alone, to 1.34.
- **Most wall cells elongate.** 64 of 72 do, and every seed's mean lies between 0.50 and 0.57.
- **Interior fields stay isotropic but grow.** Their log(var_x / var_y) is −0.003. Their area grows by 24%, and wall
  fields' by 59%.

The agent slides along walls on 41% of its ticks, so its transitions near a wall run along it, and the SR follows its
transitions.

**Predictions against outcomes.** Held: all three tests; the shift's size (predicted −1.5 to −2.5 units); negative
skewness; two-way shift within ±0.3 units; isotropic interior fields with an area above the raw fields'; the open-field
estimate at step 1's level (0.67 units).

Failed, twice:

- **"The peak stays at the cell's centre."** It moves back 0.77 units.
- **"The track estimate's error stays under 0.5 units."** One-way laps hold 0.17, but two-way laps read 0.83. Without
  the re-anchoring, the across-track coordinate drifts with the oracle's heading error, because the body never touches
  the corridor's side walls. That drift does not reach the features: the cells form one row, so a sideways offset
  scales every rate alike and normalisation removes it.

**Limitations of step 3.** The track's running is imposed, so the agent's own kinematics on a track remain untested,
as the plan's caveat feared. The SR is learned outside the engine from the engine's own trajectories. One learning
rate and one discount are used. Nothing yet tests whether the SR supports behaviour; that is step 4's gate.

## Before step 4: the gate is bounded by the motor policy (a probe; the owner decides the protocol)

RQ4(a) asks that from four start poses in the 2 m field, with the embodied estimate, the agent reach a *learned* goal
within 60 s on at least 80% of trials after 20 trials. Before writing its protocol, a probe asked how often the
research agent reaches the goal when it can *see* it, the best a learned value could do with this motor policy. The
setup was the M2b estimate, starts at the four wall midpoints facing the centre, 300 ticks, and 5 seeds × 4 starts:

| visible goal | reached within 60 s | median latency |
|---|---|---|
| centre (0, 0), radius 0.1 m | 20 of 20 | 8 ticks |
| (0.5 m, 0.5 m), radius 0.1 m | 13 of 20 | 110 ticks |
| (0.5 m, 0.5 m), radius 0.15 m | 15 of 20 | 151 ticks |

A goal straight ahead of every start is trivial. A goal off the start's line is missed on a third of trials even in
plain view: the agent sees through a 1.2 rad fan to 1.2 m, and it spends 41% of its time sliding along walls. A hidden
goal can do no better than a visible one with the same body, so on this agent the 80% bound measures the motor policy
first and the place code second.

Three ways to run the gate, for the owner (G35 C3 assumed the plan's gate as written):

1. **As written.** Add the SR's value read-out (V = M·R) as a steering source, run a water-maze-style protocol with the
   goal made visible after a 60 s miss as guidance, and report the result. It is likely to fail, for the reason above.
2. **Relative to the visible-goal ceiling** (recommended). Report both absolute rates, and gate on the hidden-goal
   success rate as a share of the same agent's visible-goal rate from the same starts. This isolates what M2b built
   (the estimate, the code and its value). It changes the plan's gate, which is the owner's decision.
3. **Improve the motor policy first, then gate as written.** This changes the research profile's behaviour, which
   moves the baselines and every engine-based M2b table, and it risks tuning the agent to the gate.

The SR value source needed by every option is the next piece of code. It is not built yet, so no engine behaviour
has changed.

## Step 4: the RQ4(a) gate, relative to the visible-goal ceiling

The owner chose the relative gate (option 2 above) on 2026-10-25. Three runs followed:

- **The preregistered gate**: `docs/prereg/m2b_gate.md`, seeds 1–30, failed for the SR source.
- **An exploratory diagnosis**: same seeds, not preregistered.
- **A confirmatory gate**: `docs/prereg/m2b_gate_confirmatory.md`, fresh seeds 31–60, passed.

Decisions entry G36. Runner: `experiments/rq4a_gate.py` (134 s, 14 s and 46 s on 4 cores). Tables are in
`docs/data/m2b/gate/` (with the exploratory run in its subdirectory) and `docs/data/m2b/gate_confirmatory/`.

**What it adds.** A value source the steering reads, `value_memory.source`:

- `"tabular"` is the value map over the estimate's bins, as before and still the default.
- `"sr"` learns online successor features over the place code and reward weights R, and reads V(p) = φ(p)·(Mᵀ R)
  at the same lookahead points.
- `"none"` gives no value steering.

An episode boundary cuts every learner at each trial's start. The tabular path is unchanged, so no hash moves.

**Protocol.** The M2b estimate, the 400-cell population, and a goal of radius 0.1 m at (0.5 m, 0.5 m). Four starts sit
0.1 m from each wall's midpoint, facing the centre, shuffled per block of four. The body is placed and the estimate
re-anchored at each start: the agent knows where it is put down, which is declared. There are 40 trials of 60 s each.

- **Hidden session.** The goal is hidden; after a 60 s miss it becomes visible for up to 60 s more, as guidance.
- **Visible session.** The goal is visible throughout.

The gate is the hidden success rate over trials 21–40 divided by the visible success rate of the same agent from the
same starts, at least 0.8. The arrival error must also be below 0.2 m.

**Results over trials 21–40** (means over 30 seeds):

| run | value source | hidden | visible | hidden ÷ visible | arrival error |
|---|---|---|---|---|---|
| preregistered (seeds 1–30) | SR, NLMS reward | 13% | 46% | **0.29 [0.23, 0.35]: fails** | 0.25 units |
| | tabular map | 84% | 82% | 1.03 | 0.39 |
| | none | 5.5% | 62.5% | 0.09 | — |
| exploratory (seeds 1–30, SR only) | SR, per-feature reward | 99.5% | 100% | 0.995 | 0.21 |
| confirmatory (seeds 31–60) | SR, per-feature reward | **98.7%** | 100% | **0.987 [0.973, 0.993]: passes** | **0.20 [0.19, 0.21]: passes** |
| | tabular map | 85.5% | 78.7% | 1.09 | — |
| | none | 5.0% | 65.2% | 0.08 | — |

**Why the preregistered SR source failed.** It learned R by normalised least mean squares, a regression of the point
reward on overlapping place fields. The many unrewarded ticks near the goal are fitted with negative weights, so R
rings the goal; at seed 1 it was 2.2 at the goal and −1.0 beside it. The value then has a trough around the goal,
−0.37 at its lowest, and near the goal its gradient points away from it. Far from the goal it is flat, 3 × 10⁻⁵ at the
west start.

The learning curve shows the ring forming. Hidden success started at 0.53 in the first block of four trials, far
above no steering's 0.06, then fell to about 0.12. Visible success fell with it, from 0.75 to 0.45, below no value
steering at all.

A per-feature rule, R += 0.5 φ (r − R), moves each weight toward the reward seen while its cell is active. It cannot
go negative when rewards do not. With it the SR source reaches the hidden goal on every trial from the second block on.
That was found on the gate's own seeds, so it was preregistered and confirmed on fresh ones.

**What the confirmatory run shows.**

- **The SR source navigates almost perfectly.** It reaches the hidden goal on 98.7% of test trials, in a median 14
  ticks (2.8 s): close to a straight line from the start. It does so at every one of the 30 seeds.
- **It clears the plan's original bound too.** It also passes the absolute 80% bound that the owner's amendment
  relaxed.
- **The tabular map passes the relative gate as well.** Its ratio is 1.09, but its median latency is 81 ticks and it
  learns slowly: hidden success climbs from 0.07 to 0.87 over the 40 trials. The SR's value spreads by prediction
  across the arena; the map's spreads only by backups along the bins the agent visited.
- **No value steering finds the hidden goal 5% of the time.** That is the chance level the learned values beat.
- **Arrival errors are small.** They are 0.20 to 0.39 units (2 to 4 cm), against the 0.2 m bound.

**Predictions against outcomes.** For the preregistered run:

- **Held:** g2 passes; the SR beats no steering (by 0.08, small); no steering's hidden success stays under 20%.
- **Held, though not for the reason I expected:** g1 fails. I predicted a ratio of 0.3 to 0.7 from paths the SR had
  not learned; the actual 0.29 came from a value trough the reward rule had built.
- **Failed:** the SR beats the tabular map (the map won by 71 points); the visible ceiling is about two thirds (the SR
  source's own visible rate was 46%, because its value misled even with the goal in view).

For the confirmatory run, every prediction held.

**Limitations of step 4.**

- **One goal and one start set.** The goal is in one place and the starts are known poses with a re-anchored estimate.
- **One reward rule was replaced after a failure.** The replacement is confirmed on fresh seeds, but it is one
  change, chosen after seeing the problem.
- **The gate's value is learned within one session.** There is no replay yet; that is M3.
- **The body is unchanged.** The motor policy is as before; only what the steering reads changed.

## Where M2b stands

Every item of the plan's row 2b acceptance is met, the gate in its amended form:

- **The corrected estimate** is at 7 cm in the open field (step 1).
- **The place population** runs at 16,200 ticks/s, against a bound of 1,000; with the SR source on, the engine runs at
  about 2,200 ticks/s (steps 2 and 4).
- **Decoding error drops at wall contact** (step 2).
- **SR fields skew backward** on one-way laps and **elongate along walls** (step 3).
- **RQ4(a) passes** on fresh seeds (step 4).

The console panels remain deferred. All of it is opt-in configuration: the profiles and the determinism baselines
are unchanged.
