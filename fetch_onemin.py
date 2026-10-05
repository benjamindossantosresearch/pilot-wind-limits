#!/usr/bin/env python3
"""
fetch_onemin.py

Downloads one-minute ASOS wind (NCEI data served by the Iowa Environmental
Mesonet) for a list of stations, one file per station per month, into
weather/onemin/<STATION>_<YYYY-MM>.csv. Existing files are skipped, so reruns
only fetch what is missing. Requests are spaced to respect IEM's limit of
about one request per second.

Usage:
    python3 fetch_onemin.py --stations LWM,OWD,BED,PYM,TAN --months 2026-03,2026-07,2026-08,2026-09

Columns: station, station_name, valid(UTC), drct, sknt, gust_drct, gust_sknt
(two-minute average wind and five-second peak gust, direction in degrees true).
"""

import argparse
import datetime as dt
import os
import time
import urllib.request

URL = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?station={st}"
       "&vars=drct&vars=sknt&vars=gust_drct&vars=gust_sknt"
       "&sts={sts}T00:00Z&ets={ets}T00:00Z&sample=1min&what=download&delim=comma&tz=UTC")


def month_bounds(ym):
    start = dt.date.fromisoformat(f"{ym}-01")
    end = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return start, end


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stations", required=True, help="comma-separated IEM ids without the K, e.g. LWM,OWD")
    ap.add_argument("--months", required=True, help="comma-separated YYYY-MM")
    ap.add_argument("--out", default="weather/onemin")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    for st in [s.strip().upper() for s in args.stations.split(",") if s.strip()]:
        for ym in [m.strip() for m in args.months.split(",") if m.strip()]:
            path = os.path.join(args.out, f"{st}_{ym}.csv")
            if os.path.exists(path):
                print(f"{st} {ym}: exists")
                continue
            start, end = month_bounds(ym)
            req = urllib.request.Request(URL.format(st=st, sts=start, ets=end),
                                         headers={"User-Agent": "wind-limits-research"})
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=300) as r:
                        data = r.read()
                    break
                except Exception as exc:
                    print(f"{st} {ym}: attempt {attempt + 1} failed ({exc!r})")
                    time.sleep(10)
            else:
                continue
            tmp = f"{path}.tmp{os.getpid()}"   # per-process name, so parallel downloaders never share a temp file
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            n = data.count(b"\n") - 1
            expected = (end - start).days * 1440
            print(f"{st} {ym}: {n:,} minutes ({100.0 * n / expected:.1f}% of the month)")
            time.sleep(2)


if __name__ == "__main__":
    main()
