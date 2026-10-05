#!/usr/bin/env python3
"""
fetch_days.py

Fills the regional ADS-B cache for a date range without running any analysis.
Each ADSB.lol archive day (2 to 4 GB) is streamed once, clipped to the region
box, and written to <cache>/<region>/YYYY-MM-DD.jsonl.gz. Days already cached
are skipped, so the command can be rerun after an interruption and only fetches
what is missing. Days are fetched newest first.

Usage:
    python3 fetch_days.py --start 2023-02-16 --end 2026-09-30 --workers 32
    python3 fetch_days.py --start 2026-09-01             # through yesterday (UTC)

The archive begins 2023-02-16. A handful of days have no release and are
reported as such.
"""

import argparse
import datetime as dt
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import adsb_airport_coverage as cov


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", help="YYYY-MM-DD inclusive (default yesterday UTC)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--region", default=cov.DEFAULT_REGION, choices=sorted(cov.REGIONS))
    ap.add_argument("--cache", default="adsb_cache")
    args = ap.parse_args()

    region = cov.REGIONS[args.region]
    cache_dir = cov.prepare_cache(args.cache, args.region)
    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end) if args.end else dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    days = [end - dt.timedelta(days=i) for i in range((end - start).days + 1)]
    todo = [d for d in days if not os.path.exists(os.path.join(cache_dir, f"{d}.jsonl.gz"))]
    print(f"{args.region}: {len(days)} day(s) {start} to {end}, {len(days) - len(todo)} cached, "
          f"{len(todo)} to fetch with {args.workers} worker(s)", flush=True)

    t0, done, failed, missing = time.time(), 0, [], []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(cov.cache_day, d, region, cache_dir) for d in todo]
        for fut in as_completed(futures):
            day, ok, status = fut.result()
            done += 1
            if not ok:
                (missing if status.startswith("no release") else failed).append(day)
            rate = done / max(time.time() - t0, 1) * 60
            eta = (len(todo) - done) / rate if rate else 0
            print(f"  [{day}] {status}   ({done}/{len(todo)}, {rate:.1f} days/min, "
                  f"about {eta:.0f} min left)", flush=True)

    print(f"\nDone in {(time.time() - t0) / 60:.0f} min. Fetched {done - len(failed) - len(missing)}, "
          f"no release {len(missing)}, failed {len(failed)}.")
    if missing:
        print("No release: " + ", ".join(str(d) for d in sorted(missing)))
    if failed:
        print("Failed (rerun to retry): " + ", ".join(str(d) for d in sorted(failed)))


if __name__ == "__main__":
    main()
