#!/usr/bin/env python3
"""
tower_compare.py

Compares operations detected from the ADS-B archive with FAA tower counts
(OPSNET Airport Operations) day by day, during tower hours only.

Detected operations use the frozen detector (ops_detector.py, v3): every
approach pass and every climb-out pass is one operation, so a touch-and-go or a
low approach counts two and a full stop or a departure counts one, as the tower
counts them. Fixed-wing aircraft only: helicopters rarely use the runways the
detector looks at, so their tower-counted operations are an expected shortfall
(rotorcraft visits are reported for context).

Input CSV columns: date (YYYY-MM-DD), facility (LWM, or several joined with +
for a combined export such as LWM+OWD+BED+EWB), total_ops (and optionally
itinerant_total, local_total).

Usage:
    python3 tower_compare.py reference/opsnet/opsnet_combined_LWM_OWD_BED_EWB_2026-03_07_08.csv --workers 24

Outputs (in --out, default ./tower_compare):
    daily.csv    detected approaches, climb-outs, operations, rotorcraft visits, tower total, per day
    summary.txt  overall ratio, daily correlation, and monthly ratios
"""

import argparse
import csv
import datetime as dt
import gzip
import json
import os
import statistics
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from zoneinfo import ZoneInfo

import adsb_airport_coverage as cov
import ops_detector as od
import runway_use as ru

LOCAL = ZoneInfo("America/New_York")
# Tower hours (local) from FAA NASR ATC_BASE, 2026-10-01 cycle. (24, 0) means midnight
# at the end of the day.
TOWER_HOURS = {
    "KLWM": lambda d: ((7, 0), (22, 0)),
    "KOWD": lambda d: ((7, 0), (22, 0)) if 5 <= d.month <= 10 else ((7, 0), (20, 0)),
    "KBED": lambda d: ((7, 0), (23, 0)),
    "KEWB": lambda d: ((6, 30), (22, 0)),
    "KBVY": lambda d: ((7, 0), (21, 0)) if (d.month, d.day) >= (5, 15) and d.month <= 10 else ((7, 0), (20, 0)),
    "KBDR": lambda d: ((6, 30), (22, 0)),
    "KDXR": lambda d: ((7, 0), (22, 0)),
    "KGON": lambda d: ((7, 0), (22, 0)),
    "KHFD": lambda d: ((6, 0), (24, 0)),
    "KHVN": lambda d: ((6, 0), (22, 0)),
    "KBAF": lambda d: ((7, 0), (22, 0)),
    "KORH": lambda d: ((6, 30), (21, 0)),
}
_NASR_AIRPORTS = {}
CACHES = ("new_england", "se_new_england")


def make_airport(name):
    """Preset from adsb_airport_coverage.AIRPORTS, or built from FAA NASR runway ends."""
    if name in cov.AIRPORTS:
        c = cov.AIRPORTS[name]
        apt = cov.Airport(name, c["lat"], c["lon"], c["elev_ft"], c["geoid_offset_ft"], c["runways"])
    else:
        if name not in _NASR_AIRPORTS:
            import rank_airports as ra
            cands = ra.load_candidates(ra.NASR_DEFAULT, ra.AWOS_DEFAULT, 0, 99999, {name[1:]})
            c = next(x for x in cands if x["id"] == name[1:])
            _NASR_AIRPORTS[name] = c
        c = _NASR_AIRPORTS[name]
        apt = cov.Airport(name, c["lat"], c["lon"], c["elev_ft"], 93.5, c["rwy_geom"])
    apt.radius = cov.DEFAULT_RADIUS_NM
    return apt


def local_ts(d, hm):
    h, m = hm
    if (h, m) == (24, 0):
        nd = d + dt.timedelta(days=1)
        return dt.datetime(nd.year, nd.month, nd.day, 0, 0, tzinfo=LOCAL).timestamp()
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=LOCAL).timestamp()


def cache_path(day):
    for region in CACHES:
        p = os.path.join("adsb_cache", region, f"{day}.jsonl.gz")
        if os.path.exists(p):
            return p
    return None


def count_day(args):
    """Detected operations during tower hours on one local date, for each airport."""
    local_date, names = args
    d = dt.date.fromisoformat(local_date)
    apts = {n: make_airport(n) for n in names}
    boxes = {n: cov.geofence_box(a, cov.DEFAULT_RADIUS_NM) for n, a in apts.items()}
    pts = {n: defaultdict(list) for n in names}  # airport -> UTC day -> points
    missing = []
    for utc_day in (d, d + dt.timedelta(days=1)):  # tower hours run past midnight UTC
        path = cache_path(utc_day)
        if not path:
            missing.append(str(utc_day))
            continue
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
                    pts[n][utc_day].extend(cov.extract_points(trace, apts[n], cov.DEFAULT_RADIUS_NM))
    out = {}
    for n, apt in apts.items():
        allp = []
        for day_pts in pts[n].values():
            cov.estimate_agl(day_pts, apt)
            allp.extend(day_pts)
        opening, closing = TOWER_HOURS[n](d)
        t_open, t_close = local_ts(d, opening), local_ts(d, closing)
        ends = ru.runway_ends(apt)
        app = clb = rotor = 0
        for v in cov.build_visits(allp) if allp else []:
            if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
                if t_open <= v[0]["t"] < t_close and any(p["agl_ft"] is not None and p["agl_ft"] < 500
                                                         and p["dist_arp_nm"] < 1.0 for p in v):
                    rotor += 1
                continue
            a = od.arrays_from_points(v, apt)
            for p in od.detect(a, ends):
                t = a["t"][p["i0"]]
                if t_open <= t < t_close:
                    app += p["kind"] == "approach"
                    clb += p["kind"] == "climb"
        out[n] = {"approaches": app, "climbs": clb, "ops": app + clb, "rotorcraft_visits": rotor}
    return local_date, out, missing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("opsnet_csv")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--out", default="tower_compare")
    args = ap.parse_args()

    tower = list(csv.DictReader(open(args.opsnet_csv)))
    facilities = sorted({r["facility"] for r in tower})
    names = sorted({"K" + f for fac in facilities for f in fac.split("+")})
    dates = sorted({r["date"] for r in tower})
    print(f"{len(dates)} dates, facilities {', '.join(facilities)}, airports {', '.join(names)}")

    detected, missing_days = {}, set()
    with ProcessPoolExecutor(args.workers) as ex:
        for local_date, out, missing in ex.map(count_day, [(d, names) for d in dates]):
            detected[local_date] = out
            missing_days.update(missing)

    os.makedirs(args.out, exist_ok=True)
    rows = []
    for r in tower:
        parts = ["K" + f for f in r["facility"].split("+")]
        det = detected.get(r["date"], {})
        if not all(p in det for p in parts):
            continue
        row = {"date": r["date"], "facility": r["facility"], "tower_ops": int(r["total_ops"])}
        for k in ("approaches", "climbs", "ops", "rotorcraft_visits"):
            row[f"detected_{k}"] = sum(det[p][k] for p in parts)
        for p in parts:
            row[f"ops_{p}"] = det[p]["ops"]
        rows.append(row)
    fields = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    with open(os.path.join(args.out, "daily.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or ["date"], restval="")
        w.writeheader()
        w.writerows(rows)

    lines = []
    for fac in facilities:
        rs = [r for r in rows if r["facility"] == fac]
        if not rs:
            continue
        tw = sum(r["tower_ops"] for r in rs)
        de = sum(r["detected_ops"] for r in rs)
        corr = statistics.correlation([r["tower_ops"] for r in rs], [r["detected_ops"] for r in rs]) if len(rs) > 2 else float("nan")
        lines += [f"{fac}: {len(rs)} days, tower ops {tw:,}, detected ops {de:,}, detected / tower {de / tw:.3f}, "
                  f"daily correlation {corr:.3f}",
                  f"  detected approaches {sum(r['detected_approaches'] for r in rs):,}, climb-outs {sum(r['detected_climbs'] for r in rs):,}, "
                  f"rotorcraft visits near the field {sum(r['detected_rotorcraft_visits'] for r in rs):,}",
                  "  by airport (detected ops): " + ", ".join(
                      f"{p} {sum(r.get('ops_' + p, 0) for r in rs):,}" for p in ["K" + x for x in fac.split("+")]),
                  "  month     days   tower    detected  ratio"]
        by_month = defaultdict(list)
        for r in rs:
            by_month[r["date"][:7]].append(r)
        for m, g in sorted(by_month.items()):
            t = sum(r["tower_ops"] for r in g)
            dd = sum(r["detected_ops"] for r in g)
            lines.append(f"  {m}  {len(g):5d}  {t:7,d}  {dd:9,d}  {dd / t if t else float('nan'):.3f}")
        lines.append("")
    if missing_days:
        lines.append("Days missing from the cache: " + ", ".join(sorted(missing_days)))
    text = "\n".join(lines)
    with open(os.path.join(args.out, "summary.txt"), "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
