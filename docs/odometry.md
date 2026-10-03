# Odometry: the research profile's self-motion noise, characterised (M1)

The research profile estimates its own motion with seeded noise (M0b item 8, `core/sensors.py`): the raw forward displacement d becomes d (1 + 0.05 ξ) and the raw heading change gets + N(0, 0.01 rad), both drawn on every tick and both *before* the Observation's clamps (forward in [−1, 1] units, turn in [−π, π]). `brain/systems/spatial.py` dead-reckons from the two numbers; nothing resets the estimate until M2b's wall-contact reset. `experiments/odometry_characterisation.py` runs that profile in a barren 5,000-unit box (no wall is ever reached) for 2,000 units of travel (200 m, docs/units.md) at 30 seeds per condition, records every 25 units the position-estimate error |estimate − body|, the signed heading error and the accumulated signed along-track error, fits the log-log slope of the mean error against distance over [50, 2000] with a seed-bootstrap BCa 95% interval (`analysis/stats.py`), and runs the ATP decorrelation of plan §4 M1. Tables: `docs/data/m1/odometry_{slopes,curves,seeds,atp}.csv` and `odometry_meta.json` (`python3 -m experiments.odometry_characterisation --workers 4`, 57 s at commit 48c5817). The quick version is `tools/probes/odometry_growth` (4 seeds); `tests/experiments/test_odometry_characterisation.py` pins the laws at 4 seeds and 400 units.

**The walk is what the body does, and in an open barren world it is a straight line.** With nothing in view the channel scores are constant (FORWARD 1.0, each TURN 0.3, REST 0.0), so at the research temperature 0.1 a TURN is a 1-in-500 draw: a 2,000-unit run is 2,004 ticks, 99.8% FORWARD, net displacement 1,935–1,940 units. Because the growth laws depend on whether the walk turns, the three named conditions are also run on a **turning** walk, `basal_ganglia.forward_bias` 0.15 instead of 0.8 (FORWARD 0.35 against TURN 0.3): 45% FORWARD, 52–54% TURN, 1–2% REST, 3,265–3,284 ticks and a net displacement of about 300 units for the same 2,000 of travel. Odometry and everything else stay the research defaults.

## Expectations, written before the runs

- **Speed noise alone.** A zero-mean multiplicative error sums to an error ∝ √distance (slope 0.5). But a FORWARD step of 1.0 sits at the top of the forward clamp, so on a full-thrust tick only a slowing error survives: the estimated step is min(1 + 0.05 ξ, 1), mean 1 − 0.05/√(2π) = 1 − 0.01995. On a straight walk that shortfall is linear in distance (slope 1.0, the random part under 2 units at 2,000); on a turning walk the per-tick shortfall vectors partly cancel and the biased part follows the body's net displacement, so the slope returns towards 0.5. TURN steps (0.3) are unclamped and unbiased.
- **Heading noise alone.** The heading error is a random walk, sd σ√t. On a straight walk the lateral error is its running sum, ∝ t^1.5, plus a t² cosine shortfall: slope 1.5 or a little above. On a turning walk the lateral errors decorrelate with the heading: slope about 1.0.
- **Both:** the heading term dominates at 2,000 units, so it should read like turn-only. The plan's band 0.5–1.5 brackets both laws on a turning walk; on the straight walk the heading law sits at its upper edge.

## Measured (30 seeds; error in units, 1 unit = 0.1 m)

| condition | walk | slope [BCa 95%] | per-seed slopes | error at 200 m, mean ± sd | heading rms at the end (σ√t) | clamp bias per unit |
|---|---|---|---|---|---|---|
| speed 0.05 | straight | **0.987** [0.970, 1.003] | 0.89–1.10 | 38.4 ± 1.9 | 0 | −0.0198 |
| turn 0.01 rad | straight | **1.472** [1.310, 1.623] | 0.23–2.49 | 394 ± 297 | 0.425 (0.448) | 0 |
| both (research defaults) | straight | **1.386** [1.263, 1.498] | 0.46–1.95 | 360 ± 211 | 0.310 (0.448) | −0.0197 |
| speed 0.05 | turning | **0.519** [0.435, 0.596] | 0.03–0.88 | 4.5 ± 2.5 | 0 | −0.0147 |
| turn 0.01 rad | turning | **1.041** [0.922, 1.159] | 0.20–1.83 | 108 ± 72 | 0.501 (0.573) | 0 |
| both | turning | **0.941** [0.814, 1.064] | −0.09–1.60 | 87 ± 71 | 0.517 (0.573) | −0.0146 |

The slopes are the expectations: 1.0 for the clamp-biased speed error on a straight walk and 0.5 once the walk turns; 1.5 for the heading random walk integrated along a straight line (1.47 with a wide per-seed spread, since one seed's lateral error is one realisation that can cross zero) and 1.0 once the walk turns. The heading error's spread follows σ√t to within the sampling error of 30 seeds (0.106 / 0.213 / 0.425 / 0.850 rad measured against 0.112 / 0.224 / 0.448 / 0.895 at 0.0025 / 0.005 / 0.01 / 0.02 rad on the straight walk). Against the plan's acceptance (slope in 0.5–1.5 over 200 m): every point estimate is inside on both walks; the turn-only interval on the straight walk reaches 1.62, which is the t^1.5 law itself rather than a defect, and the band was written for a walk with turns. The two grid cells that repeat named conditions (turn 0.01 rad at speed 0 and at 0.05) reproduce the named rows to the last digit.

**The grid** (straight walk, slope of the mean error; error at 200 m in brackets). Turn noise sets the size of the error, linearly in σ; speed noise mixes in the linear clamp term and so lowers the slope while changing the size little:

| | speed 0 | speed 0.05 | speed 0.1 |
|---|---|---|---|
| turn 0.0025 rad | 1.47 [1.31, 1.63] (100) | 1.24 [1.16, 1.32] (100) | 1.13 [1.08, 1.18] (123) |
| turn 0.005 rad | 1.47 [1.31, 1.63] (199) | 1.34 [1.23, 1.43] (185) | 1.24 [1.16, 1.32] (200) |
| turn 0.01 rad | 1.47 [1.31, 1.62] (394) | 1.39 [1.26, 1.50] (360) | 1.34 [1.23, 1.43] (369) |
| turn 0.02 rad | 1.46 [1.31, 1.61] (765) | 1.40 [1.28, 1.52] (703) | 1.38 [1.27, 1.49] (709) |

## The clamp bias

Measured as the signed along-track error per unit travelled, Σ(estimated − true forward displacement) / distance: −0.0198 per unit at speed noise 0.05 (per seed −0.0204 to −0.0184; the analytic −0.01995) and −0.0394 at 0.1 (analytic −0.0399), 0 to the bit without speed noise, and −0.0147 on the turning walk, which is −0.0199 times the FORWARD share of its distance (0.74: TURN steps carry no bias). The estimate falls short of the body by 2.0% of the distance walked at the research value, and that shortfall, not the random part, is the whole speed-only error (38 units at 200 m against a random sd of 1.9). It is a property of M0b's design choice to add the noise before the clamp, not of the value 0.05. **Recommendation for M2b:** widen the Observation's forward range (to ±2 units, or to 1 + 4σ) when the wall-contact reset is built, so that a full-thrust tick's estimate is zero-mean; the research baselines move then anyway. Lowering the speed noise would hide the defect, not fix it.

## ATP decorrelation (legacy profile, default 20 × 20 box, odometry 0.05 / 0.01 rad, 3,000 ticks)

| `gate_scales_egomotion` | r(step error, ATP), seeds 1–4 | r(error, ATP), all ticks | r(error, ATP), ticks 200–3,000 | error at tick 3,000 |
|---|---|---|---|---|
| True (legacy) | +0.872, +0.875, +0.874, +0.875 | −0.24, −0.24, −0.24, −0.23 | −0.022 to −0.020 | 21.3, 22.3, 20.9, 20.9 (mean 21.3) |
| False | −0.063, −0.072, −0.042, −0.038 | −0.23, −0.23, −0.31, −0.13 | −0.078 to +0.025 | 1.06, 1.11, 4.60, 0.39 (mean 1.79) |

The statistic that carries the mechanism is the relative step error on moving ticks, |estimated step| / |true step| − 1: with the gate scaling egomotion it is gate − 1 plus noise (−1 CLOSED, −0.6 NARROW), so it tracks ATP at r ≈ 0.87; with the flag off it is the speed noise and |r| < 0.08 at every seed, which meets the plan's |r| < 0.1. The error itself correlates with ATP at −0.13 to −0.31 under *both* flags, because ATP decays from 1.0 to its limit cycle over the first ~100 ticks while any error grows (a shared trend, not a coupling); from tick 200 on it is within ±0.08 under both. The 1,730 moving ticks are the same under both flags (the flag changes the estimate, not the body), and the gate is CLOSED on 85% of ticks.

## Against rodent data

The two placeholders are a heading random walk and a per-step distance error, the two noise sources path-integration models use (Cheung & Vickerstaff 2010; the human counterpart of the heading walk is veering without a sun or landmarks, Souman et al. 2009). In rats the head-direction signal drifts in darkness and the animal's heading error follows it, with small errors corrected by resetting on landmarks (Valerio & Taube 2012); Cheung et al. 2012 read the recordings as a head-direction system that is unstable within about three minutes without vision while place and grid fields stay stable for half an hour, and show that path integration alone cannot keep a stable place estimate beyond two to three minutes, so boundary information has to be fused in. At 0.01 rad per tick the model's heading sd is 0.3 rad (17°) after three minutes (900 ticks) and 0.95 rad after thirty, and the straight-walk position error at three minutes of running (about 90 m) is 12–16 m, five to eight widths of the 2 m arena: the same order of "unusable within minutes without a reset", which is what M2b's wall-contact reset exists for (Etienne & Jeffery 2004 on resets by familiar landmarks; Mittelstaedt & Mittelstaedt 1980 for homing by path integration in darkness in a rodent). No rodent dataset gives a growth exponent in this form, so the comparison is of time scales, not of slopes.

## Recommendation (the owner decides; G25 records it)

Keep turn noise 0.01 rad and speed noise 0.05, and have M2b remove the clamp bias rather than retune the values; the softmax temperature is not odometry and is not characterised here. At 0.01 rad the heading estimate spreads to 0.3 rad in three minutes and 0.95 rad in thirty, the time scale on which Cheung et al. 2012 read the rodent head-direction system as unstable without vision, and the error it produces is what a boundary reset exists to correct, so the value is in the right range for the mechanism M2b adds; it is also the value G23 G measured the maze against (47 of 480 off-axis runs lost), so keeping it keeps that comparison. Speed noise 0.05 is harmless to every result so far (G23 G: two runs of 480) and its only visible effect here is the clamp's 2% shortfall, which is a range to widen, not a value to lower. If the owner would rather have the research profile's acceptance read inside the plan's band with its interval, 0.005 rad halves every error (199 against 394 units at 200 m) at the same slope and keeps the drift on the darkness time scale (0.15 rad at three minutes).
