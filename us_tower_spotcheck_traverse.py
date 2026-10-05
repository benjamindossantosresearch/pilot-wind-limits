#!/usr/bin/env python3
"""
us_tower_spotcheck_traverse.py

Second step of the tower-count spot check (us_tower_spotcheck.py). Inferred
passes are about a fifth of approaches at HWO and DTO against a few percent
elsewhere, so this measures how inferred passes, and the traverse rule (detector
rule 11) in particular, move detected / tower operations at each of the 20
airports. Diagnostic only: the frozen detector v3.0.1 is not changed.

Traverse passes are split by geometry:
  parallel_dup  a pass of the same kind on a same-direction parallel runway lies
                within the rule's 60 s window (the rule only checks the same runway
                end, so a circuit seen on 10R can be counted again on 10L)
  along_runway  both points within 0.35 nm of the centerline and the track at
                the first point within 30 degrees of the runway course
  offset        everything else (a pattern leg or a crossing of the field)

Counts on the compared airport-days (included, 30 or more tower operations),
tower hours only, from the per-airport extracts. Also the signal-source mix of
approach visits and the archive's low coverage (us_daily), for FTW.

    python3 us_tower_spotcheck_traverse.py --workers 20

Writes us_tower_compare/spotcheck_traverse.txt and
us_tower_compare/spotcheck_traverse_examples.csv.
"""

import argparse
import csv
import datetime as dt
import gzip
import json
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import adsb_airport_coverage as cov
import runway_use as ru
import us_airports as ua
import us_tower_compare as tc
from us_tower_spotcheck import compared_days

EXTRACT = "q2_extract_us"
OUT = "us_tower_compare"


def airport_job(args):
    a, rows = args
    site = ua.load()[a]
    apt, tz = site.apt, site.tz
    ends = ru.runway_ends(apt)
    by_name = {e.name: e for e in ends}
    c = Counter()
    examples = []
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        opening, closing = tc.tower_hours(a, d)
        t_open, t_close = tc.local_ts(d, opening, tz), tc.local_ts(d, closing, tz)
        for utc in (d, d + dt.timedelta(days=1)):
            path = os.path.join(EXTRACT, a, f"{utc}.jsonl.gz")
            if not os.path.exists(path):
                continue
            with gzip.open(path, "rt") as f:
                for line in f:
                    rec = json.loads(line)
                    p_ = rec["pts"]
                    t = p_["t"]
                    srcs = Counter(p_["src"])
                    n = sum(srcs.values())
                    first_app = min((t[q["i0"]] for q in rec["passes"] if q["kind"] == "approach"), default=None)
                    if first_app is not None and t_open <= first_app < t_close:
                        c["visits"] += 1
                        c["visits_uat"] += (srcs["adsr_icao"] + srcs.get("uat", 0)) / n > 0.5
                        c["visits_tisb"] += sum(v for k, v in srcs.items() if k.startswith("tisb")) / n > 0.5
                        apps = [q for q in rec["passes"] if q["kind"] == "approach"]
                        if all(q["inferred"] == "traverse" for q in apps):
                            c["visits_traverse_only"] += 1
                        if all(q["inferred"] is not None for q in apps):
                            c["visits_inferred_only"] += 1
                    xy = [cov.to_xy_nm(la, lo, apt.lat, apt.lon) for la, lo in zip(p_["lat"], p_["lon"])]
                    for q in rec["passes"]:
                        if not (t_open <= t[q["i0"]] < t_close):
                            continue
                        c[("all", q["kind"])] += 1
                        if q["inferred"]:
                            c[(q["inferred"], q["kind"])] += 1
                        if q["inferred"] != "traverse":
                            continue
                        E = by_name[q["runway"]]
                        i = q["i0"] if q["kind"] == "approach" else q["i0"] - 1
                        j = i + 1
                        if i < 0 or j >= len(t):
                            continue
                        al0, lat0 = E.along_lateral(*xy[i])
                        al1, lat1 = E.along_lateral(*xy[j])
                        trk = p_["trk"][i]
                        par = [e for e in ends if e.name != E.name and ru.angle_diff(e.course, E.course) <= 20]
                        dup = any(o["kind"] == q["kind"] and o["runway"] in {e.name for e in par} and o["inferred"] != "traverse"
                                  and t[i] - 60 <= t[o["i1"] if q["kind"] == "approach" else o["i0"]] <= t[j] + 60
                                  for o in rec["passes"])
                        if dup:
                            g = "parallel_dup"
                        elif lat0 <= 0.35 and lat1 <= 0.35 and trk is not None and ru.angle_diff(trk, E.course) <= 30:
                            g = "along_runway"
                        else:
                            g = "offset"
                        c[("traverse", q["kind"], g)] += 1
                        if q["kind"] == "approach" and len(examples) < 4000:
                            examples.append({"airport": a, "date": r["date"], "icao": rec["icao"], "type": rec["type"],
                                             "local": dt.datetime.fromtimestamp(t[i], tz).strftime("%H:%M:%S"),
                                             "runway": q["runway"], "class": g, "gap_s": round(t[j] - t[i]),
                                             "agl0": p_["agl"][i], "agl1": p_["agl"][j], "lat0": round(lat0, 2), "lat1": round(lat1, 2),
                                             "trk_diff": None if trk is None else round(ru.angle_diff(trk, E.course))})
    tower = sum(int(r["tower_ops"]) for r in rows)
    det = sum(int(r["detected_ops"]) for r in rows)
    seen = [json.load(open(os.path.join("us_daily", f"{r['date']}.json")))["coverage"].get(a) for r in rows
            if os.path.exists(os.path.join("us_daily", f"{r['date']}.json"))]
    fw_ops = sum(s[0] for s in seen if s)
    fw_seen = sum(s[1] for s in seen if s)
    return a, c, tower, det, fw_seen / max(fw_ops, 1), examples


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args()
    days = compared_days()
    L = ["Detected / tower operations as counted (v3.0.1) and with traverse passes removed by class.",
         "Traverse passes per 100 tower operations by class (approach + climb). Visits = approach visits with the first approach in tower hours.", ""]
    L.append(f"{'apt':4} {'ratio':>6} {'-dup':>6} {'-dup-off':>8} {'-trav':>6} {'-infer':>6} | {'dup':>5} {'offset':>6} {'along':>6} {'gap':>5} {'end':>5} | "
             f"{'trav-only visits':>16} {'UAT visits':>10} {'TIS-B':>6} {'seen300':>7}")
    exs = []
    with ProcessPoolExecutor(args.workers) as ex:
        for a, c, tower, det, seen300, examples in ex.map(airport_job, [(a, days[a]) for a in tc.AIRPORTS]):
            tv = {g: c[("traverse", "approach", g)] + c[("traverse", "climb", g)] for g in ("parallel_dup", "along_runway", "offset")}
            trav = c[("traverse", "approach")] + c[("traverse", "climb")]
            infer = trav + c[("gap", "approach")] + c[("gap", "climb")] + c[("end", "approach")] + c[("end", "climb")]
            gap = c[("gap", "approach")] + c[("gap", "climb")]
            end = c[("end", "approach")] + c[("end", "climb")]
            v = max(c["visits"], 1)
            L.append(f"{a:4} {det / tower:6.3f} {(det - tv['parallel_dup']) / tower:6.3f} {(det - tv['parallel_dup'] - tv['offset']) / tower:8.3f} "
                     f"{(det - trav) / tower:6.3f} {(det - infer) / tower:6.3f} | "
                     f"{100 * tv['parallel_dup'] / tower:5.1f} {100 * tv['offset'] / tower:6.1f} {100 * tv['along_runway'] / tower:6.1f} "
                     f"{100 * gap / tower:5.1f} {100 * end / tower:5.1f} | "
                     f"{100 * c['visits_traverse_only'] / v:15.1f}% {100 * c['visits_uat'] / v:9.1f}% {100 * c['visits_tisb'] / v:5.1f}% {seen300:7.2f}")
            exs += examples
    text = "\n".join(L)
    open(os.path.join(OUT, "spotcheck_traverse.txt"), "w").write(text + "\n")
    print(text)
    with open(os.path.join(OUT, "spotcheck_traverse_examples.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(exs[0]))
        w.writeheader()
        w.writerows(exs)


if __name__ == "__main__":
    main()
