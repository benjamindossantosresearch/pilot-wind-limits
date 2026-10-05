#!/usr/bin/env python3
"""Outside-audit check (2026-10-05): do the approach performance results change when only approaches with
one-minute wind at the gate are used? (22% of measurable approaches fall back to METAR wind, whose gust spread
is zero unless a gust is reported.) Registered linear probability and log models, as us_q2.py."""
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import us_q2  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_q2_wind_source.txt")
us_q2_cols = ["airport", "date", "icao", "type", "group", "ownership", "runway", "status", "vmc", "straight_in", "height_source",
              "xw_kt", "hw_kt", "gust_spread", "inferred", "wind_src"] + us_q2.FP + us_q2.SPD
import us_inclusion as ui  # noqa: E402
d = pd.read_csv("q2_us_v31_cas/approaches.csv", usecols=us_q2_cols, low_memory=False)
inc = ui.load()
d = d[np.array([inc.day_ok(a, x) for a, x in zip(d["airport"].values, d["date"].values)])]
d = d[(d["group"] == "piston") & (d["vmc"] == 1) & (d["status"] == "ok") & d["inferred"].isna()].copy()
d["S_fp"] = d[us_q2.FP].max(axis=1, skipna=True)
d["S_spd"] = d[us_q2.SPD].max(axis=1, skipna=True)
d["typeg"] = d["type"].map(lambda t: us_q2.TYPE_GROUPS.get(t, "other"))
d["own"] = d["ownership"].where(d["ownership"].isin(["fleet", "private"]), "other")
m = pd.to_datetime(d["date"]).dt.month
d["season"] = np.select([m.isin([12, 1, 2]), m.isin([3, 4, 5]), m.isin([6, 7, 8])], ["DJF", "MAM", "JJA"], "SON")
d["aptrwy"] = d["airport"] + "/" + d["runway"].astype(str)
d = d[d["xw_kt"].notna() & d["hw_kt"].notna() & d["gust_spread"].notna()]


def at(x):
    w = {"xw": x}
    for k in (5, 10, 15):
        if x > k:
            w[f"xw>{k}"] = x - k
    return w


L = []
for label, sel in (("all", d), ("one-minute wind at the gate", d[d["wind_src"] == "onemin"]), ("METAR wind at the gate", d[d["wind_src"] == "metar"])):
    L.append(f"{label}: {len(sel):,} approaches")
    for a, b in ((0, 5), (5, 10), (10, 15), (15, 20)):
        g = sel[(sel["xw_kt"] >= a) & (sel["xw_kt"] < b)]
        L.append(f"  {a}-{b - 1} kt: S_fp above 1 {100 * (g['S_fp'] > 1).mean():.1f}%, above 2 {100 * (g['S_fp'] > 2).mean():.1f}%, "
                 f"S_spd above 1 {100 * (g['S_spd'] > 1).sum() / max(g['S_spd'].notna().sum(), 1):.1f}% (n={len(g):,})")
    for value, thr in (("S_fp", 1), ("S_fp", 2), ("S_spd", 1)):
        s = sel[sel[value].notna()].copy()
        s["_y"] = (s[value] > thr).astype(float)
        beta, V, pos, n = us_q2.lpm(s, "_y", "x")
        r10, r15 = us_q2.lin_combo(beta, V, pos, at(10)), us_q2.lin_combo(beta, V, pos, at(15))
        L.append(f"  {value} above {thr}: 10 kt {100 * r10[0]:+.1f} ({100 * r10[1]:+.1f} to {100 * r10[2]:+.1f}), 15 kt {100 * r15[0]:+.1f} ({100 * r15[1]:+.1f} to {100 * r15[2]:+.1f})")
    print("\n".join(L), flush=True)
open(OUT, "w").write("\n".join(L) + "\n")
