"""A snapshot of the arena layout, saved next to a run's ticks for the replay viewer.

Tick rows record where the agent was, not what the world looked like, so a run
also gets a ``scene.json``: the arena bounds, the objects in it and the agent's
start pose (the origin of its path-integration frame).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def scene_dict(engine: Any, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The engine's current world layout as plain JSON-ready data."""
    agent = engine.agent
    scene: Dict[str, Any] = {
        "bounds": [float(b) for b in engine.world.bounds],
        "objects": [
            {"x": float(o.x), "y": float(o.y), "r": float(o.radius), "kind": o.kind}
            for o in engine.world.objects
        ],
        "start_pose": [float(agent.pos[0]), float(agent.pos[1]), float(agent.heading)],
        # Glycogen is logged in absolute units; the viewer shows it as a fraction of this store.
        "energy": {"glycogen_max": float(engine.config.astrocyte.glycogen_max)},
    }
    if extra:
        scene.update(extra)
    return scene


def write_scene(engine: Any, path: Path, extra: Optional[Dict[str, Any]] = None) -> None:
    Path(path).write_text(json.dumps(scene_dict(engine, extra), indent=2, sort_keys=True))


__all__ = ["scene_dict", "write_scene"]
