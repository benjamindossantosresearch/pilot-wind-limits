#!/usr/bin/env python3
"""
check_baro_vs_metar.py

Sanity-checks the hourly baro-to-MSL correction that adsb_airport_coverage.py
estimates from GNSS/baro pairs against the airport's METAR altimeter setting.

The correction should track the altimeter setting closely:
    expected_ft = pressure altitude of the altimeter setting, sign flipped
                = 145366.45 * ((A / 29.9213) ** 0.190284 - 1)   (about 925 ft per inHg)
What is left over is mostly temperature error (true altitude above the
station grows about 4 percent per 10 C above standard), geoid offset error,
and noise from small samples.

Usage:
    python3 check_baro_vs_metar.py coverage_KPYM/baro_correction.csv weather/PYM_metar_2026-09-07_2026-09-30.csv

The METAR file is an IEM asos.py export with columns valid (UTC), alti, tmpf.
"""

import csv
import datetime as dt
import statistics
import sys


def expected_corr_ft(alti_inhg):
    return 145366.45 * ((alti_inhg / 29.9213) ** 0.190284 - 1)


def load_metars(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["alti"] in ("M", ""):
                continue
            t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
            tmpf = float(r["tmpf"]) if r.get("tmpf") not in (None, "M", "") else None
            rows.append((t, float(r["alti"]), tmpf))
    rows.sort(key=lambda r: r[0])
    return rows


def nearest(metars, t, max_min=45):
    best = min(metars, key=lambda m: abs((m[0] - t).total_seconds()), default=None)
    if best is None or abs((best[0] - t).total_seconds()) > max_min * 60:
        return None
    return best


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    corr_path, metar_path = sys.argv[1:]
    metars = load_metars(metar_path)
    rows = []
    with open(corr_path) as f:
        for r in csv.DictReader(f):
            hour = dt.datetime.fromisoformat(r["hour_utc"])
            m = nearest(metars, hour + dt.timedelta(minutes=30))
            if m is None:
                continue
            exp = expected_corr_ft(m[1])
            rows.append({
                "hour": hour, "source": r["source"], "n_pairs": int(r["n_pairs"]),
                "corr": float(r["corr_ft"]), "alti": m[1], "expected": exp,
                "diff": float(r["corr_ft"]) - exp,
                "tmp_c": (m[2] - 32) / 1.8 if m[2] is not None else None,
            })
    if not rows:
        sys.exit("No hours matched a METAR.")

    def describe(sel, label):
        d = [r["diff"] for r in sel]
        if not d:
            print(f"{label:34s} n=0")
            return
        q = sorted(d)
        print(f"{label:34s} n={len(d):4d}  median diff {statistics.median(d):+6.0f} ft  "
              f"IQR {q[len(q) // 4]:+5.0f} to {q[(3 * len(q)) // 4]:+5.0f}  "
              f"max |diff| {max(abs(x) for x in d):4.0f}")

    print("Measured correction minus METAR-implied correction (ft)")
    describe(rows, "all hours")
    describe([r for r in rows if r["source"] == "hour"], "hours with own estimate")
    describe([r for r in rows if r["source"] == "borrowed"], "hours borrowing a nearby hour")
    describe([r for r in rows if r["source"] in ("day", "overall")], "hours using a day or overall median")

    own = [r for r in rows if r["source"] == "hour"]
    if len(own) >= 3:
        try:
            print(f"\nCorrelation of measured vs expected (own-estimate hours): "
                  f"{statistics.correlation([r['corr'] for r in own], [r['expected'] for r in own]):.3f}")
        except statistics.StatisticsError:
            pass

    print("\nPer day (own-estimate hours only)")
    print("  date        hours  altimeter range   expected range    median diff")
    by_day = {}
    for r in own:
        by_day.setdefault(r["hour"].date(), []).append(r)
    for d in sorted(by_day):
        g = by_day[d]
        a = [r["alti"] for r in g]
        e = [r["expected"] for r in g]
        print(f"  {d}  {len(g):5d}  {min(a):.2f} to {max(a):.2f}    {min(e):+5.0f} to {max(e):+5.0f}     "
              f"{statistics.median(r['diff'] for r in g):+5.0f}")


if __name__ == "__main__":
    main()
