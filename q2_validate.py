#!/usr/bin/env python3
"""
q2_validate.py

Measurement checks for Q2 (notes/q2_measures.md, amendments 2026-10-02, items 2
and 3). None of these look at how piston GA performance changes with wind.
They ask whether the instrument changes with wind:

  1. Vertical: true height from barometric altitude against GNSS geometric
     height at the 300 ft gate, from independent sensors. Spread by gust band
     and a day-clustered slope against gust spread and wind speed.
  2. Descent rate: barometric against geometric vertical rate at the gate.
  3. Position accuracy: NACp at the gate by group and wind band.
  4. Measurability: share of approaches measurable at 300 ft by crosswind and
     gust band (a coverage drop in wind must not pass as better performance).
  5. Machine-flown control group: jets on straight-in approaches, and the
     subset with autopilot and approach modes reported at the gate. Their
     criterion ratios against crosswind and gust estimate the floor that comes
     from measurement and physics rather than piloting.

    python3 q2_validate.py q2/approaches.csv

Writes q2_validation/summary.txt.
"""

import csv
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

XW_BANDS = [(0, 5), (5, 10), (10, 15), (15, 99)]
GUST_BANDS = [(0, 0.5), (0.5, 5), (5, 10), (10, 99)]
CRITS = ("s", "g_c1", "g_c2a", "g_c3", "g_c4", "g_c5b", "b_c1", "b_c2a", "b_c3", "b_c4")


def windows():
    w = json.load(open("q1a/windows.json"))
    w.update(json.load(open("q1a/windows_untowered.json")))
    return w


def in_window(r, w):
    s, e = w.get(r["airport"]), w.get(r["airport"] + "_exclude_from")
    return bool(s) and s <= r["date"] <= "2026-09-30" and not (e and r["date"] >= e)


def f(r, k):
    v = r.get(k)
    return float(v) if v not in (None, "") else None


def band_label(b):
    a, z = b
    return f"{a:g}+" if z >= 99 else f"{a:g}-{z:g}"


def ols_cluster(X, y, clusters):
    """OLS with cluster-robust (CR1) standard errors."""
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    uniq, inv = np.unique(clusters, return_inverse=True)
    S = np.zeros((len(uniq), X.shape[1]))
    np.add.at(S, inv, X * e[:, None])
    G, n, k = len(uniq), len(y), X.shape[1]
    adj = G / max(G - 1, 1) * (n - 1) / max(n - k, 1)
    V = XtX_inv @ (S.T @ S) @ XtX_inv * adj
    return beta, np.sqrt(np.diag(V))


def slope_table(rows, ykey, xkeys, fe_key, label):
    """y on x variables with fixed effects for fe_key, day-clustered."""
    rows = [r for r in rows if f(r, ykey) is not None and all(f(r, k) is not None for k in xkeys)]
    if len(rows) < 100:
        return [f"  {label}: too few rows ({len(rows)})"]
    fes = sorted({r[fe_key] for r in rows})
    fidx = {v: i for i, v in enumerate(fes)}
    X = np.zeros((len(rows), len(xkeys) + len(fes)))
    for n, r in enumerate(rows):
        for j, k in enumerate(xkeys):
            X[n, j] = f(r, k)
        X[n, len(xkeys) + fidx[r[fe_key]]] = 1.0
    y = np.array([f(r, ykey) for r in rows])
    cl = np.array([f"{r['airport']}|{r['date']}" for r in rows])
    beta, se = ols_cluster(X, y, cl)
    parts = [f"{k} {10 * beta[j]:+.3f} per 10 kt (95% CI {10 * (beta[j] - 1.96 * se[j]):+.3f} to {10 * (beta[j] + 1.96 * se[j]):+.3f})"
             for j, k in enumerate(xkeys)]
    return [f"  {label} (n={len(rows):,}): " + "; ".join(parts)]


def dist_by_band(rows, key, bkey, bands, label, fmt="{:.2f}"):
    lines = [f"  {label}, by {bkey} band (kt): median / p90 / share above 1 / n"]
    for b in bands:
        v = np.array([f(r, key) for r in rows if f(r, key) is not None and f(r, bkey) is not None and b[0] <= f(r, bkey) < b[1]])
        if len(v) < 20:
            lines.append(f"    {band_label(b):>6s}: n<20")
            continue
        lines.append(f"    {band_label(b):>6s}: {fmt.format(np.median(v))} / {fmt.format(np.percentile(v, 90))} / {100 * (v > 1).mean():.1f}% / {len(v):,}")
    return lines


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    w = windows()
    allrows = [r for r in csv.DictReader(open(sys.argv[1])) if in_window(r, w) and r["vmc"] == "1"]
    ok = [r for r in allrows if r["status"] == "ok"]
    for r in allrows:
        r["month"] = r["date"][:7]
        r["apt_month"] = f"{r['airport']}|{r['month']}"
    L = [f"Q2 measurement checks: {len(allrows):,} approaches (VMC, study airports in their windows), {len(ok):,} measurable at 300 ft", ""]

    # 1. vertical
    L.append("1. True height (barometric, METAR altimeter, cold-temperature corrected) minus GNSS geometric height at the gate, ft")
    for grp in ("piston", "jet"):
        g = [r for r in ok if r["group"] == grp]
        hs = defaultdict(int)
        for r in g:
            hs[r["height_source"]] += 1
        L.append(f"  {grp} height source: " + ", ".join(f"{k} {100 * v / len(g):.1f}%" for k, v in sorted(hs.items())))
    for grp in ("piston", "jet"):
        # independent sensors only: approaches whose heights come from the barometric altitude
        rows = [r for r in ok if r["group"] == grp and r["height_source"] == "baro" and f(r, "hat_true_minus_geom_ft") is not None]
        if not rows:
            continue
        med = defaultdict(list)
        for r in rows:
            med[r["apt_month"]].append(f(r, "hat_true_minus_geom_ft"))
        med = {k: float(np.median(v)) for k, v in med.items()}
        for r in rows:
            r["dz_resid"] = f(r, "hat_true_minus_geom_ft") - med[r["apt_month"]]
            r["abs_dz_resid"] = abs(r["dz_resid"])
        v = np.array([r["dz_resid"] for r in rows])
        L.append(f"  {grp}: n={len(rows):,}, share of measurable approaches (barometric heights) with GNSS height {len(rows) / max(1, sum(1 for r in ok if r['group'] == grp and r['height_source'] == 'baro')):.2f}; "
                 f"after removing each airport-month median: SD {v.std():.1f} ft, IQR {np.percentile(v, 75) - np.percentile(v, 25):.1f} ft, "
                 f"p5 {np.percentile(v, 5):.1f}, p95 {np.percentile(v, 95):.1f}")
        L.append(f"  {grp}: absolute residual by gust spread band: " + ", ".join(
            f"{band_label(b)} kt {np.median([r['abs_dz_resid'] for r in rows if b[0] <= f(r, 'gust_spread') < b[1]] or [float('nan')]):.1f} ft"
            for b in GUST_BANDS))
        L += slope_table(rows, "abs_dz_resid", ["gust_spread", "wind_kt"], "apt_month", f"{grp}: absolute residual (ft) on gust spread and wind speed, airport-month effects")
    L.append("")

    # 2. descent rate
    L.append("2. Barometric minus geometric vertical rate at the gate, fpm")
    for grp in ("piston", "jet"):
        rows = [r for r in ok if r["group"] == grp and f(r, "vr_baro") is not None and f(r, "vr_geom") is not None]
        if not rows:
            L.append(f"  {grp}: no approaches report both rates")
            continue
        for r in rows:
            r["dvr"] = f(r, "vr_baro") - f(r, "vr_geom")
            r["abs_dvr"] = abs(r["dvr"])
        v = np.array([r["dvr"] for r in rows])
        L.append(f"  {grp}: n={len(rows):,}, mean {v.mean():+.0f}, SD {v.std():.0f}, IQR {np.percentile(v, 75) - np.percentile(v, 25):.0f}")
        L.append(f"  {grp}: absolute difference by gust spread band: " + ", ".join(
            f"{band_label(b)} kt {np.median([r['abs_dvr'] for r in rows if b[0] <= f(r, 'gust_spread') < b[1]] or [float('nan')]):.0f}"
            for b in GUST_BANDS))
        L += slope_table(rows, "abs_dvr", ["gust_spread", "wind_kt"], "apt_month", f"{grp}: absolute difference (fpm) on gust spread and wind speed")
    L.append("")

    # 3. NACp
    L.append("3. Position accuracy (NACp) at the gate. NACp 9 means under 30 m (98 ft), 10 under 10 m, 11 under 3 m. C1 tolerance is 200 ft.")
    for grp in ("piston", "jet"):
        rows = [r for r in ok if r["group"] == grp]
        vals = defaultdict(int)
        for r in rows:
            vals[r["nacp"] or "none"] += 1
        tot = len(rows)
        L.append(f"  {grp}: " + ", ".join(f"NACp {k}: {100 * v / tot:.1f}%" for k, v in sorted(vals.items(), key=lambda x: str(x[0]))))
        L.append(f"  {grp}: share NACp 9 or better by crosswind band: " + ", ".join(
            f"{band_label(b)} kt {100 * np.mean([(r['nacp'] or '0').isdigit() and int(r['nacp'] or 0) >= 9 for r in rows if f(r, 'xw_kt') is not None and b[0] <= f(r, 'xw_kt') < b[1]] or [float('nan')]):.1f}%"
            for b in XW_BANDS))
    L.append("")

    # 4. measurability
    L.append("4. Share of piston approaches measurable at 300 ft (status ok), by wind at the lowest point")
    pis = [r for r in allrows if r["group"] == "piston"]
    for key, bands in (("xw_low_kt", XW_BANDS), ("gust_spread", GUST_BANDS)):
        cells = []
        for b in bands:
            g = [r for r in pis if f(r, key) is not None and b[0] <= f(r, key) < b[1]]
            if len(g) >= 20:
                cells.append(f"{band_label(b)} kt {100 * np.mean([r['status'] == 'ok' for r in g]):.1f}% (n={len(g):,})")
        L.append(f"  by {key}: " + ", ".join(cells))
    by_apt = defaultdict(list)
    for r in pis:
        by_apt[r["airport"]].append(r)
    for a, g in sorted(by_apt.items()):
        cells = []
        for b in XW_BANDS:
            gg = [r for r in g if f(r, "xw_low_kt") is not None and b[0] <= f(r, "xw_low_kt") < b[1]]
            if len(gg) >= 20:
                cells.append(f"{band_label(b)} {100 * np.mean([r['status'] == 'ok' for r in gg]):.0f}%")
        L.append(f"    {a}: " + ", ".join(cells))
    for r in pis:
        r["measurable"] = 1.0 if r["status"] == "ok" else 0.0
    L += slope_table(pis, "measurable", ["xw_low_kt", "gust_spread"], "apt_month", "piston: measurable (0/1) on crosswind and gust spread, airport-month effects (linear probability)")
    L.append("")

    # 5. control group
    L.append("5. Machine-flown control group: criterion ratios against wind")
    jets = [r for r in ok if r["group"] == "jet" and r["straight_in"] == "yes"]
    coupled = [r for r in jets if r["coupled"] == "1"]
    L.append(f"  jets, straight-in, measurable: {len(jets):,} (autopilot and approach modes at the gate: {len(coupled):,})")
    for label, rows in (("jets straight-in", jets), ("jets coupled", coupled)):
        if len(rows) < 100:
            L.append(f"  {label}: too few")
            continue
        for k in ("s", "b_c4", "g_c5b", "b_c1", "b_c3"):
            L += dist_by_band(rows, k, "xw_kt", XW_BANDS, f"{label} {k}")
        L += dist_by_band(rows, "s", "gust_spread", GUST_BANDS, f"{label} s")
        for k in ("s", "g_c4", "b_c4", "g_c5b", "b_c1", "b_c3"):
            L += slope_table(rows, k, ["xw_kt", "hw_kt", "gust_spread"], "airport", f"{label} {k} on crosswind, headwind, gust spread, airport effects")
    L.append("")
    os.makedirs("q2_validation", exist_ok=True)
    text = "\n".join(L)
    open("q2_validation/summary.txt", "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
