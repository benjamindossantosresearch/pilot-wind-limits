#!/usr/bin/env python3
"""
q2_synthetic.py

Measurement noise model for Q2 (notes/q2_measures.md, amendment 3, last item).
Synthetic approaches with known deviations are sampled densely (0.5 s, exact
values) and again the way ADS-B delivers them (irregular 1 to 2 s updates with
dropouts, position error by NACp, barometric altitude in 25 or 100 ft steps,
vertical rate in 64 fpm steps with noise, ground speed and track from a noisy
velocity). Both go through the same q2_measures.measure(). The dense run is the
truth. The comparison shows the bias and spread the pipeline adds to each
criterion ratio, and which deviation sizes it can resolve.

    python3 q2_synthetic.py

Writes q2_synthetic/results.csv and q2_synthetic/summary.txt.
"""

import csv
import itertools
import math
import os
import random
from collections import defaultdict

import numpy as np

import q2_measures as qm

FT_PER_NM = qm.FT_PER_NM
KT_FT_S = FT_PER_NM / 3600.0
RNG = random.Random(20261002)
N_REP = 20
GPA, TCH = 3.0, 50.0


class SynthFrame:
    """Runway along +y (course 000), landing threshold at the origin. lat/lon fields carry x/y in feet."""
    course = 0.0
    length_ft = 5000.0
    tx = ty = 0.0

    def xy(self, a, b):
        return a, b

    def along_lateral(self, a, b):
        return b, a


GEOM = {"gpa": GPA, "tch": TCH, "right_traffic": False, "tpa_msl": None, "thr_elev": 0.0}


def ref_h(along):
    return TCH + max(0.0, -along) * math.tan(math.radians(GPA))


def trajectory(kind, gs0, lat_off, v_off, rate_amp, spd_amp, wind_from, wind_kt, dt=0.5):
    """Dense true trajectory: list of dicts with t, x, y, h, gs, trk, vr (fpm, positive up)."""
    pts = []
    tas = gs0
    if kind == "straight":
        x, y = lat_off, -3.0 * FT_PER_NM
        hdg_trk = 0.0
        legs = None
    else:
        # left base 0.8 nm out, 0.7 nm left of centerline, at 700 ft, turning onto final
        x, y = -0.7 * FT_PER_NM, -0.9 * FT_PER_NM
        hdg_trk = 90.0
        legs = "base"
    t = 0.0
    t_final = None
    h_base = 0.0
    h = (ref_h(y) + v_off) if kind == "straight" else 750.0
    while y < 200 and t < 400:
        # ground speed: airspeed plus wind along track, plus the injected speed oscillation
        # wind at the airplane's height follows the same power-law profile the estimator assumes
        wind_along = -wind_kt * qm.profile(h) * math.cos(math.radians(wind_from - hdg_trk))
        gs = tas + wind_along + spd_amp * math.sin(2 * math.pi * t / 25.0)
        if kind == "pattern" and legs == "base":
            # standard-rate-ish left turn starting when the turn radius brings the airplane onto the centerline
            r = (gs * KT_FT_S) ** 2 / (32.174 * math.tan(math.radians(25)))
            if x >= -r - lat_off:
                legs = "turn"
        if kind == "pattern" and legs == "turn":
            omega = (gs * KT_FT_S) / ((gs * KT_FT_S) ** 2 / (32.174 * math.tan(math.radians(25))))
            hdg_trk = hdg_trk - math.degrees(omega * dt)
            if hdg_trk <= 0:
                hdg_trk = 0.0
                legs = "final"
        vx = gs * KT_FT_S * math.sin(math.radians(hdg_trk))
        vy = gs * KT_FT_S * math.cos(math.radians(hdg_trk))
        if kind == "straight" or legs == "final":
            # on the path at the injected offset, plus a height oscillation whose rate swings by rate_amp fpm
            if t_final is None:
                t_final = t
                h_base = h - (ref_h(y) + v_off)          # leftover offset at rollout, flown off over 20 s
            tt = t - t_final
            per = 20.0
            amp_h = rate_amp / 60.0 * per / (2 * math.pi)
            path_rate = gs * KT_FT_S * 60.0 * math.tan(math.radians(GPA)) * math.cos(math.radians(hdg_trk))
            decay = max(0.0, 1.0 - tt / 20.0)
            h = ref_h(y) + v_off + h_base * decay - amp_h * math.cos(2 * math.pi * tt / per) + amp_h
            vr = -path_rate + rate_amp * math.sin(2 * math.pi * tt / per) - (h_base / 20.0 * 60.0 if decay > 0 else 0.0)
        else:
            # descend on base toward the path height at the rollout point
            vr = -550.0
        pts.append({"t": t, "x": x, "y": y, "h": h, "gs": gs, "trk": hdg_trk % 360, "vr": vr})
        x += vx * dt
        y += vy * dt
        if not (kind == "straight" or legs == "final"):
            h += vr / 60.0 * dt
        if h < 0:
            break
        t += dt
    return pts


def to_visit(pts, degrade, coarse, nacp):
    """Visit structure for measure(). degrade: sample and add ADS-B-like errors."""
    if degrade:
        sel, t_next = [], 0.0
        for p in pts:
            if p["t"] >= t_next:
                if RNG.random() > 0.10:
                    sel.append(p)
                t_next = p["t"] + RNG.uniform(1.0, 2.2)
        pos_sd = 16.0 if nacp == 10 else 49.0     # ft, 1 sigma from the 95% bound (10 m, 30 m)
    else:
        sel = pts
    P = defaultdict(list)
    for p in sel:
        x, y, h, gs, trk, vr = p["x"], p["y"], p["h"], p["gs"], p["trk"], p["vr"]
        if degrade:
            x += RNG.gauss(0, pos_sd)
            y += RNG.gauss(0, pos_sd)
            vx = gs * math.sin(math.radians(trk)) + RNG.gauss(0, 0.6)
            vy = gs * math.cos(math.radians(trk)) + RNG.gauss(0, 0.6)
            gs = round(math.hypot(vx, vy), 1)
            trk = round(math.degrees(math.atan2(vx, vy)) % 360, 1)
            if coarse:
                h_ind = round(h / 100.0) * 100.0              # Gillham encoder
                h_geo = round((h + RNG.gauss(0, 12)) / 25.0) * 25.0
            else:
                h_ind = round(h / 25.0) * 25.0
                h_geo = round((h + RNG.gauss(0, 12)) / 25.0) * 25.0
            vr = round((vr + RNG.gauss(0, 60)) / 64.0) * 64.0
        else:
            h_ind = h_geo = h
        P["t"].append(p["t"])
        P["lat"].append(x)
        P["lon"].append(y)
        P["agl_ind"].append(h_ind)
        P["agl"].append(h_ind)
        P["geom"].append(h_geo)
        P["gs"].append(gs)
        P["trk"].append(trk)
        P["vr"].append(vr)
        P["gvr"].append(vr)
        for k in ("modes", "nacp", "gva", "src", "qnh", "ias", "roll", "baro", "agl_gnss"):
            P[k].append(None)
        P["gnd"].append(False)
    P = dict(P)
    P["_coarse"] = coarse and degrade
    # coarse aircraft: calibrated GNSS heights, as in q2_measures.calibrated_gnss_heights (true = geometric + mean offset)
    if P["_coarse"]:
        off = float(np.mean([a - g for a, g in zip(P["agl"], P["geom"])]))
        P["agl"] = [g + off for g in P["geom"]]
        P["agl_ind"] = list(P["agl"])
    n = len(P["t"])
    alongs = [P["lon"][i] for i in range(n)]
    i1 = max(i for i in range(n) if alongs[i] < 0 and P["agl"][i] > 0)
    i0 = next(i for i in range(n) if alongs[i] >= -2 * FT_PER_NM and abs(qm.sdiff(P["trk"][i], 0)) <= 30 and abs(P["lat"][i]) <= 0.3 * FT_PER_NM)
    return {"pts": P, "passes": [{"kind": "approach", "runway": "36", "i0": min(i0, i1), "i1": i1}]}


def run(v, wind):
    P = v["pts"]
    hat = list(P["agl_ind"])
    hat_true = list(P["agl"])
    return qm.measure(v, 0, SynthFrame(), GEOM, hat, hat_true, 0.0, wind, None)


KEYS = ("s", "g_c1", "g_c2a", "g_c3", "g_c4", "g_c5b", "b_c1", "b_c2a", "b_c3", "b_c4", "align_hat")


def main():
    grid = {
        "kind": ["straight", "pattern"],
        "gs0": [65.0, 90.0],
        "lat_off": [0.0, 150.0, 300.0],
        "v_off": [0.0, 60.0, 150.0],
        "rate_amp": [0.0, 300.0, 600.0],
        "spd_amp": [0.0, 6.0],
        "wind": [(0.0, 0.0), (270.0, 15.0)],
    }
    rows = []
    combos = list(itertools.product(*grid.values()))
    for combo in combos:
        c = dict(zip(grid.keys(), combo))
        wf, wk = c["wind"]
        truth_pts = trajectory(c["kind"], c["gs0"], c["lat_off"], c["v_off"], c["rate_amp"], c["spd_amp"], wf, wk)
        wind = (wf, wk, wf, wk, "synthetic")
        truth = run(to_visit(truth_pts, False, False, 10), wind)
        if truth.get("status") != "ok":
            continue
        for coarse, nacp in ((False, 10), (False, 9), (True, 10)):
            for rep in range(N_REP):
                try:
                    m = run(to_visit(truth_pts, True, coarse, nacp), wind)
                except (StopIteration, ValueError):
                    continue
                row = {**{k: v for k, v in c.items() if k != "wind"}, "wind_kt": wk, "coarse": int(coarse), "nacp": nacp, "rep": rep,
                       "status": m.get("status")}
                for k in KEYS:
                    row[f"true_{k}"] = truth.get(k)
                    row[f"meas_{k}"] = m.get(k)
                rows.append(row)
    os.makedirs("q2_synthetic", exist_ok=True)
    with open("q2_synthetic/results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    L = [f"Synthetic approaches: {len(combos)} scenarios x 3 sensor cases x {N_REP} noisy samples = {len(rows):,} measured runs",
         f"Measurable at 300 ft after degradation: {100 * np.mean([r['status'] == 'ok' for r in rows]):.1f}%", ""]
    ok = [r for r in rows if r["status"] == "ok"]
    for label, sel in (("25 ft altimeter, NACp 10", [r for r in ok if not r["coarse"] and r["nacp"] == 10]),
                       ("25 ft altimeter, NACp 9", [r for r in ok if not r["coarse"] and r["nacp"] == 9]),
                       ("100 ft altimeter (calibrated GNSS heights), NACp 10", [r for r in ok if r["coarse"]])):
        L.append(label + f" ({len(sel):,} runs): measured minus true ratio, median bias / spread (half the 5-95% range) / classification agreement at 1")
        for k in KEYS[:-1]:
            pairs = [(r[f"true_{k}"], r[f"meas_{k}"]) for r in sel if r[f"true_{k}"] is not None and r[f"meas_{k}"] is not None]
            if len(pairs) < 50:
                continue
            d = np.array([m - t for t, m in pairs])
            agree = np.mean([(t > 1) == (m > 1) for t, m in pairs])
            L.append(f"  {k:6s} bias {np.median(d):+.3f}  spread {(np.percentile(d, 95) - np.percentile(d, 5)) / 2:.3f}  agree {100 * agree:.1f}%  (n={len(pairs):,})")
        pairs = [(r["true_align_hat"], r["meas_align_hat"]) for r in sel if r["true_align_hat"] is not None and r["meas_align_hat"] is not None]
        if pairs:
            d = np.array([m - t for t, m in pairs])
            L.append(f"  alignment height (ft) bias {np.median(d):+.0f}  spread {(np.percentile(d, 95) - np.percentile(d, 5)) / 2:.0f}")
        L.append("")
    L.append("Resolution: median measured ratio for each injected deviation, 25 ft altimeter, NACp 10, straight-in, calm")
    base = [r for r in ok if not r["coarse"] and r["nacp"] == 10 and r["kind"] == "straight" and r["wind_kt"] == 0]
    for name, key, crit in (("lateral offset (ft)", "lat_off", "g_c1"), ("glide path offset (ft)", "v_off", "g_c3"),
                            ("descent-rate swing (fpm)", "rate_amp", "b_c4"), ("speed swing (kt)", "spd_amp", "g_c5b")):
        cells = []
        for val in sorted({r[key] for r in base}):
            g = [r for r in base if r[key] == val and r[f"meas_{crit}"] is not None]
            tv = [r[f"true_{crit}"] for r in g if r[f"true_{crit}"] is not None]
            if g:
                cells.append(f"{val:g}: true {np.median(tv):.2f}, measured {np.median([r[f'meas_{crit}'] for r in g]):.2f}")
        L.append(f"  {name} -> {crit}: " + "; ".join(cells))
    L.append("")
    L.append("Wind check: speed-stability ratio (C5b) with a steady 15 kt crosswind and no injected speed swing (true airspeed constant)")
    for kind in ("straight", "pattern"):
        g = [r["meas_g_c5b"] for r in ok if r["kind"] == kind and r["wind_kt"] == 15 and r["spd_amp"] == 0 and not r["coarse"]
             and r["nacp"] == 10 and r["meas_g_c5b"] is not None]
        g0 = [r["meas_g_c5b"] for r in ok if r["kind"] == kind and r["wind_kt"] == 0 and r["spd_amp"] == 0 and not r["coarse"]
              and r["nacp"] == 10 and r["meas_g_c5b"] is not None]
        if g and g0:
            L.append(f"  {kind}: median C5b {np.median(g):.2f} in wind against {np.median(g0):.2f} calm")
    text = "\n".join(L)
    open("q2_synthetic/summary.txt", "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
