
import os
import json
from flask import Flask, jsonify, request, send_from_directory, redirect, url_for

from ui.replay_index import get_safe_path, read_jsonl_paged, get_run_root

app = Flask(__name__, static_folder="static")

@app.route('/')
def index():
    return redirect(url_for('replay_ui'))

@app.route('/replay')
def replay_ui():
    return send_from_directory(app.static_folder, 'replay.html')

@app.route("/api/runs")
def list_runs():
    """
    Lists available runs, distinguishing between experiment and tournament types.
    """
    run_root = get_run_root()
    runs = []
    if not run_root.exists():
        return jsonify({"runs": [], "error": f"Run directory not found: {run_root}"})

    for run_dir in sorted(run_root.iterdir()):
        if not run_dir.is_dir():
            continue
        
        run_id = run_dir.name
        run_type = "unknown"
        if (run_dir / "ticks.jsonl").exists():
            run_type = "experiment"
        elif (run_dir / "agents").exists():
            run_type = "tournament"
        
        if run_type != "unknown":
            runs.append({"id": run_id, "type": run_type})
    
    return jsonify({"runs": runs})

@app.route("/api/runs/<run_id>/episodes")
def list_episodes(run_id: str):
    """
    Lists all episodes for a given run.
    For experiments, this is just a "default" episode.
    For tournaments, this is each agent/protocol combination.
    """
    try:
        run_path = get_safe_path(run_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not run_path.exists():
        return jsonify({"error": "Run not found"}), 404

    episodes = []
    # Experiment run type
    if (run_path / "ticks.jsonl").exists():
        episodes.append({
            "episode_id": "default",
            "agent_id": "default",
            "protocol": run_id,
        })
    # Tournament run type
    elif (run_path / "agents").exists():
        agents_dir = run_path / "agents"
        for agent_dir in sorted(agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            for protocol_dir in sorted(agent_dir.iterdir()):
                if not protocol_dir.is_dir():
                    continue
                if (protocol_dir / "summary.json").exists():
                    agent_id = agent_dir.name
                    protocol = protocol_dir.name
                    episodes.append({
                        "episode_id": f"{agent_id}/{protocol}",
                        "agent_id": agent_id,
                        "protocol": protocol,
                    })
                    
    return jsonify({"episodes": episodes})


@app.route("/api/runs/<run_id>/<agent_id>/<protocol_id>/summary")
def get_summary(run_id: str, agent_id: str, protocol_id: str):
    try:
        if agent_id == "default":
            summary_path = get_safe_path(run_id, "summary.json")
        else:
            summary_path = get_safe_path(run_id, "agents", agent_id, protocol_id, "summary.json")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not summary_path.exists():
        return jsonify({"error": "Summary not found"}), 404
        
    with open(summary_path, "r") as f:
        return jsonify(json.load(f))


@app.route("/api/runs/<run_id>/<agent_id>/<protocol_id>/ticks")
def get_ticks(run_id: str, agent_id: str, protocol_id: str):
    start = request.args.get("start", 0, type=int)
    limit = request.args.get("limit", 500, type=int)

    try:
        if agent_id == "default":
            ticks_path = get_safe_path(run_id, "ticks.jsonl")
        else:
            ticks_path = get_safe_path(run_id, "agents", agent_id, protocol_id, "ticks.jsonl")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not ticks_path.exists():
        return jsonify({"error": "Ticks file not found"}), 404
        
    ticks, total = read_jsonl_paged(ticks_path, start, limit)
    
    return jsonify({
        "start": start,
        "limit": limit,
        "total": total,
        "ticks": ticks,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Default to "runs" if not set.
    if "CRITICAL_RAT_RUNS_DIR" not in os.environ:
        os.environ["CRITICAL_RAT_RUNS_DIR"] = "runs"
    
    app.run(host="0.0.0.0", port=port, debug=True)
