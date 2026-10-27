# Milestone 3: replay over the place code (the plan's row 3)

**Status:** started 2026-10-27, at the owner's request ("focus on M3, and look for opportunities to close the gap on
the areas the other two projects are stronger"). This document is M3's map: what the row demands, what the earlier
milestones hand it, how the work is split into preregistered steps, and where each step closes a gap against the two
tools the research-tool review compared the project with (RatInABox; Mattar & Daw's replay model; standard RL
frameworks). Each step has its own preregistration under `docs/prereg/` and its own decisions entry; this map is
amended by dated notes, never rewritten.

## What the row demands

`docs/research_plan.md` row 3: the replay rules of §2 run over the place population, with **need from an SR row**,
**gain from a softmax place-to-neighbour policy** and **a Dyna model as an empirical place-to-place table** (no
heading factor); **trial structure as an engine concept** (start-pose lists; trial, probe, inter-trial and rest
phases shared by the console and the headless runner); **every rule run with oracle state and with the embodied
estimate**. Acceptance: RQ1 re-run over the place population with §3's ablation expectations, and the
tabular-versus-embodied and oracle-versus-embodied differences reported with paired intervals. Tag `v1.5-place-replay`.

## What earlier milestones hand it

- **From M2a (G32 C2).** The tabular Q learner with the forward n-step extension (the fastest learner of the series,
  the only source of forward pre-run replay); need over positions (the only source of reverse replay of the lap
  just run); the east-minus-west difference as the reward-change statistic; the lap-of-origin share beside every
  direction. Do not carry the per-rule θ pilot as it stands (G32 C3); positional need and the extension are not
  additive (G32 C4).
- **From M2b (G33–G37).** The research profile's instrument: heading oracle, wall-contact reset, the 400-cell place
  population, SR value steering. The gate passed on it (G36). Its limits: one goal, known starts, a declared heading.
- **From the console work (G40–G43).** The circling instrument (decision log, orbit summaries, matched-seed
  ablations) runs on every M3 protocol (G42 C2). M3's protocols are of the gate's kind: tasks the agent's default
  loop does not solve. Fresh seeds: hidden food from 17, the gate from 61 (G42 C3). The unlearning rate is a
  stability–plasticity tradeoff the instrument does not settle (G42).

## The body is on M3's critical path

RQ1's protocol is a linear track: laps between two rewarded ends, a reward-consumption pause at each, a pre-run
window defined by running speed (§2's metric table). A probe on 2026-10-27 (the research profile, a 2 m × 0.1 m
track, four seeds × 3,000 ticks; exploratory, not committed) found the agent does complete laps under its own policy,
contrary to G35 C2's assumption, but not by running: 74% of ticks are TURNs, 81% are spent against a wall, 39% move
the body not at all, and a lap takes a median 97 ticks against 18 for a straight run. The pre-run window and the
pause structure RQ1 reads cannot be defined on that walk. M2b sidestepped it by placing the body (G35's forced laps);
M3 cannot, because replay's effect on behaviour is part of what it measures.

The cause is the body, not the brain: a TURN moves the body 0.3 units while it rotates 0.3 rad (a turning circle
1 unit in radius), and nothing aligns the body with a wall it runs into, so the centre vision ray keeps finding a
side wall and wall avoidance keeps turning. **This is exactly where RatInABox is stronger**: its agent's speed and
rotational velocity are smooth stochastic processes fitted to rat data (Sargolini et al. 2006), a control signal
drifts the velocity, and near a wall the velocity is turned to run along it (George et al. 2024). Step 1 brings
those properties in as an opt-in body.

## Steps

| step | what | gap it closes | status |
|---|---|---|---|
| 1 | **A rodent-like body** (`body.model = "rodent"`, opt-in): speed and angular velocity as Ornstein–Uhlenbeck processes drifted by the chosen action, turns in place, wall-following alignment; characterised on the track and in the open field against the discrete body, and the RQ4(a) gate re-run under it on fresh seeds | RatInABox: movement (the body runs a corridor) | preregistered: `docs/prereg/m3_body.md` |
| 2 | **Trial structure as an engine concept** and the **embodied track protocol** (Ambrose et al. 2016): start poses, trial / probe / inter-trial / rest phases, reward ends with a consumption pause, reward blocks, lap counter; shared by console and runner; the agent runs its own laps | (the row's own deliverable) | planned |
| 3 | **Replay as an in-engine event stream over the place code**: the transition memory over place-cell states, the Dyna model as an empirical place-to-place table, need from the SR row, gain from a softmax place-to-neighbour policy, a learned action value over place features that both replay and experience update and that the steering reads; the floors (none, uniform, reverse) first | RL frameworks: learning (the agent's movement values are learned, and replay changes them) | planned |
| 4 | **RQ1's positive control** (oracle state) **and the embodied run**, each rule as G32 carries it; preregistered, then confirmatory on fresh seeds | Mattar & Daw: the reference theory, now with an embodied state estimate | planned |
| A | **Feature populations as one interface**, with head-direction cells (Taube et al. 1990) and boundary-vector cells (Hartley et al. 2000) beside the place cells; console panels | RatInABox: cell types | candidate, after step 3 |
| B | **A Gymnasium adapter** for the research tasks (the gate first), so a standard RL agent can run the same task as a reference | RL frameworks: ecosystem and baselines | candidate, any time |

Steps 1–4 are the row; A and B are gap-closers that do not block it. Every step runs on its own branch stacked on the
last, preregistered before its run, merged on the owner's say-so, as in M2a and M2b.

## Decisions the owner holds

1. **Whether the rodent body becomes the research profile's default** (after step 1's result; it moves the research
   baselines once, as the plan allows per milestone).
2. **The learner M3's replay updates** (step 3): the plan's linear value over place features read by the SR's need,
   or the action value G32 recommends carrying. Step 3's preregistration will put a recommendation.
3. **Whether A and B are taken up in M3 or after it.**

## Step 1: a rodent-like body (G44; `docs/prereg/m3_body.md`; data `docs/data/m3/body/`)

**The registered result: T1 fails for every body; the gate holds under both rodent bodies.** Seeds 1–30, 3,000 ticks,
research profile (Amendment 1 redefined the stall share before the run, and disclosed a four-seed smoke):

| body | ticks per lap (bound 36) | stall share (bound 5%) | FORWARD | wall contact | track estimate error |
|---|---|---|---|---|---|
| discrete | 101.6 [96.9, 106.9] | 6.1% | 24% | 82% | 0.11 |
| rodent_quiet | 112.9 [105.9, 121.1] | 8.9% | 27% | 78% | 0.00 |
| rodent | 150.6 [136.8, 169.2] | 3.5% | 25% | 41% | 0.22 |

In the open field (2 m × 2 m): mean speed 0.25 / 0.25 / 0.32 m/s; angular velocity sd 1.08 / 0.94 / 2.26 rad/s;
within 0.1 m of a wall 60% / 53% / 29% of ticks; coverage 59% / 64% / 99%; orbit share 33% / 40% / 17%; late
estimate error 0.70 / 0.26 / 0.41 units (discrete / rodent_quiet / rodent).

The gate (seeds 61–90, the confirmatory settings): SR hidden ÷ visible **0.998 [0.992, 1.0] under both rodent
bodies** (hidden 99.8%, visible 100%), arrival error 0.18 and 0.17 units; median latency 33 ticks (rodent) and 17
(rodent_quiet). **The control moved**: with no value steering the agent finds the hidden goal on 66.5% of trials under
the noisy body (9.3% under the quiet body, 5% under the discrete one), because the noise makes it cover the arena (99%
coverage): under RatInABox's noise the gate no longer separates a navigating agent from a wandering one.

Predictions: T1 for both rodent bodies failed (the smoke had shown it); T2 held; G1 held, and the noisy body was the
slower, as predicted; in the open field the rodent bodies spent *less* time near walls, not more (predicted more), the
noisy body stalled less and orbited less (predicted), the quiet body orbited more (turning in place counts as a loop).

**Why the body was not the fix (exploratory, seeds 101–104, disclosed; not preregistered).** The decision log named the
cause. With the quiet body every chosen turn on the track happens within 0.2 m of an end: the agent spends about 70% of
its time trying to turn round. A wall dead ahead scores the left and right turns almost equally, so at the softmax
temperature the choice flips tick to tick and the heading random-walks instead of completing the U-turn; and the wall
signal counts a wall as ahead out to the vision range (1.2 m), so in a 0.1 m corridor a heading more than about 5° off
the axis already reads as a wall ahead. A probe of the two brain-side changes, the wall signal limited to 0.2 m and a
**turn commitment** (the turn in progress gets +0.3 while a wall is ahead):

| body | wall range | commitment | ticks per lap | stalls | FORWARD |
|---|---|---|---|---|---|
| discrete | 1.2 m | 0 | 96.6 | 6.1% | 24% |
| discrete | 0.2 m | 0.3 | 33.2 | 0.2% | 51% |
| rodent_quiet | 0.2 m | 0.3 | 38.8 | 0.4% | 55% |
| rodent | 0.2 m | 0.3 | 62.5 | 1.4% | 42% |

Either change alone does little (commitment with the long range makes it worse: walls are always "ahead"). Together
they make the discrete body run the corridor. RatInABox's heading noise (about 0.4 rad per tick at this tick length)
is too much for a 0.1 m corridor whatever the brain does. Step 1b preregisters the two changes on fresh seeds.

## Step 1b: the corridor options (G45; `docs/prereg/m3_corridor.md`; data `docs/data/m3/corridor/`)

A wall range of 0.2 m (`basal_ganglia.wall_avoid_range` 1/6) and a turn commitment of 0.3, on fresh seeds 31–60
(track, open field) and 91–120 (gate). Amendment 1 (before any result was read): the first attempt crashed on a
contract mismatch (a one-tick turn of exactly π, reachable only through a fault in the body's wall following at a
corner, disclosed there); the contract was aligned and the run repeated; the gate tables of both attempts are
byte-identical.

| condition | ticks per lap (bound 36) | stalls | FORWARD | near a wall, open field | coverage | orbit share |
|---|---|---|---|---|---|---|
| discrete | 105.3 | 6.0% | 23% | 59% | 59% | 31% |
| **discrete_corridor** | **33.3 [32.9, 33.8]: T1 passes** | 0.2% | 51% | 75% | 48% | 9% |
| rodent_quiet_corridor | 38.3 [38.1, 38.6]: T1′ fails | 0.4% | 55% | 58% | 64% | 52% |
| rodent_corridor | 62.4 | 1.4% | 43% | 44% | 99% | 17% |

**The gate, with the options** (SR source; trials 21–40):

| body | hidden | visible | hidden ÷ visible | no steering, hidden | tabular, hidden |
|---|---|---|---|---|---|
| discrete | 98.2% | **11.8%** | 8.3 | 9.8% | 23.5% |
| rodent_quiet | 100% | **26.2%** | 3.8 | 15.7% | 88.7% |

**G1 passes by the letter and fails in substance.** Its ratio divides by the visible success, which collapsed (100% at
the registered gate). Under the options the agent learns the hidden goal (16% → 98% over the session) but never
improves on a visible one (7% → 13%), and only 14 of 242 guided misses reach the goal once it is shown (50 of 62 at
the registered gate). A visible target mutes memory steering (the cue gate), so the visible approach rests on vision
drive alone, and with the options vision drive no longer brings the agent in; in the open field it spends 75% of
ticks within 0.1 m of a wall. Predictions: T1 held (33.3, predicted about 33); T1′ failed narrowly (predicted narrowly
either way); `rodent_corridor` about 60 (held); G1 "above 95% hidden" held and the control stayed below 20% (held), but
the prediction did not anticipate the visible collapse; the wall-zone share rose and orbits fell for the discrete body
(held), not for the quiet rodent body.

**Reading: the decision table's second row**: the options run corridors but cost navigation, so the cause is diagnosed
before step 2.

## Note, 2026-10-27: the owner's route for step 2, and the audit before it (G46)

**The route (G45 C2): (b), one wall response for every task**, chosen so that behaviour is emergent rather than set per
task. Its preregistration carries four rules: one configuration for every task (nothing knows which task it is in);
reflex settings fixed before the run from outside the results; every task passes together (the track, the visible
goal, the hidden goal, the open field), so a fix cannot buy laps with navigation as step 1b's options did; and a
no-learning control in every task, a behaviour counting as emergent only by its margin over it. On the track that is
laps with reward against laps without: step 1b's options ran a lap every 33 ticks on a track with no reward at all, a
reflex shuttle, which is why the track-only setting was not taken.

**The audit first, at the owner's request** (G46; `docs/prereg/g46_retest.md`; `docs/data/g46/`). Nothing hidden is
sensed on the research profile any more (the rays had seen hidden food as obstacles); the hidden-food memory benefit
was the leak's and is withdrawn; the gate's 99.8% needs its start anchor (37.7% told nothing, 6.2% with no aid at all,
3.5% without value steering). **From here every M3 result is reported with and without the anchor.** The owner's next
step is obstacles in the arena, then a retest; the world has no solid object yet, so that is new physics before it is
a new task.

**Obstacles, part 1 (G47, 2026-10-27).** Solid barriers exist now (`core.world.Barrier`: they stop the body and every
ray, are seen as walls, and are not reported by touch). With an L-shaped wall between two starts and the goal, the
SR's memory gets round it on 82% of trials from the walled-off starts (3% without value steering; 41% told nothing of
the start), by following the wall (seven times the open arena's latency). Part 2, the agent learning to locate itself
from what it sees, is next.

**Obstacles, part 2 (G48, 2026-10-27).** Four distal cues the agent sees (names, bearings, distances) and maps itself
give back what the start anchor gave in the open arena (95% told nothing, 100% told the start, 29% without cues).
G47's way round the wall leaned on a slide the agent could not feel; with sideways odometry it gets round on 33%, and
its value steering, which reads places across walls, pulls it into the wall even when the goal is visible. Steering
that respects walls is the next candidate; sideways odometry belongs to any protocol with barriers.

**Step 2, Part 1 (G49, 2026-10-27).** Reachable value probes (each direction read only as far as the agent sees it
could go) take the agent round the L arena's wall from every walled-off start (100% against 35%), in twice an open
run's time, and change nothing else. Part 2 (one wall response for every task; the track with alternating reward,
strict: the reflex alone must not run laps) is the design in `docs/prereg/m3_step2.md`.
