#!/usr/bin/env python3
"""Checks of the outside audit's claims on q1a_us/hours.csv (2026-10-05, logged in notes/decisions.md)."""
import math
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import q1a_crosswind as qc  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_checks.txt")
L = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def rows_of(d):
    return d.to_dict("records")


def limit(d, label, key="xw", grp="piston"):
    r = qc.empirical_limit(rows_of(d), grp, label, key=key)
    return r


def rebase(d):
    d = d.copy()
    for g in ("piston", "fleet", "private"):
        d[f"base_{g}"] = d.groupby(["airport", "season", "weekend", "hour"])[g].transform("mean")
    return d


def act(d, grp="piston"):
    return d[grp].sum() / d[f"base_{grp}"].sum() if len(d) else float("nan")


def binned_deviance(d, key, width=2.0, cap=40.0):
    y = d["piston"].values.astype(float)
    mu0 = d["base_piston"].values
    mu0 = mu0 * y.sum() / mu0.sum()
    b = np.minimum(np.floor(d[key].values / width), cap / width)
    df = pd.DataFrame({"b": b, "y": y, "base": d["base_piston"].values})
    rate = df.groupby("b")["y"].transform("sum") / df.groupby("b")["base"].transform("sum")
    mu1 = df["base"].values * rate.values

    def dev(mu):
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(y > 0, y * np.log(y / mu), 0.0)
        return 2 * np.sum(t - (y - mu))
    return dev(mu0) - dev(mu1), df["b"].nunique()


def main():
    h = pd.read_csv("q1a_us/hours.csv")
    h = h[h["base_piston"] > 0]
    say(f"Hours with a piston baseline: {len(h):,}")

    # wind source
    say("\nWIND SOURCE")
    for src in ("onemin", "metar"):
        g = h[h["wind_src"] == src]
        say(f"  {src}: {len(g):,} hours ({100 * len(g) / len(h):.1f}%), gust spread median {g['gust_spread'].median():.1f} kt, "
            f"zero on {100 * (g['gust_spread'] == 0).mean():.1f}%, max {g['gust_spread'].max():.1f} kt, above 30 kt {int((g['gust_spread'] > 30).sum())}")
        for line in limit(g, f"  model-free, {src} hours only"):
            say(line)
    lowg = h[(h["gust_spread"] <= 6.4) & (h["xw"] >= 12)]
    say(f"  low-gust (6.4 kt or less) hours with crosswind 12 kt or more: {len(lowg):,}, of which METAR {int((lowg['wind_src'] == 'metar').sum()):,}")
    for src in ("onemin", "metar"):
        g = h[(h["wind_src"] == src) & (h["gust_spread"] <= 6.4)]
        for line in limit(g, f"  low-gust hours, {src} only"):
            say(line)
    g = h[(h["wind_src"] == "onemin") & (h["gust_spread"] >= 8)]
    for line in limit(g, "  gust spread 8 kt or more, onemin only"):
        say(line)

    # wind speed against crosswind (one-minute hours)
    o = h[h["wind_src"] == "onemin"].copy()
    o["mostly_x"] = o["xw"] >= o["hw"].abs()
    say("\nACTIVITY BY TOTAL WIND, one-minute hours: crosswind under 3 kt | wind mostly across the runway (crosswind at least |headwind|)")
    for a, b in ((0, 5), (5, 8), (8, 11), (11, 14), (14, 17), (17, 20), (20, 99)):
        s = o[(o["speed"] >= a) & (o["speed"] < b)]
        g1, g2 = s[s["xw"] < 3], s[s["mostly_x"]]
        say(f"  {a}-{b if b < 99 else '+'} kt: {act(g1):.2f} (n={len(g1):,}) | {act(g2):.2f} (n={len(g2):,})")
    for name, g in (("crosswind under 3 kt", o[o["xw"] < 3]), ("mostly crosswind", o[o["mostly_x"]]), ("all one-minute hours", o)):
        for line in limit(g, f"  half point against total wind, {name}", key="speed"):
            say(line)
    say("\nDEVIANCE EXPLAINED by one-variable 2 kt binned Poisson fits (one-minute hours, offset normal demand)")
    o["peak_gust"] = o["speed"] + o["gust_spread"]
    for key in ("xw", "hw", "speed", "peak_gust", "gust_spread", "gust_xw"):
        dv, nb = binned_deviance(o, key)
        say(f"  {key:12s} {dv:10,.0f} ({nb} bins)")
    # crosswind effect at fixed total wind
    say("\nCROSSWIND AT FIXED TOTAL WIND, one-minute hours: activity by crosswind band within total wind bands")
    for a, b in ((8, 11), (11, 14), (14, 17), (17, 20)):
        s = o[(o["speed"] >= a) & (o["speed"] < b)]
        cells = []
        for xa, xb in ((0, 3), (3, 6), (6, 9), (9, 12), (12, 15), (15, 99)):
            g = s[(s["xw"] >= xa) & (s["xw"] < xb)]
            if len(g) >= 100:
                cells.append(f"xw {xa}-{xb if xb < 99 else '+'}: {act(g):.2f} (n={len(g):,})")
        say(f"  total wind {a}-{b} kt: " + ", ".join(cells))

    # base rate
    say("\nBASE RATE for the demonstrated-crosswind share (all hours)")
    s = h[h["xw"] >= 15]
    say(f"  hours with best-runway crosswind 15 kt or more: {len(s):,} ({100 * len(s) / len(h):.3f}% of hours), "
        f"{100 * s['base_piston'].sum() / h['base_piston'].sum():.3f}% of normal demand, {100 * s['piston'].sum() / h['piston'].sum():.3f}% of arrivals, activity {act(s):.2f}")

    # calm activity and half of calm
    say("\nCALM ACTIVITY")
    calm = h[h["xw"] < 4]
    c = act(calm)
    say(f"  activity at crosswind under 4 kt: {c:.3f}")
    days = defaultdict(lambda: np.zeros((len(qc.FINE), 2)))
    for r in rows_of(h[["airport", "local_date", "xw", "piston", "base_piston"]]):
        for j, (a, b) in enumerate(qc.FINE):
            if a <= r["xw"] < b:
                days[(r["airport"], r["local_date"])][j] += (r["piston"], r["base_piston"])
                break
    tot = np.array(list(days.values())).sum(axis=0)
    ratio = tot[:, 0] / tot[:, 1]
    mids = [(a + b) / 2 for a, b in qc.FINE]
    for p, lab in ((0.5, "half of normal demand"), (0.5 * c, "half of calm activity")):
        for j in range(1, len(mids)):
            if ratio[j] <= p:
                x = mids[j - 1] + (ratio[j - 1] - p) / (ratio[j - 1] - ratio[j]) * (mids[j] - mids[j - 1])
                say(f"  crossing of {lab} ({p:.3f}): {x:.1f} kt")
                break

    # capture correction with the all-12 slope
    say("\nCAPTURE CORRECTION with the all-12-airport development slope")
    for pct in (-0.064, -0.082):
        b = math.log(1 + pct) / 10.0
        d = h.copy()
        f = np.exp(b * d["speed"].values)
        for g in ("piston", "fleet", "private"):
            d[g] = d[g] / f
        d = rebase(d)
        say(limit(d, f"  {100 * pct:.1f}% per 10 kt")[1].replace("  revealed limit 50%", f"  {100 * pct:.1f}% per 10 kt: revealed limit 50%"))
    open(OUT, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
