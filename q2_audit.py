#!/usr/bin/env python3
"""
q2_audit.py

Audit of the two Q2 criteria that machine-flown jets also fail (Benjamin's
request, 2026-10-02): C4 sink rate and C5b speed stability. For each variant
the score S is rebuilt from the criterion ratios, and the variant is judged on:

  * how often it fires on piston approaches in calm crosswind (0-4 kt)
  * how often it fires on jets on straight-in approaches (machine-flown floor;
    a criterion that fails autopilot approaches is measuring noise or technique,
    not instability)
  * agreement with Benjamin's blind ratings of the 30 review approaches
    (Spearman, and whether the variant fires on the approaches he tagged for
    sink rate or speed)
  * the wind effect (odds ratio per 5 kt crosswind for S above 1 and 2)

Variants:
  C4 registered   |descent - 3 degree path rate| / 300 fpm
  C4 AFH          1,000 fpm sink is the edge on the steep side, level flight on the shallow side
  C4 stability    deviation from the approach's own median descent rate (300 to 100 ft) / 300 fpm
  C4 AFH+stab     the larger of the two
  C5b registered  estimated airspeed range over the 30 s before 300 ft / 10 kt
  C5b detrended   range around a straight-line trend over the same 30 s / 10 kt
  C5b 15 s        range over the last 15 s / 10 kt

    python3 q2_audit.py

Writes q2_audit/summary.txt.
"""

import csv
import glob
import json
import os

import numpy as np

import q2_wind as qw

POS = ["g_c1", "g_c2a", "g_c3", "b_c1", "b_c2a", "b_c3"]
C4 = {"registered": ["g_c4", "b_c4"], "AFH": ["g_c4_afh", "b_c4_afh"], "stability": ["c4_stab"],
      "AFH+stab": ["g_c4_afh", "b_c4_afh", "c4_stab"]}
C5 = {"registered": ["g_c5b"], "detrended": ["g_c5b_detr"], "15 s": ["g_c5b_15"], "none": []}
EXTRA = ["g_c4_afh", "b_c4_afh", "c4_stab", "g_c5b_detr", "g_c5b_15", "apps_in_visit", "seg_median_descent"]


def load():
    D = qw.load()
    # attach the audit columns and keys (q2_wind.load keeps a fixed column set)
    w = qw.windows()
    extra = {k: [] for k in EXTRA + ["visit", "app_no"]}
    for r in csv.DictReader(open("q2/approaches.csv")):
        if r["status"] != "ok" or r["vmc"] != "1" or not qw.in_window(r, w) or r["group"] not in ("piston", "jet"):
            continue
        for k in EXTRA:
            extra[k].append(qw.num(r[k]))
        extra["visit"].append(r["visit"])
        extra["app_no"].append(r["app_no"])
    for k, v in extra.items():
        D[k] = np.array(v)
    return D


def score(D, c4, c5):
    cols = POS + C4[c4] + C5[c5]
    comp = np.column_stack([D[c] for c in cols])
    return np.nanmax(np.where(np.isnan(comp), -np.inf, comp), axis=1)


def spearman(a, b):
    def rank(x):
        o = x.argsort()
        r = np.empty(len(x))
        r[o] = np.arange(len(x))
        for v in np.unique(x):
            m = x == v
            r[m] = r[m].mean()
        return r
    return float(np.corrcoef(rank(a), rank(b))[0, 1])


def main():
    D = load()
    P = qw.subset(D, D["group"] == "piston")
    J = qw.subset(D, (D["group"] == "jet") & (D["straight_in"] == "yes"))
    calmP = P["xw_kt"] < 5
    calmJ = J["xw_kt"] < 5
    key = {r["id"]: r for r in csv.DictReader(open("q2_review/key.csv"))}
    ans = {os.path.basename(f)[:3]: json.load(open(f)) for f in glob.glob("q2_review/answers/*.json")}
    RV = {"stable": 0, "minor": 1, "out": 2, "severe": 3}
    pos = {(a, v, n): i for i, (a, v, n) in enumerate(zip(P["airport"], P["visit"], P["app_no"]))}
    rev = [(rid, pos.get((k["airport"], k["visit"], k["app_no"]))) for rid, k in key.items()]
    rev = [(rid, i) for rid, i in rev if i is not None]

    L = [f"Q2 audit of sink rate (C4) and speed stability (C5b). Piston {len(P['s']):,} (calm {calmP.sum():,}), "
         f"jets straight-in {len(J['s']):,} (calm {calmJ.sum():,}), reviewed approaches {len(rev)}", ""]

    L.append("A. The criteria on their own, calm crosswind: share above 1")
    for name, cols in list(C4.items()) + [(k, v) for k, v in C5.items() if v]:
        fam = "C4" if name in C4 and cols in C4.values() else "C5b"
        mp = np.column_stack([P[c] for c in cols])
        mj = np.column_stack([J[c] for c in cols])
        sp = np.nanmax(np.where(np.isnan(mp), -np.inf, mp), axis=1)
        sj = np.nanmax(np.where(np.isnan(mj), -np.inf, mj), axis=1)
        L.append(f"  {fam if cols in C5.values() and name in C5 else 'C4'} {name:11s} piston {100 * np.mean(sp[calmP] > 1):5.1f}%   jets {100 * np.mean(sj[calmJ] > 1):5.1f}%")
    L.append("  (reference: centerline, lined up and glide path together: piston "
             f"{100 * np.mean(score({**P, **{}}, 'registered', 'registered')[calmP] > 1):.1f}% full score)")
    L.append("")

    L.append("B. Full score S with each combination")
    L.append("  C4 / C5b                  calm piston >1   >2    >3  | jets >1 | Spearman with blind ratings | OR per 5 kt crosswind, S>2 and S>1")
    desc_tag = {rid for rid, a in ans.items() if "descent" in a.get("issues", [])}
    spd_tag = {rid for rid, a in ans.items() if "speed" in a.get("issues", [])}
    for c4 in C4:
        for c5 in C5:
            sp = score(P, c4, c5)
            sj = score(J, c4, c5)
            rho = spearman(np.array([sp[i] for _, i in rev]), np.array([RV[ans[rid]["rating"]] for rid, _ in rev]))
            Q = dict(P)
            Q["s_var"] = sp
            or2 = qw.or_per5(Q, 2, "x", value="s_var").split("crosswind ")[-1]
            or1 = qw.or_per5(Q, 1, "x", value="s_var").split("crosswind ")[-1]
            L.append(f"  {c4:10s} / {c5:10s}    {100 * np.mean(sp[calmP] > 1):5.1f}%  {100 * np.mean(sp[calmP] > 2):5.1f}% {100 * np.mean(sp[calmP] > 3):5.1f}% | "
                     f"{100 * np.mean(sj[calmJ] > 1):5.1f}% | {rho:.3f} | {or2}  {or1}")
    L.append("")

    L.append("C. Agreement with the problems Benjamin picked on the 30 reviewed approaches")
    L.append(f"  tagged sink rate: {sorted(desc_tag)}; tagged speed: {sorted(spd_tag)}")
    for name, cols in C4.items():
        fires = {rid for rid, i in rev if np.nanmax([P[c][i] for c in cols] + [-np.inf]) > 1}
        L.append(f"  C4 {name:11s} fires on {len(fires):2d}: {len(fires & desc_tag)} of {len(desc_tag)} he tagged, {len(fires - desc_tag)} he did not")
    for name, cols in C5.items():
        if not cols:
            continue
        fires = {rid for rid, i in rev if np.nanmax([P[c][i] for c in cols] + [-np.inf]) > 1}
        L.append(f"  C5b {name:10s} fires on {len(fires):2d}: {len(fires & spd_tag)} of {len(spd_tag)} he tagged, {len(fires - spd_tag)} he did not")
    L.append("")
    L.append("D. Descent rates piston pilots fly between 300 and 100 ft (median per approach), calm")
    for grp in ("piston", "jet"):
        md = D["seg_median_descent"][(D["group"] == grp) & (D["xw_kt"] < 5)]
        md = md[~np.isnan(md)]
        L.append(f"  {grp}: median {np.median(md):.0f} fpm, p10 {np.percentile(md, 10):.0f}, p90 {np.percentile(md, 90):.0f}, "
                 f"above 1,000 fpm {100 * np.mean(md > 1000):.1f}%, n={len(md):,}")
    os.makedirs("q2_audit", exist_ok=True)
    text = "\n".join(L)
    open("q2_audit/summary.txt", "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
