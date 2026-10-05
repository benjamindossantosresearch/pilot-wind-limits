#!/usr/bin/env python3
"""
rebuild_tracks.py

Rebuilds a labeling set's tracks with the current height method
(adsb_airport_coverage.estimate_agl, METAR-based by default), keeping exactly
the same visits and points, so a frozen detector can be rescored against the
existing labels. Labels do not depend on how heights are computed.

    python3 rebuild_tracks.py labeling/heldout            -> labeling/heldout/tracks_metar.json
    python3 rebuild_tracks.py labeling --method gnss      -> labeling/tracks_gnss.json (reproduction check)

Visits are found from key.csv (ICAO, airport, start, duration). Each day is read
from whichever regional cache holds it.
"""

import argparse
import csv
import datetime as dt
import json
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import adsb_airport_coverage as cov
import make_labeling_set as mls


def rebuild_day(args):
    name, day, visits, method = args
    apt = mls.make_airport(name)
    pts = []
    d0 = dt.date.fromisoformat(day)
    for d in (d0, d0 + dt.timedelta(days=1)):  # the next day too, for visits that cross UTC midnight
        for region in ("se_new_england", "new_england"):
            cache_dir = os.path.join("adsb_cache", region)
            if os.path.exists(os.path.join(cache_dir, f"{d}.jsonl.gz")):
                _, day_pts, _ = cov.process_day(d, apt, cov.DEFAULT_RADIUS_NM, cov.REGIONS[region], cache_dir)
                pts.extend(day_pts or [])
                break
    if not pts:
        return {v["visit_id"]: None for v in visits}
    # Heights use the visit's own UTC day only, as when the set was built (the GNSS fallback is per day)
    first = [p for p in pts if dt.datetime.fromtimestamp(p["t"], dt.timezone.utc).date() == d0]
    second = [p for p in pts if dt.datetime.fromtimestamp(p["t"], dt.timezone.utc).date() != d0]
    cov.estimate_agl(first, apt, method=method)
    if second:
        cov.estimate_agl(second, apt, method=method)
    out = {}
    for k in visits:
        t0 = dt.datetime.fromisoformat(k["start_utc"]).timestamp()
        t1 = t0 + int(k["duration_s"]) + 2  # start_utc is truncated to the second
        sel, seen = [], set()
        for p in sorted((p for p in pts if p["icao"] == k["icao"] and t0 <= p["t"] <= t1), key=lambda p: p["t"]):
            if p["t"] in seen:
                continue  # build_visits drops duplicate timestamps the same way
            seen.add(p["t"])
            sel.append(p)
        xy = [cov.to_xy_nm(p["lat"], p["lon"], apt.lat, apt.lon) for p in sel]
        out[k["visit_id"]] = {
            "t": [int(round(p["t"] - sel[0]["t"])) for p in sel] if sel else [],
            "x": [round(a, 4) for a, _ in xy], "y": [round(b, 4) for _, b in xy],
            "agl": [mls.num(p["agl_ft"]) for p in sel], "gs": [mls.num(p["gs_kt"]) for p in sel],
            "trk": [mls.num(p["track"]) for p in sel], "vr": [mls.num(p["vrate_fpm"]) for p in sel],
            "gnd": [1 if p["on_ground"] else 0 for p in sel],
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set_dir", help="folder with tracks.json and key.csv")
    ap.add_argument("--method", default="metar", choices=["metar", "gnss"])
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()

    data = json.load(open(os.path.join(args.set_dir, "tracks.json")))
    keys = list(csv.DictReader(open(os.path.join(args.set_dir, "key.csv"))))
    by_day = defaultdict(list)
    for k in keys:
        by_day[(k["airport"], k["start_utc"][:10])].append(k)
    rebuilt = {}
    with ProcessPoolExecutor(args.workers) as ex:
        for part in ex.map(rebuild_day, [(a, d, v, args.method) for (a, d), v in by_day.items()]):
            rebuilt.update(part)

    mismatched = 0
    for v in data["visits"]:
        r = rebuilt.get(v["id"])
        if not r or len(r["t"]) != len(v["t"]) or r["t"] != v["t"]:
            mismatched += 1
            continue
        old_agl = v["agl"]
        v.update(r)
        v["agl_previous"] = old_agl
    data["height_method"] = args.method
    out = os.path.join(args.set_dir, f"tracks_{args.method}.json")
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    diffs = [a - b for v in data["visits"] if "agl_previous" in v
             for a, b in zip(v["agl"], v["agl_previous"]) if a is not None and b is not None]
    diffs.sort()
    print(f"{out}: {len(data['visits']) - mismatched} visits rebuilt, {mismatched} not matched (kept as before)")
    if diffs:
        print(f"  height change new minus old: median {diffs[len(diffs) // 2]:+d} ft, "
              f"5th to 95th pct {diffs[len(diffs) // 20]:+d} to {diffs[19 * len(diffs) // 20]:+d} ft")


if __name__ == "__main__":
    main()
