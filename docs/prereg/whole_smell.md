# Preregistration draft: the whole, part 2, second design — when the food moves, by smell

**Written:** 2026-10-31, after G59 and before any build or run of what it describes. The owner's decision at G58 C2
("agree, go"): redesign part 2 so that memory is needed and a move is a surprise, with food the agent can smell at
close range but not see from afar. The first design (`docs/prereg/whole_change.md`, G58) failed because the food was
visible: adapting was seeing. This one runs the parts with amendment A2's reward scale (9.7, G59); dopamine's tonic
level is as built (G59 C1, pending). The decisions entry for the pilot will be G60.

## 1. The new part: olfaction

Rats forage by smell, at close range, and compare their two nostrils to find a source's direction (Rajan, Clement &
Bhalla 2006; Khan, Sarangi & Bhalla 2012). The thirteenth part (opt-in: `sensors.olfaction`, `basal_ganglia.smell_gain`):

- **Odour**: at a point p, C(p) = Σ over food not yet eaten of exp(−max(0, |p − centre| − radius) / λ), clipped to
  [0, 1], with λ = 1.5 units (15 cm): a source is smelled to about 45 cm (C = 0.05), a fifth of the arena's width, so
  food across the arena cannot be smelled. Eaten food does not smell.
- **Two nostrils**, sampled 0.5 units from the body's centre at ±0.52 rad (30°) from the heading: the separation is
  exaggerated so one sample resolves a gradient, which a rat gets by casting its head and sniffing.
- **In selection**: strength s = (L + R)/2 and direction Δ = (L − R)/(L + R); FORWARD gains g·ι·s·(1 − |Δ|), the turn
  toward the stronger side g·ι·s·|Δ|; g = 0.6, the weight vision's pull to food has; ι is interoception's incentive
  (1 without it), as for vision.

## 2. The task

Part 2's arena, timeline and layouts (`FIRST` until tick 9,000 of 18,000, then `SECOND`, without a signal), but the
three patches are **hidden**: not seen, only smelled. Part 1's food (K = 0.065) and A2's reward scale.

**Feasibility rule, before the pilot.** On design seeds 2001–2004 (never used again) the whole must eat at least 6
meals in the first 30 minutes on average (one every 5 minutes); if not, a fourth patch is added to each layout
((−6, 6) in the first, (6, 6) in the second; placed again by amendment P1, §10) and the rule is checked once more;
the outcome is recorded here before the pilot. (The base needs nothing: it cannot smell, and hidden food is what it
rarely finds, G58's design probe.)

## 3. Validity, named first: does the task test what it is for?

- **V1, memory is needed.** Before the move (the quarter-hour before it, pinned by P1, §10), the whole's intake per
  tick is at least 1.25 times the whole's with memory unread (the means over the pilot's 12 seeds).
- **V2, the move is a surprise.** In the five minutes after the move the whole covers more ground (0.5-unit bins
  visited) than in the five before, paired by seed (`analysis.stats.paired_effect`, BCa 95%: the lower end above 0).

If either fails, the record says, before any reading of the bracket, that the task again does not test what it was
built to test.

## 4. The spark

As in part 2 (`docs/prereg/whole_change.md` §3): **A1** survival (no starvation in 60 minutes on at least 11 of 12
seeds), **A2** recovery (intake in the last quarter-hour at least 0.8 of the quarter-hour before the move), **A3**
extinction (in the last quarter-hour, time near an old patch at most 1.5 times chance). The spark is A1, A2 and A3.
Reported beside it: the share of time near the old places in the five minutes after the move (the return to where food
was, which memory predicts), the first meal at a new patch, noradrenaline and the temperature either side of the move.

## 5. The configurations and the verdict

29 configurations: the base, the whole (thirteen parts), the whole minus each, the base plus each, the whole with
memory unread. The verdict's conditions, as before: the whole shows the spark; no single addition does; removing a
single part breaks it for at least half the parts (7 of 13).

## 6. Seeds

Design probe 2001–2004; pilot 1–12; reserved for a confirmatory run 13–42.

## 7. Predictions (written before any run)

- **V1 passes**: without memory the whole finds food only where it happens to smell it. **V2 passes**: arriving at an
  emptied place where memory says food is, it searches.
- **The whole** passes A1–A3: it returns to the old places in the first minutes after the move (more than chance),
  then stops, finds the new ones by smell and search, and recovers its intake.
- **The base** starves; **no single addition** survives, olfaction included (the base's walk along the walls passes
  too far from the patches to smell them).
- **Removing olfaction, interoception or motivation** breaks the spark. **Removing dopamine** does not, and may help
  under the held-peak tonic level (G59). Removing orienting changes nothing (it orients to seen targets, and the food
  is hidden). **Memory unread** survives less often (V1). The others change little. So condition 3 fails: the weak form
  again, with the parts that do matter named.

## 8. Decision table (pilot)

| result | reading | what follows |
|---|---|---|
| V1 or V2 fails | the task does not test what it was built to | recorded first; a further redesign is the owner's call |
| V1, V2, and conditions 1 and 2, not 3 | the weak form on adaptation, now with memory needed | recorded; with G59 C1 (tonic dopamine as a rate), the basis of the next tuning decision |
| all three conditions | the strong form on adaptation | the owner registers a confirmatory run |
| the whole fails the spark | the parts as they stand do not adapt | recorded |

## 9. What would change this document

Nothing after the pilot's configurations have run. The feasibility rule's outcome and any pre-run amendment are
recorded here, dated, before the pilot.

## 10. Pre-run amendments

**P1 (2026-10-31, after the build and before the design probe; nothing had run).** Two corrections, both found while
writing the code, neither informed by any run:

1. *The fourth patch's places.* As drafted in §2, (−6, 6) in the first layout and (6, 6) in the second lie 1.4 units
   from the other layout's patches at (−5, 5) and (5, 5): inside the 2-unit zone that counts as an old place, so time
   at the new fourth patch would score as a return to an old one (A3), and the patch would barely move. Part 2's
   layouts keep every new place at least 3 units from every old one (`tests/experiments/test_whole_change.py`). If the
   rule needs it, the fourth patch is at **(−2, 7) in the first layout and (2, 7) in the second**: 3.6 units from the
   nearest place of the other layout, 7.3 from the start, and the layouts stay mirror images in x, as part 2's are.
   With four patches the chance share of A3 is 4π·2²/400 = 12.6% (three: 9.4%).
2. *V1's window, pinned.* "Before the move" in §3 is the quarter-hour before it (ticks 4,500–9,000), the window part
   2's table calls `intake_before` and A2 compares against: the time by which memory has had half an hour to form. The
   whole first half would mix in the minutes before any food is found, when memory cannot yet help.

The design probe (`--phase design`) runs the whole on seeds 2001–2004 and stops each run at the move, so nothing
after the move is seen before the pilot.
