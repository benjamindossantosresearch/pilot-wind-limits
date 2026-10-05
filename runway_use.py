#!/usr/bin/env python3
"""
runway_use.py

Counts approaches and climb-outs per runway end per day at one airport, using
the regional ADS-B cache built by adsb_airport_coverage.py. Days missing from
the cache are streamed from the ADSB.lol archive and cached on the way.

Built to date the KPYM runway 06/24 closure: approaches to 06 and 24 should
stop on the day the runway closed, whatever the wind.

Usage:
    python3 runway_use.py --airport KPYM --start 2026-09-07 --end 2026-09-30
    python3 runway_use.py --airport KPYM --start 2026-01-01 --end 2026-09-06 --step 7 --workers 24 \\
        --metar weather/PYM_metar_2025-01-01_2026-09-30.csv

Classification (fixed-wing only, rotorcraft category A7 excluded):
    approach to end R    points up to 2 nm before R's threshold, within 0.3 nm of
                         the extended centerline, ground track within 30 deg of
                         the landing course, below 900 ft AGL, descending overall
    climb-out from R     points from R's threshold to 2 nm past the far end, same
                         lateral and track limits, below 1,200 ft AGL, climbing overall
Daily counts include only approaches to land: those reaching 400 ft AGL or lower
within 0.75 nm of the threshold. Higher passes stay in passes.csv with low=False.
The approach is the unit regardless of outcome. Landings, touch-and-goes, low
approaches, and go-arounds are not separated. Dates are UTC.

Outputs (in --out, default ./runway_use_<airport>):
    passes.csv       one row per detected approach or climb-out
    daily.csv        per-day counts by runway end, plus daytime wind if --metar is given
    runway_use.png   daily approaches by runway end
"""

import argparse
import csv
import datetime as dt
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import adsb_airport_coverage as cov

APP_DIST_NM = 2.0          # approach window before the threshold
CLIMB_PAST_NM = 2.0        # climb-out window past the far end
MAX_LATERAL_NM = 0.3       # distance from the extended centerline
MAX_TRACK_DIFF = 30.0      # ground track vs runway course, degrees (allows crab)
APP_MAX_AGL = 900
CLIMB_MAX_AGL = 1200
MIN_POINTS = 3
MERGE_GAP_S = 45           # same-label points closer than this belong to one pass
MIN_HEIGHT_CHANGE = 50     # ft descended (approach) or climbed (climb-out) across a pass
# An approach counts as an approach to land ("low") if it gets down to LOW_AGL_FT within
# LOW_DIST_NM of the threshold. Passes that stay higher are overflights or high passes,
# kept in passes.csv but left out of the daily counts.
LOW_AGL_FT = 400
LOW_DIST_NM = 0.75
DAYTIME_UTC = range(11, 24)  # roughly 0700 to 1959 local in summer, for the wind summary


class RunwayEnd:
    """One landing direction: threshold, unit vector along the landing course, runway length."""

    def __init__(self, name, thr_xy, far_xy):
        self.name = name
        self.tx, self.ty = thr_xy
        dx, dy = far_xy[0] - thr_xy[0], far_xy[1] - thr_xy[1]
        self.length = math.hypot(dx, dy)
        self.ux, self.uy = dx / self.length, dy / self.length
        self.course = math.degrees(math.atan2(self.ux, self.uy)) % 360

    def along_lateral(self, x, y):
        rx, ry = x - self.tx, y - self.ty
        return rx * self.ux + ry * self.uy, abs(rx * self.uy - ry * self.ux)


def runway_ends(apt):
    ends = []
    for rid, (a, b) in apt.runways.items():
        n1, n2 = rid.split("/")
        ends.append(RunwayEnd(n1, a, b))
        ends.append(RunwayEnd(n2, b, a))
    return ends


def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def label_point(p, apt, ends):
    """Returns (("approach" | "climb", end name), along-track nm) or None."""
    if p["agl_ft"] is None or not isinstance(p["track"], (int, float)):
        return None
    x, y = cov.to_xy_nm(p["lat"], p["lon"], apt.lat, apt.lon)
    best = None
    for e in ends:
        if angle_diff(p["track"], e.course) > MAX_TRACK_DIFF:
            continue
        along, lateral = e.along_lateral(x, y)
        if lateral > MAX_LATERAL_NM:
            continue
        if -APP_DIST_NM <= along < 0 and not p["on_ground"] and p["agl_ft"] <= APP_MAX_AGL:
            cand = ("approach", e.name)
        elif 0 <= along <= e.length + CLIMB_PAST_NM and p["agl_ft"] <= CLIMB_MAX_AGL:
            cand = ("climb", e.name)
        else:
            continue
        if best is None or lateral < best[0]:
            best = (lateral, cand, along)
    return (best[1], best[2]) if best else None


def find_passes(visit, apt, ends):
    labeled = [(p, label_point(p, apt, ends)) for p in visit]
    labeled = [(p, res[0], res[1]) for p, res in labeled if res is not None]
    groups = []
    for p, lab, along in labeled:
        if groups and groups[-1][0] == lab and p["t"] - groups[-1][1][-1]["t"] <= MERGE_GAP_S:
            groups[-1][1].append(p)
            groups[-1][2].append(along)
        else:
            groups.append((lab, [p], [along]))
    passes = []
    for (kind, end), pts, alongs in groups:
        if len(pts) < MIN_POINTS:
            continue
        change = pts[-1]["agl_ft"] - pts[0]["agl_ft"]
        rates = [p["vrate_fpm"] for p in pts if isinstance(p["vrate_fpm"], (int, float))]
        med_rate = statistics.median(rates) if rates else 0
        if kind == "approach" and not (change <= -MIN_HEIGHT_CHANGE or med_rate <= -200):
            continue
        if kind == "climb" and not (change >= MIN_HEIGHT_CHANGE or med_rate >= 200):
            continue
        low_i = min(range(len(pts)), key=lambda i: pts[i]["agl_ft"])
        min_agl, dist_at_min = pts[low_i]["agl_ft"], abs(alongs[low_i])
        passes.append({
            "date_utc": dt.datetime.fromtimestamp(pts[0]["t"], dt.timezone.utc).date().isoformat(),
            "time_utc": dt.datetime.fromtimestamp(pts[0]["t"], dt.timezone.utc).isoformat(timespec="seconds"),
            "kind": kind, "runway": end,
            "icao": pts[0]["icao"], "type": pts[0]["type"],
            "squawk": next((p["squawk"] for p in pts if p["squawk"]), ""),
            "n_points": len(pts),
            "agl_start_ft": round(pts[0]["agl_ft"]), "agl_end_ft": round(pts[-1]["agl_ft"]),
            "min_agl_ft": round(min_agl), "dist_thr_at_min_nm": round(dist_at_min, 2),
            "low": kind == "approach" and min_agl <= LOW_AGL_FT and dist_at_min <= LOW_DIST_NM,
            "source": Counter(p["source"] for p in pts).most_common(1)[0][0] or "",
        })
    return passes


def daytime_wind(metar_path, ends):
    """Per UTC date: vector-mean daytime wind and mean crosswind on each runway (kt). METAR direction is true."""
    pairs = {}
    for e in ends:
        key = "/".join(sorted([e.name, next(o.name for o in ends if o is not e and angle_diff(o.course, e.course + 180) < 10)]))
        pairs.setdefault(key, e.course)
    by_day = defaultdict(list)
    with open(metar_path) as f:
        for r in csv.DictReader(f):
            t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M")
            if t.hour not in DAYTIME_UTC or r["sknt"] in ("M", ""):
                continue
            spd = float(r["sknt"])
            d = float(r["drct"]) if r["drct"] not in ("M", "") else None
            by_day[t.date().isoformat()].append((d, spd))
    out = {}
    for day, obs in by_day.items():
        u = sum(s * math.sin(math.radians(d)) for d, s in obs if d is not None) / len(obs)
        v = sum(s * math.cos(math.radians(d)) for d, s in obs if d is not None) / len(obs)
        row = {"wind": f"{round(math.degrees(math.atan2(u, v)) % 360):03d}/{statistics.mean(s for _, s in obs):.0f}"}
        for key, course in pairs.items():
            xw = [abs(s * math.sin(math.radians(d - course))) for d, s in obs if d is not None]
            row[f"xw_{key}"] = round(statistics.mean(xw), 1) if xw else ""
        out[day] = row
    return out, sorted(pairs)


def make_plot(out_dir, apt, days, counts, end_names):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed, skipping plot")
        return
    fig, ax = plt.subplots(figsize=(16, 5))
    x = [dt.date.fromisoformat(d) for d in days]
    bottom = [0] * len(days)
    colors = plt.get_cmap("tab10")
    for i, e in enumerate(end_names):
        ys = [counts[d].get(("approach", e), 0) for d in days]
        ax.bar(x, ys, bottom=bottom, width=0.8, label=f"approaches to {e}", color=colors(i))
        bottom = [b + y for b, y in zip(bottom, ys)]
    ax.set_ylabel("approaches per day")
    ax.set_title(f"{apt.name}: fixed-wing approaches to land by runway end (UTC days)")
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    path = os.path.join(out_dir, "runway_use.png")
    fig.savefig(path, dpi=130)
    print(f"plot: {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--airport", default="KPYM", help="preset with runways (KPYM, KEWB, KGHG, KTAN)")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--step", type=int, default=1, help="sample every Nth day")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--region", default=cov.DEFAULT_REGION, choices=sorted(cov.REGIONS))
    ap.add_argument("--cache", default="adsb_cache")
    ap.add_argument("--metar", help="IEM asos.py CSV with valid, drct, sknt columns for the daytime wind summary")
    ap.add_argument("--out")
    args = ap.parse_args()

    name = args.airport.upper()
    cfg = cov.AIRPORTS.get(name)
    if not cfg or not cfg["runways"]:
        sys.exit(f"{name} needs a preset with runways in adsb_airport_coverage.AIRPORTS")
    apt = cov.Airport(name, cfg["lat"], cfg["lon"], cfg["elev_ft"], cfg["geoid_offset_ft"], cfg["runways"])
    ends = runway_ends(apt)
    end_names = [e.name for e in ends]
    region = cov.REGIONS[args.region]
    radius = cov.DEFAULT_RADIUS_NM
    cache_dir = os.path.join(args.cache, args.region)
    os.makedirs(cache_dir, exist_ok=True)

    s = dt.date.fromisoformat(args.start)
    e = dt.date.fromisoformat(args.end) if args.end else s
    days = [s + dt.timedelta(days=i) for i in range(0, (e - s).days + 1, args.step)]
    print(f"{apt.name}: {len(days)} day(s), {days[0]} to {days[-1]}, step {args.step}, {args.workers} worker(s)")

    points, done = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(cov.process_day, d, apt, radius, region, cache_dir) for d in days]
        for fut in as_completed(futures):
            day, pts, status = fut.result()
            print(f"  [{day}] {status}", flush=True)
            if pts is not None:
                points.extend(pts)
                done.append(day.isoformat())
    done.sort()
    if not points:
        sys.exit("No points found.")

    cov.estimate_agl(points, apt)
    passes = []
    for v in cov.build_visits(points):
        if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
            continue
        passes.extend(find_passes(v, apt, ends))
    passes.sort(key=lambda r: r["time_utc"])

    out_dir = args.out or f"runway_use_{apt.name}"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "passes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(passes[0]) if passes else ["date_utc"])
        w.writeheader()
        w.writerows(passes)

    counts = {d: Counter() for d in done}
    for r in passes:
        if r["date_utc"] in counts and (r["kind"] == "climb" or r["low"]):
            counts[r["date_utc"]][(r["kind"], r["runway"])] += 1
    wind, pair_keys = daytime_wind(args.metar, ends) if args.metar else ({}, [])

    fields = ["date_utc"] + [f"app_{n}" for n in end_names] + [f"climb_{n}" for n in end_names]
    fields += ["wind_daytime"] + [f"xw_{k}" for k in pair_keys] if args.metar else []
    rows = []
    for d in done:
        row = {"date_utc": d}
        for n in end_names:
            row[f"app_{n}"] = counts[d][("approach", n)]
            row[f"climb_{n}"] = counts[d][("climb", n)]
        if args.metar:
            wd = wind.get(d, {})
            row["wind_daytime"] = wd.get("wind", "")
            for k in pair_keys:
                row[f"xw_{k}"] = wd.get(f"xw_{k}", "")
        rows.append(row)
    with open(os.path.join(out_dir, "daily.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    hdr = "  date        " + "".join(f"{'app ' + n:>8s}" for n in end_names) + f"{'climbs':>8s}"
    if args.metar:
        hdr += "   wind     " + "".join(f"{'xw ' + k:>11s}" for k in pair_keys)
    print(f"\nFixed-wing approaches to land (down to {LOW_AGL_FT} ft AGL within {LOW_DIST_NM} nm) "
          "by runway end, UTC days\n" + hdr)
    for row in rows:
        line = f"  {row['date_utc']}" + "".join(f"{row['app_' + n]:8d}" for n in end_names)
        line += f"{sum(row['climb_' + n] for n in end_names):8d}"
        if args.metar:
            line += f"   {row['wind_daytime']:8s} " + "".join(f"{str(row['xw_' + k]):>11s}" for k in pair_keys)
        print(line)
    make_plot(out_dir, apt, done, counts, end_names)


if __name__ == "__main__":
    main()
