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
