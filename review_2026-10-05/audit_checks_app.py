#!/usr/bin/env python3
"""Approach-level checks of the outside audit (2026-10-05): wind source and gust spread at the gate, position
source of the gate point, ownership classes. Primary US file, piston, VMC, measurable, included days."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import us_inclusion as ui  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_checks_app.txt")
cols = ["airport", "date", "group", "vmc", "status", "inferred", "wind_src", "gust_spread", "src", "ownership", "xw_kt", "nacp"]
d = pd.read_csv("q2_us_v31_cas/approaches.csv", usecols=cols, low_memory=False)
inc = ui.load()
d = d[np.array([inc.day_ok(a, x) for a, x in zip(d["airport"].values, d["date"].values)])]
P = d[(d["group"] == "piston") & (d["vmc"] == 1)]
Q = P[(P["status"] == "ok") & P["inferred"].isna()]
L = [f"Measurable piston approaches (observed): {len(Q):,}"]
L.append("Wind source at the gate: " + ", ".join(f"{k} {v:,} ({100 * v / len(Q):.1f}%)" for k, v in Q["wind_src"].value_counts(dropna=False).items()))
for s, g in Q.groupby("wind_src", dropna=False):
    gs = g["gust_spread"].dropna()
    L.append(f"  {s}: gust spread median {gs.median():.1f} kt, zero on {100 * (gs == 0).mean():.1f}%, max {gs.max():.1f}")
L.append("Position source of the gate point: " + ", ".join(f"{k} {v:,} ({100 * v / len(Q):.2f}%)" for k, v in Q["src"].value_counts(dropna=False).items()))
L.append("Ownership, measurable: " + ", ".join(f"{k} {v:,} ({100 * v / len(Q):.2f}%)" for k, v in Q["ownership"].value_counts(dropna=False).items()))
L.append("Ownership, piston VMC (Q1b base): " + ", ".join(f"{k} {v:,} ({100 * v / len(P):.2f}%)" for k, v in P["ownership"].value_counts(dropna=False).items()))
open(OUT, "w").write("\n".join(L) + "\n")
print("\n".join(L))
