#!/usr/bin/env python3
"""
q1a_counts.py

Hourly arrival counts for Q1a. For each airport and each local clock hour
(08 to 18 local), counts visits with at least one approach to a runway end,
using the frozen detector (ops_detector.py v3.0.1), in the hour of the visit's
first approach. Rules follow notes/decisions.md (pilot Q1a rules, 2026-10-01).

Counts are split by aircraft group from the FAA registry on the flight date:
    piston     piston fixed-wing GA (commercial operators such as Cape Air excluded)
    fleet      piston GA registered to a fleet (non-individual registrant with 3 or more aircraft)
    private    piston GA registered privately (individual, co-owned, or small entity)
    all_fixed  every fixed-wing visit (rotorcraft category A7 excluded)

    python3 q1a_counts.py --airports BDR,HVN,BED,LWM,OWD --start 2023-02-16 --end 2026-09-30 --workers 32

Writes q1a/hourly_arrivals.csv: airport, local_date, hour, piston, fleet, private, all_fixed.
Local hours 08 to 18 fall inside one UTC day all year in New England, so each
local date reads one UTC day of the cache.
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
import faa_registry as fr
import ops_detector as od
import runway_use as ru
import tower_compare as tc

HOURS = range(8, 19)


def count_day(args):
    local_date, names = args
    d = dt.date.fromisoformat(local_date)
    path = tc.cache_path(d)
    if not path:
        return local_date, None
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
        counts = {h: {"piston": 0, "fleet": 0, "private": 0, "all_fixed": 0} for h in HOURS}
        if pts[n]:
            cov.estimate_agl(pts[n], apt)
            ends = ru.runway_ends(apt)
            for v in cov.build_visits(pts[n]):
                if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
                    continue
                a = od.arrays_from_points(v, apt)
                apps = [p for p in od.detect(a, ends) if p["kind"] == "approach"]
                if not apps:
                    continue
                t = min(a["t"][p["i0"]] for p in apps)
                lt = dt.datetime.fromtimestamp(t, tc.LOCAL)
                if lt.date() != d or lt.hour not in counts:
                    continue
                counts[lt.hour]["all_fixed"] += 1
                rec = fr.lookup(v[0]["icao"], lt.astimezone(dt.timezone.utc).date())
                if rec and rec["piston_fixed_wing"] and rec["ownership"] != "commercial":
                    counts[lt.hour]["piston"] += 1
                    if rec["ownership"] in ("fleet", "private"):
                        counts[lt.hour][rec["ownership"]] += 1
        out[n] = counts
    return local_date, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--airports", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--out", default="q1a")
    args = ap.parse_args()
    names = ["K" + x.strip().upper() for x in args.airports.split(",") if x.strip()]
    s, e = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    dates = [(s + dt.timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]
    os.makedirs(args.out, exist_ok=True)
    rows, missing = [], []
    with ProcessPoolExecutor(args.workers) as ex:
        for local_date, out in ex.map(count_day, [(d, names) for d in dates], chunksize=4):
            if out is None:
                missing.append(local_date)
                continue
            for n, counts in out.items():
                for h, c in counts.items():
                    rows.append({"airport": n[1:], "local_date": local_date, "hour": h, **c})
    rows.sort(key=lambda r: (r["airport"], r["local_date"], r["hour"]))
    with open(os.path.join(args.out, "hourly_arrivals.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["airport", "local_date", "hour", "piston", "fleet", "private", "all_fixed"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows):,} airport-hours, {len(dates) - len(missing)} dates, missing cache days: {', '.join(missing) or 'none'}")


if __name__ == "__main__":
    main()
