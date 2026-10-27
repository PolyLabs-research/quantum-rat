# M3 step 2: the exploration behind the draft preregistration (`docs/prereg/m3_step2.md`)

Exploratory, on spent seeds (gate 31–42, track 31–38, hidden food 1–8), run before the draft was written; each prints
its table. Run from the repository root, e.g. `python3 tools/m3_step2_probes/step2_probe.py`; each uses 28 workers.

| script | what |
|---|---|
| `step2_probe.py` | reachable value probes off / on, open and L arenas, told the start or nothing with cues |
| `step2_checks.py` | the latency from the walled-off starts; hidden food with the probes |
| `g45_diag.py` | why G45's corridor options broke the visible approach: success, the target in view, time near a wall |
| `vision_probe.py` | a 300-degree visual field against the short wall range: the track and both gates |
| `track_reward_probe.py` | the track with food alternating between its ends: is lap running learned? |
