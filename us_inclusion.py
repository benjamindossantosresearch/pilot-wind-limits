"""
us_inclusion.py

Airport-month and day inclusion for the US confirmatory sample, as locked in
notes/decisions.md (2026-10-02, "LOCKED before any US-wide data is analyzed"):

  * an airport-month enters when its share of fixed-wing airport-traffic visits
    seen to 300 ft (us_pipeline.py coverage) is at least 0.60 that month
  * outage days: days whose coverage to 300 ft is below half of the airport's
    median across included months, excluded and counted
  * runway ends under 2,500 ft or unpaved are not counted as available for the
    best-runway crosswind

    import us_inclusion as ui
    inc = ui.load()
    inc.month_ok("BDR", "2026-03"), inc.day_ok("BDR", "2026-03-14"), inc.usable_ends("BDR")
"""

import csv
import glob
import io
import json
import os
import statistics
import zipfile
from collections import defaultdict

import runway_use as ru
import us_airports as ua

DAILY = "us_daily"
MIN_MONTH_SHARE = 0.60
OUTAGE_FRACTION = 0.5
MIN_RWY_FT = 2500
PAVED = ("ASPH", "CONC", "PEM", "BITU")
NASR_APT = "reference/nasr/01_Oct_2026_APT_CSV.zip"
_INC = None
# Known runway closures that change which runways are available (data correction, same as New England):
# PYM 06/24 closed from 2026-08-03, then the whole airport 2026-09-21 to 10-01 (notes/decisions.md).
CLOSED_FROM = {"PYM": "2026-08-03"}


class Inclusion:
    def __init__(self):
        self.cov_day = defaultdict(dict)         # airport -> utc day -> (fw_ops, fw_seen)
        self.days_present = set()
        self.counts = []                          # (airport, local_date, hour, piston, fleet, private, all_fixed)
        for path in sorted(glob.glob(os.path.join(DAILY, "*.json"))):
            d = json.load(open(path))
            self.days_present.add(d["day"])
            for a, (fo, fs, ao, as_) in d["coverage"].items():
                self.cov_day[a][d["day"]] = (fo, fs)
            self.counts.extend(tuple(r) for r in d["counts"])
        self.months = {}
        for a, days in self.cov_day.items():
            m = defaultdict(lambda: [0, 0])
            for day, (fo, fs) in days.items():
                m[day[:7]][0] += fo
                m[day[:7]][1] += fs
            self.months[a] = {mo: (fs / fo if fo else 0.0, fo) for mo, (fo, fs) in m.items()}
        self.outage = defaultdict(set)
        for a, days in self.cov_day.items():
            shares = [fs / fo for day, (fo, fs) in days.items() if fo and self.month_ok(a, day[:7])]
            if not shares:
                continue
            med = statistics.median(shares)
            for day, (fo, fs) in days.items():
                if self.month_ok(a, day[:7]) and (fo == 0 or fs / fo < OUTAGE_FRACTION * med):
                    self.outage[a].add(day)
        self._ends = None

    def month_ok(self, a, month):
        v = self.months.get(a, {}).get(month)
        return bool(v) and v[1] > 0 and v[0] >= MIN_MONTH_SHARE

    def day_ok(self, a, utc_day):
        if a in CLOSED_FROM and utc_day >= CLOSED_FROM[a]:
            return False
        return utc_day in self.days_present and self.month_ok(a, utc_day[:7]) and utc_day not in self.outage.get(a, set())

    def included_airports(self):
        return sorted(a for a, ms in self.months.items() if any(self.month_ok(a, m) for m in ms))

    def usable_ends(self, a):
        if self._ends is None:
            z = zipfile.ZipFile(NASR_APT)
            ok = set()
            for r in csv.DictReader(io.TextIOWrapper(z.open("APT_RWY.csv"), encoding="latin-1")):
                if (r["SURFACE_TYPE_CODE"] or "").startswith(PAVED) and r["RWY_LEN"] and float(r["RWY_LEN"]) >= MIN_RWY_FT:
                    ok.add((r["ARPT_ID"], r["RWY_ID"]))
            self._ends = ok
        site = ua.load()[a]
        keep = {rid for rid in site.apt.runways if (a, rid) in self._ends}
        return [e for e in ru.runway_ends(site.apt) if any(e.name in rid.split("/") for rid in keep)]

    def summary(self):
        inc = self.included_airports()
        n_months = sum(1 for a in self.months for m in self.months[a] if self.month_ok(a, m))
        return (f"{len(self.cov_day)} airports with traffic, {len(inc)} with at least one included month, "
                f"{n_months} included airport-months, {sum(len(v) for v in self.outage.values())} outage airport-days, "
                f"{len(self.days_present)} days processed")


def load():
    global _INC
    if _INC is None:
        _INC = Inclusion()
    return _INC
