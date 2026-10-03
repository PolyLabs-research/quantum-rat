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
   `python -m experiments.runner --list` prints every protocol name.
   Press **Refresh** in the Replay tab to see new runs.

Stop the server with `Ctrl+C`.

The console binds to `127.0.0.1` only and has no login. `--host 0.0.0.0` makes it reachable from
other machines on your network, so use that only on a network you trust.
