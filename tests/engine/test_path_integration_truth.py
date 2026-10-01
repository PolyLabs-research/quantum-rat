"""Path integration must track the true dead-reckoned position.

Behavioural assertion for the spatial system: given a known egomotion sequence,
the reconstructed grid position matches the analytic result (no sensory gating
here, so gain is 1).
"""

import math

from brain.contracts import Observation
from brain.systems.spatial import SpatialSystem


def _obs(forward: float, turn: float) -> Observation:
    return Observation(
        vision_rays=(),
        whisker_hits=(False, False),
        pain_signal=0.0,
        forward_delta=forward,
        turn_delta=turn,
    )


def test_straight_line_integration():
    sp = SpatialSystem()
    for _ in range(10):
        sp.step(_obs(0.5, 0.0))
    assert math.isclose(sp.state.grid_x, 5.0, abs_tol=1e-6)
    assert math.isclose(sp.state.grid_y, 0.0, abs_tol=1e-6)


def test_turn_then_move_integration():
    sp = SpatialSystem()
    sp.step(_obs(0.0, math.pi / 2))  # face +y
    for _ in range(4):
        sp.step(_obs(0.5, 0.0))
    assert math.isclose(sp.state.grid_x, 0.0, abs_tol=1e-6)
    assert math.isclose(sp.state.grid_y, 2.0, abs_tol=1e-6)
