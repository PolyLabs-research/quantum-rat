# Running the lab console

The lab console is a local web app with two views: **Live** (run the brain in a scenario and watch
it think) and **Replay** (open a recorded run and step through it). It needs only Flask and works
offline.

1. **Install the Python dependencies** (once):
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the console** from the project root:
   ```bash
   python -m ui
   ```
   Your browser opens at <http://127.0.0.1:8000/>. Useful options:
   * `--port 8001` to use another port
   * `--runs-dir path/to/runs` to read and write runs somewhere other than `./runs`
   * `--no-browser` to skip opening a tab

   Without `--port` or `--runs-dir`, the `PORT` and `CRITICAL_RAT_RUNS_DIR` environment variables
   are used if set (flags win).

   `python -m ui.replay_server` still works and starts the same console.

3. **Live tab.** Choose a scenario on the left. Play/pause with the button or `Space`; step one
   tick with `→`. Drag parameters to change the brain while it runs (they survive a reset).
   **Record to replay** saves the session into the runs directory.

4. **Replay tab.** Pick a run and an episode, then play or drag the scrubber. Click a chart or a
   "key moment" to jump to it. The tick inspector lists every logged field.

   To make runs from the command line instead:
   ```bash
   # one experiment run -> runs/foraging_1337/
   python -m experiments.runner --protocol foraging --ticks 2000

   # the same run under the research profile (docs/profiles.md); the bare
   # protocols take --profile, the console_* ones below bring their own config
   python -m experiments.runner --protocol foraging --ticks 2000 --profile research

   # a console scenario headless: console_open_field, console_beacon, console_foraging,
   # console_hazard_field, console_hidden_food or console_memory_maze. Same ticks as a
   # live session of that scenario at that seed, plus events.jsonl (the event log)
   python -m experiments.runner --protocol console_hidden_food --seed 7 --ticks 3000

   # a tournament with per-tick logs (without --include-ticks only summaries are saved)
   python -m tournaments.runner --seed 7 --n-agents 2 --ticks 300 \
       --protocols beacon,open_field --include-ticks --out runs/my_tournament
   ```
   Every run directory (and the tournament root, and a console recording) also gets a
   `manifest.json`: git SHA and dirty flag, the full engine config and profile, seeds,
   platform, Python and numpy versions, BLAS build and thread settings, wall-clock and
   ticks/s. It is provenance only, never part of a hash, and the replay viewer ignores it.
   A run in which the engine replayed also gets `replay_events.jsonl` (one replay event per
   line: the ticks it ran over, its trigger and rule, the cells it backed up) and
   `n_replay_events` in `summary.json`; the research profile never sleeps, so it writes neither.
   A console recording keeps the newest 50,000 ticks and the newest 4,096 replay events of the
   live session and writes only the events that end inside the recorded ticks (`n_replay_events`
   counts those; `n_replay_events_total` is every event the session saw since it was built or
   reset).
   `python -m experiments.runner --list` prints every protocol name.
   Press **Refresh** in the Replay tab to see new runs.

   The M2a replay comparison is its own command (docs/m2a_linear_track.md):
   ```bash
   # the fixed evaluation: 4 conditions x seeds 1-30, 40 laps each, 7 s on 4 cores
   python -m experiments.linear_track_replay --workers 4
   # a smoke run elsewhere (the committed tables in docs/data/m2a/track are refused for partial runs)
   python -m experiments.linear_track_replay --seeds 3 --quick --out /tmp/track
   ```
   It writes `track_laps.csv`, `track_per_seed.csv`, `track_summary.csv`, `track_learning_curve.csv`,
   `track_effects.csv`, `track_replay_events.jsonl.gz` and `track_manifest.json`; the tables are
   byte-identical at any worker count. Two companions read or re-run it:
   ```bash
   # replay events by the plan's definition, from the committed event file (0.3 s)
   python -m analysis.replay_metrics docs/data/m2a/track/track_replay_events.jsonl.gz
   # the ranking with one parameter changed at a time, 11 variants x 4 conditions x 30 seeds (about 90 s)
   python -m experiments.linear_track_sensitivity --workers 4
   # step 2 (docs/prereg/rq1_track_tabular.md): the RQ1 protocol on the four floors, four reward blocks, two
   # pauses per lap, fixed and thresholded budgets (--version step2 writes docs/data/m2a/rq1), and the
   # dose-response of the fixed budget (docs/data/m2a/rq1)
   python -m experiments.linear_track_rq1 --version step2 --workers 4
   python -m experiments.linear_track_dose_response --workers 4
   # step 3 (docs/prereg/rq1_track_gain_need.md): the same protocol with gain x need, gain-only and need-only
   # beside the floors, theta per rule, the trajectory rule's remaining-max priority; about 17 min on 4 cores,
   # writes docs/data/m2a/rq1_step3
   python -m experiments.linear_track_rq1 --version step3 --workers 4
   # step 4 (docs/prereg/rq1_track_step4.md): the seven conditions in two sessions per seed (baseline then x4;
   # baseline then x0.25), theta scaled by the learner's value scale; the pilot that set theta (6 s) and the
   # evaluation (about 17 min on 4 cores, writes docs/data/m2a/rq1_step4)
   python -m experiments.linear_track_rq1 --pilot --version step4 --workers 4
   python -m experiments.linear_track_rq1 --version step4 --workers 4
   # step 5 (docs/prereg/rq1_track_mattar_daw.md): step 4's protocol on a tabular Q learner, the floors rerun on it
   # and the Mattar & Daw rule with and without its forward n-step extension; the pilot (6 s) and the evaluation
   # (about 15 min on 4 cores, writes docs/data/m2a/rq1_step5)
   python -m experiments.linear_track_rq1 --pilot --workers 4
   python -m experiments.linear_track_rq1 --workers 4
   ```

Stop the server with `Ctrl+C`.

The console binds to `127.0.0.1` only and has no login. `--host 0.0.0.0` makes it reachable from
other machines on your network, so use that only on a network you trust.
