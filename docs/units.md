# Physical units

`core.config.UnitsConfig` declares, once, what a tick and a world unit mean:

```python
UnitsConfig(dt_s=0.2, metres_per_unit=0.1)  # EngineConfig().units, identical in the legacy and research profiles
```

It is a declaration, not a mechanism: no engine constant reads it (plan section 5, M0b item 6: "no constants change; they acquire meaning"). Its helpers are `seconds(ticks)`, `ticks(seconds)` (the nearest whole tick, halves rounded up), `metres(units)`, `units(metres)`, `metres_per_second(units_per_tick)` and `radians_per_second(rad_per_tick)`. Per-second rates multiply by `ticks_per_second = 1 / dt_s` (exactly 5.0) rather than divide by `dt_s`, so the table below holds to the last bit (`0.3 / 0.2` reads 1.4999999999999998). `EngineConfig.to_dict()` carries it under `units`, so a manifest records it. The durations and distances in the replay metric definitions of plan section 2 (the 2 s reward and pre-run windows, the 0.05 m/s run-onset threshold, the 0.3 m event span, the 0.5 m remote-start distance) are expressed through this config: a change here moves all of them together, and nothing else.

One convention this corrects: earlier probe texts and decision entries wrote "m" for a world unit ("20 x 20 m box", "the nominal 1.0 m FORWARD", "22.8 m"). Under the declaration a unit is 0.1 m, so those numbers are units: the box is 2 m x 2 m and the path-integration capture was 2.3 m. The plan already uses this reading.

## The derived table

| Engine quantity | In engine units | In physical units |
|---|---|---|
| One tick | 1 tick | 0.2 s |
| Arena, `WorldConfig.bounds` (10, 10) | 20 x 20 units | 2 m x 2 m open field |
| FORWARD step (thrust 1.0) | 1.0 unit per tick | 0.5 m/s nominal; realised only with energy scaling off (research profile) |
| TURN step (`TURN_THRUST` 0.3, `TURN_STEP` 0.3 rad) | 0.3 unit and 0.3 rad per tick | 0.15 m/s and 1.5 rad/s; heading quantised in 0.3 rad (17.2 degree) steps |
| Circle a run of TURNs traces (`TURN_RADIUS`) | 1.004 units radius | 0.10 m |
| Memory-maze trial timeout (`MemoryMaze.TIMEOUT` 300) | 300 ticks | 60 s, the standard trial |
| A 3,000-tick open-field run | 3,000 ticks | 600 s |
| Place-cell bin (`spatial.bin_size` 0.5) | 0.5 unit | 5 cm |
| Vision range (`sensors.vision_range` 12), whisker range (1) | 12 units, 1 unit | 1.2 m, 10 cm |
| Rats running a track (plan section 5 item 6), for comparison | | 0.2-0.6 m/s |

The heading quantisation is a kinematic constraint of the model whatever the calibration: the agent turns in 0.3 rad steps and never less. Every write-up states it.

## The measurement (`tools/probes/realised_speed`)

Open-field protocol, seeds 1-4, 3,000 ticks (600 s) each, moving tick = step > 0.05 units; recorded output in `tools/probes/README.md`.

| | research profile (pooled; per-seed range) | legacy profile (pooled; seeds identical) |
|---|---|---|
| Mean speed on moving ticks | 0.317 m/s (0.311-0.322) | 0.077 m/s |
| Mean speed over all ticks | 0.274 m/s | 0.044 m/s (the 0.088-unit mean step of `open_field_motion`) |
| Immobile ticks | 13.7% (10.2-17.7%) | 42.7% |
| Stop bouts (complete runs of immobile ticks) | 500; median 0.2 s (one REST tick), max 11.8 s (6.4-11.8) | 50 per seed; median 5.0 s (the 25-tick microsleep), max 7.4 s |
| Ticks with the body clamped at a wall | 28.9% (25.2-32.3%) | 1.6% |
| Ticks turning; size of a turn | 54.4%; every turn 0.3 rad (1.5 rad/s) | 48.1%; 0.08-0.28 rad, 512 distinct values (the throttle scales the turn too) |

Against rats: the research agent's moving speed sits inside the 0.2-0.6 m/s track-running band, below the nominal 0.5 m/s because about half of its moving ticks are 0.3-unit TURN steps. Its stops are mostly single ticks; the few long ones (6-12 s) are the body held in a corner by the box clamp, not a pause at a reward well (the open field has none, so a few-second reward stop is not something this protocol can show). The 29% of ticks at a wall is high; rats spend much of an open-field session at the walls too, but here it is the clamp holding a softmax-driven agent, not wall following, so it reads as a property of the box, not a match. The legacy profile is slower than any running rat on every tick and its stops are the microsleep bouts; its four seeds are one run, as `seed_pseudoreplication` says.

## Recommendation

Freeze the calibration as it is: `dt_s = 0.2`, `metres_per_unit = 0.1`. The realised moving speed under the research profile is a rat's running speed, the 2 m open field is the one RQ4 asks for, and the 300-tick timeout is the standard 60 s trial. The trade-offs if the owner prefers otherwise: a shorter tick (0.1 s) makes FORWARD 1 m/s and the realised moving speed 0.63 m/s, above the band, and turns the 300-tick timeout into a 30 s trial; a larger unit (0.2 m) also makes FORWARD 1 m/s and the arena a 4 m x 4 m field, no longer the 2 m open field. Either change also alters what a 0.3 rad step is per second (3 rad/s at a 0.1 s tick), which no write-up should present as a rat's turning rate. The owner decides; because nothing in the engine reads the declaration, changing it later costs an edit here, a re-run of the probe and a re-read of plan section 2's durations, not a baseline regeneration.
