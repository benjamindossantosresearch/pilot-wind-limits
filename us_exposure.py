#!/usr/bin/env python3
"""
us_exposure.py

Exploratory analyses X1 to X4 (notes/decisions.md, 2026-10-02 20:45), suggested
by Benjamin, logged before running and reported as exploratory.

  X1  round-number line at 10 kt: activity per 1 kt bin of crosswind and of wind speed
  X2  airports with one usable runway against more than one
  X3  airport crosswind climate (share of VMC hours with 10 kt or more of best-runway crosswind), tertiles
  X4  aircraft home-field exposure (X3 at the airport with most of its arrivals), tertiles

    python3 us_exposure.py

Inputs: q1a_us/hours.csv (us_q1a.py) and q2_us/approaches.csv (via us_q2.load).
Writes q2_us_results/exposure_summary.txt.
"""

import os
from collections import defaultdict

import numpy as np
import pandas as pd

import q1a_crosswind as qc
import us_inclusion as ui
import us_q2

RNG = np.random.default_rng(20261002)
B = 1000
OUT = os.path.join(us_q2.OUT, "exposure_summary.txt")


def bin_ratios(h, key, group, lo=4, hi=16):
    """Activity over normal demand per 1 kt bin with a day-cluster bootstrap."""
    h = h[(h[f"base_{group}"] > 0) & h[key].notna()]
    h = h.assign(b=np.floor(h[key]).astype(int))
    h = h[(h["b"] >= lo) & (h["b"] < hi)]
    days = h.groupby(["airport", "local_date", "b"])[[group, f"base_{group}"]].sum().reset_index()
    days["dk"] = days["airport"] + "|" + days["local_date"]
    codes, inv = np.unique(days["dk"].values, return_inverse=True)
    bins = list(range(lo, hi))
    num = np.zeros((len(codes), len(bins)))
    den = np.zeros((len(codes), len(bins)))
    bi = days["b"].values - lo
    np.add.at(num, (inv, bi), days[group].values)
    np.add.at(den, (inv, bi), days[f"base_{group}"].values)
    est = num.sum(0) / den.sum(0)
    reps = np.empty((B, len(bins)))
    G = len(codes)
    for r in range(B):
        w = np.bincount(RNG.integers(0, G, G), minlength=G)
        reps[r] = (w @ num) / np.maximum(w @ den, 1e-9)
    return bins, est, reps


def x1(h):
    L = ["X1. Round-number line at 10 kt: arrivals over normal demand per 1 kt bin (95% CI)"]
    for key, label in (("xw", "mean best-runway crosswind"), ("speed", "mean wind speed")):
        for group in ("piston", "fleet", "private"):
            bins, est, reps = bin_ratios(h, key, group)
            cells = ", ".join(f"{b}: {e:.2f}" for b, e in zip(bins, est))
            L.append(f"  {label}, {group}: {cells}")
            i8, i10, i12 = bins.index(8), bins.index(10), bins.index(12)
            s1 = (est[i8] - est[i10]) / 2
            s2 = (est[i10] - est[i12]) / 2
            d = (reps[:, i10] - reps[:, i12]) / 2 - (reps[:, i8] - reps[:, i10]) / 2
            L.append(f"    drop per kt, 8 to 10 kt: {s1:.3f}; 10 to 12 kt: {s2:.3f}; difference {s2 - s1:+.3f} "
                     f"(95% CI {np.percentile(d, 2.5):+.3f} to {np.percentile(d, 97.5):+.3f})")
    return L


def limit_rows(h, label):
    return qc.empirical_limit(h.to_dict("records"), "piston", f"{label}, piston") + \
        qc.empirical_limit(h.to_dict("records"), "fleet", f"{label}, fleet") + \
        qc.empirical_limit(h.to_dict("records"), "private", f"{label}, private")


def q2_effects(Q, label):
    L = []
    for value in ("S_fp", "S_spd"):
        L += us_q2.wind_effects(Q, value, label)
    T = Q[Q["S_turn"].notna()]
    L += us_q2.wind_effects(T, "S_turn", label + " turn to final")
    return [l for l in L if "above 2" in l or "log" in l]


def main():
    inc = ui.load()
    h = pd.read_csv("q1a_us/hours.csv")
    # airport attributes
    n_rwy = {a: len(inc.usable_ends(a)) // 2 for a in h["airport"].unique()}
    vmc = h.groupby("airport")["xw"].apply(lambda s: float((s >= 10).mean()))
    terc = pd.qcut(vmc, 3, labels=["low", "middle", "high"])
    h["single"] = h["airport"].map(lambda a: n_rwy.get(a, 0) == 1)
    h["climate"] = h["airport"].map(terc)
    L = [f"Exploratory analyses X1 to X4, US sample. Airports: {h['airport'].nunique()}, single-runway {sum(1 for v in n_rwy.values() if v == 1)}. "
         f"Crosswind climate tertile cut points (share of VMC hours with 10 kt or more): "
         f"{vmc.quantile(1 / 3):.3f}, {vmc.quantile(2 / 3):.3f}", ""]
    L += x1(h) + [""]

    L.append("X2/X3. Revealed limits by runway layout and crosswind climate")
    for label, sel in (("one runway", h[h["single"]]), ("more than one runway", h[~h["single"]])):
        L += limit_rows(sel, label)
    for t in ("low", "middle", "high"):
        L += limit_rows(h[h["climate"] == t], f"crosswind climate {t}")
    L.append("")

    df = us_q2.load()
    Q2 = df[(df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok")].copy()
    Q2["single"] = Q2["airport"].map(lambda a: n_rwy.get(a, len(inc.usable_ends(a)) // 2) == 1)
    Q2["climate"] = Q2["airport"].map(terc)
    L.append("X2/X3. Q2 wind effects (change in points against calm, airport-runway effects absorbed)")
    for label, sel in (("one runway", Q2[Q2["single"]]), ("more than one runway", Q2[~Q2["single"]])):
        L += q2_effects(sel, label)
    for t in ("low", "middle", "high"):
        L += q2_effects(Q2[Q2["climate"] == t], f"crosswind climate {t}")
    L.append("")

    # X4: home field of each aircraft from the arrivals in the approach data
    P = df[(df["group"] == "piston") & (df["vmc"] == 1)]
    first = P.drop_duplicates(["icao", "date", "airport"])
    counts = first.groupby(["icao", "airport"]).size().reset_index(name="n")
    tot = counts.groupby("icao")["n"].sum()
    top = counts.sort_values("n", ascending=False).drop_duplicates("icao").set_index("icao")
    home = top[(top["n"] >= 20) & (top["n"] / tot.reindex(top.index) >= 0.5)]["airport"]
    Q2["home_exposure"] = Q2["icao"].map(home).map(vmc)
    hq = Q2[Q2["home_exposure"].notna()].copy()
    cuts = hq.drop_duplicates("icao")["home_exposure"].quantile([1 / 3, 2 / 3]).values
    hq["home_t"] = np.select([hq["home_exposure"] <= cuts[0], hq["home_exposure"] <= cuts[1]], ["low", "middle"], "high")
    L.append(f"X4. Home-field exposure: {hq['icao'].nunique():,} aircraft with a home field, {len(hq):,} approaches; "
             f"tertile cut points {cuts[0]:.3f}, {cuts[1]:.3f}")
    for t in ("low", "middle", "high"):
        L += q2_effects(hq[hq["home_t"] == t], f"home exposure {t}")
    text = "\n".join(L)
    open(OUT, "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
