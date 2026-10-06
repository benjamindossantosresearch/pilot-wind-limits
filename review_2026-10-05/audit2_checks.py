#!/usr/bin/env python3
"""Second outside audit (2026-10-06): table cell intervals, climate tertiles against their own calm level,
and METAR gust outliers. From q1a_us/hours.csv."""
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import q1a_crosswind as qc  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q1a_checks import curve_at, first_crossing, spline_fit  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit2_checks.txt")
L = []
rng = np.random.default_rng(20261006)


def say(s=""):
    L.append(s)
    print(s, flush=True)


h = pd.read_csv("q1a_us/hours.csv")
h = h[h["base_piston"] > 0]
o = h[h["wind_src"] == "onemin"]

say("CELLS, one-minute hours, 14 to 17 kt total wind (day-cluster bootstrap, 2,000 resamples)")
for xa, xb in ((12, 15), (15, 99)):
    c = o[(o["speed"] >= 14) & (o["speed"] < 17) & (o["xw"] >= xa) & (o["xw"] < xb)]
    g = c.groupby(["airport", "local_date"])[["piston", "base_piston"]].sum().values
    est = g[:, 0].sum() / g[:, 1].sum()
    bs = []
    for _ in range(2000):
        i = rng.integers(0, len(g), len(g))
        bs.append(g[i, 0].sum() / g[i, 1].sum())
    say(f"  crosswind {xa}-{xb if xb < 99 else '+'} kt: {est:.2f} (95% {np.percentile(bs, 2.5):.2f} to {np.percentile(bs, 97.5):.2f}), "
        f"{len(c):,} hours, {int(c['piston'].sum()):,} arrivals, {len(g):,} airport-days")

say("\nCROSSWIND CLIMATE TERTILES (share of VMC daytime hours with best-runway crosswind of 10 kt or more, by airport)")
share = h.groupby("airport")["xw"].apply(lambda x: (x >= 10).mean())
cuts = share.quantile([1 / 3, 2 / 3]).values
say(f"  cut points {100 * cuts[0]:.2f}% and {100 * cuts[1]:.2f}% of hours")
terc = pd.Series(np.select([share <= cuts[0], share <= cuts[1]], ["low", "middle"], "high"), index=share.index)
for t in ("low", "middle", "high"):
    g = h[h["airport"].map(terc) == t]
    for grp in ("piston", "private"):
        days = defaultdict(lambda: np.zeros((len(qc.FINE), 2)))
        for a, d, x, y, b in zip(g["airport"].values, g["local_date"].values, g["xw"].values, g[grp].values, g[f"base_{grp}"].values):
            j = min(int(x // 2), len(qc.FINE) - 1)
            days[(a, d)][j] += (y, b)
        arr = np.array(list(days.values()))
        mids = [(a + b) / 2 for a, b in qc.FINE]

        def cross(tot):
            ratio = tot[:, 0] / np.maximum(tot[:, 1], 1e-9)
            calm = tot[:2, 0].sum() / tot[:2, 1].sum()
            return first_crossing(mids, ratio, 0.5), first_crossing(mids, ratio, 0.5 * calm), calm
        x50, x50c, calm = cross(arr.sum(axis=0))
        bs = np.array([cross(arr[rng.integers(0, len(arr), len(arr))].sum(axis=0))[:2] for _ in range(500)])
        say(f"  {t:6s} {grp:7s}: {g['airport'].nunique()} airports, calm activity {calm:.3f}, half of normal {x50:.1f} kt "
            f"({np.percentile(bs[:, 0], 2.5):.1f} to {np.percentile(bs[:, 0], 97.5):.1f}), half of own calm {x50c:.1f} kt "
            f"({np.percentile(bs[:, 1], 2.5):.1f} to {np.percentile(bs[:, 1], 97.5):.1f})")

say("\nMETAR GUST SPREAD")
m = h[h["wind_src"] == "metar"]
for thr in (20, 25, 30, 40):
    say(f"  METAR hours with gust spread above {thr} kt: {int((m['gust_spread'] > thr).sum())}")
say("  top values: " + ", ".join(f"{v:.0f}" for v in m["gust_spread"].sort_values(ascending=False).head(6).values))
for name, d in (("all hours", h), ("METAR gust spread above 30 kt left out", h[~((h["wind_src"] == "metar") & (h["gust_spread"] > 30))])):
    beta, keep, rows = spline_fit(d.to_dict("records"))
    hw = float(np.median([r["hw"] for r in rows]))
    gs = float(np.median([r["gust_spread"] for r in rows]))
    grid = np.arange(0, 20.05, 0.1)
    say(f"  spline point estimate, {name}: {first_crossing(grid, curve_at(beta, keep, grid, [hw] * len(grid), [gs] * len(grid))):.2f} kt")
open(OUT, "w").write("\n".join(L) + "\n")
