# Preregistration: the gate with a barrier in the way (G47)

**Written:** 2026-10-27, after the pilot below and before any run on the confirmatory seeds (the commit that adds this
document is the registration; the decisions entry will be G47). **Scope:** the owner's step "bring in obstacles and
retest", first part: solid barriers, then the RQ4(a) gate with an L-shaped wall between two of its four starts and the
goal, with and without the start anchor. The second part (the agent learning to locate itself from what it sees,
replacing the anchor) is a later preregistration.

## Why

G46 asked whether the agent is told anything it should not know. The world then had no solid object at all: the agent
walked through every object and only the arena bounds stopped it. A barrier tests the owner's criterion directly: if
the agent gets to a hidden goal from a start whose straight line to it is walled off, with nothing in it knowing the
wall is there, the way round is its own.

## What the agent has (fb6589f; nothing tuned for this task)

- `core.world.Barrier`: a solid axis-aligned rectangle. A move stops just short of the first face it would cross (x
  leg, then y leg: a move at an angle slides along it; no step passes through). Rays and whiskers see it as `"wall"`.
  The touch sense reports the arena's walls only, so the declared wall-contact reset never fires against a barrier.
  Odometry is the true displacement: a blocked body feels it did not move.
- The agent's configuration is the research profile's, unchanged (the four rules of G46 E1: one configuration for
  every task; nothing knows which task it is in). Its wall reflex treats a barrier as any wall.

## Design

`experiments/g47_barrier_gate.py --phase confirmatory`. The gate's confirmatory settings (per-feature rule, one rate,
sources `sr`, `tabular`, `none`; sessions hidden and visible; 40 trials, read 21–40; goal (5, 5), radius 1; four
starts), trials started still, the sensing of G46. Four conditions, every seed in each (paired):

| condition | barriers | the estimate at each trial start |
|---|---|---|
| `open_anchor` | none | the true start (the registered gate) |
| `open_carry` | none | nothing |
| `L_anchor` | `L` | the true start |
| `L_carry` | `L` | nothing |

`L` (`experiments.rq4a_gate.LAYOUTS`): two walls 0.4 units thick, (0.6, 1.8)–(7.0, 2.2) and (0.6, 1.8)–(1.0, 7.0),
shielding the goal's south and west sides with a 3-unit gap at each free end. The west and the south start's straight
lines to the goal meet a wall (**blocked starts**; `blocked_starts("L")`); the east and the north start's pass a gap
(**direct starts**). Every statistic is per start group: per seed, the success over the read trials from that group's
starts (about ten trials each), and the median latency of the arrivals.

**Fresh seeds 155–184 (30).**

## Disclosed: the pilot (exploratory, spent seeds 31–42; `docs/data/g47/pilot/`, `--phase pilot`)

Run to see that the gaps are passable and to size the effects; the layout was fixed before it and not changed after.
Hidden success over trials 21–40, blocked / direct starts (median latency in ticks):

| condition | sr | tabular | none | visible, sr | visible, none |
|---|---|---|---|---|---|
| open_anchor | 1.00 / 1.00 (20 / 12) | 0.88 / 0.93 | 0.03 / 0.03 | 1.00 / 1.00 | 0.61 / 0.65 |
| L_anchor | 0.82 / 0.88 (95 / 11) | 0.83 / 0.82 | 0.00 / 0.00 | 0.94 / 0.90 | 0.46 / 0.66 |
| open_carry | 0.44 / 0.23 | 0.75 / 0.72 | 0.03 / 0.03 | 0.91 / 0.98 | 0.61 / 0.65 |
| L_carry | 0.41 / 0.10 | 0.55 / 0.57 | 0.00 / 0.00 | 0.85 / 0.87 | 0.46 / 0.66 |

## Predictions (from the pilot)

- **B1 (passable, reported).** In `L`, the reflex alone (`none`, visible session) reaches the goal from blocked starts
  on 30–60% of trials.
- **B2 (primary: the way round is learned).** `L_anchor`, blocked starts, hidden: `sr` 0.70–0.95, and `sr` − `none`
  above 0 with its BCa interval's lower end above 0.5.
- **B3 (what the wall costs).** `L_anchor` − `open_anchor`, `sr`, blocked starts, hidden: below 0, interval's upper
  end below 0 (predicted −0.05 to −0.30). The median latency from blocked starts in `L` is at least three times the
  open arena's (pilot 95 against 20): the way round is found by following the wall, not planned; reported.
- **B4 (without the anchor).** `L_carry`, blocked starts, hidden: `sr` 0.25–0.55, and `sr` − `none` above 0 with its
  interval's lower end above 0.
- **B5 (reported).** The tabular source beside the SR (pilot: it holds up better without the anchor, as in G46); the
  direct starts; the visible ceilings.

## Reading rules

- **B2 holds**: the record says the agent's learned memory gets it round a wall it was never told about, from starts
  that need a detour, with the no-steering control at the floor. With B3's latency, it is a way round found by
  following the wall, not a planned route; a path-efficiency measure and a shortcut test (the wall removed after
  learning) are the next questions, not this test's.
- **B2 fails**: the wall defeats the memory the open gate passed with; diagnose before the localisation step.
- **B4** is read with G46: how much of the way round survives without the anchor.

## Outputs and acceptance

`docs/data/g47/confirmatory/`: per condition the gate's own tables; `by_start_group.csv` (success and latency per
condition, source, session, seed and start group); `effects.csv` (per-cell means with BCa intervals; the barrier's
cost, the memory against no steering in `L`, the visible ceiling's cost, all paired by seed); `manifest.json`. From a
clean tree; the full test suite passes. After the run, gate seeds 155–184 are spent.

## What would change this document

Nothing after the first run. A finding wanting another layout or condition is a new preregistered step.
