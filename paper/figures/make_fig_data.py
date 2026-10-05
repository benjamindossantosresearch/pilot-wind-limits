#!/usr/bin/env python3
"""
make_fig_data.py

Figure data for the paper, from the frozen outputs (notes/freeze_2026-10-03.md). Uses the
same loader and filters as us_q2.py, so every plotted share matches the tables.

  activity_<sample>.csv   arrivals over normal demand in 2 kt crosswind bins, piston, fleet,
                          private, with day-cluster bootstrap intervals (from the Q1a hours)
  shares_<sample>.csv     share of measurable approaches above 1, 2, 3 in 2 kt crosswind bins:
                          S_fp, S_spd, S_turn (piston) and S_fp (jets, straight-in), with
                          aircraft-cluster bootstrap intervals
  direction_<sample>.csv  overshoot above 200 ft and late alignment by crosswind relative to
                          the base leg, 2 kt bins, piston pattern approaches
  poh_xwind_<sample>.csv  maximum demonstrated crosswind of the piston approaches (published)

    cd /home/dev/wind-limits && python3 paper/figures/make_fig_data.py
    US_Q2_SAMPLE=ne US_Q2_APPROACHES=q2/approaches.csv US_Q2_OUT=q2_ne_locked \
        US_Q2_Q1A=q1a/window/summary.txt python3 paper/figures/make_fig_data.py

Writes paper/figures/data/.
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
import us_q2  # noqa: E402

OUT = "paper/figures/data"
B = 1000
RNG = np.random.default_rng(20261003)
BINS = list(range(0, 22, 2))


def cluster_share(y, clusters):
    codes, inv = np.unique(clusters, return_inverse=True)
    num = np.bincount(inv, weights=y)
    den = np.bincount(inv).astype(float)
    G = len(codes)
    reps = np.empty(B)
    for r in range(B):
        w = np.bincount(RNG.integers(0, G, G), minlength=G)
        reps[r] = (w @ num) / max(w @ den, 1)
    return num.sum() / den.sum(), np.percentile(reps, 2.5), np.percentile(reps, 97.5)


def activity(sample):
    path = "q1a_us/hours.csv" if sample == "us" else "q1a/window/hours.csv"
    h = pd.read_csv(path)
    h = h[h["xw"].notna()]
    h["b"] = np.floor(h["xw"] / 2).astype(int) * 2
    h["dk"] = h["airport"] + "|" + h["local_date"].astype(str)
    rows = []
    for grp in ("piston", "fleet", "private"):
        if f"base_{grp}" not in h:
            continue
        g = h[h[f"base_{grp}"] > 0]
        codes, inv = np.unique(g["dk"].values, return_inverse=True)
        bins = sorted(b for b in g["b"].unique() if b < 24)
        bi = {b: k for k, b in enumerate(bins)}
        num = np.zeros((len(codes), len(bins)))
        den = np.zeros((len(codes), len(bins)))
        sel = g["b"].isin(bins).values
        idx = np.array([bi[b] for b in g["b"].values[sel]])
        np.add.at(num, (inv[sel], idx), g[grp].values[sel])
        np.add.at(den, (inv[sel], idx), g[f"base_{grp}"].values[sel])
        G = len(codes)
        reps = np.empty((B, len(bins)))
        for r in range(B):
            w = np.bincount(RNG.integers(0, G, G), minlength=G)
            reps[r] = (w @ num) / np.maximum(w @ den, 1e-9)
        est = num.sum(0) / den.sum(0)
        hours = np.bincount(idx, minlength=len(bins))
        for k, b in enumerate(bins):
            rows.append({"group": grp, "bin_lo": b, "bin_mid": b + 1, "hours": int(hours[k]), "activity": est[k],
                         "lo": np.percentile(reps[:, k], 2.5), "hi": np.percentile(reps[:, k], 97.5)})
    return pd.DataFrame(rows)


def shares(df):
    P = df[(df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok")]
    J = df[(df["group"] == "jet") & (df["vmc"] == 1) & (df["status"] == "ok") & (df["straight_in"] == "yes")]
    rows = []
    for who, D, value in (("piston", P, "S_fp"), ("piston", P, "S_spd"), ("piston", P[P["S_turn"].notna()], "S_turn"),
                          ("jet", J, "S_fp")):
        D = D[D[value].notna() & D["xw_kt"].notna()]
        for a in BINS[:-1]:
            g = D[(D["xw_kt"] >= a) & (D["xw_kt"] < a + 2)]
            if len(g) < 100:
                continue
            for thr in (1, 2, 3):
                e, lo, hi = cluster_share((g[value].values > thr).astype(float), g["icao"].values)
                rows.append({"who": who, "score": value, "threshold": thr, "bin_lo": a, "bin_mid": a + 1, "n": len(g),
                             "share": e, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def direction(df):
    T = df[(df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok") & df["S_turn"].notna()]
    T = T[T["xw_from_base_kt"].notna()]
    rows = []
    for a in range(-16, 16, 2):
        g = T[(T["xw_from_base_kt"] >= a) & (T["xw_from_base_kt"] < a + 2)]
        if len(g) < 100:
            continue
        for name, y in (("overshoot_200", g["overshoot_ft"] > 200), ("late_alignment", (g["align_hat"] < 300) | g["align_hat"].isna())):
            e, lo, hi = cluster_share(y.values.astype(float), g["icao"].values)
            rows.append({"measure": name, "bin_lo": a, "bin_mid": a + 1, "n": len(g), "share": e, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def main():
    sample = us_q2.SAMPLE
    os.makedirs(OUT, exist_ok=True)
    activity(sample).to_csv(os.path.join(OUT, f"activity_{sample}.csv"), index=False)
    df = us_q2.load()
    shares(df).to_csv(os.path.join(OUT, f"shares_{sample}.csv"), index=False)
    direction(df).to_csv(os.path.join(OUT, f"direction_{sample}.csv"), index=False)
    P = df[(df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok") & (df["poh_xwind_basis"] == "published")]
    P["poh_xwind_kt"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).to_csv(os.path.join(OUT, f"poh_xwind_{sample}.csv"))
    print("done", sample)


if __name__ == "__main__":
    main()
