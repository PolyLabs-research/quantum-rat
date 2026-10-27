# Preregistration: the agent locates itself from distal cues it learns (G48)

**Written:** 2026-10-27, after three disclosed pilots and before any run on the confirmatory seeds (the commit that
adds this document is the registration; the decisions entry will be G48). **Scope:** the owner's "obstacles" step,
second part, scoped with the owner as *position from cues* (the heading oracle stays, declared): can a cue map the agent
builds itself replace the start anchor G46 found the gate leaning on? And, found on the way, what G47's way round the
wall leaned on.

## Why

G46: told the true start at each trial (the anchor), the agent finds the hidden goal on 99.8% of trials; told nothing,
37.7%. A real rat in a water maze knows where it is from the room's cues. G47 put solid walls in the arena; the agent
got round them on 82% with the anchor, 41% without.

## What the agent has (`296ae86`, `d8a373e`; nothing given that it could not sense)

- **Distal cues** (`core.world.Cue`; `experiments.rq4a_gate.CUES`): four named cues outside the arena, at (−15, 12),
  (14, 15), (16, −10), (−13, −16), placed without symmetry, seen above its walls and barriers.
- **Sight of them** (`sensors.landmark_sensing`): each cue within a 300° field of view as a name, an egocentric bearing
  (error sd 0.05 rad) and a distance (error sd 10%), from its own stream. Never a position.
- **A learned cue map** (`spatial.landmark_gain` 0.1, `landmark_learning_rate` 0.01, `landmark_min_sightings` 20):
  each sighting places the cue where the estimate says it is (running mean, then rate 0.01); once a cue has 20
  sightings, the estimate moves 0.1 of the way per tick toward where the seen cues put it. The map starts empty. Learn
  the map slowly and correct the self fast, because cues stay put and the estimate drifts: values set from that reason
  before any run, not tuned.
- **Sideways odometry** (`sensors.lateral_odometry`, `d8a373e`): the displacement perpendicular to the heading, with the
  forward odometry's error. Added after the first pilot (below), in every condition of this test.

## Disclosed: three pilots (exploratory, spent seeds 31–42)

1. **Without sideways odometry** (`docs/data/g48/pilot_without_lateral/`, at `296ae86`): the cues lifted hidden success
   told nothing in the open arena from 0.34 to 0.97, but cost the L arena with the anchor (blocked starts 0.82 to
   0.36). One session (seed 31) showed the learned map drifting 0.2 to 2.7 units: a body sliding along a barrier moves
   partly sideways, the egomotion carried only the part along the heading, and the estimate, and from it the map, took
   a bias it could not see. **The fix is a sense, not a setting**: a rat feels its sideways motion.
2. **With it** (same seeds): the estimate in the L arena with the anchor is accurate (error 0.17 against 1.07), **and the
   SR's way round the wall falls from 0.82 to 0.24** (blocked starts). G47's result leaned on the unfelt slide, which
   carried the estimate through the wall toward the goal. G47's agent is therefore paired into this test.
3. **The final design** (`docs/data/g48/pilot/`, at `7437788`): pilot 2's conditions (identical numbers) plus G47's
   agent and the frame measure (the estimate's offset on arrival, trial to trial).

Pilot 3, hidden success over trials 21–40 (L: blocked / direct starts):

| condition | sr | tabular | none | frame spread |
|---|---|---|---|---|
| open, anchor, cues off / on | 1.00 / 1.00 | 0.90 / 0.85 | 0.03 | 0.19 / 0.27 |
| open, told nothing, cues off | 0.31 | 0.67 | 0.03 | 2.51 |
| **open, told nothing, cues on** | **0.94** | 0.85 | 0.03 | 2.01 |
| L, anchor, cues off | 0.24 / 0.48 | 0.88 / 0.90 | 0.00 | 0.21 |
| L, anchor, cues on | 0.40 / 0.55 | 0.90 / 0.89 | 0.00 | 0.26 |
| L, told nothing, cues off | 0.42 / 0.08 | 0.64 / 0.58 | 0.00 | 1.59 |
| L, told nothing, cues on | 0.53 / 0.89 | 0.30 / 0.67 | 0.00 | 1.13 |
| L, anchor, G47's agent | 0.82 / 0.88 | 0.83 / 0.83 | 0.00 | 1.31 |
| L, told nothing, G47's agent | 0.41 / 0.10 | 0.55 / 0.58 | 0.00 | 1.82 |

## Design

`experiments/g48_landmark_gate.py --phase confirmatory`: the gate's confirmatory settings (per-feature rule, one rate,
sources `sr`, `tabular`, `none`; hidden and visible sessions; 40 trials, read 21–40), trials started still, the
sensing of G46. Ten conditions, every seed in each (paired): `{open, L} × {anchor, carry} × {cues off, on}`, all with
sideways odometry, and `L_{anchor, carry}_off_nolateral` (G47's agent). Start groups as G47 (`blocked`: west and
south; `direct`: east and north; `all`). Per seed and group: success, median latency, the mean estimate error against
the body, and the frame spread (the mean distance of each read arrival's offset, estimate minus body, from the mean of
those offsets). **Fresh seeds 185–214 (30).**

## Predictions (from pilot 3)

- **C1 (primary: the cues give back what the anchor gave).** Open arena, told nothing, SR hidden, all starts: cues on
  0.80–1.0, off 0.20–0.45; on − off with its BCa interval's lower end above 0.3.
- **C2.** Open arena: SR hidden told nothing with cues, against told the start without them: the difference at or above
  −0.15.
- **C3.** L arena, told nothing, SR hidden, all starts: cues on − off above 0, interval's lower end above 0.
- **C4 (what G47 leaned on).** L arena, told the start, no cues, SR hidden, blocked starts: with sideways odometry minus
  without, −0.35 to −0.75, interval's upper end below 0.
- **C5 (reported).** The cues in the L arena with the anchor (pilot +0.16 blocked); the tabular source (pilot: the cues
  hurt it in the L arena told nothing, blocked 0.64 to 0.30); the visible sessions.
- **C6 (reported, the mechanism).** Told nothing, the frame spread is lower with the cues (pilot 2.01 against 2.51 open,
  1.13 against 1.59 in L), while the error against the body is not (the cue map is built in the estimate's frame,
  which told nothing starts shifted by the first start's offset: the agent navigates in a frame of its own).
- **Controls (G46 E1 rule 4).** In every condition the no-steering control stays at or below 0.05.

## Reading rules

- **C1 and C2 hold**: in the open arena, a cue map the agent builds from nothing gives back (most of) what the start
  anchor gave, so the anchor can give way to cues in open-arena protocols (the owner's call).
- **C4 holds**: G47's headline (82% round the wall) is withdrawn as stated: it leaned on a slide the agent could not
  feel, which carried its estimate through the wall; G47's number for the agent that feels it is this test's. The
  candidate cause of what remains is the value steering, which reads the value of places ahead of the estimate
  without regard to walls, so a goal behind a wall pulls the agent into it; a later step.
- **C3** says how much of the way round the cues restore without the anchor.
- **C1 fails**: the cue map does not localise the agent; diagnose before the anchor question goes further.

## Outputs and acceptance

`docs/data/g48/confirmatory/`: per condition the gate's tables (trial rows with the estimate's error and offsets);
`by_start_group.csv`; `effects.csv` (cell means with BCa intervals; the cues' effect per arena, start estimate and
source; the frame measures; the anchor left; G47's agent against sideways odometry); `manifest.json`. From a clean
tree; the full test suite passes. After the run, gate seeds 185–214 are spent.

## What would change this document

Nothing after the first run. A finding wanting another condition is a new preregistered step.
