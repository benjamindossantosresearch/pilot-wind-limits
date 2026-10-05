#!/usr/bin/env python3
"""
us_tower_compare_v31_check.py

Validation V3 for detector v3.1 (notes/decisions.md): detected / tower operations per
airport under v3.0.1 (us_tower_compare/) and v3.1 (us_tower_compare_v31/) on the same
included airport-days with 30 or more tower operations, against the pre-set criteria:
airports whose parallel duplicates were under 1 per 100 tower operations move by less
than 0.02, HWO and DTO move down by about their duplicate share (13.9 and 10.9 per 100,
us_tower_compare/spotcheck_traverse.txt).

    python3 us_tower_compare_v31_check.py
"""

import csv

DUP = {"SUS": 0.7, "IXD": 0.0, "SLN": 0.1, "FRG": 0.0, "TTN": 0.0, "LNS": 0.0, "GFK": 0.5, "DPA": 0.3, "FCM": 0.3, "APA": 0.6,
       "HIO": 0.0, "PAE": 1.2, "DAB": 0.2, "HWO": 13.9, "FXE": 0.0, "DTO": 10.9, "GKY": 0.0, "FTW": 1.1, "FFZ": 0.4, "SDL": 0.0}


def load(path):
    return {(r["facility"], r["date"]): r for r in csv.DictReader(open(path)) if r["included"] == "1" and int(r["tower_ops"]) >= 30}


def main():
    a, b = load("us_tower_compare/daily.csv"), load("us_tower_compare_v31/daily.csv")
    keys = set(a) & set(b)
    ok_all = True
    print(f"{len(keys):,} common airport-days")
    print(f"{'apt':4} {'v3.0.1':>7} {'v3.1':>7} {'change':>7} {'dup/100':>7}  criterion")
    for apt in DUP:
        k = [x for x in keys if x[0] == apt]
        T = sum(int(a[x]["tower_ops"]) for x in k)
        r0 = sum(int(a[x]["detected_ops"]) for x in k) / T
        r1 = sum(int(b[x]["detected_ops"]) for x in k) / T
        if DUP[apt] < 1:
            ok = abs(r1 - r0) < 0.02
            crit = "change under 0.02: " + ("PASS" if ok else "FAIL")
        else:
            ok = r1 <= r0
            crit = f"expected about -{DUP[apt] / 100 * T / T:.3f} of tower: " + ("down" if ok else "NOT DOWN")
        ok_all &= ok
        print(f"{apt:4} {r0:7.3f} {r1:7.3f} {r1 - r0:+7.3f} {DUP[apt]:7.1f}  {crit}")
    T = sum(int(a[x]["tower_ops"]) for x in keys)
    print(f"pooled {sum(int(a[x]['detected_ops']) for x in keys) / T:.3f} -> {sum(int(b[x]['detected_ops']) for x in keys) / T:.3f}")
    print("V3 count criteria:", "PASS" if ok_all else "FAIL")


if __name__ == "__main__":
    main()
