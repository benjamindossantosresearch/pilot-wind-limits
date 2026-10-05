#!/usr/bin/env python3
"""
check_metar_sources.py

Cross-checks the Iowa Environmental Mesonet (IEM) METAR archive used by the
study, report by report, against one of two sources:

  --against awc    Aviation Weather Center (aviationweather.gov) data API. Serves
                   only the last 30 days, so it checks recent transcription.
  --against ncei   NOAA NCEI Integrated Surface Database (ISD, Global Hourly), an
                   independent federal archive that keeps each original report in
                   its REM field. Available 2023-01 to 2025-08-27 when checked
                   (2026-10-02). Files cached in weather/ncei/.

    python3 check_metar_sources.py --stations PYM,LWM,OWD,BED --days 30
    python3 check_metar_sources.py --stations PYM,LWM,OWD,BED,BDR --against ncei

For each station: AWC reports are fetched in 4-day windows (the API caps each
response at 400 reports) and saved to weather/awc/<STATION>_<start>_<end>.json.
Reports are matched on station and observation minute. Compared fields, read from
the raw report text so both sides are parsed the same way: wind direction,
speed, gust, altimeter setting, temperature, visibility, and the full report text.
"""

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import time
import urllib.request
from collections import Counter

AWC = "https://aviationweather.gov/api/data/metar?ids=K{st}&format=json&date={end}&hours={hours}"
HERE = os.path.dirname(os.path.abspath(__file__))


def norm(raw):
    """Report body for comparison: no METAR/SPECI prefix, maintenance flag, or trailing '='."""
    s = re.sub(r"^(METAR|SPECI)\s+", "", raw.strip())
    s = re.sub(r"\s*\$?\s*=?\s*$", "", s)
    return " ".join(s.replace("$", "").split())


def fields(raw):
    body = norm(raw).split(" RMK")[0]
    out = {}
    m = re.search(r"\s(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT", body)
    if m:
        out["wdir"], out["wspd"], out["gust"] = m.group(1), int(m.group(2)), int(m.group(3)) if m.group(3) else None
    m = re.search(r"\sA(\d{4})", body)
    out["alti"] = int(m.group(1)) if m else None
    m = re.search(r"\s(M?\d{2})/", body)
    out["temp"] = m.group(1) if m else None
    m = re.search(r"\s((?:\d+\s)?M?\d+(?:/\d+)?SM)", body)
    out["vis"] = m.group(1) if m else None
    return out


def fetch_awc(st, days, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    reports = {}
    for k in range(0, days, 4):
        end = now - dt.timedelta(days=k)
        start = end - dt.timedelta(days=4)
        path = os.path.join(out_dir, f"{st}_{start:%Y%m%d%H}_{end:%Y%m%d%H}.json")
        if not os.path.exists(path):
            url = AWC.format(st=st, end=end.strftime("%Y-%m-%dT%H:%M:%SZ"), hours=96)
            req = urllib.request.Request(url, headers={"User-Agent": "wind-limits-research"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
            except Exception as exc:
                print(f"  {st} {end:%Y-%m-%d}: {exc!r}")
                continue
            with open(path, "wb") as f:
                f.write(data)
            time.sleep(1.0)
        try:
            for o in json.load(open(path)):
                t = dt.datetime.fromtimestamp(o["obsTime"], dt.timezone.utc).replace(second=0)
                reports[t] = o["rawOb"]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return reports


NCEI = "https://www.ncei.noaa.gov/data/global-hourly/access/{year}/{sid}.csv"


def fetch_ncei(st, years, out_dir):
    """Original METAR/SPECI text by observation minute, from NCEI ISD station-year files."""
    os.makedirs(out_dir, exist_ok=True)
    hist = os.path.join(out_dir, "isd-history.csv")
    if not os.path.exists(hist):
        urllib.request.urlretrieve("https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv", hist)
    rows = [r for r in csv.DictReader(open(hist)) if r["ICAO"] == "K" + st and r["WBAN"] != "99999"]
    if not rows:
        return {}
    r = max(rows, key=lambda r: r["END"])
    sid = r["USAF"] + r["WBAN"]
    reports = {}
    for y in years:
        path = os.path.join(out_dir, f"K{st}_{y}.csv")
        if not os.path.exists(path):
            try:
                req = urllib.request.Request(NCEI.format(year=y, sid=sid), headers={"User-Agent": "wind-limits-research"})
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = resp.read()
            except Exception:
                continue
            with open(path, "wb") as f:
                f.write(data)
            time.sleep(1.0)
        try:
            for row in csv.DictReader(open(path)):
                if row.get("REPORT_TYPE", "").strip() not in ("FM-15", "FM-16"):
                    continue
                rem = row.get("REM", "")
                m = re.match(r"MET(\d{3})", rem)
                if not m:
                    continue
                # MET + 3-digit length of the report text, sometimes led by a local timestamp
                body = rem[6:6 + int(m.group(1))]
                body = re.sub(r"^\d\d/\d\d/\d\d \d\d:\d\d:\d\d\s*", "", body)
                t = dt.datetime.fromisoformat(row["DATE"]).replace(tzinfo=dt.timezone.utc, second=0)
                reports[t] = body
        except (csv.Error, ValueError):
            pass
    return reports


def load_iem(st):
    reports = {}
    for path in glob.glob(os.path.join(HERE, "weather", f"{st}_metar_*.csv")):
        with open(path) as f:
            for r in csv.DictReader(f):
                t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                reports[t] = r["metar"]
    return reports


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stations", required=True)
    ap.add_argument("--days", type=int, default=30, help="AWC only")
    ap.add_argument("--against", default="awc", choices=["awc", "ncei"])
    ap.add_argument("--years", default="2023,2024,2025", help="NCEI only")
    args = ap.parse_args()
    src = args.against.upper()
    print(f"station  window                 {src:>5s}   IEM  matched  {src}-only  IEM-only  text-differs  field mismatches")
    for st in [s.strip().upper() for s in args.stations.split(",") if s.strip()]:
        if args.against == "awc":
            awc = fetch_awc(st, args.days, os.path.join(HERE, "weather", "awc"))
        else:
            awc = fetch_ncei(st, [int(y) for y in args.years.split(",")], os.path.join(HERE, "weather", "ncei"))
        iem = load_iem(st)
        if not awc:
            print(f"  {st}: no {src} data")
            continue
        lo, hi = min(awc), max(awc)
        iem_win = {t: r for t, r in iem.items() if lo <= t <= hi}
        both = sorted(set(awc) & set(iem_win))
        mism, text_diff, examples = Counter(), 0, []
        fields_checked = Counter()
        for t in both:
            a, b = fields(awc[t]), fields(iem_win[t])
            bad = [k for k in a if a.get(k) != b.get(k)]
            fields_checked.update(a.keys())
            for k in bad:
                mism[k] += 1
            if norm(awc[t]) != norm(iem_win[t]):
                text_diff += 1
                if len(examples) < 2:
                    examples.append((t, norm(awc[t]), norm(iem_win[t])))
        only_awc = len(set(awc) - set(iem_win))
        only_iem = len(set(iem_win) - set(awc))
        print(f"  {st:5s}  {lo:%Y-%m-%d} to {hi:%Y-%m-%d}  {len(awc):5d} {len(iem_win):5d}  {len(both):7d}  {only_awc:8d}  {only_iem:8d}  "
              f"{text_diff:12d}  " + (", ".join(f"{k} {n} ({100 * n / max(fields_checked[k], 1):.2f}%)" for k, n in mism.items()) or "none"))
        for t, x, y in examples:
            print(f"      {t:%Y-%m-%d %H:%M}\n        {src}: {x}\n        IEM: {y}")


if __name__ == "__main__":
    main()
