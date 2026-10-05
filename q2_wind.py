#!/usr/bin/env python3
"""
q2_wind.py

Q2: how far approach performance moves out of tolerance as wind increases.
Plan logged in notes/decisions.md ("Q2 wind analysis plan", 2026-10-02) before
this ran. Input: q2/approaches.csv (q2_measures.py, after the review fixes).

    python3 q2_wind.py

Writes q2_wind/summary.txt and q2_wind/bands.csv (every banded statistic with
its interval, for figures).
"""

import csv
import json
import math
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

SEED = 20261002
B_DESC = 500
B_MODEL = 200
XW_BANDS = [(0, 5), (5, 10), (10, 15), (15, 99)]
FRAC_BANDS = [(0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 9)]
GUST_BANDS = [(0, 0.5), (0.5, 5), (5, 10), (10, 99)]
HW_BANDS = [(-99, 0), (0, 5), (5, 10), (10, 15), (15, 99)]
CRIT = ["g_c1", "g_c2a", "g_c3", "g_c4", "g_c5b", "b_c1", "b_c2a", "b_c3", "b_c4"]
CRIT_NAMES = {"g_c1": "centerline at 300 ft", "g_c2a": "lined up at 300 ft", "g_c3": "glide path at 300 ft",
              "g_c4": "sink rate at 300 ft", "g_c5b": "speed stability before 300 ft", "b_c1": "centerline 300-100 ft",
              "b_c2a": "lined up 300-100 ft", "b_c3": "glide path 300-100 ft", "b_c4": "sink rate 300-100 ft"}
KNOTS = (5.0, 10.0, 15.0)
TYPE_GROUPS = {"C172": "C172", "P28A": "P28A", "SR20": "SR20", "SR22": "SR22", "S22T": "SR22", "C182": "C182", "P28R": "P28R"}
OUT = "q2_wind"
BANDS_ROWS = []


def windows():
    w = json.load(open("q1a/windows.json"))
    w.update(json.load(open("q1a/windows_untowered.json")))
    return w


def in_window(r, w):
    s, e = w.get(r["airport"]), w.get(r["airport"] + "_exclude_from")
    return bool(s) and s <= r["date"] <= "2026-09-30" and not (e and r["date"] >= e)


def num(v):
    return float(v) if v not in ("", None) else np.nan


def load():
    w = windows()
    keep = ["airport", "date", "icao", "type", "group", "ownership", "runway", "straight_in", "height_source", "nacp",
            "status", "vmc", "flag_practice", "base_side"]
    nums = ["s", "s_true", "s_below50", "s_c4raw", "xw_kt", "hw_kt", "gust_spread", "poh_xwind_kt", "xw_from_base_kt",
            "overshoot_ft", "align_hat", "never_aligned", "m4_sd_descent", "m4_sd_lat_ft"] + CRIT
    rows = defaultdict(list)
    for r in csv.DictReader(open("q2/approaches.csv")):
        if r["status"] != "ok" or r["vmc"] != "1" or not in_window(r, w) or r["group"] not in ("piston", "jet"):
            continue
        if r.get("inferred"):   # inferred approaches have no observed flight path to score (2026-10-02, Benjamin)
            continue
        for k in keep:
            rows[k].append(r[k])
        for k in nums:
            rows[k].append(num(r[k]))
    D = {k: np.array(v) for k, v in rows.items()}
    D["month"] = np.array([d[5:7] for d in D["date"]])
    D["season"] = np.array([{"12": "DJF", "01": "DJF", "02": "DJF", "03": "MAM", "04": "MAM", "05": "MAM",
                             "06": "JJA", "07": "JJA", "08": "JJA"}.get(m, "SON") for m in D["month"]])
    D["typeg"] = np.array([TYPE_GROUPS.get(t, "other") for t in D["type"]])
    D["own"] = np.array([o if o in ("fleet", "private") else "other" for o in D["ownership"]])
    D["aptrwy"] = np.array([a + r for a, r in zip(D["airport"], D["runway"])])
    D["day"] = np.array([a + d for a, d in zip(D["airport"], D["date"])])
    D["frac"] = D["xw_kt"] / D["poh_xwind_kt"]
    return D


def subset(D, mask):
    return {k: v[mask] for k, v in D.items()}


# ---------------------------------------------------------------- banded statistics

def stats(s):
    if len(s) == 0:
        return [np.nan] * 5
    return [np.median(s), np.percentile(s, 90), np.percentile(s, 99), np.mean(s > 1), np.mean(s > 2)]


def cluster_index(codes):
    order = np.argsort(codes, kind="stable")
    uniq, start = np.unique(codes[order], return_index=True)
    bounds = list(start) + [len(codes)]
    return [order[bounds[i]:bounds[i + 1]] for i in range(len(uniq))]


def banded(D, key, bands, label, value="s", boot=True):
    x, s = D[key], D[value]
    ok = ~np.isnan(x) & ~np.isnan(s)
    x, s = x[ok], s[ok]
    band_of = np.full(len(x), -1)
    for bi, (a, b) in enumerate(bands):
        band_of[(x >= a) & (x < b)] = bi
    est = [stats(s[band_of == bi]) for bi in range(len(bands))]
    ns = [int((band_of == bi).sum()) for bi in range(len(bands))]
    lo = [[np.nan] * 5 for _ in bands]
    hi = [[np.nan] * 5 for _ in bands]
    if boot:
        rng = np.random.default_rng(SEED)
        widths = []
        for ckey in ("icao", "day"):
            groups = cluster_index(D[ckey][ok])
            reps = np.zeros((B_DESC, len(bands), 5))
            for r in range(B_DESC):
                pick = rng.integers(0, len(groups), len(groups))
                idx = np.concatenate([groups[i] for i in pick])
                bb, ss = band_of[idx], s[idx]
                for bi in range(len(bands)):
                    reps[r, bi] = stats(ss[bb == bi]) if (bb == bi).sum() >= 10 else [np.nan] * 5
            widths.append((np.nanpercentile(reps, 2.5, axis=0), np.nanpercentile(reps, 97.5, axis=0)))
        lo = np.minimum(widths[0][0], widths[1][0])
        hi = np.maximum(widths[0][1], widths[1][1])
    lines = [f"{label}: by {key} (kt unless noted). median / p90 / p99 of {value}, share above 1, share above 2, n"]
    for bi, (a, b) in enumerate(bands):
        name = f"{a:g}+" if b >= 9 and key == "frac" or b >= 99 else (f"<{b:g}" if a <= -99 else f"{a:g}-{b:g}")
        e = est[bi]
        if ns[bi] < 20:
            lines.append(f"  {name:>9s}: n={ns[bi]} (too few)")
            continue
        if boot:
            lines.append(f"  {name:>9s}: {e[0]:.2f} ({lo[bi][0]:.2f}-{hi[bi][0]:.2f}) / {e[1]:.2f} ({lo[bi][1]:.2f}-{hi[bi][1]:.2f}) / "
                         f"{e[2]:.2f} / {100 * e[3]:.1f}% ({100 * lo[bi][3]:.1f}-{100 * hi[bi][3]:.1f}) / "
                         f"{100 * e[4]:.1f}% ({100 * lo[bi][4]:.1f}-{100 * hi[bi][4]:.1f}) / {ns[bi]:,}")
        else:
            lines.append(f"  {name:>9s}: {e[0]:.2f} / {e[1]:.2f} / {e[2]:.2f} / {100 * e[3]:.1f}% / {100 * e[4]:.1f}% / {ns[bi]:,}")
        BANDS_ROWS.append({"table": label, "key": key, "value": value, "band": name, "n": ns[bi],
                           "median": e[0], "p90": e[1], "p99": e[2], "share_gt1": e[3], "share_gt2": e[4],
                           "median_lo": lo[bi][0], "median_hi": hi[bi][0], "share_gt2_lo": lo[bi][4], "share_gt2_hi": hi[bi][4]})
    return lines


# ---------------------------------------------------------------- models

def spline(x):
    return np.column_stack([x] + [np.maximum(0, x - k) for k in KNOTS])


def design(D, xw=None, controls=("aptrwy", "typeg", "own", "season", "straight_in", "height_source"), linear=False, levels=None):
    xw = D["xw_kt"] if xw is None else xw
    cols = [np.ones(len(xw))]
    names = ["const"]
    if linear:
        cols.append(xw)
        names.append("xw")
    else:
        sp = spline(xw)
        cols += [sp[:, j] for j in range(sp.shape[1])]
        names += ["xw", "xw>5", "xw>10", "xw>15"]
    cols += [D["hw_kt"], D["gust_spread"]]
    names += ["hw", "gust"]
    levels = levels or {}
    for c in controls:
        lv = levels.get(c) or sorted(set(D[c]))[1:]
        levels[c] = lv
        for v in lv:
            cols.append((D[c] == v).astype(float))
            names.append(f"{c}={v}")
    return np.column_stack(cols), names, levels


def logit_fit(X, y, iters=40):
    beta = np.zeros(X.shape[1])
    p0 = min(max(y.mean(), 1e-4), 1 - 1e-4)
    beta[0] = math.log(p0 / (1 - p0))
    for _ in range(iters):
        eta = np.clip(X @ beta, -30, 30)
        p = 1 / (1 + np.exp(-eta))
        W = np.maximum(p * (1 - p), 1e-9)
        z = eta + (y - p) / W
        XtWX = X.T @ (X * W[:, None]) + 1e-8 * np.eye(X.shape[1])
        new = np.linalg.solve(XtWX, X.T @ (W * z))
        if np.max(np.abs(new - beta)) < 1e-7:
            beta = new
            break
        beta = new
    return beta


def cluster_cov(X, resid_score, bread, clusters):
    uniq, inv = np.unique(clusters, return_inverse=True)
    S = np.zeros((len(uniq), X.shape[1]))
    np.add.at(S, inv, resid_score)
    G = len(uniq)
    return bread @ (S.T @ S) @ bread * G / max(G - 1, 1)


def logit_with_se(X, y, clusters):
    b = logit_fit(X, y)
    p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
    bread = np.linalg.pinv(X.T @ (X * (p * (1 - p))[:, None]))
    V = cluster_cov(X, X * (y - p)[:, None], bread, clusters)
    return b, np.sqrt(np.diag(V))


def ols_with_se(X, y, clusters):
    bread = np.linalg.pinv(X.T @ X)
    b = bread @ X.T @ y
    V = cluster_cov(X, X * (y - X @ b)[:, None], bread, clusters)
    return b, np.sqrt(np.diag(V))


def avg_pred(b, D, levels, controls, xw_value):
    X, _, _ = design(D, xw=np.full(len(D["xw_kt"]), float(xw_value)), controls=controls, levels=dict(levels))
    return float(np.mean(1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))))


def _boot_one(args):
    seed, Xy_path, xs = args
    data = np.load(Xy_path, allow_pickle=True)
    X, y, groups_flat, offsets = data["X"], data["y"], data["groups"], data["offsets"]
    Xp = data["Xp"]  # stacked prediction designs, one block per xw value
    rng = np.random.default_rng(seed)
    G = len(offsets) - 1
    pick = rng.integers(0, G, G)
    idx = np.concatenate([groups_flat[offsets[i]:offsets[i + 1]] for i in pick])
    b = logit_fit(X[idx], y[idx])
    n = X.shape[0]
    return [float(np.mean(1 / (1 + np.exp(-np.clip(Xp[k * n:(k + 1) * n] @ b, -30, 30))))) for k in range(len(xs))]


def model_block(D, threshold, label, xs=(0, 5, 10, 15, 20), controls=("aptrwy", "typeg", "own", "season", "straight_in", "height_source"),
                boot=True, pool=None):
    ok = ~np.isnan(D["s"]) & ~np.isnan(D["xw_kt"]) & ~np.isnan(D["hw_kt"]) & ~np.isnan(D["gust_spread"])
    Dm = subset(D, ok)
    X, names, levels = design(Dm, controls=controls)
    y = (Dm["s"] > threshold).astype(float)
    b, se = logit_with_se(X, y, Dm["icao"])
    nmax = int((Dm["xw_kt"] >= 15).sum())
    xs = [x for x in xs if x <= 15 or nmax >= 200]
    preds = [avg_pred(b, Dm, levels, controls, x) for x in xs]
    lines = [f"{label}: logistic model of S above {threshold:g} (n={len(y):,}, base share {100 * y.mean():.1f}%)"]
    ci = None
    if boot and pool is not None:
        tmp = os.path.join(OUT, f"_boot_{abs(hash(label)) % 10**8}.npz")
        groups = cluster_index(Dm["icao"])
        offsets = np.cumsum([0] + [len(g) for g in groups])
        Xp = np.vstack([design(Dm, xw=np.full(len(y), float(x)), controls=controls, levels=dict(levels))[0] for x in xs])
        np.savez(tmp, X=X, y=y, groups=np.concatenate(groups), offsets=offsets, Xp=Xp)
        reps = np.array(list(pool.map(_boot_one, [(SEED + i, tmp, xs) for i in range(B_MODEL)])))
        os.remove(tmp)
        ci = np.percentile(reps, [2.5, 97.5], axis=0)
    cells = []
    for k, x in enumerate(xs):
        c = f" ({100 * ci[0][k]:.1f}-{100 * ci[1][k]:.1f})" if ci is not None else ""
        cells.append(f"{x:g} kt {100 * preds[k]:.1f}%{c}")
    lines.append("  predicted share at crosswind (other conditions as observed, aircraft-cluster bootstrap 95%): " + ", ".join(cells))
    lines.append("  headwind odds ratio per 5 kt {:.3f} (95% CI {:.3f}-{:.3f}); gust spread odds ratio per 5 kt {:.3f} ({:.3f}-{:.3f})".format(
        math.exp(5 * b[5]), math.exp(5 * (b[5] - 1.96 * se[5])), math.exp(5 * (b[5] + 1.96 * se[5])),
        math.exp(5 * b[6]), math.exp(5 * (b[6] - 1.96 * se[6])), math.exp(5 * (b[6] + 1.96 * se[6]))))
    return lines, preds, xs


def logS_block(D, label, controls=("aptrwy", "typeg", "own", "season", "straight_in", "height_source")):
    ok = ~np.isnan(D["s"]) & (D["s"] > 0) & ~np.isnan(D["xw_kt"]) & ~np.isnan(D["hw_kt"]) & ~np.isnan(D["gust_spread"])
    Dm = subset(D, ok)
    X, names, levels = design(Dm, controls=controls, linear=True)
    b, se = ols_with_se(X, np.log(Dm["s"]), Dm["icao"])
    f = lambda k: f"{100 * (math.exp(5 * b[k]) - 1):+.1f}% ({100 * (math.exp(5 * (b[k] - 1.96 * se[k])) - 1):+.1f} to {100 * (math.exp(5 * (b[k] + 1.96 * se[k])) - 1):+.1f})"
    return [f"{label}: log S on wind, per 5 kt (n={len(Dm['s']):,}): crosswind {f(1)}, headwind {f(2)}, gust spread {f(3)}"], b[1], se[1]


def or_per5(D, threshold, label, controls=("aptrwy", "typeg", "own", "season", "straight_in", "height_source"), value="s"):
    ok = ~np.isnan(D[value]) & ~np.isnan(D["xw_kt"]) & ~np.isnan(D["hw_kt"]) & ~np.isnan(D["gust_spread"])
    Dm = subset(D, ok)
    X, names, levels = design(Dm, controls=controls, linear=True)
    y = (Dm[value] > threshold).astype(float)
    b, se = logit_with_se(X, y, Dm["icao"])
    return (f"{label}: n={len(y):,}, share above {threshold:g} {100 * y.mean():.1f}%, odds ratio per 5 kt crosswind "
            f"{math.exp(5 * b[1]):.3f} ({math.exp(5 * (b[1] - 1.96 * se[1])):.3f}-{math.exp(5 * (b[1] + 1.96 * se[1])):.3f})")


# ---------------------------------------------------------------- main

def main():
    os.makedirs(OUT, exist_ok=True)
    D = load()
    P = subset(D, D["group"] == "piston")
    J = subset(D, (D["group"] == "jet") & (D["straight_in"] == "yes"))
    L = [f"Q2 wind analysis. Primary population: {len(P['s']):,} measurable piston approaches (VMC, seven airports in their Q1a windows).",
         f"Machine-flown floor: {len(J['s']):,} jet straight-in approaches.", ""]

    L.append("1. DISTRIBUTION OF S BY WIND (95% intervals: wider of aircraft- and day-cluster bootstrap)")
    L += banded(P, "xw_kt", XW_BANDS, "Piston, crosswind")
    L += banded(J, "xw_kt", XW_BANDS, "Jets (floor), crosswind")
    L += banded(P, "frac", FRAC_BANDS, "Piston, crosswind as a fraction of POH max demonstrated")
    L += banded(P, "gust_spread", GUST_BANDS, "Piston, gust spread")
    L += banded(J, "gust_spread", GUST_BANDS, "Jets (floor), gust spread")
    L += banded(P, "hw_kt", HW_BANDS, "Piston, headwind (negative = tailwind)")
    L.append("")

    L.append("2. MODELS (controls: airport-runway, type, ownership, season, straight-in, height source)")
    with ProcessPoolExecutor(48) as pool:
        for thr in (1, 2):
            lines, _, _ = model_block(P, thr, f"Piston", pool=pool)
            L += lines
        for thr in (1, 2):
            lines, _, _ = model_block(J, thr, f"Jets (floor)", controls=("aptrwy", "season"), pool=pool)
            L += lines
    lp, bp, sep = logS_block(P, "Piston")
    lj, bj, sej = logS_block(J, "Jets (floor)", controls=("aptrwy", "season"))
    L += lp + lj
    d = bp - bj
    dse = math.sqrt(sep ** 2 + sej ** 2)
    L.append(f"  piston minus jet, log S per 5 kt crosswind: {100 * (math.exp(5 * d) - 1):+.1f}% "
             f"({100 * (math.exp(5 * (d - 1.96 * dse)) - 1):+.1f} to {100 * (math.exp(5 * (d + 1.96 * dse)) - 1):+.1f}), the part not explained by measurement and physics")
    L.append("")

    L.append("3. CALIBRATION AGAINST Q1: S at calm, at the revealed limit, and at the POH max demonstrated crosswind")
    for name, mask in (("calm, crosswind 0-4 kt", P["xw_kt"] < 5),
                       ("revealed limit band, 10-12 kt (activity halves at 10.8 kt)", (P["xw_kt"] >= 10) & (P["xw_kt"] < 12)),
                       ("at 0.75-1.0 of max demonstrated", (P["frac"] >= 0.75) & (P["frac"] < 1.0)),
                       ("above max demonstrated", P["frac"] >= 1.0)):
        s = P["s"][mask]
        if len(s) >= 10:
            e = stats(s)
            L.append(f"  {name}: n={len(s):,}, median {e[0]:.2f}, p90 {e[1]:.2f}, share above 1 {100 * e[3]:.1f}%, above 2 {100 * e[4]:.1f}%")
        else:
            L.append(f"  {name}: n={len(s)} (too few)")
    L.append("")

    L.append("4. WHICH ELEMENTS DEGRADE: share of approaches above 1 on each criterion, by crosswind band")
    L.append("  " + " " * 30 + "  ".join(f"{(f'{a}-{b - 1}' if b < 99 else f'{a}+'):>8s}" for a, b in XW_BANDS))
    for c in CRIT:
        cells = []
        for a, b in XW_BANDS:
            m = (P["xw_kt"] >= a) & (P["xw_kt"] < b) & ~np.isnan(P[c])
            cells.append(f"{100 * np.mean(P[c][m] > 1):7.1f}%" if m.sum() >= 20 else "    n<20")
        L.append(f"  {CRIT_NAMES[c]:30s}" + "  ".join(cells))
    for a, b in XW_BANDS:
        m = (P["xw_kt"] >= a) & (P["xw_kt"] < b)
        al = P["align_hat"][m]
        late = np.mean((al < 300) | np.isnan(al)) if m.sum() else np.nan
        L.append(f"  crosswind {a}-{b if b < 99 else '+'}: lined up below 300 ft or never {100 * late:.1f}%, "
                 f"M4 descent-rate SD median {np.nanmedian(P['m4_sd_descent'][m]):.0f} fpm, lateral SD median {np.nanmedian(P['m4_sd_lat_ft'][m]):.0f} ft (n={m.sum():,})")
    L.append("")

    L.append("5. BENJAMIN'S DIRECTION HYPOTHESIS (pattern approaches with an identified base leg; positive = wind from the base side)")
    M = subset(P, ~np.isnan(P["xw_from_base_kt"]) & (P["straight_in"] == "no"))
    sx = M["xw_from_base_kt"]
    for a, b in ((-15, -10), (-10, -5), (-5, -2), (-2, 2), (2, 5), (5, 10), (10, 15)):
        m = (sx >= a) & (sx < b)
        if m.sum() < 20:
            continue
        ov = M["overshoot_ft"][m]
        al = M["align_hat"][m]
        L.append(f"  {a:+d} to {b:+d} kt: n={m.sum():6,}, overshoot median {np.nanmedian(ov):5.0f} ft, p90 {np.nanpercentile(ov, 90):5.0f} ft, "
                 f"share above 200 ft {100 * np.nanmean(ov > 200):5.1f}%, lined up below 300 ft or never {100 * np.mean((al < 300) | np.isnan(al)):5.1f}%")
    ok = ~np.isnan(M["overshoot_ft"]) & ~np.isnan(M["hw_kt"]) & ~np.isnan(M["gust_spread"])
    Mm = subset(M, ok)
    X, names, levels = design(Mm, xw=np.zeros(ok.sum()), controls=("aptrwy", "typeg", "own", "season", "height_source"), linear=True)
    X[:, 1] = np.maximum(0, Mm["xw_from_base_kt"])
    X = np.column_stack([X, np.maximum(0, -Mm["xw_from_base_kt"])])
    y = (Mm["overshoot_ft"] > 200).astype(float)
    b, se = logit_with_se(X, y, Mm["icao"])
    L.append(f"  logistic, overshoot above 200 ft (n={len(y):,}): odds ratio per 5 kt wind from the base side {math.exp(5 * b[1]):.3f} "
             f"({math.exp(5 * (b[1] - 1.96 * se[1])):.3f}-{math.exp(5 * (b[1] + 1.96 * se[1])):.3f}), "
             f"per 5 kt from the far side {math.exp(5 * b[-1]):.3f} ({math.exp(5 * (b[-1] - 1.96 * se[-1])):.3f}-{math.exp(5 * (b[-1] + 1.96 * se[-1])):.3f})")
    L.append("")

    L.append("6. SENSITIVITIES: S above 2, odds ratio per 5 kt crosswind (linear crosswind, same controls), and S above 1")
    w = windows()
    sens = [
        ("primary", np.ones(len(P["s"]), bool), "s"),
        ("LWM out, BED from 2025-07", (P["airport"] != "LWM") & ~((P["airport"] == "BED") & (P["date"] < "2025-07-01")), "s"),
        ("straight-in only", P["straight_in"] == "yes", "s"),
        ("late-turn descriptor flag out", P["flag_practice"] != "1", "s"),
        ("25 ft altimeters only", P["height_source"] == "baro", "s"),
        ("calibrated GNSS heights only", P["height_source"] == "gnss_calibrated", "s"),
        ("NACp 10 only", P["nacp"] == "10", "s"),
        ("true height", np.ones(len(P["s"]), bool), "s_true"),
        ("floor 50 ft", np.ones(len(P["s"]), bool), "s_below50"),
        ("single-report descent rate", np.ones(len(P["s"]), bool), "s_c4raw"),
    ]
    for name, mask, value in sens:
        Q = subset(P, mask)
        ctr = ("aptrwy", "typeg", "own", "season", "straight_in") if "only" in name and ("altimeter" in name or "GNSS" in name) else \
            ("aptrwy", "typeg", "own", "season", "height_source") if name == "straight-in only" else \
            ("aptrwy", "typeg", "own", "season", "straight_in", "height_source")
        try:
            L.append("  " + or_per5(Q, 2, f"{name} [{value}], S>2", controls=ctr, value=value))
            L.append("  " + or_per5(Q, 1, f"{name} [{value}], S>1", controls=ctr, value=value))
        except np.linalg.LinAlgError:
            L.append(f"  {name}: model failed")
    # tolerance variants: recompute S from the criterion ratios
    for lat_tol, vert_tol in ((100, 100), (300, 100), (200, 75), (200, 150)):
        k1, k3 = 200 / lat_tol, 100 / vert_tol
        comp = np.column_stack([P["g_c1"] * k1, P["g_c2a"], P["g_c3"] * k3, P["g_c4"], P["g_c5b"],
                                P["b_c1"] * k1, P["b_c2a"], P["b_c3"] * k3, P["b_c4"]])
        Q = dict(P)
        Q["s_tol"] = np.nanmax(np.where(np.isnan(comp), -np.inf, comp), axis=1)
        L.append("  " + or_per5(Q, 2, f"lateral {lat_tol} ft, vertical {vert_tol} ft, S>2", value="s_tol"))
    L.append("")

    text = "\n".join(L)
    open(os.path.join(OUT, "summary.txt"), "w").write(text + "\n")
    with open(os.path.join(OUT, "bands.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(BANDS_ROWS[0]))
        wr.writeheader()
        wr.writerows(BANDS_ROWS)
    print(text)


if __name__ == "__main__":
    main()
