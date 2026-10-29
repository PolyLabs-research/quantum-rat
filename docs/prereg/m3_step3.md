# Preregistration draft: M3 step 3, a learned action value over the place code, with replay

**Written:** 2026-10-29, after G54 and before any build or run. A draft for the owner, as `docs/prereg/m3_step2.md`
was: the mechanism is built opt-in, piloted on spent seeds against the bounds below, and the owner registers the
confirmatory run (the commit that adds its registration note is the registration; the pilot's decisions entry will
be G55). **Why now:** G53 C4. Every mechanism since G44 (the orienting response, the wall responses, the reachable
probes, history, motivation, the step cap) changes how the value of *places* is read or how much the body moves; none
changes which *action* the agent prefers from a state on the strength of experience. The strict track bound asks
memory with reward to double the reflex's laps; on the research body memory multiplies them by 1.2 (35 against 30
traversals, G54) because its long-range wall response zigzags in a corridor four cells wide, and steering by the value
of places can only bias those turns. A learned preference for FORWARD along the corridor is what can suppress them.

## What the plan's row 3 demands (`docs/research_plan.md` §4 row 3; `docs/m3_place_replay.md` step 3)

Replay as an in-engine event stream over the place code: a transition memory over place-cell states, a Dyna model as
an empirical place-to-place table, need from an SR row, gain from a softmax place-to-neighbour policy, **a learned
action value over place features that both replay and experience update and that the steering reads**; the floors
(none, uniform, reverse) first. What M2a hands over (G32 C2): the tabular Q learner with the forward n-step extension
was the fastest learner of the series and the only source of forward pre-run replay; need over positions the only
source of reverse replay of the lap just run.

## The design (all opt-in; both determinism baselines must stay bit-identical)

1. **The learner** (`brain/systems/action_value.py`, `LinearQ`): Q(φ, a) = w_a · φ over the place population's rates
   at the agent's estimate, normalised to sum 1 (the φ the SR learns on), for the three movement actions FORWARD,
   TURN_LEFT and TURN_RIGHT. REST keeps its reflex score: resting has no spatial consequence to learn. Experience:
   every tick's transition (φ_t, a_t, r_t+1, φ_t+1) with Q-learning's target r + γ max_a Q(φ_t+1, a) and replacing
   eligibility traces per action (e_a ← max(γλ e_a, φ) for the action taken, γλ e_a for the others; w_a += α δ e_a),
   so that a reward's credit reaches back along the run that earned it. r is the map reward (the contact bonus;
   shaping only under `value_memory.learn_shaping`). `action_value.learning_rate` 0.1, `discount` 0.98 (γ³⁶ ≈ 0.5: a
   full-speed traversal of the track, 36 ticks, lies within the horizon), `lam` 0.9 (credit reaches back about a
   traversal), traces replacing; each set from the stated reason before any run. Traces clear at an episode boundary.
2. **The read** (`value_memory.source = "action"`): the memory term of each movement channel is `value_gain` × the
   advantage Q(φ, a) − mean_a Q(φ, ·), passed through the same split as the place-value probes
   (`split_value_signals`: dead zone, ramp, one turn at a time), so only a clear preference commands a turn; cue and
   wall gating unchanged. No probes: the action value is read at the agent's own place.
3. **The transition memory** (`TransitionMemory`, `replay.memory_capacity` 3,000, one run): every tick's transition
   with its action (`StoredTransition.action`, new; the M2a rules read the action off the geometry and leave it
   empty), episode = the engine's, index = the tick, cell = the place cell with the largest rate at the start. That
   table of cell-to-cell transitions is the Dyna model.
4. **Replay at the reward-consumption pause.** When the agent eats, the body rests for `replay.consume_ticks` (5, one
   second: the rat stops to eat), and on the pause's first tick the rule backs up `replay.backups_per_pause` (20,
   M2a's fixed budget) stored transitions into the learner, recorded as one `ReplayEvent` (trigger `reward`, the
   rule's name, the cells, the direction by the sign of the position–time slope along x, as M2a read it) in
   `engine.replay_log`: the console draws it, the headless runner writes it. Rules (`replay.rule`): `none`;
   `uniform` (drawn from the `replay` RNG stream, a named stream added for it); `reverse` (the current episode's
   transitions, most recent first); `gain_need` (Mattar & Daw's EVB on the Q learner with the forward n-step
   extension, `MattarDawReplay` as M2a step 5 built it, over a `PlaceQModel`: state = the largest-rate cell, need from
   the SR row ψ(φ_acting), gain from the softmax over the channel scores read on Q). The floors first; `gain_need`
   is built behind the same interface and piloted only if a floor passes the track. The legacy microsleep replay is
   off on the research profile and untouched.
5. **Oracle state** (`action_value.oracle_state`, opt-in): φ read at the true position instead of the estimate, the
   positive control the row names for step 4; reported in the pilot on the track, not scored.
6. **Readouts.** The decision log's memory term is the Q read; the research frames carry the three advantages and the
   learner's weight norm; the replay events are JSONL beside them; the console lists "Action value" and the replay
   rule among the mechanisms in force.

## Bounds (M3 step 2's battery under G53's statistics, `docs/prereg/m3_step2.md` as amended on 2026-10-28)

The base is the research profile as G54 left it (history with the fixed schema on) with the step cap; the learner's
configurations add `action_value.enabled`, `value_memory.source = "action"` and the replay rule. The eleven bounds:
the track, the learned arm at least 42 traversals in 3,000 ticks and each reflex arm (no reward; reward without
steering, `value_gain` 0 with the learner still learning) at most half of it; the gate, open and L hidden ≥ 0.95 /
0.90, visible ≥ 0.90, cues ≥ 0.85; hidden food ≥ 37.1 (the registered floor, 0.9 × G46's 41.2; reported against
the adopted profile's 46.3 as well); the no-steering control's margin ≥ 0.5. **The acceptance is the track**: laps
from reward and memory with the reflex alone running at most half of them, on the research body. The corridor body
(Part 2's `o1_n_S`) is reported on the track only.

**Selection rule, written before the pilot:** among the learner's configurations, the one passing the most bounds;
ties to the simplest rule (`none`, then `reverse`, then `uniform`). No configuration is chosen that fails the track.

## Pilot (exploratory, spent seeds: gate and track 31–42, hidden food 1–8; `experiments/m3_step3.py --phase pilot`)

Configurations on the research body: the profile as adopted (reference); the learner with replay `none`; with
`uniform`; with `reverse`. The oracle-state arm of the learner with `reverse` on the track, reported.

## Predictions (written before any run)

- **Replay `none`**: the track's learned arm rises above the reference's 35 traversals (the Q read prefers FORWARD
  along the corridor once a lap has paid) but 42 is uncertain, and with the reflex arms near 23 the half-bound is
  tight: predicted to fail narrowly without replay.
- **`reverse`** is the strongest: predicted learned ≥ 45 and both reflex bounds passed; `uniform` between the two.
- **The gate**: unchanged or better (the Q read needs no probes across walls); **hidden food** is the uncertain one:
  an action value learned at a renewable site can orbit it (G40's failure), so predicted at the floor, 37–46, with
  history's two-second discount holding it up.
- **The controls** ≤ 0.05 (no steering reads nothing); the margin ≥ 0.9.

## Decision table (pilot)

| result | reading | what follows |
|---|---|---|
| the track passes for some rule and nothing else is lost | the action value is the memory the row demands | the owner registers the confirmatory run on fresh seeds (gate and track 275+, hidden food 77+); then step 4, RQ1 over the place code |
| the track passes but hidden food or the gate falls | the action value trades tasks | the owner's call: a per-task reading or a learner change, recorded before any further run |
| nothing passes the track | an action value over place features cannot make the research body lap | forced laps per the Part 2 draft (G35's protocol) with the gap recorded; the learner stays for RQ1 under them |

## What would change this document

Nothing after the pilot's rule has chosen. A pre-run amendment (a parameter that must change for the build to run at
all) is recorded here with its date and reason before the pilot, as M2a's preregistrations did.

## Amendment A1 (2026-10-29, after the first pilot, before the second; the draft being the owner's to register)

**What the first pilot found** (`docs/data/m3/step3/pilot/`, G55 A): no learner configuration passed the track, and
the rule chose none. The action value solved the gate as well as the SR (hidden 0.996 / 1.000 told the start, 0.962 /
0.929 with cues) but on the track it ran fewer laps than the research profile (28.3 against 34.0 without replay) and
fewer still with replay (16.5 with reverse, 14.5 with the oracle state), and hidden food halved (24–28 against 46.5).
A check (`tools/m3_step3_probes/emptied_end.py`) showed why: with reverse replay the agent spends 65% of the run
within 1.5 units of the end it has just emptied (the profile 43%, with three times the meals), and the advantages it
steers on eight ticks after a meal are ±0.01 to ±0.05, which the split's relative dead zone turns into full turns.
Two causes, both in this design and neither in the learner's arithmetic:

1. **The state was position-only.** Q(φ, a) cannot tell the end just emptied from the full one, which is what G52's
   reading named as the first missing variable and what G54's fixed schema gives the SR's reward weights; the action
   value never read it. Reverse replay then backs the reward up along the lap just run, toward the empty end.
2. **The read had no floor.** The advantages were normalised by their own scale, so a noise-sized preference
   commanded a full turn; the split's relative dead zone was made for a spatial value relief read along probes.

**The amendment.** (a) `action_value.history_features`: the features are φ and, for each of the taste channel's
timescales (2 s, 20 s, 200 s), φ times that trace at each cell: this place, eaten at this recently. The state carries
its history, as a splitter cell's does; a transition is stored with the features it was experienced on
(`PlaceTransition`), so a replay backs it up as it was. (b) `action_value.read_floor` 0.02: the largest advantage
magnitude below which the steering reads nothing (a preference worth less than a fiftieth of a reward is noise). The
first pilot's configurations pin the floor at 0 so their tables regenerate as run. Nothing else changes.

**Pilot 2** (`--phase pilot2`, the same spent seeds and bounds): the profile; `q_floor` (the floor alone, position-only
features); `qh_none`, `qh_uniform`, `qh_reverse` (both amendments, replay by that rule). The selection rule unchanged.

**Predictions (before pilot 2):** the floor alone brings the learner back to the profile's laps (30–34) and part of
the way on hidden food (35–42: the noise turns are gone, the return to the empty site is not). With history in the
state, `qh_none` runs more laps than the profile (38–46) and holds hidden food at or above the floor (37–46); reverse
replay now helps (its backups carry "empty" with them), `qh_reverse` ≥ `qh_none` on laps; uniform between. The reflex
arms stay near 23, so the half-bound needs 46 learned traversals: uncertain, and the most likely failure.
