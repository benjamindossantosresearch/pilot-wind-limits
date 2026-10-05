#!/usr/bin/env python3
"""
make_labeling_set_us.py

Set 4: the detector validation set for the US confirmatory sample, by the rule
locked in notes/decisions.md before the US data were analyzed: 100 visits from
at least 10 included airports outside New England, drawn at random with seed
20261010, stratified by tower status and FAA region.

    airports   one towered and one non-towered included airport per FAA region
               outside New England (seven regions, so 14 airports where both
               exist), drawn at random from airports with at least 20 eligible
               visits in the sampled days
    days       30 included days drawn at random from 2025-10-01 to 2026-09-30
               (the same days for every airport, so each day file is read once)
    visits     same eligibility as Sets 1 to 3: fixed-wing piston GA in the FAA
               registry, passes within 3 nm below 2,000 ft AGL, 10 or more points,
               at most 2 hours, at most 2 visits per aircraft per airport
    quota      100 visits split as evenly as possible across the airports

Output in the labeler's format (make_labeling_set.py): labeling/us/tracks.json,
key.csv (stays on the server), detector.csv.

    python3 make_labeling_set_us.py --workers 30
"""

import argparse
import csv
import datetime as dt
import gzip
import json
import math
import os
import random
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import adsb_airport_coverage as cov
import faa_registry as fr
import make_labeling_set as mls
import runway_use as ru
import us_airports as ua
import us_inclusion as ui
import us_q1a

SEED = 20261010
N_DAYS = 30
TOTAL = 100
MIN_ELIGIBLE = 20
OUT = "labeling/us"
CACHE = "adsb_cache/us_airports"


def day_visits(args):
    """Eligible visits for every candidate airport on one UTC day (one read of the day file)."""
    day, airports = args
    sites = ua.load()
    apts = {a: sites[a].apt for a in airports}
    boxes = {a: cov.geofence_box(apt, cov.DEFAULT_RADIUS_NM) for a, apt in apts.items()}
    pts = defaultdict(list)
    with gzip.open(os.path.join(CACHE, f"{day}.jsonl.gz"), "rt") as f:
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
                pts[a].extend(cov.extract_points(tr, apts[a], cov.DEFAULT_RADIUS_NM))
    out = []
    for a, P in pts.items():
        apt = apts[a]
        ends = ru.runway_ends(apt)
        cov.estimate_agl(P, apt)
        for v in cov.build_visits(P):
            if len(v) < mls.MIN_POINTS or v[-1]["t"] - v[0]["t"] > mls.MAX_DURATION_S:
                continue
            if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
                continue
            if not any(p["agl_ft"] is not None and p["dist_arp_nm"] <= mls.NEAR_NM and p["agl_ft"] <= mls.NEAR_AGL for p in v):
                continue
            t0 = v[0]["t"]
            step = max(1, math.ceil(len(v) / mls.MAX_POINTS))
            vv = v[::step]
            xy = [cov.to_xy_nm(p["lat"], p["lon"], apt.lat, apt.lon) for p in vv]
            track = {"t": [int(round(p["t"] - t0)) for p in vv], "x": [round(x, 4) for x, _ in xy], "y": [round(y, 4) for _, y in xy],
                     "agl": [mls.num(p["agl_ft"]) for p in vv], "gs": [mls.num(p["gs_kt"]) for p in vv],
                     "trk": [mls.num(p["track"]) for p in vv], "vr": [mls.num(p["vrate_fpm"]) for p in vv],
                     "gnd": [1 if p["on_ground"] else 0 for p in vv]}
            passes = ru.find_passes(v, apt, ends)
            out.append({"airport": a, "day": day, "icao": v[0]["icao"], "start_t": t0,
                        "type": next((p["type"] for p in v if p["type"]), ""), "track": track,
                        "passes": [{k: ps[k] for k in ("kind", "runway", "low", "min_agl_ft", "dist_thr_at_min_nm", "time_utc")}
                                   for ps in passes]})
    return out


def geometry(a):
    apt = ua.load()[a].apt
    ends = ru.runway_ends(apt)
    rwys = []
    for rid, (p, q) in apt.runways.items():
        n1, n2 = rid.split("/")
        rwys.append({"id": rid, "ends": [{"name": n1, "x": round(p[0], 4), "y": round(p[1], 4)},
                                         {"name": n2, "x": round(q[0], 4), "y": round(q[1], 4)}]})
    return {"name": a, "elev_ft": apt.elev_ft, "runways": rwys, "ends": [{"name": e.name, "course_true": round(e.course)} for e in ends]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=30)
    args = ap.parse_args()
    rng = random.Random(SEED)
    inc = ui.load()
    sites = ua.load()
    pool = [a for a in inc.included_airports() if us_q1a.region_of(sites[a].state) != "ANE"]
    strata = defaultdict(list)
    for a in pool:
        strata[(us_q1a.region_of(sites[a].state), sites[a].tower.startswith("ATCT"))].append(a)
    all_days = sorted(d for d in inc.days_present if dt.date(2025, 10, 1).isoformat() <= d <= "2026-09-30")
    days = sorted(rng.sample(all_days, N_DAYS))
    # draw several candidates per stratum, keep the first with enough eligible visits
    order = {k: rng.sample(v, min(len(v), 4)) for k, v in sorted(strata.items())}
    cand_airports = sorted({a for v in order.values() for a in v})
    visits = defaultdict(list)
    with ProcessPoolExecutor(args.workers) as ex:
        for out in ex.map(day_visits, [(d, cand_airports) for d in days]):
            for v in out:
                if inc.day_ok(v["airport"], v["day"]):
                    visits[v["airport"]].append(v)
    report, chosen_airports = [], []
    for k, cands in sorted(order.items()):
        for a in cands:
            el = []
            for v in sorted(visits[a], key=lambda v: (v["day"], v["icao"], v["start_t"])):
                rec = fr.lookup(v["icao"], v["day"])
                if rec and rec["piston_fixed_wing"] and rec["ownership"] != "commercial":
                    v["type"] = v["type"] or rec["model"]
                    el.append(v)
            if len(el) >= MIN_ELIGIBLE:
                chosen_airports.append((a, el))
                report.append(f"{k[0]} {'towered' if k[1] else 'non-towered'}: {a} ({len(el)} eligible piston visits)")
                break
        else:
            report.append(f"{k[0]} {'towered' if k[1] else 'non-towered'}: no airport with {MIN_ELIGIBLE} eligible visits")
    n = len(chosen_airports)
    quotas = [TOTAL // n + (1 if i < TOTAL % n else 0) for i in range(n)]
    sample = []
    for (a, el), q in zip(chosen_airports, quotas):
        rng.shuffle(el)
        per_ac, got = defaultdict(int), []
        for v in el:
            if per_ac[v["icao"]] >= mls.MAX_PER_AIRCRAFT:
                continue
            per_ac[v["icao"]] += 1
            got.append(v)
            if len(got) == q:
                break
        sample.extend(got)
    rng.shuffle(sample)
    os.makedirs(OUT, exist_ok=True)
    vis, key_rows, det_rows = [], [], []
    for i, v in enumerate(sample, 1):
        vid = f"U{i:03d}"
        vis.append({"id": vid, "airport": v["airport"], "type": v["type"], **v["track"]})
        key_rows.append({"visit_id": vid, "airport": v["airport"], "icao": v["icao"],
                         "start_utc": dt.datetime.fromtimestamp(v["start_t"], dt.timezone.utc).isoformat(timespec="seconds"),
                         "duration_s": v["track"]["t"][-1], "n_points": len(v["track"]["t"])})
        for ps in v["passes"]:
            det_rows.append({"visit_id": vid, **ps})
    data = {"version": 1, "seed": SEED, "windows": [[d, d] for d in days],
            "airports": {a: geometry(a) for a, _ in chosen_airports}, "visits": vis}
    json.dump(data, open(os.path.join(OUT, "tracks.json"), "w"), separators=(",", ":"))
    with open(os.path.join(OUT, "key.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(key_rows[0]))
        w.writeheader()
        w.writerows(key_rows)
    with open(os.path.join(OUT, "detector.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["visit_id", "kind", "runway", "low", "min_agl_ft", "dist_thr_at_min_nm", "time_utc"])
        w.writeheader()
        w.writerows(det_rows)
    print("\n".join(report))
    print(f"{len(sample)} visits at {n} airports, days: {days[0]} to {days[-1]} ({len(days)}), "
          f"tracks.json {os.path.getsize(os.path.join(OUT, 'tracks.json')) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
