#!/usr/bin/env python3
"""Why 467 admitted airports become 441 in the revealed limit: per missing airport, included months, usable
runway ends, one-minute and METAR files, and VMC hours before the thin-cell rule."""
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import us_airports as ua  # noqa: E402
import us_inclusion as ui  # noqa: E402

inc = ui.load()
sites = ua.load()
adm = set(inc.included_airports())
q1a = {r["airport"] for r in csv.DictReader(open("q1a_us/hours.csv"))}
missing = sorted(adm - q1a)
print(f"admitted {len(adm)}, in Q1a hours {len(q1a)}, missing {len(missing)}")
arr = Counter()
for a, d, h, p, f, pr, al in inc.counts:
    if a in missing and inc.day_ok(a, d):
        arr[a] += p
for a in missing:
    months = sorted(m for m in inc.months.get(a, {}) if inc.month_ok(a, m))
    ends = inc.usable_ends(a)
    print(f"  {a}: {len(months)} included months ({months[0] if months else '-'} to {months[-1] if months else '-'}), usable ends {len(ends)}, "
          f"station {sites[a].station}, piston arrivals counted on included days {arr[a]}")
