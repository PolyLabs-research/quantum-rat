# M2a, first pass: tabular replay on a linear track, four conditions over 30 paired seeds

**Status:** the first subset of Milestone 2a (docs/research_plan.md §4): four of the nine replay rules, fixed-budget
mode only, tabular oracle state, no reward-change schedule, no console panel. Decisions entry G26.
**Reproduce:** `python3 -m experiments.linear_track_replay --workers 4` (7 s on the 4-core development box; the
same tables byte for byte at any worker count). Outputs in `docs/data/m2a/track/`: `track_laps.csv` (one row per
condition × seed × lap, 4,800 rows), `track_per_seed.csv` (the tidy per-seed table), `track_summary.csv`,
`track_learning_curve.csv`, `track_effects.csv`, `track_replay_events.jsonl.gz` (3,599 events) and
`track_manifest.json` (code revision, platform, numerical environment, every parameter, the seed list, dependency
versions, the guard's verdicts). Tests: `tests/brain/test_replay_rules.py` (7) and
`tests/experiments/test_linear_track_replay.py` (11).

## In one paragraph

A tabular TD(0) agent (`TabularTD0`, M1's learner) runs 40 laps of a 40-cell linear track, back and forth between
two rewarded ends, choosing FORWARD or TURN by a softmax over the value one step ahead. After every rewarded lap it
pauses and makes exactly 20 replay backups under one of three rules, or none. Over 30 paired seeds, **replaying the
lap just run in reverse** cut the total steps needed for the 40 laps by 2,825 [BCa 95%: 2,147 to 3,497] from
14,490 (19%; faster on 27 of 30 seeds; Cliff's δ −0.88), **replaying the transitions with the largest current TD
error** cut them by 4,016 [3,310 to 4,813] (28%; faster on 30 of 30; δ −1.00) and was itself faster than reverse
replay by 1,191 [802 to 1,626] (δ −0.50), and **uniform replay over the stored transitions did nothing** the data
can distinguish from no replay (−224 [−820 to +112]; faster on 11 of 30 seeds; δ −0.03). The three replay
conditions made the same 800 backups per seed, 5.7–7.7% of the online updates. The ordering is the textbook one
for a sparse-reward chain, and that is the point of this pass: the instrument, not the ranking, is the result.

## The specification, fixed before the run

| | |
|---|---|
| Track and state | 40 cells of 0.5 unit (20 units = 2.0 m, docs/units.md, the plan's 10 × 0.5 box). Tabular state (cell, heading ∈ {east, west}, current goal end ∈ {east, west}): 160 states, handed to `TabularTD0` as a position (x the cell centre, y one of four values for heading × goal). The state is the body's true cell: this is the plan's tabular, oracle-state arm (M3 adds the embodied, noisy-estimate arm); odometry noise plays no part. |
| Actions | FORWARD (one cell along the heading; into a wall: no move, the step counts), TURN (flip the heading in place). |
| Lap, terminal | A lap starts at one end facing the other and ends on entering the goal cell, where a *consume* transition delivers the reward as a terminal transition from the goal state (V(terminal) = 0), so V(goal state) learns the reward about to be consumed and the lookahead sees it (M1's chain with cell 10 relabelled "goal"). The goal then flips; the next lap starts from the cell just reached, turned to face the new goal. A lap reaching 2,000 steps unrewarded is capped: back to its start end, same goal, no replay. 40 laps per seed; `reset_episode` at every lap end. |
| Reward | 1.0 at both ends, every lap; no reward-change schedule (RQ1(b) is the thresholded-mode question, later). |
| Online learning | TD(0), learning rate 0.2, discount 0.95 (0.95^39 = 0.135 keeps V above 0.1 along a lap), V = 0 at the start, one backup per step plus one for the consume. |
| Exploration | Softmax at temperature 0.1 (the research profile's) over FORWARD: 0.1386 + 10 · V(s′_FORWARD) and TURN: 10 · V(s′_TURN), s′ the known next state (the engine's own steering read, V one step ahead); `basal_ganglia.softmax_sample`, one `random()` per step on the `track_action` stream. The prior 0.1 ln 4 gives an untrained agent a turn probability of 0.2 per step (a persistent random walk); the gain 10 makes a value difference of 0.01 one temperature unit, enough to carry the far end (0.95^39 (1 − 0.95²) = 0.013 between facing toward and away at 39 cells). |
| Replay trigger | The reward-consumption pause at the end of every rewarded lap; once per lap. |
| Budget | Exactly 20 TD backups per trigger in every replay condition (the plan's fixed-budget mode), 0 in `none`. |
| Eligible memory | The newest 2,000 stored transitions (about ten learned laps), each with its own successor and terminal flag, so no backup links two laps. The reverse rule reads the lap just completed only. |
| Rules | `uniform`: one stored transition drawn uniformly, with replacement, per backup. `reverse_trajectory`: the lap just completed, newest transition (the consume) first, cycling when the lap is shorter than 20. `prioritised_td`: one stored transition per backup drawn with probability ∝ |TD error| + 10⁻⁶, the error recomputed under the current values before every draw (no stale priorities; prioritised sweeping with proportional sampling). |
| Randomness | `core.rng` named streams per seed: `track_action` (the policy), `replay` (uniform and prioritised draws; untouched by `none` and by the deterministic reverse sweep). The track draws nothing. |
| Primary outcome | Total steps over the 40 laps per seed (lower = faster learning), each replay condition against `none` paired by seed: `analysis.stats.paired_effect` (BCa 95%, 10,000 replicates) and `cliffs_delta`; the replay conditions against each other likewise. |
| Secondary | Steps per lap (learning curve, mean and BCa interval per lap), steps in the last ten laps, laps capped, reward collected, online and replay update counts and their ratio, RMS error of V against the exact V* = 0.95^(actions to the goal) over the 160 states, replay direction (the plan's position–time slope sign against the lap's travel direction, with the signed correlation `sequence_r` beside it), share of backups from the lap just completed, mean distance of backed-up states from the goal and the share more than 0.5 m (10 cells) from it. |
| Seeds | 1–30. The seed is the independent unit: laps and steps are aggregated within a seed before any interval. `pseudo_replication_guard` on every per-seed lap-length vector; the first lap must be identical across the four conditions at every seed (no replay has happened yet). |

**What was exploratory.** One pilot, before the parameters were frozen: the `none` condition alone at seeds 1–3
(`--conditions none --seeds 3`), against three criteria written down first: the untrained lap at least five times
the optimal 39 steps, the no-replay learning curve falling within 40 laps, no capped laps. It met all three (first
lap 351 steps on average; laps 31–40 summing to 3,216 against 4,300 for laps 1–10; 0 caps), so the a-priori values
above were kept and nothing was tuned. A 3-seed run of all four conditions was then made to check the mechanics
(20 backups per rewarded lap, one event per trigger, identical first laps); its effect sizes were seen but no
parameter was changed after it. The fixed evaluation is the 30-seed run below, and it is the only run reported.

## Results (`docs/data/m2a/track/`)

**Per-seed totals and paired effects** (n = 30; means with BCa 95% intervals; the paired effect is condition minus
`none` or minus the named condition, in steps, negative = fewer):

| condition | total steps over 40 laps | laps 1–10 | laps 31–40 | capped laps | final RMSE of V vs V* | replay backups | replay / online updates |
|---|---|---|---|---|---|---|---|
| none | 14,490 [13,980, 15,160] | 4,170 [3,840, 4,551] | 3,125 [2,850, 3,469] | 1 of 1,200 | 0.437 | 0 | 0 |
| uniform | 14,260 [13,720, 14,900] | 4,124 [3,787, 4,491] | 3,012 [2,773, 3,265] | 1 of 1,200 | 0.434 | 799 | 0.057 |
| reverse_trajectory | 11,660 [11,260, 12,090] | 3,812 [3,537, 4,142] | 2,102 [1,915, 2,325] | 0 | 0.397 | 800 | 0.069 |
| prioritised_td | 10,470 [10,040, 10,840] | 3,626 [3,376, 3,891] | 1,712 [1,577, 1,896] | 0 | 0.373 | 800 | 0.077 |

| comparison (b vs a) | mean difference in total steps [BCa 95%] | seeds with b < a | Cliff's δ [BCa 95%] | last-ten-laps difference |
|---|---|---|---|---|
| uniform vs none | −224 [−820, +112] | 11 of 30 (8 ties) | −0.03 [−0.32, +0.26], negligible | −113 [−430, +90] |
| reverse_trajectory vs none | −2,825 [−3,497, −2,147] | 27 of 30 | −0.88 [−0.95, −0.71], large | −1,024 [−1,347, −706] |
| prioritised_td vs none | −4,016 [−4,813, −3,310] | 30 of 30 | −1.00 [−1.00, −0.95], large | −1,413 [−1,734, −1,059] |
| reverse_trajectory vs uniform | −2,601 [−3,254, −1,972] | 28 of 30 | −0.82 [−0.93, −0.61], large | −911 [−1,201, −584] |
| prioritised_td vs uniform | −3,792 [−4,430, −3,177] | 29 of 30 | −0.95 [−0.99, −0.82], large | −1,300 [−1,592, −960] |
| prioritised_td vs reverse_trajectory | −1,191 [−1,626, −802] | 25 of 30 | −0.50 [−0.71, −0.22], large | −389 [−639, −153] |

Per-seed totals range 12,212–19,479 (`none`), 10,844–19,421 (`uniform`), 9,755–13,777 (`reverse_trajectory`) and
7,802–12,396 (`prioritised_td`). The 8 ties between uniform and none are seeds on which the uniform draws never hit
a transition with a non-zero TD error, so the table and hence the walk were unchanged.

**Learning curve** (mean steps per lap over 30 seeds, BCa 95% interval, median in brackets; `track_learning_curve.csv`
has every lap):

| lap | none | uniform | reverse_trajectory | prioritised_td |
|---|---|---|---|---|
| 1 | 351 [279, 449] (300) | 351 (300) | 351 (300) | 351 (300) |
| 3 | 506 [386, 677] (390) | 506 [385, 678] (390) | 499 [381, 674] (371) | 440 [336, 585] (354) |
| 10 | 447 [354, 578] (418) | 421 [333, 554] (370) | 458 [360, 593] (410) | 332 [249, 458] (223) |
| 20 | 340 [261, 479] (262) | 359 [283, 469] (275) | 278 [226, 351] (240) | 245 [188, 322] (177) |
| 30 | 292 [230, 386] (260) | 312 [248, 404] (278) | 281 [212, 399] (159) | 201 [159, 287] (144) |
| 40 | 341 [240, 524] (214) | 276 [220, 375] (234) | 196 [153, 262] (136) | 161 [128, 220] (132) |

Lap 1 is identical across conditions at every seed (checked; `first_lap_identical_across_conditions` in the
manifest). The optimal lap is 39 steps; no condition is near it after 40 laps, and the no-replay curve is still far
from converged, so the comparison is of learning speed over a fixed budget, not of asymptotes.

**Replay content** (means over the 1,200 events per condition):

| condition | direction: reverse / forward / neither | mean sequence_r (mean \|r\|) | backups from the lap just run | mean distance from the goal (cells) | more than 0.5 m from the goal | mean \|TD error\| of the backups |
|---|---|---|---|---|---|---|
| reverse_trajectory | 1.00 / 0 / 0 | −0.976 (0.976) | 1.00 | 8.9 | 0.40 | 0.050 |
| uniform | 0.48 / 0.52 / 0 | +0.012 (0.189) | 0.21 | 20.4 | 0.73 | 0.0029 |
| prioritised_td | 0.51 / 0.49 / 0 | −0.014 (0.191) | 0.16 | 18.2 | 0.60 | 0.097 |

Reverse replay is reverse by construction and its sequence correlation is −0.98 rather than −1 because a lap's last
20 steps include turns (the body did not run straight at the goal) and short laps cycle. Uniform and prioritised
replay are at chance on the direction label (the slope sign of 20 scattered states is a coin), with a mean |r| of
0.19, what 20 unrelated positions give; the label cannot distinguish them, and the plan's content questions need the
sequence statistics it fixes (≥ 4 distinct states spanning ≥ 0.3 m), which this pass does not compute. What
distinguishes the two is where they look: prioritised replay's backups carry a mean |TD error| of 0.097 against
uniform's 0.003 (thirty times the learning signal per backup), and it reaches 2.1 cells closer to the goal on
average while still spending 60% of its backups more than 0.5 m from it; uniform replay re-samples the whole memory,
73% of it remote and almost all of it already at its TD fixed point.

**Updates.** The online update count is the step count plus one consume per rewarded lap: 14,530 (`none`), 14,300
(`uniform`), 11,700 (`reverse_trajectory`), 10,510 (`prioritised_td`) per seed on average. Every replay condition
added exactly 20 backups per rewarded lap, 800 per seed (799.3 for `uniform`, whose seed 22 capped lap 8 and so had
39 triggers; `none` capped the same lap of the same seed, the two walks being identical until uniform's first
effective backup); as a fraction of the online updates that is 5.7% (`uniform`), 6.9% (`reverse_trajectory`) and
7.7% (`prioritised_td`), the fraction rising as the laps shorten. Event counts (1,200 or 1,199 per condition) and
backup counts (24,000 or 23,980) are both reported; the comparison is at equal backups per trigger.

**Guards.** `pseudo_replication_guard`: 30 distinct lap-length vectors in each of the four conditions (every seed a
sample; the `track_action` stream is drawn every step). Lap 1 identical across conditions at every seed. The BCa
interval on the final RMSE collapsed to the estimate in every paired comparison ("all bootstrap replicates equal", a
note the tables carry): the RMSE against V* is dominated by the 120 states the policy rarely visits, whose values
stay near 0 whatever the condition, so it moves little and almost identically across seeds; it separates the
conditions in the expected order (0.437 > 0.434 > 0.397 > 0.373) but is not a sensitive measure here.

## Reading

- **The ranking.** Prioritised sweeping and reverse replay both propagate the reward's TD error back along the lap
  in one pause, which online TD(0) does one cell per lap; uniform replay spends its 20 backups almost entirely on
  transitions already at their fixed point. On a sparse-reward chain that is the expected order (Moore & Atkeson
  1993; Lin 1992; Mattar & Daw 2018 derive the reverse-after-reward pattern from the same gain term), and the
  experiment reproduces it with intervals, which is what the plan asked of M2a's first pass. It is not a finding
  about rodents and not a test of the plan's RQ1: the direction label is at chance for the two sampling rules by
  construction, the thresholded mode, the reward-change schedule and the pre-run window are not implemented, and the
  state is an oracle.
- **Why prioritised beats reverse here.** Reverse replay is confined to the last 20 steps of the lap just run,
  which on an early random-walk lap are mostly near the goal (mean 8.9 cells from it) and include turns; the
  prioritised rule reaches any stored transition whose error is large, from this lap or the nine before it, and
  recomputes the errors as it goes, so it follows the error wherever the last backup moved it. The gap narrows in
  the last ten laps (−389 [−639, −153]) as both approach short laps.
- **The null.** Uniform replay is a floor and reads as one: its interval on the primary outcome spans zero, 8 of 30
  seeds are exact ties with no replay, and its per-backup TD error is 0.003. A null result is a valid result; it is
  reported as the plan's "random" floor with its interval.
- **The no-replay baseline learns slowly.** On-policy TD(0) under a random walk learns V^π of that walk, which is
  near 0 far from the goal, so the gradient that would straighten the walk builds from the goal outward one cell
  per lap; after 40 laps the mean lap is still 7–9 times the optimum. That is the regime in which replay has
  something to add, and it was chosen by the pilot's criteria, not by looking at replay's effect. A different prior
  or gain would move every number here; they are parameters of this protocol, stated, not tuned.

## Limitations and what is not claimed

- Oracle, tabular state over the true cell; no odometry noise, no place population. The embodied arm (M3) is the
  comparison this pass exists to be compared with.
- Four rules of nine; fixed budget only; no reward-change schedule, no pre-run window, no "remote event" by the
  plan's definition (the share more than 0.5 m from the goal is reported in its place); the event is a sequence of
  backed-up cells, not a sequence of ≥ 4 distinct states spanning ≥ 0.3 m, so the plan's event-rate metrics are
  not computed. RQ1 (a)–(d) are not tested.
- The replay rules run outside the engine, on the track's own loop, with the engine's learner, sampler, RNG and
  event record; wiring them into the engine's tick and the console's arena is M3's.
- Replay direction by slope sign is uninformative for sampling rules (it is a coin on 20 scattered states); the
  signed correlation and the content measures are the usable numbers.
- One learning rate, discount, temperature, prior and gain; no sweep. The ranking's robustness to them is untested.
- Linux only (the development box: Python 3.11.15, numpy 2.4.6, OpenBLAS 0.3.31 on the SkylakeX kernel, one thread,
  detected and verified by `threadpoolctl`); no BLAS product is used, and the tables are byte-identical across
  worker counts, but a second-machine reproduction has not been made.
