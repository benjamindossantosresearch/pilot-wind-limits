#!/usr/bin/env python3
"""
us_tower_spotcheck_days.py

Third step of the tower-count spot check: a day-level look at a random sample
of compared airport-days, parsing the full archive (adsb_cache/us_airports) so
rotorcraft and every visit are included, not only the extracts' approach visits.

Per airport-day, during tower hours:
  * detected fixed-wing operations exactly as us_tower_compare.py (v3.0.1)
  * traverse passes that repeat a pass on a same-direction parallel runway
    (see us_tower_spotcheck_traverse.py)
  * rotorcraft (emitter category A7, or a helicopter type designator):
    visits, and touchdowns plus liftoffs within 0.6 nm of the runways or the
    airport reference point (one operation each)
  * fixed-wing touchdowns and liftoffs over a runway that no detected pass
    covers (missed operations among the aircraft the archive sees low)

    python3 us_tower_spotcheck_days.py --days 24 --workers 24

Writes us_tower_compare/spotcheck_days.csv and us_tower_compare/spotcheck_days.txt.
"""

import argparse
import csv
import datetime as dt
import gzip
import json
import os
import random
from collections import defaultdict

import adsb_airport_coverage as cov
import ops_detector as od
import runway_use as ru
import us_airports as ua
import us_tower_compare as tc
from us_tower_spotcheck import compared_days

AIRPORTS = ("FTW", "SUS", "APA", "HWO", "DTO", "FFZ")
CACHE = "adsb_cache/us_airports"
OUT = "us_tower_compare"
HELI_TYPES = {"R22", "R44", "R66", "B06", "B06T", "B407", "B412", "B429", "B505", "B212", "B222", "B230", "B427", "B430",
              "EC20", "EC30", "EC35", "EC45", "EC55", "EC75", "AS32", "AS50", "AS55", "AS65", "H500", "H60", "S76", "S92",
              "A109", "A119", "A139", "A169", "A189", "BK17", "MD52", "MD60", "MD90", "EN28", "EN48", "H269", "S300",
              "UH1", "UH1Y", "H47", "H64", "H72", "EH10", "CH47", "H160", "H125", "H130", "H135", "H145", "GAZL", "ALO3", "ALO2"}
LOW_FT, HIGH_FT = 100, 200


def near_field(apt, ends, x, y):
    if x * x + y * y <= 0.6 ** 2:
        return True
    for e in ends:
        along, lat = e.along_lateral(x, y)
        if -0.6 <= along <= e.length + 0.6 and lat <= 0.6:
            return True
    return False


def over_runway(ends, x, y, past=0.0):
    for e in ends:
        along, lat = e.along_lateral(x, y)
        if -0.3 <= along <= e.length + past and lat <= 0.3:
            return True
    return False


def events(v, apt, ends, fixed_wing):
    """Touchdowns (airborne above HIGH_FT then at or below LOW_FT) and liftoffs (the reverse), with times."""
    out = []
    state, t_state = None, None
    for p in v:
        h = 0 if p["on_ground"] else p["agl_ft"]
        if h is None:
            continue
        x, y = cov.to_xy_nm(p["lat"], p["lon"], apt.lat, apt.lon)
        here = over_runway(ends, x, y, past=0.3) if fixed_wing else near_field(apt, ends, x, y)
        if h <= LOW_FT and here:
            if state == "air":
                out.append(("touchdown", p["t"]))
            state = "low"
        elif h > HIGH_FT:
            if state == "low":
                out.append(("liftoff", p["t"]))
            state = "air"
    return out


def day_job(local_date):
    d = dt.date.fromisoformat(local_date)
    sites = ua.load()
    apts = {a: sites[a].apt for a in AIRPORTS}
    boxes = {a: cov.geofence_box(apt, cov.DEFAULT_RADIUS_NM) for a, apt in apts.items()}
    pts = {a: defaultdict(list) for a in AIRPORTS}
    for utc_day in (d, d + dt.timedelta(days=1)):
        path = os.path.join(CACHE, f"{utc_day}.jsonl.gz")
        if not os.path.exists(path):
            return local_date, None
        with gzip.open(path, "rt") as f:
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
                    pts[a][utc_day].extend(cov.extract_points(tr, apts[a], cov.DEFAULT_RADIUS_NM))
    out = {}
    for a, apt in apts.items():
        allp = []
        for day_pts in pts[a].values():   # heights per UTC day, as in us_tower_compare.count_day
            if day_pts:
                cov.estimate_agl(day_pts, apt)
                allp.extend(day_pts)
        tz = sites[a].tz
        opening, closing = tc.tower_hours(a, d)
        t_open, t_close = tc.local_ts(d, opening, tz), tc.local_ts(d, closing, tz)
        ends = ru.runway_ends(apt)
        r = defaultdict(int)
        for v in cov.build_visits(allp) if allp else []:
            heli = any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v) or (v[0]["type"] or "") in HELI_TYPES
            if heli:
                ev = [e for e in events(v, apt, ends, False) if t_open <= e[1] < t_close]
                if ev or any(p["agl_ft"] is not None and p["agl_ft"] <= 300 for p in v):
                    r["heli_visits"] += 1
                r["heli_events"] += len(ev)
                if not any(p["category"] == cov.ROTORCRAFT_CATEGORY for p in v):
                    # helicopter by type but not by emitter category: the pipeline treats it as fixed-wing
                    arr = od.arrays_from_points(v, apt)
                    r["heli_counted_as_fw"] += sum(1 for p in od.detect(arr, ends) if t_open <= arr["t"][p["i0"]] < t_close)
                continue
            arr = od.arrays_from_points(v, apt)
            passes = od.detect(arr, ends)
            t = arr["t"]
            for p in passes:
                if not (t_open <= t[p["i0"]] < t_close):
                    continue
                r["fw_ops"] += 1
                if p["inferred"] == "traverse":
                    E = next(e for e in ends if e.name == p["runway"])
                    par = {e.name for e in ends if e.name != E.name and ru.angle_diff(e.course, E.course) <= 20}
                    i = p["i0"] if p["kind"] == "approach" else p["i0"] - 1
                    j = min(i + 1, len(t) - 1)
                    if any(o["kind"] == p["kind"] and o["runway"] in par and o["inferred"] != "traverse"
                           and t[i] - 60 <= t[o["i1"] if p["kind"] == "approach" else o["i0"]] <= t[j] + 60 for o in passes):
                        r["parallel_dup"] += 1
            for kind, te in events(v, apt, ends, True):
                if not (t_open <= te < t_close):
                    continue
                if kind == "touchdown":
                    ok = any(p["kind"] == "approach" and t[p["i0"]] - 60 <= te <= t[p["i1"]] + 180 for p in passes)
                else:
                    ok = any(p["kind"] == "climb" and t[p["i0"]] - 180 <= te <= t[p["i1"]] + 60 for p in passes)
                r[f"fw_{kind}s"] += 1
                r[f"fw_{kind}s_missed"] += not ok
        out[a] = dict(r)
    return local_date, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=24)
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()
    days = compared_days()
    tower = {(a, r["date"]): r for a in AIRPORTS for r in days[a]}
    common = sorted(set.intersection(*[{r["date"] for r in days[a]} for a in AIRPORTS]))
    random.seed(20261002)
    sample = sorted(random.sample(common, args.days))
    rows = []
    with ProcessPoolExecutor(args.workers) as ex:
        for ld, out in ex.map(day_job, sample):
            if not out:
                continue
            for a, r in out.items():
                tr = tower[(a, ld)]
                rows.append({"airport": a, "date": ld, "tower_ops": int(tr["tower_ops"]), "detected_ops_compare": int(tr["detected_ops"]),
                             **{k: r.get(k, 0) for k in ("fw_ops", "parallel_dup", "heli_visits", "heli_events", "heli_counted_as_fw",
                                                         "fw_touchdowns", "fw_touchdowns_missed", "fw_liftoffs", "fw_liftoffs_missed")}})
    with open(os.path.join(OUT, "spotcheck_days.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    L = [f"Day-level spot check: {len(sample)} random compared days (seed 20261002), tower hours, full archive parse.",
         "Per 100 tower operations. 'Adjusted' = (fixed-wing detected - parallel duplicates + rotorcraft touchdowns and liftoffs"
         " + missed fixed-wing touchdowns and liftoffs) / tower.", ""]
    for a in AIRPORTS:
        g = [r for r in rows if r["airport"] == a]
        T = sum(r["tower_ops"] for r in g)
        s = {k: sum(r[k] for r in g) for k in g[0] if k not in ("airport", "date")}
        adj = (s["fw_ops"] - s["parallel_dup"] + s["heli_events"] + s["fw_touchdowns_missed"] + s["fw_liftoffs_missed"]) / T
        L.append(f"{a}: {len(g)} days, tower {T:,}, detected {s['fw_ops']:,} ({s['fw_ops'] / T:.3f}; compare run {s['detected_ops_compare'] / T:.3f}). "
                 f"Parallel duplicates {100 * s['parallel_dup'] / T:.1f}. Rotorcraft: {s['heli_visits']} visits, touchdowns + liftoffs "
                 f"{100 * s['heli_events'] / T:.1f}, helicopter types counted as fixed-wing {100 * s['heli_counted_as_fw'] / T:.1f}. "
                 f"Fixed-wing touchdowns seen {s['fw_touchdowns']:,}, missed {100 * s['fw_touchdowns_missed'] / max(s['fw_touchdowns'], 1):.1f}% "
                 f"({100 * s['fw_touchdowns_missed'] / T:.1f} per 100); liftoffs seen {s['fw_liftoffs']:,}, missed "
                 f"{100 * s['fw_liftoffs_missed'] / max(s['fw_liftoffs'], 1):.1f}% ({100 * s['fw_liftoffs_missed'] / T:.1f} per 100). Adjusted {adj:.3f}")
    text = "\n".join(L)
    open(os.path.join(OUT, "spotcheck_days.txt"), "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    from concurrent.futures import ProcessPoolExecutor
    main()
