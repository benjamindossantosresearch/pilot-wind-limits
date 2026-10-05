#!/usr/bin/env python3
"""
adsb_airport_coverage.py

Streams ADSB.lol daily globe_history archives, keeps low traffic inside a
regional box, and reports how low the archive's coverage reaches on approach
to one airport.

No disk needed for the raw archive (about 4 GB per day): each day is streamed
straight from GitHub, filtered in memory, and only the regional clip is kept.

Usage:
    python3 adsb_airport_coverage.py --airport KPYM --start 2026-09-07 --end 2026-09-20 --workers 4
    python3 adsb_airport_coverage.py --airport KPYM --last 3
    python3 adsb_airport_coverage.py --lat 41.67 --lon -70.96 --elev 79 --name KEWB --last 2

Regional cache:
    Each day is clipped once to a regional box (default se_new_england, below
    6,000 ft MSL) and cached in <cache>/<region>/YYYY-MM-DD.jsonl.gz, one
    clipped readsb trace per line with every raw field kept (squawk, callsign,
    category, IAS, roll, flags). Any airport inside the box reuses the same
    cache, so a KEWB or Taunton run over days already fetched for KPYM needs no
    download. Delete a day's cache file to redo it.

Outputs (in --out, default ./coverage_<airport>):
    points.csv     every trace point inside the airport geofence
    visits.csv     one row per aircraft visit with coverage stats
    summary.txt    headline coverage numbers plus a per-day breakdown
    baro_correction.csv  hourly baro-to-MSL correction and where it came from
    coverage.png   map, approach profile, and lowest-altitude histogram
                   (only if matplotlib is installed)

Data: ADSB.lol globe_history, Open Database License (ODbL 1.0).
Trace format: https://github.com/wiedehopf/readsb/blob/dev/README-json.md
"""

import argparse
import bisect
import csv
import datetime as dt
import glob
import gzip
import http.client
import io
import json
import math
import os
import statistics
import sys
import tarfile
import time
import urllib.request
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

# --------------------------------------------------------------------------
# Airport presets from FAA NASR (APT_BASE and APT_RWY_END, 2026-10-01 cycle).
# Runway coordinates are the physical runway ends (RWY_END lat/lon), not
# displaced thresholds. Displaced thresholds: KPYM 24 (300 ft),
# KEWB 23 (400 ft), KGHG 06 and 24 (300 ft each), KLWM 32 (80 ft),
# KOWD 10 (987 ft) and 28 (212 ft).
# geoid_offset_ft converts GNSS height above the WGS84 ellipsoid to MSL
# (MSL = HAE - N). N is about -28.5 m in southeastern Massachusetts.
# --------------------------------------------------------------------------
AIRPORTS = {
    "KPYM": {  # Plymouth Municipal, untowered, 29.96 nm from BOS ARP
        "lat": 41.90878833, "lon": -70.72762805, "elev_ft": 148.1,
        "geoid_offset_ft": 93.5,
        "runways": {
            "06/24": [(41.90423558, -70.7365183), (41.91407238, -70.72563955)],
            "15/33": [(41.91220105, -70.73009525), (41.90459336, -70.71778316)],
        },
    },
    "KEWB": {  # New Bedford Regional, towered, 41.27 nm from BOS ARP
        "lat": 41.67656611, "lon": -70.95783611, "elev_ft": 79.1,
        "geoid_offset_ft": 93.5,
        "runways": {
            "05/23": [(41.67126047, -70.96496772), (41.68286686, -70.95267838)],
            "14/32": [(41.68030019, -70.9639358), (41.67175708, -70.94960522)],
        },
    },
    "KLWM": {  # Lawrence Municipal, towered, 21.9 nm from BOS ARP
        "lat": 42.71704222, "lon": -71.12353333, "elev_ft": 147.6,
        "geoid_offset_ft": 93.5,
        "runways": {
            "05/23": [(42.7106893, -71.12912297), (42.72147608, -71.11762202)],
            "14/32": [(42.72098938, -71.12953744), (42.71572086, -71.11796813)],
        },
    },
    "KOWD": {  # Norwood Memorial, towered, 12.7 nm from BOS ARP
        "lat": 42.19052027, "lon": -71.17293083, "elev_ft": 49.2,
        "geoid_offset_ft": 93.5,
        "runways": {
            "10/28": [(42.19211094, -71.17850636), (42.19234672, -71.16376827)],
            "17/35": [(42.1937905, -71.17787066), (42.18384311, -71.17156708)],
        },
    },
    "KBED": {  # Laurence G. Hanscom Field, towered, 14.1 nm from BOS ARP
        "lat": 42.46994444, "lon": -71.289, "elev_ft": 132,
        "geoid_offset_ft": 93.5,
        "runways": {
            "05/23": [(42.46343577, -71.29686813), (42.47460861, -71.28544269)],
            "11/29": [(42.47182372, -71.30034297), (42.46943597, -71.27455988)],
        },
    },
    "KGHG": {  # Marshfield Municipal, untowered, 21.76 nm from BOS ARP
        "lat": 42.09749883, "lon": -70.67301986, "elev_ft": 8.9,
        "geoid_offset_ft": 93.5,
        "runways": {
            "06/24": [(42.09378719, -70.67819563), (42.10121047, -70.66784408)],
        },
    },
    "KTAN": {  # Taunton Municipal, untowered, 29.35 nm from BOS ARP
        "lat": 41.87408027, "lon": -71.01523277, "elev_ft": 41.3,
        "geoid_offset_ft": 93.5,
        "runways": {
            "04/22": [(41.87755644, -71.02128111), (41.88009533, -71.01958422)],  # turf, 1,034 ft
            "12/30": [(41.87413547, -71.01981683), (41.87121986, -71.00757544)],
        },
    },
}

# Regional cache boxes. Every airport geofence inside a box is served from the
# same per-day cache. Changing a box means starting a new cache directory.
REGIONS = {
    # All six New England states. The southern edge (41.0 N) leaves out the New
    # York metro area to keep the text prefilter selective. Bridgeport, Groton,
    # Block Island, and Nantucket still fit with a 5 nm geofence.
    "new_england": {"lat": (41.0, 47.5), "lon": (-73.75, -66.9), "max_alt_ft": 6000},
    # Eastern Massachusetts, Rhode Island, southern New Hampshire, Cape and Islands.
    # Superseded by new_england (a strict subset of it), kept for the first 2026 cache.
    "se_new_england": {"lat": (41.0, 43.0), "lon": (-72.0, -69.5), "max_alt_ft": 6000},
}
DEFAULT_REGION = "new_england"

PREFERRED_URL = "https://raw.githubusercontent.com/adsblol/{repo}/main/PREFERRED_RELEASES.txt"
NM_PER_DEG_LAT = 60.0
FT_PER_NM = 6076.12

# Geofence and analysis thresholds
DEFAULT_RADIUS_NM = 5.0
MAX_ALT_FT_MSL = 4000          # ignore traffic above this near the field
VISIT_GAP_S = 300              # split an aircraft's day into visits on gaps longer than this
# A visit counts as airport traffic if, within OPS_ZONE_NM of a runway threshold and
# below OPS_AGL_FT, it is descending. This does not require low coverage, so
# approaches whose data drops out early still count against the coverage numbers.
OPS_ZONE_NM = 3.0
OPS_AGL_FT = 1500
OPS_DESCENT_FPM = -300
INTERVAL_ZONE_NM = 3.0         # sample-interval stats use consecutive points inside this radius ...
INTERVAL_ZONE_AGL = 1000       # ... and below this AGL
MIN_PAIRS_PER_HOUR = 20        # GNSS/baro pairs needed for an hourly altimeter estimate
WEATHER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather")
METAR_MAX_GAP_S = 90 * 60      # interpolate the altimeter between reports at most this far apart
METAR_NEAREST_S = 60 * 60      # otherwise use the nearest report within this window
BORROW_HOURS = 3               # thin hours borrow the nearest good hour up to this far away
ROTORCRAFT_CATEGORY = "A7"     # ADS-B emitter category for rotorcraft


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------
def to_xy_nm(lat, lon, lat0, lon0):
    """Flat-earth projection to nautical miles east/north of a reference point."""
    x = (lon - lon0) * NM_PER_DEG_LAT * math.cos(math.radians(lat0))
    y = (lat - lat0) * NM_PER_DEG_LAT
    return x, y


def point_segment_nm(px, py, ax, ay, bx, by):
    """Distance from point P to segment AB, plus distance from P to the nearer end."""
    abx, aby = bx - ax, by - ay
    t = ((px - ax) * abx + (py - ay) * aby) / (abx * abx + aby * aby)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * abx, ay + t * aby
    d_seg = math.hypot(px - cx, py - cy)
    d_end = min(math.hypot(px - ax, py - ay), math.hypot(px - bx, py - by))
    return d_seg, d_end


class Airport:
    def __init__(self, name, lat, lon, elev_ft, geoid_offset_ft, runways):
        self.name, self.lat, self.lon = name, lat, lon
        self.elev_ft, self.geoid_offset_ft = elev_ft, geoid_offset_ft
        self.runways = {
            rid: [to_xy_nm(a[0], a[1], lat, lon), to_xy_nm(b[0], b[1], lat, lon)]
            for rid, (a, b) in runways.items()
        }

    def distances(self, lat, lon):
        """Returns (dist to ARP, dist to nearest runway centerline, dist to nearest threshold) in nm."""
        x, y = to_xy_nm(lat, lon, self.lat, self.lon)
        d_arp = math.hypot(x, y)
        if not self.runways:
            return d_arp, d_arp, d_arp
        best_seg, best_end = float("inf"), float("inf")
        for (ax, ay), (bx, by) in self.runways.values():
            d_seg, d_end = point_segment_nm(x, y, ax, ay, bx, by)
            best_seg, best_end = min(best_seg, d_seg), min(best_end, d_end)
        return d_arp, best_seg, best_end


def geofence_box(apt, radius_nm):
    dlat = radius_nm / NM_PER_DEG_LAT
    dlon = radius_nm / (NM_PER_DEG_LAT * math.cos(math.radians(apt.lat)))
    return (apt.lat - dlat, apt.lat + dlat), (apt.lon - dlon, apt.lon + dlon)


def region_covers(region, apt, radius_nm):
    (la0, la1), (lo0, lo1) = geofence_box(apt, radius_nm)
    (ra0, ra1), (ro0, ro1) = region["lat"], region["lon"]
    return ra0 <= la0 and la1 <= ra1 and ro0 <= lo0 and lo1 <= ro1 and MAX_ALT_FT_MSL <= region["max_alt_ft"]


# --------------------------------------------------------------------------
# Archive access
# --------------------------------------------------------------------------
def release_urls_for(day):
    """Find the preferred release (prod or staging) for a date. Skips MLAT-only releases."""
    tag = f"v{day:%Y.%m.%d}-"
    for repo_year in (day.year, day.year + 1):
        repo = f"globe_history_{repo_year}"
        try:
            with urllib.request.urlopen(PREFERRED_URL.format(repo=repo), timeout=60) as r:
                lines = r.read().decode().splitlines()
        except Exception:
            continue
        for line in lines:
            if tag in line and "mlatonly" not in line:
                return [u.strip() for u in line.split(",") if u.strip()]
    return None


class ChainedHTTPStream(io.RawIOBase):
    """
    Reads several URLs back to back as one stream (the archive is a split tar).
    A dropped connection resumes from the same byte with a Range request, so a
    network hiccup late in a 2 GB part does not restart the whole day.
    """

    def __init__(self, urls, label="", retries=6):
        self.urls = list(urls)
        self.label, self.retries = label, retries
        self.resp = None
        self.part_offset = 0
        self.bytes_read = 0

    def readable(self):
        return True

    def _open(self):
        headers = {"User-Agent": "adsb-coverage-check"}
        if self.part_offset:
            headers["Range"] = f"bytes={self.part_offset}-"
        self.resp = urllib.request.urlopen(urllib.request.Request(self.urls[0], headers=headers), timeout=120)
        if self.part_offset and self.resp.status != 206:
            raise OSError(f"server ignored Range request (status {self.resp.status})")

    def _close(self):
        if self.resp is not None:
            try:
                self.resp.close()
            except Exception:
                pass
        self.resp = None

    def readinto(self, b):
        failures = 0
        while self.urls:
            try:
                if self.resp is None:
                    self._open()
                n = self.resp.readinto(b)
            except (OSError, http.client.HTTPException) as exc:
                failures += 1
                self._close()
                if failures > self.retries:
                    raise
                print(f"  {self.label} read error at {self.bytes_read / 1e9:.2f} GB ({exc!r}), "
                      f"resuming (try {failures}/{self.retries})", flush=True)
                time.sleep(5 * failures)
                continue
            if n:
                self.part_offset += n
                self.bytes_read += n
                return n
            self._close()
            self.urls.pop(0)
            self.part_offset = 0
        return 0


def coord_prefixes(lo, hi):
    """
    Byte prefixes that any JSON coordinate in [lo, hi] must start with. Uses
    tenths of a degree for small ranges and whole degrees for wide ones.
    int() truncates toward zero, which matches how negative numbers print.
    """
    if hi - lo < 1.0:
        a, b = sorted((int(lo * 10), int(hi * 10)))
        return [f",{v / 10:.1f}".encode() for v in range(a, b + 1)]
    a, b = sorted((int(lo), int(hi)))
    return [f",{v}.".encode() for v in range(a, b + 1)]


def iter_region_traces(urls, region, label=""):
    """Stream one day's tar and yield parsed trace JSON for aircraft that may enter the region box."""
    lat_pfx = coord_prefixes(*region["lat"])
    lon_pfx = coord_prefixes(*region["lon"])

    stream = ChainedHTTPStream(urls, label)
    buffered = io.BufferedReader(stream, buffer_size=8 * 1024 * 1024)
    stats = Counter()
    t0 = time.time()
    with tarfile.open(fileobj=buffered, mode="r|*") as tar:
        for member in tar:
            if not member.isfile() or "/traces/" not in member.name:
                continue
            stats["trace_files"] += 1
            if stats["trace_files"] % 20000 == 0:
                mb = stream.bytes_read / 1e6
                print(f"  {label} {stats['trace_files']:,} traces, {mb:,.0f} MB, {time.time() - t0:,.0f}s", flush=True)
            raw = tar.extractfile(member).read()
            if raw[:2] == b"\x1f\x8b":
                try:
                    raw = gzip.decompress(raw)
                except (OSError, EOFError, zlib.error):
                    stats["bad_gzip"] += 1
                    continue
            # Cheap text prefilter before parsing JSON
            if not any(p in raw for p in lat_pfx) or not any(p in raw for p in lon_pfx):
                continue
            stats["candidates"] += 1
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                stats["bad_json"] += 1
    bad = f", {stats['bad_gzip']} bad gzip, {stats['bad_json']} bad json" if stats["bad_gzip"] or stats["bad_json"] else ""
    print(f"  {label} streamed {stats['trace_files']:,} trace files, {stats['candidates']:,} candidates, "
          f"{stream.bytes_read / 1e9:.2f} GB in {time.time() - t0:,.0f}s{bad}", flush=True)


def clip_trace(trace, region):
    """
    Keep the points of one trace inside the region box and below its altitude
    cap. The first point of each stretch inside the box inherits the last
    aircraft-details object seen before it, so squawk and callsign survive
    the clip.
    """
    (la0, la1), (lo0, lo1), cap = region["lat"], region["lon"], region["max_alt_ft"]
    kept, last_details, inside_prev = [], None, False
    for p in trace.get("trace", []):
        details = p[8] if len(p) > 8 and isinstance(p[8], dict) else None
        lat, lon, alt = p[1], p[2], p[3]
        geom = p[10] if len(p) > 10 else None
        ref = alt if isinstance(alt, (int, float)) else geom if isinstance(geom, (int, float)) else None
        inside = (lat is not None and lon is not None and la0 <= lat <= la1 and lo0 <= lon <= lo1
                  and (ref is None or ref <= cap))
        if inside:
            if details is None and not inside_prev and last_details is not None and len(p) > 8:
                p = list(p)
                p[8] = last_details
            kept.append(p)
        if details is not None:
            last_details = details
        inside_prev = inside
    if not kept:
        return None
    out = {k: v for k, v in trace.items() if k != "trace"}
    out["trace"] = kept
    return out


# --------------------------------------------------------------------------
# Point extraction
# --------------------------------------------------------------------------
def extract_points(trace, apt, radius_nm):
    """Yield dicts for trace points inside the airport geofence."""
    base = trace.get("timestamp", 0)
    icao = trace.get("icao", "")
    reg, actype = trace.get("r", ""), trace.get("t", "")
    db_flags = trace.get("dbFlags", 0) or 0
    squawk = flight = category = ""
    nacp = gva = nav_modes = nav_qnh = None
    # 4,000 ft MSL near the field, raised for high airports so their pattern is kept
    # (unchanged for every airport below 500 ft, which includes all of New England)
    alt_cap = max(MAX_ALT_FT_MSL, apt.elev_ft + 3500)
    for p in trace.get("trace", []):
        details = p[8] if len(p) > 8 and isinstance(p[8], dict) else {}
        # Carry the last known squawk, callsign, and category forward
        squawk = details.get("squawk", squawk) or squawk
        flight = (details.get("flight") or flight).strip()
        category = details.get("category", category) or category
        # Accuracy and autopilot fields (sent every few points), carried forward the same way
        nacp = details.get("nac_p", nacp)
        gva = details.get("gva", gva)
        nav_qnh = details.get("nav_qnh", nav_qnh)
        if "nav_modes" in details:
            nav_modes = "|".join(details["nav_modes"] or [])
        lat, lon = p[1], p[2]
        if lat is None or lon is None:
            continue
        # cheap distance check first: most points of a trace are far from this airport
        x, y = to_xy_nm(lat, lon, apt.lat, apt.lon)
        if x * x + y * y > radius_nm * radius_nm:
            continue
        d_arp, d_rwy, d_thr = apt.distances(lat, lon)
        if d_arp > radius_nm:
            continue
        alt = p[3]
        flags = p[6] if len(p) > 6 and isinstance(p[6], int) else 0
        on_ground = alt == "ground"
        baro = geom = None
        if isinstance(alt, (int, float)):
            if flags & 8:      # altitude field is geometric, not barometric
                geom = alt
            else:
                baro = alt
        if len(p) > 10 and isinstance(p[10], (int, float)):
            geom = p[10]
        ref = baro if baro is not None else geom
        if ref is not None and ref > alt_cap:
            continue
        yield {
            "icao": icao,
            "reg": reg or details.get("r", ""),
            "type": actype or details.get("t", ""),
            "db_flags": db_flags,
            "squawk": squawk, "flight": flight, "category": category,
            "t": base + p[0],
            "lat": lat, "lon": lon,
            "baro_ft": baro, "geom_ft": geom,
            "on_ground": on_ground,
            "gs_kt": p[4] if len(p) > 4 else None,
            "track": p[5] if len(p) > 5 else None,
            "vrate_fpm": p[7] if len(p) > 7 else None,
            "source": p[9] if len(p) > 9 else None,
            "geom_rate_fpm": p[11] if len(p) > 11 else None,
            "ias_kt": p[12] if len(p) > 12 else None,
            "roll_deg": p[13] if len(p) > 13 else None,
            "stale": bool(flags & 1),
            "new_leg": bool(flags & 2),
            "nac_p": nacp, "gva": gva, "nav_modes": nav_modes, "nav_qnh": nav_qnh,
            "dist_arp_nm": d_arp, "dist_rwy_nm": d_rwy, "dist_thr_nm": d_thr,
        }


_METAR_CACHE = {}


def metar_station(apt):
    """IEM station id for an airport preset name (KPYM -> PYM)."""
    return apt.name[1:] if len(apt.name) == 4 and apt.name.startswith("K") else apt.name


def load_metar_obs(station, weather_dir=WEATHER_DIR):
    """
    Altimeter (inHg) and temperature (C) reports for a station from every
    weather/<STATION>_metar_*.csv (IEM asos.py exports), merged, one per time,
    sorted. Cached per process.
    """
    key = (station, weather_dir)
    if key not in _METAR_CACHE:
        obs = {}
        for path in sorted(glob.glob(os.path.join(weather_dir, f"{station}_metar_*.csv"))):
            with open(path) as f:
                for r in csv.DictReader(f):
                    if r.get("alti") in (None, "", "M"):
                        continue
                    t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp()
                    tc = (float(r["tmpf"]) - 32) / 1.8 if r.get("tmpf") not in (None, "", "M") else None
                    obs[t] = (float(r["alti"]), tc)
        times = sorted(obs)
        _METAR_CACHE[key] = (times, [obs[t] for t in times])
    return _METAR_CACHE[key]


def metar_at(obs, t):
    """
    (altimeter inHg, temperature C or None) at epoch t. The altimeter is
    interpolated between the reports on either side when they are at most
    METAR_MAX_GAP_S apart, otherwise the nearest report within METAR_NEAREST_S
    is used. None when no report is close enough.
    """
    times, vals = obs
    if not times:
        return None
    i = bisect.bisect_left(times, t)
    lo = i - 1 if i > 0 else None
    hi = i if i < len(times) else None
    if lo is not None and hi is not None and times[hi] - times[lo] <= METAR_MAX_GAP_S:
        span = times[hi] - times[lo]
        f = (t - times[lo]) / span if span else 0.0
        alti = vals[lo][0] + f * (vals[hi][0] - vals[lo][0])
        near, far = (lo, hi) if t - times[lo] <= times[hi] - t else (hi, lo)
        temp = vals[near][1] if vals[near][1] is not None else vals[far][1]
        return alti, temp
    cands = [j for j in (lo, hi) if j is not None and abs(times[j] - t) <= METAR_NEAREST_S]
    if not cands:
        return None
    return vals[min(cands, key=lambda j: abs(times[j] - t))]


def indicated_alt_ft(pressure_alt_ft, altimeter_inhg):
    """What an altimeter set to altimeter_inhg reads at this pressure altitude (standard atmosphere)."""
    k, e, p0 = 145366.45, 0.190284, 29.92126
    return k * (1 - (1 - pressure_alt_ft / k) * (p0 / altimeter_inhg) ** e)


def temperature_ratio(temp_c, elev_ft):
    """
    True height above the field per indicated foot: surface temperature over
    the standard temperature at field elevation, both in kelvin. Assumes the
    temperature deviation holds with height (the usual cold-temperature
    correction). 1.0 when the temperature is missing.
    """
    if temp_c is None:
        return 1.0
    return (temp_c + 273.15) / (288.15 - 0.0019812 * elev_ft)


def estimate_agl(points, apt, method="metar"):
    """
    Height above the field for every point. Sets p["agl_ft"] (true height),
    p["agl_ind_ft"] (what the pilot's altimeter showed above field elevation,
    METAR method only), p["agl_gnss_ft"] (the GNSS/baro method below), and
    p["agl_method"] ("metar", "gnss", "geom", or "ground").

    method="metar" (default): pressure altitude converted with the airport's
    METAR altimeter setting (interpolated in time) gives the indicated height
    above the field, and the cold-temperature correction from the METAR
    temperature gives the true height. The altimeter setting is exact at field
    elevation, so this has no seasonal bias near the ground. Points with no
    METAR within reach fall back to the GNSS/baro method.

    method="gnss": the original estimate, kept to reproduce earlier results.
    The GNSS/baro method below reads aircraft near the ground 50 to 100 ft low
    in cold months (notes/decisions.md, 2026-10-01).

    Returns (per-UTC-day GNSS medians, overall GNSS median, hourly GNSS table).
    """
    result = _estimate_agl_gnss(points, apt)
    for p in points:
        p["agl_gnss_ft"] = p["agl_ft"]
        p["agl_ind_ft"] = None
        p["agl_method"] = ("ground" if p["on_ground"] else "gnss" if p["baro_ft"] is not None
                           else "geom" if p["geom_ft"] is not None else None)
    if method == "metar":
        obs = load_metar_obs(metar_station(apt))
        for p in points:
            if p["on_ground"] or p["baro_ft"] is None:
                continue
            m = metar_at(obs, p["t"])
            if m is None:
                continue
            ind = indicated_alt_ft(p["baro_ft"], m[0]) - apt.elev_ft
            p["agl_ind_ft"] = ind
            p["agl_ft"] = ind * temperature_ratio(m[1], apt.elev_ft)
            p["agl_method"] = "metar"
    return result


def _estimate_agl_gnss(points, apt):
    """
    Barometric altitude is pressure altitude (29.92 datum). Correct it per hour
    using aircraft that report both baro and GNSS altitude:
        correction = median(geom_msl - baro)
    This approximates the local altimeter setting without needing METARs.
    Hours with too few pairs borrow the nearest good hour (up to BORROW_HOURS
    away), then fall back to that UTC day's median, then the overall median.
    Returns (per-UTC-day medians, overall median, hourly table). The hourly
    table lists every hour that has points, with its pair count, the correction
    applied, and where that correction came from.
    """
    by_hour = defaultdict(list)
    for p in points:
        if p["baro_ft"] is not None and p["geom_ft"] is not None:
            by_hour[int(p["t"] // 3600)].append(p["geom_ft"] + apt.geoid_offset_ft - p["baro_ft"])
    good = {h: statistics.median(v) for h, v in by_hour.items() if len(v) >= MIN_PAIRS_PER_HOUR}
    by_day = defaultdict(list)
    for h, v in by_hour.items():
        by_day[h // 24].extend(v)
    day_med = {d: statistics.median(v) for d, v in by_day.items()}
    all_diffs = [d for v in by_hour.values() for d in v]
    overall = statistics.median(all_diffs) if all_diffs else 0.0

    cache = {}

    def corr_for(h):
        """Returns (correction ft, source) for an epoch hour."""
        if h not in cache:
            if h in good:
                cache[h] = (good[h], "hour")
            else:
                near = next((good[hh] for k in range(1, BORROW_HOURS + 1)
                             for hh in (h - k, h + k) if hh in good), None)
                if near is not None:
                    cache[h] = (near, "borrowed")
                elif h // 24 in day_med:
                    cache[h] = (day_med[h // 24], "day")
                else:
                    cache[h] = (overall, "overall")
        return cache[h]

    for p in points:
        h = int(p["t"] // 3600)
        corr_for(h)
        if p["on_ground"]:
            p["agl_ft"] = 0.0
        elif p["baro_ft"] is not None:
            p["agl_ft"] = p["baro_ft"] + cache[h][0] - apt.elev_ft
        elif p["geom_ft"] is not None:
            p["agl_ft"] = p["geom_ft"] + apt.geoid_offset_ft - apt.elev_ft
        else:
            p["agl_ft"] = None
    day_corr = {dt.datetime.fromtimestamp(d * 86400, dt.timezone.utc).date().isoformat(): m
                for d, m in day_med.items()}
    hourly = [{"hour_utc": dt.datetime.fromtimestamp(h * 3600, dt.timezone.utc).isoformat(timespec="minutes"),
               "n_pairs": len(by_hour.get(h, [])),
               "corr_ft": round(c, 1), "source": src}
              for h, (c, src) in sorted(cache.items())]
    return day_corr, overall, hourly


def prepare_cache(cache_root, region_name):
    """Create <cache_root>/<region_name> and check its region.json matches the box in REGIONS."""
    cache_dir = os.path.join(cache_root, region_name)
    os.makedirs(cache_dir, exist_ok=True)
    meta_path = os.path.join(cache_dir, "region.json")
    meta = {"region": region_name, **REGIONS[region_name]}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            if json.load(f) != json.loads(json.dumps(meta)):
                sys.exit(f"{meta_path} describes a different box. Use a new --cache directory.")
    else:
        with open(meta_path, "w") as f:
            json.dump(meta, f)
    return cache_dir


def cache_day(day, region, cache_dir):
    """
    Stream one archive day, clip it to the region, and write the cache file.
    Returns (day, ok, status). Runs in a worker process.
    """
    label = f"[{day}]"
    path = os.path.join(cache_dir, f"{day}.jsonl.gz")
    if os.path.exists(path):
        return day, True, "cached"
    urls = release_urls_for(day)
    if not urls:
        return day, False, "no release found (archive may lag a day or two)"

    print(f"  {label} streaming {len(urls)} part(s)", flush=True)
    for attempt in range(3):
        tmp = f"{path}.tmp{os.getpid()}"
        try:
            n_ac = 0
            with gzip.open(tmp, "wt", compresslevel=6) as f:
                for trace in iter_region_traces(urls, region, label):
                    clipped = clip_trace(trace, region)
                    if clipped is None:
                        continue
                    f.write(json.dumps(clipped, separators=(",", ":")) + "\n")
                    n_ac += 1
            os.replace(tmp, path)
            return day, True, f"ok ({n_ac:,} aircraft in region, {os.path.getsize(path) / 1e6:.1f} MB)"
        except Exception as exc:
            print(f"  {label} attempt {attempt + 1} failed: {exc!r}", flush=True)
            if os.path.exists(tmp):
                os.remove(tmp)
            time.sleep(15)
    return day, False, "failed after 3 attempts"


def process_day(day, apt, radius_nm, region, cache_dir):
    """
    Return one day's points inside the airport geofence, fetching the day into
    the regional cache first if it is missing. Runs in a worker process.
    """
    path = os.path.join(cache_dir, f"{day}.jsonl.gz")
    note = "cached"
    if not os.path.exists(path):
        day, ok, note = cache_day(day, region, cache_dir)
        if not ok:
            return day, None, note
    pts = []
    with gzip.open(path, "rt") as f:
        for line in f:
            pts.extend(extract_points(json.loads(line), apt, radius_nm))
    return day, pts, f"{note} ({len(pts):,} points near {apt.name})"


# --------------------------------------------------------------------------
# Visits and summary
# --------------------------------------------------------------------------
def build_visits(points):
    by_ac = defaultdict(list)
    for p in points:
        by_ac[p["icao"]].append(p)
    visits = []
    for icao, pts in by_ac.items():
        pts.sort(key=lambda q: q["t"])
        cur = [pts[0]]
        for q in pts[1:]:
            if q["t"] == cur[-1]["t"]:
                continue  # duplicate point (for example from overlapping day files)
            if q["t"] - cur[-1]["t"] > VISIT_GAP_S:
                visits.append(cur)
                cur = [q]
            else:
                cur.append(q)
        visits.append(cur)
    return visits


def in_interval_zone(p):
    return p["agl_ft"] is not None and p["dist_arp_nm"] <= INTERVAL_ZONE_NM and p["agl_ft"] <= INTERVAL_ZONE_AGL


def summarize_visit(v):
    agls = [p["agl_ft"] for p in v if p["agl_ft"] is not None]
    low = min(agls) if agls else None
    low_pt = min((p for p in v if p["agl_ft"] is not None), key=lambda p: p["agl_ft"], default=None)
    # Gaps only between consecutive points that are both in the zone. Time spent
    # climbing out above the zone between pattern circuits is not a sample gap.
    zone = [in_interval_zone(p) for p in v]
    gaps = [b["t"] - a["t"] for a, b, za, zb in zip(v, v[1:], zone, zone[1:]) if za and zb]
    approach = [p for p in v if p["agl_ft"] is not None
                and p["dist_thr_nm"] <= OPS_ZONE_NM and p["agl_ft"] <= OPS_AGL_FT]
    descending = any(isinstance(p["vrate_fpm"], (int, float)) and p["vrate_fpm"] <= OPS_DESCENT_FPM
                     for p in approach)
    if approach and not descending:
        descending = approach[0]["agl_ft"] - min(p["agl_ft"] for p in approach) >= 300
    is_ops = bool(approach) and descending
    return {
        "icao": v[0]["icao"], "reg": v[0]["reg"], "type": v[0]["type"],
        "flight": next((p["flight"] for p in v if p["flight"]), ""),
        "squawk": next((p["squawk"] for p in v if p["squawk"]), ""),
        "category": next((p["category"] for p in v if p["category"]), ""),
        "start_utc": dt.datetime.fromtimestamp(v[0]["t"], dt.timezone.utc).isoformat(timespec="seconds"),
        "duration_s": round(v[-1]["t"] - v[0]["t"]),
        "n_points": len(v),
        "airport_ops": is_ops,
        "lowest_agl_ft": round(low) if low is not None else "",
        "ground_reports": sum(p["on_ground"] for p in v),
        "thr_dist_at_lowest_nm": round(low_pt["dist_thr_nm"], 2) if low_pt else "",
        "median_gap_low_s": round(statistics.median(gaps), 1) if gaps else "",
        "max_gap_low_s": round(max(gaps), 1) if gaps else "",
        "main_source": Counter(p["source"] for p in v).most_common(1)[0][0] or "",
        "sources": "|".join(f"{k}:{c}" for k, c in Counter(p["source"] for p in v).most_common()),
        "_gaps": gaps,
    }


def pct(n, d):
    return f"{100.0 * n / d:5.1f}%" if d else "  n/a"


def write_outputs(out_dir, apt, days, points, summaries, day_corr, overall_corr, hourly):
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "baro_correction.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["hour_utc", "n_pairs", "corr_ft", "source"])
        w.writeheader()
        w.writerows(hourly)

    pfields = ["icao", "reg", "type", "flight", "squawk", "category", "db_flags", "time_utc",
               "lat", "lon", "baro_ft", "geom_ft", "agl_ft", "agl_ind_ft", "agl_gnss_ft", "agl_method", "on_ground", "gs_kt", "ias_kt", "track",
               "roll_deg", "vrate_fpm", "geom_rate_fpm", "source", "stale", "new_leg",
               "dist_arp_nm", "dist_rwy_nm", "dist_thr_nm"]
    with open(os.path.join(out_dir, "points.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pfields, extrasaction="ignore")
        w.writeheader()
        for p in sorted(points, key=lambda q: (q["icao"], q["t"])):
            row = dict(p)
            row["time_utc"] = dt.datetime.fromtimestamp(p["t"], dt.timezone.utc).isoformat(timespec="seconds")
            for k in ("dist_arp_nm", "dist_rwy_nm", "dist_thr_nm"):
                row[k] = round(p[k], 3)
            for k in ("agl_ft", "agl_ind_ft", "agl_gnss_ft"):
                row[k] = round(p[k]) if p.get(k) is not None else ""
            w.writerow(row)

    vfields = [k for k in summaries[0] if not k.startswith("_")] if summaries else []
    with open(os.path.join(out_dir, "visits.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=vfields, extrasaction="ignore")
        w.writeheader()
        w.writerows(summaries)

    ops = [s for s in summaries if s["airport_ops"]]
    lows = [s["lowest_agl_ft"] for s in ops if s["lowest_agl_ft"] != ""]
    gaps = [g for s in ops for g in s["_gaps"]]
    src = Counter(p["source"] for p in points)
    n = len(ops)
    fw = [s_ for s_ in ops if s_["category"] != ROTORCRAFT_CATEGORY]
    by_src = defaultdict(list)
    for s_ in fw:
        by_src[s_["main_source"]].append(s_)

    def share300(group):
        ok = sum(1 for s_ in group if s_["lowest_agl_ft"] != "" and s_["lowest_agl_ft"] <= 300)
        return pct(ok, len(group))

    lines = [
        f"ADS-B archive coverage check: {apt.name}",
        f"Days: {', '.join(d.isoformat() for d in days)}",
        f"Geofence: {apt.radius} nm radius, below {MAX_ALT_FT_MSL} ft MSL",
        "",
        f"Points in geofence:          {len(points):,}",
        f"Aircraft (unique ICAO):      {len({p['icao'] for p in points}):,}",
        f"Visits:                      {len(summaries):,}",
        f"Airport-traffic visits:      {n:,}  (descending below {OPS_AGL_FT} ft AGL within {OPS_ZONE_NM} nm of a threshold)",
        "",
        "How low does coverage reach on airport-traffic visits?",
        f"  lowest point <= 1000 ft AGL: {pct(sum(x <= 1000 for x in lows), n)}",
        f"  lowest point <=  500 ft AGL: {pct(sum(x <= 500 for x in lows), n)}",
        f"  lowest point <=  300 ft AGL: {pct(sum(x <= 300 for x in lows), n)}   <- pilot-study Q2 criterion: 70%",
        f"  lowest point <=  100 ft AGL: {pct(sum(x <= 100 for x in lows), n)}",
        f"  any on-ground report:        {pct(sum(s['ground_reports'] > 0 for s in ops), n)}",
        f"  median lowest AGL:           {statistics.median(lows):.0f} ft" if lows else "  median lowest AGL: n/a",
        "",
        f"Fixed-wing only (excludes category {ROTORCRAFT_CATEGORY} rotorcraft), the paper's population:",
        f"  visits {len(fw):,}, lowest point <= 300 ft AGL: {share300(fw)}",
        "  by main position source (adsr = UAT rebroadcast by FAA ground stations):",
        *[f"    {k or 'unknown':16s} {len(g):5,} visits   <= 300 ft AGL: {share300(g)}"
          for k, g in sorted(by_src.items(), key=lambda kv: -len(kv[1]))],
        "",
        f"Sample spacing between consecutive points within {INTERVAL_ZONE_NM} nm and below {INTERVAL_ZONE_AGL} ft AGL:",
        f"  median gap: {statistics.median(gaps):.1f} s" if gaps else "  median gap: n/a",
        f"  90th pct:   {sorted(gaps)[int(0.9 * (len(gaps) - 1))]:.1f} s" if gaps else "  90th pct: n/a",
        "",
        "Position sources (all points):",
        *[f"  {k or 'unknown'}: {c:,}" for k, c in src.most_common()],
        "",
        "Height method (points): " + ", ".join(f"{k} {c:,}" for k, c in Counter(p.get("agl_method") for p in points).most_common()),
        f"Baro-to-MSL correction from GNSS/baro pairs (fallback): overall median {overall_corr:+.0f} ft",
        "  (roughly (altimeter - 29.92) x 925 plus a temperature term. Per-day values below,",
        "   hourly values in baro_correction.csv. Check with check_baro_vs_metar.py.)",
        "  hours by correction source: " + ", ".join(
            f"{k} {c}" for k, c in Counter(h["source"] for h in hourly).most_common()),
        "",
        "Per day (UTC dates):",
        "  date        aircraft  ops visits  fixed-wing  <=300 ft  ground  baro corr",
    ]
    by_day = defaultdict(list)
    for s_ in summaries:
        by_day[s_["start_utc"][:10]].append(s_)
    for d in sorted(set(by_day) | set(day_corr)):
        day_ops = [s_ for s_ in by_day[d] if s_["airport_ops"]]
        n300 = sum(1 for s_ in day_ops if s_["lowest_agl_ft"] != "" and s_["lowest_agl_ft"] <= 300)
        ngnd = sum(1 for s_ in day_ops if s_["ground_reports"] > 0)
        corr = f"{day_corr[d]:+6.0f} ft" if d in day_corr else "     n/a"
        n_fw = sum(1 for s_ in day_ops if s_["category"] != ROTORCRAFT_CATEGORY)
        lines.append(f"  {d}  {len({s_['icao'] for s_ in by_day[d]}):8d}  {len(day_ops):10d}  {n_fw:10d}  "
                     f"{pct(n300, len(day_ops))}  {pct(ngnd, len(day_ops))}  {corr}")
    text = "\n".join(lines)
    with open(os.path.join(out_dir, "summary.txt"), "w") as f:
        f.write(text + "\n")
    print("\n" + text)
    return ops


def make_plots(out_dir, apt, points, ops):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed, skipping plots")
        return

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.8))

    # 1. Map of low traffic colored by AGL
    ax = axes[0]
    low = [p for p in points if p["agl_ft"] is not None and p["agl_ft"] <= 2000 and p["dist_arp_nm"] <= 3]
    xs, ys = zip(*[to_xy_nm(p["lat"], p["lon"], apt.lat, apt.lon) for p in low]) if low else ([], [])
    sc = ax.scatter(xs, ys, c=[p["agl_ft"] for p in low], s=4, cmap="viridis_r", vmin=0, vmax=2000)
    for rid, ((ax0, ay0), (bx0, by0)) in apt.runways.items():
        ax.plot([ax0, bx0], [ay0, by0], "r-", lw=3)
        ax.text(bx0, by0, rid, color="red", fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlim(-3, 3)
    ax.set_ylim(-3, 3)
    ax.set_title(f"{apt.name}: points below 2,000 ft AGL within 3 nm")
    ax.set_xlabel("nm east")
    ax.set_ylabel("nm north")
    fig.colorbar(sc, ax=ax, label="ft AGL")

    # 2. Approach profile: AGL vs distance to nearest threshold
    ax = axes[1]
    prof = [p for p in points if p["agl_ft"] is not None and p["dist_thr_nm"] <= 4 and p["agl_ft"] <= 2500]
    ax.scatter([p["dist_thr_nm"] for p in prof], [p["agl_ft"] for p in prof], s=3, alpha=0.4)
    d = [0, 4]
    ax.plot(d, [x * FT_PER_NM * math.tan(math.radians(3)) for x in d], "k--", lw=1, label="3 deg path")
    ax.axhline(300, color="red", lw=1, ls=":", label="300 ft AGL")
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 2500)
    ax.set_xlabel("distance to nearest runway threshold (nm)")
    ax.set_ylabel("ft AGL")
    ax.set_title("Where the data runs out")
    ax.legend(loc="upper left")

    # 3. Lowest observed AGL per airport-traffic visit
    ax = axes[2]
    lows = [s["lowest_agl_ft"] for s in ops if s["lowest_agl_ft"] != ""]
    ax.hist(lows, bins=range(0, 1300, 50))
    ax.axvline(300, color="red", lw=1, ls=":")
    ax.set_xlabel("lowest observed ft AGL")
    ax.set_ylabel("visits")
    ax.set_title(f"Lowest point per visit (n={len(lows)})")

    fig.tight_layout()
    path = os.path.join(out_dir, "coverage.png")
    fig.savefig(path, dpi=130)
    print(f"plot: {path}")


# --------------------------------------------------------------------------
def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--airport", default="KPYM", help="preset name (KPYM, KEWB, KLWM, KOWD, KBED, KGHG, KTAN)")
    ap.add_argument("--name", help="label when using --lat/--lon")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--elev", type=float, help="field elevation ft MSL")
    ap.add_argument("--geoid-offset", type=float, default=93.5, help="ft to add to GNSS HAE to get MSL")
    ap.add_argument("--radius", type=float, default=DEFAULT_RADIUS_NM, help="geofence radius nm")
    ap.add_argument("--start", help="YYYY-MM-DD")
    ap.add_argument("--end", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--last", type=int, help="process the N most recent days (ending yesterday UTC)")
    ap.add_argument("--workers", type=int, default=1,
                    help="days processed in parallel (each uses about one CPU core and its own download)")
    ap.add_argument("--region", default=DEFAULT_REGION, choices=sorted(REGIONS),
                    help="regional cache box the airport must sit inside")
    ap.add_argument("--cache", default="adsb_cache", help="regional cache root directory")
    ap.add_argument("--out", help="output directory")
    return ap.parse_args()


def main():
    args = parse_args()
    if args.lat is not None and args.lon is not None:
        cfg = {"lat": args.lat, "lon": args.lon, "elev_ft": args.elev or 0,
               "geoid_offset_ft": args.geoid_offset, "runways": {}}
        name = args.name or "CUSTOM"
    else:
        name = args.airport.upper()
        if name not in AIRPORTS:
            sys.exit(f"Unknown preset {name}. Use --lat/--lon/--elev instead.")
        cfg = AIRPORTS[name]
    apt = Airport(name, cfg["lat"], cfg["lon"], cfg["elev_ft"], cfg["geoid_offset_ft"], cfg["runways"])
    apt.radius = args.radius

    region = REGIONS[args.region]
    if not region_covers(region, apt, args.radius):
        sys.exit(f"{apt.name} geofence ({args.radius} nm, {MAX_ALT_FT_MSL} ft) is not inside region "
                 f"{args.region}. Add a region to REGIONS.")

    if args.last:
        end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
        days = [end - dt.timedelta(days=i) for i in range(args.last)][::-1]
    elif args.start:
        s = dt.date.fromisoformat(args.start)
        e = dt.date.fromisoformat(args.end) if args.end else s
        days = [s + dt.timedelta(days=i) for i in range((e - s).days + 1)]
    else:
        sys.exit("Give --last N or --start/--end")

    out_dir = args.out or f"coverage_{apt.name}"
    cache_dir = prepare_cache(args.cache, args.region)

    print(f"{apt.name}: {len(days)} day(s), {days[0]} to {days[-1]}, {args.workers} worker(s), "
          f"cache {cache_dir}")
    points, done = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(process_day, d, apt, args.radius, region, cache_dir) for d in days]
        for fut in as_completed(futures):
            day, pts, status = fut.result()
            print(f"  [{day}] {status}", flush=True)
            if pts is not None:
                points.extend(pts)
                done.append(day)
    done.sort()

    if not points:
        sys.exit("No points found in the geofence.")

    day_corr, overall_corr, hourly = estimate_agl(points, apt)
    visits = build_visits(points)
    summaries = [summarize_visit(v) for v in visits]
    ops = write_outputs(out_dir, apt, done, points, summaries, day_corr, overall_corr, hourly)
    make_plots(out_dir, apt, points, ops)


if __name__ == "__main__":
    main()
