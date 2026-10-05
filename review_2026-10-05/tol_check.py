#!/usr/bin/env python3
"""
tol_check.py

The tolerance sensitivities prespecified for New England (centerline 100 and 300 ft, glide path 75 and 150 ft),
run on the US primary sample (post-hoc check for the review, 2026-10-05). The flight-path score is rebuilt from
the stored check ratios with the centerline or glide-path ratios rescaled. Registered linear probability model.

    python3 review_2026-10-05/tol_check.py review_2026-10-05/us_cas.pkl
"""

import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import us_q2  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tol_check.txt")


def at(x):
    w = {"xw": x}
    for k in (5, 10, 15):
        if x > k:
            w[f"xw>{k}"] = x - k
    return w


def main(pkl):
    df = pd.read_pickle(pkl)
    Q = df[df["day_ok"] & (df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok")]
    Q = Q[Q["xw_kt"].notna() & Q["hw_kt"].notna() & Q["gust_spread"].notna()].copy()
    del df
    L = [f"US primary sample, {len(Q):,} measurable piston approaches with gate wind"]
    other = ["g_c2a", "b_c2a", "g_c4_afh", "b_c4_afh", "c4_stab"]
    for name, lat, vert in (("as prespecified (200 ft, 100 ft)", 200, 100), ("centerline 100 ft", 100, 100), ("centerline 300 ft", 300, 100),
                            ("glide path 75 ft", 200, 75), ("glide path 150 ft", 200, 150)):
        parts = [Q[c] for c in other] + [Q["g_c1"] * 200 / lat, Q["b_c1"] * 200 / lat, Q["g_c3"] * 100 / vert, Q["b_c3"] * 100 / vert]
        s = pd.concat(parts, axis=1).max(axis=1, skipna=True)
        Q["_s"] = s
        cells = []
        for thr in (1, 2):
            Q["_y"] = (Q["_s"] > thr).astype(float)
            beta, V, pos, n = us_q2.lpm(Q, "_y", "x")
            r15 = us_q2.lin_combo(beta, V, pos, at(15))
            cells.append(f"above {thr}: calm {100 * Q.loc[Q['xw_kt'] < 5, '_y'].mean():.1f}%, 15 kt {100 * r15[0]:+.1f} ({100 * r15[1]:+.1f} to {100 * r15[2]:+.1f})")
        d = Q[Q["_s"] > 0].copy()
        d["_ly"] = np.log(d["_s"])
        beta, V, pos, n = us_q2.lpm(d, "_ly", "x", spline=False)
        e = us_q2.lin_combo(beta, V, pos, {"xw": 5})
        cells.append(f"log score per 5 kt {100 * (math.exp(e[0]) - 1):+.1f}% ({100 * (math.exp(e[1]) - 1):+.1f} to {100 * (math.exp(e[2]) - 1):+.1f})")
        L.append(f"  {name}: " + "; ".join(cells).replace(";", " |"))
    text = "\n".join(L)
    open(OUT, "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1])
