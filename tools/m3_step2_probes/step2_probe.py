import sys, math, statistics as st
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from experiments import rq4a_gate as rg
SEEDS = range(31, 43)
REACH = {"sensors.free_space_sensing": True, "value_memory.reachable_probes": True}
CONDS = {
    "open_anchor": dict(layout="open", start_estimate="anchor", lateral_odometry=True),
    "L_anchor": dict(layout="L", start_estimate="anchor", lateral_odometry=True),
    "L_carry_cues": dict(layout="L", start_estimate="carry", lateral_odometry=True, landmarks=True),
    "open_carry_cues": dict(layout="open", start_estimate="carry", lateral_odometry=True, landmarks=True),
}
def job(a):
    cond, reach, src, ses, seed = a
    rows = rg.run_session(src, ses, seed, reward_rule="per_feature", still_start=True, overrides=REACH if reach else None, **CONDS[cond])
    test = [r for r in rows if r["trial"] > rg.LEARNING_TRIALS]
    blocked = [r for r in test if r["start"] in rg.blocked_starts("L")]
    direct = [r for r in test if r["start"] not in rg.blocked_starts("L")]
    f = lambda rr: sum(r["reached"] for r in rr) / len(rr) if rr else float("nan")
    lat = [r["latency"] for r in test if r["reached"]]
    return cond, reach, src, ses, seed, f(test), f(blocked), f(direct), (st.median(lat) if lat else float("nan"))
if __name__ == "__main__":
    jobs = [(c, r, src, ses, s) for c in CONDS for r in (False, True) for src in ("sr", "none") for ses in ("hidden", "visible") for s in SEEDS]
    with ProcessPoolExecutor(28) as p:
        out = list(p.map(job, jobs, chunksize=1))
    for c in CONDS:
        for src in ("sr", "none"):
            for ses in ("hidden", "visible"):
                parts = []
                for r in (False, True):
                    v = [o for o in out if o[0] == c and o[1] == r and o[2] == src and o[3] == ses]
                    m = lambda i: st.mean(x[i] for x in v)
                    parts.append(f"reach={'on ' if r else 'off'} all {m(5):.3f} blk {m(6):.3f} dir {m(7):.3f} lat {st.median(x[8] for x in v if x[8]==x[8]) if any(x[8]==x[8] for x in v) else float('nan'):.0f}")
                print(f"{c:16s} {src:4s} {ses:7s} | " + " | ".join(parts))
