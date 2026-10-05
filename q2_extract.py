#!/usr/bin/env python3
"""
q2_extract.py

One pass over the regional cache that saves, per airport and day, every
fixed-wing visit with at least one detected approach (frozen detector
ops_detector.py v3.0.1), with the point fields Q2 needs. Q2 measures and their
reruns then read these small files instead of the 25 GB cache.

    python3 q2_extract.py --airports BDR,HVN,BED,LWM,OWD,PYM,TAN --start 2023-02-16 --end 2026-09-30 --workers 32

Writes q2_extract/<APT>/<YYYY-MM-DD>.jsonl.gz. Each line is one visit:
    icao, reg, type, category, flight, db_flags, passes (detector output),
    pts: columnar arrays t, lat, lon, baro, geom, agl, agl_ind, agl_gnss, gs, trk,
         vr, gvr, gnd, src, nacp, gva, modes, qnh, ias, roll
Heights use the METAR method (agl = true height, agl_ind = indicated height,
both above field elevation).
"""

import argparse
import datetime as dt
import gzip
import json
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import adsb_airport_coverage as cov
import ops_detector as od
import runway_use as ru
import tower_compare as tc

OUT = "q2_extract"
FIELDS = [("t", "t", 1), ("lat", "lat", 6), ("lon", "lon", 6), ("baro", "baro_ft", 0), ("geom", "geom_ft", 0),
          ("agl", "agl_ft", 1), ("agl_ind", "agl_ind_ft", 1), ("agl_gnss", "agl_gnss_ft", 1), ("gs", "gs_kt", 1),
          ("trk", "track", 2), ("vr", "vrate_fpm", 0), ("gvr", "geom_rate_fpm", 0), ("gnd", "on_ground", None),
          ("src", "source", None), ("nacp", "nac_p", None), ("gva", "gva", None), ("modes", "nav_modes", None),
          ("qnh", "nav_qnh", 1), ("ias", "ias_kt", 0), ("roll", "roll_deg", 1)]


def _r(v, nd):
    if nd is None or not isinstance(v, (int, float)) or isinstance(v, bool):
        return v
    return round(v, nd) if nd else round(v)


def extract_day(args):
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
    counts = {}
    for n, apt in apts.items():
        out_dir = os.path.join(OUT, n[1:])
        os.makedirs(out_dir, exist_ok=True)
        kept = 0
        lines = []
        if pts[n]:
            cov.estimate_agl(pts[n], apt)
            ends = ru.runway_ends(apt)
            for v in cov.build_visits(pts[n]):
                if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
                    continue
                passes = od.detect(od.arrays_from_points(v, apt), ends)
                if not any(p["kind"] == "approach" for p in passes):
                    continue
                rec = {"icao": v[0]["icao"], "reg": v[0]["reg"], "type": v[0]["type"],
                       "category": next((p["category"] for p in v if p["category"]), ""),
                       "flight": next((p["flight"] for p in v if p["flight"]), ""),
                       "db_flags": v[0]["db_flags"],
                       "passes": [{k: (_r(x, 3) if isinstance(x, float) else x) for k, x in p.items()} for p in passes],
                       "pts": {k: [_r(p.get(src), nd) for p in v] for k, src, nd in FIELDS}}
                lines.append(json.dumps(rec, separators=(",", ":")))
                kept += 1
        with gzip.open(os.path.join(out_dir, f"{day}.jsonl.gz"), "wt", compresslevel=6) as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
        counts[n] = kept
    return day, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--airports", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()
    names = ["K" + x.strip().upper() for x in args.airports.split(",") if x.strip()]
    s, e = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    days = [(s + dt.timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]
    total, missing = defaultdict(int), []
    with ProcessPoolExecutor(args.workers) as ex:
        for day, counts in ex.map(extract_day, [(d, names) for d in days], chunksize=2):
            if counts is None:
                missing.append(day)
                continue
            for n, k in counts.items():
                total[n] += k
    print("visits with an approach: " + ", ".join(f"{n[1:]} {k:,}" for n, k in sorted(total.items())))
    print(f"missing cache days: {', '.join(missing) or 'none'}")


if __name__ == "__main__":
    main()
