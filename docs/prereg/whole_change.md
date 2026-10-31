# Preregistration draft: the whole, part 2 — foraging when the world changes

**Written:** 2026-10-31, after part 1's confirmatory run (G57) and before any build or run of what it describes. The
owner's decision at G56 D2 ("agree, go"): the next target behaviour should be one that needs the parts resource
management did not (acetylcholine, noradrenaline, criticality, the action value, replay, memory). The parts and their
couplings are part 1's, unchanged (`docs/prereg/whole_resource.md` §2): part 1's confirmatory run found a reward-scale
mismatch that leaves the action value inert and dopamine's vigour near constant (G57 B4), and whether to tune the
parts jointly is the owner's call; this pilot runs the whole as it stands, as the baseline that call is made against.
The decisions entry for the pilot will be G58.

## 1. The behaviour

**Adapting to a change in where food is.** When food a mammal has learned to find is no longer there, it stops
returning to the old places (extinction), searches (an exploratory burst after the surprise), finds the new places and
re-establishes its intake (reversal learning in the water maze and on food-site tasks: Morris 1984; Vorhees & Williams
2006). Every part has a role in that: interoception and motivation keep it foraging, memory has to be revised,
noradrenaline answers the surprise of an empty site, acetylcholine raises encoding in the changed places, replay
consolidates the new map, and over an hour sleep pressure builds against hunger.

## 2. The task

Part 1's arena, cues, body physics and food (K = 0.065: the food's energy, calibrated in part 1, is a property of the
food, not of the task). **Three visible patches**, radius 0.75 units, regrowing 600 ticks after being eaten, at
(5, 5), (−6, −2), (2, −6) for the first 30 minutes; at tick 9,000 they move, without any signal, to (−5, 5), (6, −2),
(−2, −6) (mirrored; none within 3 units of an old one). A run is **18,000 ticks** (60 minutes), from E = 0.6.
Metabolism on in every configuration; starvation ends the run.

Disclosed design probe (before this document): hidden patches at the first layout, radius 1.0 or 1.25, gave the base
1 to 6 meals in 30 minutes (seeds 2001–2002, never used again): a meal at break-even would have been a third of the
body's capacity or more, so hidden food here is not a resource task, and the food is visible.

## 3. The spark: adapting

Measured from the physics in every configuration (windows in ticks):

- **A1, survival**: no starvation in 60 minutes on at least 11 of 12 seeds.
- **A2, recovery**: the energy eaten per tick in the last quarter-hour (13,500–18,000) is at least 0.8 times that in
  the quarter-hour before the change (4,500–9,000), averaged over seeds (a starved run counts 0 after it starved).
- **A3, extinction**: in the last quarter-hour, the share of awake ticks spent within 2 units of an old patch's centre
  is at most 1.5 times the share of the arena those zones cover (3 × π × 2² / 400 = 9.4%, so at most 14.1%),
  averaged over seeds.
- **The spark is A1, A2 and A3.**

Reported, no bound: the time from the change to the first meal at a new patch; the share of awake ticks near the old
patches in the five minutes after the change; the area covered (0.5-unit bins visited) in the five minutes after the
change against the five before (the exploratory burst); noradrenaline and the softmax temperature over the same
windows; meals, efficiency, sleep and the energy over the run; and, the whole against the whole with memory unread,
the energy eaten per unit of locomotor energy before and after the change (memory's margin and its cost).

What is wired and what is not: none of the parts was built for this behaviour. A3 alone is passed by an agent with no
memory at all (nothing pulls it back to the old places), so it is evidence of flexibility only together with A2 and
the memory margin.

## 4. The configurations and the emergence test

Part 1's 27: the base, the whole, the whole minus each of the twelve parts, the base plus each, the whole with memory
unread (`experiments/whole_resource.configurations`). The verdict's three conditions, as in part 1: the whole shows the
spark; no single addition to the base does; removing a single part breaks it for at least 6 of the 12.

## 5. Seeds and runs

Pilot 1–12. Reserved for a confirmatory run: 13–42, and a held-out relocation (patches moved to positions the pilot
never used). `experiments/whole_change.py --phase pilot`, from a clean tree with warnings as errors, writes
`docs/data/whole/change/pilot/`.

## 6. Predictions (written before any run)

- **The base** starves before the change on most seeds (three patches it rarely meets) or fails A2; it fails A1.
- **The whole** survives, recovers its intake (A2) and stops visiting the old places (A3): it passes. After the change
  it covers more ground for a few minutes than before it.
- **Memory unread** passes A3 (nothing pulls it back) and A1; its efficiency is lower before the change and no
  different after it.
- **No single addition** passes A1 (part 1: every single addition but orienting starved in scarcity; orienting
  overeats and does not regulate).
- **Removing interoception, motivation, dopamine or orienting** breaks the spark (part 1's scarce arena: these
  starve or cannot compensate). **Removing noradrenaline** slows the recovery but does not break it. **Removing
  acetylcholine, replay, sleep, criticality or the action value** changes nothing (the action value is inert at this
  reward scale, G57). So condition 3 fails again: the weak form, with four named parts.

## 7. Decision table (pilot)

| result | reading | what follows |
|---|---|---|
| 1 and 2, not 3 | the weak form again, on a behaviour none of the parts was built for | recorded; with part 1, the basis of the joint-tuning decision (G57 C1) |
| all three | the strong form, on adaptation | the owner registers a confirmatory run |
| the whole fails | the whole as it stands does not adapt | recorded; the joint-tuning decision is taken against both parts |
| a single addition shows it | one mechanism suffices | recorded, with which |

## 8. What would change this document

Nothing after the pilot's configurations have run. A pre-run amendment is recorded here, dated, before the pilot.

## The pilot ran (2026-10-31; `docs/data/whole/change/pilot/`; read in G58)

The whole shows the spark, but so does the base with dopamine, acetylcholine or orienting alone, and no single
removal breaks it: by §7, one mechanism suffices. With the food visible, adapting to its move needs no memory and
violates no expectation, so the task did not test the parts it was built for. This document is not changed after the
run; G58 C2 puts a redesign to the owner.
