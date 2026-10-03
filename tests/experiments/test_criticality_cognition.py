"""The criticality-gain coupling (basal_ganglia.criticality_gain, 0 by default): the gain curve
peaks at kappa = 1 and, at the default coupling, changes no decision in the probed worlds
(tools/probes/dormant_couplings). These tests pin the legacy mechanism; see docs/decisions.md G22."""

from brain.contracts import Observation, VisionRay
from brain.systems.basal_ganglia import _channel_scores
from brain.systems.criticality import near_critical_gain
from core.config import BasalGangliaConfig
from experiments.criticality_cognition import assert_gain_peaks_near_criticality, run_gain_sweep


def test_near_critical_gain_peaks_at_one():
    assert near_critical_gain(1.0) == 1.0
    assert near_critical_gain(1.0) > near_critical_gain(0.7)
    assert near_critical_gain(1.0) > near_critical_gain(1.3)


def test_cortical_gain_peaks_near_criticality():
    assert_gain_peaks_near_criticality(run_gain_sweep())


def test_criticality_gain_scales_sensory_drive():
    obs = Observation(
        vision_rays=(VisionRay(0.3, "target", 0.0),),
        whisker_hits=(False, False),
        pain_signal=0.0,
        forward_delta=0.0,
        turn_delta=0.0,
    )
    on = BasalGangliaConfig(criticality_gain=1.0)
    full = _channel_scores(obs, 0.0, 1.0, False, on, {}, criticality_gain=1.0)
    reduced = _channel_scores(obs, 0.0, 1.0, False, on, {}, criticality_gain=0.5)
    assert full["FORWARD"] > reduced["FORWARD"]  # lower cortical gain weakens the target drive

    off = BasalGangliaConfig(criticality_gain=0.0)  # coupling disabled (default)
    a = _channel_scores(obs, 0.0, 1.0, False, off, {}, criticality_gain=1.0)
    b = _channel_scores(obs, 0.0, 1.0, False, off, {}, criticality_gain=0.5)
    assert a["FORWARD"] == b["FORWARD"]
