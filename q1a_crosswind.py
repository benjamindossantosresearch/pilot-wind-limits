#!/usr/bin/env python3
"""
q1a_crosswind.py

Q1a: how arrival activity falls off with crosswind, headwind, and gusts,
relative to normal demand. Rules are pre-registered in notes/decisions.md
(2026-10-02, "Q1a analysis" and "Q1a backtest").

    python3 q1a_crosswind.py --mode window      # each airport's logged window, season-year baselines
    python3 q1a_crosswind.py --mode backtest    # full 2023-02-16 to 2026-09-30, quarter baselines

Inputs: q1a/hourly_arrivals.csv (q1a_counts.py), q1a/windows.json (window
start per airport), tower_compare_full/daily.csv (outage days), weather/onemin/
(one-minute ASOS), weather/*_metar_*.csv (VMC and wind fallback).

Outputs in q1a/<mode>/: hours.csv (every analyzed airport-hour with weather,
baseline, ratio) and summary.txt.
"""

import argparse
import bisect
import csv
import datetime as dt
import glob
import json
import math
import os
import statistics
from collections import defaultdict

import numpy as np

import adsb_airport_coverage as cov
import runway_use as ru
import tower_compare as tc
import wind_activity as wa
import wind_qc

END = "2026-09-30"
FULL_START = "2023-02-16"
MIN_CELL_HOURS = 8
# Runways left out of the best-runway crosswind: not usable by the study fleet in practice.
# TAN 04/22 is a 1,034 ft turf-gravel strip (NASR APT_RWY) with almost no detected use (post-hoc fix, 2026-10-02).
UNUSABLE_ENDS = {"TAN": {"04", "22"}}
MIN_ONEMIN = 30
BANDS = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 99)]
BOOT = 1000
BOOT_MODEL = 200
GROUPS = ("piston", "fleet", "private")
RNG = np.random.default_rng(20261002)


def season_key(d, mode):
    if mode == "backtest":
        return f"{d.year}Q{(d.month - 1) // 3 + 1}"
    y = d.year + 1 if d.month == 12 else d.year
    s = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA"}.get(d.month, "SON")
    return f"{y}{s}"


def components(drct, spd, ends):
    """(crosswind, headwind, course of the chosen end) for the runway end with the least crosswind among ends with headwind >= 0."""
    if spd is None:
        return None
    if spd == 0:
        return 0.0, 0.0, None
    if drct is None:
        return None
    best = None
    for e in ends:
        th = math.radians(drct - e.course)
        hw, xw = spd * math.cos(th), abs(spd * math.sin(th))
        if hw >= 0 and (best is None or xw < best[0]):
            best = (xw, hw, e.course)
    return best


def load_onemin(station):
    data = {}
    for path in glob.glob(os.path.join(cov.WEATHER_DIR, "onemin", f"{station}_*.csv")):
        with open(path) as f:
            for r in csv.DictReader(f):
                try:
                    t = dt.datetime.strptime(r["valid(UTC)"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                except (KeyError, ValueError):
                    continue
                num = lambda k: float(r[k]) if r.get(k) not in (None, "", "M") else None
                data[int(t.timestamp()) // 60] = (num("drct"), num("sknt"), num("gust_drct"), num("gust_sknt"))
    return data


def load_metar_obs(station):
    obs = []
    for path in sorted(glob.glob(os.path.join(cov.WEATHER_DIR, f"{station}_metar_*.csv"))):
        obs += wa.load_metars(path)
    obs.sort(key=lambda o: o["t"])
    seen, uniq = set(), []
    for o in obs:
        if o["t"] not in seen:
            seen.add(o["t"])
            uniq.append(o)
    return uniq, [o["t"] for o in uniq]


def hour_weather(t0, onemin, metars, mtimes, ends):
    """Weather for the local hour starting at epoch t0."""
    mid = dt.datetime.fromtimestamp(t0 + 1800, dt.timezone.utc)
    i = bisect.bisect_left(mtimes, mid)
    cand = [metars[j] for j in (i - 1, i) if 0 <= j < len(metars)]
    o = min(cand, key=lambda c: abs((c["t"] - mid).total_seconds()), default=None)
    if o is None or abs((o["t"] - mid).total_seconds()) > 40 * 60:
        return None
    vmc = ((o["ceiling"] is None or o["ceiling"] >= 3000) and o["vis"] is not None and o["vis"] >= 5 and not o["precip"])
    xs, hs, sp, gx, gmax = [], [], [], [], 0.0
    m0 = int(t0) // 60
    for m in range(m0, m0 + 60):
        rec = onemin.get(m)
        if not rec or rec[1] is None:
            continue
        c = components(rec[0], rec[1], ends)
        if c is None:
            continue
        xs.append(c[0])
        hs.append(c[1])
        sp.append(rec[1])
        if rec[3] is not None:
            gmax = max(gmax, rec[3])
            if rec[2] is not None and c[2] is not None:
                gx.append(abs(rec[3] * math.sin(math.radians(rec[2] - c[2]))))
    if len(xs) >= MIN_ONEMIN:
        mean_sp = sum(sp) / len(sp)
        return {"vmc": vmc, "wind_src": "onemin", "xw": sum(xs) / len(xs), "hw": sum(hs) / len(hs),
                "speed": mean_sp, "gust_spread": max(0.0, gmax - mean_sp) if gmax else 0.0,
                "gust_xw": max(gx) if gx else sum(xs) / len(xs)}
    c = components(o["drct"], o["sknt"], ends)
    if c is None:
        return None
    gxw = c[0]
    if o["gust"] and o["drct"] is not None and c[2] is not None:
        gxw = abs(o["gust"] * math.sin(math.radians(o["drct"] - c[2])))
    return {"vmc": vmc, "wind_src": "metar", "xw": c[0], "hw": c[1], "speed": o["sknt"],
            "gust_spread": max(0.0, (o["gust"] or 0) - o["sknt"]) if o["gust"] else 0.0, "gust_xw": gxw}


def outage_days(mode, windows):
    """Airport -> set of local dates excluded as archive outages (tower-count capture)."""
    path = "tower_compare_full/daily.csv"
    if not os.path.exists(path):
        return {}
    by = defaultdict(list)
    for r in csv.DictReader(open(path)):
        tw, de = int(r["tower_ops"]), int(r["detected_ops"])
        if tw >= 30:
            by[r["facility"]].append((r["date"], de / tw))
    out = {}
    for fac, rows in by.items():
        if mode == "window":
            start = windows.get(fac)
            rows = [x for x in rows if start and x[0] >= start]
            med = statistics.median([c for _, c in rows]) if rows else None
            out[fac] = {d for d, c in rows if med and c < 0.5 * med}
        else:
            q = defaultdict(list)
            for d, c in rows:
                q[season_key(dt.date.fromisoformat(d), "backtest")].append((d, c))
            out[fac] = set()
            for _, g in q.items():
                med = statistics.median([c for _, c in g])
                out[fac] |= {d for d, c in g if c < 0.5 * med}
    return out


def poisson_fit(X, y, offset, clusters):
    """Poisson GLM with offset by IRLS. Returns beta and cluster-robust covariance."""
    beta = np.zeros(X.shape[1])
    beta[0] = math.log(max(y.mean(), 1e-6) / max(np.exp(offset).mean(), 1e-6))
    for _ in range(50):
        eta = np.clip(X @ beta + offset, -30, 30)
        mu = np.exp(eta)
        z = eta - offset + (y - mu) / mu
        W = mu
        XtWX = X.T @ (X * W[:, None])
        new = np.linalg.solve(XtWX, X.T @ (W * z))
        if np.max(np.abs(new - beta)) < 1e-8:
            beta = new
            break
        beta = new
    mu = np.exp(X @ beta + offset)
    bread = np.linalg.inv(X.T @ (X * mu[:, None]))
    score = X * (y - mu)[:, None]
    uniq, inv = np.unique(clusters, return_inverse=True)
    S = np.zeros((len(uniq), X.shape[1]))
    np.add.at(S, inv, score)
    G = len(uniq)
    meat = S.T @ S * G / max(G - 1, 1)
    return beta, bread @ meat @ bread


def model_block(rows, group, label):
    """Pooled Poisson model, rate ratios per 5 kt, revealed limits with day-cluster bootstrap."""
    rows = [r for r in rows if r[f"base_{group}"] > 0]
    if len(rows) < 200:
        return [f"{label}: too few hours ({len(rows)})"]
    X = np.array([[1.0, r["xw"], r["hw"], r["gust_spread"]] for r in rows])
    y = np.array([r[group] for r in rows], dtype=float)
    off = np.log(np.array([r[f"base_{group}"] for r in rows]))
    cl = np.array([f"{r['airport']}|{r['local_date']}" for r in rows])
    beta, V = poisson_fit(X, y, off, cl)
    se = np.sqrt(np.diag(V))
    rr = lambda b: math.exp(5 * b)
    lines = [f"{label}: {len(rows):,} VMC airport-hours, {int(y.sum()):,} arrivals"]
    for k, name in ((1, "crosswind"), (2, "headwind"), (3, "gust spread")):
        lines.append(f"  rate ratio per 5 kt {name}: {rr(beta[k]):.3f} (95% CI {rr(beta[k] - 1.96 * se[k]):.3f} to {rr(beta[k] + 1.96 * se[k]):.3f})")
    # revealed limits (pre-registered): crosswind at which modeled activity falls to 50 and 75 percent
    # of normal demand, headwind and gust spread at their medians
    hw_med, gs_med = float(np.median(X[:, 2])), float(np.median(X[:, 3]))

    def limits(b):
        if b[1] >= 0:
            return float("inf"), float("inf")
        rest = b[0] + b[2] * hw_med + b[3] * gs_med
        return tuple(max(0.0, (math.log(p) - rest) / b[1]) for p in (0.5, 0.75))
    x50, x75 = limits(beta)
    uniq = np.unique(cl)
    idx = defaultdict(list)
    for i, c in enumerate(cl):
        idx[c].append(i)
    bs50, bs75 = [], []
    for _ in range(BOOT_MODEL):
        pick = RNG.choice(uniq, size=len(uniq), replace=True)
        ii = np.concatenate([idx[c] for c in pick])
        try:
            b, _ = poisson_fit(X[ii], y[ii], off[ii], np.arange(len(ii)))
        except np.linalg.LinAlgError:
            continue
        if not np.all(np.isfinite(b)):
            continue
        a, c = limits(b)
        bs50.append(a)
        bs75.append(c)
    q = lambda v, p: float(np.percentile([x for x in v if math.isfinite(x)] or [float("nan")], p))
    lines.append(f"  revealed limit, crosswind at 50% of normal demand (headwind {hw_med:.1f} kt, gust spread {gs_med:.1f} kt): "
                 f"{x50:.1f} kt (95% CI {q(bs50, 2.5):.1f} to {q(bs50, 97.5):.1f})")
    lines.append(f"  revealed limit, crosswind at 75% of normal demand: {x75:.1f} kt (95% CI {q(bs75, 2.5):.1f} to {q(bs75, 97.5):.1f})")
    # fit diagnostic (not pre-registered): observed against modeled activity by crosswind band
    mu = np.exp(X @ beta + off)
    base = np.exp(off)
    cells = []
    for a, b in BANDS:
        m = (X[:, 1] >= a) & (X[:, 1] < b)
        if m.sum() >= 20:
            cells.append(f"{a}-{b - 1 if b < 99 else '+'} kt obs {y[m].sum() / base[m].sum():.2f} model {mu[m].sum() / base[m].sum():.2f}")
    lines.append("  fit check by crosswind band: " + ", ".join(cells))
    return lines


KNOTS = (5.0, 10.0, 15.0)
FINE = [(a, a + 2) for a in range(0, 24, 2)]


def spline(x):
    """Piecewise-linear basis: x and max(0, x - k) for each knot."""
    return [x] + [max(0.0, x - k) for k in KNOTS]


def flexible_block(rows, group, label):
    """Post-hoc (not pre-registered, added after the fit check failed): Poisson model with piecewise-linear
    splines in crosswind, headwind, and gust spread (knots 5, 10, 15 kt). Revealed limit solved on a 0.1 kt grid
    with headwind and gust spread at their medians."""
    rows = [r for r in rows if r[f"base_{group}"] > 0]
    if len(rows) < 200:
        return [f"{label}: too few hours ({len(rows)})"]
    X = np.array([[1.0] + spline(r["xw"]) + spline(r["hw"]) + spline(r["gust_spread"]) for r in rows])
    y = np.array([r[group] for r in rows], dtype=float)
    off = np.log(np.array([r[f"base_{group}"] for r in rows]))
    cl = np.array([f"{r['airport']}|{r['local_date']}" for r in rows])
    # a knot term is kept only if at least 20 hours lie beyond the knot
    keep = np.array([True] + [(X[:, j] > 0).sum() >= 20 for j in range(1, X.shape[1])])
    xmax = float(np.sort(X[:, 1])[-20])
    hw_med, gs_med = float(np.median(X[:, 5])), float(np.median(X[:, 9]))
    grid = np.arange(0, xmax + 0.05, 0.1)
    G = np.array([[1.0] + spline(x) + spline(hw_med) + spline(gs_med) for x in grid])[:, keep]
    X = X[:, keep]

    def limits(b):
        curve = np.exp(G @ b)
        out = []
        for p in (0.5, 0.75):
            below = np.nonzero(curve <= p)[0]
            out.append(float(grid[below[0]]) if len(below) else float("inf"))
        return out, curve
    beta, _ = poisson_fit(X, y, off, cl)
    (x50, x75), curve = limits(beta)
    uniq = np.unique(cl)
    idx = defaultdict(list)
    for i, c in enumerate(cl):
        idx[c].append(i)
    bs50, bs75 = [], []
    for _ in range(BOOT_MODEL):
        pick = RNG.choice(uniq, size=len(uniq), replace=True)
        ii = np.concatenate([idx[c] for c in pick])
        try:
            b, _ = poisson_fit(X[ii], y[ii], off[ii], np.arange(len(ii)))
        except np.linalg.LinAlgError:
            continue
        if not np.all(np.isfinite(b)):
            continue
        (a, c), _ = limits(b)
        bs50.append(a)
        bs75.append(c)
    fmt = lambda v: f"{v:.1f} kt" if math.isfinite(v) else f"not reached within observed range (to {xmax:.1f} kt)"
    ci = lambda v: (f"95% CI {np.percentile(v, 2.5):.1f} to {np.percentile(v, 97.5):.1f}" if np.mean(np.isfinite(v)) >= 0.975
                    else f"not reached in {100 * np.mean(~np.isfinite(v)):.0f}% of resamples")
    mu, base = np.exp(X @ beta + off), np.exp(off)
    cells = []
    for a, b in BANDS:
        m = (X[:, 1] >= a) & (X[:, 1] < b)
        if m.sum() >= 20:
            cells.append(f"{a}-{b - 1 if b < 99 else '+'} kt obs {y[m].sum() / base[m].sum():.2f} model {mu[m].sum() / base[m].sum():.2f}")
    return [f"{label} [post-hoc spline model]: {len(rows):,} hours, headwind {hw_med:.1f} kt, gust spread {gs_med:.1f} kt",
            f"  modeled activity / normal demand at crosswind 0, 5, 10, 15 kt: "
            + ", ".join(f"{curve[min(int(round(x * 10)), len(curve) - 1)]:.2f}" for x in (0, 5, 10, 15) if x <= xmax),
            f"  revealed limit 50%: {fmt(x50)} ({ci(np.array(bs50))})",
            f"  revealed limit 75%: {fmt(x75)} ({ci(np.array(bs75))})",
            "  fit check by crosswind band: " + ", ".join(cells)]


def empirical_limit(rows, group, label, key="xw"):
    """Post-hoc: model-free revealed limit. Arrivals over normal demand (ratio of sums) in 2 kt bins of the
    hour's mean crosswind, first crossing of 50 and 75 percent by linear interpolation between bin centers,
    day-cluster bootstrap. Includes whatever headwind and gust come with that crosswind in practice."""
    rows = [r for r in rows if r[f"base_{group}"] > 0]
    days = defaultdict(lambda: np.zeros((len(FINE), 3)))
    for r in rows:
        for j, (a, b) in enumerate(FINE):
            if a <= r[key] < b:
                d = days[(r["airport"], r["local_date"])]
                d[j] += (r[group], r[f"base_{group}"], 1)
                break
    arr = np.array(list(days.values()))
    if not len(arr):
        return [f"{label}: no data"]
    mids = np.array([(a + b) / 2 for a, b in FINE])

    def crossing(tot):
        ok = tot[:, 2] >= 20
        ratio = np.where(ok, tot[:, 0] / np.maximum(tot[:, 1], 1e-9), np.nan)
        out = []
        for p in (0.5, 0.75):
            x = float("inf")
            for j in range(1, len(FINE)):
                if not ok[j]:
                    break
                if ratio[j] <= p:
                    x = mids[j - 1] + (ratio[j - 1] - p) / (ratio[j - 1] - ratio[j]) * (mids[j] - mids[j - 1]) if ratio[j - 1] > p else mids[j]
                    break
            out.append(x)
        return out, ratio
    (x50, x75), ratio = crossing(arr.sum(axis=0))
    boots = np.array([crossing(arr[RNG.integers(0, len(arr), len(arr))].sum(axis=0))[0] for _ in range(BOOT)])
    def show(v, bs):
        if not math.isfinite(v):
            return "not reached in bins with at least 20 hours"
        fin = bs[np.isfinite(bs)]
        tail = "" if len(fin) >= 0.975 * len(bs) else f", not reached in {100 * (1 - len(fin) / len(bs)):.0f}% of resamples"
        return f"{v:.1f} kt (95% CI {np.percentile(fin, 2.5):.1f} to {np.percentile(fin, 97.5):.1f}{tail})"
    curve = ", ".join(f"{a}-{b}: {r:.2f}" for (a, b), r in zip(FINE, ratio) if np.isfinite(r))
    return [f"{label} [post-hoc, model-free, {key}]: activity / normal demand by 2 kt bin: {curve}",
            f"  revealed limit 50%: {show(x50, boots[:, 0])}",
            f"  revealed limit 75%: {show(x75, boots[:, 1])}"]


def band_table(rows, key, group, label):
    lines = [f"{label}: arrivals / normal demand by {key} band (ratio of sums, day-cluster bootstrap 95% CI)"]
    lines.append("  airport   " + "  ".join(f"{(f'{a}-{b - 1}' if b < 99 else f'{a}+'):>22s}" for a, b in BANDS))
    airports = sorted({r["airport"] for r in rows}) + ["pooled"]
    for ap in airports:
        rs = [r for r in rows if (ap == "pooled" or r["airport"] == ap) and r[f"base_{group}"] > 0]
        cells = []
        for a, b in BANDS:
            g = [r for r in rs if a <= r[key] < b]
            if len(g) < 20:
                cells.append(f"{'n<20':>22s}")
                continue
            days = defaultdict(lambda: [0.0, 0.0])
            for r in g:
                k = (r["airport"], r["local_date"])
                days[k][0] += r[group]
                days[k][1] += r[f"base_{group}"]
            vals = np.array(list(days.values()))
            est = vals[:, 0].sum() / vals[:, 1].sum()
            n = len(vals)
            boots = []
            for _ in range(BOOT):
                s = vals[RNG.integers(0, n, n)]
                boots.append(s[:, 0].sum() / s[:, 1].sum())
            lo, hi = np.percentile(boots, [2.5, 97.5])
            cells.append(f"{est:5.2f} ({lo:4.2f}-{hi:4.2f}) n={len(g):5d}")
        lines.append(f"  {ap:8s}  " + "  ".join(cells))
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["window", "backtest"], required=True)
    ap.add_argument("--airports", default="BDR,HVN,BED,LWM,OWD")
    ap.add_argument("--windows", default="q1a/windows.json")
    ap.add_argument("--tag", default="", help="suffix for the output folder, q1a/<mode><tag>")
    args = ap.parse_args()
    airports = [a.strip().upper() for a in args.airports.split(",")]
    windows = json.load(open(args.windows))
    outages = outage_days(args.mode, windows)

    arrivals = defaultdict(dict)
    for r in csv.DictReader(open("q1a/hourly_arrivals.csv")):
        if r["airport"] in airports:
            arrivals[r["airport"]][(r["local_date"], int(r["hour"]))] = {g: int(r[g]) for g in GROUPS + ("all_fixed",)}

    rows, skipped = [], defaultdict(int)
    for apname in airports:
        apt = tc.make_airport("K" + apname)
        ends = [e for e in ru.runway_ends(apt) if e.name not in UNUSABLE_ENDS.get(apname, set())]
        onemin = load_onemin(apname)
        metars, mtimes = load_metar_obs(apname)
        onemin, _ = wind_qc.qc_onemin(onemin, [t.timestamp() for t in mtimes], [o["sknt"] for o in metars])
        start = windows.get(apname) if args.mode == "window" else FULL_START
        excl_end = windows.get(apname + "_exclude_from")
        if not start:
            skipped[f"{apname} no window"] += 1
            continue
        for (ld, h), c in arrivals[apname].items():
            if ld < start or ld > END or (excl_end and ld >= excl_end):
                continue
            if ld in outages.get(apname, set()):
                skipped["outage day"] += 1
                continue
            d = dt.date.fromisoformat(ld)
            t0 = dt.datetime(d.year, d.month, d.day, h, tzinfo=tc.LOCAL).timestamp()
            wx = hour_weather(t0, onemin, metars, mtimes, ends)
            if wx is None:
                skipped["no weather"] += 1
                continue
            if not wx["vmc"]:
                skipped["not VMC"] += 1
                continue
            rows.append({"airport": apname, "local_date": ld, "hour": h, "weekend": d.weekday() >= 5,
                         "season": season_key(d, args.mode), **c, **wx})

    cells = defaultdict(list)
    for r in rows:
        cells[(r["airport"], r["season"], r["weekend"], r["hour"])].append(r)
    kept = []
    for k, g in cells.items():
        if len(g) < MIN_CELL_HOURS:
            skipped["thin baseline cell (hours)"] += len(g)
            continue
        for grp in GROUPS:
            m = sum(r[grp] for r in g) / len(g)
            for r in g:
                r[f"base_{grp}"] = m
        kept.extend(g)
    rows = kept

    out_dir = os.path.join("q1a", args.mode + args.tag)
    os.makedirs(out_dir, exist_ok=True)
    fields = ["airport", "local_date", "hour", "weekend", "season", "wind_src", "xw", "hw", "speed", "gust_spread",
              "gust_xw"] + list(GROUPS) + ["all_fixed"] + [f"base_{g}" for g in GROUPS]
    with open(os.path.join(out_dir, "hours.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    lines = [f"Q1a {args.mode}: {len(rows):,} VMC airport-hours (08-18 local) at {', '.join(airports)}",
             "Windows: " + ", ".join(f"{a} from {windows.get(a)}" for a in airports) if args.mode == "window"
             else f"Full period {FULL_START} to {END}, quarter baselines",
             "Excluded: " + ", ".join(f"{k} {v:,}" for k, v in sorted(skipped.items())),
             "Wind source: " + ", ".join(f"{s} {sum(1 for r in rows if r['wind_src'] == s):,}" for s in ("onemin", "metar")),
             ""]
    lines += band_table(rows, "xw", "piston", "Piston GA, mean best-runway crosswind") + [""]
    lines += band_table(rows, "gust_xw", "piston", "Piston GA, peak gust crosswind") + [""]
    lines += band_table(rows, "hw", "piston", "Piston GA, mean headwind on that runway") + [""]
    for grp in GROUPS:
        lines += model_block(rows, grp, f"Poisson model, {grp}") + [""]
    for apname in airports:
        lines += model_block([r for r in rows if r["airport"] == apname], "piston", f"Poisson model, piston, {apname} only") + [""]
    lines += ["=" * 100, "POST-HOC (added 2026-10-02 after the pre-registered model failed its fit check above 10 kt; see notes/decisions.md)", ""]
    for grp in GROUPS:
        lines += empirical_limit(rows, grp, f"Model-free, {grp}") + [""]
    lines += empirical_limit(rows, "piston", "Model-free, piston", key="gust_xw") + [""]
    for apname in airports:
        lines += empirical_limit([r for r in rows if r["airport"] == apname], "piston", f"Model-free, piston, {apname} only") + [""]
    for grp in GROUPS:
        lines += flexible_block(rows, grp, f"Spline model, {grp}") + [""]
    for apname in airports:
        lines += flexible_block([r for r in rows if r["airport"] == apname], "piston", f"Spline model, piston, {apname} only") + [""]
    text = "\n".join(lines)
    with open(os.path.join(out_dir, "summary.txt"), "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
