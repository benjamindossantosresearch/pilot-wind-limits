#!/usr/bin/env python3
"""
capture_weather.py

Does the share of tower-counted operations that the ADS-B archive captures
change with the weather? Q1a compares activity against each airport's normal
demand, so a constant capture rate cancels out, but a capture rate that moves
with wind would bias the drop-off curve.

Rules (fixed before running, see notes/decisions.md, 2026-10-02):
    unit        airport-day with at least MIN_TOWER_OPS tower operations
    capture     detected operations / tower operations (tower_compare.py daily.csv)
    outages     capture below OUTAGE_CAPTURE: counted, reported, excluded
    weather     the airport's METARs during tower hours, the report nearest each
                mid-hour: mean sustained wind, peak gust, mean best-runway
                crosswind, VMC share (ceiling at least 3,000 ft or none,
                visibility at least 5 SM, no precipitation), precipitation share
    model       log(capture) ~ wind + VMC share + precipitation share
                + airport-by-quarter fixed effects + weekday fixed effects,
                weighted by tower operations, HC1 robust standard errors
    pass        10 kt more mean wind changes capture by no more than 5 percent,
                95 percent interval inside plus or minus 10 percent

    python3 capture_weather.py tower_compare_full/daily.csv

Writes capture_weather/days.csv and capture_weather/summary.txt.
"""

import bisect
import csv
import datetime as dt
import math
import os
import sys
from collections import defaultdict

import numpy as np

import adsb_airport_coverage as cov
import runway_use as ru
import tower_compare as tc
import wind_activity as wa

MIN_TOWER_OPS = 30
OUTAGE_CAPTURE = 0.2
WELL_COVERED = ("BED", "BDR", "HVN", "LWM", "OWD")
WIND_BANDS = [(0, 5), (5, 8), (8, 11), (11, 14), (14, 99)]


def daily_weather(station, apt, dates):
    """Per local date: tower-hours weather summary from the station's METARs."""
    obs = []
    for path in sorted(__import__("glob").glob(os.path.join(cov.WEATHER_DIR, f"{station}_metar_*.csv"))):
        obs += wa.load_metars(path)
    obs.sort(key=lambda o: o["t"])
    seen, uniq = set(), []
    for o in obs:
        if o["t"] not in seen:
            seen.add(o["t"])
            uniq.append(o)
    times = [o["t"] for o in uniq]
    ends = ru.runway_ends(apt)
    out = {}
    for ds in dates:
        d = dt.date.fromisoformat(ds)
        opening, closing = tc.TOWER_HOURS[apt.name](d)
        t = tc.local_ts(d, opening)
        t_close = tc.local_ts(d, closing)
        hours = []
        while t < t_close:
            mid = dt.datetime.fromtimestamp(t + 1800, dt.timezone.utc)
            i = bisect.bisect_left(times, mid)
            cand = [uniq[j] for j in (i - 1, i) if 0 <= j < len(uniq)]
            o = min(cand, key=lambda c: abs((c["t"] - mid).total_seconds()), default=None)
            if o is not None and abs((o["t"] - mid).total_seconds()) <= 40 * 60 and o["sknt"] is not None:
                hours.append(o)
            t += 3600
        if len(hours) < 6:
            continue
        vmc = [(h["ceiling"] is None or h["ceiling"] >= 3000) and h["vis"] is not None and h["vis"] >= 5 and not h["precip"]
               for h in hours]
        xws = [wa.best_crosswind(h["drct"], h["sknt"], ends) for h in hours]
        xws = [x for x in xws if x is not None]
        out[ds] = {
            "wind_mean": sum(h["sknt"] for h in hours) / len(hours),
            "gust_max": max((h["gust"] or 0) for h in hours),
            "xw_mean": sum(xws) / len(xws) if xws else None,
            "vmc_share": sum(vmc) / len(hours),
            "precip_share": sum(h["precip"] for h in hours) / len(hours),
        }
    return out


def ols_hc1(X, y, w):
    """Weighted least squares with HC1 robust standard errors."""
    sw = np.sqrt(w)
    Xw, yw = X * sw[:, None], y * sw
    XtX_inv = np.linalg.pinv(Xw.T @ Xw)
    beta = XtX_inv @ Xw.T @ yw
    resid = yw - Xw @ beta
    n, k = Xw.shape
    meat = (Xw * resid[:, None]).T @ (Xw * resid[:, None])
    cov_b = XtX_inv @ meat @ XtX_inv * n / max(n - np.linalg.matrix_rank(Xw), 1)
    return beta, np.sqrt(np.diag(cov_b))


def fit(rows, wind_key):
    rows = [r for r in rows if r[wind_key] is not None]
    groups = sorted({(r["facility"], r["quarter"]) for r in rows})
    gidx = {g: i for i, g in enumerate(groups)}
    weekdays = list(range(1, 7))  # Monday is the base
    k = 3 + len(groups) + len(weekdays)
    X = np.zeros((len(rows), k))
    for n, r in enumerate(rows):
        X[n, 0] = r[wind_key] / 10.0
        X[n, 1] = r["vmc_share"]
        X[n, 2] = r["precip_share"]
        X[n, 3 + gidx[(r["facility"], r["quarter"])]] = 1.0
        wd = dt.date.fromisoformat(r["date"]).weekday()
        if wd in weekdays:
            X[n, 3 + len(groups) + weekdays.index(wd)] = 1.0
    y = np.array([math.log(r["capture"]) for r in rows])
    w = np.array([r["tower_ops"] for r in rows], dtype=float)
    beta, se = ols_hc1(X, y, w)
    pct = lambda b: 100 * (math.exp(b) - 1)
    return {"n": len(rows), "wind": (pct(beta[0]), pct(beta[0] - 1.96 * se[0]), pct(beta[0] + 1.96 * se[0])),
            "vmc": (pct(beta[1]), pct(beta[1] - 1.96 * se[1]), pct(beta[1] + 1.96 * se[1])),
            "precip": (pct(beta[2]), pct(beta[2] - 1.96 * se[2]), pct(beta[2] + 1.96 * se[2]))}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    daily = list(csv.DictReader(open(sys.argv[1])))
    by_fac = defaultdict(list)
    for r in daily:
        by_fac[r["facility"]].append(r)
    rows, outages, small = [], defaultdict(int), defaultdict(int)
    for fac, rs in sorted(by_fac.items()):
        apt = tc.make_airport("K" + fac)
        wx = daily_weather(fac, apt, [r["date"] for r in rs])
        for r in rs:
            tw, de = int(r["tower_ops"]), int(r["detected_ops"])
            if tw < MIN_TOWER_OPS:
                small[fac] += 1
                continue
            cap = de / tw
            if cap < OUTAGE_CAPTURE:
                outages[fac] += 1
                continue
            if r["date"] not in wx:
                continue
            d = dt.date.fromisoformat(r["date"])
            rows.append({"facility": fac, "date": r["date"], "quarter": f"{d.year}Q{(d.month - 1) // 3 + 1}",
                         "tower_ops": tw, "detected_ops": de, "capture": cap, **wx[r["date"]]})

    os.makedirs("capture_weather", exist_ok=True)
    with open("capture_weather/days.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    lines = [f"Airport-days used: {len(rows):,} (excluded: fewer than {MIN_TOWER_OPS} tower ops "
             f"{sum(small.values()):,}, archive outages (capture < {OUTAGE_CAPTURE}) {sum(outages.values()):,})",
             "Outages by airport: " + ", ".join(f"{k} {v}" for k, v in sorted(outages.items())), ""]

    lines.append("Capture by mean wind during tower hours, relative to the same airport's 0-4 kt days")
    lines.append("  airport  " + "  ".join(f"{a}-{b - 1 if b < 99 else '+':>2} kt".rjust(10) for a, b in WIND_BANDS))
    for fac in sorted({r["facility"] for r in rows}):
        rs = [r for r in rows if r["facility"] == fac]
        cells, base = [], None
        for a, b in WIND_BANDS:
            g = [r for r in rs if a <= r["wind_mean"] < b]
            if len(g) < 10:
                cells.append(f"{'n<10':>10}")
                continue
            ratio = sum(r["detected_ops"] for r in g) / sum(r["tower_ops"] for r in g)
            base = ratio if base is None and a == 0 else base
            cells.append(f"{ratio / base if base else float('nan'):6.3f} ({len(g):3d})" if base else f"{ratio:6.3f} ({len(g):3d})")
        lines.append(f"  {fac:7s}  " + "  ".join(cells))
    lines.append("  (cells: capture relative to calm days, with the number of days)")
    lines.append("")

    for label, facs in (("Well-covered airports (" + ", ".join(WELL_COVERED) + ")", WELL_COVERED),
                        ("All 12 airports", None)):
        sel = [r for r in rows if facs is None or r["facility"] in facs]
        for key, name in (("wind_mean", "mean wind"), ("xw_mean", "mean best-runway crosswind")):
            res = fit(sel, key)
            wv, vv, pv = res["wind"], res["vmc"], res["precip"]
            verdict = "PASS" if abs(wv[0]) <= 5 and -10 <= wv[1] and wv[2] <= 10 else "FAIL"
            lines.append(f"{label}, {name}: {res['n']:,} airport-days")
            lines.append(f"  capture change per 10 kt {name}: {wv[0]:+.1f}% (95% CI {wv[1]:+.1f} to {wv[2]:+.1f})  -> {verdict}")
            lines.append(f"  all-VMC day vs no-VMC day: {vv[0]:+.1f}% ({vv[1]:+.1f} to {vv[2]:+.1f}); "
                         f"all-precipitation day: {pv[0]:+.1f}% ({pv[1]:+.1f} to {pv[2]:+.1f})")
        lines.append("")
    text = "\n".join(lines)
    with open("capture_weather/summary.txt", "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
