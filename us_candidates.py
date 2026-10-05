#!/usr/bin/env python3
"""
us_candidates.py

Candidate airports for the US-wide expansion (contiguous US). An airport is a
candidate if it is public use, has an ASOS (the one-minute wind archive covers
ASOS only, not AWOS), and has at least one paved runway of 2,500 ft or more.
Whether the ADS-B archive sees it well enough is decided later by the
coverage rule, the same as PYM and TAN.

    python3 us_candidates.py

Writes reference/us_candidates.csv: airport, name, state, lat, lon, elev_ft,
tower (NASR tower type), runways (paved, 2,500 ft or more), asos_id.
"""

import csv
import io
import zipfile

NASR_APT = "reference/nasr/01_Oct_2026_APT_CSV.zip"
NASR_AWOS = "reference/nasr/01_Oct_2026_AWOS_CSV.zip"
NOT_CONUS = {"AK", "HI", "PR", "VI", "GU", "AS", "MP", "UM", ""}
PAVED = ("ASPH", "CONC", "PEM", "BITU")
MIN_LEN = 2500
OUT = "reference/us_candidates.csv"


def rows(zpath, name):
    z = zipfile.ZipFile(zpath)
    return list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="latin-1")))


def main():
    base = {r["SITE_NO"]: r for r in rows(NASR_APT, "APT_BASE.csv")}
    rwys = {}
    for r in rows(NASR_APT, "APT_RWY.csv"):
        surf = r["SURFACE_TYPE_CODE"] or ""
        if any(surf.startswith(p) for p in PAVED) and r["RWY_LEN"] and float(r["RWY_LEN"]) >= MIN_LEN and "H" not in r["RWY_ID"]:
            rwys.setdefault(r["SITE_NO"], []).append(r["RWY_ID"])
    out, seen = [], set()
    for a in rows(NASR_AWOS, "AWOS.csv"):
        if a["ASOS_AWOS_TYPE"] != "ASOS":
            continue
        b = base.get(a["SITE_NO"])
        if not b or b["SITE_TYPE_CODE"] != "A" or b["FACILITY_USE_CODE"] != "PU" or b["STATE_CODE"] in NOT_CONUS:
            continue
        if a["SITE_NO"] not in rwys or b["ARPT_ID"] in seen:
            continue
        seen.add(b["ARPT_ID"])
        out.append({"airport": b["ARPT_ID"], "name": b.get("ARPT_NAME", ""), "state": b["STATE_CODE"],
                    "lat": float(b["LAT_DECIMAL"]), "lon": float(b["LONG_DECIMAL"]), "elev_ft": float(b["ELEV"] or 0),
                    "tower": b.get("TWR_TYPE_CODE", ""), "runways": "|".join(sorted(rwys[a["SITE_NO"]])),
                    "asos_id": a["ASOS_AWOS_ID"]})
    out.sort(key=lambda r: (r["state"], r["airport"]))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    towered = sum(1 for r in out if r["tower"].startswith("ATCT"))
    print(f"{len(out)} candidate airports in {len({r['state'] for r in out})} states, {towered} with a tower (ATCT types)")


if __name__ == "__main__":
    main()
