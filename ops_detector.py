#!/usr/bin/env python3
"""
ops_detector.py

Approach and climb-out detector, version 3 (VERSION below). Version 2 is frozen
at notes/ops_detector_v2_frozen_2026-10-01.py. Works on one visit given as arrays
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

Version 3 changes, written after the Set 2 review (Set 2 is development data from
here on; v3 is scored on a fresh Set 3):

  8. Go-around split. An approach pass that descends and then climbs at least
     100 ft before the threshold is split at its lowest point: the descent is
     the approach, the rest joins the climb-out on that runway (T067).
  9. Cross-runway merge. Two passes of the same kind on different runways
     within 90 s, with nothing between them, count once: the earlier for
     climb-outs (the takeoff runway, the later one being a turn through another
     runway's window), the later for approaches (the landing runway, the earlier
     being part of the base-to-final turn) (T001, T056, T061).
 10. Rule 6 picks the runway whose course best matches the last track, then the
     smaller lateral offset, instead of lateral offset alone (T005).
 11. Runway traversal through a gap. Two consecutive points 20 to 300 s apart,
     the first low (at or below 700 ft) up to 1.5 nm before a threshold and within
     0.8 nm of the centerline, the second past the threshold (at least 0.3 nm
     along) within 1 nm of the centerline, at least 1 nm further along the
     runway direction: the airplane flew down the runway in the gap. It gets an
     approach and a climb-out on that runway (inferred="traverse"), skipping
     either one already detected there. Tight circuits whose final, touchdown,
     and climb-out all fall in a coverage gap (T049).

Version 3.1 (2026-10-02, after the US tower-count spot check, logged in
notes/decisions.md before validation; v3.0.1 frozen at notes/ops_detector_v3.0.1_2026-10-02.py):

 12. Parallel runways. Ends within 10 deg of the same course whose centerlines
     are at most 0.8 nm apart form a parallel group. Rules 5, 6, 7 and 11 only
     looked for a pass on the same end, so a circuit seen on 28L could be
     counted again on 28R (HWO, DTO). (a) Two passes of the same kind on one
     group within 120 s count once, an observed pass kept over an inferred
     one (two observed passes are left alone). (b) An inferred pass in a
     group takes the runway of the nearest centerline from the visit's
     final-approach points (approach window, 120 s before) or climb-out points
     (climb window, 120 s after), else from the side of the downwind (6 min
     before an approach or after a climb-out, outermost runway on that side)
     where that runway end's pattern side is reliable (side_ok, from
     us_parallel/side_reliable.json), else it keeps its runway. A traverse
     approach and its climb-out share one runway. (c) Merge again.
     Observed passes are never reassigned.

Each pass: {"kind": "approach" | "climb", "runway", "i0", "i1", "min_agl",
"inferred": None | "gap" | "end" | "traverse"}.
"""

import statistics

import adsb_airport_coverage as cov
import runway_use as ru

VERSION = 3.1  # 3.0.1: guard against a missing start height in rule 5. 3.1: rule 12 (parallel runways)
MERGE_GAP_S = 45
GA_RISE_FT = 100
CROSS_MERGE_S = 90
TRAVERSE = {"gap": (20, 300), "before_along": (-1.5, 0.0), "before_lat": 0.8, "before_agl": 700,
            "after_along_min": 0.3, "after_lat": 1.0, "min_progress": 1.0, "dedup_s": 60}
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
PARALLEL = {"course": 10, "sep": 0.8, "merge_s": 120, "window_s": 120, "min_pts": 2, "win_lat": 0.5,
            "app_along": -2.0, "app_agl": 900, "clb_past": 2.0, "clb_agl": 1200, "trk": 30,
            "downwind_s": 360, "dw_agl": (300, 2000), "dw_margin": 0.5, "dw_min_pts": 3}


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


def detect(a, ends, side_ok=None):
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

    # Rule 8: split an approach that bottoms out and climbs again before the threshold
    split = []
    for g in groups:
        if g["lab"][0] == "approach" and len(g["idx"]) >= 3:
            hs = [h(i) for i in g["idx"]]
            k = min(range(len(hs)), key=lambda m: hs[m])
            if k < len(hs) - 1 and hs[-1] - hs[k] >= GA_RISE_FT:
                split.append({"lab": g["lab"], "idx": g["idx"][:k + 1], "along": g["along"][:k + 1]})
                split.append({"lab": ("climb", g["lab"][1]), "idx": g["idx"][k:], "along": g["along"][k:]})
                continue
        split.append(g)
    groups = []
    for g in split:
        if groups and groups[-1]["lab"] == g["lab"] and a["t"][g["idx"][0]] - a["t"][groups[-1]["idx"][-1]] <= MERGE_GAP_S:
            groups[-1]["idx"] += g["idx"]
            groups[-1]["along"] += g["along"]
        else:
            groups.append({"lab": g["lab"], "idx": list(g["idx"]), "along": list(g["along"])})

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

    # Rule 9: one maneuver sweeping two runways' windows counts once
    passes.sort(key=lambda p: a["t"][p["i0"]])
    dedup = []
    for p in passes:
        q = dedup[-1] if dedup else None
        if q and q["kind"] == p["kind"] and q["runway"] != p["runway"] \
                and a["t"][p["i0"]] - a["t"][q["i1"]] <= CROSS_MERGE_S:
            if p["kind"] == "approach":
                dedup[-1] = p
            continue
        dedup.append(p)
    passes = dedup

    # Rule 11: flew down the runway inside a coverage gap
    for i in range(n - 1):
        gap = a["t"][i + 1] - a["t"][i]
        if not (TRAVERSE["gap"][0] <= gap <= TRAVERSE["gap"][1]) or a["gnd"][i] or a["agl"][i] is None:
            continue
        if a["agl"][i] > TRAVERSE["before_agl"]:
            continue
        for e in ends:
            al0, lat0 = e.along_lateral(a["x"][i], a["y"][i])
            al1, lat1 = e.along_lateral(a["x"][i + 1], a["y"][i + 1])
            if not (TRAVERSE["before_along"][0] <= al0 < TRAVERSE["before_along"][1] and lat0 <= TRAVERSE["before_lat"]):
                continue
            if not (al1 >= TRAVERSE["after_along_min"] and lat1 <= TRAVERSE["after_lat"] and al1 - al0 >= TRAVERSE["min_progress"]):
                continue
            t0, t1, w = a["t"][i], a["t"][i + 1], TRAVERSE["dedup_s"]
            has_app = any(q["kind"] == "approach" and q["runway"] == e.name and t0 - w <= a["t"][q["i1"]] <= t1 for q in passes)
            has_clb = any(q["kind"] == "climb" and q["runway"] == e.name and t0 <= a["t"][q["i0"]] <= t1 + w for q in passes)
            if not has_app:
                passes.append({"kind": "approach", "runway": e.name, "i0": i, "i1": i, "min_agl": a["agl"][i],
                               "inferred": "traverse", "start_along": al0, "start_agl": a["agl"][i]})
            if not has_clb:
                passes.append({"kind": "climb", "runway": e.name, "i0": i + 1, "i1": i + 1, "min_agl": None,
                               "inferred": "traverse", "start_along": al1, "start_agl": h(i + 1)})
            break

    # Rule 5: a low climb-out by an airplane already airborne implies an approach to that runway
    out, last_climb_t = [], a["t"][0] - 1
    passes.sort(key=lambda p: a["t"][p["i0"]])
    for p in passes:
        if p["kind"] == "climb":
            t0 = a["t"][p["i0"]]
            e = end_by_name[p["runway"]]
            airborne_before = any(not a["gnd"][i] and a["t"][i] < t0 - AIRBORNE_BEFORE_S for i in range(p["i0"]))
            starts_low = (p["start_agl"] is not None and p["start_agl"] <= INFER_CLIMB_START_AGL
                          and p["start_along"] <= e.length + INFER_CLIMB_START_PAST)
            seen = any(q["kind"] == "approach" and q["runway"] == p["runway"]
                       and last_climb_t < a["t"][q["i1"]] <= t0 for q in passes)
            if airborne_before and starts_low and not seen and p["inferred"] is None:
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
                    if best is None or (td, lat) < best[1]:
                        best = (e.name, (td, lat))
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
    final = _parallel_groups_rule(a, ends, final, side_ok)
    for p in final:
        p.pop("start_along", None)
        p.pop("start_agl", None)
    return final


def _signed(e, x, y):
    """Along-track distance and signed lateral offset (positive to the right of the landing direction)."""
    rx, ry = x - e.tx, y - e.ty
    return rx * e.ux + ry * e.uy, rx * e.uy - ry * e.ux


def parallel_groups(ends):
    """end name -> [(centerline offset from this end's, end), ...] left to right, for ends with a parallel."""
    out = {}
    for e in ends:
        g = []
        for f in ends:
            if ru.angle_diff(e.course, f.course) > PARALLEL["course"]:
                continue
            _, off = _signed(e, f.tx + f.ux * f.length / 2, f.ty + f.uy * f.length / 2)
            if abs(off) <= PARALLEL["sep"]:
                g.append((0.0 if f is e else off, f))
        if len(g) > 1:
            out[e.name] = sorted(g, key=lambda t: t[0])
    return out


def _lateral_choice(a, grp, idx, kind):
    """Nearest centerline in a group from the median lateral offset of window points, or None."""
    ref = grp[0][1]
    lats = []
    for j in idx:
        if a["trk"][j] is None or (a["agl"][j] is None and not a["gnd"][j]):
            continue
        h = 0 if a["gnd"][j] else a["agl"][j]
        if ru.angle_diff(a["trk"][j], ref.course) > PARALLEL["trk"]:
            continue
        hit = False
        for _, e in grp:
            along, lat = e.along_lateral(a["x"][j], a["y"][j])
            if lat > PARALLEL["win_lat"]:
                continue
            if kind == "approach" and PARALLEL["app_along"] <= along < 0 and h <= PARALLEL["app_agl"]:
                hit = True
            if kind == "climb" and 0 <= along <= e.length + PARALLEL["clb_past"] and h <= PARALLEL["clb_agl"]:
                hit = True
        if hit:
            lats.append(_signed(ref, a["x"][j], a["y"][j])[1])
    if len(lats) < PARALLEL["min_pts"]:
        return None
    m = statistics.median(lats)
    return min(grp, key=lambda t: abs(m - t[0]))[1].name


def _side_choice(a, grp, idx, side_ok):
    """Outermost runway on the downwind's side, if that end's pattern side is reliable, else None."""
    if not side_ok:
        return None
    ref = grp[0][1]
    mid = (grp[0][0] + grp[-1][0]) / 2
    offs = []
    for j in idx:
        h = a["agl"][j]
        if h is None or a["gnd"][j] or a["trk"][j] is None or not (PARALLEL["dw_agl"][0] <= h <= PARALLEL["dw_agl"][1]):
            continue
        if ru.angle_diff(a["trk"][j], (ref.course + 180) % 360) > PARALLEL["trk"]:
            continue
        along, off = _signed(ref, a["x"][j], a["y"][j])
        if -PARALLEL["dw_margin"] <= along <= ref.length + PARALLEL["dw_margin"]:
            offs.append(off - mid)
    if len(offs) < PARALLEL["dw_min_pts"]:
        return None
    name = grp[0][1].name if statistics.median(offs) < 0 else grp[-1][1].name
    return name if name in side_ok else None


def _parallel_groups_rule(a, ends, passes, side_ok):
    """Rule 12: one maneuver per parallel group, and runway choice for inferred passes in a group."""
    groups = parallel_groups(ends)
    if not groups or not passes:
        return passes
    t = a["t"]
    gkey = {name: tuple(sorted(f.name for _, f in g)) for name, g in groups.items()}

    def ptime(p):
        return t[p["i1"]] if p["kind"] == "approach" else t[p["i0"]]

    def merge(ps):
        keep = list(ps)
        changed = True
        while changed:
            changed = False
            for i, p in enumerate(keep):
                for q in keep[i + 1:]:
                    if p["kind"] != q["kind"] or p["runway"] not in gkey or gkey[p["runway"]] != gkey.get(q["runway"]):
                        continue
                    if abs(ptime(p) - ptime(q)) > PARALLEL["merge_s"]:
                        continue
                    pi, qi = p["inferred"] is not None, q["inferred"] is not None
                    if not pi and not qi:
                        continue
                    if pi and qi:   # both inferred: the later approach, the earlier climb-out (as rule 9)
                        drop = (p if ptime(p) <= ptime(q) else q) if p["kind"] == "approach" else (q if ptime(p) <= ptime(q) else p)
                    else:
                        drop = p if pi else q
                    keep.remove(drop)
                    changed = True
                    break
                if changed:
                    break
        return keep

    passes = merge(passes)
    n = len(t)

    def window(t0, t1):
        return [j for j in range(n) if t0 <= t[j] <= t1]

    # inferred passes in a group: runway from final or climb-out points, else the pattern side
    done = set()
    for p in passes:
        if p["inferred"] is None or p["runway"] not in groups or id(p) in done:
            continue
        grp = groups[p["runway"]]
        mate = None
        if p["inferred"] == "traverse":
            mate = next((q for q in passes if q is not p and q["inferred"] == "traverse" and q["runway"] == p["runway"]
                         and q["kind"] != p["kind"] and abs(q["i0"] - p["i0"]) <= 1), None)
        app = p if p["kind"] == "approach" else (mate if mate and mate["kind"] == "approach" else None)
        clb = p if p["kind"] == "climb" else (mate if mate and mate["kind"] == "climb" else None)
        choice = None
        if app is not None:
            ta = t[app["i1"]]
            choice = _lateral_choice(a, grp, window(ta - PARALLEL["window_s"], ta), "approach")
        if choice is None and clb is not None:
            tc = t[clb["i0"]]
            choice = _lateral_choice(a, grp, window(tc, tc + PARALLEL["window_s"]), "climb")
        if choice is None and app is not None:
            ta = t[app["i1"]]
            choice = _side_choice(a, grp, window(ta - PARALLEL["downwind_s"], ta), side_ok)
        if choice is None and clb is not None:
            tc = t[clb["i0"]]
            choice = _side_choice(a, grp, window(tc, tc + PARALLEL["downwind_s"]), side_ok)
        for q in (app, clb):
            if q is not None:
                if choice:
                    q["runway"] = choice
                done.add(id(q))
    return merge(passes)


def ends_from_geometry(apt_geom):
    """RunwayEnd list from a labeling tracks.json airport entry."""
    out = []
    for r in apt_geom["runways"]:
        e0, e1 = r["ends"]
        out.append(ru.RunwayEnd(e0["name"], (e0["x"], e0["y"]), (e1["x"], e1["y"])))
        out.append(ru.RunwayEnd(e1["name"], (e1["x"], e1["y"]), (e0["x"], e0["y"])))
    return out
