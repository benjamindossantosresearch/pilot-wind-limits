#!/usr/bin/env python3
"""
q2_pattern_wind.py

Wind at pattern height from ADS-B ground speed in turns (notes/q2_measures.md,
amendment 3, "Wind at pattern height"). In a turn the airplane's airspeed is
nearly constant while its track sweeps through the wind, so ground speed rises
and falls with the wind component along the track:

    gs = TAS_j - W cos(track - wind_from)

Pooling every turning segment in one airport-hour, with one TAS per segment
(fixed effect) and one wind vector shared by all, gives the wind near pattern
altitude. Comparing it with the surface one-minute ASOS wind tests the 1/7
power-law profile that the estimated airspeed (C5a, C5b) relies on.

Segments: consecutive points 600 to 1,600 ft above the field, within 4 nm of
the airport, no gap over 20 s, at least 6 points, track sweeping at least 90
degrees, vertical rate under 800 fpm. An airport-hour needs 3 or more segments
and the fitted wind's standard error under 3 kt.

    python3 q2_pattern_wind.py --workers 32

Writes q2_pattern_wind/hours.csv and q2_pattern_wind/summary.txt.
"""

import argparse
import csv
import datetime as dt
import glob
import gzip
import json
import math
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import adsb_airport_coverage as cov
import q2_measures as qm
import tower_compare as tc

H_LO, H_HI = 600, 1600
MAX_NM = 4.0
MIN_PTS = 6
MIN_SWEEP = 90.0
MAX_VR = 800
MIN_SEGS = 3
MAX_SE = 3.0
REF_H_M = 10.0


def windows():
    w = json.load(open("q1a/windows.json"))
    w.update(json.load(open("q1a/windows_untowered.json")))
    return w


def segments(P, apt):
    t, gs, trk, h, vr = P["t"], P["gs"], P["trk"], P["agl_ind"], P["vr"]
    segs, cur = [], []
    for i in range(len(t)):
        ok = (h[i] is not None and H_LO <= h[i] <= H_HI and gs[i] is not None and trk[i] is not None
              and (vr[i] is None or abs(vr[i]) <= MAX_VR)
              and math.hypot(*cov.to_xy_nm(P["lat"][i], P["lon"][i], apt.lat, apt.lon)) <= MAX_NM)
        if ok and cur and t[i] - t[cur[-1]] > 20:
            segs.append(cur)
            cur = []
        if ok:
            cur.append(i)
        elif cur:
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    out = []
    for s in segs:
        if len(s) < MIN_PTS:
            continue
        # cumulative track sweep
        sweep, lo, hi = 0.0, 0.0, 0.0
        for a, b in zip(s, s[1:]):
            sweep += qm.sdiff(trk[b], trk[a])
            lo, hi = min(lo, sweep), max(hi, sweep)
        if hi - lo >= MIN_SWEEP:
            out.append([(t[i], gs[i], trk[i], h[i]) for i in s])
    return out


def fit_hour(segs):
    n = sum(len(s) for s in segs)
    X = np.zeros((n, 2 + len(segs)))
    y = np.zeros(n)
    r = 0
    for j, s in enumerate(segs):
        for (_, g, tr, _) in s:
            a = math.radians(tr)
            X[r, 0], X[r, 1], X[r, 2 + j] = math.cos(a), math.sin(a), 1.0
            y[r] = g
            r += 1
    beta, res, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    if rank < X.shape[1]:
        return None
    e = y - X @ beta
    s2 = (e @ e) / max(n - X.shape[1], 1)
    cov_b = s2 * np.linalg.pinv(X.T @ X)
    b, c = beta[0], beta[1]
    W = math.hypot(b, c)
    se = math.sqrt(max(cov_b[0, 0], cov_b[1, 1]))
    wfrom = math.degrees(math.atan2(-c, -b)) % 360
    return W, wfrom, se, n, float(np.sqrt(s2)), float(np.mean([p[3] for s in segs for p in s]))


def process_month(args):
    apt_name, month, start = args
    apt = tc.make_airport("K" + apt_name)
    onemin = qm.load_onemin_month(apt_name, month)
    by_hour = defaultdict(list)
    for path in sorted(glob.glob(os.path.join("q2_extract", apt_name, f"{month}-*.jsonl.gz"))):
        day = os.path.basename(path)[:10]
        if day < start:
            continue
        with gzip.open(path, "rt") as f:
            for line in f:
                if not line.strip():
                    continue
                v = json.loads(line)
                for s in segments(v["pts"], apt):
                    by_hour[int(s[len(s) // 2][0] // 3600)].append(s)
    rows = []
    for hour, segs in by_hour.items():
        if len(segs) < MIN_SEGS:
            continue
        fit = fit_hour(segs)
        if not fit:
            continue
        W, wfrom, se, n, rmse, hbar = fit
        if se > MAX_SE:
            continue
        # surface wind: vector mean of one-minute two-minute winds in the hour
        u = vv = 0.0
        k = 0
        for m in range(hour * 60, hour * 60 + 60):
            rec = onemin.get(m)
            if rec and rec[1] is not None and rec[0] is not None:
                u += rec[1] * math.sin(math.radians(rec[0]))
                vv += rec[1] * math.cos(math.radians(rec[0]))
                k += 1
        if k < 30:
            continue
        sw = math.hypot(u / k, vv / k)
        sdir = math.degrees(math.atan2(u / k, vv / k)) % 360
        lt = dt.datetime.fromtimestamp(hour * 3600, tc.LOCAL)
        rows.append({"airport": apt_name, "hour_utc": hour, "local_date": lt.date().isoformat(), "local_hour": lt.hour,
                     "month": lt.month, "segments": len(segs), "points": n, "mean_height_ft": round(hbar),
                     "pattern_wind_kt": round(W, 2), "pattern_wind_from": round(wfrom), "se_kt": round(se, 2), "rmse_kt": round(rmse, 2),
                     "surface_wind_kt": round(sw, 2), "surface_wind_from": round(sdir)})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()
    w = windows()
    tasks = []
    for a in ("BDR", "HVN", "BED", "LWM", "OWD", "PYM", "TAN"):
        start = w[a]
        months = sorted({os.path.basename(p)[:7] for p in glob.glob(os.path.join("q2_extract", a, "*.jsonl.gz"))})
        tasks += [(a, m, start) for m in months if m >= start[:7]]
    rows = []
    with ProcessPoolExecutor(args.workers) as ex:
        for r in ex.map(process_month, tasks):
            rows += r
    os.makedirs("q2_pattern_wind", exist_ok=True)
    with open("q2_pattern_wind/hours.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    L = [f"Pattern-height wind from ground speed in turns: {len(rows):,} airport-hours with a fit (standard error under {MAX_SE:g} kt)", ""]
    good = [r for r in rows if r["surface_wind_kt"] >= 5]
    ratio = np.array([r["pattern_wind_kt"] / r["surface_wind_kt"] for r in good])
    hbar = np.array([r["mean_height_ft"] for r in good])
    alpha = np.log(ratio) / np.log(hbar * 0.3048 / REF_H_M)
    veer = np.array([qm.sdiff(r["pattern_wind_from"], r["surface_wind_from"]) for r in good])
    pl = ((np.median(hbar) * 0.3048 / REF_H_M) ** (1 / 7))
    L.append(f"Hours with surface wind 5 kt or more: {len(good):,}. Mean fit height {np.median(hbar):.0f} ft above the field.")
    L.append(f"  pattern / surface wind speed: median {np.median(ratio):.2f} (IQR {np.percentile(ratio, 25):.2f} to {np.percentile(ratio, 75):.2f}); the 1/7 power law predicts {pl:.2f} at that height")
    L.append(f"  implied power-law exponent: median {np.median(alpha):.3f} (IQR {np.percentile(alpha, 25):.3f} to {np.percentile(alpha, 75):.3f}); 1/7 = 0.143, sensitivity runs use 0 and 0.25")
    L.append(f"  direction, pattern minus surface (positive = veering with height): median {np.median(veer):+.0f} deg, IQR {np.percentile(veer, 25):+.0f} to {np.percentile(veer, 75):+.0f}")
    L.append("")
    L.append("By surface wind band: n, median ratio, median exponent")
    for lo, hi in ((5, 10), (10, 15), (15, 99)):
        m = np.array([lo <= r["surface_wind_kt"] < hi for r in good])
        if m.sum() >= 20:
            L.append(f"  {lo}-{hi if hi < 99 else '+'} kt: {m.sum():,}, {np.median(ratio[m]):.2f}, {np.median(alpha[m]):.3f}")
    L.append("By local hour: n, median exponent (morning stable air should show more shear than afternoon mixing)")
    for lo, hi in ((7, 10), (10, 13), (13, 16), (16, 20)):
        m = np.array([lo <= r["local_hour"] < hi for r in good])
        if m.sum() >= 20:
            L.append(f"  {lo:02d}-{hi:02d}: {m.sum():,}, {np.median(alpha[m]):.3f}")
    L.append("By airport: n, median ratio, median exponent")
    for a in ("BDR", "HVN", "BED", "LWM", "OWD", "PYM", "TAN"):
        m = np.array([r["airport"] == a for r in good])
        if m.sum() >= 20:
            L.append(f"  {a}: {m.sum():,}, {np.median(ratio[m]):.2f}, {np.median(alpha[m]):.3f}")
    calm = [r for r in rows if r["surface_wind_kt"] < 2]
    if calm:
        L.append(f"Check on calm-surface hours (under 2 kt, {len(calm):,}): median fitted pattern wind {np.median([r['pattern_wind_kt'] for r in calm]):.1f} kt")
    text = "\n".join(L)
    open("q2_pattern_wind/summary.txt", "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
