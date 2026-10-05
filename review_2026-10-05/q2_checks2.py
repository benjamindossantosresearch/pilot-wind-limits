#!/usr/bin/env python3
"""
q2_checks2.py

Follow-ups found while running q2_checks.py (2026-10-05, post-hoc diagnostics):
  * S_spd for aircraft without a POH approach speed is the consistency check alone. Shares and the wind effect
    with S_spd restricted to approaches that have a POH approach speed (value check present).
  * Table 4 with the maximum demonstrated crosswind from published values only (as in Q1b), with intervals.

    python3 review_2026-10-05/q2_checks2.py review_2026-10-05/us_cas.pkl
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import us_q2  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "q2_checks2.txt")
XW = [(0, 5), (5, 10), (10, 15), (15, 20)]
L = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def at(x):
    w = {"xw": x}
    for k in (5, 10, 15):
        if x > k:
            w[f"xw>{k}"] = x - k
    return w


def main(pkl):
    df = pd.read_pickle(pkl)
    Q2 = df[df["day_ok"] & (df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok")].copy()
    has = Q2["poh_approach_kias"].notna()
    say(f"Measurable piston approaches {len(Q2):,}; with a POH approach speed {int(has.sum()):,} ({100 * has.mean():.1f}%)")
    say("S_spd above 1 by crosswind band: all with a speed score | with a POH approach speed (value and consistency) | without (consistency only)")
    for a, b in XW:
        g = Q2[(Q2["xw_kt"] >= a) & (Q2["xw_kt"] < b)]
        s_all = g["S_spd"].dropna()
        s_poh = g[g["poh_approach_kias"].notna()]["S_spd"].dropna()
        s_no = g[g["poh_approach_kias"].isna()]["S_spd"].dropna()
        say(f"  {a}-{b - 1} kt: {100 * (s_all > 1).mean():.1f}% (n={len(s_all):,}) | {100 * (s_poh > 1).mean():.1f}% (n={len(s_poh):,}) | {100 * (s_no > 1).mean():.1f}% (n={len(s_no):,})")
    d = Q2[has & Q2["S_spd"].notna() & Q2["xw_kt"].notna() & Q2["hw_kt"].notna() & Q2["gust_spread"].notna()].copy()
    for thr in (1, 2):
        d["_y"] = (d["S_spd"] > thr).astype(float)
        beta, V, pos, n = us_q2.lpm(d, "_y", "x")
        r10, r15 = us_q2.lin_combo(beta, V, pos, at(10)), us_q2.lin_combo(beta, V, pos, at(15))
        h = us_q2.lin_combo(beta, V, pos, {"hw": 5})
        say(f"  with a POH approach speed, S_spd above {thr}: base {100 * d['_y'].mean():.1f}%, 10 kt {100 * r10[0]:+.1f} ({100 * r10[1]:+.1f} to {100 * r10[2]:+.1f}), "
            f"15 kt {100 * r15[0]:+.1f} ({100 * r15[1]:+.1f} to {100 * r15[2]:+.1f}), per 5 kt headwind {100 * h[0]:+.1f}")
    say("")
    say("Table 4 with published maximum demonstrated values only (as Q1b). Intervals: wider of aircraft and day cluster bootstrap.")
    Q2["frac_pub"] = np.where(Q2["poh_xwind_basis"].astype(str) == "published", Q2["frac"], np.nan)
    rows = [("Calm, crosswind below 5 kt", Q2["xw_kt"] < 5), ("Revealed limit, 11.6 kt plus or minus 1 kt", (Q2["xw_kt"] >= 10.6) & (Q2["xw_kt"] < 12.6)),
            ("0.75 to 1.0 of maximum demonstrated (published)", (Q2["frac_pub"] >= 0.75) & (Q2["frac_pub"] < 1.0)),
            ("Above maximum demonstrated (published)", Q2["frac_pub"] >= 1.0)]
    for name, m in rows:
        g = Q2[m]
        cells = []
        for col, thr in (("S_fp", 1), ("S_fp", 2), ("S_fp", 3), ("S_spd", 1)):
            gg = g[g[col].notna()]
            e, lo, hi = us_q2.shares(gg, col, thr)
            cells.append(f"{col}>{thr} {100 * e:.1f} ({100 * lo:.1f} to {100 * hi:.1f})")
        say(f"  {name}: n={len(g):,} | " + " | ".join(cells))
    open(OUT, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
