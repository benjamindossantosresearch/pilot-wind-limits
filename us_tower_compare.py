#!/usr/bin/env python3
"""
us_tower_compare.py

US confirmatory tower-count check (plan locked 2026-10-02): detected operations
(approaches plus climb-outs, frozen detector v3.0.1) during tower hours against
FAA OPSNET daily counts at 20 towered GA airports, 2025-10-01 to 2026-08-31,
on included airport-days (us_inclusion.py). Same counting rule as
tower_compare.py. Tower hours from NASR ATC_BASE (TWR_HRS), with the two
seasonal schedules (FCM, FFZ) coded below.

Then the capture-vs-weather test, as in capture_weather.py: log(capture) on mean
wind (and separately mean best-runway crosswind), VMC share and precipitation
share during tower hours, with airport-by-quarter and weekday fixed effects,
weighted by tower operations, HC1 standard errors. Pass: the effect of 10 kt
more mean wind within plus or minus 5 percent, 95 percent interval inside plus
or minus 10 percent.

    python3 us_tower_compare.py --workers 48

Writes <out>/daily.csv and <out>/summary.txt (default us_tower_compare/).
"""

import argparse
import bisect
import csv
import datetime as dt
import gzip
import json
import math
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import adsb_airport_coverage as cov
import capture_weather as cw
import ops_detector as od
import runway_use as ru
import us_airports as ua
import us_inclusion as ui
import wind_activity as wa

AIRPORTS = "SUS IXD SLN FRG TTN LNS GFK DPA FCM APA HIO PAE DAB HWO FXE DTO GKY FTW FFZ SDL".split()
CACHE = "adsb_cache/us_airports"
OUT = "us_tower_compare_v31"   # detector v3.1 (primary). The v3.0.1 run is in us_tower_compare/
SIDE = "us_parallel/side_reliable.json"   # detector v3.1 rule 12 pattern sides
START, END = dt.date(2025, 10, 1), dt.date(2026, 8, 31)
FIXED = {"APA": ((0, 0), (24, 0)), "DAB": ((0, 0), (24, 0)), "DPA": ((0, 0), (24, 0)), "FTW": ((0, 0), (24, 0)),
         "FXE": ((0, 0), (24, 0)), "DTO": ((6, 0), (22, 0)), "FRG": ((7, 0), (23, 0)), "GFK": ((6, 0), (23, 30)),
         "GKY": ((7, 0), (21, 0)), "HIO": ((6, 0), (22, 0)), "HWO": ((7, 0), (21, 0)), "IXD": ((6, 0), (22, 0)),
         "LNS": ((6, 0), (23, 0)), "PAE": ((7, 0), (21, 0)), "SDL": ((6, 0), (21, 0)), "SLN": ((7, 0), (23, 0)),
         "SUS": ((6, 0), (23, 0)), "TTN": ((6, 0), (22, 0))}


def nth_weekday(year, month, weekday, n):
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def tower_hours(a, d):
    if a == "FCM":   # 0600-2100 1st Sun in Nov to 2nd Sat in Mar, 0600-2200 2nd Sun in Mar to 1st Sat in Nov
        summer = nth_weekday(d.year, 3, 6, 2) <= d < nth_weekday(d.year, 11, 6, 1)
        return ((6, 0), (22, 0)) if summer else ((6, 0), (21, 0))
    if a == "FFZ":   # May 15 to Aug 15 0530-2100, otherwise 0600-2100
        return ((5, 30), (21, 0)) if dt.date(d.year, 5, 15) <= d <= dt.date(d.year, 8, 15) else ((6, 0), (21, 0))
    return FIXED[a]


def local_ts(d, hm, tz):
    h, m = hm
    if (h, m) == (24, 0):
        nd = d + dt.timedelta(days=1)
        return dt.datetime(nd.year, nd.month, nd.day, 0, 0, tzinfo=tz).timestamp()
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=tz).timestamp()


def count_day(local_date):
    d = dt.date.fromisoformat(local_date)
    sites = ua.load()
    apts = {a: sites[a].apt for a in AIRPORTS}
    boxes = {a: cov.geofence_box(apt, cov.DEFAULT_RADIUS_NM) for a, apt in apts.items()}
    pts = {a: defaultdict(list) for a in AIRPORTS}
    for utc_day in (d, d + dt.timedelta(days=1)):
        path = os.path.join(CACHE, f"{utc_day}.jsonl.gz")
        if not os.path.exists(path):
            return local_date, None
        with gzip.open(path, "rt") as f:
            for line in f:
                tr = json.loads(line)
                lats = [p[1] for p in tr["trace"] if p[1] is not None]
                lons = [p[2] for p in tr["trace"] if p[2] is not None]
                if not lats:
                    continue
                la0, la1, lo0, lo1 = min(lats), max(lats), min(lons), max(lons)
                for a, ((b0, b1), (c0, c1)) in boxes.items():
                    if la1 < b0 or la0 > b1 or lo1 < c0 or lo0 > c1:
                        continue
                    pts[a][utc_day].extend(cov.extract_points(tr, apts[a], cov.DEFAULT_RADIUS_NM))
    side = json.load(open(SIDE))["reliable"] if os.path.exists(SIDE) else {}
    side_ok = {a: set(side.get(a, [])) for a in AIRPORTS}
    out = {}
    for a, apt in apts.items():
        tz = sites[a].tz
        allp = []
        for day_pts in pts[a].values():
            if day_pts:
                cov.estimate_agl(day_pts, apt)
                allp.extend(day_pts)
        opening, closing = tower_hours(a, d)
        t_open, t_close = local_ts(d, opening, tz), local_ts(d, closing, tz)
        ends = ru.runway_ends(apt)
        app = clb = 0
        for v in cov.build_visits(allp) if allp else []:
            if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
                continue
            arr = od.arrays_from_points(v, apt)
            for p in od.detect(arr, ends, side_ok.get(a)):
                t = arr["t"][p["i0"]]
                if t_open <= t < t_close:
                    app += p["kind"] == "approach"
                    clb += p["kind"] == "climb"
        out[a] = (app, clb)
    return local_date, out


def daily_weather(a, dates):
    site = ua.load()[a]
    obs = []
    import glob
    for path in sorted(glob.glob(os.path.join(cov.WEATHER_DIR, f"{site.station}_metar_*.csv"))):
        obs += wa.load_metars(path)
    obs.sort(key=lambda o: o["t"])
    times = [o["t"] for o in obs]
    ends = ui.load().usable_ends(a)
    out = {}
    for ds in dates:
        d = dt.date.fromisoformat(ds)
        opening, closing = tower_hours(a, d)
        t, tc_ = local_ts(d, opening, site.tz), local_ts(d, closing, site.tz)
        hours = []
        while t < tc_:
            mid = dt.datetime.fromtimestamp(t + 1800, dt.timezone.utc)
            i = bisect.bisect_left(times, mid)
            cand = [obs[j] for j in (i - 1, i) if 0 <= j < len(obs)]
            o = min(cand, key=lambda c: abs((c["t"] - mid).total_seconds()), default=None)
            if o is not None and abs((o["t"] - mid).total_seconds()) <= 2400 and o["sknt"] is not None:
                hours.append(o)
            t += 3600
        if len(hours) < 6:
            continue
        vmc = [(h["ceiling"] is None or h["ceiling"] >= 3000) and h["vis"] is not None and h["vis"] >= 5 and not h["precip"] for h in hours]
        xws = [x for x in (wa.best_crosswind(h["drct"], h["sknt"], ends) for h in hours) if x is not None]
        out[ds] = {"wind_mean": sum(h["sknt"] for h in hours) / len(hours), "xw_mean": sum(xws) / len(xws) if xws else None,
                   "vmc_share": sum(vmc) / len(hours), "precip_share": sum(h["precip"] for h in hours) / len(hours)}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--out", default=OUT, help="output folder (us_tower_compare_v31 for the v3.1 rerun)")
    args = ap.parse_args()
    dates = [(START + dt.timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
    det = {}
    with ProcessPoolExecutor(args.workers) as ex:
        for ld, out in ex.map(count_day, dates):
            if out:
                det[ld] = out
    tower = {}
    for r in csv.DictReader(open("reference/opsnet/opsnet_daily.csv")):
        if r["facility"] in AIRPORTS:
            tower[(r["facility"], r["date"])] = int(r["total_ops"])
    inc = ui.load()
    rows = []
    for ld, out in det.items():
        nd = (dt.date.fromisoformat(ld) + dt.timedelta(days=1)).isoformat()
        for a, (app, clb) in out.items():
            if (a, ld) not in tower:
                continue
            rows.append({"date": ld, "facility": a, "tower_ops": tower[(a, ld)], "detected_approaches": app, "detected_climbs": clb,
                         "detected_ops": app + clb, "included": int(inc.day_ok(a, ld) and inc.day_ok(a, nd))})
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "daily.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    L = [f"US tower-count check, detector v{od.VERSION}: {len(rows):,} airport-days with OPSNET counts, {sum(r['included'] for r in rows):,} on included days", ""]
    L.append("Detected / tower operations on included days, daily correlation:")
    for a in AIRPORTS:
        g = [r for r in rows if r["facility"] == a and r["included"] and r["tower_ops"] >= 30]
        if len(g) < 20:
            L.append(f"  {a}: {len(g)} included days with 30 or more tower operations")
            continue
        det_s, tw_s = sum(r["detected_ops"] for r in g), sum(r["tower_ops"] for r in g)
        c = np.corrcoef([r["detected_ops"] for r in g], [r["tower_ops"] for r in g])[0, 1]
        L.append(f"  {a} ({ua.load()[a].state}): {det_s / tw_s:.3f} over {len(g)} days, daily correlation {c:.2f}")
    allg = [r for r in rows if r["included"] and r["tower_ops"] >= 30]
    L.append(f"  pooled: {sum(r['detected_ops'] for r in allg) / sum(r['tower_ops'] for r in allg):.3f} over {len(allg):,} airport-days")
    L.append("")
    # capture against weather
    data = []
    for a in AIRPORTS:
        g = [r for r in allg if r["facility"] == a]
        wx = daily_weather(a, [r["date"] for r in g])
        for r in g:
            if r["date"] not in wx or r["detected_ops"] == 0:
                continue
            d = dt.date.fromisoformat(r["date"])
            data.append({"facility": a, "date": r["date"], "quarter": f"{d.year}Q{(d.month - 1) // 3 + 1}", "tower_ops": r["tower_ops"],
                         "capture": r["detected_ops"] / r["tower_ops"], **wx[r["date"]]})
    for key, name in (("wind_mean", "mean wind"), ("xw_mean", "mean best-runway crosswind")):
        res = cw.fit(data, key)
        wv, vv, pv = res["wind"], res["vmc"], res["precip"]
        verdict = "PASS" if abs(wv[0]) <= 5 and -10 <= wv[1] and wv[2] <= 10 else "FAIL"
        L.append(f"Capture against weather, {name} ({res['n']:,} airport-days): {wv[0]:+.1f}% per 10 kt (95% CI {wv[1]:+.1f} to {wv[2]:+.1f}) -> {verdict}")
        L.append(f"  all-VMC day against no-VMC day {vv[0]:+.1f}% ({vv[1]:+.1f} to {vv[2]:+.1f}); all-precipitation day {pv[0]:+.1f}% ({pv[1]:+.1f} to {pv[2]:+.1f})")
    text = "\n".join(L)
    open(os.path.join(args.out, "summary.txt"), "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
