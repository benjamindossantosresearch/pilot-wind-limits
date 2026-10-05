#!/usr/bin/env python3
"""
wind_activity.py

Pilot-study check for Q1a: does arrival activity fall off as the crosswind on
the best available runway rises, relative to normal demand for that hour of day
and type of day? Uses the regional ADS-B cache (days missing from it are
streamed and cached) and an IEM METAR export for the airport.

Rules, fixed before looking at results (see notes/decisions.md):
    unit            local clock hour, daytime only (--hours, default 08 to 18 local)
    arrivals        fixed-wing visits (rotorcraft category A7 excluded) with at least
                    one runway-aligned approach pass (runway_use.py rules, no minimum
                    height, so coverage near the ground does not matter), counted in
                    the hour of the first approach pass
    weather         the METAR closest to the middle of the hour (within 40 minutes)
    VMC             ceiling (lowest BKN, OVC, or VV) at least 3,000 ft or none,
                    visibility at least 5 SM, no precipitation or thunderstorm
                    reported at the field. Non-VMC hours are dropped
    best_xw         crosswind component of the sustained wind on the runway end
                    with the smallest crosswind among ends with zero or positive
                    headwind (kt). Calm counts as 0. Variable direction is dropped
    gust_xw         the same with the gust speed when a gust is reported, else best_xw
    baseline        mean arrivals for the same local hour of day and day type
                    (weekday or weekend) across all VMC hours in the window
    ratio           arrivals / baseline for each hour
    aircraft        piston fixed-wing only, identified through the FAA registry on the
                    flight date (faa_registry.py). Scheduled commercial operators and
                    aircraft not in the US registry are dropped. --all-aircraft turns
                    the filter off
    groups          the table is repeated for fleet and private aircraft, each against
                    its own baseline (trust-registered aircraft count in "all" only)

Usage:
    python3 wind_activity.py --airport KLWM --start 2026-03-01 --end 2026-03-31 \\
        --metar weather/LWM_metar_2025-01-01_2026-09-30.csv --workers 24

Outputs (in --out, default ./wind_activity_<airport>_<start>_<end>):
    hours.csv       one row per daytime VMC hour with weather, crosswind, arrivals, ratio
    summary.txt     mean ratio and arrivals by crosswind band, sustained and gust
"""

import argparse
import bisect
import csv
import datetime as dt
import math
import os
import re
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from zoneinfo import ZoneInfo

import adsb_airport_coverage as cov
import faa_registry as fr
import runway_use as ru

LOCAL = ZoneInfo("America/New_York")
VMC_CEILING_FT = 3000
VMC_VIS_SM = 5.0
BANDS = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 99)]
PRECIP = re.compile(r"(?<![A-Z])(?:[-+]|VC)?(?:TS|SH|FZ)?(?:DZ|RA|SN|SG|IC|PL|GR|GS|UP)|(?<![A-Z])[-+]?TS(?![A-Z])")


def parse_metar(text):
    """Returns (ceiling ft or None for no ceiling, visibility SM or None, precip bool)."""
    body = text.split(" RMK")[0]
    vis = None
    m = re.search(r"\s(?:(\d+)\s)?M?(\d+)/(\d+)SM", body)
    if m:
        vis = (int(m.group(1)) if m.group(1) else 0) + int(m.group(2)) / int(m.group(3))
    else:
        m = re.search(r"\s(\d+)SM", body)
        if m:
            vis = float(m.group(1))
    layers = [int(h) * 100 for h in re.findall(r"\s(?:BKN|OVC|VV)(\d{3})", body)]
    ceiling = min(layers) if layers else None
    # Present weather sits between the visibility and the sky groups
    wx_zone = re.split(r"\s(?:FEW|SCT|BKN|OVC|VV|CLR|SKC)\d{0,3}", body, maxsplit=1)[0]
    wx_zone = re.sub(r"^.*?SM", "", wx_zone)
    precip = any(not m.group(0).startswith("VC") for m in PRECIP.finditer(wx_zone))
    return ceiling, vis, precip


def load_metars(path):
    obs = []
    with open(path) as f:
        for r in csv.DictReader(f):
            t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
            num = lambda k: float(r[k]) if r.get(k) not in (None, "", "M") else None
            ceiling, vis, precip = parse_metar(r["metar"])
            obs.append({"t": t, "drct": num("drct"), "sknt": num("sknt"), "gust": num("gust"),
                        "ceiling": ceiling, "vis": vis, "precip": precip, "metar": r["metar"]})
    obs.sort(key=lambda o: o["t"])
    return obs


def best_crosswind(drct, spd, ends):
    if spd is None:
        return None
    if spd == 0:
        return 0.0
    if drct is None:
        return None
    best = None
    for e in ends:
        theta = math.radians(drct - e.course)
        if spd * math.cos(theta) >= 0:
            xw = abs(spd * math.sin(theta))
            best = xw if best is None else min(best, xw)
    return best


def band_of(x):
    return next(f"{a}-{b - 1}" if b < 99 else f"{a}+" for a, b in BANDS if a <= x < b)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--airport", required=True, help="preset with runways")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--metar", required=True, help="IEM asos.py CSV with valid, metar, drct, sknt, gust")
    ap.add_argument("--hours", default="8-18", help="local hours to keep, inclusive, e.g. 8-18")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--region", default=cov.DEFAULT_REGION, choices=sorted(cov.REGIONS))
    ap.add_argument("--cache", default="adsb_cache")
    ap.add_argument("--all-aircraft", action="store_true", help="skip the registry piston filter")
    ap.add_argument("--out")
    args = ap.parse_args()

    name = args.airport.upper()
    cfg = cov.AIRPORTS.get(name)
    if not cfg or not cfg["runways"]:
        sys.exit(f"{name} needs a preset with runways")
    apt = cov.Airport(name, cfg["lat"], cfg["lon"], cfg["elev_ft"], cfg["geoid_offset_ft"], cfg["runways"])
    ends = ru.runway_ends(apt)
    h0, h1 = (int(x) for x in args.hours.split("-"))
    region = cov.REGIONS[args.region]
    cache_dir = os.path.join(args.cache, args.region)
    s, e = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    days = [s + dt.timedelta(days=i) for i in range((e - s).days + 1)]

    points = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(cov.process_day, d, apt, cov.DEFAULT_RADIUS_NM, region, cache_dir) for d in days]
        for fut in as_completed(futures):
            day, pts, status = fut.result()
            if pts is None:
                print(f"  [{day}] {status}")
            else:
                points.extend(pts)
    cov.estimate_agl(points, apt)

    # Arrivals by local hour, overall and by ownership group
    arrivals = {g: defaultdict(int) for g in ("all", "fleet", "private")}
    dropped = defaultdict(int)
    for v in cov.build_visits(points):
        if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
            continue
        apps = [x for x in ru.find_passes(v, apt, ends) if x["kind"] == "approach"]
        if not apps:
            continue
        t = dt.datetime.fromisoformat(apps[0]["time_utc"]).astimezone(LOCAL)
        hour = t.replace(minute=0, second=0, microsecond=0)
        group = None
        if not args.all_aircraft:
            rec = fr.lookup(v[0]["icao"], t.astimezone(dt.timezone.utc).date())
            if rec is None:
                dropped["not in US registry"] += 1
                continue
            if not rec["piston_fixed_wing"] or rec["ownership"] == "commercial":
                dropped["not piston GA"] += 1
                continue
            group = rec["ownership"] if rec["ownership"] in ("fleet", "private") else None
        arrivals["all"][hour] += 1
        if group:
            arrivals[group][hour] += 1

    # Weather per local hour
    metars = load_metars(args.metar)
    times = [o["t"] for o in metars]
    hours = []
    for d in days:
        for h in range(h0, h1 + 1):
            lt = dt.datetime(d.year, d.month, d.day, h, tzinfo=LOCAL)
            mid = (lt + dt.timedelta(minutes=30)).astimezone(dt.timezone.utc)
            i = bisect.bisect_left(times, mid)
            cand = [metars[j] for j in (i - 1, i) if 0 <= j < len(metars)]
            o = min(cand, key=lambda c: abs((c["t"] - mid).total_seconds()), default=None)
            if o is None or abs((o["t"] - mid).total_seconds()) > 40 * 60:
                continue
            vmc = ((o["ceiling"] is None or o["ceiling"] >= VMC_CEILING_FT)
                   and o["vis"] is not None and o["vis"] >= VMC_VIS_SM and not o["precip"])
            xw = best_crosswind(o["drct"], o["sknt"], ends)
            gxw = best_crosswind(o["drct"], o["gust"], ends) if o["gust"] else xw
            hours.append({"local_hour": lt.isoformat(timespec="minutes"), "weekend": lt.weekday() >= 5,
                          "hod": h, "vmc": vmc, "drct": o["drct"], "sknt": o["sknt"], "gust": o["gust"],
                          "ceiling_ft": o["ceiling"], "vis_sm": o["vis"], "best_xw": xw, "gust_xw": gxw,
                          "arrivals": arrivals["all"].get(lt, 0),
                          "arrivals_fleet": arrivals["fleet"].get(lt, 0),
                          "arrivals_private": arrivals["private"].get(lt, 0), "metar": o["metar"]})

    keep = [r for r in hours if r["vmc"] and r["best_xw"] is not None]
    for suffix in ("", "_fleet", "_private"):
        base = defaultdict(list)
        for r in keep:
            base[(r["hod"], r["weekend"])].append(r["arrivals" + suffix])
        base = {k: statistics.mean(v) for k, v in base.items()}
        for r in keep:
            b = base[(r["hod"], r["weekend"])]
            r["baseline" + suffix] = round(b, 2)
            r["ratio" + suffix] = round(r["arrivals" + suffix] / b, 3) if b > 0 else ""

    out_dir = args.out or f"wind_activity_{name}_{args.start}_{args.end}"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "hours.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(hours[0]) + ["baseline", "ratio", "baseline_fleet", "ratio_fleet",
                                                           "baseline_private", "ratio_private"], extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(hours, key=lambda r: r["local_hour"]))

    def table(key, label, suffix=""):
        """Mean ratio by band. SE is clustered by day: hours are averaged within each day first."""
        lines = [f"By {label} (kt), daytime VMC hours",
                 "  band     hours  days  arrivals/hr  ratio to normal demand (day mean +/- 1.96 SE)"]
        groups = defaultdict(list)
        for r in keep:
            if r["ratio" + suffix] != "":
                groups[band_of(r[key])].append(r)
        for a, b in BANDS:
            k = f"{a}-{b - 1}" if b < 99 else f"{a}+"
            g = groups.get(k, [])
            if not g:
                continue
            by_day = defaultdict(list)
            for r in g:
                by_day[r["local_hour"][:10]].append(r["ratio" + suffix])
            day_means = [statistics.mean(v) for v in by_day.values()]
            m = statistics.mean(day_means)
            se = statistics.stdev(day_means) / math.sqrt(len(day_means)) if len(day_means) > 1 else float("nan")
            lines.append(f"  {k:7s} {len(g):6d} {len(day_means):5d}  "
                         f"{statistics.mean(r['arrivals' + suffix] for r in g):11.2f}  {m:5.2f} +/- {1.96 * se:4.2f}")
        return lines

    n_all = len(hours)
    filt = "all fixed-wing" if args.all_aircraft else "piston fixed-wing GA (FAA registry)"
    lines = [f"{name} arrivals vs crosswind, {args.start} to {args.end}, local hours {h0:02d}-{h1:02d}, {filt}",
             f"Hours with a METAR: {n_all}, VMC with usable wind: {len(keep)}, "
             f"arrivals in those hours: {sum(r['arrivals'] for r in keep)} "
             f"(fleet {sum(r['arrivals_fleet'] for r in keep)}, private {sum(r['arrivals_private'] for r in keep)})"]
    if dropped:
        lines.append("Dropped arrivals: " + ", ".join(f"{k} {v}" for k, v in dropped.items()))
    lines += [""] + table("best_xw", "best-runway crosswind, sustained") + [""] + table("gust_xw", "best-runway crosswind, gust")
    if not args.all_aircraft:
        lines += [""] + table("best_xw", "best-runway crosswind, sustained, FLEET aircraft", "_fleet")
        lines += [""] + table("best_xw", "best-runway crosswind, sustained, PRIVATE aircraft", "_private")
    text = "\n".join(lines)
    with open(os.path.join(out_dir, "summary.txt"), "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
