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
