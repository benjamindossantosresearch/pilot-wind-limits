#!/usr/bin/env python3
"""
load_slim.py

Reads a US approaches file once (all approaches, before inclusion) and writes a pickle with the columns the
2026-10-05 review checks need, plus the derived scores of us_q2.load() (S_fp, S_spd, S_turn, frac, typeg,
own, season, aptrwy, dayk) and flags for inclusion (day_ok) and inferred passes. Nothing in the frozen
outputs is touched.

    python3 review_2026-10-05/load_slim.py q2_us_v31_cas/approaches.csv review_2026-10-05/us_cas.pkl
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import us_airports as ua  # noqa: E402
import us_inclusion as ui  # noqa: E402
import us_q1a  # noqa: E402
import us_q2  # noqa: E402

EXTRA = ["local_time", "local_hour", "visit", "category", "model", "year_mfr", "poh_approach_kias", "coupled",
         "status_500", "s500", "g500_c1", "g500_c2a", "g500_c3", "g500_c4", "g500_c5b", "gate_est_as", "gate_est_tas",
         "cas_factor", "gust_kt", "wind_drct", "lowest_time", "app_no", "g_c5b", "align_censored", "never_aligned"]


def main(src, dst):
    base = ["airport", "date", "icao", "type", "group", "ownership", "runway", "status", "vmc", "straight_in", "height_source",
            "nacp", "apps_in_visit", "base_side", "xw_kt", "hw_kt", "gust_spread", "xw_low_kt", "gust_xw_low_kt", "xw_right_kt",
            "xw_from_base_kt", "poh_xwind_kt", "poh_xwind_basis", "overshoot_ft", "align_hat", "lowest_hat", "turn_max_bank",
            "flag_practice", "hat_true_minus_geom_ft", "s", "inferred", "wind_kt"] + us_q2.FP + us_q2.SPD
    df = pd.read_csv(src, usecols=base + EXTRA, low_memory=False)
    inc = ui.load()
    df["day_ok"] = np.array([inc.day_ok(a, d) for a, d in zip(df["airport"].values, df["date"].values)])
    df["is_inferred"] = df["inferred"].notna()
    df["status_raw"] = df["status"]
    df.loc[df["is_inferred"], "status"] = "inferred"
    sites = ua.load()
    known = df["airport"].map(lambda a: a in sites)
    df = df[known].copy()
    df["tower"] = df["airport"].map(lambda a: sites[a].tower.startswith("ATCT"))
    df["region"] = df["airport"].map(lambda a: us_q1a.region_of(sites[a].state))
    df["S_fp"] = df[us_q2.FP].max(axis=1, skipna=True)
    df["S_spd"] = df[us_q2.SPD].max(axis=1, skipna=True)
    df["S_comb"] = df[["S_fp", "S_spd"]].max(axis=1, skipna=True)
    turn = (df["straight_in"] == "no") & df["base_side"].notna()
    t1 = df["overshoot_ft"] / 200.0
    alt = df["align_hat"].where(df["align_hat"].notna(), df["lowest_hat"])
    t2 = (300.0 / alt.clip(lower=50.0)).clip(upper=6.0)
    df["S_turn"] = np.where(turn, np.fmax(t1.fillna(0), t2), np.nan)
    df["frac"] = df["xw_kt"] / df["poh_xwind_kt"]
    df["typeg"] = df["type"].map(lambda t: us_q2.TYPE_GROUPS.get(t, "other"))
    df["own"] = df["ownership"].where(df["ownership"].isin(["fleet", "private"]), "other")
    m = pd.to_datetime(df["date"]).dt.month
    df["season"] = np.select([m.isin([12, 1, 2]), m.isin([3, 4, 5]), m.isin([6, 7, 8])], ["DJF", "MAM", "JJA"], "SON")
    df["aptrwy"] = df["airport"] + "/" + df["runway"].astype(str)
    df["dayk"] = df["airport"] + "|" + df["date"]
    for c in ("airport", "type", "group", "ownership", "runway", "status", "status_raw", "straight_in", "height_source",
              "poh_xwind_basis", "typeg", "own", "season", "region", "category", "status_500"):
        df[c] = df[c].astype("category")
    df.to_pickle(dst)
    print(f"{len(df):,} approaches written to {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
