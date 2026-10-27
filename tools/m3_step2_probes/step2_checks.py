import sys, statistics as st
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from experiments import rq4a_gate as rg
from experiments import console_ablation as ca
REACH = {"sensors.free_space_sensing": True, "value_memory.reachable_probes": True}
def lat(a):
    reach, layout, seed = a
    rows = rg.run_session("sr", "hidden", seed, reward_rule="per_feature", still_start=True, layout=layout, lateral_odometry=True,
                          overrides=REACH if reach else None)
    return reach, layout, seed, [r["latency"] for r in rows if r["trial"] > 20 and r["reached"] and r["start"] in rg.blocked_starts("L")]
def food(a):
    reach, arm, seed = a
    r = ca.run_one(("hidden_food", "research", arm, seed, 3000, {**(REACH if reach else {}), "sensors.lateral_odometry": True}, ca.ARMS))
    return reach, arm, seed, r["metrics"]["finds"], r["metrics"]["orbit_fraction"]
if __name__ == "__main__":
    with ProcessPoolExecutor(28) as p:
        L = list(p.map(lat, [(r, lay, s) for r in (False, True) for lay in ("open", "L") for s in range(31, 43)]))
        F = list(p.map(food, [(r, a, s) for r in (False, True) for a in ("steer", "no_steer") for s in range(1, 9)]))
    for r in (False, True):
        for lay in ("open", "L"):
            v = [x for o in L if o[0] == r and o[1] == lay for x in o[3]]
            print(f"reach={r} {lay}: blocked-start arrivals {len(v)}, median latency {st.median(v) if v else float('nan')}")
    for r in (False, True):
        for arm in ("steer", "no_steer"):
            v = [o for o in F if o[0] == r and o[1] == arm]
            print(f"hidden food reach={r} {arm}: finds {st.mean(o[3] for o in v):.2f} orbit {st.mean(o[4] for o in v):.3f}")
