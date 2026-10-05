#!/usr/bin/env python3
"""
us_q1a.py

Q1a revealed limits for the US confirmatory sample, by the rules locked in
notes/decisions.md before the US data were analyzed:

  * included airport-months and outage days from us_inclusion.py
  * VMC airport-hours 08 to 18 local, arrivals counted once per visit (us_pipeline.py)
  * hourly wind from one-minute ASOS (METAR fallback), crosswind on the best
    usable runway end (paved, 2,500 ft or more)
  * normal demand: airport by season by day type by hour, cells of fewer than 8
    VMC hours dropped
  * primary: model-free revealed limit (activity / normal demand in 2 kt bins,
    50 percent crossing, day-cluster bootstrap); second: spline Poisson model;
    the log-linear model is reported as in New England

    python3 us_q1a.py --workers 48

Writes q1a_us/hours.csv and q1a_us/summary.txt.
"""

import argparse
import csv
import datetime as dt
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import q1a_crosswind as qc
import us_airports as ua
import us_inclusion as ui
import wind_qc

OUT = "q1a_us"
GROUPS = ("piston", "fleet", "private")
FAA_REGION = {
    "ANE": {"CT", "MA", "ME", "NH", "RI", "VT"},
    "AEA": {"DE", "DC", "MD", "NJ", "NY", "PA", "VA", "WV"},
    "ASO": {"AL", "FL", "GA", "KY", "MS", "NC", "SC", "TN", "PR", "VI"},
    "AGL": {"IL", "IN", "MI", "MN", "ND", "OH", "SD", "WI"},
    "ACE": {"IA", "KS", "MO", "NE"},
    "ASW": {"AR", "LA", "NM", "OK", "TX"},
    "ANM": {"CO", "ID", "MT", "OR", "UT", "WA", "WY"},
    "AWP": {"AZ", "CA", "NV", "HI"},
}


def region_of(state):
    return next((r for r, s in FAA_REGION.items() if state in s), "other")


def airport_rows(args):
    """All analyzable VMC hours for one airport (runs in a worker)."""
    a, counts = args
    inc = ui.load()
    site = ua.load()[a]
    ends = inc.usable_ends(a)
    if not ends:
        return a, []
    onemin = qc.load_onemin(site.station)
    metars, mtimes = qc.load_metar_obs(site.station)
    onemin, _ = wind_qc.qc_onemin(onemin, [t.timestamp() for t in mtimes], [o["sknt"] for o in metars])
    by_hour = {(d, h): c for d, h, c in counts}
    rows = []
    d = dt.date(2025, 10, 1)
    while d <= dt.date(2026, 9, 30):
        # every UTC day touched by local 08:00 to 18:59 must be included
        t_first = dt.datetime(d.year, d.month, d.day, 8, tzinfo=site.tz)
        t_last = dt.datetime(d.year, d.month, d.day, 18, 59, tzinfo=site.tz)
        utc_days = {t_first.astimezone(dt.timezone.utc).date().isoformat(), t_last.astimezone(dt.timezone.utc).date().isoformat()}
        if all(inc.day_ok(a, u) for u in utc_days) and inc.month_ok(a, d.isoformat()[:7]):
            for h in range(8, 19):
                t0 = dt.datetime(d.year, d.month, d.day, h, tzinfo=site.tz).timestamp()
                wx = qc.hour_weather(t0, onemin, metars, mtimes, ends)
                if wx is None or not wx["vmc"]:
                    continue
                c = by_hour.get((d.isoformat(), h), (0, 0, 0, 0))
                rows.append({"airport": a, "local_date": d.isoformat(), "hour": h, "weekend": d.weekday() >= 5,
                             "season": qc.season_key(d, "window"), "piston": c[0], "fleet": c[1], "private": c[2],
                             "all_fixed": c[3], "tower": site.tower.startswith("ATCT"), "region": region_of(site.state), **wx})
        d += dt.timedelta(days=1)
    return a, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()
    inc = ui.load()
    airports = inc.included_airports()
    per = defaultdict(list)
    for a, d, h, p, f, pr, al in inc.counts:
        per[a].append((d, h, (p, f, pr, al)))
    rows = []
    with ProcessPoolExecutor(args.workers) as ex:
        for a, r in ex.map(airport_rows, [(a, per.get(a, [])) for a in airports]):
            rows.extend(r)
    cells = defaultdict(list)
    for r in rows:
        cells[(r["airport"], r["season"], r["weekend"], r["hour"])].append(r)
    kept, thin = [], 0
    for g in cells.values():
        if len(g) < qc.MIN_CELL_HOURS:
            thin += len(g)
            continue
        for grp in GROUPS:
            m = sum(r[grp] for r in g) / len(g)
            for r in g:
                r[f"base_{grp}"] = m
        kept.extend(g)
    rows = kept
    os.makedirs(OUT, exist_ok=True)
    fields = ["airport", "local_date", "hour", "weekend", "season", "tower", "region", "wind_src", "xw", "hw", "speed",
              "gust_spread", "gust_xw"] + list(GROUPS) + ["all_fixed"] + [f"base_{g}" for g in GROUPS]
    with open(os.path.join(OUT, "hours.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    L = [f"US Q1a: {len(rows):,} VMC airport-hours at {len({r['airport'] for r in rows})} airports. {inc.summary()}. "
         f"Thin baseline cells dropped: {thin:,} hours.",
         "Wind source: " + ", ".join(f"{s} {sum(1 for r in rows if r['wind_src'] == s):,}" for s in ("onemin", "metar")), ""]
    L += ["PRIMARY: model-free revealed limit"]
    for grp in GROUPS:
        L += qc.empirical_limit(rows, grp, f"Model-free, {grp}") + [""]
    L += qc.empirical_limit(rows, "piston", "Model-free, piston", key="gust_xw") + [""]
    for label, sel in (("towered", [r for r in rows if r["tower"]]), ("non-towered", [r for r in rows if not r["tower"]])):
        L += qc.empirical_limit(sel, "piston", f"Model-free, piston, {label}") + [""]
    for reg in sorted({r["region"] for r in rows}):
        sel = [r for r in rows if r["region"] == reg]
        L += qc.empirical_limit(sel, "piston", f"Model-free, piston, FAA region {reg} ({len({r['airport'] for r in sel})} airports)") + [""]
    L += ["SECOND: spline Poisson model"]
    for grp in GROUPS:
        L += qc.flexible_block(rows, grp, f"Spline model, {grp}") + [""]
    L += ["AS REGISTERED IN NEW ENGLAND: log-linear Poisson model"]
    L += qc.model_block(rows, "piston", "Log-linear model, piston") + [""]
    L += qc.band_table([dict(r, airport=r["region"]) for r in rows], "xw", "piston", "Piston by FAA region, mean best-runway crosswind")
    text = "\n".join(L)
    open(os.path.join(OUT, "summary.txt"), "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
