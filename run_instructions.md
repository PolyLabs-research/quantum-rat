To run and check the Replay GUI, please follow these steps:

1.  **Ensure Python Dependencies are Installed:**
    Make sure all required Python packages are installed. If you haven't recently, run:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Prepare Run Data:**
    The replay server needs a directory containing your experiment or tournament run data. By default, it looks for a folder named `runs` in your project root. Let's create an example tournament run data within this directory.
    ```bash
    mkdir -p runs
    cp -r analysis/data runs/my_tournament_run
    ```
    This will create a directory `runs/my_tournament_run` which the server will discover.

3.  **Start the Replay Server:**
    Navigate to your project's root directory in your terminal and start the Flask server.
    ```bash
    python3 -m ui.replay_server --runs-dir runs --port 8000
    ```
    You should see output indicating that the Flask development server is running, likely on `http://127.0.0.1:8000/`.

4.  **Access the UI in your Web Browser:**
    Open your web browser and go to `http://localhost:8000/replay`.

    You should see the Replay UI.
    *   Use the "Runs" dropdown to select `my_tournament_run`.
    *   Then, use the "Episodes" dropdown to select an agent/protocol (e.g., `agent_0000/open_field`).
    *   The summary, tick data, and plots should then load and become interactive.

To stop the server, press `Ctrl+C` in the terminal where it's running.
