#!/usr/bin/env python3
"""
ops_detector.py

Approach and climb-out detector, version 2. Works on one visit given as arrays
in local nautical-mile coordinates around the airport, so the same code runs on
the labeling tracks (labeling/tracks.json) and on the pipeline's point dicts
(see arrays_from_points).

Version 1 is runway_use.find_passes. Version 2 changes, written after Benjamin's
100 development labels (2026-10-01) and to be scored on a fresh held-out sample:

  1. Curved short finals. Besides the v1 window (up to 2 nm out, within 0.3 nm
     of the centerline, track within 30 deg, below 900 ft), a near-field window
     accepts points up to 1 nm out, within 0.5 nm, track within 50 deg, below
     600 ft. Catches tight base-to-final turns where the data ends mid-turn.
  2. Two-point passes. An approach may have 2 points when it ends within 1 nm of
     the threshold below 500 ft. A climb-out may have 2 points.
  3. Early-turning climb-outs. A near-field climb window (to 1 nm past the far
     end, within 0.5 nm, track within 50 deg, below 900 ft) catches departures
     and touch-and-goes that turn crosswind early.
  4. Climb-outs must start low: the pass's lowest point at or below 800 ft AGL.
  5. Inferred approach before a climb-out. A climb-out that starts low (at or
     below 600 ft, within 1 nm past the far end) by an airplane that was already
     airborne earlier in the visit means it touched down or went around on that
     runway. If no approach to that runway was seen since the previous climb-out,
     one is added (inferred="gap"). Covers circuits whose final falls in a
     coverage gap.
  6. Data ends on final. A visit whose last point is airborne, at or below 600 ft,
     up to 1.2 nm before a threshold, within 0.5 nm of the centerline, and
     descending gets an approach to that runway (inferred="end") if none already
     covers the end of the visit. The track must be within 60 deg of the runway
     course, or within 100 deg and converging on it by at least 30 deg over the
     last 30 s (data ending in the base-to-final turn).
  7. Implied climb-out. Two approaches to the same runway with no climb-out
     between them get one inferred climb-out (inferred="gap"): the airplane had
     to climb back to the pattern.
Rules 6 (converging turn) and 7 were added after review of V096, V015, and V052,
before the held-out sample was drawn. v2 is frozen from here for the held-out score.

Each pass: {"kind": "approach" | "climb", "runway", "i0", "i1", "min_agl",
"inferred": None | "gap" | "end"}.
"""

import statistics

import adsb_airport_coverage as cov
import runway_use as ru

MERGE_GAP_S = 45
MIN_HEIGHT_CHANGE = 50
APP_STRICT = {"along": (-2.0, 0.0), "lat": 0.30, "trk": 30, "agl": 900}
APP_NEAR = {"along": (-1.0, 0.0), "lat": 0.50, "trk": 50, "agl": 600}
CLB_STRICT = {"past": 2.0, "lat": 0.30, "trk": 30, "agl": 1200}
CLB_NEAR = {"past": 1.0, "lat": 0.50, "trk": 50, "agl": 900}
TWO_POINT_APP = {"along_min": -1.0, "agl": 500}
CLIMB_MAX_LOWEST_AGL = 800
INFER_CLIMB_START_AGL = 600
INFER_CLIMB_START_PAST = 1.0
AIRBORNE_BEFORE_S = 30
END_RULE = {"agl": 600, "along": (-1.2, 0.0), "lat": 0.50, "trk": 60, "lookback_s": 30, "drop_ft": 50,
            "turning_trk": 100, "converge_deg": 30}


def arrays_from_points(points, apt):
    """Convert one visit's point dicts (adsb_airport_coverage) to detector arrays."""
    xy = [cov.to_xy_nm(p["lat"], p["lon"], apt.lat, apt.lon) for p in points]
    return {
        "t": [p["t"] for p in points], "x": [a for a, _ in xy], "y": [b for _, b in xy],
        "agl": [p["agl_ft"] for p in points], "trk": [p["track"] for p in points],
        "vr": [p["vrate_fpm"] for p in points], "gnd": [1 if p["on_ground"] else 0 for p in points],
    }


def _label(i, a, ends):
    """Best (kind, end, tier) for point i, or None. Strict tier beats near tier, then smaller lateral."""
    agl, trk, gnd = a["agl"][i], a["trk"][i], a["gnd"][i]
    if (agl is None and not gnd) or trk is None:
        return None
    h = 0 if gnd else agl
    best = None
    for e in ends:
        along, lat = e.along_lateral(a["x"][i], a["y"][i])
        td = ru.angle_diff(trk, e.course)
        cands = []
        if along < 0 and not gnd:
            for tier, w in (("strict", APP_STRICT), ("near", APP_NEAR)):
                if w["along"][0] <= along < w["along"][1] and lat <= w["lat"] and td <= w["trk"] and h <= w["agl"]:
                    cands.append(("approach", tier))
                    break
        if along >= 0:
            for tier, w in (("strict", CLB_STRICT), ("near", CLB_NEAR)):
                if along <= e.length + w["past"] and lat <= w["lat"] and td <= w["trk"] and h <= w["agl"]:
                    cands.append(("climb", tier))
                    break
        for kind, tier in cands:
            key = (0 if tier == "strict" else 1, lat)
            if best is None or key < best[0]:
                best = (key, (kind, e.name), along)
    return (best[1], best[2]) if best else None


def detect(a, ends):
    n = len(a["t"])
    end_by_name = {e.name: e for e in ends}
    labeled = []
    for i in range(n):
        r = _label(i, a, ends)
        if r:
            labeled.append((i, r[0], r[1]))
    groups = []
    for i, lab, along in labeled:
        if groups and groups[-1]["lab"] == lab and a["t"][i] - a["t"][groups[-1]["idx"][-1]] <= MERGE_GAP_S:
            groups[-1]["idx"].append(i)
            groups[-1]["along"].append(along)
        else:
            groups.append({"lab": lab, "idx": [i], "along": [along]})

    def h(i):
        return 0 if a["gnd"][i] else a["agl"][i]

    passes = []
    for g in groups:
        kind, end = g["lab"]
        idx = g["idx"]
        hs = [h(i) for i in idx]
        change = hs[-1] - hs[0]
        rates = [a["vr"][i] for i in idx if isinstance(a["vr"][i], (int, float))]
        med = statistics.median(rates) if rates else 0
        if kind == "approach":
            two_ok = len(idx) == 2 and g["along"][-1] >= TWO_POINT_APP["along_min"] and hs[-1] <= TWO_POINT_APP["agl"]
            if len(idx) < 3 and not two_ok:
                continue
            need = -25 if len(idx) == 2 else -MIN_HEIGHT_CHANGE
            if not (change <= need or med <= -200):
                continue
        else:
            if len(idx) < 2 or min(hs) > CLIMB_MAX_LOWEST_AGL:
                continue
            if not (change >= MIN_HEIGHT_CHANGE or med >= 200):
                continue
        passes.append({"kind": kind, "runway": end, "i0": idx[0], "i1": idx[-1],
                       "min_agl": min(hs), "inferred": None, "start_along": g["along"][0], "start_agl": hs[0]})

    # Rule 5: a low climb-out by an airplane already airborne implies an approach to that runway
    out, last_climb_t = [], a["t"][0] - 1
    passes.sort(key=lambda p: a["t"][p["i0"]])
    for p in passes:
        if p["kind"] == "climb":
            t0 = a["t"][p["i0"]]
            e = end_by_name[p["runway"]]
            airborne_before = any(not a["gnd"][i] and a["t"][i] < t0 - AIRBORNE_BEFORE_S for i in range(p["i0"]))
            starts_low = p["start_agl"] <= INFER_CLIMB_START_AGL and p["start_along"] <= e.length + INFER_CLIMB_START_PAST
            seen = any(q["kind"] == "approach" and q["runway"] == p["runway"]
                       and last_climb_t < a["t"][q["i1"]] <= t0 for q in passes)
            if airborne_before and starts_low and not seen:
                out.append({"kind": "approach", "runway": p["runway"], "i0": p["i0"], "i1": p["i0"],
                            "min_agl": None, "inferred": "gap"})
            last_climb_t = a["t"][p["i1"]]
        out.append(p)

    # Rule 6: data ends on final
    last = n - 1
    if n and not a["gnd"][last] and a["agl"][last] is not None and a["agl"][last] <= END_RULE["agl"] \
            and a["trk"][last] is not None:
        covered = any(q["kind"] == "approach" and q["i1"] >= last - 1 for q in out)
        if not covered:
            t_back = a["t"][last] - END_RULE["lookback_s"]
            j = next((k for k in range(last, -1, -1) if a["t"][k] <= t_back), 0)
            prior = h(j) if h(j) is not None else a["agl"][last]
            descending = prior - a["agl"][last] >= END_RULE["drop_ft"] or \
                (isinstance(a["vr"][last], (int, float)) and a["vr"][last] <= -200)
            best = None
            for e in ends:
                along, lat = e.along_lateral(a["x"][last], a["y"][last])
                td = ru.angle_diff(a["trk"][last], e.course)
                td_back = ru.angle_diff(a["trk"][j], e.course) if a["trk"][j] is not None else None
                aligned = td <= END_RULE["trk"] or (
                    td <= END_RULE["turning_trk"] and td_back is not None
                    and td_back - td >= END_RULE["converge_deg"])
                if END_RULE["along"][0] <= along < END_RULE["along"][1] and lat <= END_RULE["lat"] and aligned:
                    if best is None or lat < best[1]:
                        best = (e.name, lat)
            if best and descending:
                out.append({"kind": "approach", "runway": best[0], "i0": last, "i1": last,
                            "min_agl": a["agl"][last], "inferred": "end"})
    # Rule 7: two approaches to the same runway need a climb-out between them
    out.sort(key=lambda p: (a["t"][p["i1"]], 0 if p["kind"] == "approach" else 1))
    final = []
    for k, p in enumerate(out):
        final.append(p)
        if p["kind"] != "approach":
            continue
        nxt = next((q for q in out[k + 1:] if q["kind"] == "approach"), None)
        if nxt is None or nxt["runway"] != p["runway"]:
            continue
        t_a, t_b = a["t"][p["i1"]], a["t"][nxt["i0"]]
        between = any(q["kind"] == "climb" and t_a <= a["t"][q["i0"]] <= t_b for q in out)
        if not between:
            final.append({"kind": "climb", "runway": p["runway"], "i0": p["i1"], "i1": p["i1"],
                          "min_agl": None, "inferred": "gap"})
    for p in final:
        p.pop("start_along", None)
        p.pop("start_agl", None)
    return final


def ends_from_geometry(apt_geom):
    """RunwayEnd list from a labeling tracks.json airport entry."""
    out = []
    for r in apt_geom["runways"]:
        e0, e1 = r["ends"]
        out.append(ru.RunwayEnd(e0["name"], (e0["x"], e0["y"]), (e1["x"], e1["y"])))
        out.append(ru.RunwayEnd(e1["name"], (e1["x"], e1["y"]), (e0["x"], e0["y"])))
    return out
