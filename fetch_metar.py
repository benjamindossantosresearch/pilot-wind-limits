#!/usr/bin/env python3
"""
fetch_metar.py

Downloads METARs (routine and special reports) from the Iowa Environmental
Mesonet for a list of stations and one date range, one file per station:
weather/<STATION>_metar_<start>_<end>.csv with the columns the rest of the
project reads (station, valid, metar, alti, tmpf, drct, sknt, gust).
Existing files are skipped. Requests are spaced to about one per second.

    python3 fetch_metar.py --stations-file reference/us_candidates.csv --start 2025-09-01 --end 2026-09-30
"""

import argparse
import csv
import datetime as dt
import os
import time
import urllib.request

URL = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={st}"
       "&data=metar&data=alti&data=tmpf&data=drct&data=sknt&data=gust"
       "&year1={y1}&month1={m1}&day1={d1}&year2={y2}&month2={m2}&day2={d2}"
       "&tz=Etc%2FUTC&format=onlycomma&latlon=no&elev=no&missing=M&trace=T&direct=yes&report_type=3&report_type=4")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stations-file", required=True, help="CSV with an asos_id column")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True, help="last day included")
    ap.add_argument("--out", default="weather")
    args = ap.parse_args()
    stations = [r["asos_id"] for r in csv.DictReader(open(args.stations_file))]
    s = dt.date.fromisoformat(args.start)
    e = dt.date.fromisoformat(args.end) + dt.timedelta(days=1)
    done = failed = 0
    for st in stations:
        path = os.path.join(args.out, f"{st}_metar_{args.start}_{args.end}.csv")
        if os.path.exists(path) and os.path.getsize(path) > 100:
            continue
        url = URL.format(st=st, y1=s.year, m1=s.month, d1=s.day, y2=e.year, m2=e.month, d2=e.day)
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "wind-limits research (IEM bulk METAR)"})
                with urllib.request.urlopen(req, timeout=600) as r:
                    data = r.read()
                if not data.startswith(b"station,"):
                    raise ValueError(data[:120])
                tmp = path + ".part"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, path)
                done += 1
                print(f"{st}: {data.count(b'\n') - 1:,} reports", flush=True)
                break
            except Exception as ex:
                print(f"{st}: attempt {attempt + 1} failed ({ex})", flush=True)
                time.sleep(10 * (attempt + 1))
        else:
            failed += 1
        time.sleep(1.2)
    print(f"done {done}, failed {failed}")


if __name__ == "__main__":
    main()
