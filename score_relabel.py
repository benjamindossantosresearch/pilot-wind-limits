#!/usr/bin/env python3
"""
score_relabel.py

Intra-rater check (notes/decisions.md, 2026-10-03): Benjamin's second, blind labels of
30 visits (R01 to R30, labeling/relabel/) against his first labels of the same visits in
Sets 1 to 4, both unadjudicated. Also detector v3.1 against each labeling, for context.

    python3 score_relabel.py labeling/export_relabel_BD

The export folder holds labels/<rater>/visits/R##.json (ArtifactData list with out_dir).
"""

import csv
import glob
import json
import math
import os
import sys
from collections import Counter

import ops_detector as od
from score_labels import events_from_label, load_json

FIRST = {"Set 1": ("labeling/export_BD_raw_2026-10-01", "labeling/tracks.json"),
         "Set 2": ("labeling/export_heldout_BD", "labeling/heldout/tracks.json"),
         "Set 3": ("labeling/export_set3_BD_raw", "labeling/set3/tracks.json"),
         "Set 4": ("labeling/export_us_BD_raw", "labeling/us/tracks.json")}


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def labels_in(root):
    out = {}
    for p in glob.glob(os.path.join(root, "labels", "*", "visits", "*.json")):
        out[os.path.basename(p)[:-5]] = load_json(p)
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "labeling/export_relabel_BD"
    key = list(csv.DictReader(open("labeling/relabel/key.csv")))
    second = labels_in(root)
    first_by_set = {s: labels_in(r) for s, (r, _) in FIRST.items()}
    side = json.load(open("us_parallel/side_reliable.json"))["reliable"]
    rows = []
    for k in key:
        a, b = first_by_set[k["set"]].get(k["original_id"]), second.get(k["relabel_id"])
        if a is None or b is None:
            print(f"missing label: {k}")
            continue
        data = json.load(open(FIRST[k["set"]][1]))
        v = next(x for x in data["visits"] if x["id"] == k["original_id"])
        ends = od.ends_from_geometry(data["airports"][v["airport"]])
        det = Counter((p["kind"], p["runway"]) for p in od.detect(v, ends, set(side.get(v["airport"].lstrip("K") if len(v["airport"]) == 4 else v["airport"], []))))
        ea, eb = events_from_label(a), events_from_label(b)
        rows.append({"id": k["relabel_id"], "orig": k["original_id"], "set": k["set"], "a": ea, "b": eb, "det": det,
                     "sparse": bool(a.get("sparse") or b.get("sparse"))})
    for label, sel in (("all", rows), ("neither marked too little data", [r for r in rows if not r["sparse"]])):
        n = len(sel)
        same = sum(r["a"] == r["b"] for r in sel)
        arr = sum((sum(c for (kd, _), c in r["a"].items() if kd == "approach") > 0) == (sum(c for (kd, _), c in r["b"].items() if kd == "approach") > 0) for r in sel)
        napp = sum(sum(c for (kd, _), c in r["a"].items() if kd == "approach") == sum(c for (kd, _), c in r["b"].items() if kd == "approach") for r in sel)
        apps = lambda e: Counter({e2: c for (kd, e2), c in e.items() if kd == "approach"})
        rwy = sum(apps(r["a"]) == apps(r["b"]) for r in sel)
        d1 = sum(r["det"] == r["a"] for r in sel)
        d2 = sum(r["det"] == r["b"] for r in sel)
        lo, hi = wilson(same, n)
        print(f"{label}: {n} visits")
        print(f"  same events both times {same}/{n} ({100 * same / n:.0f}%, Wilson 95% {100 * lo:.0f} to {100 * hi:.0f}%)")
        print(f"  same arrival yes/no {arr}/{n}, same number of approaches {napp}/{n}, same approaches by runway {rwy}/{n}")
        print(f"  detector v3.1 matches first labels {d1}/{n}, second labels {d2}/{n}")
    print("\nDisagreements between the two labelings:")
    for r in rows:
        if r["a"] != r["b"]:
            print(f"  {r['id']} ({r['set']} {r['orig']}): first {dict(r['a'])}, second {dict(r['b'])}, detector {dict(r['det'])}")


if __name__ == "__main__":
    main()
