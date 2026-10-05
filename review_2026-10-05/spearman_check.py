#!/usr/bin/env python3
"""
spearman_check.py

Spearman rank correlation between Benjamin's blind ratings of the 30 review approaches (q2_review/answers) and
the scores as they stand in the paper: the registered New England score s, the locked flight-path score S_fp,
the speed score S_spd, and the combined score. Scores come from the New England file the paper uses
(q2/approaches.csv: review fixes applied, calibrated airspeed). Intervals: percentile bootstrap over the
reviewed approaches (10,000 resamples) and the Fisher z interval with the Bonett-Wright variance.

    python3 review_2026-10-05/spearman_check.py
"""

import csv
import glob
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import us_q2  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spearman_check.txt")
RV = {"stable": 0, "minor": 1, "out": 2, "severe": 3}


def rank(x):
    o = x.argsort()
    r = np.empty(len(x))
    r[o] = np.arange(len(x))
    for v in np.unique(x):
        m = x == v
        r[m] = r[m].mean()
    return r


def spearman(a, b):
    return float(np.corrcoef(rank(a), rank(b))[0, 1])


def main():
    key = {r["id"]: r for r in csv.DictReader(open("q2_review/key.csv"))}
    ans = {os.path.basename(f)[:3]: json.load(open(f)) for f in glob.glob("q2_review/answers/*.json")}
    cols = ["airport", "visit", "app_no", "s", "status", "inferred"] + us_q2.FP + us_q2.SPD
    df = pd.read_csv("q2/approaches.csv", usecols=cols, low_memory=False)
    df["S_fp"] = df[us_q2.FP].max(axis=1, skipna=True)
    df["S_spd"] = df[us_q2.SPD].max(axis=1, skipna=True)
    df["S_comb"] = df[["S_fp", "S_spd"]].max(axis=1, skipna=True)
    df["app_no"] = df["app_no"].astype(str)
    idx = df.set_index(["airport", "visit", "app_no"])
    rows = []
    for rid, k in sorted(key.items()):
        try:
            r = idx.loc[(k["airport"], k["visit"], str(k["app_no"]))]
        except KeyError:
            continue
        if isinstance(r, pd.DataFrame):
            r = r.iloc[0]
        rows.append({"id": rid, "rating": RV[ans[rid]["rating"]], "status": r["status"], "s": r["s"], "S_fp": r["S_fp"],
                     "S_spd": r["S_spd"], "S_comb": r["S_comb"]})
    R = pd.DataFrame(rows)
    rng = np.random.default_rng(20261005)
    L = [f"Blind review: {len(ans)} answers, {len(R)} matched in q2/approaches.csv, {int((R['status'] == 'ok').sum())} measurable now", ""]
    for c in ("s", "S_fp", "S_spd", "S_comb"):
        d = R[R["status"].eq("ok") & R[c].notna()]
        n = len(d)
        a, b = d[c].values, d["rating"].values.astype(float)
        rho = spearman(a, b)
        boots = []
        for _ in range(10000):
            i = rng.integers(0, n, n)
            if len(np.unique(b[i])) > 1 and len(np.unique(a[i])) > 1:
                boots.append(spearman(a[i], b[i]))
        z = math.atanh(rho)
        se = math.sqrt((1 + rho ** 2 / 2) / (n - 3))
        L.append(f"{c:7s} n={n}: Spearman {rho:.2f} (bootstrap 95% {np.percentile(boots, 2.5):.2f} to {np.percentile(boots, 97.5):.2f}; "
                 f"Fisher z with Bonett-Wright variance {math.tanh(z - 1.96 * se):.2f} to {math.tanh(z + 1.96 * se):.2f})")
    L.append("")
    L.append("Per approach: id, rating (0 stabilized to 3 far off), status, s, S_fp, S_spd")
    for _, r in R.iterrows():
        L.append(f"  {r['id']} {r['rating']} {r['status']:>18s} {r['s']:.2f} {r['S_fp']:.2f} {r['S_spd']:.2f}")
    text = "\n".join(L)
    open(OUT, "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
