#!/usr/bin/env python3
"""
wind_filter_check.py

Benjamin's question on the draft: could the one-minute wind filter throw away real, localized gusts? The filter
(wind_qc.py) tests only the two-minute sustained speed. A five-second gust is dropped only when it is above 80 kt
or more than 40 kt above the sustained wind, and the sustained wind is then kept. This counts, for the stations of
the admitted US airports, how many one-minute records each rule removes, and what the weather looked like when a
record was removed in a month that was otherwise kept.

    python3 review_2026-10-05/wind_filter_check.py --workers 40
"""

import argparse
import bisect
import datetime as dt
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import q1a_crosswind as qc  # noqa: E402
import us_airports as ua  # noqa: E402
import us_inclusion as ui  # noqa: E402
import wind_qc  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wind_filter_check.txt")


def station_stats(station):
    onemin = qc.load_onemin(station)
    metars, mtimes = qc.load_metar_obs(station)
    if not onemin:
        return station, None
    mt = [t.timestamp() for t in mtimes]
    ms = [o["sknt"] for o in metars]
    mg = [o["gust"] for o in metars]
    clean, _ = wind_qc._qc_minutes(onemin, mt, ms)
    month = lambda m: dt.datetime.fromtimestamp(m * 60, dt.timezone.utc).strftime("%Y-%m")
    total, kept = {}, {}
    for m in onemin:
        total[month(m)] = total.get(month(m), 0) + 1
    for m in clean:
        kept[month(m)] = kept.get(month(m), 0) + 1
    bad_months = {mo for mo, n in total.items() if n and (n - kept.get(mo, 0)) / n > wind_qc.MONTH_DROP_SHARE}
    res = {"records": 0, "with_speed": 0, "drop_max": 0, "drop_metar": 0, "drop_neighbor": 0, "gust_dropped": 0,
           "months": len(total), "bad_months": len(bad_months), "records_in_bad_months": sum(total[m] for m in bad_months),
           "kept_month_drops": [], "kept_month_records": 0, "gusts_kept_ge25": 0, "gusts_kept_ge35": 0}
    mins = sorted(onemin)
    for k, m in enumerate(mins):
        rec = onemin[m]
        res["records"] += 1
        if rec[1] is None:
            continue
        res["with_speed"] += 1
        in_bad = month(m) in bad_months
        if not in_bad:
            res["kept_month_records"] += 1
        if m not in clean:
            s = rec[1]
            t = m * 60
            i = bisect.bisect_left(mt, t)
            near = [j for j in (i - 1, i) if 0 <= j < len(mt) and abs(mt[j] - t) <= wind_qc.METAR_WINDOW_S and ms[j] is not None]
            j = min(near, key=lambda j: abs(mt[j] - t)) if near else None
            if s > wind_qc.MAX_KT:
                res["drop_max"] += 1
            elif j is not None and abs(s - ms[j]) > wind_qc.DIFF_KT:
                res["drop_metar"] += 1
            else:
                res["drop_neighbor"] += 1
            if not in_bad:
                w = [onemin[mins[q]][1] for q in range(max(0, k - 5), min(len(mins), k + 6))
                     if q != k and abs(mins[q] - m) <= 5 and onemin[mins[q]][1] is not None]
                res["kept_month_drops"].append((s, ms[j] if j is not None else None, mg[j] if j is not None else None,
                                                statistics.median(w) if w else None, rec[3]))
        else:
            if clean[m][3] is None and rec[3] is not None:
                res["gust_dropped"] += 1
            if not in_bad and clean[m][3] is not None:
                res["gusts_kept_ge25"] += clean[m][3] >= 25
                res["gusts_kept_ge35"] += clean[m][3] >= 35
    return station, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=40)
    args = ap.parse_args()
    inc = ui.load()
    sites = ua.load()
    stations = sorted({sites[a].station for a in inc.included_airports()})
    agg = None
    drops = []
    per = []
    with ProcessPoolExecutor(args.workers) as ex:
        for st, r in ex.map(station_stats, stations):
            if r is None:
                continue
            per.append((st, r))
            drops += [(st,) + x for x in r["kept_month_drops"]]
            if agg is None:
                agg = {k: 0 for k, v in r.items() if not isinstance(v, list)}
            for k in agg:
                agg[k] += r[k]
    L = [f"One-minute wind filter at {len(per)} stations of the admitted US airports (2025-09 to 2026-09 files)", ""]
    L.append(f"  records {agg['records']:,}, with a sustained speed {agg['with_speed']:,}")
    L.append(f"  dropped by the minute rules: above 60 kt {agg['drop_max']:,}, more than 15 kt from the METAR {agg['drop_metar']:,}, "
             f"more than 15 kt from the 5-minute median {agg['drop_neighbor']:,} "
             f"(together {100 * (agg['drop_max'] + agg['drop_metar'] + agg['drop_neighbor']) / agg['with_speed']:.3f}% of records)")
    L.append(f"  station-months dropped whole: {agg['bad_months']} of {agg['months']:,} ({agg['records_in_bad_months']:,} records)")
    L.append(f"  gusts set aside (above 80 kt or more than 40 kt over the sustained wind) with the sustained wind kept: {agg['gust_dropped']:,}")
    L.append(f"  in kept months: {agg['kept_month_records']:,} records, {len(drops):,} dropped by the minute rules "
             f"({100 * len(drops) / max(agg['kept_month_records'], 1):.4f}%). Gusts kept: {agg['gusts_kept_ge25']:,} records with a gust of 25 kt or more, "
             f"{agg['gusts_kept_ge35']:,} with 35 kt or more")
    if drops:
        s = np.array([d[1] for d in drops], dtype=float)
        mtr = np.array([np.nan if d[2] is None else d[2] for d in drops], dtype=float)
        mg = np.array([np.nan if d[3] is None else d[3] for d in drops], dtype=float)
        nb = np.array([np.nan if d[4] is None else d[4] for d in drops], dtype=float)
        L.append(f"  dropped records in kept months: median sustained {np.nanmedian(s):.0f} kt against the METAR's {np.nanmedian(mtr):.0f} kt "
                 f"and the 5-minute median {np.nanmedian(nb):.0f} kt; METAR reported a gust for {100 * np.mean(~np.isnan(mg)):.1f}% of them; "
                 f"dropped value lower than both METAR and neighbors {100 * np.mean((s < mtr) & (s < nb)):.1f}%, higher than both {100 * np.mean((s > mtr) & (s > nb)):.1f}%")
        top = {}
        for d in drops:
            top[d[0]] = top.get(d[0], 0) + 1
        L.append("  stations with the most drops in kept months: " + ", ".join(f"{k} {v}" for k, v in sorted(top.items(), key=lambda x: -x[1])[:10]))
    bad = [(st, r["bad_months"]) for st, r in per if r["bad_months"]]
    L.append("  stations with months dropped whole: " + ", ".join(f"{st} ({n})" for st, n in bad))
    text = "\n".join(L)
    open(OUT, "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
