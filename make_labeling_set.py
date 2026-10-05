#!/usr/bin/env python3
"""
make_labeling_set.py

Draws the hand-labeling sample for validating the operations detector and
writes it in two parts:

    labeling/tracks.json    what raters see: anonymized tracks in local
                            nautical-mile coordinates, runway geometry, and the
                            aircraft type. No ICAO address, registration, date,
                            or time of day
    labeling/key.csv        what stays on the server: visit id to ICAO, date,
                            start time, and airport
    labeling/detector.csv   the detector's passes for each sampled visit
                            (runway_use.py rules), for scoring agreement later.
                            Raters never see it

Sampling rules (fixed before labeling, see notes/decisions.md):
    airports        KLWM 35, KOWD 35, KBED 30 (towered, so FAA counts exist)
    window          2026-07-18 to 2026-09-20 (UTC days)
    eligible visit  fixed-wing, not rotorcraft, piston GA in the FAA registry on
                    that date (Cape Air and other commercial excluded), passes
                    within 3 nm of the airport reference point below 2,000 ft AGL,
                    at least 10 points, at most 2 hours long. Eligibility does
                    not use the detector, so overflights and departures are in
                    the pool along with arrivals
    draw            simple random sample per airport, seed 20261001, at most 2
                    visits per aircraft per airport, then shuffled together
                    into one presentation order

Usage:
    python3 make_labeling_set.py --workers 24
    python3 make_labeling_set.py --windows 2026-03-01:2026-03-31,2026-09-21:2026-09-30 \
        --seed 20261002 --prefix T --out labeling/heldout --workers 24     (held-out set)
"""

import argparse
import csv
import datetime as dt
import json
import math
import os
import random
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import adsb_airport_coverage as cov
import faa_registry as fr
import runway_use as ru

QUOTAS = {"KLWM": 35, "KOWD": 35, "KBED": 30}
WINDOWS = "2026-07-18:2026-09-20"
SEED = 20261001
NEAR_NM, NEAR_AGL = 3.0, 2000
MIN_POINTS, MAX_DURATION_S = 10, 7200
MAX_PER_AIRCRAFT = 2
MAX_POINTS = 2500
OUT_DIR = "labeling"


def make_airport(name):
    c = cov.AIRPORTS[name]
    apt = cov.Airport(name, c["lat"], c["lon"], c["elev_ft"], c["geoid_offset_ft"], c["runways"])
    apt.radius = cov.DEFAULT_RADIUS_NM
    return apt


def num(v, digits=None):
    if not isinstance(v, (int, float)):
        return None
    return round(v, digits) if digits else int(round(v))


def day_visits(name, day, region_name, cache_root):
    """Eligible visits for one airport and day, with compact tracks and detector passes."""
    apt = make_airport(name)
    ends = ru.runway_ends(apt)
    region = cov.REGIONS[region_name]
    _, pts, _ = cov.process_day(day, apt, cov.DEFAULT_RADIUS_NM, region, os.path.join(cache_root, region_name))
    if not pts:
        return []
    cov.estimate_agl(pts, apt)
    out = []
    for v in cov.build_visits(pts):
        if len(v) < MIN_POINTS or v[-1]["t"] - v[0]["t"] > MAX_DURATION_S:
            continue
        if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
            continue
        if not any(p["agl_ft"] is not None and p["dist_arp_nm"] <= NEAR_NM and p["agl_ft"] <= NEAR_AGL for p in v):
            continue
        t0 = v[0]["t"]
        step = max(1, math.ceil(len(v) / MAX_POINTS))
        vv = v[::step]
        xy = [cov.to_xy_nm(p["lat"], p["lon"], apt.lat, apt.lon) for p in vv]
        track = {
            "t": [int(round(p["t"] - t0)) for p in vv],
            "x": [round(a, 4) for a, _ in xy],
            "y": [round(b, 4) for _, b in xy],
            "agl": [num(p["agl_ft"]) for p in vv],
            "gs": [num(p["gs_kt"]) for p in vv],
            "trk": [num(p["track"]) for p in vv],
            "vr": [num(p["vrate_fpm"]) for p in vv],
            "gnd": [1 if p["on_ground"] else 0 for p in vv],
        }
        passes = ru.find_passes(v, apt, ends)
        out.append({
            "airport": name, "day": day.isoformat(), "icao": v[0]["icao"], "start_t": t0,
            "type": next((p["type"] for p in v if p["type"]), ""),
            "track": track,
            "passes": [{k: ps[k] for k in ("kind", "runway", "low", "min_agl_ft", "dist_thr_at_min_nm", "time_utc")}
                       for ps in passes],
        })
    return out


def runway_geometry(name):
    apt = make_airport(name)
    ends = ru.runway_ends(apt)
    rwys = []
    for rid, (a, b) in apt.runways.items():
        n1, n2 = rid.split("/")
        rwys.append({"id": rid, "ends": [{"name": n1, "x": round(a[0], 4), "y": round(a[1], 4)},
                                         {"name": n2, "x": round(b[0], 4), "y": round(b[1], 4)}]})
    return {"name": name, "elev_ft": apt.elev_ft, "runways": rwys,
            "ends": [{"name": e.name, "course_true": round(e.course)} for e in ends]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--region", default="se_new_england", choices=sorted(cov.REGIONS))
    ap.add_argument("--cache", default="adsb_cache")
    ap.add_argument("--windows", default=WINDOWS, help="comma-separated START:END date ranges (UTC days)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--prefix", default="V", help="visit id prefix")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()

    days, windows = [], []
    for w in args.windows.split(","):
        a, b = w.split(":")
        s, e = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
        windows.append([a, b])
        days += [s + dt.timedelta(days=i) for i in range((e - s).days + 1)]
    pool = defaultdict(list)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(day_visits, name, d, args.region, args.cache) for name in QUOTAS for d in days]
        for f in as_completed(futs):
            for v in f.result():
                pool[v["airport"]].append(v)

    rng = random.Random(args.seed)
    sample, report = [], []
    for name, quota in QUOTAS.items():
        cands = []
        for v in sorted(pool[name], key=lambda v: (v["day"], v["icao"], v["start_t"])):
            rec = fr.lookup(v["icao"], v["day"])
            if rec and rec["piston_fixed_wing"] and rec["ownership"] != "commercial":
                v["type"] = v["type"] or rec["model"]
                cands.append(v)
        rng.shuffle(cands)
        per_ac, chosen = defaultdict(int), []
        for v in cands:
            if per_ac[v["icao"]] >= MAX_PER_AIRCRAFT:
                continue
            per_ac[v["icao"]] += 1
            chosen.append(v)
            if len(chosen) == quota:
                break
        report.append(f"{name}: {len(pool[name])} eligible visits, {len(cands)} piston GA, sampled {len(chosen)}")
        sample.extend(chosen)
    rng.shuffle(sample)

    os.makedirs(args.out, exist_ok=True)
    visits_out, key_rows, det_rows = [], [], []
    for i, v in enumerate(sample, 1):
        vid = f"{args.prefix}{i:03d}"
        visits_out.append({"id": vid, "airport": v["airport"], "type": v["type"], **v["track"]})
        start = dt.datetime.fromtimestamp(v["start_t"], dt.timezone.utc)
        key_rows.append({"visit_id": vid, "airport": v["airport"], "icao": v["icao"],
                         "start_utc": start.isoformat(timespec="seconds"),
                         "duration_s": v["track"]["t"][-1], "n_points": len(v["track"]["t"])})
        for ps in v["passes"]:
            det_rows.append({"visit_id": vid, **ps})
    data = {"version": 1, "seed": args.seed, "windows": windows,
            "airports": {name: runway_geometry(name) for name in QUOTAS}, "visits": visits_out}
    with open(os.path.join(args.out, "tracks.json"), "w") as f:
        json.dump(data, f, separators=(",", ":"))
    with open(os.path.join(args.out, "key.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(key_rows[0]))
        w.writeheader()
        w.writerows(key_rows)
    with open(os.path.join(args.out, "detector.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["visit_id", "kind", "runway", "low", "min_agl_ft",
                                          "dist_thr_at_min_nm", "time_utc"])
        w.writeheader()
        w.writerows(det_rows)
    print("\n".join(report))
    print(f"{len(sample)} visits, {sum(len(v['t']) for v in visits_out):,} points, "
          f"tracks.json {os.path.getsize(os.path.join(args.out, 'tracks.json')) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
