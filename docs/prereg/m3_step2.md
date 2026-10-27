# Preregistration: M3 step 2, one action selection for every task

> **STATUS: Part 1 REGISTERED 2026-10-27, at the owner's instruction ("Register and run"), after the draft was put to
> the owner; nothing has run on its seeds (the commit that changes this line is the registration). Part 2 remains a
> design; the owner's decisions on it are recorded at the end.**

**Scope.** The owner's route for step 2 (G45 C2 (b), G46 E1): one action selection for every task, under the four
rules: one configuration for every task (nothing knows which task it is in); reflex settings fixed before the run
from outside the results; every task passes together; a no-learning control in every task, a behaviour counting as
emergent only by its margin over it. Folded in at the owner's request: steering that respects walls (G48 D2).

An exploration on spent seeds, run to ground this draft (disclosed below), split the work in two. **Part 1**, steering
that respects walls, is ready: one mechanism, a large effect in the pilot, no cost elsewhere. **Part 2**, the wall
response and the track, is not: what the exploration found there is a design problem, and this draft proposes how to
work it rather than a test.

## What the exploration found (disclosed; `tools/m3_step2_probes/`; gate seeds 31–42, track 31–38, hidden food 1–8)

All on the research profile with sideways odometry (G48) and the sensing of G46.

**1. Reading value through walls was the whole problem in the walled arena.** The value steering reads the learned
value one unit away along a fan of directions (ahead, ±0.3, ±0.8, ±1.4 rad), wherever that point is. Reading each
direction only as far as the agent can see it could go (**reachable probes**, below):

| SR, success over trials 21–40 | probes as now | reachable probes |
|---|---|---|
| L arena, told the start, hidden (blocked / direct starts) | 0.24 / 0.48 | **1.00 / 1.00** |
| L arena, told the start, visible | 0.35 | **1.00** |
| L arena, told nothing, with cues, hidden | 0.71 | **0.96** |
| open arena, told the start, hidden and visible | 1.00 | 1.00 |
| open arena, told nothing, with cues, hidden | 0.94 | 0.98 |
| no value steering, every arena | ≤ 0.03 | unchanged |

From the walled-off starts every one of 120 trials arrives, in a median 40.5 ticks (20 in the open arena; G47's
wall-following took 112–140): a way round close to direct. Hidden food is unchanged (memory steering 41.8 against 42.3
finds; still below no steering's 51.9, G46's separate problem).

**2. The open arena's visible approach rested on the long-range wall signal, by accident.** G45's corridor options
broke it. Separated (open arena, told the start, SR):

| options | visible success | target in view | ticks within 1 unit of a wall |
|---|---|---|---|
| none | 1.00 | 57% | 0% |
| turn commitment 0.3 only | 1.00 | 60% | 0% |
| wall range 1/6 only | **0.01** | **2%** | **83%** |
| both | 0.03 | 4% | 71% |

The approach to a seen target is weak: a target off to the side adds to a turn only 0.6 × its closeness (about 0.2 at
8 units) against FORWARD's bias of 0.8, so the agent drives on. With the long-range wall signal every wall in view
adds turning drive, the agent keeps turning in open space, and the target's pull tips the choice. With the short range
the agent runs straight to a wall, follows it, and with a 1.2-rad field of view never faces the goal again.

**3. A rat's field of view (300°, 11 rays) rescues the visible approach in the open, but not with the short range.**
Wide vision alone: both gates 1.00 (no steering's visible 1.00 too: the visible session becomes the reflex alone);
the track 69 ticks a traversal (101 now; the bound is 36). Wide vision with the short range: the track 32, but visible
0.12–0.16, because a seen target still cannot beat the forward bias.

**4. Lap running is not learned.** The 2 m × 0.1 m track with food alternating between its ends (eaten at one end,
it appears at the other):

| | ticks per traversal, with reward, SR | with reward, no steering | without reward |
|---|---|---|---|
| the wall response now | 89 | 102 | 102 |
| G45's options | 57 | 34 | 34 |

With the current wall response the agent crawls whatever it learns; with G45's options it shuttles at 34 ticks with or
without reward (a reflex lap runner, which the four rules exclude), and memory steering makes it worse by pulling it
back to the end it just emptied (G40–G43's stale reward).

## Part 1: reachable value probes (ready to register)

**The mechanism** (`value_memory.reachable_probes`, `sensors.free_space_sensing`; built, opt-in, tested). The agent
senses how far it could move in each direction of its value fan, the distance to the nearest solid (arena wall or
barrier) along each, from its own position, exact as its wall rangefinder is (`Observation.free_space`). Each probe
point is pulled back to just short (0.05 units) of what it sees; a probe against a wall reads the place it is in.
Nothing is told about walls, goals or tasks: it is the value of places the agent could step to, read from what it
sees. Task-blind; inert where no solid is within one unit of a direction; inert without a value source.

**The configuration** (every condition): the research profile + sideways odometry (G48) + reachable probes, against the
same without reachable probes. Nothing else changes.

**The battery, fresh seeds 215–244 (30), every task, paired** (`python3 -m experiments.m3_reachable --workers 28`,
`docs/data/m3/reachable/`; the gate as G48 ran it: per-feature rule, one rate, 40 trials read 21–40, trials started
still; told nothing means `carry` with G48's cues; hidden food and the reflex measures 3,000 ticks):

| task | conditions | read |
|---|---|---|
| the gate, open arena | told the start; told nothing with cues | SR, tabular and no steering, hidden and visible |
| the gate, L arena | the same | the same, by start group |
| hidden food (research, the scenario's U = 4) | memory steering, no steering | finds |
| the track without reward | the reflex alone | ticks per traversal, the stall share |
| the open field (G44's measures) | the reflex alone | wall-zone share, coverage, orbit share |

**Predictions** (from the exploration):

- **R1 (primary).** L arena, told the start, SR hidden from the blocked starts: reachable probes ≥ 0.90, and their
  effect's interval's lower end above 0.4.
- **R2.** The median latency from the blocked starts with reachable probes at most 2.5 times the open arena's.
- **R3.** L arena told the start, SR visible ≥ 0.90; told nothing with cues, SR hidden ≥ 0.85.
- **R4 (no cost).** Open arena, every source and session: within ±0.03 of without. Hidden food: within ±3 finds.
  The track and the open field: unchanged (the reflex alone does not read value).
- **R5 (controls).** No steering ≤ 0.05 hidden in every condition, unchanged by the probes.

**Reading rules.** R1–R5 hold: reachable probes join the research profile (with sideways odometry and the free-space
sense; the owner's call, the research baselines regenerate once), and the record says the agent's learned memory takes
it round a wall nearly directly, with no steering at the floor: under the four rules, an emergent detour. R4 fails:
the probes cost something elsewhere; diagnose before adopting. A shortcut test (the wall removed after learning) is the
natural follow-up.

## Part 2: the wall response and the track (a design to work, not yet a test)

What has to be true at once (the four rules' "every task passes together"), as **bounds the eventual preregistration
would carry**:

| task | bound |
|---|---|
| the track, food alternating | with reward and memory steering, at most 36 ticks a traversal |
| the track, the reflex alone | without reward, and with reward but no steering: at least twice that (the agent does not shuttle by reflex) |
| the gate, open and L, told the start | SR hidden ≥ 0.95 / ≥ 0.90; visible ≥ 0.90 |
| the gate, told nothing with cues | SR hidden ≥ 0.85 |
| hidden food | memory steering not below G46's 41.2 finds by more than 10% |
| controls | no steering ≤ 0.05 hidden |
| the open field | reported: wall-zone share, coverage, orbit share |

No configuration explored passes them. The exploration says three things must change, and proposes one candidate for
each, each set from a stated reason before any pilot:

1. **An orienting response to a seen target** (to build): a target seen off-axis turns the agent toward it with a
   drive that outweighs the forward bias (as a rat orients to a seen reward), so the visible approach stops resting on
   wall turning. *Reason*: finding 2.
2. **A rat's field of view** (`sensors.fov` 300°, 11 rays; exists): finding 3. It makes the visible session a pure
   reflex test (no steering reaches a visible goal too), which is what that session is for.
3. **Forgetting a reward that has been eaten** on the track: the scenario's own U = 4 (G43's setting for renewable
   reward) or a reward-consumed signal; *reason*: finding 4's pull back to the emptied end.

With these, the wall range is left as the one free choice (long, as now, or G45's 1/6 with commitment 0.3).

**Plan.** (a) Build the orienting response. (b) A pilot on spent seeds over the whole battery, for the candidates'
combinations with each wall range (at most 8 configurations), **choosing by a rule written before it runs**: the
configuration passing the most bounds; ties to the fewest changes from the research profile; none passing the track's
reflex bound is chosen (a reflex lap runner is not a result). (c) The chosen configuration preregistered and run on
fresh seeds. If none passes, the record says so, and RQ1's track uses forced laps (G35's protocol) with the gap
recorded, as step 1's decision table already allows.

## The owner's decisions (2026-10-27)

1. **Part 1: registered and run** (above).
2. **Part 2's track bound is the strict one**: the reflex alone must not run laps; laps must come from reward and
   memory. If no candidate passes, RQ1's track uses forced laps with the gap recorded.
3. **A 300° field of view counts as sensing** (a rat's), knowing it turns the visible session into the reflex alone.
