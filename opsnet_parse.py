#!/usr/bin/env python3
"""
opsnet_parse.py

Converts FAA OPSNET / ATADS "Airport Operations: Standard Report" exports (HTML
tables saved with an .xls name) into one tidy CSV. The facility and date range
are read from each file's header, so file names do not matter. Reports that
combine several facilities keep them joined with "+" (LWM+OWD+BED+EWB).

    python3 opsnet_parse.py reference/opsnet/*.xls

Writes reference/opsnet/opsnet_daily.csv with one row per date and facility:
    date, facility, ifr_itin_{ac,at,ga,mil,total}, vfr_itin_{...}, itin_{...},
    local_civil, local_mil, local_total, total_ops
Rows for the same facility and date from several files are de-duplicated.
Empty files and files without a daily table are reported and skipped.
"""

import csv
import datetime as dt
import os
import re
import sys
from html.parser import HTMLParser

COLS = ["ifr_itin_ac", "ifr_itin_at", "ifr_itin_ga", "ifr_itin_mil", "ifr_itin_total",
        "vfr_itin_ac", "vfr_itin_at", "vfr_itin_ga", "vfr_itin_mil", "vfr_itin_total",
        "itin_ac", "itin_at", "itin_ga", "itin_mil", "itin_total",
        "local_civil", "local_mil", "local_total", "total_ops"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference", "opsnet", "opsnet_daily.csv")


class Cells(HTMLParser):
    """Collects the text of every table row as a list of cell strings."""

    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.row is not None and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def parse(path):
    text = open(path, encoding="latin-1").read()
    if not text.strip():
        return None, [], "empty file"
    m = re.search(r"Facility=([A-Z0-9, ]+)", text)
    if not m:
        return None, [], "no facility in header"
    facility = "+".join(x.strip() for x in m.group(1).split(",") if x.strip())
    p = Cells()
    p.feed(text)
    rows = []
    for r in p.rows:
        if len(r) != 1 + len(COLS) or not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", r[0]):
            continue
        mo, da, yr = (int(x) for x in r[0].split("/"))
        yr += 2000 if yr < 100 else 0
        vals = [int(x.replace(",", "")) if x.replace(",", "").isdigit() else 0 for x in r[1:]]
        rows.append({"date": dt.date(yr, mo, da).isoformat(), "facility": facility, **dict(zip(COLS, vals))})
    return facility, rows, f"{len(rows)} days"


def main():
    paths = sys.argv[1:]
    if not paths:
        sys.exit(__doc__)
    merged = {}
    for path in sorted(paths):
        facility, rows, note = parse(path)
        print(f"{os.path.basename(path)}: {facility or '-'} {note}"
              + (f", {rows[0]['date']} to {rows[-1]['date']}" if rows else ""))
        for r in rows:
            merged[(r["facility"], r["date"])] = r
    out = sorted(merged.values(), key=lambda r: (r["facility"], r["date"]))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "facility"] + COLS)
        w.writeheader()
        w.writerows(out)
    bad = [r for r in out if r["itin_total"] + r["local_total"] != r["total_ops"]]
    print(f"{OUT}: {len(out)} rows, facilities {sorted({r['facility'] for r in out})}, "
          f"{len(bad)} rows where itinerant + local != total")


if __name__ == "__main__":
    main()
