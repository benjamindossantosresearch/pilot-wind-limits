#!/usr/bin/env python3
"""
approach_count_check.py

Benjamin's question on the draft: is counting one arrival per visit (ten touch-and-goes count once) a good thing?
Sensitivity (post-hoc, 2026-10-05): the revealed limit with every piston approach counted, on the same VMC
airport-hours as q1a_us/hours.csv, with normal demand recomputed from approach counts.

    python3 review_2026-10-05/approach_count_check.py review_2026-10-05/us_cas.pkl
"""

import datetime as dt
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import q1a_crosswind as qc  # noqa: E402
import us_airports as ua  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "approach_count_check.txt")


def main(pkl):
    df = pd.read_pickle(pkl)
    p = df[(df["group"] == "piston") & df["local_hour"].between(8, 18)][["airport", "date", "local_time", "local_hour", "ownership"]].copy()
    del df
    sites = ua.load()
    # 'date' is the UTC day of the trace. Local date = UTC day minus one when local hour minus the UTC offset passes midnight.
    off = {}
    for a in p["airport"].astype(str).unique():
        tz = sites[a].tz
        off[a] = tz.utcoffset(dt.datetime(2026, 1, 15, 12)).total_seconds() / 3600, tz.utcoffset(dt.datetime(2026, 7, 15, 12)).total_seconds() / 3600
    month = pd.to_datetime(p["date"]).dt.month.values
    a_off = np.array([off[a][1] if 4 <= m <= 10 else off[a][0] for a, m in zip(p["airport"].astype(str).values, month)])
    shift = (p["local_hour"].values - a_off) >= 24
    p["local_date"] = (pd.to_datetime(p["date"]) - pd.to_timedelta(shift.astype(int), unit="D")).dt.strftime("%Y-%m-%d")
    p["fleet"] = (p["ownership"].astype(str) == "fleet").astype(int)
    p["private"] = (p["ownership"].astype(str) == "private").astype(int)
    g = p.groupby([p["airport"].astype(str), "local_date", "local_hour"]).agg(apps=("fleet", "size"), apps_fleet=("fleet", "sum"), apps_private=("private", "sum"))
    counts = g.to_dict("index")
    rows = []
    for r in pd.read_csv("q1a_us/hours.csv").to_dict("records"):
        c = counts.get((r["airport"], r["local_date"], r["hour"]), {"apps": 0, "apps_fleet": 0, "apps_private": 0})
        r.update(c)
        rows.append(r)
    cells = defaultdict(list)
    for r in rows:
        cells[(r["airport"], r["season"], r["weekend"], r["hour"])].append(r)
    for grp in ("apps", "apps_fleet", "apps_private"):
        for gg in cells.values():
            m = sum(r[grp] for r in gg) / len(gg)
            for r in gg:
                r[f"base_{grp}"] = m
    L = [f"Every piston approach counted (not one arrival per visit), {len(rows):,} VMC airport-hours, "
         f"{sum(r['apps'] for r in rows):,} approaches against {sum(r['piston'] for r in rows):,} arrivals"]
    for grp, lab in (("apps", "piston"), ("apps_fleet", "fleet"), ("apps_private", "private")):
        L += qc.empirical_limit(rows, grp, f"approaches, {lab}")
    text = "\n".join(L)
    open(OUT, "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1])
