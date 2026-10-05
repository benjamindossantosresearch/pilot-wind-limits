"""
poh.py

POH values per aircraft (max demonstrated crosswind, approach speed with
landing flaps, VSO) from reference/poh_types.csv, sourced in
notes/poh_sources/all_types_report.md. Rows are matched in file order: first
row whose designator matches, whose model_regex (if any) matches the FAA
registry model, and whose year range (if any) holds the year built.

    rec = poh.lookup("C172", "172S", 2004)
    rec["xwind_kt"], rec["xwind_basis"], rec["approach_kias"]

xwind_basis is "published" (the type's own POH gives the value) or "assumed"
(no published value for that model, family value used). Q1b counts only
published values in the primary analysis.
"""

import csv
import os
import re

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference", "poh_types.csv")
_ROWS = None


def _rows():
    global _ROWS
    if _ROWS is None:
        _ROWS = []
        for r in csv.DictReader(open(PATH)):
            r["xwind_kt"] = float(r["xwind_kt"])
            r["approach_kias"] = float(r["approach_kias"]) if r["approach_kias"] else None
            r["vso_kias"] = float(r["vso_kias"]) if r["vso_kias"] else None
            r["year_min"] = int(r["year_min"]) if r["year_min"] else None
            r["year_max"] = int(r["year_max"]) if r["year_max"] else None
            r["rx"] = re.compile(r["model_regex"]) if r["model_regex"] else None
            _ROWS.append(r)
    return _ROWS


def lookup(designator, model="", year=None):
    model = (model or "").strip().upper()
    for r in _rows():
        if r["designator"] != designator:
            continue
        if r["rx"] and not r["rx"].search(model):
            continue
        if year and r["year_min"] and year < r["year_min"]:
            continue
        if year and r["year_max"] and year > r["year_max"]:
            continue
        if not year and (r["year_min"] or r["year_max"]):
            continue
        return r
    return None
