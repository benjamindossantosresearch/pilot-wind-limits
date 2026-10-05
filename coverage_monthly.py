#!/usr/bin/env python3
"""
coverage_monthly.py

Monthly archive low-altitude coverage per airport: the share of fixed-wing
airport-traffic visits (descending below 1,500 ft AGL within 3 nm of a
threshold, adsb_airport_coverage.summarize_visit) whose lowest observed point
is at or below 300 ft AGL. Sets the Q1a windows for the untowered airports
(PYM, TAN) under the rule logged in notes/decisions.md (2026-10-02), and for
the towered airports shows how this measure tracks tower-count capture.

    python3 coverage_monthly.py --airports BDR,HVN,BED,LWM,OWD,PYM,TAN --start 2023-02-16 --end 2026-09-30 --workers 32

Writes coverage_monthly/daily.csv and coverage_monthly/monthly.csv.
"""

import argparse
import csv
import datetime as dt
import gzip
import json
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import adsb_airport_coverage as cov
import tower_compare as tc


def day_coverage(args):
    day, names = args
    d = dt.date.fromisoformat(day)
    path = tc.cache_path(d)
    if not path:
        return day, None
    apts = {n: tc.make_airport(n) for n in names}
    boxes = {n: cov.geofence_box(a, cov.DEFAULT_RADIUS_NM) for n, a in apts.items()}
    pts = defaultdict(list)
    with gzip.open(path, "rt") as f:
        for line in f:
            trace = json.loads(line)
            lats = [p[1] for p in trace["trace"] if p[1] is not None]
            lons = [p[2] for p in trace["trace"] if p[2] is not None]
            if not lats:
                continue
            la0, la1, lo0, lo1 = min(lats), max(lats), min(lons), max(lons)
            for n, ((b0, b1), (c0, c1)) in boxes.items():
                if la1 < b0 or la0 > b1 or lo1 < c0 or lo0 > c1:
                    continue
                pts[n].extend(cov.extract_points(trace, apts[n], cov.DEFAULT_RADIUS_NM))
    out = {}
    for n, apt in apts.items():
        ops = low = ops_all = low_all = 0
        if pts[n]:
            cov.estimate_agl(pts[n], apt)
            for v in cov.build_visits(pts[n]):
                s = cov.summarize_visit(v)
                if not s["airport_ops"]:
                    continue
                seen = s["lowest_agl_ft"] != "" and s["lowest_agl_ft"] <= 300
                ops_all += 1
                low_all += seen
                if s["category"] != cov.ROTORCRAFT_CATEGORY:
                    ops += 1
                    low += seen
        out[n] = (ops, low, ops_all, low_all)
    return day, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--airports", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--out", default="coverage_monthly")
    args = ap.parse_args()
    names = ["K" + x.strip().upper() for x in args.airports.split(",") if x.strip()]
    s, e = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    days = [(s + dt.timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]
    os.makedirs(args.out, exist_ok=True)
    daily, monthly = [], defaultdict(lambda: [0, 0, 0, 0])
    with ProcessPoolExecutor(args.workers) as ex:
        for day, out in ex.map(day_coverage, [(d, names) for d in days], chunksize=4):
            if out is None:
                continue
            for n, (ops, low, ops_all, low_all) in out.items():
                daily.append({"airport": n[1:], "date": day, "fw_ops_visits": ops, "fw_seen_300": low,
                              "all_ops_visits": ops_all, "all_seen_300": low_all})
                m = monthly[(n[1:], day[:7])]
                m[0] += ops
                m[1] += low
                m[2] += ops_all
                m[3] += low_all
    daily.sort(key=lambda r: (r["airport"], r["date"]))
    with open(os.path.join(args.out, "daily.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(daily[0]))
        w.writeheader()
        w.writerows(daily)
    with open(os.path.join(args.out, "monthly.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["airport", "month", "fw_ops_visits", "fw_seen_300", "fw_share_300", "all_ops_visits", "all_seen_300", "all_share_300"])
        for (a, mo), (o, l, oa, la) in sorted(monthly.items()):
            w.writerow([a, mo, o, l, round(l / o, 4) if o else "", oa, la, round(la / oa, 4) if oa else ""])
    print(f"{len(daily):,} airport-days written to {args.out}/")


if __name__ == "__main__":
    main()
