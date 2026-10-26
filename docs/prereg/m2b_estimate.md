# Preregistration: the corrected position estimate, step 1 of M2b

**Written:** 2026-10-25, before the evaluation run (branch `m2b-estimate` from the `v1.3-track-replay` merge `04f80b6`;
the decisions entry that reports the result is G33). **Scope:** the first of M2b's components in the plan's §4 row 2b,
"the corrected estimate" that the place population will sit on: the declared heading oracle (plan §2 item 1) and the
wall-contact position reset (Hardcastle, Ganguli & Giocomo 2015, for the reset only), characterised in the 2 m open
field. No place cells, no SR, no behaviour change: those are later steps.

**Disclosure.** Two runs preceded this document. A five-seed probe of the research profile as it stands (3,000 ticks,
2 m box, no objects) found the body pressed against a wall on 1,139 to 1,393 of 3,000 ticks with 26 to 42 separate
contacts per run, and the dead-reckoned estimate 1.6 to 14.7 units off at ticks 1,000, 2,000 and 3,000. A smoke of
the experiment below at 300 ticks and two seeds checked that it runs end to end and that every cell walks the same
body path within a seed. Neither is the evaluation; the predictions below were written after seeing both.

## M2b in four steps (the plan's row 2b decomposed; each preregistered on its own)

1. **The corrected estimate** (this document): heading oracle, wall-contact sensing and reset, characterised.
2. **The place population**: Gaussian place cells over the corrected estimate (RatInABox conventions), rate maps
   against true position, a population decoder, throughput with a 400-cell population against the plan's ≥ 1,000
   ticks/s; "decoding error drops at wall contact".
3. **The SR over the place code**: successor features learned by TD from the agent's own trajectories (V = M·R),
   with the tabular TD(0) learner as the ablation; on a track, SR fields skew backward against the running direction
   after 50 laps (measured before the bound is fixed, as the plan's caveat says); near walls, fields elongate.
4. **The RQ4(a) gate**: from four start poses in the 2 m field with the embodied estimate, a learned goal within
   60 s on ≥ 80% of trials after 20 trials, median estimate error at arrival < 0.2 m.

The console panels of the row are deferred, as M2a's replay panel was; they are not needed for any of the four tests.

## What is implemented (all off by default; every earlier run, hash and table is unchanged)

- **The heading oracle** (`SensorConfig.heading_oracle`, `heading_oracle_noise`): the Observation carries
  `heading`, the body's allocentric heading plus N(0, σ) drawn per tick from a new named stream, `sensors_heading`.
  `SpatialConfig.heading_source = "oracle"` makes the spatial system take its heading estimate from that reading
  instead of summing the egomotion turn. σ = 0.05 rad (2.9°) is the preregistered value: small against the 45° a
  wall's identity needs, and large enough not to be exact. It is a declared limitation in every result that uses it.
- **Wall-contact sensing** (`SensorConfig.wall_contact_sensing`): the Observation carries `wall_contacts`, the
  egocentric angle of the outward normal of each wall the body touches (it touches a wall when it sits on the wall's
  line, which the world's clamp puts it on). Touch is exact.
- **The reset** (`SpatialConfig.wall_reset`): on every tick with a contact, the allocentric normal (heading estimate +
  the touch's angle) is snapped to the nearest arena axis to identify the wall, and the estimate's coordinate along
  that wall's normal is set to the wall's; the along-wall coordinate is untouched. The agent knows the arena's
  half-extent in its estimate frame (declared; the estimate starts at the body's start pose, the origin).
- New Observation fields are left out of the checksum and the determinism record while they are None, so the legacy
  and research baselines and the observation sidecar are byte-identical (verified by the suite's exact-hash tests).

## Protocol

The research profile, the default 2 m box (bounds 10 × 10 units), no objects, 3,000 ticks (600 s) per run, seeds 1–30.
The heading oracle (σ 0.05) and wall-contact sensing are on in every run, so the Observation stream, and with it the
body's walk, is the same in every cell of a seed (checked by a digest of the body's path); only the estimate differs.
Cells: `integrated` (the summed egomotion turn, no reset: the research estimate so far), `integrated_reset`,
`oracle` (the oracle's heading, no reset) and `oracle_reset` (the M2b estimate); and `oracle_reset` at oracle
σ ∈ {0, 0.02, 0.1, 0.2} rad (sensitivity, the walk again the same).

Per run: the position error |estimate − body| every tick; the late window is ticks 1,001–3,000; the heading error;
contact onsets (the first tick of each bout at a wall) with the error on the tick before and on the onset tick (after
the reset), in total and along the touched wall's normal; every reset write scored against the walls the body
actually touches (a write to a wall not touched is a wrong-wall reset). The seed is the unit; BCa 95% intervals over
seeds (10,000 replicates); paired comparisons by seed with Cliff's δ.

## Preregistered tests

1. **Level** (`t1_level`): for `oracle_reset`, the per-seed median error over the late window, averaged over seeds, is
   below 2 units (0.2 m, RQ4(a)'s arrival bound read here on the open-field estimate), the upper end of its interval
   below 2.
2. **Against today's estimate** (`t2_primary_vs_integrated`): the late mean error of `oracle_reset` minus
   `integrated`, paired by seed: Cliff's δ ≤ −0.3 and the interval below 0.
3. **The drop at contact** (`t3_drop_at_contact`): for `oracle_reset`, the per-seed mean of (error after the reset −
   error before) over contact onsets is below 0, interval below 0.
4. **Wall identity** (`t4_wrong_wall`): for `oracle_reset`, wrong-wall resets are below 1% of reset writes.

Reported without a bound: the error curves; the four mechanism comparisons (the reset under each heading source, the
oracle with and without the reset); `integrated_reset`'s wrong-wall share and drop at contact; the sensitivity cells.

## Predictions (written before the run)

- **integrated**: the error grows with the heading random walk and with the wall-sliding under-read (a body sliding
  along a wall at an angle φ to it moves cos φ per unit thrust, the egomotion reads its projection on the heading,
  cos² φ, along the heading: the estimate under-reads the slide and moves into the wall); late mean error several
  units, of the order of the probe's 2 to 15.
- **oracle** (no reset): the heading drift is gone but the under-read at walls is not, and with 40% of ticks at a wall
  it accumulates: lower than `integrated`, **above the 2-unit bound**, with less confidence.
- **integrated_reset**: each contact removes the normal error; the heading estimate still drifts (sd about 0.55 rad at
  3,000 ticks), so position error builds between contacts and, at seeds where the heading error passes 45°, resets
  write the wrong wall: lower than `integrated`, above `oracle_reset`; wrong-wall share above 0 at some seeds.
- **oracle_reset**: the error stays bounded (a stationary curve after the first contacts), set by the along-wall
  under-read during slides and the drift between contacts; **t1 passes**, **t2 passes**, **t3 passes**, **t4 passes**
  (a 45° error at σ 0.05 is a 16-sd event).
- **Sensitivity**: the level rises with σ and stays below the bound at 0.1; wrong-wall share 0 up to 0.2 rad.

## What would change this document

Nothing after the run. If a cell cannot run as specified, the deviation is recorded in G33.
