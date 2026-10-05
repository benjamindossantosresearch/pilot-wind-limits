#!/usr/bin/env python3
"""
make_q2_review.py

Builds the Q2 sanity-check set (notes/q2_measures.md, "Sanity check before the
full run"): 30 measurable piston approaches from the Q2 population (VMC, study
airports in their windows), drawn at random with a fixed seed from three
severity strata:
    10 extreme  S at or above the 98th percentile
    10 high     S between the 75th and 95th percentiles
    10 low      S at or below the 25th percentile
The order is shuffled and the stratum is hidden, so the reviewer rates each
approach before seeing its score.

    python3 make_q2_review.py

Writes q2_review/review.json (tracks and measures for the review page) and
q2_review/key.csv (stratum and source row for each review id, not published).
"""

import csv
import gzip
import io
import json
import math
import os
import random
import zipfile

import numpy as np

import q2_measures as qm
import tower_compare as tc

SEED = 20261002
OUT = "q2_review"
CRITS = ("g_c1", "g_c2a", "g_c3", "g_c4", "g_c5b", "b_c1", "b_c2a", "b_c3", "b_c4")


def windows():
    w = json.load(open("q1a/windows.json"))
    w.update(json.load(open("q1a/windows_untowered.json")))
    return w


def in_window(r, w):
    s, e = w.get(r["airport"]), w.get(r["airport"] + "_exclude_from")
    return bool(s) and s <= r["date"] <= "2026-09-30" and not (e and r["date"] >= e)


def track_for(r):
    """Per-point series around the approach, recomputed with the same code as q2_measures."""
    apt = tc.make_airport("K" + r["airport"])
    geo = qm.load_runway_geometry({r["airport"]})
    g = geo[(r["airport"], r["runway"])]
    frame = qm.Frame(g, apt)
    day, vi = r["visit"].split(":")
    with gzip.open(os.path.join("q2_extract", r["airport"], f"{day}.jsonl.gz"), "rt") as f:
        visits = [json.loads(line) for line in f if line.strip()]
    v = visits[int(vi)]
    P, t = v["pts"], v["pts"]["t"]
    apps = [i for i, p in enumerate(v["passes"]) if p["kind"] == "approach"]
    p = v["passes"][apps[int(r["app_no"]) - 1]]
    off = apt.elev_ft - g["thr_elev"]
    # same height source as q2_measures: calibrated GNSS heights for 100 ft-step altimeters
    res = qm.baro_resolution(P)
    vr_orig = list(P["vr"])
    qm.clean_velocity(P, apt)
    hyb = qm.calibrated_gnss_heights(P, apt) if res == 100 else None
    P["_coarse"] = res == 100
    if hyb:
        hyb = (qm.clean_heights(hyb[0], P["t"], vr_orig), qm.clean_heights(hyb[1], P["t"], vr_orig))
    else:
        P["agl_ind"] = qm.clean_heights(P["agl_ind"], P["t"], vr_orig)
        P["agl"] = qm.clean_heights(P["agl"], P["t"], vr_orig)
    src_ind, src_true = hyb if hyb else (P["agl_ind"], P["agl"])
    hat = [None if (a if a is not None else b) is None else (a if a is not None else b) + off
           for a, b in zip(src_ind, src_true)]
    tg = float(r["gate_time"])
    t_low = float(r["lowest_time"])
    idx = [i for i in range(len(t)) if tg - 180 <= t[i] <= t_low + 6]
    tan_g = math.tan(math.radians(g["gpa"]))
    drct = float(r["wind_drct"]) if r["wind_drct"] else None
    sknt = float(r["wind_kt"]) if r["wind_kt"] else None
    hw_rwy = float(r["hw_kt"]) if r["hw_kt"] else None
    pts = []
    for i in idx:
        al, lr = frame.along_lateral(P["lat"][i], P["lon"][i])
        d = qm.descent_rate(P, i, hat)
        gs = P["gs"][i]
        trk = P["trk"][i]
        hwt = qm.track_headwind(drct, sknt, trk, hw_rwy)
        pts.append({
            "t": round(t[i] - tg, 1), "along_nm": round(al / qm.FT_PER_NM, 4), "lat_ft": round(lr, 1),
            "hat": None if hat[i] is None else round(hat[i], 1),
            "ref": round(g["tch"] + max(0.0, -al) * tan_g, 1),
            "gs": gs, "trk_err": None if trk is None else round(qm.sdiff(trk, frame.course), 1),
            "desc": None if d is None else round(d), "req": None if gs is None else round(gs * qm.FPM_PER_KT * tan_g),
            "eas": None if gs is None or hwt is None else round(qm.est_airspeed(gs, hwt, hat[i]), 1),
            "gnd": bool(P["gnd"][i])})
    # every runway at the airport, in this approach's frame (nm), for the map
    rwys, seen = [], set()
    widths = runway_widths(r["airport"])
    for (a_id, end_id), ge in qm.load_runway_geometry({r["airport"]}).items():
        far_id = next((e for (a2, e), g2 in qm.load_runway_geometry({r["airport"]}).items()
                       if e != end_id and g2["end_lat"] == ge["far_lat"] and g2["end_lon"] == ge["far_lon"]), "")
        key = tuple(sorted((end_id, far_id)))
        if key in seen:
            continue
        seen.add(key)
        a1, l1 = frame.along_lateral(ge["end_lat"], ge["end_lon"])
        a2, l2 = frame.along_lateral(ge["far_lat"], ge["far_lon"])
        rwys.append({"ends": [end_id, far_id], "a": [round(a1 / qm.FT_PER_NM, 4), round(a2 / qm.FT_PER_NM, 4)],
                     "l": [round(l1 / qm.FT_PER_NM, 4), round(l2 / qm.FT_PER_NM, 4)],
                     "width_ft": widths.get(key, 100), "active": r["runway"] in key})
    return pts, g, frame.length_ft / qm.FT_PER_NM, rwys, ("gnss_calibrated" if hyb else "baro"), frame.course


def runway_widths(apt_id):
    z = zipfile.ZipFile(qm.NASR_ZIP)
    out = {}
    for row in csv.DictReader(io.TextIOWrapper(z.open("APT_RWY.csv"), encoding="latin-1")):
        if row["ARPT_ID"] == apt_id:
            out[tuple(sorted(row["RWY_ID"].split("/")))] = float(row["RWY_WIDTH"] or 100)
    return out


def main():
    w = windows()
    pop = [r for r in csv.DictReader(open("q2/approaches.csv"))
           if r["group"] == "piston" and r["status"] == "ok" and r["vmc"] == "1" and in_window(r, w)]
    S = np.array([float(r["s"]) for r in pop])
    p25, p75, p95, p98 = np.percentile(S, [25, 75, 95, 98])
    strata = {"extreme": [r for r, s in zip(pop, S) if s >= p98],
              "high": [r for r, s in zip(pop, S) if p75 <= s <= p95],
              "low": [r for r, s in zip(pop, S) if s <= p25]}
    rng = random.Random(SEED)
    picks = []
    for name, rows in strata.items():
        for r in rng.sample(rows, 10):
            picks.append((name, r))
    rng.shuffle(picks)
    os.makedirs(OUT, exist_ok=True)
    items, key = [], []
    for n, (stratum, r) in enumerate(picks, 1):
        rid = f"R{n:02d}"
        pts, g, rwy_nm, rwys, hsrc, course = track_for(r)
        vals = {k: float(r[k]) for k in CRITS if r[k]}
        driver = max(vals, key=vals.get)
        num = lambda k: float(r[k]) if r[k] not in ("", None) else None
        items.append({
            "id": rid, "airport": "K" + r["airport"], "runway": r["runway"], "date": r["date"], "local_time": r["local_time"][:5],
            "type": r["type"], "ownership": r["ownership"], "gpa": g["gpa"], "tch": g["tch"], "runway_len_nm": round(rwy_nm, 3), "runways": rwys, "height_source": hsrc, "course": round(course, 1),
            "straight_in": r["straight_in"], "base_side": r["base_side"],
            "wind": {"drct": num("wind_drct"), "kt": num("wind_kt"), "gust": num("gust_kt"), "xw": num("xw_kt"),
                     "xw_right": num("xw_right_kt"), "hw": num("hw_kt"), "src": r["wind_src"]},
            "measures": {k: num(k) for k in ("s", "s_gate", "s_below", "g_c1", "g_c2a", "g_c3", "g_c4", "g_c5b", "g_c5a", "g_c2b",
                                             "b_c1", "b_c2a", "b_c3", "b_c4", "align_hat", "overshoot_ft", "final_length_nm",
                                             "gate_along_nm", "gate_lat_ft", "gate_trk_err", "gate_descent_fpm", "gate_req_fpm", "gate_est_as",
                                             "gate_as_range", "lowest_hat")},
            "flags": {k: r[k] == "1" for k in ("flag_practice", "flag_p1_power_off", "flag_p2_steep", "flag_sink_1000", "flag_level")},
            "driver": driver, "poh_approach": num("poh_approach_kias"), "pts": pts})
        key.append({"id": rid, "stratum": stratum, "s": r["s"], "driver": driver, "airport": r["airport"], "visit": r["visit"],
                    "app_no": r["app_no"], "icao": r["icao"]})
    json.dump({"generated": "2026-10-02", "percentiles": {"p25": round(p25, 2), "p75": round(p75, 2), "p95": round(p95, 2), "p98": round(p98, 2)},
               "population": len(pop), "items": items}, open(os.path.join(OUT, "review.json"), "w"), separators=(",", ":"))
    with open(os.path.join(OUT, "key.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(key[0]))
        wr.writeheader()
        wr.writerows(key)
    print(f"population {len(pop):,}; S p25 {p25:.2f} p75 {p75:.2f} p95 {p95:.2f} p98 {p98:.2f}")
    for k in key:
        print(k["id"], k["stratum"], k["s"], k["driver"], k["airport"])


if __name__ == "__main__":
    main()
