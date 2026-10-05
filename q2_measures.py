#!/usr/bin/env python3
"""
q2_measures.py

Per-approach Q2 measures, as defined in notes/q2_measures.md (final 2026-10-02,
with the amendments of the same day). Reads q2_extract/ (q2_extract.py), so
reruns do not touch the regional cache.

    python3 q2_measures.py --airports BDR,HVN,BED,LWM,OWD,PYM,TAN --workers 32

Writes q2/approaches.csv (one row per detected approach, every aircraft group,
every day; population filters are applied in the analysis) and q2/counts.txt.

Implementation details fixed here before any Q2 result was looked at (also
logged in notes/decisions.md):
  * Below-gate criteria (C1 to C4 between 300 ft and the lowest observed point)
    stop at FLOOR_HAT = 100 ft HAT. Below that the airplane is in the roundout,
    where descent rate and path height leave the approach tolerances by design.
    Sensitivity: floor 50 ft (s_below50).
  * Gate crossing: the last descent through the gate height before the
    approach's lowest point, interpolated in time between the two points that
    straddle it, each within 10 s of the crossing.
  * Descent rate: median of the ADS-B barometric rates reported within 5 s
    of the point (geometric rate if no barometric rate, else the differenced
    height track). Single reports come in 64 fpm steps and are noisy: coupled
    jets exceed the C4 tolerance below the gate on 16 percent of approaches
    with single reports. Single-report values are kept (g_c4raw, b_c4raw,
    s_c4raw) as a sensitivity. Required rate = ground speed x tan(glide path).
  * Estimated airspeed: ground speed plus the surface wind component against
    the airplane's own ground track at each point, scaled to height (1/7 power
    law). Using the runway-course headwind for every point would turn the
    ground-speed swing of a turn in wind into a false airspeed change.
  * A point is aligned when C1 and C2a are both at or below 1. Alignment (M3)
    walks back from the gate while aligned points continue with no gap over 20 s.
  * Base leg (M2, M5, M6): the last point before alignment whose track differs
    from the runway course by 60 degrees or more. Base side = side of the
    centerline that point is on.
  * Altimeter resolution: about a third of piston aircraft report barometric
    altitude in 100 ft steps (Gillham encoders), too coarse for the 100 ft
    glide path tolerance. For those visits, heights come from GNSS geometric
    height shifted by the visit's mean offset to the barometric indicated
    (and true) height, and descent rate prefers the geometric rate. Results
    are also reported split by altimeter resolution.
  * Data glitches (found in Benjamin's review, 2026-10-02): frozen velocity
    (same ground speed and track for more than 5 s while the position moves)
    is replaced by track and speed from positions, and its vertical rates are
    dropped. Height spikes (more than 50 ft from the median of a symmetric
    window of up to 3 points each side) and frozen heights (same value for more than 8 s at a reported rate
    of 300 fpm or more) are dropped.
  * Practice flags: P1 (power-off 180 shape) alignment below 300 ft or never,
    with the turn to final starting within 0.6 nm of the threshold. P2 (steep)
    descent angle between the 500 and 300 ft crossings above 5.5 degrees.
  * Coupled (control group): the aircraft reports autopilot and approach modes
    at the gate.
"""

import argparse
import bisect
import csv
import datetime as dt
import glob
import gzip
import io
import json
import math
import os
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import adsb_airport_coverage as cov
import faa_registry as fr
import poh
import tower_compare as tc
import wind_activity as wa
import wind_qc

FT_PER_NM = 6076.12
FPM_PER_KT = 101.27
G = 9.80665
GATE, GATE2 = 300.0, 500.0
FLOOR_HAT, FLOOR_HAT_SENS = 100.0, 50.0
TOL = {"c1": 200.0, "c2a": 10.0, "c2b": 15.0, "c3": 100.0, "c4": 300.0, "c5b": 10.0}
GATE_GAP_S = 10.0
RATE_WIN_S = 5.0
ALIGN_GAP_S = 20.0
PROFILE_EXP = 1.0 / 7.0   # --profile-exp for the registered sensitivity (0, 1/4) and the observed 0.20
AIRSPEED = "cas"   # 2026-10-02 (Benjamin): estimated true airspeed is converted to calibrated airspeed before any
                   # comparison with POH (indicated) speeds or the 10 kt stability tolerance. "tas" reproduces the old runs.
STRAIGHT_IN_NM = 2.0
STRAIGHT_IN_DEG = 30.0
BASE_DEG = 60.0
P1_TURN_NM = 0.6
P2_DEG = 5.5
NASR_ZIP = "reference/nasr/01_Oct_2026_APT_CSV.zip"
OUT = "q2"


# ---------------------------------------------------------------- geometry

_NASR_ROWS = {}


def _nasr(name):
    """All rows of one NASR airport table, read once per process."""
    if name not in _NASR_ROWS:
        z = zipfile.ZipFile(NASR_ZIP)
        _NASR_ROWS[name] = list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="latin-1")))
    return _NASR_ROWS[name]


def load_runway_geometry(airport_ids):
    """(airport, end id) -> landing threshold, course, threshold elevation, glide path, TCH, right traffic."""
    ends = [r for r in _nasr("APT_RWY_END.csv") if r["ARPT_ID"] in airport_ids]
    base = {r["ARPT_ID"]: r for r in _nasr("APT_BASE.csv") if r["ARPT_ID"] in airport_ids}
    by_rwy = defaultdict(list)
    for r in ends:
        by_rwy[(r["ARPT_ID"], r["RWY_ID"])].append(r)
    geo = {}
    for (apt_id, _), pair in by_rwy.items():
        if len(pair) != 2:
            continue
        for a, b in ((pair[0], pair[1]), (pair[1], pair[0])):
            num = lambda r, k: float(r[k]) if r.get(k, "").strip() else None
            displaced = num(a, "LAT_DISPLACED_THR_DECIMAL") is not None
            thr_lat = num(a, "LAT_DISPLACED_THR_DECIMAL") if displaced else num(a, "LAT_DECIMAL")
            thr_lon = num(a, "LONG_DISPLACED_THR_DECIMAL") if displaced else num(a, "LONG_DECIMAL")
            elev = (num(a, "DISPLACED_THR_ELEV") if displaced else None) or num(a, "RWY_END_ELEV")
            geo[(apt_id, a["RWY_END_ID"])] = {
                "end_lat": num(a, "LAT_DECIMAL"), "end_lon": num(a, "LONG_DECIMAL"),
                "far_lat": num(b, "LAT_DECIMAL"), "far_lon": num(b, "LONG_DECIMAL"),
                "thr_lat": thr_lat, "thr_lon": thr_lon, "thr_elev": elev, "displaced": displaced,
                "gpa": num(a, "VISUAL_GLIDE_PATH_ANGLE") or 3.0, "gpa_default": num(a, "VISUAL_GLIDE_PATH_ANGLE") is None,
                "tch": num(a, "THR_CROSSING_HGT") or 50.0,
                "right_traffic": a.get("RIGHT_HAND_TRAFFIC_PAT_FLAG", "") == "Y",
                "tpa_msl": num(base.get(apt_id, {}), "TPA"),
            }
    return geo


class Frame:
    """Runway-end frame in feet: along (negative before the landing threshold) and lateral (positive right of course)."""

    def __init__(self, g, apt):
        self.lat0, self.lon0 = apt.lat, apt.lon
        ex, ey = self.xy(g["end_lat"], g["end_lon"])
        fx, fy = self.xy(g["far_lat"], g["far_lon"])
        self.tx, self.ty = self.xy(g["thr_lat"], g["thr_lon"])
        n = math.hypot(fx - ex, fy - ey)
        self.ux, self.uy = (fx - ex) / n, (fy - ey) / n
        self.course = math.degrees(math.atan2(self.ux, self.uy)) % 360
        self.length_ft = n

    def xy(self, lat, lon):
        x, y = cov.to_xy_nm(lat, lon, self.lat0, self.lon0)
        return x * FT_PER_NM, y * FT_PER_NM

    def along_lateral(self, lat, lon):
        x, y = self.xy(lat, lon)
        rx, ry = x - self.tx, y - self.ty
        return rx * self.ux + ry * self.uy, rx * self.uy - ry * self.ux


def sdiff(a, b):
    """Signed angle a - b in (-180, 180]."""
    return (a - b + 180) % 360 - 180


# ---------------------------------------------------------------- weather

def load_onemin_month(station, month):
    path = os.path.join(cov.WEATHER_DIR, "onemin", f"{station}_{month}.csv")
    data = {}
    if not os.path.exists(path):
        return data
    for r in csv.DictReader(open(path)):
        try:
            t = dt.datetime.strptime(r["valid(UTC)"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
        except (KeyError, ValueError):
            continue
        num = lambda k: float(r[k]) if r.get(k) not in (None, "", "M") else None
        data[int(t.timestamp()) // 60] = (num("drct"), num("sknt"), num("gust_drct"), num("gust_sknt"))
    return data


def load_metars(station):
    obs = []
    for path in sorted(glob.glob(os.path.join(cov.WEATHER_DIR, f"{station}_metar_*.csv"))):
        obs += wa.load_metars(path)
    obs.sort(key=lambda o: o["t"])
    seen, uniq = set(), []
    for o in obs:
        if o["t"] not in seen:
            seen.add(o["t"])
            m = re.search(r"\sA(\d{4})\b", o["metar"].split(" RMK")[0])
            o["alt_inhg"] = int(m.group(1)) / 100 if m else None
            o["temp_c"] = metar_temp_c(o["metar"])
            uniq.append(o)
    return uniq, [o["t"].timestamp() for o in uniq]


def metar_temp_c(metar):
    """Air temperature (C) from a METAR: the remarks T group (tenths) if present, else the body group."""
    m = re.search(r"\sT([01])(\d{3})(?:[01]\d{3})?\b", metar)
    if m:
        v = int(m.group(2)) / 10.0
        return -v if m.group(1) == "1" else v
    m = re.search(r"\s(M?\d{2})/(?:M?\d{2})?\s", metar.split(" RMK")[0] + " ")
    if m:
        s_ = m.group(1)
        return -float(s_[1:]) if s_.startswith("M") else float(s_)
    return None


def cas_factor(field_elev_ft, hat_ft, air):
    """sqrt(rho / rho0) at the airplane's height, so calibrated airspeed = true airspeed x factor (low speed,
    no compressibility). Station pressure from the altimeter setting and field elevation, the METAR
    temperature, standard lapse rate up to the airplane. Standard values where the METAR lacks them."""
    if AIRSPEED != "cas" or field_elev_ft is None:
        return 1.0
    temp_c, alt_inhg = air if air else (None, None)
    if alt_inhg is None:
        alt_inhg = 29.92
    if temp_c is None:
        temp_c = 15.0 - 1.98 * field_elev_ft / 1000.0
    h_field = field_elev_ft * 0.3048
    p_field = alt_inhg * 33.8639 * (1.0 - 0.0065 * h_field / 288.15) ** 5.2559
    t_field = temp_c + 273.15
    t_air = t_field - 0.0065 * max(hat_ft or 0.0, 0.0) * 0.3048
    p_air = p_field * (t_air / t_field) ** 5.2559
    return math.sqrt(p_air * 100.0 / (287.05 * t_air) / 1.225)


def metar_near(metars, mtimes, t, max_s=40 * 60):
    i = bisect.bisect_left(mtimes, t)
    cand = [j for j in (i - 1, i) if 0 <= j < len(metars)]
    if not cand:
        return None
    j = min(cand, key=lambda j: abs(mtimes[j] - t))
    return metars[j] if abs(mtimes[j] - t) <= max_s else None


def gate_wind(t, onemin, metars, mtimes):
    """(drct, sknt, gust_drct, gust_sknt, source) at time t."""
    m = int(t) // 60
    for dm in (0, -1, 1, -2, 2):
        r = onemin.get(m + dm)
        if r and r[1] is not None and (r[0] is not None or r[1] == 0):
            return r[0], r[1], r[2], r[3], "onemin"
    o = metar_near(metars, mtimes, t)
    if o and o["sknt"] is not None:
        return o["drct"], o["sknt"], o["drct"], o["gust"], "metar"
    return None


def profile(hat_ft):
    """Power-law factor from 10 m to the airplane's height."""
    h = max(hat_ft or 0.0, 33.0) * 0.3048
    return (h / 10.0) ** PROFILE_EXP


# ---------------------------------------------------------------- measures

def interp(a, b, f):
    return None if a is None or b is None else a + f * (b - a)


def interp_angle(a, b, f):
    return None if a is None or b is None else (a + f * sdiff(b, a)) % 360


def descent_rate(P, i, hat, smooth=True):
    """Descent rate (fpm, positive down) at point i. smooth: median of the reported rates within
    RATE_WIN_S of the point (single reports are quantized to 64 fpm and noisy). Raw: the point's own report."""
    t = P["t"]
    for k in (("gvr", "vr") if P.get("_coarse") else ("vr", "gvr")):
        if smooth:
            vals = [P[k][j] for j in range(max(0, i - 6), min(len(t), i + 7))
                    if abs(t[j] - t[i]) <= RATE_WIN_S and isinstance(P[k][j], (int, float))]
            if vals:
                return -float(statistics.median(vals))
        else:
            v = P[k][i]
            if isinstance(v, (int, float)):
                return -float(v)
    lo = max(0, i - 2)
    hi = min(len(t) - 1, i + 2)
    if hat[lo] is not None and hat[hi] is not None and t[hi] - t[lo] >= 2:
        return (hat[lo] - hat[hi]) / (t[hi] - t[lo]) * 60
    return None


def find_crossing(hat, t, j_lo, j_low, gate):
    """Index k with hat[k] >= gate > hat[k+1], the last descent through the gate before j_low, or a status."""
    valid = [i for i in range(j_lo, j_low + 1) if hat[i] is not None]
    if not valid:
        return None, "no_height"
    if hat[j_low] is None or hat[j_low] >= gate:
        return None, "ends_above_gate"
    for a, b in zip(reversed(valid[:-1]), reversed(valid[1:])):
        if hat[a] >= gate > hat[b]:
            f = (hat[a] - gate) / (hat[a] - hat[b])
            tg = t[a] + f * (t[b] - t[a])
            if tg - t[a] > GATE_GAP_S or t[b] - tg > GATE_GAP_S:
                return (a, b, f, tg), "gap_at_gate"
            return (a, b, f, tg), "ok"
    return None, "starts_below_gate"


def baro_resolution(P):
    """100 if the aircraft reports barometric altitude in 100 ft steps (Gillham encoder), else 25."""
    b = [x for x in P["baro"] if isinstance(x, (int, float))]
    if len(b) >= 20 and sum(1 for x in b if x % 100 == 0) >= 0.95 * len(b):
        return 100
    return 25


def calibrated_gnss_heights(P, apt):
    """Heights above field for a 100 ft-step aircraft. GNSS geometric height and true height differ by a
    constant (geoid model and GNSS bias), so true height = geometric height + the visit's mean
    (true - geometric) offset, where the mean over many points removes the 100 ft quantization.
    Indicated height = true height / the point's cold-temperature ratio (true / indicated from the
    METAR method). Returns (indicated, true) lists, or None if fewer than 10 pairs."""
    geo = [None if g is None else g + apt.geoid_offset_ft - apt.elev_ft for g in P["geom"]]
    pairs = [(b, gg) for b, gg in zip(P["agl"], geo) if gg is not None and b is not None]
    if len(pairs) < 10:
        return None
    off = sum(b - gg for b, gg in pairs) / len(pairs)
    ratios = [b / a for a, b in zip(P["agl_ind"], P["agl"]) if a is not None and b is not None and a > 200]
    r0 = statistics.median(ratios) if ratios else 1.0
    true = [None if gg is None else gg + off for gg in geo]
    ind = [None if t is None else t / r0 for t in true]
    return ind, true


FROZEN_VEL_S = 5.0
FROZEN_H_S = 8.0
SPIKE_FT = 50.0


def clean_velocity(P, apt):
    """Frozen velocity: an aircraft that stops sending velocity keeps its last ground speed and track in the
    trace while its position moves on. Points whose (ground speed, track) pair has been unchanged for more
    than FROZEN_VEL_S get track and ground speed from their positions instead (neighbors at least 1.5 s
    apart), and their vertical rates are dropped. Returns the number of points replaced."""
    t, n = P["t"], len(P["t"])
    xy = [cov.to_xy_nm(a, b, apt.lat, apt.lon) for a, b in zip(P["lat"], P["lon"])]
    frozen, start = [False] * n, 0
    for i in range(1, n):
        same = P["gs"][i] is not None and P["gs"][i] == P["gs"][i - 1] and P["trk"][i] == P["trk"][i - 1]
        if not same:
            start = i
        elif t[i] - t[start] > FROZEN_VEL_S:
            frozen[i] = True
    for i in range(n):
        if not frozen[i]:
            continue
        a, b = i - 1, i + 1
        while a > 0 and t[i] - t[a] < 0.75:
            a -= 1
        while b < n - 1 and t[b] - t[i] < 0.75:
            b += 1
        a, b = max(a, 0), min(b, n - 1)
        dt = t[b] - t[a]
        if dt >= 1.5:
            dx, dy = xy[b][0] - xy[a][0], xy[b][1] - xy[a][1]
            P["trk"][i] = math.degrees(math.atan2(dx, dy)) % 360
            P["gs"][i] = math.hypot(dx, dy) / dt * 3600.0
        else:
            P["trk"][i] = P["gs"][i] = None
        P["vr"][i] = P["gvr"][i] = None
    return sum(frozen)


def clean_heights(h, t, vr):
    """Height glitches. Spikes: a Hampel filter on a symmetric window (the same number of points on each
    side, up to 3, all within 12 s, the point itself included). A point more than SPIKE_FT from the window
    median is dropped. The median of a symmetric window over a steady climb or descent is the center point,
    so real height changes never trip it. Frozen heights: the same value held for more than FROZEN_H_S
    while the reported rate says 300 fpm or more, which a 25 ft step cannot do."""
    n = len(h)
    out = list(h)
    valid = [i for i in range(n) if h[i] is not None]
    for pos, i in enumerate(valid):
        left = [j for j in valid[max(0, pos - 3):pos] if t[i] - t[j] <= 12]
        right = [j for j in valid[pos + 1:pos + 4] if t[j] - t[i] <= 12]
        k = min(len(left), len(right))
        if k == 0:
            continue
        w = [h[j] for j in left[len(left) - k:]] + [h[i]] + [h[j] for j in right[:k]]
        if abs(h[i] - statistics.median(w)) > SPIKE_FT:
            out[i] = None
    start = 0
    for i in range(1, n):
        if out[i] is None or out[i] != out[start]:
            start = i
            continue
        if t[i] - t[start] > FROZEN_H_S:
            rates = [abs(v) for v in vr[start:i + 1] if isinstance(v, (int, float))]
            if rates and statistics.median(rates) >= 300:
                out[i] = None
    return out


def est_airspeed(gs, hw, hat):
    return None if gs is None or hw is None else gs + hw * profile(hat)


def track_headwind(drct, sknt, trk, fallback):
    """Surface wind component against the airplane's ground track (its headwind on that track)."""
    if sknt is None:
        return None
    if sknt == 0 or drct is None:
        return 0.0
    if not isinstance(trk, (int, float)):
        return fallback
    return sknt * math.cos(math.radians(drct - trk))


def measure(v, p_idx, frame, g, hat, hat_true, field_elev, wind, poh_rec, air=None):
    """All Q2 measures for one approach. hat: height above threshold used for gates (indicated, primary)."""
    P = v["pts"]
    t = P["t"]
    passes = v["passes"]
    p = passes[p_idx]
    # the approach starts after the latest earlier pass that ended before it (passes are not in time order)
    j_lo = max([q["i1"] for qi, q in enumerate(passes) if qi != p_idx and q["i1"] < p["i0"]] + [-1]) + 1
    cand = [i for i in range(p["i0"], p["i1"] + 1) if hat[i] is not None]
    if not cand:
        return {"status": "no_height"}
    j_low = min(cand, key=lambda i: hat[i])
    n = len(t)
    al = [None] * n
    lr = [None] * n
    for i in range(j_lo, min(n, j_low + 1)):
        al[i], lr[i] = frame.along_lateral(P["lat"][i], P["lon"][i])
    terr = [sdiff(P["trk"][i], frame.course) if isinstance(P["trk"][i], (int, float)) else None for i in range(n)]
    tan_g = math.tan(math.radians(g["gpa"]))

    def ref_h(a):
        return g["tch"] + max(0.0, -a) * tan_g

    out = {"status": None, "lowest_hat": round(hat[j_low], 1), "lowest_along_nm": round(al[j_low] / FT_PER_NM, 3),
           "lowest_time": round(t[j_low], 1)}
    drct, sknt, gdrct, gsknt, wsrc = wind if wind else (None, None, None, None, None)
    hw = xw_r = None
    if sknt is not None:
        if sknt == 0 or drct is None:
            hw, xw_r = 0.0, 0.0
        else:
            hw = sknt * math.cos(math.radians(drct - frame.course))
            xw_r = sknt * math.sin(math.radians(drct - frame.course))
    gust_spread = max(0.0, gsknt - sknt) if (gsknt is not None and sknt is not None) else 0.0
    gxw = None
    if gsknt is not None and gdrct is not None:
        gxw = abs(gsknt * math.sin(math.radians(gdrct - frame.course)))
    out.update({"wind_src": wsrc, "wind_drct": drct, "wind_kt": sknt, "gust_kt": gsknt, "gust_spread": round(gust_spread, 1),
                "hw_kt": None if hw is None else round(hw, 2), "xw_right_kt": None if xw_r is None else round(xw_r, 2),
                "xw_kt": None if xw_r is None else round(abs(xw_r), 2), "gust_xw_kt": None if gxw is None else round(gxw, 2)})

    def point_ratios(i):
        r = {}
        if lr[i] is not None:
            r["c1"] = abs(lr[i]) / TOL["c1"]
        if terr[i] is not None:
            r["c2a"] = abs(terr[i]) / TOL["c2a"]
        if al[i] is not None and al[i] <= 0 and hat[i] is not None:
            r["c3"] = abs(hat[i] - ref_h(al[i])) / TOL["c3"]
        d = descent_rate(P, i, hat)
        gs = P["gs"][i]
        if d is not None and gs is not None:
            r["c4"] = abs(d - gs * FPM_PER_KT * tan_g) / TOL["c4"]
        d_raw = descent_rate(P, i, hat, smooth=False)
        if d_raw is not None and gs is not None:
            r["c4raw"] = abs(d_raw - gs * FPM_PER_KT * tan_g) / TOL["c4"]
        return r, d

    def gate_values(h_arr, gate):
        cr, status = find_crossing(h_arr, t, j_lo, j_low, gate)
        if status != "ok":
            return status, None
        a, b, f, tg = cr
        lat_a, lat_b = lr[a], lr[b]
        lat_g = interp(lat_a, lat_b, f)
        al_g = interp(al[a], al[b], f)
        trk_g = interp_angle(P["trk"][a], P["trk"][b], f)
        gs_g = interp(P["gs"][a], P["gs"][b], f)
        da, db = descent_rate(P, a, h_arr), descent_rate(P, b, h_arr)
        d_g = interp(da, db, f) if da is not None and db is not None else (da if da is not None else db)
        ra, rb = descent_rate(P, a, h_arr, smooth=False), descent_rate(P, b, h_arr, smooth=False)
        d_raw = interp(ra, rb, f) if ra is not None and rb is not None else (ra if ra is not None else rb)
        gv = {"k": a, "kb": b, "tg": tg, "lat": lat_g, "along": al_g, "trk_err": None if trk_g is None else sdiff(trk_g, frame.course),
              "gs": gs_g, "descent": d_g}
        gv["c1"] = abs(lat_g) / TOL["c1"] if lat_g is not None else None
        gv["c2a"] = abs(gv["trk_err"]) / TOL["c2a"] if gv["trk_err"] is not None else None
        gv["c3"] = abs(gate - ref_h(al_g)) / TOL["c3"] if al_g is not None else None
        gv["req"] = gs_g * FPM_PER_KT * tan_g if gs_g is not None else None
        gv["c4"] = abs(d_g - gv["req"]) / TOL["c4"] if d_g is not None and gv["req"] is not None else None
        gv["c4raw"] = abs(d_raw - gv["req"]) / TOL["c4"] if d_raw is not None and gv["req"] is not None else None
        # C5b speed stability: estimated airspeed range over the 30 s before the gate
        w = [i for i in range(j_lo, b) if tg - 30 <= t[i] <= tg and P["gs"][i] is not None]
        eas = None
        if hw is not None and len(w) >= 4 and t[w[-1]] - t[w[0]] >= 20:
            # calibrated airspeed (groundspeed and headwind are known for every point in w)
            eas = [est_airspeed(P["gs"][i], track_headwind(drct, sknt, P["trk"][i], hw),
                                hat_true[i] if hat_true[i] is not None else h_arr[i]) * cas_factor(field_elev, h_arr[i], air)
                   for i in w]
        if eas is not None:
            gv["c5b"] = (max(eas) - min(eas)) / TOL["c5b"]
            gv["as_range"] = max(eas) - min(eas)
            # audit variants (2026-10-02): range around a straight-line trend (a steady slowdown to
            # approach speed does not count), and the range over the last 15 s only
            tt = [t[i] - tg for i in w]
            tm = sum(tt) / len(tt)
            em = sum(eas) / len(eas)
            sxx = sum((x - tm) ** 2 for x in tt)
            slope = sum((x - tm) * (e - em) for x, e in zip(tt, eas)) / sxx if sxx > 0 else 0.0
            res = [e - (em + slope * (x - tm)) for x, e in zip(tt, eas)]
            gv["c5b_detr"] = (max(res) - min(res)) / TOL["c5b"]
            w15 = [k for k, x in enumerate(tt) if x >= -15]
            gv["c5b_15"] = ((max(eas[k] for k in w15) - min(eas[k] for k in w15)) / TOL["c5b"]
                            if len(w15) >= 3 and tt[w15[-1]] - tt[w15[0]] >= 10 else None)
        else:
            gv["c5b"] = gv["as_range"] = gv["c5b_detr"] = gv["c5b_15"] = None
        # C5a airspeed against the POH target (secondary)
        gv["est_tas"] = est_airspeed(gs_g, track_headwind(drct, sknt, trk_g, hw), gate)
        gv["cas_factor"] = cas_factor(field_elev, gate, air)
        gv["est_as"] = None if gv["est_tas"] is None else gv["est_tas"] * gv["cas_factor"]
        gv["c5a"] = None
        if poh_rec and poh_rec["approach_kias"] and gv["est_as"] is not None:
            dev = gv["est_as"] - (poh_rec["approach_kias"] + 0.5 * gust_spread)
            gv["c5a"] = -dev / 5.0 if dev < 0 else dev / 10.0
        # C2b inferred bank over the previous 10 s (secondary)
        gv["c2b"] = gv["bank"] = None
        prev = [i for i in range(j_lo, b) if tg - 14 <= t[i] <= tg - 6 and P["trk"][i] is not None]
        if prev and trk_g is not None and gv["est_tas"] is not None:
            i0 = min(prev, key=lambda i: abs(t[i] - (tg - 10)))
            rate = math.radians(sdiff(trk_g, P["trk"][i0])) / max(tg - t[i0], 1.0)
            gv["bank"] = math.degrees(math.atan(gv["est_tas"] * 0.514444 * rate / G))
            gv["c2b"] = abs(gv["bank"]) / TOL["c2b"]
        return "ok", gv

    status, gv = gate_values(hat, GATE)
    out["status"] = status
    status_t, gv_t = gate_values(hat_true, GATE)
    out["status_true"] = status_t
    status2, gv2 = gate_values(hat, GATE2)
    out["status_500"] = status2
    out["coupled"] = None

    # straight-in check: walk back from the approach's lowest point
    straight = "unknown"
    for i in range(j_low, j_lo - 1, -1):
        if i < j_low and t[i + 1] - t[i] > 30:
            break
        if terr[i] is None or al[i] is None:
            continue
        if abs(terr[i]) > STRAIGHT_IN_DEG and al[i] < 0:
            straight = "no"
            break
        if al[i] <= -STRAIGHT_IN_NM * FT_PER_NM:
            straight = "yes"
            break
    out["straight_in"] = straight

    if gv2:
        for k in ("c1", "c2a", "c3", "c4", "c5b"):
            out[f"g500_{k}"] = None if gv2[k] is None else round(gv2[k], 3)
        vals = [gv2[k] for k in ("c1", "c2a", "c3", "c4", "c5b") if gv2[k] is not None]
        out["s500"] = round(max(vals), 3) if vals else None

    if gv_t:
        vals = [gv_t[k] for k in ("c1", "c2a", "c3", "c4", "c5b") if gv_t[k] is not None]
        below = []
        for i in range(gv_t["kb"], j_low + 1):
            if hat_true[i] is not None and hat_true[i] >= FLOOR_HAT:
                r, _ = point_ratios(i)
                below += [x for c, x in r.items() if c != "c4raw"]
        out["s_true"] = round(max(vals + below), 3) if vals else None

    if not gv:
        return out

    k, kb, tg = gv["k"], gv["kb"], gv["tg"]
    modes = P["modes"][k] or ""
    out["coupled"] = int("autopilot" in modes and "approach" in modes)
    out.update({"gate_time": round(tg, 1), "gate_along_nm": round(gv["along"] / FT_PER_NM, 3), "gate_lat_ft": round(gv["lat"], 1),
                "gate_trk_err": None if gv["trk_err"] is None else round(gv["trk_err"], 2), "gate_gs": gv["gs"],
                "gate_descent_fpm": None if gv["descent"] is None else round(gv["descent"]),
                "gate_req_fpm": None if gv["req"] is None else round(gv["req"]),
                "gate_est_as": None if gv["est_as"] is None else round(gv["est_as"], 1),
                "gate_est_tas": None if gv["est_tas"] is None else round(gv["est_tas"], 1),
                "cas_factor": round(gv["cas_factor"], 4),
                "gate_as_range": None if gv["as_range"] is None else round(gv["as_range"], 1),
                "gate_bank": None if gv["bank"] is None else round(gv["bank"], 1)})
    for c in ("c1", "c2a", "c2b", "c3", "c4", "c4raw", "c5a", "c5b"):
        out[f"g_{c}"] = None if gv[c] is None else round(gv[c], 3)

    # below the gate to the floor
    below = defaultdict(float)
    below50 = 0.0
    sink_flag = level_run = level_flag = 0
    seg = []   # (descent, required) from the gate down to the floor, for the sink-rate audit variants
    if gv["descent"] is not None and gv["req"] is not None:
        seg.append((gv["descent"], gv["req"]))
    for i in range(kb, j_low + 1):
        if hat[i] is None:
            continue
        r, d = point_ratios(i)
        if hat[i] >= FLOOR_HAT:
            for c, x in r.items():
                below[c] = max(below[c], x)
            if d is not None and P["gs"][i] is not None:
                seg.append((d, P["gs"][i] * FPM_PER_KT * tan_g))
            # speed value below the gate: estimated airspeed against the POH target (deficit / 5 kt, excess / 10 kt)
            if poh_rec and poh_rec["approach_kias"] and P["gs"][i] is not None:
                ea = est_airspeed(P["gs"][i], track_headwind(drct, sknt, P["trk"][i], hw), hat_true[i] if hat_true[i] is not None else hat[i])
                if ea is not None:
                    ea *= cas_factor(field_elev, hat[i], air)
                    dv = ea - (poh_rec["approach_kias"] + 0.5 * gust_spread)
                    below["c5a"] = max(below["c5a"], -dv / 5.0 if dv < 0 else dv / 10.0)
        if hat[i] >= FLOOR_HAT_SENS:
            below50 = max([below50] + [x for c, x in r.items() if c != "c4raw"])
        if d is not None:
            sink_flag |= d > 1000
            level_run = level_run + 1 if (d <= 0 and i < j_low) else 0
            level_flag |= level_run >= 2
    if gv["descent"] is not None:
        sink_flag |= gv["descent"] > 1000
    for c in ("c1", "c2a", "c3", "c4", "c4raw", "c5a"):
        out[f"b_{c}"] = round(below[c], 3) if c in below else None
    gate_vals = [gv[c] for c in ("c1", "c2a", "c3", "c4", "c5b") if gv[c] is not None]
    below_vals = [below[c] for c in below if c not in ("c4raw", "c5a")]
    raw_vals = [gv[c] for c in ("c1", "c2a", "c3", "c4raw", "c5b") if gv[c] is not None] + \
        [below[c] for c in below if c not in ("c4", "c5a")]
    out["s_c4raw"] = round(max(raw_vals), 3) if raw_vals else None
    # sink-rate audit variants (2026-10-02). AFH-literal: 1,000 fpm sink is the edge (ratio d / 1000) on the
    # steep side, level flight is the edge on the shallow side (ratio (req - d) / req). Stability: deviation
    # from the approach's own median descent rate between 300 and 100 ft, tolerance 300 fpm.
    def afh(d, req):
        return d / 1000.0 if d >= req else ((req - d) / req if req > 0 else 0.0)
    if seg:
        out["g_c4_afh"] = round(afh(*seg[0]), 3) if gv["descent"] is not None and gv["req"] is not None else None
        out["b_c4_afh"] = round(max(afh(d, q) for d, q in seg), 3)
        med = statistics.median(d for d, _ in seg)
        out["c4_stab"] = round(max(abs(d - med) for d, _ in seg) / TOL["c4"], 3) if len(seg) >= 3 else None
        out["seg_median_descent"] = round(med)
    for c in ("c5b_detr", "c5b_15"):
        out[f"g_{c}"] = None if gv.get(c) is None else round(gv[c], 3)
    out["s_gate"] = round(max(gate_vals), 3) if gate_vals else None
    out["s_below"] = round(max(below_vals), 3) if below_vals else None
    out["s"] = round(max(gate_vals + below_vals), 3) if gate_vals else None
    out["s_below50"] = round(below50, 3)
    out["s_has_c5b"] = int(gv["c5b"] is not None)
    out["flag_sink_1000"] = int(bool(sink_flag))
    out["flag_level"] = int(bool(level_flag))

    # M3 alignment
    def aligned(i):
        return lr[i] is not None and terr[i] is not None and hat[i] is not None \
            and abs(lr[i]) <= TOL["c1"] and abs(terr[i]) <= TOL["c2a"]
    align_i, censored = None, 0
    if gv["c1"] is not None and gv["c1"] <= 1 and gv["c2a"] is not None and gv["c2a"] <= 1:
        m = k if aligned(k) else kb
        while m - 1 >= j_lo and aligned(m - 1) and t[m] - t[m - 1] <= ALIGN_GAP_S:
            m -= 1
        censored = int(m - 1 < j_lo or t[m] - t[m - 1] > ALIGN_GAP_S or (P["trk"][m - 1] is None))
        align_i = m
    else:
        tail = [i for i in range(kb, j_low + 1) if hat[i] is not None]
        for idx, i in enumerate(tail):
            if all(aligned(j) for j in tail[idx:]):
                align_i = i
                break
    out["align_hat"] = None if align_i is None else round(hat[align_i], 1)
    out["align_censored"] = censored
    out["never_aligned"] = int(align_i is None)
    out["final_length_nm"] = None if align_i is None else round(-al[align_i] / FT_PER_NM, 3)

    # M2 overshoot from a base leg
    stop = align_i if align_i is not None else j_low
    base_i = None
    for i in range(stop, j_lo - 1, -1):
        if i < stop and t[i + 1] - t[i] > ALIGN_GAP_S:
            break
        if terr[i] is not None and abs(terr[i]) >= BASE_DEG:
            base_i = i
            break
    side = None
    if base_i is not None and lr[base_i] is not None and abs(lr[base_i]) >= 100:
        side = 1 if lr[base_i] > 0 else -1
    out["base_side"] = {1: "right", -1: "left", None: None}[side]
    out["nasr_right_traffic"] = int(g["right_traffic"])
    if side is not None:
        seg = [i for i in range(base_i, stop + 1) if lr[i] is not None]
        out["overshoot_ft"] = round(max([0.0] + [-side * lr[i] for i in seg]), 1)
        banks = []
        for i in seg[1:-1]:
            if P["trk"][i - 1] is None or P["trk"][i + 1] is None or t[i + 1] - t[i - 1] <= 0:
                continue
            rate = math.radians(sdiff(P["trk"][i + 1], P["trk"][i - 1])) / (t[i + 1] - t[i - 1])
            spd = est_airspeed(P["gs"][i], track_headwind(drct, sknt, P["trk"][i], hw) or 0.0, hat[i])
            if spd is not None:
                banks.append(abs(math.degrees(math.atan(spd * 0.514444 * rate / G))))
        out["turn_max_bank"] = round(max(banks), 1) if banks else None
        out["turn_start_along_nm"] = round(al[base_i] / FT_PER_NM, 3)
        out["xw_from_base_kt"] = None if xw_r is None else round(side * xw_r, 2)
        # M5 downwind on the same side before the base leg
        dw = [i for i in range(j_lo, base_i) if terr[i] is not None and abs(terr[i]) >= 160 and lr[i] is not None
              and side * lr[i] >= 0.3 * FT_PER_NM and abs(lr[i]) <= 2 * FT_PER_NM and al[i] is not None
              and -0.5 * FT_PER_NM <= al[i] <= frame.length_ft + 0.5 * FT_PER_NM and P["agl_ind"][i] is not None]
        if len(dw) >= 5:
            tpa_agl = (g["tpa_msl"] - field_elev) if g["tpa_msl"] else 1000.0
            h = statistics.median(P["agl_ind"][i] for i in dw)
            out["dw_alt_dev_ft"] = round(h - tpa_agl, 1)
            out["dw_alt_ratio"] = round(abs(h - tpa_agl) / 100.0, 3)
            out["dw_spacing_nm"] = round(statistics.median(abs(lr[i]) for i in dw) / FT_PER_NM, 3)
            out["dw_spacing_sd_nm"] = round(statistics.pstdev([abs(lr[i]) for i in dw]) / FT_PER_NM, 3)

    # M4 variability on final
    top = min(out["align_hat"] if out["align_hat"] is not None else GATE2, GATE2)
    seg = [i for i in range(j_lo, j_low + 1) if hat[i] is not None and 200 <= hat[i] <= top
           and (align_i is None or i >= align_i)]
    rates = [descent_rate(P, i, hat) for i in seg]
    rates = [r for r in rates if r is not None]
    if len(seg) >= 5 and len(rates) >= 5:
        out["m4_sd_descent"] = round(statistics.pstdev(rates), 1)
        out["m4_sd_lat_ft"] = round(statistics.pstdev([lr[i] for i in seg]), 1)
        out["m4_n"] = len(seg)

    # practice flags
    p1 = (align_i is None or hat[align_i] < GATE) and base_i is not None and al[base_i] is not None \
        and al[base_i] >= -P1_TURN_NM * FT_PER_NM
    p2 = 0
    if gv2:
        a2, b2 = gv2["k"], gv["kb"]
        dist = 0.0
        for i in range(a2, b2):
            x0, y0 = frame.xy(P["lat"][i], P["lon"][i])
            x1, y1 = frame.xy(P["lat"][i + 1], P["lon"][i + 1])
            dist += math.hypot(x1 - x0, y1 - y0)
        if dist > 0:
            ang = math.degrees(math.atan((GATE2 - GATE) / dist))
            out["descent_angle_500_300"] = round(ang, 2)
            p2 = int(ang > P2_DEG)
    out["flag_p1_power_off"] = int(bool(p1))
    out["flag_p2_steep"] = p2
    out["flag_practice"] = int(bool(p1) or bool(p2))

    # validation fields at the gate
    near = k if abs(t[k] - tg) <= abs(t[kb] - tg) else kb
    out["nacp"] = P["nacp"][near]
    out["gva"] = P["gva"][near]
    out["src"] = P["src"][near]
    out["qnh_hpa"] = P["qnh"][near]
    gh = P["geom"][near]
    out["hat_true_minus_geom_ft"] = None if gh is None or hat_true[near] is None else \
        round(hat_true[near] - (gh + cov.AIRPORTS.get("K" + "X", {}).get("geoid_offset_ft", 93.5) - g["thr_elev"]), 1)
    out["vr_baro"] = P["vr"][near]
    out["vr_geom"] = P["gvr"][near]
    out["ias_reported"] = P["ias"][near]
    return out


# ---------------------------------------------------------------- driver

def group_of(rec, category):
    if rec:
        if rec["ownership"] == "commercial":
            return "commercial"
        if rec["piston_fixed_wing"]:
            return "piston"
        if rec["type_engine"] in ("turbofan", "turbojet"):
            return "jet"
        if rec["type_engine"] == "turboprop":
            return "turboprop"
        return "other"
    if category in ("A3", "A4", "A5"):
        return "jet"
    return "unregistered"


_RULE12 = {}


def apply_rule12(v, apt, apt_name):
    """Detector v3.1 (rule 12, parallel runways) on a stored visit: v3.0.1 and v3.1 are both rerun on the
    stored points, and the visit's passes are replaced only where the two differ, so rounding in the
    stored points cannot move anything rule 12 does not touch. Returns True if the passes changed."""
    import importlib.util
    import ops_detector as od31
    import runway_use as ru
    if "od301" not in _RULE12:
        spec = importlib.util.spec_from_file_location("od301", "notes/ops_detector_v3.0.1_2026-10-02.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _RULE12["od301"] = m
        _RULE12["side"] = json.load(open("us_parallel/side_reliable.json"))["reliable"]
    if apt_name not in _RULE12:
        _RULE12[apt_name] = ru.runway_ends(apt)
    ends = _RULE12[apt_name]
    if not od31.parallel_groups(ends):
        return False
    P = v["pts"]

    def arrays():
        xy = [cov.to_xy_nm(la, lo, apt.lat, apt.lon) for la, lo in zip(P["lat"], P["lon"])]
        return {"t": P["t"], "x": [x for x, _ in xy], "y": [y for _, y in xy], "agl": list(P["agl"]),
                "trk": P["trk"], "vr": list(P["vr"]), "gnd": [1 if g else 0 for g in P["gnd"]]}
    key = lambda ps: sorted((p["kind"], p["runway"], p["i0"], p["i1"], p["inferred"] or "") for p in ps)
    p301 = _RULE12["od301"].detect(arrays(), ends)
    p31 = od31.detect(arrays(), ends, set(_RULE12["side"].get(apt_name, [])))
    if key(p31) == key(p301):
        return False
    v["passes"] = [{k: p.get(k) for k in ("kind", "runway", "i0", "i1", "min_agl", "inferred")} for p in p31]
    return True


def process_month(args):
    """One airport-month. args: (airport, month, start, end) for New England, or with a fifth element "us"
    for the confirmatory sample (us_airports.py geometry, weather station, and local time zone)."""
    apt_name, month, start, end = args[:4]
    global PROFILE_EXP, AIRSPEED
    us = len(args) > 4 and args[4] == "us"
    redetect = us and len(args) > 5 and args[5]
    opts = args[6] if len(args) > 6 else {}
    PROFILE_EXP = opts.get("profile_exp", PROFILE_EXP)
    AIRSPEED = opts.get("airspeed", AIRSPEED)
    if us:
        import us_airports as ua
        site = ua.load()[apt_name]
        apt, station, tz, extract_dir = site.apt, site.station, site.tz, "q2_extract_us"
    else:
        apt, station, tz, extract_dir = tc.make_airport("K" + apt_name), apt_name, tc.LOCAL, "q2_extract"
    geo = load_runway_geometry({apt_name})
    # NASR has a few runway ends without coordinates or elevation; those ends get no frame and their
    # approaches are counted as no_runway_geometry
    geo = {k: g for k, g in geo.items()
           if None not in (g["end_lat"], g["end_lon"], g["far_lat"], g["far_lon"], g["thr_lat"], g["thr_lon"], g["thr_elev"])}
    frames = {e: Frame(g, apt) for (a, e), g in geo.items()}
    onemin = load_onemin_month(station, month)
    metars, mtimes = load_metars(station)
    onemin, _ = wind_qc.qc_onemin(onemin, mtimes, [o["sknt"] for o in metars])
    rows, counts = [], Counter()
    for path in sorted(glob.glob(os.path.join(extract_dir, apt_name, f"{month}-*.jsonl.gz"))):
        day = os.path.basename(path)[:10]
        if not (start <= day <= end):
            continue
        with gzip.open(path, "rt") as f:
            visits = [json.loads(line) for line in f if line.strip()]
        if redetect:
            counts["visits_changed_by_rule12"] += sum(apply_rule12(v, apt, apt_name) for v in visits)
        for vi, v in enumerate(visits):
            P = v["pts"]
            napp = sum(1 for q in v["passes"] if q["kind"] == "approach")
            res = baro_resolution(P)
            vr_orig = list(P["vr"])
            n_frozen = clean_velocity(P, apt)
            hyb = calibrated_gnss_heights(P, apt) if res == 100 else None
            P["_coarse"] = res == 100
            if hyb:
                hyb = (clean_heights(hyb[0], P["t"], vr_orig), clean_heights(hyb[1], P["t"], vr_orig))
            else:
                P["agl_ind"] = clean_heights(P["agl_ind"], P["t"], vr_orig)
                P["agl"] = clean_heights(P["agl"], P["t"], vr_orig)
            rec = fr.lookup(v["icao"], day)
            grp = group_of(rec, v["category"])
            year = int(rec["year_mfr"]) if rec and rec.get("year_mfr", "").strip().isdigit() else None
            poh_rec = poh.lookup(v["type"], rec["model"] if rec else "", year) if grp == "piston" else None
            app_no = 0
            for pi, p in enumerate(v["passes"]):
                if p["kind"] != "approach":
                    continue
                app_no += 1
                counts["approaches"] += 1
                g = geo.get((apt_name, p["runway"]))
                if g is None or p["runway"] not in frames:
                    counts["no_runway_geometry"] += 1
                    continue
                frame = frames[p["runway"]]
                off = apt.elev_ft - g["thr_elev"]
                src_ind, src_true = (hyb if hyb else (P["agl_ind"], P["agl"]))
                hat = [None if (a if a is not None else b) is None else (a if a is not None else b) + off
                       for a, b in zip(src_ind, src_true)]
                hat_true = [None if a is None else a + off for a in src_true]
                t_ref = P["t"][p["i1"]]
                wind = gate_wind(t_ref, onemin, metars, mtimes)
                o_air = metar_near(metars, mtimes, t_ref, max_s=90 * 60)
                air = (o_air["temp_c"], o_air["alt_inhg"]) if o_air else None
                m = measure(v, pi, frame, g, hat, hat_true, apt.elev_ft, wind, poh_rec, air)
                if m.get("gate_time"):
                    wind = gate_wind(m["gate_time"], onemin, metars, mtimes)
                    m = measure(v, pi, frame, g, hat, hat_true, apt.elev_ft, wind, poh_rec, air)
                m["air_temp_c"] = air[0] if air else None
                # Q1b wind: at the minute of the approach's lowest observed point
                wl = gate_wind(m["lowest_time"], onemin, metars, mtimes) if m.get("lowest_time") else None
                if wl and wl[1] is not None:
                    d0, s0, gd, gs_ = wl[0], wl[1], wl[2], wl[3]
                    m["wind_src_low"] = wl[4]
                    m["xw_low_kt"] = 0.0 if (s0 == 0 or d0 is None) else round(abs(s0 * math.sin(math.radians(d0 - frame.course))), 2)
                    m["gust_xw_low_kt"] = None if (gs_ is None or gd is None) else round(abs(gs_ * math.sin(math.radians(gd - frame.course))), 2)
                t_obs = m.get("gate_time") or t_ref
                o = metar_near(metars, mtimes, t_obs)
                vmc = None if o is None else int((o["ceiling"] is None or o["ceiling"] >= 3000) and o["vis"] is not None
                                                 and o["vis"] >= 5 and not o["precip"])
                lt = dt.datetime.fromtimestamp(t_obs, tz)
                counts[f"status_{m['status']}"] += 1
                rows.append({
                    "airport": apt_name, "date": day, "local_time": lt.strftime("%H:%M:%S"), "local_hour": lt.hour,
                    "visit": f"{day}:{vi}", "icao": v["icao"], "type": v["type"], "category": v["category"],
                    "group": grp, "ownership": rec["ownership"] if rec else "", "model": rec["model"] if rec else "",
                    "year_mfr": year, "runway": p["runway"], "inferred": p.get("inferred") or "",
                    "app_no": app_no, "apps_in_visit": napp,
                    "gpa": g["gpa"], "gpa_default": int(g["gpa_default"]), "tch": g["tch"],
                    "poh_xwind_kt": poh_rec["xwind_kt"] if poh_rec else None,
                    "poh_xwind_basis": poh_rec["xwind_basis"] if poh_rec else "",
                    "poh_approach_kias": poh_rec["approach_kias"] if poh_rec else None,
                    "vmc": vmc, "metar_alt_inhg": o["alt_inhg"] if o else None,
                    "baro_res": res, "frozen_vel_pts": n_frozen, "height_source": "gnss_calibrated" if hyb else ("baro_coarse" if res == 100 else "baro"), **m})
    return apt_name, month, rows, counts


FIELDS = ["airport", "date", "local_time", "local_hour", "visit", "icao", "type", "category", "group", "ownership", "model",
          "year_mfr", "baro_res", "frozen_vel_pts", "height_source", "runway", "inferred", "app_no", "apps_in_visit", "gpa", "gpa_default", "tch", "poh_xwind_kt",
          "poh_xwind_basis", "poh_approach_kias", "vmc", "status", "status_true", "status_500", "straight_in", "coupled",
          "lowest_hat", "lowest_along_nm", "lowest_time", "wind_src_low", "xw_low_kt", "gust_xw_low_kt", "wind_src", "wind_drct", "wind_kt", "gust_kt", "gust_spread", "hw_kt",
          "xw_right_kt", "xw_kt", "gust_xw_kt", "gate_time", "gate_along_nm", "gate_lat_ft", "gate_trk_err", "gate_gs",
          "gate_descent_fpm", "gate_req_fpm", "gate_est_as", "gate_as_range", "gate_bank",
          "g_c1", "g_c2a", "g_c2b", "g_c3", "g_c4", "g_c4raw", "g_c5a", "g_c5b", "b_c1", "b_c2a", "b_c3", "b_c4", "b_c4raw",
          "s", "s_gate", "s_below", "s_below50", "s_true", "s_c4raw", "s_has_c5b", "s500",
          "g_c4_afh", "b_c4_afh", "c4_stab", "seg_median_descent", "g_c5b_detr", "g_c5b_15", "b_c5a",
          "g500_c1", "g500_c2a", "g500_c3", "g500_c4", "g500_c5b", "flag_sink_1000", "flag_level",
          "align_hat", "align_censored", "never_aligned", "final_length_nm", "base_side", "nasr_right_traffic",
          "overshoot_ft", "turn_max_bank", "turn_start_along_nm", "xw_from_base_kt",
          "dw_alt_dev_ft", "dw_alt_ratio", "dw_spacing_nm", "dw_spacing_sd_nm", "m4_sd_descent", "m4_sd_lat_ft", "m4_n",
          "descent_angle_500_300", "flag_p1_power_off", "flag_p2_steep", "flag_practice",
          "nacp", "gva", "src", "qnh_hpa", "metar_alt_inhg", "hat_true_minus_geom_ft", "vr_baro", "vr_geom", "ias_reported",
          "gate_est_tas", "cas_factor", "air_temp_c"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--airports", default="BDR,HVN,BED,LWM,OWD,PYM,TAN")
    ap.add_argument("--start", default="2023-02-16")
    ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--us", action="store_true", help="confirmatory sample: every airport in q2_extract_us/")
    ap.add_argument("--rule12", action="store_true", help="US only: detector v3.1 passes where rule 12 changes a visit")
    ap.add_argument("--profile-exp", type=float, default=PROFILE_EXP, help="wind profile exponent (registered 1/7)")
    ap.add_argument("--airspeed", choices=("cas", "tas"), default=AIRSPEED,
                    help="cas (primary): compare calibrated airspeed with POH speeds; tas: the uncorrected runs")
    args = ap.parse_args()
    extract_dir = "q2_extract_us" if args.us else "q2_extract"
    airports = sorted(os.listdir(extract_dir)) if args.us else [a.strip().upper() for a in args.airports.split(",")]
    months = sorted({os.path.basename(p)[:7] for a in airports for p in glob.glob(os.path.join(extract_dir, a, "*.jsonl.gz"))})
    months = [m for m in months if args.start[:7] <= m <= args.end[:7]]
    opts = {"profile_exp": args.profile_exp, "airspeed": args.airspeed}
    tasks = [(a, m, args.start, args.end, "us" if args.us else "", args.rule12, opts) for a in airports for m in months]
    os.makedirs(args.out, exist_ok=True)
    total = Counter()
    with open(os.path.join(args.out, "approaches.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        with ProcessPoolExecutor(args.workers) as ex:
            for apt_name, month, rows, counts in ex.map(process_month, tasks):
                w.writerows(rows)
                total.update(counts)
    lines = [f"{k}: {v:,}" for k, v in sorted(total.items())]
    open(os.path.join(args.out, "counts.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
