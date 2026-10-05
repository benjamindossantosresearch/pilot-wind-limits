#!/usr/bin/env python3
"""
us_wind_speed.py

Exploratory X5 (notes/decisions.md, 2026-10-04): approach performance against total wind
speed instead of crosswind. Same primary sample and scores as us_q2.py.

  * shares above 1, 2, 3 by total wind speed band
  * the registered model with total wind speed in place of crosswind (piecewise linear,
    knots 5, 10, 15 kt), no headwind term, gust spread and controls kept
  * at the same total wind, shares above 1 by the crosswind fraction of the wind

    python3 us_wind_speed.py

Writes <us_q2.OUT>/wind_speed_summary.txt.
"""

import math
import os

import numpy as np

import us_q2

BANDS = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 99)]


def total_wind_effects(d, value, label):
    L = []
    d = d[d["wind_kt"].notna()].copy()
    d["xw_kt"] = d["wind_kt"]   # the model's wind variable becomes total wind speed
    d["hw_kt"] = 0.0            # constant, so it drops out
    for thr in (1, 2):
        d["_y"] = (d[value] > thr).astype(float)
        beta, V, pos, n = us_q2.lpm(d, "_y", label)
        cells = []
        for x in (5, 10, 15, 20):
            w = {"xw": x}
            for k in (5, 10, 15):
                if x > k:
                    w[f"xw>{k}"] = x - k
            e, lo, hi = us_q2.lin_combo(beta, V, pos, w)
            cells.append(f"{x} kt {100 * e:+.1f} ({100 * lo:+.1f} to {100 * hi:+.1f})")
        g = us_q2.lin_combo(beta, V, pos, {"gust": 5})
        L.append(f"  {label}, {value} above {thr} (base {100 * d['_y'].mean():.1f}%, n={n:,}): change in points against calm, by total wind: "
                 + ", ".join(cells) + f". Per 5 kt gust spread {100 * g[0]:+.1f} ({100 * g[1]:+.1f} to {100 * g[2]:+.1f})")
    dd = d[d[value] > 0].copy()
    dd["_ly"] = np.log(dd[value])
    beta, V, pos, n = us_q2.lpm(dd, "_ly", label, spline=False)
    e, lo, hi = us_q2.lin_combo(beta, V, pos, {"xw": 5})
    L.append(f"  {label}, log {value} per 5 kt total wind: {100 * (math.exp(e) - 1):+.1f}% ({100 * (math.exp(lo) - 1):+.1f} to {100 * (math.exp(hi) - 1):+.1f}), n={n:,}")
    return L


def main():
    df = us_q2.load()
    P = df[(df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok")].copy()
    J = df[(df["group"] == "jet") & (df["vmc"] == 1) & (df["status"] == "ok") & (df["straight_in"] == "yes")].copy()
    T = P[P["S_turn"].notna()]
    L = [f"X5 exploratory: approach performance against total wind speed. Piston measurable approaches {len(P):,}, with total wind {P['wind_kt'].notna().sum():,}.", ""]
    L.append("1. Shares by total wind speed band")
    for d, value, label in ((P, "S_fp", "Piston"), (P, "S_spd", "Piston"), (T, "S_turn", "Piston turn to final"), (J, "S_fp", "Jets")):
        L += us_q2.banded(d, "wind_kt", BANDS, value, f"{label}, total wind")
    L.append("")
    L.append("2. Model with total wind speed in place of crosswind (no headwind term)")
    for d, value, label in ((P, "S_fp", "Piston"), (P, "S_spd", "Piston"), (T, "S_turn", "Piston turn to final"), (J, "S_fp", "Jets (floor)")):
        L += total_wind_effects(d, value, label)
    L.append("")
    L.append("3. Same total wind, by crosswind fraction of the wind (share above 1)")
    P = P[P["wind_kt"] > 0].copy()
    P["frac_x"] = P["xw_kt"] / P["wind_kt"]
    for lo, hi in ((5, 10), (10, 15), (15, 20)):
        g = P[(P["wind_kt"] >= lo) & (P["wind_kt"] < hi)]
        cells = []
        for a, b, name in ((0, 1 / 3, "mostly along the runway"), (1 / 3, 2 / 3, "mixed"), (2 / 3, 1.01, "mostly across")):
            h = g[(g["frac_x"] >= a) & (g["frac_x"] < b)]
            if len(h) < 100:
                cells.append(f"{name}: n<100")
                continue
            cells.append(f"{name} (n={len(h):,}): flight path {100 * (h['S_fp'] > 1).mean():.1f}%, speed {100 * (h['S_spd'] > 1).mean():.1f}%")
        L.append(f"  total wind {lo}-{hi - 1} kt: " + "; ".join(cells).replace("; ", " | "))
    text = "\n".join(L)
    open(os.path.join(us_q2.OUT, "wind_speed_summary.txt"), "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
