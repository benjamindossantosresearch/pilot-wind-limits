#!/usr/bin/env python3
"""
us_q2_inferred_check.py

Post-hoc sensitivity found by the tower-count spot check (us_tower_spotcheck_traverse.py):
detector rule 11 (traverse) can repeat a circuit on a closely spaced parallel runway,
and an inferred approach can then be measured against the wrong runway. This reruns
the primary US Q2 wind effects (piston, VMC, measurable) with traverse-inferred
approaches excluded, and with all inferred approaches excluded, next to the full sample.

    python3 us_q2_inferred_check.py

Writes q2_us_results/inferred_check.txt.
"""

import os

import numpy as np

import us_q2


def main():
    df = us_q2.load()
    P = df[(df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok")].copy()
    P["inferred"] = P["inferred"].fillna("")
    L = [f"Primary Q2 sample: {len(P):,} approaches. Inferred: " +
         ", ".join(f"{k or 'none'} {v:,} ({100 * v / len(P):.2f}%)" for k, v in P["inferred"].value_counts().items()), ""]
    L.append("S_fp by inferred type: median, share above 1, above 2")
    for k, g in P.groupby("inferred"):
        L.append(f"  {k or 'none':9s} n={len(g):>9,}  median {g['S_fp'].median():.2f}  above 1 {100 * (g['S_fp'] > 1).mean():.1f}%  "
                 f"above 2 {100 * (g['S_fp'] > 2).mean():.1f}%")
    L.append("")
    top = P[P["inferred"] == "traverse"]["airport"].value_counts().head(10)
    L.append("Airports with most traverse-inferred measurable approaches (share of the airport's sample): " +
             ", ".join(f"{a} {n:,} ({100 * n / (P['airport'] == a).sum():.1f}%)" for a, n in top.items()))
    L.append("")
    for label, sel in (("all approaches (as reported)", P), ("traverse excluded", P[P["inferred"] != "traverse"]),
                       ("all inferred excluded", P[P["inferred"] == ""])):
        L.append(f"== {label}, n={len(sel):,}")
        for value in ("S_fp", "S_spd"):
            L += [l for l in us_q2.wind_effects(sel, value, label) if "above 1" in l or "above 2" in l or "log" in l]
        T = sel[sel["S_turn"].notna()]
        L += [l for l in us_q2.wind_effects(T, "S_turn", label + " turn to final") if "above 1" in l or "log" in l]
        for lo, hi in ((0, 5), (10, 15), (15, 20)):
            g = sel[(sel["xw_kt"] >= lo) & (sel["xw_kt"] < hi)]
            L.append(f"  crosswind {lo}-{hi - 1} kt: S_fp above 1 {100 * (g['S_fp'] > 1).mean():.1f}%, above 2 {100 * (g['S_fp'] > 2).mean():.1f}%, "
                     f"S_spd above 1 {100 * (g['S_spd'] > 1).mean():.1f}% (n={len(g):,})")
        L.append("")
    text = "\n".join(L)
    open(os.path.join(us_q2.OUT, "inferred_check.txt"), "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
