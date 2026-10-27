# Preregistration: a rodent-like body (M3 step 1)

**Written:** 2026-10-27, before the body exists and before any run of it (the commit that adds this document is the
registration; the decisions entry will be G44). **Scope:** an opt-in body model, characterised on a track and in the
open field against today's discrete body, and the RQ4(a) gate re-run under it on fresh seeds. No profile default
changes by this step; adopting the body is the owner's decision afterwards (`docs/m3_place_replay.md`).

## Why

M3's RQ1 protocol is a linear track with runs, reward pauses and a pre-run window defined by running speed. An
exploratory probe (research profile, 2 m × 0.1 m track, seeds 1–4 × 3,000 ticks, not committed) found the agent
completes laps by crawling: 74% of ticks TURN, 81% against a wall, 39% with no displacement, a median 97 ticks per lap
against 18 for a straight run. The cause is the body: a TURN translates 0.3 units while it rotates 0.3 rad, and nothing
aligns the body with a wall it meets, so the centre vision ray keeps finding a side wall. RatInABox's agent (George et
al. 2024) has what is missing: smooth speed and rotational velocity as Ornstein–Uhlenbeck processes fitted to rat data
(Sargolini et al. 2006), a control drift on the velocity, and wall following. Its defaults, read from its published
source (`ratinabox` 1.15.3, `Agent.default_params`): speed coherence time 0.7 s, speed standard deviation 0.08 m/s,
rotational velocity standard deviation 120°/s with coherence time 0.08 s, wall repel distance 0.1 m.

## The body (`core/body.py`, `BodyConfig`; `body.model = "rodent"`; default `"discrete"`, today's body)

State: speed `s` (m/s, ≥ 0) and angular velocity `ω` (rad/s). Per tick (`dt` = `units.dt_s`, 0.2 s):

1. **Targets from the chosen action**, scaled by the energy scale as the discrete body scales thrust (1.0 in the
   research profile): FORWARD (`run_speed`, 0); TURN_LEFT (`turn_speed`, +`turn_rate`); TURN_RIGHT (`turn_speed`,
   −`turn_rate`); REST (0, 0).
2. **Ornstein–Uhlenbeck steps toward the targets**, exactly discretised: with `a = exp(−dt/τ)`,
   `x ← x* + (x − x*)·a + σ·√(1 − a²)·ξ`, `ω` first (`rotational_coherence_time`, `rotational_noise`), then `s`
   (`speed_coherence_time`, `speed_noise`), `s` clipped at 0. The draws come from a new named stream, `body_motion`,
   only when the σ is above 0, so the existing streams are untouched.
3. **Heading** `θ ← θ + ω·dt`.
4. **Wall following.** For each arena wall (x walls, then y walls) at distance `d < wall_align_distance` toward which
   the heading points, the heading turns toward the nearer wall-parallel direction by the fraction
   `(1 − d / wall_align_distance) × min(1, s / run_speed)`: full alignment at contact and at running speed, none
   while turning in place.
5. **Move** `s·dt` metres (÷ `units.metres_per_unit`) along the heading; clamp to the bounds as today.

Parameters: `run_speed` 0.5 m/s and `turn_rate` 1.5 rad/s (today's FORWARD step and TURN step, so every task keeps
its time scale), `turn_speed` 0 (turns in place: no turning circle), `speed_coherence_time` 0.7 s,
`rotational_coherence_time` 0.08 s, `wall_align_distance` 0.1 m (RatInABox's). The egomotion contract, the estimate,
the brain and the action selection are unchanged; a heading change from wall following is a turn the body made, so
the egomotion reports it. The engine resets `s` and `ω` to 0 at `begin_episode` and the gate at each trial start (the
animal is put down still).

## Conditions

- `discrete`: today's body.
- `rodent_quiet`: the rodent body with `rotational_noise` 0 and `speed_noise` 0.
- `rodent`: the rodent body with RatInABox's noise, `rotational_noise` 120°/s (2.094 rad/s), `speed_noise` 0.08 m/s.

All on `EngineConfig.research()` (`experiments/body_characterisation.py`), seeds 1–30, 3,000 ticks each.

## Measures

- **Track** (bounds 10 × 0.5 units: 2 m × 0.1 m; the plan's track): laps (traversals between the two 1-unit end
  zones), median ticks per lap (a straight run is 18), the FORWARD share, the wall-contact share, the **stall share**
  (ticks whose action is not REST and whose displacement is below 1e-6 units), the late median estimate error
  (ticks 1,000–3,000).
- **Open field** (bounds 10 × 10: 2 m × 2 m): mean and standard deviation of speed (m/s), standard deviation of
  angular velocity (rad/s), the share of ticks within 0.1 m of a wall, coverage (the share of 0.1 m bins visited), the
  stall share, the late median estimate error, and the orbit share (`analysis.orbits`, the G40 definition).
- **The gate** (`experiments/rq4a_gate.py --body rodent|rodent_quiet`, seeds 61–90, the confirmatory settings of
  `docs/prereg/m2b_gate_confirmatory.md` otherwise: per-feature rule, one rate, all three sources).

## Bounds

- **T1 (track, primary): a rodent condition runs the track.** Median ticks per lap ≤ 36 (twice a straight run) and
  stall share < 5%, each as the mean over seeds with its BCa 95% interval's upper end below the bound.
- **T2 (track): the discrete body does not** (reported against T1's bounds; it is the baseline the step exists for).
- **G1 (gate, per rodent condition): RQ4(a) holds under the body**: the SR source's hidden ÷ visible success over
  trials 21–40 at least 0.8 and the arrival error below 2 units, as G36's bounds.
- **D (determinism):** the legacy and research baselines unchanged (the default body is `discrete`).
- **Reported, no bound:** every open-field measure, against the discrete body and against RatInABox's fitted values
  where they are comparable (its foraging mean speed is 0.08 m/s; ours is a directed agent at `run_speed`, so speed
  is not expected to match and is not a test).

## Predictions (written before any run)

- T1: `rodent_quiet` passes (median 22–30 ticks per lap, stalls under 2%); `rodent` passes more narrowly (median
  28–36; its heading noise, about 0.4 rad per tick, drives it into the side walls that alignment then corrects).
- T2: the discrete body fails both (about 97 ticks, about 35% stalls), as the probe found.
- G1: both rodent conditions pass, hidden success 90–99%; `rodent` slower to arrive than `rodent_quiet`.
- Open field: the rodent bodies spend more ticks within 0.1 m of a wall than the discrete body (wall following), have
  far fewer stalls, and a lower orbit share (no turning circle).

## Decision table

| T1 | G1 | Decision |
|---|---|---|
| a rodent condition passes | passes for it | **That condition is the candidate research-profile body**, the owner's call (the research baselines regenerate once); M3's track protocol (step 2) is built on it. If both pass, `rodent` (the RatInABox-faithful one) is recommended unless its gate result is materially worse |
| passes | fails | The body runs corridors but breaks navigation: diagnose (most likely the turn-in-place against the value steering's fan) before step 2 |
| neither passes | any | The body is not adopted; step 2 uses forced laps (G35's protocol) and the gap is recorded |

## What would change this document

Nothing after the first run. A parameter found wanting is a new preregistered step, not an amendment.
