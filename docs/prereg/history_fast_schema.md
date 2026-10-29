# Preregistration: a fixed two-second taste schema for the SR's expected reward (history, research profile)

**Written:** 2026-10-28, after G53's fixed-schema probe (`docs/decisions.md` G53) and before any run of this
experiment (the commit that adds this document and `experiments/history_fast_schema.py` is the registration; the
decisions entry will be G54). The owner's decision at G53 D1: register a confirmatory run on fresh seeds, with adoption
into the research profile if it holds.
**Scope:** one opt-in mechanism already built (G52's history, with G53's fixed schema) tested for adoption on the
battery G53 piloted it on. No movement rule changes; the research profile's defaults do not change by this run.

## What happened before this document

- **G52 built history** (`brain/systems/history.py`): what the agent has sensed and done, and where, as decaying
  traces over the place code, one bank per channel at 2 s, 20 s and 200 s; for the channels in `reward_context` the
  SR's expected reward at each place is R + Σ u·h. With the schema u *learned* from R's prediction errors, history cost
  every memory task (hidden food 41.8 → 27.1 finds; the L arena's hidden goal 1.00 → 0.71); the learned schema was
  (−0.29, −0.25, +0.66) and R itself went to zero or below.
- **G53 fixed the schema** (`history.schema`: given, never learned; R keeps G36's rule and the history term is read on
  top) and probed three on spent seeds (gate and track 31–42, hidden food 1–8), both bodies. `fast`, (−1, 0, 0), "the
  place I am eating at is empty" two seconds wide, was the first history that cost nothing: hidden-food finds 46.5
  against 41.8 on the research profile (38.4 against 34.5 on the corridor body), the research body's laps 34.0 against
  30.1 traversals a run, the gate and the cues unchanged (0.96–1.00 against 0.96–1.00). `lap`, (0, −1, 0), and the
  learned schema hurt everywhere; the learned one's slow positive term was the harm.

## The change under test

`EngineConfig.research()` with `history.enabled = True`, `history.channels = ("taste", "visit")`,
`history.reward_context = ("taste",)`, `history.schema = {"taste": (-1.0, 0.0, 0.0)}` (the taste timescales at their
defaults, 10, 100 and 1,000 ticks). Nothing else: not the read, not the SR, not the body, not motivation (off).

## The runs (`experiments/history_fast_schema.py`)

The research profile, two arms matched by seed, `none` (the profile as it stands) and `fast` (the change), over
M3 step 2's battery (`experiments/m3_part2.run_battery`): the RQ4(a) gate in the open and the L arena, told the start
and told nothing with cues, sources `sr` and `none`, hidden and visible sessions, 40 trials; the alternating-reward
track, 3,000 ticks, the three arms (reward and memory steering; reward without steering; no reward); hidden food,
3,000 ticks, steering and no steering; the open field, reported. **Fresh seeds, none run before:** gate and track
245–274, hidden food 47–76 (spent: gate 1–244; track 1–60 and 215–244; hidden food 1–46).
Command: `python3 -m experiments.history_fast_schema --phase confirmatory --workers 28` →
`docs/data/m3/history_motivation/fast_schema_confirmatory/`, from a clean tree, warnings as errors.

## Bounds (paired by seed; `analysis.stats.paired_effect`, BCa 95%, 10,000 resamples)

- **K1 (primary): hidden-food finds with memory steering.** finds(fast) − finds(none): the interval's lower end
  above 0.
- **K2 (no loss on the gate):** on each of the six SR values (open and L hidden, told the start; open and L visible,
  told the start; open and L hidden, told nothing with cues), the mean difference fast − none is at least −0.03.
- **K3 (no loss on the track):** traversals per run with reward and memory steering, fast − none: the interval's lower
  end above −0.1 × mean(none).
- **Reported, no bound:** rewards per run and the two reflex arms on the track; hidden food without steering (G46's
  standard: every result with and without steering; on this profile steering is below no steering, 41.8 against 51.9
  on spent seeds, and this run does not test that); the no-steering gate controls; the open field; G53's eleven
  bounds for both arms.

## Predictions (written before any run)

K1 passes, a gain of 2–6 finds (the pilot's +4.7 on eight seeds; I expect it to shrink on thirty). K2 passes, every
difference within 0.02. K3 passes, +1 to +5 traversals. The uncertain one is K1's size: the two-second trace acts only
while the agent is at the site it has just eaten, and the gain is the orbits it does not make there; if the pilot's
eight seeds were the lucky ones, the lower end of the interval sits near 0 and K1 fails narrowly.

## Decision table (confirmatory)

| result | reading | what follows |
|---|---|---|
| K1, K2 and K3 pass | a consumption signal two seconds wide pays on the task that needs it and costs nothing elsewhere | G54 adopts the change into `EngineConfig.research()`; `PRE_G54` pins history off for every registration before it (carried by `PRE_G53` and `PRE_G50`); the research determinism baselines regenerate if they move (a second time in M3, reported) |
| K1 fails | the pilot's gain was its seeds' | history stays opt-in with the schema available; the reading goes to step 3 (a learned action value has its own way to carry "I just ate here") |
| K2 or K3 fails | the gain on hidden food is bought at the gate or on the track | history stays opt-in; the trade is recorded and the schema's width (2 s) is the next suspect |

## What would change this document

Nothing. The arms, seeds, bounds and the rule are fixed here; a run that stops on a numerical warning is reported as
such and re-run only after the fault is recorded in the decisions log.
