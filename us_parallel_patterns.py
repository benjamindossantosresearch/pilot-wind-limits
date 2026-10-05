#!/usr/bin/env python3
"""
us_parallel_patterns.py

Development analysis for a pattern-side rule at parallel runways (Benjamin,
2026-10-02: parallel runways do not have overlapping traffic patterns, so the
side the downwind is flown on should identify the runway). Tests the premise on
circuits whose landing runway is not in doubt, before any rule is written.

Parallel group: runway ends within 10 degrees of the same course whose
centerlines are at most 0.8 nm apart. For every observed (not inferred) approach
to an outer runway of a group, in the US per-airport extracts:
  * decisive runway: low points (300 ft or less, from 0.5 nm before the
    threshold to the far end) have a median lateral offset within 30% of the
    separation from one centerline and at least 70% of it from the other
  * downwind side: in the 6 minutes before the approach, points abeam the
    runway (0.5 nm before the threshold to 0.5 nm past the far end), 300 to
    2,000 ft above the field, track within 30 degrees of the reciprocal course;
    side = sign of the median offset from the group's middle, relative to the
    landing direction (at least 3 points)
Reports, per airport and overall, how often the downwind is on the same side
as the runway the airplane landed on (the outside pattern), the share of
approaches with a decisive low track, and the published NASR flags.

    python3 us_parallel_patterns.py --every 4 --workers 40

Writes us_parallel/patterns.txt and us_parallel/patterns.csv.
"""

import argparse
import csv
import datetime as dt
import gzip
import json
import os
import statistics
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import adsb_airport_coverage as cov
import runway_use as ru
import us_airports as ua
import us_inclusion as ui

OUT = "us_parallel"
MAX_SEP = 0.8


def signed(e, x, y):
    """Along-track distance and signed lateral offset (positive right of the landing direction)."""
    rx, ry = x - e.tx, y - e.ty
    return rx * e.ux + ry * e.uy, rx * e.uy - ry * e.ux


def parallel_groups(ends):
    """end name -> list of (offset of that end's centerline from this end's, end), sorted left to right."""
    out = {}
    for e in ends:
        g = []
        for f in ends:
            if ru.angle_diff(e.course, f.course) > 10:
                continue
            mx, my = f.tx + f.ux * f.length / 2, f.ty + f.uy * f.length / 2
            _, off = signed(e, mx, my)
            if abs(off) <= MAX_SEP:
                g.append((0.0 if f is e else off, f))
        if len(g) > 1:
            out[e.name] = sorted(g, key=lambda t: t[0])
    return out


def airport_job(args):
    a, dates = args
    site = ua.load()[a]
    apt = site.apt
    ends = ru.runway_ends(apt)
    by = {e.name: e for e in ends}
    groups = parallel_groups(ends)
    if not groups:
        return a, []
    rows = []
    for date in dates:
        path = os.path.join("q2_extract_us", a, f"{date}.jsonl.gz")
        if not os.path.exists(path):
            continue
        with gzip.open(path, "rt") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("category") == cov.ROTORCRAFT_CATEGORY:
                    continue
                p_ = rec["pts"]
                t = p_["t"]
                xy = [cov.to_xy_nm(la, lo, apt.lat, apt.lon) for la, lo in zip(p_["lat"], p_["lon"])]
                h = [0 if g else v for g, v in zip(p_["gnd"], p_["agl"])]
                for q in rec["passes"]:
                    if q["kind"] != "approach" or q["inferred"] or q["runway"] not in groups:
                        continue
                    grp = groups[q["runway"]]
                    E = by[q["runway"]]
                    offs = [o for o, _ in grp]
                    mid = (offs[0] + offs[-1]) / 2
                    sep = min(b - a_ for a_, b in zip(offs, offs[1:]))
                    # low points over the group's runways, from the pass start to 60 s after it ends
                    t_end = t[q["i1"]] + 60
                    lows = [j for j in range(q["i0"], len(t)) if t[j] <= t_end and h[j] is not None and h[j] <= 300]
                    lows = [j for j in lows if -0.5 <= signed(E, *xy[j])[0] <= E.length + 0.2]
                    decisive = None
                    if len(lows) >= 2:
                        lat_med = statistics.median(signed(E, *xy[j])[1] for j in lows)
                        d = sorted((abs(lat_med - o), f.name, k) for k, (o, f) in enumerate(grp))
                        if d[0][0] <= 0.3 * sep and d[1][0] >= 0.7 * sep:
                            decisive = (d[0][1], d[0][2])
                    # downwind before the approach
                    t0 = t[q["i0"]]
                    dw = []
                    for j in range(q["i0"] - 1, -1, -1):
                        if t[j] < t0 - 360:
                            break
                        if h[j] is None or not (300 <= h[j] <= 2000) or p_["trk"][j] is None:
                            continue
                        if ru.angle_diff(p_["trk"][j], (E.course + 180) % 360) > 30:
                            continue
                        al, off = signed(E, *xy[j])
                        if -0.5 <= al <= E.length + 0.5:
                            dw.append(off - mid)
                    side = None
                    if len(dw) >= 3:
                        m = statistics.median(dw)
                        side = "right" if m > 0 else "left"
                    # simulated loss of the low track: nearest centerline from the pass's points above 300 ft
                    hi = [j for j in range(q["i0"], q["i1"] + 1) if h[j] is not None and h[j] > 300]
                    hi_choice, hi_amb = "", ""
                    if len(hi) >= 2:
                        lat_hi = statistics.median(signed(E, *xy[j])[1] for j in hi)
                        d = sorted((abs(lat_hi - o), k) for k, (o, f) in enumerate(grp))
                        hi_choice = grp[d[0][1]][1].name
                        hi_amb = int(d[0][0] > 0.3 * sep)
                    pos = None
                    if decisive:
                        k = decisive[1]
                        pos = "left" if k == 0 else ("right" if k == len(grp) - 1 else "center")
                    rows.append({"airport": a, "date": date, "assigned": q["runway"], "group": "/".join(f.name for _, f in grp),
                                 "sep_nm": round(sep, 3), "decisive": decisive[0] if decisive else "",
                                 "runway_pos": pos or "", "downwind_side": side or "",
                                 "dw_offset_nm": round(statistics.median(dw) - 0, 2) if dw else "",
                                 "hi_choice": hi_choice, "hi_ambiguous": hi_amb,
                                 "side_choice": (grp[0][1].name if side == "left" else grp[-1][1].name) if side else ""})
    return a, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--every", type=int, default=4, help="use every n-th day")
    ap.add_argument("--workers", type=int, default=40)
    args = ap.parse_args()
    inc = ui.load()
    S = ua.load()
    apts = [a for a in inc.included_airports() if parallel_groups(ru.runway_ends(S[a].apt))]
    start = dt.date(2025, 10, 1)
    dates = [(start + dt.timedelta(days=i)).isoformat() for i in range(0, 365, args.every)]
    jobs = [(a, [d for d in dates if inc.day_ok(a, d)]) for a in apts]
    rows = []
    with ProcessPoolExecutor(args.workers) as ex:
        for a, r in ex.map(airport_job, jobs):
            rows += r
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "patterns.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    L = [f"Parallel-runway pattern sides, {len(apts)} included airports with parallels within {MAX_SEP} nm, every {args.every}th day.",
         f"Observed approaches to a runway in a parallel group: {len(rows):,}. Decisive low track: {sum(1 for r in rows if r['decisive']):,}. "
         f"With a downwind: {sum(1 for r in rows if r['downwind_side']):,}.", ""]
    both = [r for r in rows if r["decisive"] and r["downwind_side"] and r["runway_pos"] in ("left", "right")]
    agree = sum(r["downwind_side"] == r["runway_pos"] for r in both)
    L.append(f"Outer runway decided by the low track, downwind seen: {len(both):,}. Downwind on the same side as the landing runway: "
             f"{agree:,} ({100 * agree / max(len(both), 1):.1f}%)")
    for lo, hi in ((0, 0.15), (0.15, 0.25), (0.25, 0.4), (0.4, 0.81)):
        g = [r for r in both if lo <= r["sep_nm"] < hi]
        if g:
            k = sum(r["downwind_side"] == r["runway_pos"] for r in g)
            L.append(f"  separation {lo}-{hi} nm: {len(g):,} circuits, same side {100 * k / len(g):.1f}%")
    # the detector's own assignment against the low track
    dec = [r for r in rows if r["decisive"]]
    wrong = sum(r["decisive"] != r["assigned"] for r in dec)
    L.append(f"Detector runway (v3.0.1) against the decisive low track: {wrong:,} of {len(dec):,} differ ({100 * wrong / max(len(dec), 1):.1f}%)")
    nd = [r for r in rows if not r["decisive"]]
    L.append(f"Approaches without a decisive low track: {len(nd):,} ({100 * len(nd) / len(rows):.1f}%), of which with a downwind side: "
             f"{sum(1 for r in nd if r['downwind_side']):,}")
    L.append("")
    L.append("Simulated loss of the low track (truth = decisive low track, outer runways, downwind seen, pass points above 300 ft):")
    sim = [r for r in both if r["hi_choice"]]
    if sim:
        for lab, sel in (("all", sim), ("lateral unambiguous", [r for r in sim if r["hi_ambiguous"] == 0]),
                         ("lateral ambiguous", [r for r in sim if r["hi_ambiguous"] == 1])):
            if not sel:
                continue
            k_lat = sum(r["hi_choice"] == r["decisive"] for r in sel)
            k_side = sum(r["side_choice"] == r["decisive"] for r in sel)
            L.append(f"  {lab}: {len(sel):,} circuits. Nearest centerline above 300 ft right {100 * k_lat / len(sel):.1f}%, downwind side right {100 * k_side / len(sel):.1f}%")
        comb = sum((r["hi_choice"] if r["hi_ambiguous"] == 0 else r["side_choice"]) == r["decisive"] for r in sim)
        L.append(f"  combined (lateral when unambiguous, else downwind side): right {100 * comb / len(sim):.1f}%")
    L.append("")
    L.append("Per airport (circuits with both a decisive outer runway and a downwind): n, same side %, separation")
    per = defaultdict(list)
    for r in both:
        per[r["airport"]].append(r)
    for a, g in sorted(per.items(), key=lambda kv: -len(kv[1])):
        k = sum(r["downwind_side"] == r["runway_pos"] for r in g)
        L.append(f"  {a}: {len(g):,}, {100 * k / len(g):.1f}%, {min(r['sep_nm'] for r in g):.2f} nm")
    text = "\n".join(L)
    open(os.path.join(OUT, "patterns.txt"), "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
