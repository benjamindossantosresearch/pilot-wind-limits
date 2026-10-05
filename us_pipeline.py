#!/usr/bin/env python3
"""
us_pipeline.py

Processes the US-wide cache (us_fetch.py) one UTC day at a time, with the same
frozen code as New England (detector v3.0.1, METAR heights, adsb_airport_coverage
visits), for every candidate airport (us_airports.py):

  * visits with at least one detected approach -> q2_extract_us/<ID>/<day>.jsonl.gz
    (same record format as q2_extract.py, read by q2_measures.py)
  * arrivals per local date and hour, 08 to 18 local, split piston / fleet /
    private / all fixed-wing (same rules as q1a_counts.py)
  * coverage: fixed-wing airport-traffic visits and how many were seen to 300 ft
    (same rule as coverage_monthly.py)

Counts and coverage go to us_daily/<day>.json. A local flying day can span two
UTC days in the western time zones, so arrivals carry their local date and the
aggregation sums across files.

The day file is parsed once and each trace is copied to the longitude band(s)
of the airports it passes near. Bands are then processed one at a time, so a
worker holds one band's points at a time.

    python3 us_pipeline.py --start 2025-10-01 --end 2026-09-30 --workers 32
    python3 us_pipeline.py --day 2026-09-15          # one day, for testing
"""

import argparse
import datetime as dt
import gzip
import json
import math
import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import adsb_airport_coverage as cov
import faa_registry as fr
import ops_detector as od
import q2_extract as qx
import runway_use as ru
import us_airports as ua

CACHE = "adsb_cache/us_airports"
OUT_EXTRACT = "q2_extract_us"
OUT_DAILY = "us_daily"
TMP = "tmp_us_bands"
HOURS = range(8, 19)
# 3.5 degree longitude bands, so a worker holds a small slice of the country's points at a time
BANDS = [(-126 + 3.5 * i, -126 + 3.5 * (i + 1)) for i in range(18)]
CELL = 0.5


def band_index(sites):
    """Per longitude band: grid cell -> airport ids whose geofence box touches the cell."""
    out = []
    for lo, hi in BANDS:
        idx = defaultdict(list)
        for sid, s in sites.items():
            if not (lo <= s.apt.lon < hi):
                continue
            (la0, la1), (lo0, lo1) = cov.geofence_box(s.apt, cov.DEFAULT_RADIUS_NM)
            for i in range(math.floor(la0 / CELL), math.floor(la1 / CELL) + 1):
                for j in range(math.floor(lo0 / CELL), math.floor(lo1 / CELL) + 1):
                    idx[(i, j)].append(sid)
        out.append(dict(idx))
    return out


def process_day(day):
    path = os.path.join(CACHE, f"{day}.jsonl.gz")
    done_marker = os.path.join(OUT_DAILY, f"{day}.json")
    if os.path.exists(done_marker):
        return day, "done before"
    if not os.path.exists(path):
        return day, "no cache file"
    sites = ua.load()
    t0 = time.time()
    counts = defaultdict(lambda: [0, 0, 0, 0])
    coverage = {}
    n_visits = n_app_visits = 0
    # one parse of the day: each trace goes to the band file(s) of the airports it passes near
    bidx = band_index(sites)
    tmpdir = os.path.join(TMP, str(day))
    os.makedirs(tmpdir, exist_ok=True)
    bfiles = [gzip.open(os.path.join(tmpdir, f"band{b}.jsonl.gz"), "wt", compresslevel=1) for b in range(len(bidx))]
    with gzip.open(path, "rt") as f:
        for line in f:
            tr = json.loads(line)["trace"]
            cells = {(math.floor(p[1] / CELL), math.floor(p[2] / CELL)) for p in tr if p[1] is not None and p[2] is not None}
            for b, idx in enumerate(bidx):
                if any(c in idx for c in cells):
                    bfiles[b].write(line if line.endswith("\n") else line + "\n")
    for bf in bfiles:
        bf.close()
    for bi, idx in enumerate(bidx):
        if not idx:
            continue
        pts = defaultdict(list)
        with gzip.open(os.path.join(tmpdir, f"band{bi}.jsonl.gz"), "rt") as f:
            for line in f:
                trace = json.loads(line)
                tr = trace["trace"]
                cells = {(math.floor(p[1] / CELL), math.floor(p[2] / CELL)) for p in tr if p[1] is not None and p[2] is not None}
                hits = set()
                for c in cells:
                    hits.update(idx.get(c, ()))
                for sid in hits:
                    pts[sid].extend(cov.extract_points(trace, sites[sid].apt, cov.DEFAULT_RADIUS_NM))
        for sid, P in pts.items():
            if not P:
                continue
            s = sites[sid]
            apt = s.apt
            cov.estimate_agl(P, apt)
            ends = ru.runway_ends(apt)
            lines = []
            fw_ops = fw_seen = all_ops = all_seen = 0
            for v in cov.build_visits(P):
                n_visits += 1
                summ = cov.summarize_visit(v)
                if summ["airport_ops"]:
                    seen = summ["lowest_agl_ft"] != "" and summ["lowest_agl_ft"] <= 300
                    all_ops += 1
                    all_seen += seen
                    if summ["category"] != cov.ROTORCRAFT_CATEGORY:
                        fw_ops += 1
                        fw_seen += seen
                if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
                    continue
                a = od.arrays_from_points(v, apt)
                passes = od.detect(a, ends)
                apps = [p for p in passes if p["kind"] == "approach"]
                if not apps:
                    continue
                n_app_visits += 1
                rec = {"icao": v[0]["icao"], "reg": v[0]["reg"], "type": v[0]["type"],
                       "category": next((p["category"] for p in v if p["category"]), ""),
                       "flight": next((p["flight"] for p in v if p["flight"]), ""), "db_flags": v[0]["db_flags"],
                       "passes": [{k: (qx._r(x, 3) if isinstance(x, float) else x) for k, x in p.items()} for p in passes],
                       "pts": {k: [qx._r(p.get(src), nd) for p in v] for k, src, nd in qx.FIELDS}}
                lines.append(json.dumps(rec, separators=(",", ":")))
                # arrival counts by local date and hour (first approach of the visit)
                t_first = min(a["t"][p["i0"]] for p in apps)
                lt = dt.datetime.fromtimestamp(t_first, s.tz)
                if lt.hour in HOURS:
                    c = counts[(sid, lt.date().isoformat(), lt.hour)]
                    c[3] += 1
                    r = fr.lookup(v[0]["icao"], dt.datetime.fromtimestamp(t_first, dt.timezone.utc).date())
                    if r and r["piston_fixed_wing"] and r["ownership"] != "commercial":
                        c[0] += 1
                        if r["ownership"] == "fleet":
                            c[1] += 1
                        elif r["ownership"] == "private":
                            c[2] += 1
            coverage[sid] = [fw_ops, fw_seen, all_ops, all_seen]
            if lines:
                d = os.path.join(OUT_EXTRACT, sid)
                os.makedirs(d, exist_ok=True)
                with gzip.open(os.path.join(d, f"{day}.jsonl.gz"), "wt", compresslevel=6) as f:
                    f.write("\n".join(lines) + "\n")
        del pts
        os.remove(os.path.join(tmpdir, f"band{bi}.jsonl.gz"))
    for b in range(len(bidx)):
        fp = os.path.join(tmpdir, f"band{b}.jsonl.gz")
        if os.path.exists(fp):
            os.remove(fp)
    os.rmdir(tmpdir)
    os.makedirs(OUT_DAILY, exist_ok=True)
    tmp = done_marker + ".tmp"
    json.dump({"day": str(day), "coverage": coverage,
               "counts": [[k[0], k[1], k[2]] + v for k, v in sorted(counts.items())]}, open(tmp, "w"))
    os.replace(tmp, done_marker)
    return day, f"ok ({len(coverage)} airports, {n_visits:,} visits, {n_app_visits:,} with approaches, {time.time() - t0:,.0f}s)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--day")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    if args.day:
        print(process_day(dt.date.fromisoformat(args.day)))
        return
    s, e = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    days = [s + dt.timedelta(days=i) for i in range((e - s).days + 1)]
    t0 = time.time()
    with ProcessPoolExecutor(args.workers) as ex:
        futs = [ex.submit(process_day, d) for d in days]
        for n, fut in enumerate(as_completed(futs), 1):
            day, status = fut.result()
            print(f"  [{day}] {status}  ({n}/{len(days)}, {(time.time() - t0) / 60:.0f} min)", flush=True)


if __name__ == "__main__":
    main()
