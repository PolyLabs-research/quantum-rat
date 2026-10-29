# M3 step 3: a learned action value over the place code, with replay (the pilots; G55)

`python3 -m experiments.m3_step3 --phase pilot|pilot2 --workers 28`, exploratory on the Part 2 pilot's spent seeds
(gate and track 31–42, hidden food 1–8), step 2's battery under G53's statistics (`docs/prereg/m3_step2.md` as
amended) on the research profile as G54 left it with the step cap; the design and its selection rule in
`docs/prereg/m3_step3.md` (a draft for the owner); read in `docs/decisions.md` G55. Each directory: `gate.csv`,
`track.csv` (with `traversals_late`, `rest_share` and `replay_events`, the events the run's replay made),
`hidden_food.csv`, `open_field.csv` per configuration and seed; `summary.json` the values against the eleven bounds,
the track arms' means and the configuration the rule chose (none, in both); `manifest.json`.

`pilot/` (at `b35f0bd`, clean tree, warnings as errors, 286 s): the profile; the learner with replay none, uniform
and reverse; and reverse with the oracle state. Its read had no floor (`action_value.read_floor` 0, pinned).

`pilot2/` (at `f9d82f4`, 277 s; amendment A1): the profile; the floor alone; history among the action value's
features with replay none, uniform and reverse.

The check behind the reading (where the agent spends the track run, the wall gate's share, the turn share, the
advantages read) is `tools/m3_step3_probes/emptied_end.py`, output beside it.
