"""
us_airports.py

Airport objects, weather station ids, and local time zones for the US-wide
candidate airports (reference/us_candidates.csv). Geometry comes from FAA NASR
for every airport, New England included, so the confirmatory sample uses one
source throughout.

    import us_airports as ua
    A = ua.load()            # id -> Site(apt, station, tz, state, tower)
"""

import csv
from collections import namedtuple
from zoneinfo import ZoneInfo

import adsb_airport_coverage as cov
import rank_airports as ra

CANDIDATES = "reference/us_candidates.csv"
Site = namedtuple("Site", "id apt station tz state tower")
_SITES = None

EASTERN = {"CT", "DE", "DC", "GA", "ME", "MD", "MA", "NH", "NJ", "NY", "NC", "OH", "PA", "RI", "SC", "VT", "VA", "WV"}
CENTRAL = {"AL", "AR", "IL", "IA", "LA", "MN", "MS", "MO", "OK", "WI"}
MOUNTAIN = {"CO", "MT", "NM", "UT", "WY"}
PACIFIC = {"CA", "NV", "WA"}


def tz_name(state, lat, lon):
    """Local time zone from state, with longitude splits for the states that span two zones.
    The splits follow the zone boundaries closely enough for airport locations."""
    if state in EASTERN:
        return "America/New_York"
    if state in CENTRAL:
        return "America/Chicago"
    if state in MOUNTAIN:
        return "America/Denver"
    if state in PACIFIC:
        return "America/Los_Angeles"
    if state == "AZ":
        return "America/Phoenix"
    if state == "FL":
        return "America/Chicago" if lon < -85.0 else "America/New_York"
    if state == "IN":
        return "America/Chicago" if lon < -86.9 and (lat > 41.0 or lat < 38.4) else "America/New_York"
    if state == "KY":
        return "America/Chicago" if lon < -85.9 else "America/New_York"
    if state == "TN":
        return "America/New_York" if lon > -85.0 else "America/Chicago"
    if state == "MI":
        return "America/Chicago" if lon < -87.6 and lat > 45.0 else "America/New_York"
    if state == "TX":
        return "America/Denver" if lon < -104.9 else "America/Chicago"
    if state == "KS":
        return "America/Denver" if lon < -101.5 else "America/Chicago"
    if state == "NE":
        return "America/Denver" if lon < -100.5 else "America/Chicago"
    if state == "SD":
        return "America/Denver" if lon < -100.3 else "America/Chicago"
    if state == "ND":
        return "America/Denver" if lon < -101.0 and lat < 47.5 else "America/Chicago"
    if state == "ID":
        return "America/Los_Angeles" if lat > 45.5 else "America/Denver"
    if state == "OR":
        return "America/Denver" if lon > -117.5 and lat < 44.5 else "America/Los_Angeles"
    return "America/New_York"


def apt_name(aid):
    """Name used by adsb_airport_coverage (KXXX for three-letter ids), so metar_station() maps back to the id."""
    return "K" + aid if len(aid) == 3 and aid.isalpha() else aid


def load():
    global _SITES
    if _SITES is None:
        rows = list(csv.DictReader(open(CANDIDATES)))
        ids = {r["airport"] for r in rows}
        cands = {c["id"]: c for c in ra.load_candidates(ra.NASR_DEFAULT, ra.AWOS_DEFAULT, 0, 99999, ids)}
        sites = {}
        for r in rows:
            c = cands.get(r["airport"])
            if not c or not c["rwy_geom"]:
                continue
            apt = cov.Airport(apt_name(r["airport"]), c["lat"], c["lon"], c["elev_ft"], 93.5, c["rwy_geom"])
            apt.radius = cov.DEFAULT_RADIUS_NM
            sites[r["airport"]] = Site(r["airport"], apt, r["asos_id"], ZoneInfo(tz_name(r["state"], c["lat"], c["lon"])),
                                       r["state"], r["tower"])
        _SITES = sites
    return _SITES
