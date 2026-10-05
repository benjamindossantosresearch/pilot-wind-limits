#!/usr/bin/env python3
"""
us_tower_spotcheck_plot.py

Plan view and height profile of one visit from the per-airport extracts, for
checking the classes in us_tower_spotcheck.py by eye. Detected passes are
marked (approach A, climb C) with their runway.

    python3 us_tower_spotcheck_plot.py HWO 2026-03-14 ad84f6 [HH:MM]

Writes us_tower_compare/spotcheck_tracks/<AIRPORT>_<date>_<icao>_<HHMM>.png.
The plots show individual aircraft and stay local (not for publication).
"""

import datetime as dt
import gzip
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import adsb_airport_coverage as cov
import runway_use as ru
import us_airports as ua

OUT = "us_tower_compare/spotcheck_tracks"


def find_visit(a, date, icao, hhmm=None):
    site = ua.load()[a]
    d = dt.date.fromisoformat(date)
    best = None
    for utc in (d, d + dt.timedelta(days=1)):
        path = os.path.join("q2_extract_us", a, f"{utc}.jsonl.gz")
        if not os.path.exists(path):
            continue
        with gzip.open(path, "rt") as f:
            for line in f:
                rec = json.loads(line)
                if rec["icao"] != icao:
                    continue
                t = rec["pts"]["t"]
                if hhmm:
                    h, m = map(int, hhmm.split(":")[:2])
                    target = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=site.tz).timestamp()
                    gap = 0 if t[0] - 60 <= target <= t[-1] + 60 else min(abs(t[0] - target), abs(t[-1] - target))
                else:
                    gap = 0
                if best is None or gap < best[0]:
                    best = (gap, rec)
    return site, best[1] if best else None


def plot(a, date, icao, hhmm=None):
    site, rec = find_visit(a, date, icao, hhmm)
    if rec is None:
        print("visit not found")
        return None
    apt, tz = site.apt, site.tz
    p = rec["pts"]
    xy = [cov.to_xy_nm(la, lo, apt.lat, apt.lon) for la, lo in zip(p["lat"], p["lon"])]
    h = [0 if g else v for g, v in zip(p["gnd"], p["agl"])]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 5.5), gridspec_kw={"width_ratios": [1, 1.2]})
    for e in ru.runway_ends(apt):
        fx, fy = e.tx + e.ux * e.length, e.ty + e.uy * e.length
        ax.plot([e.tx, fx], [e.ty, fy], color="0.3", lw=3, solid_capstyle="butt")
        ax.text(e.tx - e.ux * 0.12, e.ty - e.uy * 0.12, e.name, fontsize=8, ha="center", va="center", color="0.2")
    sc = ax.scatter([q[0] for q in xy], [q[1] for q in xy], c=[v if v is not None else -1 for v in h], cmap="viridis",
                    vmin=0, vmax=1200, s=10, zorder=3)
    ax.plot([q[0] for q in xy], [q[1] for q in xy], color="0.6", lw=0.6, zorder=2)
    t0 = p["t"][0]
    for k, ps in enumerate(rec["passes"]):
        i = ps["i0"]
        lab = ("A" if ps["kind"] == "approach" else "C") + ps["runway"]
        ax.annotate(f"{k + 1}:{lab}", xy[i], fontsize=8, color="crimson", zorder=4,
                    xytext=(4, 4), textcoords="offset points")
        bx.axvspan(p["t"][ps["i0"]] - t0, p["t"][ps["i1"]] - t0 + 1, color="crimson" if ps["kind"] == "approach" else "royalblue", alpha=0.2)
        bx.text(p["t"][ps["i0"]] - t0, 0.02, f"{k + 1}:{lab}", fontsize=8, rotation=90, va="bottom", transform=bx.get_xaxis_transform())
    ax.set_aspect("equal")
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(-2.5, 2.5)
    ax.set_xlabel("nm east of airport reference point")
    ax.set_ylabel("nm north")
    fig.colorbar(sc, ax=ax, label="height above field, ft", shrink=0.7)
    bx.plot([t - t0 for t in p["t"]], [v if v is not None else float("nan") for v in h], ".-", ms=3, lw=0.8)
    bx.set_xlabel("seconds from first point")
    bx.set_ylabel("height above field, ft")
    bx.grid(alpha=0.3)
    start = dt.datetime.fromtimestamp(t0, tz).strftime("%H:%M")
    fig.suptitle(f"{a} {date} {start} local, {rec['type']}, passes: " +
                 ", ".join(f"{k + 1} {q['kind']} {q['runway']} (lowest {q['min_agl']})" for k, q in enumerate(rec["passes"]))[:200],
                 fontsize=9)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{a}_{date}_{icao}_{start.replace(':', '')}.png")
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)
    print(path)
    return path


if __name__ == "__main__":
    plot(*sys.argv[1:5])
