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
