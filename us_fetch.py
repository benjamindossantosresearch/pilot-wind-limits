#!/usr/bin/env python3
"""
us_fetch.py

Builds the US-wide low-altitude cache for the confirmatory sample. Each
ADSB.lol archive day is streamed once (the same download as the New England
fill) and every trace is clipped to the airspace the analysis uses: points
within RADIUS_NM of a candidate airport (reference/us_candidates.csv) and no
higher than that airport's elevation plus ALT_ABOVE_FT. Everything else is
dropped. One file per day: adsb_cache/us_airports/YYYY-MM-DD.jsonl.gz, in the
same per-trace format as the regional caches, so the existing pipeline reads it.

    python3 us_fetch.py --start 2025-10-01 --end 2026-09-30 --workers 32
    python3 us_fetch.py --test 2026-09-15        # one day, timing and size

Days already cached are skipped. Days are fetched newest first.
"""

import argparse
import csv
import datetime as dt
import gzip
import io
import json
import math
import os
import tarfile
import time
import zlib
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import adsb_airport_coverage as cov

CANDIDATES = "reference/us_candidates.csv"
CACHE_DIR = "adsb_cache/us_airports"
RADIUS_NM = 5.5          # a little wider than the 5 nm analysis geofence
ALT_ABOVE_FT = 4500      # above field elevation (the analysis uses 3,500 above or 4,000 MSL)
CELL = 0.5               # degrees, spatial index cell
_INDEX = None


def load_index():
    """Grid cell -> list of (lat, lon, cos_lat, alt_cap) for airports whose clip circle reaches the cell."""
    global _INDEX
    if _INDEX is None:
        idx = defaultdict(list)
        for r in csv.DictReader(open(CANDIDATES)):
            lat, lon, elev = float(r["lat"]), float(r["lon"]), float(r["elev_ft"])
            c = math.cos(math.radians(lat))
            dlat = RADIUS_NM / 60.0
            dlon = RADIUS_NM / (60.0 * c)
            for i in range(math.floor((lat - dlat) / CELL), math.floor((lat + dlat) / CELL) + 1):
                for j in range(math.floor((lon - dlon) / CELL), math.floor((lon + dlon) / CELL) + 1):
                    idx[(i, j)].append((lat, lon, c, elev + ALT_ABOVE_FT))
        _INDEX = dict(idx)
    return _INDEX


def inside(lat, lon, ref):
    near = _INDEX.get((math.floor(lat / CELL), math.floor(lon / CELL)))
    if not near:
        return False
    r2 = RADIUS_NM * RADIUS_NM
    for alat, alon, c, cap in near:
        if ref is not None and ref > cap:
            continue
        dy = (lat - alat) * 60.0
        dx = (lon - alon) * 60.0 * c
        if dx * dx + dy * dy <= r2:
            return True
    return False


def clip_trace_us(trace):
    """Keep the points near a candidate airport and low enough. Same detail-carrying rule as cov.clip_trace."""
    pts = trace.get("trace", [])
    kept, last_details, inside_prev = [], None, False
    for p in pts:
        details = p[8] if len(p) > 8 and isinstance(p[8], dict) else None
        lat, lon, alt = p[1], p[2], p[3]
        if lat is None or lon is None:
            ins = False
        else:
            geom = p[10] if len(p) > 10 else None
            ref = alt if isinstance(alt, (int, float)) else geom if isinstance(geom, (int, float)) else None
            ins = (ref is None or ref < 16000) and inside(lat, lon, ref)
        if ins:
            if details is None and not inside_prev and last_details is not None and len(p) > 8:
                p = list(p)
                p[8] = last_details
            kept.append(p)
        if details is not None:
            last_details = details
        inside_prev = ins
    if not kept:
        return None
    out = {k: v for k, v in trace.items() if k != "trace"}
    out["trace"] = kept
    return out


def iter_all_traces(urls, label):
    stream = cov.ChainedHTTPStream(urls, label)
    buffered = io.BufferedReader(stream, buffer_size=8 * 1024 * 1024)
    n = bad = 0
    t0 = time.time()
    with tarfile.open(fileobj=buffered, mode="r|*") as tar:
        for member in tar:
            if not member.isfile() or "/traces/" not in member.name:
                continue
            raw = tar.extractfile(member).read()
            if raw[:2] == b"\x1f\x8b":
                try:
                    raw = gzip.decompress(raw)
                except (OSError, EOFError, zlib.error):
                    bad += 1
                    continue
            n += 1
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                bad += 1
    print(f"  {label} {n:,} traces, {stream.bytes_read / 1e9:.2f} GB in {time.time() - t0:,.0f}s" + (f", {bad} bad" if bad else ""), flush=True)


def cache_day_us(day):
    load_index()
    label = f"[{day}]"
    path = os.path.join(CACHE_DIR, f"{day}.jsonl.gz")
    if os.path.exists(path):
        return day, True, "cached"
    urls = cov.release_urls_for(day)
    if not urls:
        return day, False, "no release found"
    for attempt in range(3):
        tmp = f"{path}.tmp{os.getpid()}"
        try:
            n_ac = 0
            t0 = time.time()
            with gzip.open(tmp, "wt", compresslevel=6) as f:
                for trace in iter_all_traces(urls, label):
                    c = clip_trace_us(trace)
                    if c is None:
                        continue
                    f.write(json.dumps(c, separators=(",", ":")) + "\n")
                    n_ac += 1
            os.replace(tmp, path)
            return day, True, f"ok ({n_ac:,} aircraft, {os.path.getsize(path) / 1e6:.0f} MB, {time.time() - t0:,.0f}s)"
        except Exception as exc:
            print(f"  {label} attempt {attempt + 1} failed: {exc!r}", flush=True)
            if os.path.exists(tmp):
                os.remove(tmp)
            time.sleep(15)
    return day, False, "failed after 3 attempts"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--test", help="fetch one day and report")
    args = ap.parse_args()
    os.makedirs(CACHE_DIR, exist_ok=True)
    meta = os.path.join(CACHE_DIR, "region.json")
    if not os.path.exists(meta):
        json.dump({"region": "us_airports", "candidates": CANDIDATES, "radius_nm": RADIUS_NM, "alt_above_ft": ALT_ABOVE_FT}, open(meta, "w"))
    if args.test:
        print(cache_day_us(dt.date.fromisoformat(args.test)))
        return
    s, e = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    days = [e - dt.timedelta(days=i) for i in range((e - s).days + 1)]
    todo = [d for d in days if not os.path.exists(os.path.join(CACHE_DIR, f"{d}.jsonl.gz"))]
    print(f"us_airports: {len(days)} days, {len(todo)} to fetch with {args.workers} workers", flush=True)
    t0, done, failed = time.time(), 0, []
    with ProcessPoolExecutor(args.workers) as ex:
        futs = [ex.submit(cache_day_us, d) for d in todo]
        for fut in as_completed(futs):
            day, ok, status = fut.result()
            done += 1
            if not ok:
                failed.append(day)
            rate = done / max(time.time() - t0, 1) * 60
            print(f"  [{day}] {status}  ({done}/{len(todo)}, {rate:.2f} days/min)", flush=True)
    print(f"done in {(time.time() - t0) / 60:.0f} min, failed or missing: {', '.join(map(str, failed)) or 'none'}")


if __name__ == "__main__":
    main()
