#!/usr/bin/env python3
"""
us_speed_check.py

Diagnostic of the speed score (S_spd) before the US results are frozen. Estimated
airspeed is groundspeed plus the ASOS headwind scaled to height, so an error in the
wind estimate grows with the wind. If the rise of S_spd with wind came mostly from
"too slow" flags in strong headwind, it would point to the wind estimate (wind at
pattern height underestimated) rather than to pilots. "Too fast" and unsteady speed
are what pilots plausibly do in wind and gusts.

At the 300 ft gate: slow = estimated airspeed more than 5 kt below the POH approach
speed plus half the gust spread, fast = more than 10 kt above, unsteady = detrended
30 s range above 10 kt (g_c5b_detr above 1). Piston, VMC, measurable, observed
approaches, the primary run (us_q2.APPROACHES), all included days.

    python3 us_speed_check.py

Writes <us_q2.OUT>/speed_check.txt.
"""

import numpy as np
import pandas as pd

import us_inclusion as ui
import us_q2

COLS = ["airport", "date", "group", "vmc", "status", "inferred", "xw_kt", "hw_kt", "gust_spread", "gate_est_as",
        "poh_approach_kias", "g_c5a", "b_c5a", "g_c5b_detr"]


def main():
    df = pd.read_csv(us_q2.APPROACHES, usecols=COLS, low_memory=False)
    df = df[(df["group"] == "piston") & (df["vmc"] == 1) & (df["status"] == "ok") & df["inferred"].isna()]
    inc = ui.load()
    df = df[np.array([inc.day_ok(a, d) for a, d in zip(df["airport"].values, df["date"].values)])]
    d = df[df["gate_est_as"].notna() & df["poh_approach_kias"].notna()].copy()
    d["dv"] = d["gate_est_as"] - (d["poh_approach_kias"] + 0.5 * d["gust_spread"].fillna(0))
    d["slow"] = d["dv"] < -5
    d["fast"] = d["dv"] > 10
    d["unsteady"] = d["g_c5b_detr"] > 1
    L = [f"Speed score diagnostic, {len(d):,} piston approaches with a gate airspeed and a POH approach speed.", ""]
    for key, bands, label in (("xw_kt", [(0, 5), (5, 10), (10, 15), (15, 20)], "crosswind"),
                              ("hw_kt", [(-10, -5), (-5, 0), (0, 5), (5, 10), (10, 15), (15, 25)], "headwind")):
        L.append(f"By {label} (kt): n | median gate airspeed minus target | slow | fast | unsteady")
        for lo, hi in bands:
            g = d[(d[key] >= lo) & (d[key] < hi)]
            if len(g) < 100:
                continue
            L.append(f"  {lo:>4} to {hi:<4} n={len(g):>9,} | {g['dv'].median():+5.1f} kt | {100 * g['slow'].mean():5.1f}% | "
                     f"{100 * g['fast'].mean():5.1f}% | {100 * g['unsteady'].mean():5.1f}%")
        L.append("")
    text = "\n".join(L)
    open(us_q2.OUT + "/speed_check.txt", "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
