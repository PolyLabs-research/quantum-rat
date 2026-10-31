# Preregistration draft: the whole, part 2, third design — a short reach, and an economy in balance

**Written:** 2026-10-31, after G61 and before any build or run of what it describes. The owner's go at G60 C1 ("go on
all"): redesign part 2 so that the task tests what it is for. The second design (`docs/prereg/whole_smell.md`, G60)
failed both validity checks, for two reasons this design removes: the odour of three patches reached two thirds of the
floor, so hidden food was found by smell during a sweep and memory was not needed; and the whole was in deficit from
the first minute, sweeping on four awake ticks in five, so a move could not show as a surprise and survival measured
the energy budget. The parts are as in G60 (part 1's twelve on A2's reward scale, olfaction the thirteenth; dopamine's
tonic level the held peak, G61). The decisions entry for the pilot will be G62.

## 1. What changes from the second design

Everything in `docs/prereg/whole_smell.md` §1–§6 holds (the arena, the three hidden patches in `FIRST` then `SECOND`
at minute 30 of 60 without a signal, regrowth after 600 ticks, the spark A1–A3, the 29 configurations, the verdict with
condition 3 at 7 of 13, V1 and V2 as amendment P1 pinned them), except:

1. **The odour's reach.** The length λ is set so that the three patches of a layout mark at most 15% of the floor at
   the encounter threshold (C ≥ 0.05), a rule on geometry alone: **λ = 0.5 units** (5 cm; the odour falls to 0.05 at
   15 cm past a patch's edge) marks 12% (λ = 1.0: 34%; the second design's 1.5: 66%). The layouts are mirror images,
   so the second marks the same share. The nostrils and the smell gain (0.6) are unchanged.
2. **The economy.** The food's energy K is the smallest on the ladder **0.065, 0.08, 0.10, 0.125, 0.15, 0.20** at
   which the whole is in balance before the move: on design seeds 4001–4004 (never used again), each run stopped at
   the move, its reserve averaged over the ten minutes before the move is at least 0.6 (where it starts), on average
   over the seeds, and no run starves. Every rung runs (24 runs); the rule picks. If no rung passes, the record says
   so here and the pilot does not run.
3. **The reward scale follows K.** A meal's reward is the drive it removes, which grows with the meal; so that a meal
   still brings about 1 (amendment A2's aim), the scale is 9.7 × 0.065 / K at every rung and in the pilot.

## 2. Validity, the spark and the verdict

As the second design (§3–§5 there, with P1): V1, the whole's intake in the quarter-hour before the move at least 1.25
times the whole's with memory unread; V2, more ground covered in the five minutes after the move than in the five
before, paired by seed, the BCa interval's lower end above 0. Either failing is recorded first, before the bracket.

## 3. Seeds

Design probe 4001–4004; pilot 1–12; reserved for a confirmatory run 13–42.

## 4. Predictions (written before any run)

- **The rule picks K = 0.10 or 0.125**: at 0.065 the whole ran a deficit with a long reach; a short reach makes food
  harder to find.
- **V1 passes**: with the odour short, the whole without memory finds food only where its sweep happens to pass within
  a few body lengths; the whole goes back to where it ate. **V2 passes**: in balance, the whole rests between bouts,
  and finding a remembered place empty sends it searching.
- **The whole** shows the spark: it returns to the old places in the first minutes after the move (more than chance),
  then stops, finds the new ones, and recovers its intake.
- **The base** starves (it follows the walls, which pass no patch). **The base with the rodent body** may survive on
  the richer food by sweeping (G60: it ate at nine tenths of the whole's rate), which would fail condition 2; the
  other single additions starve.
- **Removing** interoception, motivation, the rodent body or olfaction breaks the spark; removing orienting changes
  nothing (no food is seen); memory unread fails V1's margin and recovers more slowly. Condition 3 fails: the weak
  form, with the parts that matter named.

## 5. Decision table (pilot)

| result | reading | what follows |
|---|---|---|
| V1 or V2 fails | the task does not test what it was built to, a third time | recorded first; the owner's call whether part 2 continues in this form |
| V1, V2, conditions 1 and 2, not 3 | the weak form on adaptation, with memory needed | recorded; the parts that matter named; a confirmatory run is the owner's call |
| all three conditions | the strong form on adaptation | the owner registers a confirmatory run |
| the whole fails the spark | the parts as they stand do not adapt | recorded |

## 6. What would change this document

Nothing after the pilot's configurations have run. The design probe's outcome and any pre-run amendment are recorded
here, dated, before the pilot.

## 7. The design probe's outcome (2026-10-31, before the pilot)

`docs/data/whole/change/short_design/` (at `3406cb4`, clean tree, warnings as errors, 17.5 s): the whole on design
seeds 4001–4004, each run stopped at the move, odour length 0.5. Its reserve over the ten minutes before the move, by
rung (none starved at any): K 0.065, **0.50** (not in balance; 23.75 meals); **0.08, 0.63** (16.75 meals; asleep 15–16%
of the time); 0.10, 0.65; 0.125, 0.68; 0.15, 0.70; 0.20, 0.70. **The rule picks K = 0.08**, the reward scale 9.7 ×
0.065 / 0.08 = 7.88. The prediction (0.10 or 0.125) was wrong. Noted before the pilot: at 0.065 the whole ate about as
many meals before the move with the short reach as the second design's whole did with the long one (23.75 against
24.75), so finding the food was not made much harder. The pilot runs as §1–§3 describe.
