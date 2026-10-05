#!/usr/bin/env python3
"""
score_labels_v31.py

Validation V1 and V2 for detector v3.1 (rule 12, notes/decisions.md): visit
agreement of frozen v3.0.1 and current v3.1 against Benjamin's labels on every
labeled set, with the Set 4 adjudication (labeling/us/adjudication.csv) applied
for the adjudicated figure. Uses score_labels.py's label reading and agreement
unit (identical event sets per visit). v3.1 gets each airport's reliable
pattern sides from us_parallel/side_reliable.json.

    python3 score_labels_v31.py
"""

import glob
import importlib.util
import json
import os
from collections import Counter, defaultdict

import ops_detector as od31
from score_labels import events_from_label, load_json

SETS = [("Set 1 (development)", "labeling/export_BD_current", "labeling/tracks.json"),
        ("Set 2 (held-out)", "labeling/export_heldout_BD", "labeling/heldout/tracks.json"),
        ("Set 3", "labeling/export_set3_BD_raw", "labeling/set3/tracks.json"),
        ("Set 4 (US)", "labeling/export_us_BD_raw", "labeling/us/tracks.json")]
ADJ = {  # labeling/us/adjudication.csv, as confirmed by Benjamin 2026-10-02
    "U022": [("rename", None, "17", "18")],
    "U088": [("rename", None, "13", "19")],
    "U063": [("rename", "climb", "04L", "22R")],
    "U080": [("rename", "climb", "24R", "06L")],
    "U070": [("add", "climb", "36", 2)],
}


def load_v301():
    spec = importlib.util.spec_from_file_location("od301", "notes/ops_detector_v3.0.1_2026-10-02.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def adjudicate(vid, ev):
    ev = Counter(ev)
    for op, kind, a, b in ADJ.get(vid, []):
        if op == "rename":
            for k in list(ev):
                if k[1] == a and (kind is None or k[0] == kind):
                    ev[(k[0], b)] += ev.pop(k)
        else:
            ev[(kind, a)] += b
    return ev


def labels(root, visits):
    out = {}
    for vdir in glob.glob(os.path.join(root, "labels", "*", "visits")):
        for p in glob.glob(os.path.join(vdir, "*.json")):
            vid = os.path.basename(p)[:-5]
            if vid in visits:
                out[vid] = load_json(p)
    return out


def main():
    od301 = load_v301()
    side = json.load(open("us_parallel/side_reliable.json"))["reliable"]
    for name, root, tracks in SETS:
        data = json.load(open(tracks))
        ends = {k: od31.ends_from_geometry(g) for k, g in data["airports"].items()}
        visits = {v["id"]: v for v in data["visits"]}
        labs = labels(root, set(visits))
        ev = {"v3.0.1": defaultdict(Counter), "v3.1": defaultdict(Counter)}
        for vid, v in visits.items():
            for p in od301.detect(v, ends[v["airport"]]):
                ev["v3.0.1"][vid][(p["kind"], p["runway"])] += 1
            for p in od31.detect(v, ends[v["airport"]], set(side.get(v["airport"], []))):
                ev["v3.1"][vid][(p["kind"], p["runway"])] += 1
        changed = [vid for vid in visits if ev["v3.0.1"][vid] != ev["v3.1"][vid]]
        print(f"{name}: {len(visits)} visits, {len(labs)} labeled, event sets changed by v3.1: {len(changed)} {changed}")
        for variant in ("v3.0.1", "v3.1"):
            raw = sum(events_from_label(labs[v]) == ev[variant][v] for v in labs)
            line = f"  {variant:6s} raw {raw}/{len(labs)}"
            if name.startswith("Set 4"):
                adj = sum(adjudicate(v, events_from_label(labs[v])) == ev[variant][v] for v in labs)
                line += f", adjudicated {adj}/{len(labs)}"
            print(line)
        for vid in changed:
            lab = adjudicate(vid, events_from_label(labs[vid])) if vid in labs else None
            print(f"    {vid} ({visits[vid]['airport']}): label {dict(lab) if lab is not None else '-'}")
            print(f"      v3.0.1 {dict(ev['v3.0.1'][vid])}")
            print(f"      v3.1   {dict(ev['v3.1'][vid])}")


if __name__ == "__main__":
    main()
