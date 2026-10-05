#!/usr/bin/env python3
"""
q2_checks.py

Review checks on the US approach results (logged in notes/decisions.md, 2026-10-05). Post-hoc diagnostics and
sensitivities from the frozen primary approaches file (v3.1, no inferred approaches, calibrated airspeed),
read once by load_slim.py. Nothing in the frozen outputs changes.

    python3 review_2026-10-05/q2_checks.py review_2026-10-05/us_cas.pkl review_2026-10-05/us_exp0.pkl
"""

import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import us_q2  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "q2_checks.txt")
DEV = {"BDR", "HVN", "BED", "LWM", "OWD", "PYM", "TAN"}
XW = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 99)]
CONTROLS = ("typeg", "own", "season", "straight_in", "height_source")
L = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def band_name(a, b):
    return f"{a}+" if b >= 99 else f"{a}-{b - 1}"


# ------------------------------------------------------------------ models with several clusterings

def design(d, yname, absorb="aptrwy", controls=CONTROLS, spline=True, extra=None):
    """Demeaned design for the registered linear models (as us_q2.lpm)."""
    X = pd.DataFrame(index=d.index)
    if extra is None:
        X["xw"] = d["xw_kt"]
        if spline:
            for k in (5, 10, 15):
                X[f"xw>{k}"] = (d["xw_kt"] - k).clip(lower=0)
        X["hw"] = d["hw_kt"]
        X["gust"] = d["gust_spread"]
    else:
        for c in extra:
            X[c] = d[c]
    for c in controls:
        X = pd.concat([X, pd.get_dummies(d[c].astype(str), prefix=c, drop_first=True, dtype=float)], axis=1)
    X["_y"] = d[yname].values
    g = d[absorb].astype(str).values
    Z = X - X.groupby(g).transform("mean")
    keep = [c for c in Z.columns if c != "_y" and Z[c].abs().sum() > 0]
    return Z[keep].values, Z["_y"].values, keep


def fit_multi(d, yname, clusterings, **kw):
    """OLS on the demeaned design. Returns beta, {name: V}, positions."""
    Xm, y, cols = design(d, yname, **kw)
    bread = np.linalg.pinv(Xm.T @ Xm)
    beta = bread @ (Xm.T @ y)
    e = y - Xm @ beta
    U = Xm * e[:, None]
    Vs = {}
    meats = {}
    for name, key in clusterings.items():
        if isinstance(key, tuple):
            continue
        codes, inv = np.unique(d[key].astype(str).values, return_inverse=True)
        S = np.zeros((len(codes), Xm.shape[1]))
        np.add.at(S, inv, U)
        G = len(codes)
        meats[name] = S.T @ S * G / max(G - 1, 1)
        Vs[name] = bread @ meats[name] @ bread
    for name, key in clusterings.items():
        if isinstance(key, tuple):
            a, b, ab = key
            Vs[name] = Vs[a] + Vs[b] - Vs[ab]
    return beta, Vs, {c: i for i, c in enumerate(cols)}


def combo(beta, V, pos, weights):
    w = np.zeros(len(beta))
    for c, v in weights.items():
        if c in pos:
            w[pos[c]] = v
    est = float(w @ beta)
    se = math.sqrt(max(float(w @ V @ w), 0.0))
    return est, est - 1.96 * se, est + 1.96 * se


def at(x):
    w = {"xw": x}
    for k in (5, 10, 15):
        if x > k:
            w[f"xw>{k}"] = x - k
    return w


def shares_ci(d, col, thr):
    """Share above thr with the wider of the aircraft and day cluster bootstrap (as us_q2.shares)."""
    d = d[d[col].notna()]
    if len(d) < 30:
        return float("nan"), float("nan"), float("nan"), len(d)
    e, lo, hi = us_q2.shares(d, col, thr)
    return e, lo, hi, len(d)


def main(pkl, pkl0):
    df = pd.read_pickle(pkl)
    say(f"Loaded {len(df):,} approaches (all airports in the extract, before inclusion) from {pkl}")
    inc = df[df["day_ok"]]
    P = inc[(inc["group"] == "piston") & (inc["vmc"] == 1)]
    Q2 = P[P["status"] == "ok"].copy()
    J = inc[(inc["group"] == "jet") & (inc["vmc"] == 1) & (inc["status"] == "ok") & (inc["straight_in"] == "yes")].copy()
    say(f"Included days: {len(inc):,}. Piston VMC {len(P):,}. Measurable piston (Q2) {len(Q2):,} at {Q2['airport'].nunique()} airports. "
        f"Jets straight-in measurable {len(J):,} at {J['airport'].nunique()} airports.")
    say()

    part2 = os.environ.get("PART2") == "1"   # sections 18, 1, 42, 44, 38 already in q2_checks_part1.txt
    w = P[P["xw_low_kt"].notna()]
    Qm = Q2[Q2["xw_kt"].notna() & Q2["hw_kt"].notna() & Q2["gust_spread"].notna()].copy()
    if part2:
        main_part2(Q2, Qm, P, J, w, pkl0)
        open(OUT.replace(".txt", "_part2.txt"), "w").write("\n".join(L) + "\n")
        return
    # ---------------------------------------------------------- 18. count ladder
    say("18. COUNT LADDER (US confirmatory, detector v3.1)")
    say(f"  All detected approaches in the extract (755 airports with traffic): {len(df):,}")
    say(f"  At admitted airports on included days: {len(inc):,} at {inc['airport'].nunique()} airports")
    for g in ("piston", "jet", "turboprop", "other"):
        n = int((inc["group"] == g).sum())
        if n:
            say(f"    group {g}: {n:,}")
    pist = inc[inc["group"] == "piston"]
    say(f"  Piston: {len(pist):,}. In VMC: {len(P):,} ({100 * len(P) / len(pist):.1f}%)")
    basis = P["poh_xwind_basis"].astype(str).value_counts(dropna=False)
    say("  Piston VMC by POH crosswind basis: " + ", ".join(f"{k} {v:,} ({100 * v / len(P):.1f}%)" for k, v in basis.items()))
    typed = P["poh_xwind_basis"].astype(str).isin(["published", "assumed"])
    say(f"  Share of piston VMC approaches flown by the 20 POH types (published or assumed value): {100 * typed.mean():.1f}%")
    say(f"  Same share among measurable piston approaches: {100 * Q2['poh_xwind_basis'].astype(str).isin(['published', 'assumed']).mean():.1f}%")
    w = P[P["xw_low_kt"].notna()]
    say(f"  Piston VMC with wind at the lowest observed point: {len(w):,}")
    for lab, sel in (("published value (Q1b primary)", w[w["poh_xwind_basis"] == "published"]),
                     ("published or assumed value", w[w["poh_xwind_basis"].astype(str).isin(["published", "assumed"])])):
        ex = sel["xw_low_kt"] > sel["poh_xwind_kt"]
        exg = sel["gust_xw_low_kt"].fillna(sel["xw_low_kt"]) > sel["poh_xwind_kt"]
        say(f"    {lab}: {len(sel):,} approaches, sustained above max demonstrated {int(ex.sum()):,} ({100 * ex.mean():.3f}%), "
            f"gust above {int(exg.sum()):,} ({100 * exg.mean():.2f}%). Inferred passes among them {int(sel['is_inferred'].sum()):,}")
    pub = w[w["poh_xwind_basis"] == "published"]
    obs = pub[~pub["is_inferred"]]
    say(f"    published, observed passes only: {len(obs):,}, sustained above {int((obs['xw_low_kt'] > obs['poh_xwind_kt']).sum()):,} "
        f"({100 * (obs['xw_low_kt'] > obs['poh_xwind_kt']).mean():.3f}%)")
    say(f"  Measurable at 300 ft (inferred passes excluded): {len(Q2):,}. With gate crosswind: {int(Q2['xw_kt'].notna().sum()):,}")
    for lab, sel in (("published", Q2[Q2["poh_xwind_basis"] == "published"]),
                     ("published or assumed", Q2[Q2["poh_xwind_basis"].astype(str).isin(["published", "assumed"])])):
        sel = sel[sel["xw_kt"].notna()]
        say(f"    measurable with a {lab} value: {len(sel):,}; gate crosswind at or above max demonstrated {int((sel['frac'] >= 1).sum()):,} "
            f"({100 * (sel['frac'] >= 1).mean():.3f}%); 0.75 to 1.0 {int(((sel['frac'] >= 0.75) & (sel['frac'] < 1)).sum()):,}")
    both = Q2[(Q2["poh_xwind_basis"] == "published") & Q2["xw_low_kt"].notna() & Q2["xw_kt"].notna()]
    say(f"    measurable, published: above max demonstrated at the lowest point {int((both['xw_low_kt'] > both['poh_xwind_kt']).sum()):,}, "
        f"at the 300 ft gate {int((both['xw_kt'] >= both['poh_xwind_kt']).sum()):,}")
    say("  Measurable piston approaches by gate crosswind band: " + ", ".join(
        f"{band_name(a, b)} kt {int(((Q2['xw_kt'] >= a) & (Q2['xw_kt'] < b)).sum()):,} ({100 * ((Q2['xw_kt'] >= a) & (Q2['xw_kt'] < b)).mean():.2f}%)" for a, b in XW))
    say()

    # ---------------------------------------------------------- 1. speed consistency and speed excess
    say("1. SPEED BY CROSSWIND BAND (piston, measurable). Consistency = g_c5b_detr above 1 (range of calibrated airspeed about its")
    say("   straight-line trend over the 30 s before 300 ft, over 10 kt). Excess = calibrated airspeed at 300 ft minus (POH approach speed + half the gust spread).")
    Q2["dv"] = Q2["gate_est_as"] - (Q2["poh_approach_kias"] + 0.5 * Q2["gust_spread"].fillna(0))
    J["cons"] = J["g_c5b_detr"]
    for a, b in XW:
        g = Q2[(Q2["xw_kt"] >= a) & (Q2["xw_kt"] < b)]
        c = shares_ci(g, "g_c5b_detr", 1)
        v = g["dv"].dropna()
        cj = J[(J["xw_kt"] >= a) & (J["xw_kt"] < b)]["g_c5b_detr"].dropna()
        val = shares_ci(g.assign(_v=g[["g_c5a", "b_c5a"]].max(axis=1, skipna=True).where(g[["g_c5a", "b_c5a"]].notna().any(axis=1))), "_v", 1)
        say(f"  {band_name(a, b):>5s} kt: consistency above 1 {100 * c[0]:.1f}% ({100 * c[1]:.1f} to {100 * c[2]:.1f}, n={c[3]:,}); "
            f"value check above 1 {100 * val[0]:.1f}%; median excess {v.median():+.1f} kt (IQR {v.quantile(.25):+.1f} to {v.quantile(.75):+.1f}, n={len(v):,}); "
            f"more than 10 kt fast {100 * (v > 10).mean():.1f}%, more than 5 kt slow {100 * (v < -5).mean():.1f}%; "
            f"median airspeed range about trend {10 * g['g_c5b_detr'].median():.1f} kt; jets consistency above 1 {100 * (cj > 1).mean():.1f}% (n={len(cj):,})")
    say()

    # ---------------------------------------------------------- 42. calm cutoff and denominators
    say("42. CALM-WIND SPEED SHARE: cutoff and denominator")
    for cut in (4, 5):
        g = Q2[Q2["xw_kt"] < cut]
        say(f"  crosswind below {cut} kt: S_spd above 1 = {100 * (g['S_spd'] > 1).sum() / g['S_spd'].notna().sum():.1f}% of the {int(g['S_spd'].notna().sum()):,} with a speed score; "
            f"{100 * (g['S_spd'] > 1).mean():.1f}% of all {len(g):,} measurable (no speed score counted as not above 1). "
            f"S_fp above 1 / 2 / 3: {100 * (g['S_fp'] > 1).mean():.1f} / {100 * (g['S_fp'] > 2).mean():.1f} / {100 * (g['S_fp'] > 3).mean():.1f}%")
    say(f"  Measurable approaches without a speed score: {int(Q2['S_spd'].isna().sum()):,} ({100 * Q2['S_spd'].isna().mean():.2f}%), "
        f"of which without a POH approach speed {int((Q2['S_spd'].isna() & Q2['poh_approach_kias'].isna()).sum()):,}")
    say()

    # ---------------------------------------------------------- 44. Table 4 with intervals
    say("44. PERFORMANCE AT FOUR POINTS (Table 4), share above each threshold, 95% interval = wider of aircraft and day cluster bootstrap (500 each).")
    say("    S_spd uses approaches with a speed score as the denominator.")
    rl = 11.6
    rows = [("Calm, crosswind below 5 kt", Q2["xw_kt"] < 5), (f"Revealed limit, {rl} kt plus or minus 1 kt", (Q2["xw_kt"] >= rl - 1) & (Q2["xw_kt"] < rl + 1)),
            ("0.75 to 1.0 of maximum demonstrated", (Q2["frac"] >= 0.75) & (Q2["frac"] < 1.0)), ("Above maximum demonstrated", Q2["frac"] >= 1.0)]
    for name, m in rows:
        g = Q2[m]
        cells = []
        for col, thr in (("S_fp", 1), ("S_fp", 2), ("S_fp", 3), ("S_spd", 1)):
            e, lo, hi, n = shares_ci(g, col, thr)
            cells.append(f"{col}>{thr} {100 * e:.1f} ({100 * lo:.1f} to {100 * hi:.1f})")
        bas = g["poh_xwind_basis"].astype(str).value_counts()
        say(f"  {name}: n={len(g):,} [{', '.join(f'{k} {v:,}' for k, v in bas.items())}] | " + " | ".join(cells))
    say()

    # ---------------------------------------------------------- 38. clustering
    say("38. CLUSTERING. Registered models (linear probability and log score, airport-runway absorbed, controls as registered).")
    say("    Same point estimates, standard errors clustered by aircraft (as registered), airport-day, both (two-way), and airport.")
    for frame in (Q2, J):
        frame["acday"] = frame["icao"].astype(str) + "|" + frame["dayk"].astype(str)
    CL = {"aircraft": "icao", "airport-day": "dayk", "acday": "acday", "airport": "airport", "two-way": ("aircraft", "airport-day", "acday")}
    order = ("aircraft", "airport-day", "two-way", "airport")
    Qm = Q2[Q2["xw_kt"].notna() & Q2["hw_kt"].notna() & Q2["gust_spread"].notna()].copy()
    for value, thr in (("S_fp", 1), ("S_fp", 2), ("S_fp", 3), ("S_spd", 1), ("S_spd", 2)):
        d = Qm[Qm[value].notna()].copy()
        d["_y"] = (d[value] > thr).astype(float)
        beta, Vs, pos = fit_multi(d, "_y", CL)
        for x in (10, 15):
            parts = []
            for nm in order:
                e, lo, hi = combo(beta, Vs[nm], pos, at(x))
                parts.append(f"{nm} {100 * lo:+.1f} to {100 * hi:+.1f}")
            say(f"  {value} above {thr}, change at {x} kt: {100 * e:+.1f} points | " + " | ".join(parts))
        for nm_w, wt in (("per 5 kt headwind", {"hw": 5}), ("per 5 kt gust spread", {"gust": 5})):
            e = combo(beta, Vs["aircraft"], pos, wt)[0]
            say(f"    {nm_w}: {100 * e:+.1f} | " + " | ".join(f"{nm} {100 * combo(beta, Vs[nm], pos, wt)[1]:+.1f} to {100 * combo(beta, Vs[nm], pos, wt)[2]:+.1f}" for nm in order))
    T = Qm[Qm["S_turn"].notna()].copy()
    T["_y"] = (T["S_turn"] > 1).astype(float)
    beta, Vs, pos = fit_multi(T, "_y", CL)
    for x in (10, 15):
        e = combo(beta, Vs["aircraft"], pos, at(x))[0]
        say(f"  S_turn above 1, change at {x} kt: {100 * e:+.1f} | " + " | ".join(f"{nm} {100 * combo(beta, Vs[nm], pos, at(x))[1]:+.1f} to {100 * combo(beta, Vs[nm], pos, at(x))[2]:+.1f}" for nm in order))
    for label, frame, value, ctr in (("Piston log S_fp", Qm, "S_fp", CONTROLS), ("Piston log S_spd", Qm, "S_spd", CONTROLS),
                                     ("Jets log S_fp", J[J["xw_kt"].notna() & J["hw_kt"].notna() & J["gust_spread"].notna()], "S_fp", ("season",))):
        d = frame[frame[value] > 0].copy()
        d["_ly"] = np.log(d[value])
        beta, Vs, pos = fit_multi(d, "_ly", CL, controls=ctr, spline=False)
        e = combo(beta, Vs["aircraft"], pos, {"xw": 5})[0]
        say(f"  {label} per 5 kt crosswind: {100 * (math.exp(e) - 1):+.1f}% | " + " | ".join(
            f"{nm} {100 * (math.exp(combo(beta, Vs[nm], pos, {'xw': 5})[1]) - 1):+.1f} to {100 * (math.exp(combo(beta, Vs[nm], pos, {'xw': 5})[2]) - 1):+.1f}" for nm in order))
    # direction models (as us_q2.py: from-base and from-far slopes, headwind, gust spread, airport-runway absorbed)
    TT = Q2[(Q2["straight_in"] == "no") & Q2["base_side"].notna()].copy()
    TT["from_base"] = TT["xw_from_base_kt"].clip(lower=0)
    TT["from_far"] = (-TT["xw_from_base_kt"]).clip(lower=0)
    TT["over200"] = (TT["overshoot_ft"] > 200).astype(float)
    TT["late"] = ((TT["align_hat"] < 300) | TT["align_hat"].isna()).astype(float)
    TT = TT[TT[["from_base", "from_far", "hw_kt", "gust_spread"]].notna().all(axis=1)]
    for yname, lab, k in (("over200", "overshoot above 200 ft, per 5 kt tailwind on base", "from_base"),
                          ("late", "not aligned by 300 ft, per 5 kt headwind on base", "from_far")):
        beta, Vs, pos = fit_multi(TT, yname, CL, controls=(), extra=["from_base", "from_far", "hw_kt", "gust_spread"])
        e = combo(beta, Vs["aircraft"], pos, {k: 5})[0]
        say(f"  {lab}: {100 * e:+.2f} points | " + " | ".join(f"{nm} {100 * combo(beta, Vs[nm], pos, {k: 5})[1]:+.2f} to {100 * combo(beta, Vs[nm], pos, {k: 5})[2]:+.2f}" for nm in order))
    say(f"  Clusters: aircraft {Qm['icao'].nunique():,}, airport-days {Qm['dayk'].nunique():,}, airports {Qm['airport'].nunique()}")
    say()

    # ---------------------------------------------------------- 13. development airports out
    say("13. DEVELOPMENT AIRPORTS OUT (US Q1b and Q2 headline without BDR, HVN, BED, LWM, OWD, PYM, TAN)")
    say(f"  Development airports in the measurable sample: {sorted(set(Q2['airport'].astype(str)) & DEV)}, "
        f"{int(Q2['airport'].isin(DEV).sum()):,} measurable piston approaches")
    Qx = Q2[~Q2["airport"].isin(DEV)]
    Bx = w[(w["poh_xwind_basis"] == "published") & ~w["airport"].isin(DEV)]
    say(f"  Q1b sustained above max demonstrated: {100 * (Bx['xw_low_kt'] > Bx['poh_xwind_kt']).mean():.3f}% of {len(Bx):,}")
    for value, thr in (("S_fp", 1), ("S_fp", 2), ("S_spd", 1)):
        d = Qx[Qx[value].notna() & Qx["xw_kt"].notna() & Qx["hw_kt"].notna() & Qx["gust_spread"].notna()].copy()
        d["_y"] = (d[value] > thr).astype(float)
        beta, V, pos, n = us_q2.lpm(d, "_y", "x")
        r10, r15 = us_q2.lin_combo(beta, V, pos, at(10)), us_q2.lin_combo(beta, V, pos, at(15))
        say(f"  {value} above {thr}: 10 kt {100 * r10[0]:+.1f} ({100 * r10[1]:+.1f} to {100 * r10[2]:+.1f}), 15 kt {100 * r15[0]:+.1f} ({100 * r15[1]:+.1f} to {100 * r15[2]:+.1f})")
    say()

    # ---------------------------------------------------------- 43. headwind on the speed score, no-growth profile
    say("43. HEADWIND EFFECT ON THE SPEED SCORE BY WIND PROFILE (per 5 kt headwind, crosswind and gust spread held, registered model)")
    for lab, path in (("1/7 (primary)", None), ("0, no growth with height", pkl0)):
        if path is None:
            D = Qm
        else:
            d0 = pd.read_pickle(path)
            d0 = d0[d0["day_ok"] & (d0["group"] == "piston") & (d0["vmc"] == 1) & (d0["status"] == "ok")]
            D = d0[d0["xw_kt"].notna() & d0["hw_kt"].notna() & d0["gust_spread"].notna()].copy()
        for thr in (1, 2):
            d = D[D["S_spd"].notna()].copy()
            d["_y"] = (d["S_spd"] > thr).astype(float)
            beta, V, pos, n = us_q2.lpm(d, "_y", "x")
            h = us_q2.lin_combo(beta, V, pos, {"hw": 5})
            r15 = us_q2.lin_combo(beta, V, pos, at(15))
            say(f"  exponent {lab}, S_spd above {thr}: per 5 kt headwind {100 * h[0]:+.1f} ({100 * h[1]:+.1f} to {100 * h[2]:+.1f}); crosswind 15 kt {100 * r15[0]:+.1f}")
        hb = []
        for a, b in ((-99, 0), (0, 5), (5, 10), (10, 15), (15, 99)):
            g = D[(D["hw_kt"] >= a) & (D["hw_kt"] < b) & D["S_spd"].notna()]
            dv = g["gate_est_as"] - (g["poh_approach_kias"] + 0.5 * g["gust_spread"].fillna(0))
            hb.append(f"{'tailwind' if a < -90 else f'{a}-{b - 1 if b < 99 else chr(43)}'} {100 * (g['S_spd'] > 1).mean():.1f}% (median excess {dv.median():+.1f} kt)")
        say("    S_spd above 1 by headwind band: " + ", ".join(hb))
    say()

    # ---------------------------------------------------------- 19. jets: autopilot or approach mode at the gate
    say("19. JETS ON STRAIGHT-IN APPROACHES: autopilot or approach mode reported at the gate ('coupled')")
    say("  values: " + ", ".join(f"{k!r} {v:,}" for k, v in J["coupled"].value_counts(dropna=False).items()))
    say()

    # ---------------------------------------------------------- jets by airport
    say("JET COMPARISON GROUP BY AIRPORT (straight-in, measurable, VMC)")
    top = J["airport"].astype(str).value_counts()
    say(f"  {len(J):,} approaches at {J['airport'].nunique()} airports. Top 25: " + ", ".join(f"{a} {n:,}" for a, n in top.head(25).items()))
    say(f"  Share from the top 30 airports: {100 * top.head(30).sum() / len(J):.1f}%")
    say()

    # ---------------------------------------------------------- turn to final by wind side
    say("TURN TO FINAL BY WIND SIDE (pattern approaches with a base leg). Positive = tailwind on base (wind from the base-leg side)")
    TT2 = Q2[(Q2["straight_in"] == "no") & Q2["base_side"].notna()]
    for a, b in ((-20, -10), (-10, -5), (-5, -2), (-2, 2), (2, 5), (5, 10), (10, 20)):
        g = TT2[(TT2["xw_from_base_kt"] >= a) & (TT2["xw_from_base_kt"] < b)]
        say(f"  {a:+d} to {b:+d} kt: n={len(g):,}; S_turn above 1 {100 * (g['S_turn'] > 1).mean():.1f}%, above 2 {100 * (g['S_turn'] > 2).mean():.1f}%, above 3 {100 * (g['S_turn'] > 3).mean():.1f}%; "
            f"overshoot over 200 ft {100 * (g['overshoot_ft'] > 200).mean():.1f}%, over 400 ft {100 * (g['overshoot_ft'] > 400).mean():.1f}%; "
            f"not aligned by 300 ft {100 * ((g['align_hat'] < 300) | g['align_hat'].isna()).mean():.1f}%, not aligned by 150 ft {100 * ((g['align_hat'] < 150) | g['align_hat'].isna()).mean():.1f}%; "
            f"S_fp above 1 {100 * (g['S_fp'] > 1).mean():.1f}%, above 2 {100 * (g['S_fp'] > 2).mean():.1f}%, above 3 {100 * (g['S_fp'] > 3).mean():.1f}%")
    say()

    # ---------------------------------------------------------- readings
    say("READINGS")
    si = Q2[Q2["straight_in"] == "yes"]
    say(f"  Straight-in S_fp above 2: all crosswinds {100 * (si['S_fp'] > 2).mean():.1f}% (n={len(si):,}), calm below 5 kt {100 * (si[si['xw_kt'] < 5]['S_fp'] > 2).mean():.1f}%; "
        f"pattern approaches calm {100 * (Q2[(Q2['straight_in'] == 'no') & (Q2['xw_kt'] < 5)]['S_fp'] > 2).mean():.1f}%")
    tw = Q2[Q2["hw_kt"] < 0]
    say(f"  Tailwind (headwind below 0): S_fp above 1 {100 * (tw['S_fp'] > 1).mean():.1f}%, S_spd above 1 {100 * (tw['S_spd'] > 1).sum() / tw['S_spd'].notna().sum():.1f}%, S_turn above 1 {100 * (tw['S_turn'] > 1).sum() / tw['S_turn'].notna().sum():.1f}%")
    q = Q2["S_fp"].quantile([0.01, 0.05, 0.10, 0.25, 0.5])
    say("  S_fp percentiles (lower is better): " + ", ".join(f"p{int(100 * k)} {v:.2f}" for k, v in q.items())
        + f". Share below 0.5: {100 * (Q2['S_fp'] < 0.5).mean():.1f}%. Median sink value at 300 ft (g_c4_afh): {Q2['g_c4_afh'].median():.2f}")
    say()

    # ---------------------------------------------------------- 31. 500 ft gate
    say("31. SECONDARY 500 FT GATE (position and path checks at 500 ft: centerline, lined up, glide path)")
    Q5 = P[(P["status_500"].astype(str) == "ok") & (P["status"] != "inferred")].copy()
    Q5["fp500"] = Q5[["g500_c1", "g500_c2a", "g500_c3"]].max(axis=1, skipna=True)
    Q2["fp300g"] = Q2[["g_c1", "g_c2a", "g_c3"]].max(axis=1, skipna=True)
    say(f"  measurable at 500 ft: {len(Q5):,}")
    for a, b in XW[:4]:
        g5 = Q5[(Q5["xw_kt"] >= a) & (Q5["xw_kt"] < b)]
        g3 = Q2[(Q2["xw_kt"] >= a) & (Q2["xw_kt"] < b)]
        say(f"  {band_name(a, b):>5s} kt: at 500 ft above 1 {100 * (g5['fp500'] > 1).mean():.1f}%, above 2 {100 * (g5['fp500'] > 2).mean():.1f}% (n={len(g5):,}); "
            f"same checks at 300 ft above 1 {100 * (g3['fp300g'] > 1).mean():.1f}%, above 2 {100 * (g3['fp300g'] > 2).mean():.1f}%")
    d = Q5[Q5["fp500"].notna() & Q5["xw_kt"].notna() & Q5["hw_kt"].notna() & Q5["gust_spread"].notna()].copy()
    for thr in (1, 2):
        d["_y"] = (d["fp500"] > thr).astype(float)
        beta, V, pos, n = us_q2.lpm(d, "_y", "x")
        r10, r15 = us_q2.lin_combo(beta, V, pos, at(10)), us_q2.lin_combo(beta, V, pos, at(15))
        say(f"  500 ft gate checks above {thr}: change at 10 kt {100 * r10[0]:+.1f} ({100 * r10[1]:+.1f} to {100 * r10[2]:+.1f}), "
            f"15 kt {100 * r15[0]:+.1f} ({100 * r15[1]:+.1f} to {100 * r15[2]:+.1f}), base {100 * d['_y'].mean():.1f}%")
    open(OUT, "w").write("\n".join(L) + "\n")


def main_part2(Q2, Qm, P, J, w, pkl0):
    # ---------------------------------------------------------- 13. development airports out
    say("13. DEVELOPMENT AIRPORTS OUT (US Q1b and Q2 headline without BDR, HVN, BED, LWM, OWD, PYM, TAN)")
    say(f"  Development airports in the measurable sample: {sorted(set(Q2['airport'].astype(str)) & DEV)}, "
        f"{int(Q2['airport'].isin(DEV).sum()):,} measurable piston approaches")
    Qx = Q2[~Q2["airport"].isin(DEV)]
    Bx = w[(w["poh_xwind_basis"] == "published") & ~w["airport"].isin(DEV)]
    say(f"  Q1b sustained above max demonstrated: {100 * (Bx['xw_low_kt'] > Bx['poh_xwind_kt']).mean():.3f}% of {len(Bx):,}")
    for value, thr in (("S_fp", 1), ("S_fp", 2), ("S_spd", 1)):
        d = Qx[Qx[value].notna() & Qx["xw_kt"].notna() & Qx["hw_kt"].notna() & Qx["gust_spread"].notna()].copy()
        d["_y"] = (d[value] > thr).astype(float)
        beta, V, pos, n = us_q2.lpm(d, "_y", "x")
        r10, r15 = us_q2.lin_combo(beta, V, pos, at(10)), us_q2.lin_combo(beta, V, pos, at(15))
        say(f"  {value} above {thr}: 10 kt {100 * r10[0]:+.1f} ({100 * r10[1]:+.1f} to {100 * r10[2]:+.1f}), 15 kt {100 * r15[0]:+.1f} ({100 * r15[1]:+.1f} to {100 * r15[2]:+.1f})")
    say()

    # ---------------------------------------------------------- 43. headwind on the speed score, no-growth profile
    say("43. HEADWIND EFFECT ON THE SPEED SCORE BY WIND PROFILE (per 5 kt headwind, crosswind and gust spread held, registered model)")
    for lab, path in (("1/7 (primary)", None), ("0, no growth with height", pkl0)):
        if path is None:
            D = Qm
        else:
            d0 = pd.read_pickle(path)
            d0 = d0[d0["day_ok"] & (d0["group"] == "piston") & (d0["vmc"] == 1) & (d0["status"] == "ok")]
            D = d0[d0["xw_kt"].notna() & d0["hw_kt"].notna() & d0["gust_spread"].notna()].copy()
        for thr in (1, 2):
            d = D[D["S_spd"].notna()].copy()
            d["_y"] = (d["S_spd"] > thr).astype(float)
            beta, V, pos, n = us_q2.lpm(d, "_y", "x")
            h = us_q2.lin_combo(beta, V, pos, {"hw": 5})
            r15 = us_q2.lin_combo(beta, V, pos, at(15))
            say(f"  exponent {lab}, S_spd above {thr}: per 5 kt headwind {100 * h[0]:+.1f} ({100 * h[1]:+.1f} to {100 * h[2]:+.1f}); crosswind 15 kt {100 * r15[0]:+.1f}")
        hb = []
        for a, b in ((-99, 0), (0, 5), (5, 10), (10, 15), (15, 99)):
            g = D[(D["hw_kt"] >= a) & (D["hw_kt"] < b) & D["S_spd"].notna()]
            dv = g["gate_est_as"] - (g["poh_approach_kias"] + 0.5 * g["gust_spread"].fillna(0))
            hb.append(f"{'tailwind' if a < -90 else f'{a}-{b - 1 if b < 99 else chr(43)}'} {100 * (g['S_spd'] > 1).mean():.1f}% (median excess {dv.median():+.1f} kt)")
        say("    S_spd above 1 by headwind band: " + ", ".join(hb))
    say()

    # ---------------------------------------------------------- 19. jets: autopilot or approach mode at the gate
    say("19. JETS ON STRAIGHT-IN APPROACHES: autopilot or approach mode reported at the gate ('coupled')")
    say("  values: " + ", ".join(f"{k!r} {v:,}" for k, v in J["coupled"].value_counts(dropna=False).items()))
    say()

    # ---------------------------------------------------------- jets by airport
    say("JET COMPARISON GROUP BY AIRPORT (straight-in, measurable, VMC)")
    top = J["airport"].astype(str).value_counts()
    say(f"  {len(J):,} approaches at {J['airport'].nunique()} airports. Top 25: " + ", ".join(f"{a} {n:,}" for a, n in top.head(25).items()))
    say(f"  Share from the top 30 airports: {100 * top.head(30).sum() / len(J):.1f}%")
    say()

    # ---------------------------------------------------------- turn to final by wind side
    say("TURN TO FINAL BY WIND SIDE (pattern approaches with a base leg). Positive = tailwind on base (wind from the base-leg side)")
    TT2 = Q2[(Q2["straight_in"] == "no") & Q2["base_side"].notna()]
    for a, b in ((-20, -10), (-10, -5), (-5, -2), (-2, 2), (2, 5), (5, 10), (10, 20)):
        g = TT2[(TT2["xw_from_base_kt"] >= a) & (TT2["xw_from_base_kt"] < b)]
        say(f"  {a:+d} to {b:+d} kt: n={len(g):,}; S_turn above 1 {100 * (g['S_turn'] > 1).mean():.1f}%, above 2 {100 * (g['S_turn'] > 2).mean():.1f}%, above 3 {100 * (g['S_turn'] > 3).mean():.1f}%; "
            f"overshoot over 200 ft {100 * (g['overshoot_ft'] > 200).mean():.1f}%, over 400 ft {100 * (g['overshoot_ft'] > 400).mean():.1f}%; "
            f"not aligned by 300 ft {100 * ((g['align_hat'] < 300) | g['align_hat'].isna()).mean():.1f}%, not aligned by 150 ft {100 * ((g['align_hat'] < 150) | g['align_hat'].isna()).mean():.1f}%; "
            f"S_fp above 1 {100 * (g['S_fp'] > 1).mean():.1f}%, above 2 {100 * (g['S_fp'] > 2).mean():.1f}%, above 3 {100 * (g['S_fp'] > 3).mean():.1f}%")
    say()

    # ---------------------------------------------------------- readings
    say("READINGS")
    si = Q2[Q2["straight_in"] == "yes"]
    say(f"  Straight-in S_fp above 2: all crosswinds {100 * (si['S_fp'] > 2).mean():.1f}% (n={len(si):,}), calm below 5 kt {100 * (si[si['xw_kt'] < 5]['S_fp'] > 2).mean():.1f}%; "
        f"pattern approaches calm {100 * (Q2[(Q2['straight_in'] == 'no') & (Q2['xw_kt'] < 5)]['S_fp'] > 2).mean():.1f}%")
    tw = Q2[Q2["hw_kt"] < 0]
    say(f"  Tailwind (headwind below 0): S_fp above 1 {100 * (tw['S_fp'] > 1).mean():.1f}%, S_spd above 1 {100 * (tw['S_spd'] > 1).sum() / tw['S_spd'].notna().sum():.1f}%, S_turn above 1 {100 * (tw['S_turn'] > 1).sum() / tw['S_turn'].notna().sum():.1f}%")
    q = Q2["S_fp"].quantile([0.01, 0.05, 0.10, 0.25, 0.5])
    say("  S_fp percentiles (lower is better): " + ", ".join(f"p{int(100 * k)} {v:.2f}" for k, v in q.items())
        + f". Share below 0.5: {100 * (Q2['S_fp'] < 0.5).mean():.1f}%. Median sink value at 300 ft (g_c4_afh): {Q2['g_c4_afh'].median():.2f}")
    say()

    # ---------------------------------------------------------- 31. 500 ft gate
    say("31. SECONDARY 500 FT GATE (position and path checks at 500 ft: centerline, lined up, glide path)")
    Q5 = P[(P["status_500"].astype(str) == "ok") & (P["status"] != "inferred")].copy()
    Q5["fp500"] = Q5[["g500_c1", "g500_c2a", "g500_c3"]].max(axis=1, skipna=True)
    Q2["fp300g"] = Q2[["g_c1", "g_c2a", "g_c3"]].max(axis=1, skipna=True)
    say(f"  measurable at 500 ft: {len(Q5):,}")
    for a, b in XW[:4]:
        g5 = Q5[(Q5["xw_kt"] >= a) & (Q5["xw_kt"] < b)]
        g3 = Q2[(Q2["xw_kt"] >= a) & (Q2["xw_kt"] < b)]
        say(f"  {band_name(a, b):>5s} kt: at 500 ft above 1 {100 * (g5['fp500'] > 1).mean():.1f}%, above 2 {100 * (g5['fp500'] > 2).mean():.1f}% (n={len(g5):,}); "
            f"same checks at 300 ft above 1 {100 * (g3['fp300g'] > 1).mean():.1f}%, above 2 {100 * (g3['fp300g'] > 2).mean():.1f}%")
    d = Q5[Q5["fp500"].notna() & Q5["xw_kt"].notna() & Q5["hw_kt"].notna() & Q5["gust_spread"].notna()].copy()
    for thr in (1, 2):
        d["_y"] = (d["fp500"] > thr).astype(float)
        beta, V, pos, n = us_q2.lpm(d, "_y", "x")
        r10, r15 = us_q2.lin_combo(beta, V, pos, at(10)), us_q2.lin_combo(beta, V, pos, at(15))
        say(f"  500 ft gate checks above {thr}: change at 10 kt {100 * r10[0]:+.1f} ({100 * r10[1]:+.1f} to {100 * r10[2]:+.1f}), "
            f"15 kt {100 * r15[0]:+.1f} ({100 * r15[1]:+.1f} to {100 * r15[2]:+.1f}), base {100 * d['_y'].mean():.1f}%")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
