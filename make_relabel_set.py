#!/usr/bin/env python3
"""
make_relabel_set.py

Intra-rater check (notes/decisions.md, 2026-10-03): 30 visits drawn from labeling
Sets 1 to 4 (7, 7, 8, 8) with seed 20261003, given new IDs R01 to R30 in a new random
order so the labeling tool shows no earlier labels. The tracks are copied unchanged
from the files the tool served for each set.

    python3 make_relabel_set.py

Writes labeling/relabel/tracks.json (published as relabel.json) and
labeling/relabel/key.csv (not published: R id, original id, set).
"""

import csv
import json
import os
import random

SETS = [("Set 1", "labeling/tracks.json", 7), ("Set 2", "labeling/heldout/tracks.json", 7),
        ("Set 3", "labeling/set3/tracks.json", 8), ("Set 4", "labeling/us/tracks.json", 8)]
SEED = 20261003
OUT = "labeling/relabel"


def main():
    rng = random.Random(SEED)
    picked, airports = [], {}
    for name, path, n in SETS:
        d = json.load(open(path))
        for v in rng.sample(d["visits"], n):
            picked.append((name, v))
            airports[v["airport"]] = d["airports"][v["airport"]]
    rng.shuffle(picked)
    visits, key = [], []
    for k, (name, v) in enumerate(picked, 1):
        rid = f"R{k:02d}"
        key.append({"relabel_id": rid, "original_id": v["id"], "set": name})
        visits.append(dict(v, id=rid))
    os.makedirs(OUT, exist_ok=True)
    json.dump({"version": "relabel-1", "seed": SEED, "airports": airports, "visits": visits},
              open(os.path.join(OUT, "tracks.json"), "w"), separators=(",", ":"))
    with open(os.path.join(OUT, "key.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["relabel_id", "original_id", "set"])
        w.writeheader()
        w.writerows(key)
    print(f"{len(visits)} visits at {len(airports)} airports:", ", ".join(sorted(airports)))


if __name__ == "__main__":
    main()
