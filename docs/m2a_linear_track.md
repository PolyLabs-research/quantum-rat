# M2a, first pass: tabular replay on a linear track, four conditions over 30 paired seeds

**Status:** the first subset of Milestone 2a (docs/research_plan.md §4): four of the nine replay rules, fixed-budget
mode only, tabular oracle state, no reward-change schedule, no console panel. Decisions entry G26.
**Reproduce:** `python3 -m experiments.linear_track_replay --workers 4` (7 s on the 4-core development box; the
same tables byte for byte at any worker count). Outputs in `docs/data/m2a/track/`: `track_laps.csv` (one row per
condition × seed × lap, 4,800 rows), `track_per_seed.csv` (the tidy per-seed table), `track_summary.csv`,
`track_learning_curve.csv`, `track_effects.csv`, `track_replay_events.jsonl.gz` (3,599 replays) and
`track_manifest.json` (code revision, platform, numerical environment, every parameter, the seed list, dependency
versions, the guard's verdicts); since step 1 of the remainder also `track_sequence_*.csv` (events by the plan's
definition, `python3 -m analysis.replay_metrics docs/data/m2a/track/track_replay_events.jsonl.gz`) and
`sensitivity_*.csv` (`python3 -m experiments.linear_track_sensitivity --workers 4`). Tests:
`tests/brain/test_replay_rules.py` (7), `tests/experiments/test_linear_track_replay.py` (11),
`tests/analysis/test_replay_metrics.py` (7), `tests/experiments/test_linear_track_sensitivity.py` (2).

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

## Step 1 of the remainder: events by the plan's definition, a visit-weighted value error, and a sensitivity sweep

Added after the fixed evaluation (decisions G27), without re-running it: the three additions below read the
committed data or run the same protocol at other parameter values, and every number of the fixed evaluation above
is unchanged (`track_laps.csv` gained one column, the per-seed, summary and effects tables gained rows for the new
metric, and every pre-existing row is byte-identical).

**Replay events by the plan's definition** (`analysis/replay_metrics.py`; `python3 -m analysis.replay_metrics
docs/data/m2a/track/track_replay_events.jsonl.gz`; tables `track_sequence_events.csv`, `track_sequence_metrics.csv`,
`track_sequence_rate_by_lap.csv`). The plan's event is a sampled sequence of at least 4 distinct states spanning at
least 0.3 m. Read off a replay's backup list: consecutive backups are linked when their start cells are the same or
adjacent (a TURN keeps the cell), a maximal linked run is a segment, and a segment with at least 4 distinct cells
spanning at least 6 cells (0.3 m at 5 cm per cell) is an event, with the direction and signed correlation of its own
cells against the lap's travel, and a remote flag when it starts more than 10 cells (0.5 m) from the agent, which
sits at the goal cell during the pause.

| condition | events per stop | stops with an event | direction of events | mean span (cells) | remote events | mean \|r\| |
|---|---|---|---|---|---|---|
| reverse_trajectory | 0.999 [0.997, 1.000] (1,199 of 1,200 stops) | 0.999 [0.995, 1.000] | 1.00 reverse | 16.9 [16.8, 17.0] | 0 (every event starts at the goal) | 0.977 |
| uniform | 0 | 0 | undefined (no event) | | | |
| prioritised_td | 0 | 0 | undefined (no event) | | | |

Under the plan's definition the two sampling rules produce no sequence events at all in this protocol: their
backups jump between transitions near the two ends of the track (both carry TD error) and never chain through four
adjacent cells. The slope-sign coin of G26 is thereby replaced by the honest statement: on the 1,200 pauses of each
rule, uniform and prioritised replay made no sequence by the plan's criterion, so their direction is not a
quantity. Reverse replay made one event at every pause but one (a lap whose last 20 steps wandered within five
cells), reverse by construction, spanning 17 of the 20 backed-up cells on average. How much this depends on the
extraction rule, from the same events: linking cells two apart adds four events in total (uniform 0.0025 per stop,
prioritised 0.0008); two apart with a span of four cells gives uniform 0.005 and prioritised 0.029 per stop; three
apart with three distinct cells over four gives uniform 0.13 and prioritised 0.30 per stop (reverse 0.46, remote
0.55), so even the loosest reading leaves the sampling rules an order of magnitude below the sequence rule. The
plan's reward-window and pre-run-window rates need the pre-run pause of step 2; here every pause is a reward pause.

**A visit-weighted value error.** The RMSE against V* over all 160 states (above) is dominated by the states the
policy rarely occupies and its paired intervals collapsed. `value_rmse_visited` weights each state by how often the
agent occupied it over the run; the final values are `none` 0.289 [0.286, 0.293], `uniform` 0.287 [0.284, 0.290],
`reverse_trajectory` 0.249 [0.246, 0.251], `prioritised_td` 0.226 [0.224, 0.229]; paired against `none`: uniform
−0.0027 [−0.0039, −0.0014] (lower on 28 of 30 seeds: uniform replay does move the visited states' values a little,
too little to move the walk), reverse −0.040 [−0.045, −0.037], prioritised −0.063 [−0.066, −0.059], and prioritised
against reverse −0.022 [−0.025, −0.020], every seed. The ordering is the one the steps give.

**Sensitivity of the ranking** (`experiments/linear_track_sensitivity.py`; `sensitivity_effects.csv`,
`sensitivity_summary.csv`; 11 variants × 4 conditions × 30 seeds, 79 s on 4 cores). Each variant changes one
parameter from the fixed set and re-runs all four conditions at the same seeds; the fixed evaluation's numbers stay
the result, this is what happens around them. Paired differences in total steps over 40 laps, mean [BCa 95%]:

| variant | none | reverse − none | prioritised − none | uniform − none | prioritised − reverse | capped laps |
|---|---|---|---|---|---|---|
| base (the fixed evaluation) | 14,488 | −2,825 [−3,497, −2,147] | −4,016 [−4,813, −3,310] | −224 [−820, +112] | −1,191 [−1,626, −802] | 2 |
| learning rate 0.1 | 15,985 | −2,076 [−2,689, −1,589] | −3,597 [−4,193, −3,010] | +100 [−95, +453] | −1,520 [−2,116, −1,019] | 4 |
| learning rate 0.5 | 12,598 | −5,824 [−6,281, −5,314] | −5,595 [−6,119, −5,067] | −233 [−398, −73] | **+229 [+9, +496]** | 2 |
| discount 0.9 | 14,696 | −2,926 [−3,483, −2,291] | −4,037 [−4,745, −3,348] | −160 [−490, +156] | −1,111 [−1,461, −803] | 2 |
| discount 0.98 | 14,412 | −2,940 [−3,502, −2,343] | −4,142 [−4,930, −3,537] | −296 [−864, +50] | −1,202 [−1,666, −818] | 2 |
| temperature 0.05 (= gain 20) | 14,228 | −2,930 [−3,398, −2,339] | −3,942 [−4,550, −3,378] | −204 [−621, +24] | −1,012 [−1,380, −653] | 2 |
| temperature 0.2 (= gain 5) | 14,787 | −2,900 [−3,438, −2,334] | −4,023 [−4,728, −3,368] | −77 [−257, +150] | −1,123 [−1,503, −815] | 2 |
| untrained turn probability 0.1 | 8,340 | −1,337 [−1,684, −1,010] | −1,881 [−2,264, −1,502] | −133 [−259, −58] | −544 [−801, −282] | 0 |
| untrained turn probability 0.3 | 23,148 | −4,545 [−5,498, −3,664] | −6,502 [−7,448, −5,512] | −90 [−578, +251] | −1,957 [−2,723, −1,349] | 63 |

Both sequence rules beat no replay with intervals excluding zero in all 11 variants. Prioritised beats reverse in 10
of 11; at learning rate 0.5 the order flips (reverse 6,774 against prioritised 7,003 steps), where a single reverse
sweep at a large step already carries the reward's error the length of the lap tail and the prioritised rule's
scattered backups buy nothing more. Uniform is a null in 9 of 11 and a small real gain in two (learning rate 0.5 and
turn probability 0.1, both regimes in which the no-replay walk is short enough for a few effective uniform backups
to show). Two pairs of variants are the same experiment: the softmax reads the scores divided by the temperature,
and with the prior rescaled to hold the untrained turn probability, temperature 0.05 at gain 10 is gain 20 at
temperature 0.1 and temperature 0.2 is gain 5, so the table above has nine distinct variants (the two gain rows are
omitted; `sensitivity_summary.csv` carries all 11, identical to the digit). The turn-probability axis moves the
baseline most (8,340 to 23,148 steps) and at 0.3 the cap of 2,000 steps is hit on 63 of 4,800 laps.



## Step 2 of the remainder: the RQ1 protocol on the floors, thresholded mode, and the dose-response

Preregistered in `docs/prereg/rq1_track_tabular.md` before any run (its pilot clause moved θ once, from 0.02 to
0.0035, recorded there); decisions entry G28. Runners: `experiments/linear_track_rq1.py` (both budget modes, 258 s on
4 cores) and `experiments/linear_track_dose_response.py` (28 s); tables in `docs/data/m2a/rq1/`. The three rules here
are the plan's floors; the prereg predicted which RQ1 bounds each would fail, and this section reports every verdict
against those predictions. The guard found 30 distinct lap-length vectors in every condition and mode.

**The protocol.** The fixed evaluation's track and agent, 80 laps in four blocks of 20 (east reward 1.0, 4.0, 1.0,
0.25; west 1.0 throughout, the control end), a pre-run pause at the start of every lap beside the reward pause at its
end, both running the condition's rule on the same memory; fixed mode makes 20 backups per pause, thresholded mode
replays while the rule's priority exceeds θ = 0.0035 up to 100 backups per pause. Events are the plan's (step 1), their
direction read against the lap the replayed states belong to.

**Dose-response** (`dose_response_effects.csv`, `dose_response_slopes.csv`; the 40-lap stable-reward protocol at 5, 10,
20 and 40 backups per reward pause, 30 seeds; 20 reproduces the fixed evaluation to the digit):

| backups per pause | uniform − none | reverse − none | prioritised − none |
|---|---|---|---|
| 5 | −23 [−359, +209] | −1,511 [−2,044, −988] | −1,564 [−2,171, −938] |
| 10 | −7 [−304, +274] | −2,232 [−2,798, −1,590] | −2,560 [−3,195, −1,799] |
| 20 | −224 [−820, +112] | −2,825 [−3,497, −2,147] | −4,016 [−4,813, −3,310] |
| 40 | −283 [−717, +57] | −2,815 [−3,495, −2,139] | −5,891 [−6,549, −5,344] |
| slope per doubling | −100 [−219, −13] (negative on 18 of 30 seeds) | −450 [−604, −322] (28 of 30) | −1,444 [−1,628, −1,252] (30 of 30) |

Prioritised replay does what the causal reading requires: its effect grows with every doubling, every seed. Reverse
replay grows from 5 to 20 and then stops (40 equals 20): a sweep is one pass over the lap tail, and the backups beyond
the first twenty or so carry no TD error (the chain of errors behind a consume decays by a factor of about 0.19 per
transition), so more of them change nothing; its slope is negative because of the first half of the range. The
preregistered prediction (effect growing with the dose) therefore holds for prioritised and holds for reverse up to
saturation, which is itself the mechanism showing: the dose that matters is error-carrying backups, not backups.
Uniform stays a null at every dose as predicted, with a small trend (more draws, more chances to hit a transition with
error) whose interval just excludes zero against the prediction of none.

**RQ1 verdicts** (`rq1_tests.csv`; n = 30 seeds unless marked; the prediction in brackets is the prereg's):

| test | reverse_trajectory | uniform | prioritised_td |
|---|---|---|---|
| (a) reverse share of reward-pause events > 0.6 | 1.00 [1.00, 1.00], **passes** (predicted) | undefined, no events (predicted) | undefined, no events (predicted) |
| (a) forward share of pre-run events > 0.6 | 0.00, **fails** (predicted: it replays the completed lap backward) | undefined | undefined |
| (d) remote events ≥ 10% | 0.00, **fails** (predicted: every sweep starts at the goal) | undefined | undefined |
| (b) east end, ×4 block − baseline, backups per stop | +10.3 [+10.2, +10.3] (8.6 → 18.9), **passes** (predicted) | +81 [+72, +87] (18 → 99, the cap), passes, degenerate | 0 (100 → 100, the cap), degenerate |
| (b) east end, ×4 block − baseline, reverse events per stop | +0.30 (0.70 → 1.00 at every seed), **passes** | 0 events | 0 events |
| (b) east end, ×0.25 block − washout, backups per stop | **+1.7** [+1.5, +1.7] (24.8 → 26.4), **fails "down"** (predicted: an unsigned rule rises) | 0 (cap) | 0 (cap) |
| (b) east end, ×0.25 block − washout, reverse events per stop | −0.20 (1.00 → 0.80 at every seed), meets the criterion, see below | 0 events | 0 events |
| (b) west control end, ×4 block − baseline | −8.7 [−8.8, −8.7] backups (8.7 → 0): **not equivalent** | +80 (16 → 96, the cap) | 0 (cap) |
| (b) forward rate unchanged | degenerate: no forward events anywhere | degenerate | degenerate |
| (c) rate falling across laps in block 1 | slope **+0.18** [+0.17, +0.18] backups per lap, **fails** (predicted: falls) | −0.53 [−1.50, +0.29], fails | 0 (cap), fails |

What the thresholded mode did, rule by rule:

- **reverse_trajectory.** Its priority is the TD error of the next transition of its sweep, read first at the consume.
  While the goal's value is off by more than θ the sweep runs the whole lap (the chain of errors behind a changed
  reward stays above 0.0035 for about thirty pauses at |Δr| = 3 and twenty-four at 0.75); once the goal's value is
  within θ the sweep never starts, whatever error lies deeper in the lap. So its rate is a step function of the goal's
  surprise. That gives: within block 1, backups per stop grew lap by lap (4, 6, 7, 9, …, 14 as the value front moved
  back along the track) and collapsed to 0 at lap 19 when V(goal) passed 1 − θ, a rise and a cliff rather than the
  decline (c) asked for, and the decline the pilot showed at θ = 0.02 (0 from lap 13) moved past the end of the block
  at θ = 0.0035; at the west end, whose reward never changes, 0 backups and 0 events in blocks 2 to 4 (the "control
  end unchanged" test fails because the end went quiet, 8.7 → 0, not because it moved with the east end); at the
  east end whole-lap sweeps through blocks 2, 3 and 4 (18.9, 24.8, 26.4 backups per stop, the laps shortening), so
  the rate rose at the ×4 increase and rose again at the ×0.25 decrease, the unsigned-rule prediction, and the
  "down at the reduced end" bound fails on the rule's own rate. The reverse-event count did fall there (1.00 → 0.80,
  identical at all 30 seeds, so the interval collapses): the surprise of a 0.75 change decays below θ two pauses
  before the block ends (|Δr| · 0.8ⁱ with three backups of the consume per lap), so laps 77 and 79 made no replay at
  any seed, where the washout block's surprise of 3.0 lasted the whole block. The criterion is met on events by the
  same unsigned mechanism, a shorter-lived surprise, not by a signed response to a loss; the backups-per-stop row is
  the honest reading of (b).
- **uniform** and **prioritised_td.** Their priorities are the mean and the largest |TD error| over a memory of 2,000
  transitions. The largest exceeds 0.0035 at every pause from the first lap on and the mean from the first reward
  change on, so both rules replay to the cap of 100 at (almost) every pause: the deviation case the prereg named (a
  cap that binds), so their thresholded rows are exploratory and degenerate. Neither made a single sequence event in
  either mode, under a reward change included (G27 C's open question, answered: no); their backups are scattered.
- **Fixed mode** behaved as in step 1 across the reward schedule: the reverse rule made an event at every reward pause
  and at 98.7% of pre-run pauses (1,199 and 1,184 of 1,200), all reverse relative to the replayed lap; the sampling
  rules none. In fixed mode (`rq1_adaptation.csv`) the reward changes left no visible transient in any condition
  (the policy is the same whatever the reward's size; only V's scale moves, which sharpens or softens the softmax):
  mean steps on the first lap of each block were 351 / 271 / 334 / 270 for `none`, 351 / 201 / 135 / 110 for reverse
  and 351 / 195 / 134 / 95 for prioritised, the learning continuing through the schedule.

What this step establishes: the protocol, both budget modes and the plan's metrics run end to end with manifests and
intervals; the three floors behave as the prereg predicted on (a) and (d); the reverse rule's thresholded rate tracks
the magnitude of the reward surprise and not its sign (the discriminating prediction for step 3's signed rule); and
the familiarity test is sensitive to θ in a way the prereg did not anticipate (a step function cannot show a decline
inside a block unless θ is set so that the goal's value crosses 1 − θ inside it). Nothing here is the RQ1 test, which
is step 3's.

## Step 3 of the remainder: gain × need and its ablations on the preregistered protocol

Preregistered in `docs/prereg/rq1_track_gain_need.md` before any run, with two pre-run amendments recorded there
(the successor representation learns the inter-lap placements and starts from the known cyclic structure under a
uniform-random policy, because the rule as first written had a need of exactly zero for every candidate at every
reward pause) and the per-rule θ values of its pilot; decisions entry G29. Runner: `experiments/linear_track_rq1.py`
(the default, step-3 version; `--version step2` reproduces step 2), 17–20 min on 4 cores; tables in
`docs/data/m2a/rq1_step3/`. Seven conditions: the four of step 2 (the trajectory rule now with its "remaining
sweep" priority) and `gain_need`, `gain_only`, `need_only` (`brain/systems/replay_gain_need.py`,
`brain/systems/successor.py`). The guard found 30 distinct lap-length vectors in every condition and mode.

**The rules.** Need is a tabular successor representation over the 160 states (M starts as the SR of the cyclic lap
structure under a random policy and learns by TD on every state change the agent lives through), read from the
state the agent acts from next, the start of the next lap. Gain is Mattar & Daw's, read on this track: a backup moves
V(s), the decisions that read V(s) are at s's predecessors, and gain is the expected improvement of those decisions
under the policy's softmax, evaluated with the updated values. gain × need is their product; the ablations each term
alone. Selection is the argmax over the distinct stored transitions, recomputed after every backup; no draw is made.
θ per rule, from the pilot: 1.6 × 10⁻⁷ (gain × need), 2.7 × 10⁻⁴ (gain-only), 2.7 (need-only), 0.137 (reverse),
0.156 (prioritised), 0.0027 (uniform).

**Fixed mode, what the rules replay** (all blocks pooled, 30 seeds):

| condition | events per reward pause | reverse share | forward share | remote share | events per pre-run pause | reverse / forward / remote |
|---|---|---|---|---|---|---|
| gain_need | 0.63 | 1.00 | 0.00 | 0.999 | 1.07 | 1.00 / 0.00 / 1.00 |
| gain_only | 1.01 | 0.998 | 0.001 | 0.65 | 1.22 | 0.997 / 0.002 / 0.78 |
| need_only | 0 | undefined | | | 0 | undefined |
| reverse_trajectory | 1.00 | 1.00 | 0.00 | 0.00 | 0.99 | 1.00 / 0.00 / 0.00 |
| uniform, prioritised_td | 0 | undefined | | | 0 | undefined |

gain × need makes reverse sequences at both pauses and almost every one of them starts far from the agent. That is
not reverse replay of the lap just run: need from the next start weights the states of the lap *ahead* (the lap just
run lies a full lap further round the cycle, at a need of about γ^lap), so at a reward pause the rule sweeps the
upcoming lap backward from its goal at the far end, and does the same at the pre-run pause. The `from_this_lap_share`
column of `rq1_seed_blocks.csv` gives the share of a reward pause's backups that came from the lap just run: 0.013 for
gain_need against 1.00 for reverse_trajectory (0.69 for gain_only, 0.17 for uniform, 0.10 for prioritised_td; fixed
mode, mean over seeds and blocks). Gain alone
also chains backward from where the policy is still undecided, nearer the agent (remote 0.65), and need alone replays
the acting state's own transitions over and over (the largest need is the state itself), which form no sequence and
carry no error. The floors are as in step 2.

**The RQ1 verdicts** (`rq1_tests.csv`; the prereg's prediction in brackets):

| test | gain_need | gain_only | need_only |
|---|---|---|---|
| (a) reverse share at reward pauses > 0.6 | 1.00, **passes** [pass] | 0.997, **passes** [pass] | undefined, no events [fail] |
| (a) forward share at pre-run pauses > 0.6 | 0.00, **fails** [pass, less confident] | 0.002, fails [fail] | undefined [fail] |
| (d) remote events ≥ 10% | 0.999 / 1.00, **passes** [pass] | 0.65 / 0.78, passes [fail] | undefined [pass] |
| (b) ×4 block − baseline, east, thresholded | events per stop +3.52 [+3.21, +3.78], passes; backups 19 → 99 (the cap) | events **−0.20** [−0.28, −0.13], **fails**; backups 19.4 → 7.9 | backups +17 [+7, +27], δ 0.40, passes; no events |
| (b) ×0.25 block − washout, east | events −0.36 [−0.68, −0.05], δ −0.31 [−0.57, −0.02], **passes the criterion**; backups 100 → 100, fails | events +0.07 [−0.01, +0.14], fails | no events; backups +3 [−6, +11] |
| exploratory: ×0.25 block − baseline, east (not preregistered) | events **+2.64** [+2.33, +2.91]; backups +81 | events −0.24 [−0.32, −0.17] | backups +23 |
| (b) west control end, ×4 block − baseline | events +2.87 [+2.50, +3.23]: **not equivalent** | events −0.15 [−0.24, −0.08]: not equivalent | backups +10 |
| (c) rate falling across laps, block 1 | backups slope **+4.6** per lap (to the cap), fails; first lap at 0: lap 1 (the first pause, EVB below θ) | backups slope −2.31 [−2.37, −2.24], **passes**; first lap at 0: 5.2 | fails |
| (c) block 3 | backups 0 (cap), fails; events −0.030 [−0.056, −0.001], passes | fails | fails |

Floors with step 3's changes: reverse_trajectory (remaining-sweep priority, θ 0.137) rises at the ×4 increase (events
0.20 → 0.90, backups 4.0 → 10.5), falls from the washout to the decrease on backups (17.6 → 14.7, **passes "down"**)
and rises against the baseline (+10.7 backups, +0.8 events), goes quiet at the unchanged west end (4.0 → 0), and now
passes (c) in block 1 (slope −0.038 [−0.040, −0.037], 0 from lap 17), the change G28 C1 asked for. prioritised_td and
uniform run to the cap from the first reward change (prioritised 54 → 92 → 100 → 100 backups per stop) and make no
sequence event; need_only's rate hovers at its θ (52 → 69 → 72 → 75, no events).

**Learning speed** (`rq1_learning.csv`; mean total steps over the 80 laps, fixed mode): none 25,627; uniform 24,343;
reverse 14,633; prioritised 13,134; gain_need 11,945; gain_only 11,121; need_only 25,627, identical to none (its
backups carry no TD error). Thresholded: prioritised 9,360 (100 backups per pause), gain_need 12,550, gain_only
14,533, reverse 19,944, uniform 21,278. The prereg's last prediction (the gain rules at least as fast as prioritised)
holds in fixed mode on the paired differences as well: gain_need − prioritised −1,189 [−1,557, −780] steps, faster on
26 of 30 seeds, Cliff's δ −0.63 [−0.80, −0.36]; gain_only − prioritised −2,013 [−2,385, −1,679], faster on 30 of 30,
δ −0.81 [−0.93, −0.60]; against none, −13,682 [−14,470, −12,950] and −14,506 [−15,233, −13,785], faster on every
seed. need_only − none is exactly 0 on every seed (δ 0 [−0.29, +0.30]). Uniform − none is −1,284 [−1,825, −766],
faster on 25 of 30 (δ −0.35 [−0.60, −0.06]): on this protocol uniform is no longer the null it was in the 40-lap
fixed evaluation (G28). The two runs differ in length and in reward scale (the ×4 block raises every TD error), so
which of these moved it is not separated here. In thresholded mode the ordering inverts at the top:
prioritised at the cap of 100 backups per pause is fastest (−16,267 [−17,052, −15,508] against none), gain_need
−13,076 [−13,886, −12,319], gain_only −11,094 [−11,752, −10,359].

**Reading the thresholded results.** Three facts organise them. First, gain × need's θ is the median of a baseline
EVB of order 10⁻⁷; any change of the reward's scale moves every gain in the lap's states by a factor of that scale, so
after the first change the largest EVB exceeds θ at every pause and the rule replays to the cap of 100 for the rest of
the protocol, at the changed end and the control end alike. Its (b) verdicts therefore rest on how many of 100 backups
chained into sequences, and both changes raised that count about sevenfold against the baseline: in effect unsigned.
The preregistered "down" test passes because its reference, the washout block, carries a surprise of 3.0 against the
decrease's 0.75, so a rule that follows the size of the surprise passes it for a magnitude reason; the exploratory
comparison against the baseline block, added after the run and labelled so, shows the decrease *raising* the rate for
every rule that responds at all (gain × need +2.64 events per stop, reverse +0.8). The protocol as preregistered cannot
separate a signed response from an unsigned one; a decrease block preceded by a baseline block can, and step 4 should
have one. Second, gain alone falls after the ×4 increase (19.4 → 7.9 backups per stop) and stays low: gain is the size
of the change a backup makes to a decision, and a larger reward scale saturates the softmax at the goal's neighbours,
so there is less to gain; the gain term tracks decision uncertainty, not reward surprise. Third, the direction label
reads the plan's definition against the lap the replayed states belong to, and under that definition every sequence
these argmax rules produce is reverse: a backup of V(s) changes decisions at s's predecessors, which lie behind s, so a
chain of greatest-improvement backups walks backward in space whatever the pause. Forward replay before a run, which
Mattar & Daw obtain when need dominates a flat gain, does not arise in this afterstate variant, where need-only cannot
form a sequence at all.

**What this means for the M2a row.** The RQ1 bounds were written for gain × need. In this tabular variant it meets (a)
at the reward window, (d), and the ×4 increase, and fails the pre-run forward bound, the decline with familiarity in
block 1 (its rate climbs to the cap), and, read honestly against the baseline, the decrease bound. The plan's
acceptance is **not met**, and the result is informative rather than null: the Mattar & Daw phenomenon set that
survives here is "reverse sequences after reward, starting remote, more of them after a bigger reward"; what does not
survive is the forward pre-run replay and the signed response to a decrease, and the reason is structural (afterstate
gain chains backward; a scale change moves every gain). The thresholded mode's design (one θ per rule from a baseline
median, a washout reference) is the other half of the reason, and is the first thing to change.

## Step 4 of the remainder: each change against its baseline, θ in value units, the lap of origin

Preregistered in `docs/prereg/rq1_track_step4.md` before any run, with the θ values of its pilot recorded there;
decisions entry G30. No rule changed. Runner: `experiments/linear_track_rq1.py` (the default, step-4 version;
`--version step3` and `--version step2` reproduce the earlier protocols), 12 min on 4 cores; tables in
`docs/data/m2a/rq1_step4/`. Three changes from step 3, all three of G29 C: (1) **two sessions per seed** instead of
four blocks, *increase* (20 laps at east 1.0, then 20 at 4.0) and *decrease* (20 at 1.0, then 20 at 0.25), run from
the same seed so that their baseline blocks are the same 20 laps (verified by the tests) and each change is read
against the baseline block that precedes it, not against a washout block with a surprise of its own; (2) in the
thresholded mode a rule whose priority is in value units (a |TD error| or a gain) is compared with **θ × the mean
|V| over the states occupied so far**, read before each pause, with θ per rule set by step 3's pilot rule on the
normalised priority (uniform 0.131, reverse 2.26, prioritised 1.59, gain_need 6.13 × 10⁻⁶, gain_only 0.0102;
need_only's priority is an occupancy and keeps its raw θ 2.71, the same value as step 3's to the digit); (3) the
**share of a reward pause's backups that came from the lap just run** is a metric of `analysis.replay_metrics` and
sits beside every direction share below. The guard found 30 distinct lap-length vectors in every condition, mode
and session.

**Fixed-mode content** (20 backups per pause; events per pause and the shares among them; "after" pools the two
changed blocks, which differ little; `from_this_lap` is the share of the reward pauses' backups from the lap just
run):

| condition | events / reward pause, baseline → after | events / pre-run pause | reverse share | remote share (reward / pre-run) | from_this_lap |
|---|---|---|---|---|---|
| gain_need | 0.52 → 0.54 | 0.66 → 1.05 | 1.00 | 1.00 / 1.00 | 0.05 → 0.00 |
| gain_only | 0.75 → 1.16 | 0.78 → 1.42 | 1.00 | 0.24 → 0.57 / 0.49 → 0.72 | 0.71 → 0.70 |
| reverse_trajectory | 1.00 → 1.00 | 0.95 → 1.00 | 1.00 | 0.00 / 0.00 | 1.00 |
| uniform | 0 | 0 | undefined | undefined | 0.26 → 0.16 |
| prioritised_td | 0 | 0 | undefined | undefined | 0.20 → 0.09 |
| need_only | 0 | 0 | undefined | undefined | 0.05 → 0.00 |

The content is step 3's: gain × need makes reverse, remote sequences at both pauses, and after a change none of its
reward-pause backups come from the lap just run (they sweep the lap ahead, backward from its far goal); the
trajectory rule's are all from the lap just run; gain alone sits between (0.7).

**The preregistered verdicts** (`rq1_tests.csv`; thresholded rows are the east end's reward pauses, block 2 − block 1
of the named session, paired by seed; the prereg's prediction in brackets):

| test | gain_need | gain_only | reverse_trajectory | prioritised_td / uniform / need_only |
|---|---|---|---|---|
| (a) reverse share, reward pauses, baseline > 0.6 | 1.00 **passes** [pass] | 1.00 passes [pass] | 1.00 passes [pass] | undefined, no events |
| (a) forward share, pre-run pauses > 0.6 | 0.00 **fails** [fail] | 0.00 fails [fail] | 0.00 fails [fail] | undefined |
| (d) remote ≥ 10%, reward / pre-run | 1.00 / 1.00 passes [pass] | 0.49 / 0.67 passes [pass] | 0 fails [fail] | undefined |
| (b) increase: backups per stop | **+59.2** [+48.8, +66.5] (19.6 → 78.7), δ 0.96, passes [pass] | **−25.6** [−27.0, −24.4] (25.6 → 0.0), fails [fail] | −0.44 [−1.58, +0.10] (5.7 → 5.3), fails | prioritised +15.4 [+9.6, +22.4] passes; uniform −18.8 fails; need_only +17 [+7, +27] passes [fail] |
| (b) increase: events per stop | +2.80 [+2.31, +3.17] (0.44 → 3.24), passes | −1.07 [−1.17, −0.99], fails | +0.093 [+0.077, +0.107] passes (reverse events +0.100 passes) [pass] | 0, no events |
| (b) decrease: backups per stop, "down" | **+78.1** [+72.1, +82.0] (19.6 → 97.7), δ +1.00, **fails** [fail] | −25.3 [−26.6, −24.0] (25.6 → 0.3), passes [pass] | −4.11 [−5.16, −3.53] (5.7 → 1.6), passes [fail] | prioritised +24.1 fails [fail]; uniform −50.1 passes [fail]; need_only +17 fails [fail] |
| (b) decrease: events per stop, "down" | +3.50 [+3.16, +3.73] (0.44 → 3.94), **fails** | −1.07 [−1.17, −0.98], passes | −0.313 [−0.330, −0.303] passes (reverse events −0.307 passes) | 0, no events |
| (b) west control end, backups, TOST ±20% | +59.1 / +71.7, not equivalent [not equivalent] | −20.9 / −20.6, not equivalent | −5.56 / −5.56, not equivalent [equivalent] | prioritised +15.2 / +25.2; uniform −28.4 / −49.1; need_only +10 / +10: not equivalent |
| (c) baseline: slope of backups per stop vs lap | **+1.70** [+1.18, +2.22], **fails** [pass] | −5.25 [−5.36, −5.16] passes, 0 from lap 7.6 [pass] | −0.409 [−0.603, −0.279] passes, 0 from lap 17 [pass] | prioritised −6.73 passes, 0 from lap 11.2 [pass]; uniform −6.13 passes, 0 from lap 10.6 [pass]; need_only −0.21 [−1.13, +0.60] fails [fail] |
| (c) after each change (secondary) | +2.26 / +0.61, fails; 0 reached at 15 / 2 of 30 seeds | −0.007 / +0.011; 0 from the first changed lap | −0.101 / −0.117 passes, 0 from lap 22 | prioritised −5.9 / −4.7 passes; uniform −4.8 / −0.9 passes; need_only +0.85 fails |

Two sessions, two modes, seven conditions and thirty seeds ran as specified; no deviation to record. The cap of 100
binds for gain × need at the decrease (97.7 of 100 per stop) and nowhere else.

**Three readings.**

1. **The decrease, read cleanly, is unsigned for gain × need.** Against its own baseline the rule's thresholded rate
   *rises* after the ×0.25 decrease, by 78 backups and 3.5 events per stop, on every one of the 30 seeds (δ = 1.00),
   more than after the ×4 increase (+59 and +2.8). Step 3's "down" pass against the washout block was the magnitude
   artefact G29 C2 suspected, and the G29 C1 reading stands: gain is the size of the policy's move whatever the
   sign of the change. The sweeps that carry the rise are of the lap ahead backward from its far goal
   (`from_this_lap` 0.00), at both ends alike (+59 west after the east increase, +72 after the decrease): at a west
   pause the lap ahead *is* the east-bound lap whose reward changed, so for this rule the unchanged end is not a
   control, as the prereg said.
2. **Familiarity: the scaled θ gives the decline to every |TD error| rule and to gain alone, and not to gain × need.**
   Within the baseline block uniform, prioritised, reverse_trajectory and gain_only now fall to zero backups at every
   seed (first zero at laps 10.6, 11.2, 17 and 7.6), the (c) pass that step 3's raw θ could not show for three of
   them because its cap bound. gain × need's rate rises across the same block, +1.7 backups per lap, and after both
   changes (+2.3, +0.6): with θ in value units the gain term no longer carries the scale, so what remains is the
   need term, which *grows* with familiarity (the learned successor representation concentrates occupancy on the
   lap ahead as laps shorten) faster than gain shrinks. The failure of (c) is therefore not θ's scale, which change 2
   removed, but the need term's own course; a declining rate would need gain to vanish, as it does for gain alone.
3. **A change read against its own baseline is also read against time.** Block 2 is always the later block, and four
   rules' rates fall over laps (reading 2). Where a "down" verdict passes for a declining rule, the unchanged west
   end fell by as much: reverse_trajectory −4.1 east against −5.6 west, gain_only −25.3 against −20.6, uniform −50
   against −49. The preregistered test cannot separate the change from the trend; the within-session control can.
   **Exploratory, not preregistered:** the east change minus the west change, (east block 2 − block 1) − (west block
   2 − block 1), paired by seed, backups per stop: reverse_trajectory **+5.1** [+3.8, +6.7] at the increase and
   **+1.5** [+0.2, +3.0] at the decrease (δ 0.88, 0.70): relative to its own unchanged end the trajectory rule's rate
   rises after both changes, tracking |Δr| as G28 found; gain_only −4.7 [−6.1, −3.5] at both (a slightly larger fall
   at the changed end, whatever the sign); uniform +9.6 [+4.4, +15.1] at the increase, −1.0 [−4.6, +2.9] at the
   decrease; prioritised_td +0.3 and −1.1 (its priority is the largest |TD error| anywhere in memory, so the east
   change raises both ends equally); gain_need +0.1 [−12.6, +11.8] and +6.3 [−0.9, +13.6] (both ends rise equally,
   reading 1); need_only +7 [−5, +19] at both (its backups change no value, and its rate is identical in the two
   sessions). On this statistic no rule shows a signed response to the reward change; the only one with the sign of
   the change in it, gain_only's, has the wrong sign at the increase. Its "up" and "down" passes in the table are
   time.

**Gain does not respond to a magnitude change once the policy is decided.** gain_only's thresholded rate goes to 0.0
backups per stop after the ×4 increase and 0.3 after the decrease, and its total steps over the thresholded sessions
are identical in the two sessions (7,015): by lap 8 of the baseline its policy is deterministic along the lap, and a
scalar change of the reward moves no decision, so the expected improvement of any backup is near zero whatever the
new values. The rate-after-a-reward-change bound of RQ1 (b), written from Ambrose et al.'s finding, is a |TD error|
phenomenon in this family: the floors and need × gain (through need) show it, gain alone cannot, and gain × need
shows it unsigned.

**Learning speed per session** (`rq1_learning.csv`; total steps over the 40 laps, fixed mode; the two sessions share
their first 20 laps): none 14,488; uniform 14,204 (−283 [−714, +48] against none, faster on 13 of 30, δ −0.08: the
null of the 40-lap evaluation again, G28); reverse_trajectory 9,884 (−4,604 [−5,348, −3,905], every seed);
prioritised_td 9,161 (increase) / 8,807 (decrease); gain_need 7,866 in both, faster than prioritised by 1,295
[916, 1,670] on 27 of 30 seeds (δ −0.68 [−0.84, −0.42]) in the increase session and by 941 [594, 1,301] on 24 of 30
in the decrease session; gain_only 7,940 / 7,946, faster than prioritised on 28 and 26 of 30; need_only 14,488,
identical to none on every seed. The prereg's learning prediction holds. Thresholded: prioritised_td is fastest
(7,186 / 6,824) with gain_only level with it (−171 [−561, +260]; +192 [−202, +586]), gain_need slower by 1,501 [959,
2,080] and 1,590 [1,074, 2,153], reverse 12,296, uniform 13,470 / 13,623.

**Predictions against outcomes.** Held: gain × need's (a), (d), (b) increase, (b) decrease (unsigned), west end;
gain_only's (a), (d), fall at the increase, fall at the decrease, (c); the floors' content and (c) under the scaled
θ; the learning ordering; the identical baselines. Failed: gain × need's (c) in the baseline block (predicted to
pass, rose); reverse_trajectory's decrease (predicted to rise against the baseline, fell with time, and rose only
against the west end); need_only's "up" at the increase (predicted to fail; passes on a time trend shared with the
west end). The step's question has an answer: of the two step-3 failures, the decrease was the confound (and the
clean reading is still a fail, for the structural reason), the familiarity decline was not.

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
- Seven rules of nine after steps 3 and 4 (the goal-uncertainty need variant and Diekmann–Cheng remain); both budget
  modes, the reward schedule, the pre-run window, the plan's event definition and remote flag are in place since
  steps 1 and 2, and RQ1 (a)–(d) have been run (steps 3 and 4: the acceptance is not met, for the structural reasons
  given there). Under step 4's scaled θ the thresholded cap binds only for gain × need after the decrease (97.7 of
  100 backups per stop); under step 3's raw θ it bound for gain × need, prioritised and uniform through most of the
  protocol.
- Step 4's two sessions read each change against the baseline that precedes it, but block 2 is always the later
  block and four rules' rates fall over laps, so a "down" verdict can be the trend; the unchanged west end is the
  within-session control, and the east change minus the west change is reported as exploratory, not preregistered.
  The two sessions are not independent samples of the baseline (same seed, same 20 laps), so the baseline block is
  counted once in every pooled statistic.
- The replay rules run outside the engine, on the track's own loop, with the engine's learner, sampler, RNG and
  event record; wiring them into the engine's tick and the console's arena is M3's.
- Direction is read on the plan's sequences against the lap the replayed states belong to (step 1 and step 3); the
  label cannot tell a sweep of the lap just run from a sweep of the lap ahead, which `from_this_lap_share` does
  (reported beside every direction share since step 4).
- One learning rate, discount, temperature, prior and gain; no sweep. The ranking's robustness to them is untested.
- Linux only (the development box: Python 3.11.15, numpy 2.4.6, OpenBLAS 0.3.31 on the SkylakeX kernel, one thread,
  detected and verified by `threadpoolctl`); no BLAS product is used, and the tables are byte-identical across
  worker counts, but a second-machine reproduction has not been made.
