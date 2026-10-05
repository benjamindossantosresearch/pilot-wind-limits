#!/usr/bin/env python3
"""
q1b_exceedance.py

Q1b: how often piston GA approaches are flown with a crosswind above the
aircraft's POH maximum demonstrated crosswind, fleet against private. Rules as
logged in notes/decisions.md (2026-10-02, "Q1b"):

  unit        approach (detector v3.0.1), piston GA, VMC, study airports in their windows
  crosswind   one-minute ASOS two-minute sustained wind at the minute of the approach's
              lowest observed point, component on the runway end's true course
              (gust version: five-second gust)
  exceedance  crosswind above the POH maximum demonstrated crosswind for the
              aircraft (reference/poh_types.csv via poh.py). Primary: published
              values only. Sensitivity: family values where none is published.
  reported    exceedance share overall and by ownership, bootstrap intervals
              clustered by aircraft and, separately, by day (the wider is
              reported), and the distribution of crosswind / max demonstrated.

    python3 q1b_exceedance.py q2/approaches.csv

Writes q1b/summary.txt.
"""

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

RNG = np.random.default_rng(20261002)
BOOT = 1000
RATIO_MARKS = (0.5, 0.75, 1.0)


def windows():
    w = json.load(open("q1a/windows.json"))
    w.update(json.load(open("q1a/windows_untowered.json")))
    return w


def in_window(r, w):
    start = w.get(r["airport"])
    if not start or r["date"] < start or r["date"] > "2026-09-30":
        return False
    excl = w.get(r["airport"] + "_exclude_from")
    return not (excl and r["date"] >= excl)


def share_ci(rows, key_fn, cluster_key):
    """Share of rows with key_fn true, percentile bootstrap over clusters."""
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        c = by[r[cluster_key]]
        c[0] += key_fn(r)
        c[1] += 1
    arr = np.array(list(by.values()), dtype=float)
    est = arr[:, 0].sum() / arr[:, 1].sum()
    n = len(arr)
    boots = [(s := arr[RNG.integers(0, n, n)])[:, 0].sum() / s[:, 1].sum() for _ in range(BOOT)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return est, lo, hi


def fmt_share(rows, key_fn):
    if not rows:
        return "no approaches"
    e, a_lo, a_hi = share_ci(rows, key_fn, "icao")
    _, d_lo, d_hi = share_ci(rows, key_fn, "daykey")
    lo, hi = min(a_lo, d_lo), max(a_hi, d_hi)
    k = sum(key_fn(r) for r in rows)
    return f"{100 * e:.2f}% ({k:,} of {len(rows):,}; 95% CI {100 * lo:.2f} to {100 * hi:.2f}, wider of aircraft and day clustering)"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    w = windows()
    rows, dropped = [], defaultdict(int)
    for r in csv.DictReader(open(sys.argv[1])):
        if r["group"] != "piston":
            continue
        if not in_window(r, w):
            dropped["outside window"] += 1
            continue
        if r["vmc"] != "1":
            dropped["not VMC"] += 1
            continue
        if not r["xw_low_kt"]:
            dropped["no wind"] += 1
            continue
        if not r["poh_xwind_kt"]:
            dropped["no POH value (type not in table)"] += 1
            continue
        r["xw"] = float(r["xw_low_kt"])
        r["gxw"] = float(r["gust_xw_low_kt"]) if r["gust_xw_low_kt"] else r["xw"]
        r["demo"] = float(r["poh_xwind_kt"])
        r["daykey"] = f"{r['airport']}|{r['date']}"
        rows.append(r)
    pub = [r for r in rows if r["poh_xwind_basis"] == "published"]
    lines = [f"Q1b: piston GA approaches, VMC, study airports in their windows",
             f"Approaches with wind and a POH value: {len(rows):,} (published value {len(pub):,}, family value {len(rows) - len(pub):,})",
             "Dropped: " + ", ".join(f"{k} {v:,}" for k, v in sorted(dropped.items())), ""]
    for label, sel in (("PRIMARY (published POH values)", pub), ("SENSITIVITY (published and family values)", rows)):
        lines.append(label)
        for name, fn in (("sustained crosswind above max demonstrated", lambda r: r["xw"] > r["demo"]),
                         ("gust crosswind above max demonstrated", lambda r: r["gxw"] > r["demo"])):
            lines.append(f"  {name}:")
            lines.append(f"    all      {fmt_share(sel, fn)}")
            for own in ("fleet", "private", "trust"):
                sub = [r for r in sel if r["ownership"] == own]
                if sub:
                    lines.append(f"    {own:8s} {fmt_share(sub, fn)}")
        ratios = np.array([r["xw"] / r["demo"] for r in sel])
        gratios = np.array([r["gxw"] / r["demo"] for r in sel])
        if len(ratios):
            q = np.percentile(ratios, [50, 90, 99, 99.9])
            gq = np.percentile(gratios, [50, 90, 99, 99.9])
            lines.append("  crosswind / max demonstrated, sustained: median {:.2f}, p90 {:.2f}, p99 {:.2f}, p99.9 {:.2f}".format(*q))
            lines.append("  crosswind / max demonstrated, gust:      median {:.2f}, p90 {:.2f}, p99 {:.2f}, p99.9 {:.2f}".format(*gq))
            lines.append("  share above " + ", ".join(f"{m:.2f}: sustained {100 * (ratios > m).mean():.2f}%, gust {100 * (gratios > m).mean():.2f}%"
                                                      for m in RATIO_MARKS))
        by_type = defaultdict(list)
        for r in sel:
            by_type[r["type"]].append(r)
        lines.append("  by type (types with at least 200 approaches): approaches, max demo, sustained exceedance, gust exceedance")
        for ty, g in sorted(by_type.items(), key=lambda x: -len(x[1])):
            if len(g) < 200:
                continue
            demos = sorted({r["demo"] for r in g})
            lines.append(f"    {ty:5s} {len(g):7,}  {'/'.join(f'{d:g}' for d in demos):>7s} kt  "
                         f"{100 * np.mean([r['xw'] > r['demo'] for r in g]):5.2f}%  {100 * np.mean([r['gxw'] > r['demo'] for r in g]):5.2f}%")
        lines.append("")
    os.makedirs("q1b", exist_ok=True)
    text = "\n".join(lines)
    open("q1b/summary.txt", "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
