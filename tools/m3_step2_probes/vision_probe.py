import sys, statistics as st
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from experiments import rq4a_gate as rg
from experiments import body_characterisation as bc
BASE = {"sensors.free_space_sensing": True, "value_memory.reachable_probes": True, "sensors.lateral_odometry": True}
WIDE = {"sensors.fov": 5.235987755982989, "sensors.vision_rays": 11}
SHORT = {"basal_ganglia.wall_avoid_range": 1/6, "basal_ganglia.turn_commitment": 0.3}
CFGS = {"A_current": {}, "B_short": SHORT, "C_wide": WIDE, "D_wide_short": {**WIDE, **SHORT}}
def gate(a):
    c, src, ses, layout, seed = a
    rows = rg.run_session(src, ses, seed, reward_rule="per_feature", still_start=True, layout=layout,
                          overrides={**BASE, **CFGS[c]})
    t = [r for r in rows if r["trial"] > 20]
    return "gate", c, src, ses, layout, seed, sum(r["reached"] for r in t) / len(t)
def track(a):
    c, seed = a
    r = bc.run_world("track", {**BASE, **CFGS[c]}, seed, 3000)
    return "track", c, seed, r["ticks_per_lap"], r["laps"], r["stall_share"]
if __name__ == "__main__":
    gj = [(c, src, ses, lay, s) for c in CFGS for src in ("sr", "none") for ses in ("hidden", "visible") for lay in ("open", "L") for s in range(31, 43)]
    tj = [(c, s) for c in CFGS for s in range(31, 39)]
    with ProcessPoolExecutor(28) as p:
        g = list(p.map(gate, gj, chunksize=1)); t = list(p.map(track, tj, chunksize=1))
    for c in CFGS:
        parts = []
        for lay in ("open", "L"):
            for src in ("sr", "none"):
                for ses in ("hidden", "visible"):
                    v = [x[6] for x in g if x[1] == c and x[2] == src and x[3] == ses and x[4] == lay]
                    parts.append(f"{lay}/{src}/{ses[:3]} {st.mean(v):.2f}")
        tr = [x for x in t if x[1] == c]
        print(f"{c:13s} track ticks/lap {st.mean(x[3] for x in tr):6.1f} laps {st.mean(x[4] for x in tr):5.1f} stall {st.mean(x[5] for x in tr):.3f} | " + "  ".join(parts))
