#!/usr/bin/env python3
"""
faa_registry.py

Builds an aircraft lookup keyed by ICAO (Mode S) hex address from the FAA
releasable aircraft database, and provides lookup(hex, date) for the analysis
scripts.

    python3 faa_registry.py reference/faa_registry/ReleasableAircraft_2026-10-01.zip

Writes reference/faa_registry/aircraft_registry.csv with one row per
registration record:
    current registrations (MASTER.txt), valid from the certificate issue date
    registrations canceled since 2023-01-01 (DEREG.txt), valid from the
        certificate issue date to the cancel date, so aircraft exported,
        destroyed, or re-registered since the archive began still resolve

Fields kept: model and engine data, registrant type, a derived ownership class,
and fleet size. Registrant names are kept only for fleet operators (organizations
holding three or more aircraft). Individual owners are never named.

Ownership classes (commercial marks scheduled operators listed in
COMMERCIAL_OPERATORS, out of scope for the study):
    trust        registered by a trust company for a non-citizen owner (names with
                 TRUSTEE or TRUST). The operator is unknown
    fleet        non-individual registrant (corporation, LLC, partnership,
                 government, non-citizen) holding FLEET_MIN or more aircraft.
                 Flight schools, clubs, rental operators, and agencies land here
    private      individual or co-owned, or a non-individual registrant with fewer
                 than FLEET_MIN aircraft (single-aircraft LLCs are usually a
                 private owner's holding company)
    unknown      canceled registrations (DEREG.txt has no registrant type)

Known limits: the FAA publishes only the current database, so a sale between the
flight date and today is invisible unless the registration was canceled. Rows
whose certificate was issued after the flight date are flagged by lookup().
Leasebacks (private aircraft rented out by a school) show as private.
"""

import csv
import datetime as dt
import io
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

OUT_DEFAULT = "reference/faa_registry/aircraft_registry.csv"
FLEET_MIN = 3
DEREG_SINCE = "20230101"
# Scheduled commercial operators are out of scope (fixed-wing piston GA only).
# Matched against the normalized registrant name. Hyannis Air Service is Cape Air.
COMMERCIAL_OPERATORS = ("HYANNIS AIR SERVICE",)

TYPE_REGISTRANT = {"1": "individual", "2": "partnership", "3": "corporation", "4": "co-owned",
                   "5": "government", "7": "llc", "8": "non-citizen corporation",
                   "9": "non-citizen co-owned"}
TYPE_AIRCRAFT = {"1": "glider", "2": "balloon", "3": "blimp", "4": "fixed wing single",
                 "5": "fixed wing multi", "6": "rotorcraft", "7": "weight-shift", "8": "powered parachute",
                 "9": "gyroplane", "H": "hybrid lift", "O": "other"}
TYPE_ENGINE = {"0": "none", "1": "reciprocating", "2": "turboprop", "3": "turboshaft", "4": "turbojet",
               "5": "turbofan", "6": "ramjet", "7": "2 cycle", "8": "4 cycle", "9": "unknown",
               "10": "electric", "11": "rotary"}
PISTON_ENGINES = {"1", "7", "8", "11"}
FIXED_WING = {"4", "5"}
FIELDS = ["icao_hex", "n_number", "source", "valid_from", "valid_to", "mfr", "model", "year_mfr",
          "type_aircraft", "type_engine", "n_engines", "n_seats", "weight_class", "piston_fixed_wing",
          "registrant_type", "ownership", "fleet_size", "operator", "state"]


def read_txt(z, name):
    with z.open(name) as f:
        r = csv.reader(io.TextIOWrapper(f, "utf-8-sig", errors="replace"))
        header = [h.strip() for h in next(r)]
        for row in r:
            yield dict(zip(header, (x.strip() for x in row)))


def norm_name(s):
    """Uppercase, punctuation removed, and any "DBA ..." trade-name suffix dropped."""
    s = re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", s.upper())).strip()
    return re.split(r"\bDBA\b", s)[0].strip()


def is_trust(name):
    return bool(re.search(r"\bTRUSTEE\b|\bTRUST\b|\bTR\b", norm_name(name)))


def build(zip_path, out_path):
    z = zipfile.ZipFile(zip_path)
    ref = {r["CODE"]: r for r in read_txt(z, "ACFTREF.txt")}
    master = list(read_txt(z, "MASTER.txt"))
    holdings = Counter(norm_name(r["NAME"]) for r in master if r["NAME"])

    def model_fields(code, type_acft=None, type_eng=None):
        a = ref.get(code, {})
        ta = type_acft or a.get("TYPE-ACFT", "")
        te = type_eng or a.get("TYPE-ENG", "")
        return {
            "mfr": a.get("MFR", ""), "model": a.get("MODEL", ""),
            "type_aircraft": TYPE_AIRCRAFT.get(ta, ta), "type_engine": TYPE_ENGINE.get(te, te),
            "n_engines": a.get("NO-ENG", ""), "n_seats": a.get("NO-SEATS", ""),
            "weight_class": a.get("AC-WEIGHT", "").replace("CLASS ", ""),
            "piston_fixed_wing": ta in FIXED_WING and te in PISTON_ENGINES,
        }

    rows = []
    for r in master:
        hexcode = r["MODE S CODE HEX"].lower()
        if not hexcode:
            continue
        rtype = r["TYPE REGISTRANT"]
        n_held = holdings.get(norm_name(r["NAME"]), 0)
        individual = rtype in ("1", "4")
        trust = not individual and is_trust(r["NAME"])
        fleet = not individual and not trust and n_held >= FLEET_MIN
        commercial = fleet and norm_name(r["NAME"]).startswith(COMMERCIAL_OPERATORS)
        rows.append({
            "icao_hex": hexcode, "n_number": "N" + r["N-NUMBER"], "source": "master",
            "valid_from": r["CERT ISSUE DATE"], "valid_to": "",
            **model_fields(r["MFR MDL CODE"], r["TYPE AIRCRAFT"], r["TYPE ENGINE"]),
            "year_mfr": r["YEAR MFR"],
            "registrant_type": TYPE_REGISTRANT.get(rtype, rtype),
            "ownership": "commercial" if commercial else "fleet" if fleet else "trust" if trust else "private",
            "fleet_size": n_held if fleet else "",
            "operator": norm_name(r["NAME"]) if fleet else "",
            "state": r["STATE"],
        })
    n_master = len(rows)

    for r in read_txt(z, "DEREG.txt"):
        hexcode = r.get("MODE S CODE HEX", "").lower()
        if not hexcode or r["CANCEL-DATE"] < DEREG_SINCE:
            continue
        rows.append({
            "icao_hex": hexcode, "n_number": "N" + r["N-NUMBER"], "source": "dereg",
            "valid_from": r["CERT-ISSUE-DATE"], "valid_to": r["CANCEL-DATE"],
            **model_fields(r["MFR-MDL-CODE"]),
            "year_mfr": r["YEAR-MFR"], "registrant_type": "", "ownership": "unknown",
            "fleet_size": "", "operator": "", "state": r["STATE-ABBREV-MAIL"],
        })

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    own = Counter(r["ownership"] for r in rows[:n_master])
    piston = sum(r["piston_fixed_wing"] for r in rows[:n_master])
    print(f"{out_path}: {n_master:,} current registrations, {len(rows) - n_master:,} canceled since 2023")
    print(f"  current: piston fixed-wing {piston:,}, ownership {dict(own)}")


_cache = {}


def load(path=OUT_DEFAULT):
    """Returns {hex: [record, ...]} with current records first."""
    if path not in _cache:
        by_hex = defaultdict(list)
        with open(path) as f:
            for r in csv.DictReader(f):
                r["piston_fixed_wing"] = r["piston_fixed_wing"] == "True"
                by_hex[r["icao_hex"]].append(r)
        _cache[path] = by_hex
    return _cache[path]


def lookup(hexcode, date, path=OUT_DEFAULT):
    """
    Registration record for an ICAO hex on a date (datetime.date or YYYY-MM-DD).
    Prefers the record whose validity covers the date. Falls back to the current
    record with registered_after=True when its certificate postdates the flight.
    Returns None for addresses not in the US registry (foreign, TIS-B, military).
    """
    recs = load(path).get(hexcode.lower().lstrip("~"))
    if not recs:
        return None
    d = (date.isoformat() if isinstance(date, dt.date) else date).replace("-", "")
    for r in recs:
        if (not r["valid_from"] or r["valid_from"] <= d) and (not r["valid_to"] or d <= r["valid_to"]):
            return {**r, "registered_after": False}
    current = next((r for r in recs if r["source"] == "master"), None)
    return {**current, "registered_after": True} if current else None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else OUT_DEFAULT)
