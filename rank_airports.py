#!/usr/bin/env python3
"""
rank_airports.py

Scores candidate airports for the study from the regional ADS-B cache built by
adsb_airport_coverage.py. No downloads: only days already in the cache are used.

Candidates come from FAA NASR (APT, AWOS, and runway-end CSVs): public-use
airports within --max-nm of the Boston Logan ARP (the Mode C veil is 30 nm)
with at least one paved runway of --min-rwy-ft or more, plus any --extra IDs.
Runway geometry comes from NASR runway ends, so no presets are needed.

Per airport, over the cached days (fixed-wing only, rotorcraft category A7 excluded):
    arrivals/day      airport-traffic visits per day (descending below 1,500 ft AGL within
                      3 nm of a runway end, as in adsb_airport_coverage.py). Does not need
                      low coverage, so it is the fairer traffic measure across airports
    approaches/day    approaches to land per day. Needs data down to 400 ft, so it is a
                      lower bound where cov300 is poor (runway_use.py rules: aligned with a
                      runway end, down to 400 ft AGL within 0.75 nm of the threshold)
    trainer share     share of those approaches flown by common training types
                      (a proxy: private owners fly these types too)
    repeat share      share of approaches that follow an earlier approach in the same
                      visit, a pattern-work signal (touch-and-goes, circuits)
    top5 share        share of approaches flown by the five busiest aircraft, a
                      fleet-concentration signal (a school fleet shows up here)
    uat share         share of approaches seen mainly via ADS-R (UAT aircraft)
    cov300            share of airport-traffic visits whose data reaches 300 ft AGL
                      (same definition as adsb_airport_coverage.py)
With the FAA registry lookup (faa_registry.py) built, also:
    resolved          share of approaches whose aircraft is in the US registry on that date
    piston            share of resolved approaches flown by piston fixed-wing aircraft
    fleet             share of piston approaches flown by fleet-registered aircraft
                      (schools, clubs, rental), the rest being private or trust
    top fleet         the fleet operator with the most piston approaches, and its share

Usage:
    python3 rank_airports.py --start 2026-09-07 --end 2026-09-30 --workers 24
    python3 rank_airports.py --start 2026-07-18 --end 2026-09-30 --workers 24 --extra EWB

Outputs (in --out, default ./airport_ranking):
    ranking.csv   one row per airport with the metrics above and NASR attributes
"""

import argparse
import csv
import datetime as dt
import gzip
import io
import json
import math
import os
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import adsb_airport_coverage as cov
import faa_registry as fr
import runway_use as ru

NASR_DEFAULT = "reference/nasr/01_Oct_2026_APT_CSV.zip"
AWOS_DEFAULT = "reference/nasr/01_Oct_2026_AWOS_CSV.zip"
TRAINER_TYPES = {
    "C150", "C152", "C162", "C172", "P28A", "P28B", "P28R", "PA38",
    "DV20", "DA40", "DA42", "SR20", "BE76", "PA44", "RV12",
}
PAVED = ("ASPH", "CONC")


def nasr_rows(zip_path, name):
    with zipfile.ZipFile(zip_path).open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, "latin-1"))


def gc_nm(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * math.asin(math.sqrt(h)) * 3440.065


def load_candidates(nasr, awos, max_nm, min_rwy_ft, extra):
    base = {r["ARPT_ID"]: r for r in nasr_rows(nasr, "APT_BASE.csv")}
    bos = (float(base["BOS"]["LAT_DECIMAL"]), float(base["BOS"]["LONG_DECIMAL"]))
    rwys = defaultdict(list)
    for r in nasr_rows(nasr, "APT_RWY.csv"):
        rwys[r["ARPT_ID"]].append(r)
    ends = defaultdict(dict)
    for r in nasr_rows(nasr, "APT_RWY_END.csv"):
        if r["LAT_DECIMAL"] and r["LONG_DECIMAL"]:
            ends[(r["ARPT_ID"], r["RWY_ID"])][r["RWY_END_ID"]] = (float(r["LAT_DECIMAL"]), float(r["LONG_DECIMAL"]))
    wx = {}
    for r in nasr_rows(awos, "AWOS.csv"):
        wx.setdefault(r["ASOS_AWOS_ID"], r["ASOS_AWOS_TYPE"])

    out = []
    for aid, r in base.items():
        if aid == "BOS" or r["SITE_TYPE_CODE"] != "A" or r["ARPT_STATUS"] != "O":
            continue
        pos = (float(r["LAT_DECIMAL"]), float(r["LONG_DECIMAL"]))
        d_bos = gc_nm(bos, pos)
        paved = [x for x in rwys[aid] if x["SURFACE_TYPE_CODE"].startswith(PAVED)
                 and x["RWY_LEN"] and int(x["RWY_LEN"]) >= min_rwy_ft]
        if aid not in extra and (r["FACILITY_USE_CODE"] != "PU" or d_bos > max_nm or not paved):
            continue
        runways = {}
        for x in rwys[aid]:
            e = ends.get((aid, x["RWY_ID"]), {})
            names = x["RWY_ID"].split("/")
            if len(names) == 2 and all(n in e for n in names) and x["SURFACE_TYPE_CODE"].startswith(PAVED):
                runways[x["RWY_ID"]] = [e[names[0]], e[names[1]]]
        if not runways:
            continue
        out.append({
            "id": aid, "name": r["ARPT_NAME"].title(), "nm_from_bos": round(d_bos, 1),
            "tower": "yes" if r["TWR_TYPE_CODE"] == "ATCT" else "no", "weather": wx.get(aid, "none"),
            "runways": " ".join(f'{x["RWY_ID"]}:{x["RWY_LEN"]}' for x in rwys[aid]),
            "lat": pos[0], "lon": pos[1], "elev_ft": float(r["ELEV"]), "rwy_geom": runways,
        })
    return out


def make_airport(c):
    apt = cov.Airport(c["id"], c["lat"], c["lon"], c["elev_ft"], 93.5, c["rwy_geom"])
    apt.radius = cov.DEFAULT_RADIUS_NM
    return apt


def process_day(path, cands):
    day = os.path.basename(path)[:10]
    """One cached day: per-airport visit and approach records. Runs in a worker process."""
    apts = [make_airport(c) for c in cands]
    boxes = [cov.geofence_box(a, cov.DEFAULT_RADIUS_NM) for a in apts]
    pts_by_apt = defaultdict(list)
    with gzip.open(path, "rt") as f:
        for line in f:
            trace = json.loads(line)
            lats = [p[1] for p in trace["trace"] if p[1] is not None]
            lons = [p[2] for p in trace["trace"] if p[2] is not None]
            if not lats:
                continue
            la0, la1, lo0, lo1 = min(lats), max(lats), min(lons), max(lons)
            for apt, ((bla0, bla1), (blo0, blo1)) in zip(apts, boxes):
                if la1 < bla0 or la0 > bla1 or lo1 < blo0 or lo0 > blo1:
                    continue
                pts_by_apt[apt.name].extend(cov.extract_points(trace, apt, cov.DEFAULT_RADIUS_NM))

    result = {}
    for apt in apts:
        pts = pts_by_apt.get(apt.name)
        if not pts:
            result[apt.name] = {"visits": [], "approaches": []}
            continue
        cov.estimate_agl(pts, apt)
        ends = ru.runway_ends(apt)
        visits_out, apps_out = [], []
        for i, v in enumerate(cov.build_visits(pts)):
            if any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
                continue
            s = cov.summarize_visit(v)
            if s["airport_ops"]:
                visits_out.append(s["lowest_agl_ft"] if s["lowest_agl_ft"] != "" else None)
            for k, ps in enumerate([x for x in ru.find_passes(v, apt, ends) if x["low"]]):
                apps_out.append({"icao": ps["icao"], "type": ps["type"], "source": ps["source"],
                                 "squawk": ps["squawk"], "repeat": k > 0, "date": day})
        result[apt.name] = {"visits": visits_out, "approaches": apps_out}
    return result


def share(n, d):
    return round(100.0 * n / d, 1) if d else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-nm", type=float, default=30.5, help="max distance from BOS ARP")
    ap.add_argument("--min-rwy-ft", type=int, default=2000, help="min paved runway length")
    ap.add_argument("--extra", default="EWB", help="comma-separated NASR IDs to include regardless of filters")
    ap.add_argument("--nasr", default=NASR_DEFAULT)
    ap.add_argument("--awos", default=AWOS_DEFAULT)
    ap.add_argument("--region", default=cov.DEFAULT_REGION, choices=sorted(cov.REGIONS))
    ap.add_argument("--cache", default="adsb_cache")
    ap.add_argument("--out", default="airport_ranking")
    args = ap.parse_args()

    extra = {x.strip().upper() for x in args.extra.split(",") if x.strip()}
    cands = load_candidates(args.nasr, args.awos, args.max_nm, args.min_rwy_ft, extra)
    region = cov.REGIONS[args.region]
    cands = [c for c in cands if cov.region_covers(region, make_airport(c), cov.DEFAULT_RADIUS_NM)]
    cache_dir = os.path.join(args.cache, args.region)
    s, e = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    days = [s + dt.timedelta(days=i) for i in range((e - s).days + 1)]
    paths = [(d, os.path.join(cache_dir, f"{d}.jsonl.gz")) for d in days]
    missing = [d for d, p in paths if not os.path.exists(p)]
    paths = [(d, p) for d, p in paths if os.path.exists(p)]
    print(f"{len(cands)} airports: {', '.join(c['id'] for c in cands)}")
    print(f"{len(paths)} cached day(s) in {args.start}..{args.end}"
          + (f", {len(missing)} not cached and skipped" if missing else ""))

    visits, apps = defaultdict(list), defaultdict(list)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process_day, p, cands): d for d, p in paths}
        for fut in as_completed(futures):
            for aid, r in fut.result().items():
                visits[aid].extend(r["visits"])
                apps[aid].extend(r["approaches"])

    n_days = len(paths)
    use_reg = os.path.exists(fr.OUT_DEFAULT)
    rows = []
    for c in cands:
        a, v = apps[c["id"]], visits[c["id"]]
        per_ac = Counter(x["icao"] for x in a)
        reg = {}
        if use_reg:
            recs = [fr.lookup(x["icao"], x["date"]) for x in a]
            resolved = [r for r in recs if r]
            piston = [r for r in resolved if r["piston_fixed_wing"] and r["ownership"] != "commercial"]
            fleet = [r for r in piston if r["ownership"] == "fleet"]
            top = Counter(r["operator"] for r in fleet).most_common(1)
            reg = {"resolved": share(len(resolved), len(a)), "piston": share(len(piston), len(resolved)),
                   "fleet": share(len(fleet), len(piston)),
                   "top_fleet": f"{top[0][0].title()} ({share(top[0][1], len(piston))}%)" if top else ""}
        rows.append({
            "id": c["id"], "name": c["name"], "nm_from_bos": c["nm_from_bos"],
            "tower": c["tower"], "weather": c["weather"], "runways": c["runways"],
            "days": n_days,
            "arrivals_per_day": round(len(v) / n_days, 1) if n_days else "",
            "approaches_per_day": round(len(a) / n_days, 1) if n_days else "",
            "trainer_share": share(sum(x["type"] in TRAINER_TYPES for x in a), len(a)),
            "repeat_share": share(sum(x["repeat"] for x in a), len(a)),
            "top5_share": share(sum(n for _, n in per_ac.most_common(5)), len(a)),
            "aircraft": len(per_ac),
            "vfr1200_share": share(sum(x["squawk"] == "1200" for x in a), len(a)),
            "uat_share": share(sum(x["source"] == "adsr_icao" for x in a), len(a)),
            "cov300": share(sum(1 for x in v if x is not None and x <= 300), len(v)),
            "top_types": " ".join(f"{t}:{n}" for t, n in Counter(x["type"] for x in a).most_common(4)),
            **reg,
        })
    rows.sort(key=lambda r: -(r["arrivals_per_day"] or 0))

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "ranking.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"\n{'id':5s} {'nm':>5s} {'twr':>4s} {'weather':>9s} {'arr/day':>8s} {'app/day':>8s} {'trainer':>8s} "
          f"{'repeat':>7s} {'top5':>6s} {'ac':>5s} {'uat':>6s} {'cov300':>7s}  top types")
    for r in rows:
        print(f"{r['id']:5s} {r['nm_from_bos']:5.1f} {r['tower']:>4s} {r['weather']:>9s} "
              f"{r['arrivals_per_day']:8} {r['approaches_per_day']:8} {str(r['trainer_share']):>7s}% {str(r['repeat_share']):>6s}% "
              f"{str(r['top5_share']):>5s}% {r['aircraft']:5d} {str(r['uat_share']):>5s}% {str(r['cov300']):>6s}%  "
              f"{r['top_types']}")
    if use_reg:
        print(f"\n{'id':5s} {'resolved':>9s} {'piston':>7s} {'fleet':>6s}  top fleet operator (share of piston approaches)")
        for r in rows:
            print(f"{r['id']:5s} {str(r['resolved']):>8s}% {str(r['piston']):>6s}% {str(r['fleet']):>5s}%  {r['top_fleet']}")


if __name__ == "__main__":
    main()
