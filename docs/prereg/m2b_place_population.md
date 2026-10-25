# Preregistration: the place population over the corrected estimate, step 2 of M2b

**Written:** 2026-10-25, before the evaluation run (branch `m2b-place` stacked on step 1's `m2b-estimate` at
`127765e`; the decisions entry that reports the result is G34). **Scope:** step 2 of the four in
`docs/prereg/m2b_estimate.md`: a Gaussian place-cell population over the position estimate, its rate maps against
the body's true position, a decoder, and the engine's throughput with it, against the plan's row 2b items "decoding
error drops at wall contact" and "throughput ≥ 1,000 ticks/s with a 400-cell population". Nothing reads the
population yet: no action, learner or replay rule (step 3 builds the SR over it).

**Disclosure.** During development, three timed 3,000-tick runs gave about 15,000 ticks/s with the population on and
16,000 off; the decoder recovered six test positions (including two outside the arena) to 4 × 10⁻¹⁵ units; a smoke
of the experiment at 300 ticks and two seeds ran end to end with the same walk across estimates. None is the
evaluation; the predictions below were written after seeing them.

## What is implemented (off by default; every earlier hash and table unchanged)

- **The population** (`brain/systems/place_population.py`, `EngineConfig.place`): 400 cells on a 20 × 20 grid at
  1-unit (0.1 m) spacing over the 2 m box, rates r_j = exp(−|e − c_j|² / (2 w²)) at the estimate e with w = 1 unit
  (0.1 m; full width at half maximum 0.24 m), the Gaussian form of RatInABox's place cells. A rate model with no
  spiking or rate noise (plan §2.1): the code is a deterministic function of the estimate. The engine computes the
  rates in the spatial step when `place.enabled` is on, importing numpy only then (numpy rule 2); they enter no
  TickData field.
- **The decoder** (`PlacePopulation.decode`): for Gaussian tuning the log-rates are linear in the position, so a
  least-squares solve over the nine most active cells inverts the code exactly. With noiseless rates the decoded
  position is the estimate, so the decoding error with respect to the body *is* the estimate's error: the test below
  checks the code and the decoder, and the drop at contact follows from step 1.
- **Rate maps** (`analysis/place_metrics.py`): each cell's mean rate in 1-unit bins of the *true* position; two
  populations recorded on the same walk are compared cell by cell on the bins visited at least 5 times (Pearson
  correlation of the maps, distance between their rate-weighted centroids, Skaggs spatial information), for every
  cell whose reference map reaches 0.5 in a compared bin.

## Protocol

The research profile, the 2 m box, no objects, 3,000 ticks per run, seeds 1–30, the heading oracle (σ 0.05) and
wall-contact sensing on (step 1's sensors). Per seed, two engines walk the same body path (checked by a digest):
`integrated` (the research estimate) and `m2b` (step 1's estimate: oracle heading and reset), each with the population
on. The **reference** population is the same cells read at the body's true position on that walk, the code a perfect
estimate gives; its maps are the standard the other two are compared with. Wall cells: centres within 2 units of a
wall (the outer two rings, 144 of 400). After the runs, a throughput benchmark times one engine (the M2b estimate, a
3,000-tick run) five times with the population on and five off, in one process. The seed is the unit; BCa 95%
intervals over seeds; paired comparisons by seed with Cliff's δ.

## Preregistered tests

1. **Throughput** (`t1_throughput`): the median of the five timed runs with the population on is ≥ 1,000 ticks/s.
2. **The decoder** (`t2_decoder`): the decoded position differs from the estimate by less than 10⁻⁶ units at every
   tick of every run of both engine populations.
3. **Decoding error drops at wall contact** (`t3_decoding_drop_at_contact`): for `m2b`, the per-seed mean of the
   decoding error on the contact-onset tick minus the tick before is below 0, interval below 0.
4. **Map fidelity** (`t4_map_fidelity`): the per-seed mean map correlation with the reference is higher for `m2b`
   than for `integrated`, paired: Cliff's δ ≥ 0.3 and the interval of the difference above 0.

Reported without a bound: the map correlation, centroid shift and information ratio (population / reference) per
estimate, overall and for wall and interior cells; the decoding error's late median; the throughput with the
population off.

## Predictions (written before the run)

- t1 passes by an order of magnitude; t2 passes (the solve is exact to rounding); t3 passes (it is step 1's drop at
  contact, −0.56 units, read through the code).
- **t4 passes.** `integrated`'s estimate drifts to about 10 units late in the run, several field widths, so its maps
  are fields displaced and smeared across the arena: mean correlation **below 0.5**, centroid shifts of several units,
  information ratio below 0.6. `m2b`'s error, about 0.9 units, is under one field width: mean correlation **above
  0.85**, centroid shifts under 1 unit, information ratio above 0.8.
- **Wall against interior cells under `m2b`**: the reset makes the normal coordinate exact at every contact while the
  along-wall coordinate carries the slide under-read, so wall-cell fields are sharp across the wall and shifted along
  it; no prediction on which group correlates better, reported.

## What would change this document

Nothing after the run. A deviation is recorded in G34.
