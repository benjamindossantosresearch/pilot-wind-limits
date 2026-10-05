#!/usr/bin/env python3
"""
us_tower_spotcheck.py

Spot check of the US tower-count comparison (us_tower_compare.py): why HWO and
APA count above the tower and FTW below it. Diagnostic only, nothing here
changes the detector or the analysis samples.

Every detected pass during tower hours on the compared airport-days (included,
30 or more tower operations) is classified by what the aircraft did next, from
the per-airport extracts (q2_extract_us, visits with at least one approach):

  approach  landed_or_low  reached 150 ft AGL or the ground over this runway or a
                           same-direction parallel within 150 s
            low_approach   reached 400 ft there instead (low approach or go-around)
            reversed       neither, then landed on an opposite-direction runway
                           within 6 min (a pattern leg or circle-to-land taken as
                           an approach, an overcount against the tower)
            crossing       neither, then landed on a crossing runway within 6 min
            none_low / none_high   none of these, lowest height at most / above 400 ft
  climb     from_runway    at 150 ft or the ground over this runway direction in the
                           2 min before or during the climb
            after_approach after an approach to this runway direction (go-around)
            unpaired       neither

Also: passes near the ends of tower hours, rotorcraft visits (us_daily), and
the OPSNET operation mix with a fit of detected operations on itinerant and
local tower counts.

    python3 us_tower_spotcheck.py --workers 20

Writes us_tower_compare/spotcheck.txt and us_tower_compare/spotcheck_examples.txt.
"""

import argparse
import bisect
import csv
import datetime as dt
import gzip
import json
import math
import os
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import adsb_airport_coverage as cov
import runway_use as ru
import us_airports as ua
import us_tower_compare as tc

EXTRACT = "q2_extract_us"
OUT = "us_tower_compare"
FOCUS = ("HWO", "APA", "FTW")
APP_CLASSES = ("landed_or_low", "low_approach", "reversed", "crossing", "none_low", "none_high")
CLB_CLASSES = ("from_runway", "after_approach", "unpaired")


def compared_days():
    days = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(OUT, "daily.csv"))):
        if r["included"] == "1" and int(r["tower_ops"]) >= 30:
            days[r["facility"]].append(r)
    return days


def classify(rec, ends, apt, t_open, t_close):
    p_ = rec["pts"]
    t = p_["t"]
    order = sorted(range(len(t)), key=lambda i: t[i])
    if order != list(range(len(t))):
        return []
    xy = [cov.to_xy_nm(la, lo, apt.lat, apt.lon) for la, lo in zip(p_["lat"], p_["lon"])]
    h = [0 if g else a for g, a in zip(p_["gnd"], p_["agl"])]
    by_name = {e.name: e for e in ends}
    geo = {}

    def al(e, j):
        if (e.name, j) not in geo:
            geo[(e.name, j)] = e.along_lateral(*xy[j])
        return geo[(e.name, j)]

    def idx(tt):
        return bisect.bisect_right(t, tt) - 1

    def low_over(es, j0, j1, hmax):
        for j in range(max(j0, 0), min(j1, len(t) - 1) + 1):
            if h[j] is None or h[j] > hmax:
                continue
            for e in es:
                along, lat = al(e, j)
                if -0.3 <= along <= e.length + 0.1 and lat <= 0.35:
                    return e.name
        return None

    out = []
    for p in rec["passes"]:
        E = by_name.get(p["runway"])
        if E is None:
            continue
        i0, i1 = p["i0"], p["i1"]
        if not (t_open <= t[i0] < t_close):
            continue
        same = [e for e in ends if ru.angle_diff(e.course, E.course) <= 20]
        opp = [e for e in ends if ru.angle_diff(e.course, E.course) >= 160]
        cross = [e for e in ends if 20 < ru.angle_diff(e.course, E.course) < 160]
        row = {"kind": p["kind"], "runway": p["runway"], "t": t[i0], "min_agl": p["min_agl"], "inferred": p["inferred"],
               "icao": rec["icao"], "type": rec["type"], "i0": i0, "i1": i1}
        if p["kind"] == "approach":
            w = idx(t[i1] + 150)
            if low_over(same, i0, w, 150):
                c = "landed_or_low"
            elif low_over(same, i0, w, 400):
                c = "low_approach"
            else:
                w6 = idx(t[i1] + 360)
                r = low_over(opp, i1, w6, 150)
                x = None if r else low_over(cross, i1, w6, 150)
                if r:
                    c, row["then"] = "reversed", r
                elif x:
                    c, row["then"] = "crossing", x
                else:
                    c = "none_low" if p["min_agl"] is not None and p["min_agl"] <= 400 else "none_high"
            if c in ("reversed", "crossing", "none_high"):
                j = min(range(i0, i1 + 1), key=lambda k: abs(al(E, k)[0] + 0.5))
                row["geom"] = {"along": round(al(E, j)[0], 2), "lateral": round(al(E, j)[1], 2),
                               "agl": h[j], "trk": p_["trk"][j], "gs": p_["gs"][j],
                               "lat": p_["lat"][j], "lon": p_["lon"][j]}
        else:
            if low_over(same, idx(t[i0] - 120), i1, 150):
                c = "from_runway"
            elif any(q["kind"] == "approach" and q["runway"] in {e.name for e in same}
                     and 0 <= t[i0] - t[q["i1"]] <= 300 for q in rec["passes"]):
                c = "after_approach"
            else:
                c = "unpaired"
        row["class"] = c
        out.append(row)
    return out


def airport_job(args):
    a, rows = args
    site = ua.load()[a]
    apt, tz = site.apt, site.tz
    ends = ru.runway_ends(apt)
    per_day = {}
    examples = []
    edges = Counter()
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        opening, closing = tc.tower_hours(a, d)
        t_open, t_close = tc.local_ts(d, opening, tz), tc.local_ts(d, closing, tz)
        cnt = Counter()
        for utc in (d, d + dt.timedelta(days=1)):
            path = os.path.join(EXTRACT, a, f"{utc}.jsonl.gz")
            if not os.path.exists(path):
                continue
            with gzip.open(path, "rt") as f:
                for line in f:
                    rec = json.loads(line)
                    if rec.get("category") == cov.ROTORCRAFT_CATEGORY:
                        continue
                    ts = rec["pts"]["t"]
                    for p in rec["passes"]:
                        tt = ts[p["i0"]]
                        if t_open - 3600 <= tt < t_open:
                            edges["hour_before_open"] += 1
                        elif t_close <= tt < t_close + 3600:
                            edges["hour_after_close"] += 1
                        elif t_open <= tt < t_open + 1800:
                            edges["first_30min"] += 1
                        elif t_close - 1800 <= tt < t_close:
                            edges["last_30min"] += 1
                        elif t_open <= tt < t_close:
                            edges["inside"] += 1
                    for row in classify(rec, ends, apt, t_open, t_close):
                        cnt[(row["kind"], row["class"])] += 1
                        cnt[(row["kind"], "inferred")] += row["inferred"] is not None
                        if row["class"] in ("reversed", "crossing", "none_high", "unpaired"):
                            row["date"] = r["date"]
                            row["local"] = dt.datetime.fromtimestamp(row["t"], tz).strftime("%H:%M:%S")
                            examples.append(row)
        per_day[r["date"]] = {"tower": int(r["tower_ops"]), "detected": int(r["detected_ops"]),
                              "det_app": int(r["detected_approaches"]), "det_clb": int(r["detected_climbs"]), "cnt": cnt}
    return a, per_day, examples, edges


def rotorcraft(days_by_apt):
    out = {}
    for a, rows in days_by_apt.items():
        tot = 0
        for r in rows:
            path = os.path.join("us_daily", f"{r['date']}.json")
            if os.path.exists(path):
                c = json.load(open(path))["coverage"].get(a)
                if c:
                    tot += c[2] - c[0]
        out[a] = tot
    return out


def opsnet_mix(days_by_apt):
    ops = {}
    for r in csv.DictReader(open("reference/opsnet/opsnet_daily.csv")):
        if r["facility"] in days_by_apt:
            ops[(r["facility"], r["date"])] = r
    res = {}
    for a, rows in days_by_apt.items():
        o = [ops[(a, r["date"])] for r in rows]
        tot = sum(int(x["total_ops"]) for x in o)
        mix = {k: sum(int(x[k]) for x in o) / tot for k in ("itin_at", "itin_ac", "itin_ga", "itin_mil", "local_civil", "local_mil")}
        # detected = a x itinerant + b x local, no intercept, least squares
        X = np.array([[int(x["itin_total"]), int(x["local_total"])] for x in o], float)
        y = np.array([int(r["detected_ops"]) for r in rows], float)
        coef = np.linalg.lstsq(X, y, rcond=None)[0] if X[:, 1].sum() > 0 else (np.nan, np.nan)
        res[a] = (mix, coef)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args()
    days = compared_days()
    results, examples, edges = {}, {}, {}
    with ProcessPoolExecutor(args.workers) as ex:
        for a, per_day, exm, edg in ex.map(airport_job, [(a, days[a]) for a in tc.AIRPORTS]):
            results[a], examples[a], edges[a] = per_day, exm, edg
    rot = rotorcraft(days)
    mix = opsnet_mix(days)

    L = ["US tower-count spot check. Passes during tower hours on the compared airport-days, classified from the per-airport extracts.",
         "Shares of detected approaches (extract) by what followed. Overcount = reversed + crossing (one approach the tower would not count).", ""]
    hdr = f"{'apt':4} {'ratio':>6} {'adj':>6} {'appr':>7} " + " ".join(f"{c[:9]:>9}" for c in APP_CLASSES) + f" {'inferred':>8}"
    L.append(hdr)
    summary = {}
    for a in tc.AIRPORTS:
        pd_ = results[a]
        tower = sum(v["tower"] for v in pd_.values())
        det = sum(v["detected"] for v in pd_.values())
        c = Counter()
        for v in pd_.values():
            c.update(v["cnt"])
        n_app = sum(c[("approach", k)] for k in APP_CLASSES)
        over = c[("approach", "reversed")] + c[("approach", "crossing")]
        adj = (det - over) / tower
        summary[a] = (det / tower, adj, c, n_app, tower, det)
        L.append(f"{a:4} {det / tower:6.3f} {adj:6.3f} {n_app:7,} " +
                 " ".join(f"{100 * c[('approach', k)] / n_app:8.1f}%" for k in APP_CLASSES) +
                 f" {100 * c[('approach', 'inferred')] / n_app:7.1f}%")
    L.append("")
    L.append("Climbs in approach visits by what preceded them:")
    for a in tc.AIRPORTS:
        c = summary[a][2]
        n = sum(c[("climb", k)] for k in CLB_CLASSES)
        L.append(f"  {a}: {n:,} climbs, " + ", ".join(f"{k} {100 * c[('climb', k)] / max(n, 1):.1f}%" for k in CLB_CLASSES))
    L.append("")
    L.append("Tower-hour edges (approach-visit passes): first 30 min, last 30 min, hour before opening, hour after closing, as % of passes inside tower hours")
    for a in tc.AIRPORTS:
        e = edges[a]
        inside = e["inside"] + e["first_30min"] + e["last_30min"]
        if tc.tower_hours(a, dt.date(2026, 3, 1)) == ((0, 0), (24, 0)):
            L.append(f"  {a}: 24-hour tower")
            continue
        L.append(f"  {a}: first {100 * e['first_30min'] / inside:.1f}%, last {100 * e['last_30min'] / inside:.1f}%, "
                 f"before {100 * e['hour_before_open'] / inside:.1f}%, after {100 * e['hour_after_close'] / inside:.1f}%")
    L.append("")
    L.append("OPSNET mix (share of tower operations) and fit detected = a x itinerant + b x local; rotorcraft visits (all day) per 100 tower operations")
    for a in tc.AIRPORTS:
        m, (ca, cb) = mix[a]
        L.append(f"  {a}: air taxi {100 * m['itin_at']:.1f}%, air carrier {100 * m['itin_ac']:.1f}%, itinerant GA {100 * m['itin_ga']:.1f}%, "
                 f"military {100 * (m['itin_mil'] + m['local_mil']):.1f}%, local civil {100 * m['local_civil']:.1f}%. "
                 f"a {ca:.2f}, b {cb:.2f}. Rotorcraft {100 * rot[a] / summary[a][4]:.1f}")
    ratios = np.array([summary[a][0] for a in tc.AIRPORTS])
    rev = np.array([(summary[a][2][("approach", "reversed")] + summary[a][2][("approach", "crossing")]) / summary[a][4] for a in tc.AIRPORTS])
    L.append("")
    L.append(f"Across the 20 airports, correlation of detected/tower with overcount per tower operation: {np.corrcoef(ratios, rev)[0, 1]:.2f}")
    text = "\n".join(L)
    open(os.path.join(OUT, "spotcheck.txt"), "w").write(text + "\n")
    print(text)

    E = []
    rng = np.random.default_rng(20261002)
    for a in FOCUS:
        for cls in ("reversed", "crossing", "none_high", "unpaired"):
            ex_ = [r for r in examples[a] if r["class"] == cls]
            pick = rng.choice(len(ex_), size=min(8, len(ex_)), replace=False) if ex_ else []
            E.append(f"{a} {cls}: {len(ex_):,} passes, {len(pick)} at random")
            for k in pick:
                r = ex_[k]
                E.append(f"  {r['date']} {r['local']} {r['icao']} {r['type']:5} {r['kind']} {r['runway']} min_agl {r['min_agl']} "
                         f"then {r.get('then', '-')} geom {json.dumps(r.get('geom', {}))}")
            E.append("")
    open(os.path.join(OUT, "spotcheck_examples.txt"), "w").write("\n".join(E) + "\n")


if __name__ == "__main__":
    main()
