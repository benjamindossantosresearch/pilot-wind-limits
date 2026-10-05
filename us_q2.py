#!/usr/bin/env python3
"""
us_q2.py

Q1b and Q2 for the US confirmatory sample, by the outcomes and plan locked in
notes/decisions.md before the US data were analyzed:

  S_fp    flight-path score (primary): centerline, lined up, glide path, sink value, sink consistency
  S_spd   speed score: speed value against the POH approach speed, speed consistency around its trend
  S_comb  the larger of the two
  S_turn  turn to final: overshoot / 200 ft, and 300 ft / alignment height (cap 6), pattern approaches with a base leg

Inclusion: us_inclusion.py (airport-months with coverage to 300 ft of at least 0.60, outage days and
known closures out). Q2 population: piston, VMC, measurable at 300 ft. Q1b: piston, VMC, wind at the
lowest point and a published POH crosswind.

Distributions use every approach. Intervals for shares come from cluster bootstraps over aircraft and
over days (500 each, the wider reported). At US scale, airport-runway effects are absorbed in linear
probability and log-score models (within-group demeaning) with aircraft-clustered standard errors, in
place of the New England logistic models, which do not scale to thousands of airport-runways.

    python3 us_q2.py

Writes q2_us_results/summary.txt and q2_us_results/bands.csv. Environment US_Q2_APPROACHES and US_Q2_OUT
select another approaches file and output folder (detector v3.1: q2_us_v31/approaches.csv, q2_us_results_v31).
"""

import math
import os
import re

import numpy as np
import pandas as pd

import us_airports as ua
import us_inclusion as ui
import us_q1a

# Primary since 2026-10-02 (Benjamin): detector v3.1 and no inferred approaches in Q2. The v3.0.1 run is
# q2_us/approaches.csv with results in q2_us_results/ (inferred approaches included, as first registered).
OUT = os.environ.get("US_Q2_OUT", "q2_us_results_v31_cas")   # v3.1, no inferred approaches, calibrated airspeed
APPROACHES = os.environ.get("US_Q2_APPROACHES", "q2_us_v31_cas/approaches.csv")
KEEP_INFERRED = os.environ.get("US_Q2_KEEP_INFERRED") == "1"   # 1 reproduces the as-registered sample
# US_Q2_SAMPLE=ne runs the New England development sample (q2/approaches.csv, Q1a windows) on the same scores,
# with US_Q2_Q1A pointing at the New England Q1a summary for the revealed limit.
SAMPLE = os.environ.get("US_Q2_SAMPLE", "us")
Q1A_SUMMARY = os.environ.get("US_Q2_Q1A", "q1a_us/summary.txt")
RNG = np.random.default_rng(20261010)
B = 500
FP = ["g_c1", "g_c2a", "g_c3", "b_c1", "b_c2a", "b_c3", "g_c4_afh", "b_c4_afh", "c4_stab"]
SPD = ["g_c5a", "b_c5a", "g_c5b_detr"]
NAMES = {"g_c1": "centerline at 300 ft", "b_c1": "centerline 300-100 ft", "g_c2a": "lined up at 300 ft",
         "b_c2a": "lined up 300-100 ft", "g_c3": "glide path at 300 ft", "b_c3": "glide path 300-100 ft",
         "g_c4_afh": "sink value at 300 ft", "b_c4_afh": "sink value 300-100 ft", "c4_stab": "sink consistency",
         "g_c5a": "speed value at 300 ft", "b_c5a": "speed value 300-100 ft", "g_c5b_detr": "speed consistency"}
XW = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 99)]
FRAC = [(0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 9)]
GUST = [(0, 0.5), (0.5, 5), (5, 10), (10, 99)]
HW = [(-99, 0), (0, 5), (5, 10), (10, 15), (15, 99)]
TYPE_GROUPS = {"C172": "C172", "P28A": "P28A", "SR20": "SR20", "SR22": "SR22", "S22T": "SR22", "C182": "C182", "P28R": "P28R"}
BANDS_ROWS = []


def load():
    cols = ["airport", "date", "icao", "type", "group", "ownership", "runway", "status", "vmc", "straight_in", "height_source",
            "nacp", "apps_in_visit", "base_side", "xw_kt", "hw_kt", "gust_spread", "xw_low_kt", "gust_xw_low_kt", "xw_right_kt",
            "xw_from_base_kt", "poh_xwind_kt", "poh_xwind_basis", "overshoot_ft", "align_hat", "lowest_hat", "turn_max_bank",
            "flag_practice", "hat_true_minus_geom_ft", "s", "inferred", "wind_kt"] + FP + SPD
    df = pd.read_csv(APPROACHES, usecols=cols, low_memory=False)
    if SAMPLE == "ne":
        import q2_wind
        w = q2_wind.windows()
        ok = [q2_wind.in_window({"airport": a, "date": d}, w) for a, d in zip(df["airport"].values, df["date"].values)]
    else:
        inc = ui.load()
        ok = [inc.day_ok(a, d) for a, d in zip(df["airport"].values, df["date"].values)]
    df = df[np.array(ok)].copy()
    if not KEEP_INFERRED:
        # inferred approaches (detector rules 5, 6, 7, 11) were not observed, so they have no flight path to
        # score: not measurable for Q2. They stay in Q1b, which counts operations, not flight paths.
        df.loc[df["inferred"].notna(), "status"] = "inferred"
    sites = ua.load()
    df["tower"] = df["airport"].map(lambda a: sites[a].tower.startswith("ATCT"))
    df["region"] = df["airport"].map(lambda a: us_q1a.region_of(sites[a].state))
    df["S_fp"] = df[FP].max(axis=1, skipna=True)
    df["S_spd"] = df[SPD].max(axis=1, skipna=True)
    df["S_comb"] = df[["S_fp", "S_spd"]].max(axis=1, skipna=True)
    turn = (df["straight_in"] == "no") & df["base_side"].notna()
    t1 = df["overshoot_ft"] / 200.0
    alt = df["align_hat"].where(df["align_hat"].notna(), df["lowest_hat"])
    t2 = (300.0 / alt.clip(lower=50.0)).clip(upper=6.0)
    df["S_turn"] = np.where(turn, np.fmax(t1.fillna(0), t2), np.nan)
    df["frac"] = df["xw_kt"] / df["poh_xwind_kt"]
    df["typeg"] = df["type"].map(lambda t: TYPE_GROUPS.get(t, "other"))
    df["own"] = df["ownership"].where(df["ownership"].isin(["fleet", "private"]), "other")
    m = pd.to_datetime(df["date"]).dt.month
    df["season"] = np.select([m.isin([12, 1, 2]), m.isin([3, 4, 5]), m.isin([6, 7, 8])], ["DJF", "MAM", "JJA"], "SON")
    df["aptrwy"] = df["airport"] + "/" + df["runway"].astype(str)
    df["dayk"] = df["airport"] + "|" + df["date"]
    return df


# ---------------------------------------------------------------- shares with cluster bootstrap

def share_ci(y, clusters):
    """Share of y with a cluster bootstrap on cluster totals."""
    codes, inv = np.unique(clusters, return_inverse=True)
    num = np.bincount(inv, weights=y)
    den = np.bincount(inv)
    est = num.sum() / den.sum()
    G = len(codes)
    reps = np.empty(B)
    for i in range(B):
        w = np.bincount(RNG.integers(0, G, G), minlength=G)
        reps[i] = (w * num).sum() / max((w * den).sum(), 1)
    return est, np.percentile(reps, 2.5), np.percentile(reps, 97.5)


def shares(d, value, thr):
    y = (d[value].values > thr).astype(float)
    e, a_lo, a_hi = share_ci(y, d["icao"].values)
    _, d_lo, d_hi = share_ci(y, d["dayk"].values)
    return e, min(a_lo, d_lo), max(a_hi, d_hi)


def banded(d, key, bands, value, label):
    d = d[d[key].notna() & d[value].notna()]
    L = [f"{label}: {value} by {key}. median / p90 / p99 | above 1, above 2, above 3 (95% CI, wider of aircraft and day bootstrap) | n"]
    for a, b in bands:
        g = d[(d[key] >= a) & (d[key] < b)]
        name = f"{a:g}+" if b >= 99 or (key == "frac" and b >= 9) else (f"<{b:g}" if a <= -99 else f"{a:g}-{b:g}")
        if len(g) < 30:
            L.append(f"  {name:>9s}: n={len(g)} (too few)")
            continue
        s = g[value].values
        cells = []
        row = {"table": label, "key": key, "value": value, "band": name, "n": len(g), "median": np.median(s),
               "p90": np.percentile(s, 90), "p99": np.percentile(s, 99)}
        for thr in (1, 2, 3):
            e, lo, hi = shares(g, value, thr)
            cells.append(f"{100 * e:5.1f}% ({100 * lo:.1f}-{100 * hi:.1f})")
            row.update({f"gt{thr}": e, f"gt{thr}_lo": lo, f"gt{thr}_hi": hi})
        BANDS_ROWS.append(row)
        L.append(f"  {name:>9s}: {np.median(s):.2f} / {np.percentile(s, 90):.2f} / {np.percentile(s, 99):.2f} | " + ", ".join(cells) + f" | {len(g):,}")
    return L


# ---------------------------------------------------------------- linear models with absorbed effects

def demean(frame, cols, by):
    return frame[cols] - frame.groupby(by)[cols].transform("mean")


def lpm(d, yname, label, absorb="aptrwy", controls=("typeg", "own", "season", "straight_in", "height_source"), spline=True):
    d = d[d["xw_kt"].notna() & d["hw_kt"].notna() & d["gust_spread"].notna() & d[yname].notna()].copy()
    X = pd.DataFrame({"xw": d["xw_kt"]})
    names = ["xw"]
    if spline:
        for k in (5, 10, 15):
            X[f"xw>{k}"] = (d["xw_kt"] - k).clip(lower=0)
            names.append(f"xw>{k}")
    X["hw"] = d["hw_kt"]
    X["gust"] = d["gust_spread"]
    for c in controls:
        dm = pd.get_dummies(d[c].astype(str), prefix=c, drop_first=True, dtype=float)
        X = pd.concat([X, dm], axis=1)
    X[absorb] = d[absorb].values
    X["_y"] = d[yname].values
    cols = [c for c in X.columns if c not in (absorb,)]
    Z = demean(X, cols, absorb)
    keep = Z.columns[(Z.abs().sum() > 0)]
    Xm = Z[[c for c in keep if c != "_y"]].values
    y = Z["_y"].values
    bread = np.linalg.pinv(Xm.T @ Xm)
    beta = bread @ Xm.T @ y
    e = y - Xm @ beta
    codes, inv = np.unique(d["icao"].values, return_inverse=True)
    S = np.zeros((len(codes), Xm.shape[1]))
    np.add.at(S, inv, Xm * e[:, None])
    G = len(codes)
    V = bread @ (S.T @ S) @ bread * G / max(G - 1, 1)
    xcols = [c for c in keep if c != "_y"]
    pos = {c: i for i, c in enumerate(xcols)}
    return beta, V, pos, len(y)


def lin_combo(beta, V, pos, weights):
    w = np.zeros(len(beta))
    for c, v in weights.items():
        if c in pos:
            w[pos[c]] = v
    est = w @ beta
    se = math.sqrt(max(w @ V @ w, 0))
    return est, est - 1.96 * se, est + 1.96 * se


def wind_effects(d, value, label, absorb="aptrwy", controls=("typeg", "own", "season", "straight_in", "height_source")):
    L = []
    for thr in (1, 2, 3):
        d = d.copy()
        d["_y"] = (d[value] > thr).astype(float)
        beta, V, pos, n = lpm(d, "_y", label, absorb, controls)
        base = d["_y"].mean()
        cells = []
        for x in (5, 10, 15, 20):
            w = {"xw": x}
            for k in (5, 10, 15):
                if x > k:
                    w[f"xw>{k}"] = x - k
            e, lo, hi = lin_combo(beta, V, pos, w)
            cells.append(f"{x} kt {100 * e:+.1f} ({100 * lo:+.1f} to {100 * hi:+.1f})")
        h = lin_combo(beta, V, pos, {"hw": 5})
        g = lin_combo(beta, V, pos, {"gust": 5})
        L.append(f"  {label}, {value} above {thr} (base {100 * base:.1f}%, n={n:,}): change in points against calm crosswind: "
                 + ", ".join(cells) + f". Per 5 kt headwind {100 * h[0]:+.1f} ({100 * h[1]:+.1f} to {100 * h[2]:+.1f}), "
                 f"per 5 kt gust spread {100 * g[0]:+.1f} ({100 * g[1]:+.1f} to {100 * g[2]:+.1f})")
    dd = d[d[value] > 0].copy()
    dd["_ly"] = np.log(dd[value])
    beta, V, pos, n = lpm(dd, "_ly", label, absorb, controls, spline=False)
    e, lo, hi = lin_combo(beta, V, pos, {"xw": 5})
    L.append(f"  {label}, log {value} per 5 kt crosswind: {100 * (math.exp(e) - 1):+.1f}% ({100 * (math.exp(lo) - 1):+.1f} to {100 * (math.exp(hi) - 1):+.1f}), n={n:,}")
    return L


# ---------------------------------------------------------------- main

def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    P = df[(df["group"] == "piston") & (df["vmc"] == 1)]
    Q2 = P[P["status"] == "ok"]
    J = df[(df["group"] == "jet") & (df["vmc"] == 1) & (df["status"] == "ok") & (df["straight_in"] == "yes")]
    q1a_text = open(Q1A_SUMMARY).read() if os.path.exists(Q1A_SUMMARY) else ""
    m = re.search(r"Model-free, piston \[post-hoc, model-free, xw\].*?revealed limit 50%: ([\d.]+) kt", q1a_text, re.S)
    rl = float(m.group(1)) if m else None
    L = [f"{'New England development' if SAMPLE == 'ne' else 'US confirmatory'} sample. Approaches after inclusion: {len(df):,}. Piston VMC: {len(P):,}, measurable at 300 ft: {len(Q2):,}. "
         f"Jets straight-in measurable (floor): {len(J):,}. Airports with measurable piston approaches: {Q2['airport'].nunique()}.",
         f"US revealed limit (model-free 50% point, us_q1a.py): {rl} kt" if rl else "US revealed limit not yet available", ""]

    L.append("1. Q1b: approaches flown above the POH maximum demonstrated crosswind (published values)")
    B1 = P[P["xw_low_kt"].notna() & (P["poh_xwind_basis"] == "published")].copy()
    B1["sust"] = (B1["xw_low_kt"] > B1["poh_xwind_kt"]).astype(float)
    B1["gst"] = (B1["gust_xw_low_kt"].fillna(B1["xw_low_kt"]) > B1["poh_xwind_kt"]).astype(float)
    for label, sel in (("all", B1), ("fleet", B1[B1["ownership"] == "fleet"]), ("private", B1[B1["ownership"] == "private"]),
                       ("towered", B1[B1["tower"]]), ("non-towered", B1[~B1["tower"]])):
        if len(sel) < 100:
            continue
        cells = []
        for col, nm in (("sust", "sustained"), ("gst", "gust")):
            e, lo, hi = shares(sel.assign(_v=sel[col]), "_v", 0.5)
            cells.append(f"{nm} {100 * e:.2f}% ({100 * lo:.2f}-{100 * hi:.2f})")
        L.append(f"  {label:12s} n={len(sel):,}: " + ", ".join(cells))
    fr = (B1["xw_low_kt"] / B1["poh_xwind_kt"]).values
    L.append(f"  crosswind / max demonstrated, sustained: median {np.median(fr):.2f}, p90 {np.percentile(fr, 90):.2f}, p99 {np.percentile(fr, 99):.2f}; "
             f"above 0.5: {100 * np.mean(fr > 0.5):.1f}%, above 0.75: {100 * np.mean(fr > 0.75):.2f}%")
    L.append("")

    L.append("2. Q2 distributions (piston, measurable)")
    for value in ("S_fp", "S_spd", "S_comb"):
        L += banded(Q2, "xw_kt", XW, value, "Piston, crosswind")
    L += banded(J, "xw_kt", XW, "S_fp", "Jets (floor), crosswind")
    L += banded(Q2, "frac", FRAC, "S_fp", "Piston, crosswind as a fraction of max demonstrated")
    L += banded(Q2, "frac", FRAC, "S_spd", "Piston, crosswind as a fraction of max demonstrated")
    L += banded(Q2, "gust_spread", GUST, "S_fp", "Piston, gust spread")
    L += banded(Q2, "hw_kt", HW, "S_fp", "Piston, headwind (negative = tailwind)")
    T = Q2[Q2["S_turn"].notna()]
    L += banded(T, "xw_kt", XW, "S_turn", "Piston pattern approaches with a base leg, turn to final")
    for label, sel in (("fleet", Q2[Q2["ownership"] == "fleet"]), ("private", Q2[Q2["ownership"] == "private"]),
                       ("single arrival", Q2[Q2["apps_in_visit"] == 1]), ("pattern circuits", Q2[Q2["apps_in_visit"] >= 2]),
                       ("towered", Q2[Q2["tower"]]), ("non-towered", Q2[~Q2["tower"]])):
        L += banded(sel, "xw_kt", XW[:4], "S_fp", f"Piston {label}, crosswind")
    L.append("")

    L.append("3. Q2 models: change against calm crosswind, airport-runway effects absorbed, controls for type, ownership, season, entry, height source")
    for value in ("S_fp", "S_spd", "S_comb"):
        L += wind_effects(Q2, value, "Piston")
    L += wind_effects(T, "S_turn", "Piston turn to final")
    L += wind_effects(J, "S_fp", "Jets (floor)", controls=("season",))
    L += ["  Within-aircraft (aircraft effects absorbed, controls season, entry, height source):"]
    L += wind_effects(Q2, "S_fp", "Piston within-aircraft", absorb="icao", controls=("season", "straight_in", "height_source"))
    L.append("")

    L.append("4. Calibration against Q1")
    bands = [("calm, 0-4 kt", Q2["xw_kt"] < 5), ("10-12 kt (New England revealed-limit band)", (Q2["xw_kt"] >= 10) & (Q2["xw_kt"] < 12))]
    if rl:
        bands.append((f"US revealed limit {rl:.1f} kt plus or minus 1 kt", (Q2["xw_kt"] >= rl - 1) & (Q2["xw_kt"] < rl + 1)))
    bands += [("0.75-1.0 of max demonstrated", (Q2["frac"] >= 0.75) & (Q2["frac"] < 1.0)), ("above max demonstrated", Q2["frac"] >= 1.0)]
    for name, msk in bands:
        g = Q2[msk]
        if len(g) < 30:
            L.append(f"  {name}: n={len(g)}")
            continue
        L.append(f"  {name}: n={len(g):,}, S_fp median {g['S_fp'].median():.2f}, above 1 {100 * (g['S_fp'] > 1).mean():.1f}%, "
                 f"above 2 {100 * (g['S_fp'] > 2).mean():.1f}%, above 3 {100 * (g['S_fp'] > 3).mean():.1f}%; "
                 f"S_spd above 1 {100 * (g['S_spd'] > 1).mean():.1f}%")
    L.append("")

    L.append("5. Which elements degrade: share above 1 by crosswind band")
    L.append("  " + " " * 26 + "".join(f"{(f'{a}-{b - 1}' if b < 99 else f'{a}+'):>9s}" for a, b in XW))
    for c in FP + SPD:
        cells = []
        for a, b in XW:
            g = Q2[(Q2["xw_kt"] >= a) & (Q2["xw_kt"] < b) & Q2[c].notna()]
            cells.append(f"{100 * (g[c] > 1).mean():8.1f}%" if len(g) >= 30 else "     n<30")
        L.append(f"  {NAMES[c]:26s}" + "".join(cells))
    L.append("")

    L.append("6. Crosswind direction relative to the base leg (pattern approaches with a base leg; positive = wind from the base side)")
    sx = T["xw_from_base_kt"]
    for a, b in ((-20, -10), (-10, -5), (-5, -2), (-2, 2), (2, 5), (5, 10), (10, 20)):
        g = T[(sx >= a) & (sx < b)]
        if len(g) < 30:
            continue
        L.append(f"  {a:+d} to {b:+d} kt: n={len(g):8,}, overshoot above 200 ft {100 * (g['overshoot_ft'] > 200).mean():5.1f}%, "
                 f"lined up below 300 ft or never {100 * ((g['align_hat'] < 300) | g['align_hat'].isna()).mean():5.1f}%")
    TT = T.copy()
    TT["from_base"] = TT["xw_from_base_kt"].clip(lower=0)
    TT["from_far"] = (-TT["xw_from_base_kt"]).clip(lower=0)
    for yname, ylab in (("over200", "overshoot above 200 ft"), ("late", "lined up below 300 ft or never")):
        TT[yname] = ((TT["overshoot_ft"] > 200) if yname == "over200" else ((TT["align_hat"] < 300) | TT["align_hat"].isna())).astype(float)
        X = TT[["from_base", "from_far", "hw_kt", "gust_spread", yname, "aptrwy", "icao"]].dropna()
        Z = demean(X, ["from_base", "from_far", "hw_kt", "gust_spread", yname], "aptrwy")
        Xm, y = Z[["from_base", "from_far", "hw_kt", "gust_spread"]].values, Z[yname].values
        bread = np.linalg.pinv(Xm.T @ Xm)
        beta = bread @ Xm.T @ y
        e = y - Xm @ beta
        codes, inv = np.unique(X["icao"].values, return_inverse=True)
        Sg = np.zeros((len(codes), 4))
        np.add.at(Sg, inv, Xm * e[:, None])
        Vv = bread @ (Sg.T @ Sg) @ bread * len(codes) / max(len(codes) - 1, 1)
        se = np.sqrt(np.diag(Vv))
        L.append(f"  {ylab}: per 5 kt from the base side {500 * beta[0]:+.2f} points ({500 * (beta[0] - 1.96 * se[0]):+.2f} to {500 * (beta[0] + 1.96 * se[0]):+.2f}), "
                 f"per 5 kt from the far side {500 * beta[1]:+.2f} ({500 * (beta[1] - 1.96 * se[1]):+.2f} to {500 * (beta[1] + 1.96 * se[1]):+.2f}), base share {100 * X[yname].mean():.1f}%")
    L.append("")

    L.append("7. Measurement checks")
    b = Q2[(Q2["height_source"] == "baro") & Q2["hat_true_minus_geom_ft"].notna()].copy()
    b["resid"] = b["hat_true_minus_geom_ft"] - b.groupby(["airport", b["date"].str[:7]])["hat_true_minus_geom_ft"].transform("median")
    for a_, b_ in GUST:
        g = b[(b["gust_spread"] >= a_) & (b["gust_spread"] < b_)]
        L.append(f"  barometric minus GNSS height at the gate, gust {a_:g}-{b_ if b_ < 99 else '+'} kt: median absolute residual {g['resid'].abs().median():.1f} ft (n={len(g):,})")
    L.append(f"  NACp 10 or better at the gate: {100 * (pd.to_numeric(Q2['nacp'], errors='coerce') >= 10).mean():.1f}%, NACp 9 or better {100 * (pd.to_numeric(Q2['nacp'], errors='coerce') >= 9).mean():.1f}%")
    Pm = P[P["xw_low_kt"].notna()].copy()
    Pm["measurable"] = (Pm["status"] == "ok").astype(float)
    for a_, b_ in XW:
        g = Pm[(Pm["xw_low_kt"] >= a_) & (Pm["xw_low_kt"] < b_)]
        if len(g) >= 30:
            L.append(f"  measurable at 300 ft, crosswind {a_}-{b_ if b_ < 99 else '+'} kt: {100 * g['measurable'].mean():.1f}% (n={len(g):,})")
    L.append("")

    L.append("8. Sensitivities: S_fp above 2, change at 10 and 15 kt against calm (points)")
    sens = [("straight-in only", Q2[Q2["straight_in"] == "yes"]), ("25 ft altimeters only", Q2[Q2["height_source"] == "baro"]),
            ("calibrated GNSS heights only", Q2[Q2["height_source"] == "gnss_calibrated"]),
            ("NACp 10 only", Q2[pd.to_numeric(Q2["nacp"], errors="coerce") >= 10]), ("late-turn descriptor out", Q2[Q2["flag_practice"] != 1]),
            ("towered", Q2[Q2["tower"]]), ("non-towered", Q2[~Q2["tower"]])]
    # airports where two distinct runways run within 20 degrees of each other (parallels, near-parallels):
    # Set 4 showed the detector can assign an approach to the neighboring runway there
    sites = ua.load()
    near_par = set()
    for a, site in sites.items():
        crs = []
        for rid, (p1, p2) in site.apt.runways.items():
            c = math.degrees(math.atan2(p2[0] - p1[0], p2[1] - p1[1])) % 180
            crs.append(c)
        if any(min(abs(x - y), 180 - abs(x - y)) < 20 for i, x in enumerate(crs) for y in crs[i + 1:]):
            near_par.add(a)
    sens.append(("no parallel or near-parallel runways", Q2[~Q2["airport"].isin(near_par)]))
    for reg in sorted(Q2["region"].unique()):
        sens.append((f"FAA region {reg}", Q2[Q2["region"] == reg]))
    for name, sel in sens:
        if len(sel) < 2000:
            L.append(f"  {name}: n={len(sel)} (too few)")
            continue
        sel = sel.copy()
        sel["_y"] = (sel["S_fp"] > 2).astype(float)
        ctr = tuple(c for c in ("typeg", "own", "season", "straight_in", "height_source")
                    if not (c == "straight_in" and name == "straight-in only") and not (c == "height_source" and "only" in name and "altimeter" in name or "GNSS" in name))
        beta, V, pos, n = lpm(sel, "_y", name, "aptrwy", ctr)
        r10 = lin_combo(beta, V, pos, {"xw": 10, "xw>5": 5})
        r15 = lin_combo(beta, V, pos, {"xw": 15, "xw>5": 10, "xw>10": 5})
        L.append(f"  {name:28s} n={n:9,}, base {100 * sel['_y'].mean():5.1f}%: 10 kt {100 * r10[0]:+.1f} ({100 * r10[1]:+.1f} to {100 * r10[2]:+.1f}), "
                 f"15 kt {100 * r15[0]:+.1f} ({100 * r15[1]:+.1f} to {100 * r15[2]:+.1f})")
    reg_s = Q2[Q2["s"].notna()].copy()
    reg_s["_y"] = (reg_s["s"] > 2).astype(float)
    beta, V, pos, n = lpm(reg_s, "_y", "registered", "aptrwy")
    r15 = lin_combo(beta, V, pos, {"xw": 15, "xw>5": 10, "xw>10": 5})
    L.append(f"  registered New England score (s) above 2: base {100 * reg_s['_y'].mean():.1f}%, 15 kt {100 * r15[0]:+.1f} ({100 * r15[1]:+.1f} to {100 * r15[2]:+.1f})")

    text = "\n".join(L)
    open(os.path.join(OUT, "summary.txt"), "w").write(text + "\n")
    pd.DataFrame(BANDS_ROWS).to_csv(os.path.join(OUT, "bands.csv"), index=False)
    print(text)


if __name__ == "__main__":
    main()
