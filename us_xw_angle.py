#!/usr/bin/env python3
"""
us_xw_angle.py

Exploratory X6 (notes/decisions.md, 2026-10-04): is crosswind strength or wind angle more
tied to out-of-tolerance approaches? Same primary sample and scores as us_q2.py.

  * grid of crosswind strength by wind angle relative to the runway in use
  * the variance each wind description adds over the controls (within R squared), for
    S_fp above 1, S_fp above 2 and S_spd above 1

    python3 us_xw_angle.py

Writes <us_q2.OUT>/xw_angle_summary.txt.
"""

import os

import numpy as np
import pandas as pd

import us_q2

CONTROLS = ("typeg", "own", "season", "straight_in", "height_source")


def spline(x, knots, name):
    cols = {name: x}
    for k in knots:
        cols[f"{name}>{k}"] = (x - k).clip(lower=0)
    return pd.DataFrame(cols)


def within_r2(d, y, wind):
    """Within R squared (airport-runway absorbed) of controls plus the given wind columns."""
    X = pd.concat([wind] + [pd.get_dummies(d[c].astype(str), prefix=c, drop_first=True, dtype=float) for c in CONTROLS], axis=1)
    X["aptrwy"] = d["aptrwy"].values
    X["_y"] = y
    cols = [c for c in X.columns if c != "aptrwy"]
    Z = us_q2.demean(X, cols, "aptrwy")
    keep = [c for c in Z.columns if c != "_y" and Z[c].abs().sum() > 0]
    Xm, yy = Z[keep].values, Z["_y"].values
    beta = np.linalg.lstsq(Xm, yy, rcond=None)[0]
    e = yy - Xm @ beta
    return 1 - (e @ e) / (yy @ yy)


def main():
    df = us_q2.load()
    P = df[(df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok") & df["xw_kt"].notna() & df["hw_kt"].notna()].copy()
    P["angle"] = np.degrees(np.arctan2(P["xw_kt"], P["hw_kt"]))
    P["wind"] = np.hypot(P["xw_kt"], P["hw_kt"])
    L = [f"X6 exploratory: crosswind strength against wind angle. Piston measurable approaches with wind: {len(P):,}.",
         "Angle = atan2(crosswind, headwind) on the runway in use: 0 straight down the runway, 90 direct crosswind, above 90 quartering tailwind.", ""]
    L.append("1. Grid: share above 1 (above 2) for the flight path, above 1 for speed and turn to final")
    for xl, xh in ((5, 10), (10, 15), (15, 20)):
        for al, ah in ((0, 30), (30, 60), (60, 90), (90, 181)):
            g = P[(P["xw_kt"] >= xl) & (P["xw_kt"] < xh) & (P["angle"] >= al) & (P["angle"] < ah)]
            if len(g) < 200:
                L.append(f"  crosswind {xl}-{xh - 1} kt, angle {al}-{min(ah, 180)} deg: n={len(g)} (too few)")
                continue
            t = g[g["S_turn"].notna()]
            L.append(f"  crosswind {xl}-{xh - 1} kt, angle {al}-{min(ah, 180)} deg: n={len(g):>9,}, total wind {g['wind'].median():4.1f} kt median | "
                     f"flight path {100 * (g['S_fp'] > 1).mean():5.1f}% ({100 * (g['S_fp'] > 2).mean():4.1f}%) | speed {100 * (g['S_spd'] > 1).mean():5.1f}% | "
                     f"turn {100 * (t['S_turn'] > 1).mean():5.1f}%")
        L.append("")
    L.append("2. Variance added over the controls (within R squared x 1000), one wind description at a time")
    specs = {
        "crosswind (kt)": spline(P["xw_kt"], (5, 10, 15), "xw"),
        "wind angle (deg)": spline(P["angle"], (30, 60, 90), "ang"),
        "total wind (kt)": spline(P["wind"], (5, 10, 15), "w"),
        "crosswind + headwind (kt)": pd.concat([spline(P["xw_kt"], (5, 10, 15), "xw"), spline(P["hw_kt"], (0, 5, 10), "hw")], axis=1),
        "crosswind + angle": pd.concat([spline(P["xw_kt"], (5, 10, 15), "xw"), spline(P["angle"], (30, 60, 90), "ang")], axis=1),
    }
    for yname, y in (("flight path above 1", (P["S_fp"] > 1).astype(float).values),
                     ("flight path above 2", (P["S_fp"] > 2).astype(float).values),
                     ("speed above 1", (P["S_spd"] > 1).astype(float).values)):
        base = within_r2(P, y, pd.DataFrame(index=P.index))
        cells = [f"{name} {1000 * (within_r2(P, y, X) - base):.2f}" for name, X in specs.items()]
        L.append(f"  {yname} (controls alone {1000 * base:.2f}): " + ", ".join(cells))
    text = "\n".join(L)
    open(os.path.join(us_q2.OUT, "xw_angle_summary.txt"), "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
