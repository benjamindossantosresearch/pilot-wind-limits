#!/usr/bin/env python3
"""Third outside audit (2026-10-06): activity by headwind and crosswind components, one-minute hours."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import q1a_crosswind as qc  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit3_checks.txt")
L = []
h = pd.read_csv("q1a_us/hours.csv")
h = h[(h["base_piston"] > 0) & (h["wind_src"] == "onemin")]
act = lambda d: d["piston"].sum() / d["base_piston"].sum()
B = [(0, 3), (3, 6), (6, 9), (9, 12), (12, 15), (15, 18)]
L.append("Activity (hours, mean gust spread) by headwind row and crosswind column, one-minute hours")
L.append("  headwind | " + " | ".join(f"xw {a}-{b}" for a, b in B[:5]))
for ha, hb in B:
    cells = []
    for xa, xb in B[:5]:
        c = h[(h["hw"] >= ha) & (h["hw"] < hb) & (h["xw"] >= xa) & (h["xw"] < xb)]
        cells.append(f"{act(c):.2f} ({len(c):,}, g {c['gust_spread'].mean():.1f})" if len(c) >= 100 else f"n={len(c)}")
    L.append(f"  {ha}-{hb} | " + " | ".join(cells))
L.append("  tailwind hours (headwind below 0): " + f"{int((h['hw'] < 0).sum()):,}")
for line in qc.empirical_limit(h[h["hw"] < 3].to_dict("records"), "piston", "crosswind, headwind under 3 kt"):
    L.append(line)
for line in qc.empirical_limit(h[h["xw"] < 3].to_dict("records"), "piston", "headwind, crosswind under 3 kt", key="hw"):
    L.append(line)
open(OUT, "w").write("\n".join(L) + "\n")
print("\n".join(L))
