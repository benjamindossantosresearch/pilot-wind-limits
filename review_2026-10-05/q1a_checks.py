#!/usr/bin/env python3
"""
q1a_checks.py

Review checks on the US revealed limit (logged in notes/decisions.md, 2026-10-05). Post-hoc, from the frozen
q1a_us/hours.csv. Nothing in the frozen outputs changes.

  A. Headline limit with the seven New England development airports left out.
  B. Capture correction: arrivals divided by modeled capture exp(b x hourly mean wind), baselines recomputed.
  C. Model-free (11.6 kt) against spline (13.3 kt): what accompanies crosswind in practice.

    python3 review_2026-10-05/q1a_checks.py
"""

import csv
import math
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import q1a_crosswind as qc  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "q1a_checks.txt")
DEV = {"BDR", "HVN", "BED", "LWM", "OWD", "PYM", "TAN"}
GROUPS = ("piston", "fleet", "private")


def load():
    rows = []
    with open("q1a_us/hours.csv") as f:
        for r in csv.DictReader(f):
            for k in ("xw", "hw", "speed", "gust_spread", "gust_xw", "base_piston", "base_fleet", "base_private"):
                r[k] = float(r[k])
            for k in ("hour", "piston", "fleet", "private", "all_fixed"):
                r[k] = int(r[k])
            rows.append(r)
    return rows


def rebase(rows, groups=GROUPS):
    """Recompute normal demand per airport, season, day type, and hour from the (possibly corrected) counts."""
    cells = defaultdict(list)
    for r in rows:
        cells[(r["airport"], r["season"], r["weekend"], r["hour"])].append(r)
    for g in cells.values():
        for grp in groups:
            m = sum(r[grp] for r in g) / len(g)
            for r in g:
                r[f"base_{grp}"] = m
    return rows


def spline_fit(rows, group="piston"):
    rows = [r for r in rows if r[f"base_{group}"] > 0]
    X = np.array([[1.0] + qc.spline(r["xw"]) + qc.spline(r["hw"]) + qc.spline(r["gust_spread"]) for r in rows])
    y = np.array([r[group] for r in rows], dtype=float)
    off = np.log(np.array([r[f"base_{group}"] for r in rows]))
    keep = np.array([True] + [(X[:, j] > 0).sum() >= 20 for j in range(1, X.shape[1])])
    beta, _ = qc.poisson_fit(X[:, keep], y, off, np.arange(len(y)))
    return beta, keep, rows


def curve_at(beta, keep, xs, hws, gss):
    G = np.array([[1.0] + qc.spline(x) + qc.spline(h) + qc.spline(g) for x, h, g in zip(xs, hws, gss)])[:, keep]
    return np.exp(G @ beta)


def first_crossing(xs, ys, p=0.5):
    for i in range(1, len(xs)):
        if ys[i] <= p:
            return xs[i - 1] + (ys[i - 1] - p) / (ys[i - 1] - ys[i]) * (xs[i] - xs[i - 1]) if ys[i - 1] > p else xs[i]
    return float("inf")


def main():
    rows = load()
    L = [f"Review checks on the US revealed limit, from q1a_us/hours.csv ({len(rows):,} VMC airport-hours)", ""]

    # A. development airports out
    dev_in = sorted({r["airport"] for r in rows} & DEV)
    L.append(f"A. New England development airports present in the US Q1a hours: {', '.join(dev_in)} "
             f"({sum(1 for r in rows if r['airport'] in DEV):,} hours, {sum(r['piston'] for r in rows if r['airport'] in DEV):,} piston arrivals)")
    sel = [r for r in rows if r["airport"] not in DEV]
    for grp in GROUPS:
        L += qc.empirical_limit(sel, grp, f"Development airports out, model-free, {grp}")
    L.append("")

    # B. capture correction
    L.append("B. Capture correction. Arrivals divided by exp(b x wind), b from the capture-vs-weather tests (log capture), baselines recomputed.")
    tests = [("development, mean wind, -3.9% per 10 kt", "speed", -0.039), ("development, lower bound, -6.2% per 10 kt", "speed", -0.062),
             ("US v3.1, mean wind, -1.8% per 10 kt", "speed", -0.018), ("US v3.1, lower bound, -4.0% per 10 kt", "speed", -0.040),
             ("development, best-runway crosswind, -1.9% per 10 kt", "xw", -0.019), ("US v3.1, crosswind, -2.9% per 10 kt", "xw", -0.029),
             ("US v3.1, crosswind lower bound, -6.4% per 10 kt", "xw", -0.064)]
    for name, key, pct in tests:
        b = math.log(1 + pct) / 10.0
        cor = []
        for r in rows:
            c = dict(r)
            f = math.exp(b * r[key])
            for grp in GROUPS:
                c[grp] = r[grp] / f
            cor.append(c)
        rebase(cor)
        res = qc.empirical_limit(cor, "piston", f"Capture-corrected ({name}), piston")
        L.append(res[1].replace("  revealed limit 50%", f"  {name}: revealed limit 50%"))
    L.append("")

    # C. model-free against spline
    L.append("C. Why the model-free limit (total effect) sits below the spline limit (headwind and gust spread at their medians)")
    bins = [(a, a + 2) for a in range(0, 20, 2)]
    L.append("  Mean headwind, gust spread, and total wind by 2 kt crosswind bin (piston hours with a baseline):")
    for a, b in bins:
        g = [r for r in rows if a <= r["xw"] < b and r["base_piston"] > 0]
        if len(g) >= 20:
            L.append(f"    {a:2d}-{b:2d} kt: n={len(g):7,}, headwind {np.mean([r['hw'] for r in g]):5.1f}, gust spread {np.mean([r['gust_spread'] for r in g]):5.1f}, "
                     f"total wind {np.mean([r['speed'] for r in g]):5.1f}, activity {sum(r['piston'] for r in g) / sum(r['base_piston'] for r in g):.2f}")
    beta, keep, fit_rows = spline_fit(rows)
    hw_med = float(np.median([r["hw"] for r in fit_rows]))
    gs_med = float(np.median([r["gust_spread"] for r in fit_rows]))
    grid = np.arange(0, 20.05, 0.1)
    c_med = curve_at(beta, keep, grid, [hw_med] * len(grid), [gs_med] * len(grid))
    L.append(f"  Spline fit, headwind {hw_med:.1f} and gust spread {gs_med:.1f} at their medians: 50% point {first_crossing(grid, c_med):.1f} kt")
    mids, hws, gss, obs = [], [], [], []
    for a, b in bins:
        g = [r for r in fit_rows if a <= r["xw"] < b]
        if len(g) >= 20:
            mids.append((a + b) / 2)
            hws.append(np.mean([r["hw"] for r in g]))
            gss.append(np.mean([r["gust_spread"] for r in g]))
            obs.append(sum(r["piston"] for r in g) / sum(r["base_piston"] for r in g))
    c_bin = curve_at(beta, keep, mids, hws, gss)
    L.append(f"  Spline fit, headwind and gust spread at the means seen in each crosswind bin (the conditions that come with that crosswind): "
             f"50% point {first_crossing(mids, c_bin):.1f} kt")
    c_gs = curve_at(beta, keep, mids, [hw_med] * len(mids), gss)
    L.append(f"  Spline fit, headwind at its median, gust spread at the bin means: 50% point {first_crossing(mids, c_gs):.1f} kt")
    c_hw = curve_at(beta, keep, mids, hws, [gs_med] * len(mids))
    L.append(f"  Spline fit, gust spread at its median, headwind at the bin means: 50% point {first_crossing(mids, c_hw):.1f} kt")
    L.append(f"  Observed (model-free on the same 2 kt bins, centers): 50% point {first_crossing(mids, obs):.1f} kt")
    # crosswind-only spline: should reproduce the model-free curve
    X = np.array([[1.0] + qc.spline(r["xw"]) for r in fit_rows])
    y = np.array([r["piston"] for r in fit_rows], dtype=float)
    off = np.log(np.array([r["base_piston"] for r in fit_rows]))
    b1, _ = qc.poisson_fit(X, y, off, np.arange(len(y)))
    c1 = np.exp(np.array([[1.0] + qc.spline(x) for x in grid]) @ b1)
    L.append(f"  Spline in crosswind only (no headwind or gust terms): 50% point {first_crossing(grid, c1):.1f} kt")
    L.append("  Model-free limit within strata (hours split by gust spread and headwind):")
    for name, f in (("gust spread under 3 kt", lambda r: r["gust_spread"] < 3), ("gust spread 3 to 8 kt", lambda r: 3 <= r["gust_spread"] < 8),
                    ("gust spread 8 kt or more", lambda r: r["gust_spread"] >= 8),
                    (f"gust spread at or below the median ({gs_med:.1f} kt)", lambda r: r["gust_spread"] <= gs_med),
                    ("headwind under 3 kt", lambda r: r["hw"] < 3), ("headwind 3 to 8 kt", lambda r: 3 <= r["hw"] < 8),
                    ("headwind 8 kt or more", lambda r: r["hw"] >= 8),
                    ("total wind under 15 kt", lambda r: r["speed"] < 15)):
        res = qc.empirical_limit([r for r in rows if f(r)], "piston", f"    {name}")
        L.append(res[0])
        L.append("  " + res[1])
    text = "\n".join(L)
    open(OUT, "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
