# Preregistration: the corridor fix, a short wall range and a turn commitment (M3 step 1b)

**Written:** 2026-10-27, after step 1 (G44) and its disclosed probe, and before any run on the seeds below (the commit
that adds this document is the registration; the decisions entry will be G45). **Scope:** two action-selection
options, run with every body on fresh seeds; no profile default changes by this step.

## Why

Step 1 (G44) found that no body runs the plan's track (101.6 to 150.6 ticks a lap against a bound of 36). The decision
log traced the crawl to the action selection, not the body: a wall dead ahead scores the two turns almost equally, so
at the softmax temperature the agent dithers between them at the track's ends instead of turning round, and the wall
signal reads a wall out to the vision range (1.2 m), so in a 0.1 m corridor a heading about 5° off the axis already has
a wall ahead. **Disclosed: an exploratory probe** (seeds 101–104, the track only, the options patched in memory, not
committed): with the wall range cut to 0.2 m and a turn commitment of 0.3, the discrete body ran laps in 33.2 ticks
(stalls 0.2%), the quiet rodent body in 38.8, the noisy rodent body in 62.5; either option alone did little or worse.
The values below are the probe's; this step confirms them on seeds no run has used.

## The options (`BasalGangliaConfig`; both off by default, every baseline bit-identical)

- **`wall_avoid_range`**: the fraction of `sensors.vision_range` within which a wall on the centre ray counts as ahead;
  its closeness is `max(0, 1 − dist / range)`. 1.0 is every result to date. **Here 1/6: 0.2 m** at the default 1.2 m.
- **`turn_commitment`**: added to the previous tick's turn channel while a wall is ahead (closeness above 0), so the
  turn in progress keeps winning until the wall is no longer ahead. 0 is off. **Here 0.3.** It is a named term
  (`commit`) in the decision readouts, which still sum to the scores.

## Conditions (`experiments/body_characterisation.py --condition-set corridor`), on `EngineConfig.research()`

| condition | body | wall range | commitment |
|---|---|---|---|
| `discrete` | discrete | 1.0 | 0 |
| `discrete_corridor` | discrete | 1/6 | 0.3 |
| `rodent_quiet_corridor` | rodent_quiet | 1/6 | 0.3 |
| `rodent_corridor` | rodent | 1/6 | 0.3 |

**Seeds 31–60** (fresh: step 1 used 1–30, the probe 101–104), 3,000 ticks, the track and the open field, step 1's
measures (stall share as amended there). **The gate** (`experiments/rq4a_gate.py`, seeds **91–120**, the confirmatory
settings otherwise) with the corridor options, under the discrete body and under the quiet rodent body.

## Bounds

- **T1 (primary): `discrete_corridor` runs the track**: median ticks per lap ≤ 36 and stall share < 5%, each as the
  mean over seeds with its BCa 95% interval's upper end below the bound (step 1's T1).
- **T1′: the same bounds for `rodent_quiet_corridor`** (secondary).
- **G1 (gate) under each body with the options**: SR hidden ÷ visible ≥ 0.8 and arrival error < 2 units; **and the
  no-steering control's hidden success stays below 20%** (step 1 found the noisy body lifts it to 66.5%; a gate the
  control passes does not separate navigation from wandering).
- **Reported, no bound:** `rodent_corridor` on the track; every open-field measure for every condition (the options
  change how close the agent comes to a wall before it turns, so wall-zone share and orbits will move).

## Predictions (written before the run)

- T1 passes for `discrete_corridor` (about 33 ticks, stalls under 1%).
- T1′ fails narrowly or passes narrowly for `rodent_quiet_corridor` (36–40 ticks).
- `rodent_corridor` fails the lap bound (about 60 ticks).
- G1 passes under both bodies, SR hidden success above 95%, and the control stays below 20% under both.
- In the open field the options raise the wall-zone share (the agent turns later) and the orbit share falls.

## Decision table

| T1 | G1 (discrete) | Decision |
|---|---|---|
| passes | passes | **The corridor options are the candidate research-profile setting**, the owner's call (they move the research baselines, regenerated once with whatever else M3 adopts); step 2 builds the embodied track on the discrete body with them. If T1′ and G1 under the quiet rodent body pass too, it is offered as the alternative body |
| passes | fails | They run corridors but cost navigation: diagnose before step 2 |
| fails | any | Step 2 uses forced laps (G35's protocol), as step 1's table says |

## What would change this document

Nothing after the first run.
