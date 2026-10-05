#!/usr/bin/env python3
"""
score_labels.py

Scores the operations detector against hand labels from the Approach Track
Labeler, and the raters against each other.

Labels are exported from the labeler's database into a local folder first
(Claude does this with the ArtifactData tool, list with out_dir), giving
    <labels_dir>/labels/<rater id>/visits/<visit id>.json
and, for rater initials,
    <labels_dir>/labels/<rater id>.json

Usage:
    python3 score_labels.py labeling/export
    python3 score_labels.py labeling/export_heldout labeling/heldout     (held-out set)
    python3 score_labels.py labeling/export_heldout labeling/heldout tracks_metar.json   (other heights)

Agreement unit: the visit. A visit's event set is the count of approaches and
climb-outs per runway end. The detector and a rater agree on a visit when the
two sets are identical. Three detector variants are scored:
    all      v1 (runway_use.py), every approach pass (no minimum height)
    low      v1, only approaches reaching 400 ft AGL within 0.75 nm
    v2       frozen v2 (notes/ops_detector_v2_frozen_2026-10-01.py), rerun on the labeling tracks
    v3       current ops_detector.py, rerun on the labeling tracks
Climb-outs are the same in both v1 variants. Pilot-study criterion: 90 percent
visit-level agreement. Visits a rater marked "too little data" are reported
both ways.
"""

import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict

DETECTOR = "labeling/detector.csv"
TRACKS = "labeling/tracks.json"


def load_json(path):
    with open(path) as f:
        d = json.load(f)
    return d.get("data", d) if isinstance(d, dict) else d


def events_from_label(lab):
    ev = Counter()
    if lab.get("none"):
        return ev
    for end, c in (lab.get("counts") or {}).items():
        if c.get("app"):
            ev[("approach", end)] += int(c["app"])
        if c.get("dep"):
            ev[("climb", end)] += int(c["dep"])
    return ev


def detector_events(variant):
    if variant in ("v2", "v3"):
        if variant == "v2":
            import importlib.util
            spec = importlib.util.spec_from_file_location("ops_detector_v2", "notes/ops_detector_v2_frozen_2026-10-01.py")
            od = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(od)
        else:
            import ops_detector as od
        data = json.load(open(TRACKS))
        ends = {k: od.ends_from_geometry(g) for k, g in data["airports"].items()}
        ev = defaultdict(Counter)
        for v in data["visits"]:
            for p in od.detect(v, ends[v["airport"]]):
                ev[v["id"]][(p["kind"], p["runway"])] += 1
        return ev
    ev = defaultdict(Counter)
    with open(DETECTOR) as f:
        for r in csv.DictReader(f):
            if r["kind"] == "approach" and variant == "low" and r["low"] != "True":
                continue
            ev[r["visit_id"]][(r["kind"], r["runway"])] += 1
    return ev


def kappa(a, b):
    """Cohen's kappa for two equal-length lists of labels."""
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def pct(n, d):
    return f"{100.0 * n / d:5.1f}% ({n}/{d})" if d else "n/a"


def main():
    global TRACKS, DETECTOR
    if len(sys.argv) not in (2, 3, 4):
        sys.exit(__doc__)
    root = sys.argv[1]
    if len(sys.argv) >= 3:
        TRACKS = os.path.join(sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else "tracks.json")
        DETECTOR = os.path.join(sys.argv[2], "detector.csv")
    visits = [v["id"] for v in json.load(open(TRACKS))["visits"]]
    raters = {}
    for vdir in sorted(glob.glob(os.path.join(root, "labels", "*", "visits"))):
        rid = os.path.basename(os.path.dirname(vdir))
        meta_path = os.path.join(root, "labels", rid + ".json")
        initials = load_json(meta_path).get("initials", rid[:6]) if os.path.exists(meta_path) else rid[:6]
        labs = {os.path.basename(p)[:-5]: load_json(p) for p in glob.glob(os.path.join(vdir, "*.json"))}
        labs = {k: v for k, v in labs.items() if k in set(visits)}
        raters[initials] = labs
    if not raters:
        sys.exit(f"No labels under {root}/labels/*/visits")

    det = {v: detector_events(v) for v in ("all", "low", "v2", "v3")}
    print(f"{len(visits)} visits in the sample, raters: {', '.join(f'{k} ({len(v)} labeled)' for k, v in raters.items())}\n")

    for name, labs in raters.items():
        print(f"Rater {name} vs detector")
        for variant in ("all", "low", "v2", "v3"):
            for skip_sparse in (False, True):
                agree = total = 0
                for vid in visits:
                    lab = labs.get(vid)
                    if not lab or (skip_sparse and lab.get("sparse")):
                        continue
                    total += 1
                    agree += events_from_label(lab) == det[variant].get(vid, Counter())
                tag = "excluding too-little-data" if skip_sparse else "all labeled visits"
                print(f"  detector {variant:3s}, {tag:26s} visit agreement {pct(agree, total)}")
        ga_visits = [vid for vid in visits if labs.get(vid) and (labs[vid].get("ga") or 0) > 0]
        if ga_visits:
            for variant in ("v2", "v3"):
                ok = sum(events_from_label(labs[v]) == det[variant].get(v, Counter()) for v in ga_visits)
                print(f"  detector {variant:3s}, visits with a go-around ({sum(labs[v]['ga'] for v in ga_visits)} go-arounds): "
                      f"visit agreement {pct(ok, len(ga_visits))}")
        # event-level recall and precision
        for variant in ("all", "low", "v2", "v3"):
            tp = fn = fp = 0
            for vid in visits:
                lab = labs.get(vid)
                if not lab:
                    continue
                h, d = events_from_label(lab), det[variant].get(vid, Counter())
                for k in set(h) | set(d):
                    tp += min(h[k], d[k]); fn += max(0, h[k] - d[k]); fp += max(0, d[k] - h[k])
            print(f"  detector {variant:3s}, events: recall {pct(tp, tp + fn)}, precision {pct(tp, tp + fp)}")
        print()

    names = list(raters)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = raters[names[i]], raters[names[j]]
            both = [v for v in visits if v in a and v in b]
            same = sum(events_from_label(a[v]) == events_from_label(b[v]) for v in both)
            has_a = [bool(any(k[0] == "approach" for k in events_from_label(a[v]))) for v in both]
            has_b = [bool(any(k[0] == "approach" for k in events_from_label(b[v]))) for v in both]
            print(f"Raters {names[i]} vs {names[j]}: {len(both)} visits labeled by both")
            print(f"  identical event sets {pct(same, len(both))}")
            print(f"  Cohen's kappa, visit has an approach: {kappa(has_a, has_b):.2f}")
            diffs = [v for v in both if events_from_label(a[v]) != events_from_label(b[v])]
            if diffs:
                print(f"  disagreements to review: {', '.join(diffs)}")


if __name__ == "__main__":
    main()
