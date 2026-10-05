#!/usr/bin/env python3
"""Set 4 (US detector check): visit, arrival, and approach agreement for frozen v3.0.1 and v3.1, under the raw
labels, the adjudicated labels, and the adjudicated labels with Benjamin's U078 relabel (approach 24R)."""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ops_detector as od31  # noqa: E402
from score_labels import events_from_label  # noqa: E402
from score_labels_v31 import adjudicate, labels, load_v301  # noqa: E402

data = json.load(open("labeling/us/tracks.json"))
ends = {k: od31.ends_from_geometry(g) for k, g in data["airports"].items()}
visits = {v["id"]: v for v in data["visits"]}
labs = labels("labeling/export_us_BD_raw", set(visits))
side = json.load(open("us_parallel/side_reliable.json"))["reliable"]
od301 = load_v301()
ev = {"v3.0.1": defaultdict(Counter), "v3.1": defaultdict(Counter)}
for vid, v in visits.items():
    for p in od301.detect(v, ends[v["airport"]]):
        ev["v3.0.1"][vid][(p["kind"], p["runway"])] += 1
    for p in od31.detect(v, ends[v["airport"]], set(side.get(v["airport"], []))):
        ev["v3.1"][vid][(p["kind"], p["runway"])] += 1
L = {"raw": {v: events_from_label(labs[v]) for v in labs}}
L["adjudicated"] = {v: adjudicate(v, L["raw"][v]) for v in labs}
L["adjudicated + U078 relabel"] = dict(L["adjudicated"])
L["adjudicated + U078 relabel"]["U078"] = Counter({("approach", "24R"): 1})
for variant in ("v3.0.1", "v3.1"):
    for name, lab in L.items():
        D = ev[variant]
        vis = sorted(lab)
        full = sum(1 for v in vis if +lab[v] == +D[v])
        al = {v for v in vis if any(k == "approach" for k, _ in lab[v])}
        ad = {v for v in vis if any(k == "approach" for k, _ in D[v])}
        agree = sum(1 for v in vis if (v in al) == (v in ad))
        napp = sum(n for v in vis for (k, _), n in lab[v].items() if k == "approach")
        dapp = sum(n for v in vis for (k, _), n in D[v].items() if k == "approach")
        anyrw = sum(min(sum(n for (k, _), n in lab[v].items() if k == "approach"), sum(n for (k, _), n in D[v].items() if k == "approach")) for v in vis)
        right = sum(min(n, D[v][(k, e)]) for v in vis for (k, e), n in lab[v].items() if k == "approach")
        print(f"{variant} vs {name}: fully correct {full}/100. Arrival yes or no agrees {agree}/100. Labeled arrivals {len(al)}, "
              f"found {len(al & ad)}, detector-only {len(ad - al)}. Labeled approaches {napp}, detector approaches {dapp}, "
              f"matched ignoring runway {anyrw}, on the right runway {right}")
