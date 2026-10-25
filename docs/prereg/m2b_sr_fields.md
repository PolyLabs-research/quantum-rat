# Preregistration: successor features over the place code, step 3 of M2b

**Written:** 2026-10-25, before the evaluation run (branch `m2b-sr` stacked on step 2's `m2b-place` at `383a4cc`; the
decisions entry that reports the result is G35). **Scope:** step 3 of the four in `docs/prereg/m2b_estimate.md`: a
successor representation over step 2's place population, learned by TD from the agent's own transitions, against the
plan's row 2b items "after 50 laps on the track, SR fields skew backward against the running direction (Stachenfeld
2017)" and "near walls, fields elongate along the wall". The SR feeds nothing yet; V = M·R and behaviour are step 4.

**Disclosure.** A sanity check of the learner outside the engine (50 eastward laps of exact positions on a 20-cell
track) put three cells' SR field centres 1.9 to 2.6 units west of their own. A smoke of the experiment below (6 laps,
600 open-field ticks, two seeds) ran end to end: one-way fields shifted −0.42 units, two-way +0.02, and the open-field
wall elongation was 0.03 with an interval spanning 0 at that length. Neither is the evaluation; the predictions below
were written after seeing both.

## What is implemented

- **The learner** (`brain/systems/successor_features.py`): successor features ψ(s) = M φ(s) over the place
  population's rates normalised to sum 1 (a partition of unity, which keeps the TD fixed point finite), M from the
  identity by TD(0), M ← M + α δ φ(s)ᵀ with δ = φ(s) + γ M φ(s′) − M φ(s), no bootstrap across an episode boundary;
  α = 0.1, γ = 0.95 (the track protocol's discount since M2a). Element-wise numpy and `numpy.sum` only, so the tables
  reproduce bit for bit across platforms. A feature's SR field is ψ_j as a function of position.
- **The experiment** (`experiments/sr_fields.py`), with step 1's M2b estimate and step 2's population in both parts.

## Protocol

**Track.** A 2 m × 0.1 m corridor (world bounds 10 × 0.5 units), 20 cells along it, 50 laps, seeds 1–30. The agent's
own policy cannot run laps in a 0.1 m corridor (its turning circle is 0.1 m in radius, the corridor's half-width
0.05 m: the plan's kinematic caveat), so the protocol imposes the running: every tick the body is driven forward along
the track at a speed drawn uniformly from 0.5 to 1.0 units per tick from a protocol stream (seeds walk different
paths). `one_way`: each lap runs from the west wall to the east wall, then the body is carried back to the west wall,
an episode boundary for the SR, with the estimate re-anchored there (the rat put back on the start platform).
`two_way`: at each wall the body turns round in place and runs back, with no boundary. The SR field of each interior
cell (centres at least 3.5 units from either end: 14 cells) is evaluated along the track at 0.25-unit pitch; its
centre of mass minus the cell's centre is the shift (negative is backward for eastward running), with its skewness
and its peak's shift reported.

**Open field.** The 2 m box, the research agent's own walk, 12,000 ticks (40 minutes, four times steps 1 and 2, for
coverage), seeds 1–30. Each cell's SR field is evaluated on a 0.5-unit grid of the arena; above half its maximum, its
variance along and across the nearest wall. The wall truncates even the raw place field's region (its log
along/across ratio is about 0.8 before any learning), so the statistic is the SR's change: elongation = log(along /
across) of the SR field minus the same of the raw place field. Wall cells: centres 0.5 units from exactly one wall
(72 cells); interior cells: at least 3.5 units from every wall (196 cells), reported as log(var_x / var_y).

The seed is the unit; BCa 95% intervals over seeds (10,000 replicates); paired comparisons by seed with Cliff's δ.

## Preregistered tests

1. **Backward skew** (`t1_backward_shift`): one-way laps, the per-seed mean shift over interior cells is below 0,
   interval below 0.
2. **Direction-specific** (`t2_direction_specific`): one-way minus two-way shift, paired by seed: Cliff's δ ≤ −0.3 and
   the interval below 0. With features of position alone, a policy that runs both ways predicts its own past in both
   directions, so the skew cancels; the plan's bound reads as a property of directional running.
3. **Elongation along walls** (`t3_wall_elongation`): open field, the per-seed mean elongation over wall cells is above
   0, interval above 0.

Reported: skewness and peak shift on the track; the estimate's error in both parts; the interior cells' log ratio; the
SR fields' area relative to the raw fields'.

## Predictions (written before the run)

- **t1 passes**, with a shift of about −1.5 to −2.5 units (the sanity check's range, reduced a little by the random
  speeds, which shorten the effective horizon in units of distance); skewness negative (a tail to the west); the peak
  stays at the cell's centre (the SR adds a backward tail; it does not move the peak).
- **t2 passes**: two-way shift within ±0.3 units of 0.
- **t3 passes**, with less confidence: the agent spends 41% of its time sliding along walls, so transitions from a wall
  cell's field run along the wall and the SR extends there; interior cells' log ratio near 0, their SR fields larger
  than the raw fields (area ratio above 1).
- The estimate's error stays at step 1's level (track: under 0.5 units; open field: about 0.7).

## What would change this document

Nothing after the run. A deviation is recorded in G35.
