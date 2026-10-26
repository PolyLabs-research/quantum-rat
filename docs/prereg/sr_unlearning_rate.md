# Preregistration: an unlearning rate for the SR's per-feature reward rule (hidden food, research profile)

**Written:** 2026-10-26, after the circling measurement (`docs/decisions.md` G40) and before any run of this
experiment (the commit that adds this document is the registration; the decisions entry will be G41).
**Scope:** one knob on a rule already in force, tested on the task and with the instrument G40 measured it with.
No movement rule changes; the research profile's defaults do not change by this run.

## What happened before this document

- **G40 measured the circling.** On the research profile, memory steering (the SR value V = φ·MᵀR with the
  per-feature reward rule, `R += 0.5 φ (r − R)`) costs a third of the hidden-food finds: 17.6 against 26.5 without
  steering over eight seeds × 3,000 ticks (`docs/data/console_ablation/hidden_food_research/`), worse on every seed,
  with 1,254 ticks per run in memory-category orbits against none. Every one of the 147 memory bouts begins a median
  10 ticks after a contact, orbits at radius 1.24 units about one unit from the emptied site, and the turn is taken
  with probability 0.92 with the memory term and 0.13 without it. The agent eats, the value at the place outlasts
  the food (it regrows after 150 ticks), the steering turns toward the peak and the turn's 1-unit radius makes an
  orbit beside the site. In the empty arena the steering arms are identical; on the legacy profile memory helps.
- **The rule has one rate for both directions.** A cell's weight moves toward the reward it sees at rate 0.5 φ_i
  whether that reward is the food or nothing. The orbit's cells are active while the agent circles, so R does fall
  there; the bouts' median length (66 ticks) is what that fall takes at this rate.

## The change

`PlaceConfig.reward_unlearning_rate`: with the per-feature rule, the rate used on a tick whose reward is 0 (nothing
seen). `None`, the default, uses `reward_learning_rate`: the rule exactly as preregistered in G36, so every
committed result and the research baselines are unchanged (the determinism gates pin this). A value U > 0.5 makes R
fall faster at the active cells when nothing is there than it rises when something is. Nothing else changes: not the
read, not the SR, not the body.

## The runs (`experiments/sr_unlearning.py`)

Hidden food on the research profile, 3,000 ticks, arms matched by seed, every run logged (`metrics.decisions`) and
cut into orbits (`analysis.orbits`), as in G40. Arms: `no_steer` (`value_gain` 0: memory not read), `u0.5` (the
rule as it stands), `u<U>` (`reward_unlearning_rate` = U).

1. **Pilot, seeds 1–8, U ∈ {1, 2, 4}** (the G40 seeds; exploratory: it chooses U and nothing else). **The rule
   for choosing U**, fixed here: the U arm with the highest mean finds; a tie goes to the smaller U.
2. **Confirmatory, seeds 9–16 (none run before), the chosen U only**, with `no_steer` and `u0.5` on the same seeds.
   Command: `python -m experiments.sr_unlearning --phase confirmatory --unlearning <U> --prereg
   docs/prereg/sr_unlearning_rate.md --out docs/data/console_ablation/sr_unlearning_confirmatory`.

The pseudo-replication guard runs on the baseline arm's trajectories (the research profile's seeds are samples).

## Bounds (confirmatory run; paired by seed; `analysis.stats.paired_effect`, BCa 95%)

- **K1 (primary): finds.** finds(u<U>) − finds(u0.5): the interval's lower end above 0.
- **K2: the persistence.** Memory-category orbit ticks per run: mean(u<U>) ≤ 0.5 × mean(u0.5); the paired
  difference's interval reported.
- **K3 (the use test): not worse than no steering.** finds(u<U>) − finds(no_steer): the interval's lower end above
  −0.1 × mean finds(no_steer) on the same seeds (memory steering may cost at most a tenth of the floor).
- **Reported, no bound:** unique sites, distance per find, wall-contact share, productive and wall orbit ticks, the
  mean memory influence, reward; the pilot's dose curve over U.

## Predictions (written before any run)

- Pilot: finds rise with U and memory-orbit ticks fall roughly in proportion to 1/U; U = 2 or U = 4 is chosen (U = 4
  if the fall in persistence has not yet cost the memory its use, which I cannot tell beforehand).
- Confirmatory: **K1 passes** (a gain of 3–8 finds) and **K2 passes** (memory-orbit ticks under 600). **K3 is the
  uncertain one and I lean to it failing narrowly**: on this profile the no-steer agent's perimeter loop brushes the
  sites 26 times per run, and a steering that no longer persists may still not beat a loop the sites were placed
  beside (G21 put them 2.5 units in from the walls for the legacy agent's loop).

## Decision table (confirmatory)

| result | reading | what follows |
|---|---|---|
| K1, K2 and K3 pass | the persistence was the unlearning rate, and the steering now pays on the task | G41 recommends U as the research profile's default; adopting it is the owner's call (the research baselines regenerate once) |
| K1 and K2 pass, K3 fails | the persistence is removed, but the SR steering still does not earn its keep on hidden food | the knob stays available, the default unchanged; the reading goes to M3's design (the value source has to pay on a task) |
| K1 fails | the unlearning rate is not the lever | next suspect: the read (a 1-unit lookahead against a 1-unit turn radius), measured the same way |

## What would change this document

Nothing after the pilot's rule has chosen U. If the pilot's best U is the baseline itself (no U arm beats 0.5 on
mean finds), the confirmatory run uses U = 2 and the prediction is already failed on the pilot; that is reported.
