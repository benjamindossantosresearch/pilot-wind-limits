#!/usr/bin/env python3
"""
make_fig_results.py

Results figures from paper/figures/data/ (make_fig_data.py) and the frozen Q1a summaries,
in the shared style (figstyle.py).

  activity.pdf     Fig. 2: traffic as a percent of normal against crosswind, with the
                   revealed limits marked and each line labeled where it ends
  calibration.pdf  Fig. 3: (a) traffic and (b) the change from calm in the share of
                   approaches beyond tolerance, on one crosswind scale, with the revealed
                   limit and the typical maximum demonstrated crosswind
  direction.pdf    Fig. 4: (a) what each wind side does to the turn to final, (b) overshoot
                   and (c) late alignment by the crosswind component relative to the base leg

    cd /home/dev/wind-limits && python3 paper/figures/make_fig_results.py
"""

import os
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import figstyle as fs  # noqa: E402

D = os.path.join(HERE, "data")
# Calm baseline = crosswind below 5 kt, the 0-4 kt band of the tables (changed 2026-10-05 from the 2 kt bins below 4 kt)
BANDS = os.path.join(HERE, "..", "..", "q2_us_results_v31_cas", "bands.csv")
BAND_TABLE = {("piston", "S_fp"): "Piston, crosswind", ("piston", "S_spd"): "Piston, crosswind",
              ("piston", "S_turn"): "Piston pattern approaches with a base leg, turn to final", ("jet", "S_fp"): "Jets (floor), crosswind"}


def calm_base(who, score, thr):
    b = pd.read_csv(BANDS)
    r = b[(b.table == BAND_TABLE[(who, score)]) & (b.value == score) & (b.band == "0-5")].iloc[0]
    return float(r[f"gt{thr}"])
C = fs.COLORS


def limit(path, grp, key="xw"):
    t = open(path).read()
    m = re.search(rf"Model-free, {grp} \[post-hoc, model-free, {key}\].*?revealed limit 50%: ([\d.]+) kt \(95% CI ([\d.]+) to ([\d.]+)", t, re.S)
    return tuple(float(x) for x in m.groups())


def end_label(ax, x, y, text, color, dy=0.0):
    ax.text(x + 0.35, y + dy, text, color=color, fontsize=8.5, va="center", ha="left")


def fig_activity():
    a = pd.read_csv(os.path.join(D, "activity_us.csv"))
    fig, ax = plt.subplots(figsize=(fs.WIDTH, 3.5))
    ax.axhline(100, color=fs.MUTED, lw=0.6, zorder=1)
    ax.axhline(50, color=fs.MUTED, lw=0.6, ls=(0, (4, 3)), zorder=1)
    ax.text(20.3, 101.5, "normal traffic", fontsize=8, color=fs.MUTED, va="bottom")
    ax.text(20.3, 51.5, "half of normal", fontsize=8, color=fs.MUTED, va="bottom")
    series = [("private", "Private aircraft", 2.5), ("all", "All piston aircraft", 0.0), ("fleet", "Fleet aircraft", -2.5)]
    for key, lab, dy in series:
        grp = "piston" if key == "all" else key
        g = a[(a.group == grp) & (a.hours >= 100)]
        lw = 2.0 if key == "all" else 1.3
        ax.fill_between(g.bin_mid, 100 * g.lo, 100 * g.hi, color=C[key], alpha=0.16, lw=0, zorder=2)
        ax.plot(g.bin_mid, 100 * g.activity, color=C[key], lw=lw, zorder=4)
        end_label(ax, g.bin_mid.iloc[-1], 100 * g.activity.iloc[-1], lab, C[key], dy)
    # revealed limits: points on the half line, values at the foot of a drop line
    marks = [("fleet", limit("q1a_us/summary.txt", "fleet")[0]), ("all", limit("q1a_us/summary.txt", "piston")[0]),
             ("private", limit("q1a_us/summary.txt", "private")[0])]
    place = {"fleet": ("right", -0.15, 2), "all": ("center", 0.0, 9), "private": ("left", 0.15, 2)}
    for key, x in marks:
        ax.plot([x, x], [0, 50], color=C[key], lw=0.8, ls=":", zorder=3)
        ax.plot(x, 50, "o", color=C[key], ms=5, mec="white", mew=0.8, zorder=6)
        ha, dx, y = place[key]
        ax.text(x + dx, y, f"{x:.1f} kt", color=C[key], fontsize=8, ha=ha, va="bottom",
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"), zorder=7)
    ax.set_xlim(0, 24.5)
    ax.set_xticks(range(0, 21, 2))
    ax.spines["bottom"].set_bounds(0, 20)
    ax.set_ylim(0, 112)
    ax.set_yticks(range(0, 101, 25))
    ax.set_xlabel("Crosswind (kt): hourly mean, on the runway most nearly into the wind")
    ax.set_ylabel("Arrivals, % of normal demand")
    fig.tight_layout()
    fs.save(fig, os.path.join(HERE, "activity"))


def share_levels(s, who, score, thr):
    g = s[(s.who == who) & (s.score == score) & (s.threshold == thr)].sort_values("bin_mid")
    base = calm_base(who, score, thr)
    g = g[g.n >= 900]
    return g.bin_mid.values, 100 * g.share.values, 100 * g.lo.values, 100 * g.hi.values, 100 * base


def change_from_calm(s, who, score, thr):
    g = s[(s.who == who) & (s.score == score) & (s.threshold == thr)].sort_values("bin_mid")
    base = calm_base(who, score, thr)
    g = g[g.n >= 900]
    return g.bin_mid.values, 100 * (g.share.values - base), 100 * (g.lo.values - base), 100 * (g.hi.values - base), 100 * base


LINES = [("piston", "S_spd", 1, "spd", "Speed", "-"), ("piston", "S_turn", 1, "turn", "Turn to final", "-"),
         ("piston", "S_fp", 1, "fp", "Flight path", "-"), ("jet", "S_fp", 1, "jet", "Jets, flight path", (0, (4, 2)))]


def draw_lines(ax, s, fn, gap):
    ends = {}
    for who, score, thr, key, lab, ls in LINES:
        x, y, lo, hi, base = fn(s, who, score, thr)
        ax.fill_between(x, lo, hi, color=C[key], alpha=0.16, lw=0)
        ax.plot(x, y, color=C[key], lw=2.0 if key != "jet" else 1.3, ls=ls)
        ends[key] = (x[-1], y[-1], lab, base)
    placed = []
    for key, (x, y, lab, base) in sorted(ends.items(), key=lambda kv: kv[1][1]):
        yy = y
        for p in placed:
            if abs(yy - p) < gap:
                yy = p + gap
        placed.append(yy)
        ax.text(x + 0.35, yy, lab, color=C[key], fontsize=8.5, va="center")
    return {k: v[3] for k, v in ends.items()}


def fig_calibration():
    a = pd.read_csv(os.path.join(D, "activity_us.csv"))
    s = pd.read_csv(os.path.join(D, "shares_us.csv"))
    poh = pd.read_csv(os.path.join(D, "poh_xwind_us.csv"), index_col=0).iloc[:, 0]
    e = limit("q1a_us/summary.txt", "piston")[0]
    fig, (ax, bx, cx) = plt.subplots(3, 1, figsize=(fs.WIDTH, 7.1), sharex=True,
                                     gridspec_kw={"height_ratios": [1, 1.1, 1.1], "hspace": 0.42})
    for x in (ax, bx, cx):
        x.axvspan(poh["25%"], poh["75%"], color=C["poh"], lw=0, zorder=0)
        x.axvline(e, color=C["limit"], lw=0.9, ls=(0, (4, 3)), zorder=1)
        x.set_xlim(0, 22.5)
        x.set_xticks(range(0, 21, 2))
        x.spines["bottom"].set_bounds(0, 20)
    ax.text(e - 0.2, 104, f"revealed limit, {e:.1f} kt", fontsize=8, ha="right", va="top")
    ax.text((poh["25%"] + poh["75%"]) / 2, 104, "typical maximum\ndemonstrated\ncrosswind", fontsize=8, ha="center", va="top", color="#2a5d84")

    g = a[(a.group == "piston") & (a.hours >= 100)]
    ax.fill_between(g.bin_mid, 100 * g.lo, 100 * g.hi, color=C["all"], alpha=0.16, lw=0)
    ax.plot(g.bin_mid, 100 * g.activity, color=C["all"], lw=2.0)
    ax.plot(e, 50, "o", color=C["all"], ms=5, mec="white", mew=0.8, zorder=5)
    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("% of normal demand")
    ax.tick_params(labelbottom=True)
    ax.set_xlabel("Crosswind (kt), hourly mean on the runway most nearly into the wind")
    fs.panel_title(ax, "a", "Arrivals relative to normal demand")

    draw_lines(bx, s, share_levels, 5.0)
    bx.tick_params(labelbottom=True)
    bx.set_ylim(0, 70)
    bx.set_yticks(range(0, 71, 10))
    bx.set_ylabel("% of approaches")
    fs.panel_title(bx, "b", "Approaches beyond tolerance (score above 1)")

    bases = draw_lines(cx, s, change_from_calm, 1.5)
    cx.axhline(0, color=fs.MUTED, lw=0.7)
    cx.text(20, 0.3, "same as calm wind", fontsize=7.5, color=fs.MUTED, ha="right", va="bottom")
    cx.set_ylim(-2, 18)
    cx.set_yticks([0, 5, 10, 15])
    cx.set_ylabel("Increase over calm wind\n(percentage points)")
    cx.set_xlabel("Crosswind (kt) on the runway in use, at each approach")
    fs.panel_title(cx, "c", "Increase over calm wind")
    fs.save(fig, os.path.join(HERE, "calibration"))
    return bases


def smooth(points, n=24):
    """Catmull-Rom curve through the points."""
    P = np.array(points, float)
    P = np.vstack([P[0], P, P[-1]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return np.array(out)


def turn_sketch(ax, case):
    """Plan view of the turn from base to final for one wind side. The base leg comes from the
    right, so the base-leg side is the right and the far side is the left. Gray dashes are the
    turn in calm wind, the colored line is what the wind does."""
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((-0.12, 0.0), 0.24, 1.1, color=fs.INK, lw=0))
    ax.text(0.22, 0.55, "runway", fontsize=8, ha="left", va="center")
    ax.plot([0, 0], [-2.6, 0], color=fs.MUTED, lw=0.6, ls=(0, (2, 2)))
    calm = smooth([(2.7, -2.2), (0.9, -2.2), (0.25, -1.95), (0.0, -1.35), (0.0, 0.0)])
    ax.plot(calm[:, 0], calm[:, 1], color=fs.MUTED, lw=1.1, ls=(0, (4, 2)))
    ax.text(2.0, -2.33, "base leg", fontsize=8, color=fs.MUTED, ha="center", va="top")
    ax.text(-0.1, -2.55, "final", fontsize=8, color=fs.MUTED, ha="right", va="bottom")
    if case == "base":
        col = C["overshoot"]
        path = smooth([(2.7, -2.2), (0.9, -2.2), (0.2, -2.0), (-0.3, -1.6), (-0.55, -1.15), (-0.4, -0.7), (-0.1, -0.35), (0.0, -0.1), (0.0, 0.0)])
        ax.plot(path[:, 0], path[:, 1], color=col, lw=2.0)
        k = np.argmin(path[:, 0])
        ax.annotate("", (path[k, 0], path[k, 1]), (0, path[k, 1]), arrowprops=dict(arrowstyle="<->", lw=0.8, color=col, shrinkA=0, shrinkB=0))
        ax.text(path[k, 0] - 0.08, path[k, 1], "overshoots\nthe centerline", fontsize=8, color=col, ha="right", va="center")
        ax.add_patch(FancyArrowPatch((2.6, -1.0), (1.4, -1.0), arrowstyle="-|>", mutation_scale=12, color=col, lw=1.8))
        ax.text(2.0, -0.85, "wind", fontsize=8.5, color=col, ha="center", va="bottom")
    else:
        col = C["late"]
        path = smooth([(2.7, -2.2), (0.9, -2.2), (0.6, -2.0), (0.5, -1.5), (0.42, -0.95), (0.28, -0.5), (0.1, -0.18), (0.0, -0.05), (0.0, 0.0)])
        ax.plot(path[:, 0], path[:, 1], color=col, lw=2.0)
        ax.plot(0.0, -0.1, "o", color=col, ms=4.5, zorder=5)
        ax.annotate("aligned only\nnear the runway", (0.03, -0.12), xytext=(0.75, -0.55), fontsize=8, color=col, ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", lw=0.7, color=col, shrinkA=2, shrinkB=3))
        ax.add_patch(FancyArrowPatch((-1.9, -1.0), (-0.6, -1.0), arrowstyle="-|>", mutation_scale=12, color=col, lw=1.8))
        ax.text(-1.25, -0.85, "wind", fontsize=8.5, color=col, ha="center", va="bottom")
    ax.set_xlim(-2.0, 3.0)
    ax.set_ylim(-2.7, 1.2)


def direction_levels(d, measure, side):
    g = d[d.measure == measure]
    calm = g[g.bin_lo.isin([-2, 0])]
    base = (calm.share * calm.n).sum() / calm.n.sum()
    g = g[g.n >= 900]
    g = g[g.bin_lo >= 0] if side == "base" else g[g.bin_lo < -2]
    x = np.abs(g.bin_mid.values)
    o = np.argsort(x)
    x = np.r_[0, x[o]]
    y = np.r_[100 * base, 100 * g.share.values[o]]
    lo = np.r_[100 * base, 100 * g.lo.values[o]]
    hi = np.r_[100 * base, 100 * g.hi.values[o]]
    return x, y, lo, hi, 100 * base


def fig_direction():
    d = pd.read_csv(os.path.join(D, "direction_us.csv"))
    fig = plt.figure(figsize=(fs.WIDTH, 5.0))
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.45], hspace=0.5, wspace=0.32)
    rows = (("base", "a", "b", "Tailwind on base", "Tailwind on base (kt)"),
            ("far", "c", "d", "Headwind on base", "Headwind on base (kt)"))
    for r, (side, la, lb, name, xlab) in enumerate(rows):
        ax = fig.add_subplot(gs[r, 0])
        turn_sketch(ax, side)
        fs.panel_title(ax, la, name)
        bx = fig.add_subplot(gs[r, 1])
        for measure, key, lab in (("late_alignment", "late", "Not aligned by 300 ft"), ("overshoot_200", "overshoot", "Overshoot, 200 ft or more")):
            x, y, lo, hi, base = direction_levels(d, measure, side)
            bx.plot([0, 15], [base, base], color=C[key], lw=0.8, ls=(0, (1, 2)), zorder=1)
            if key == "late":
                bx.text(15, base + 0.8, "calm wind", fontsize=7.5, color=fs.MUTED, ha="right", va="bottom")
            bx.fill_between(x, lo, hi, color=C[key], alpha=0.18, lw=0)
            bx.plot(x, y, color=C[key], lw=2.0)
            bx.text(x[-1] + 0.3, y[-1], lab, color=C[key], fontsize=8.5, va="center", ha="left")
        bx.set_xlim(0, 25)
        bx.set_xticks([0, 5, 10, 15])
        bx.spines["bottom"].set_bounds(0, 15)
        bx.set_ylim(0, 52)
        bx.set_yticks([0, 10, 20, 30, 40, 50])
        bx.set_ylabel("% of pattern approaches")
        bx.set_xlabel(xlab)
        fs.panel_title(bx, lb, "What happens in the turn to final")
    fs.save(fig, os.path.join(HERE, "direction"))


def main():
    fs.apply()
    fig_activity()
    bases = fig_calibration()
    fig_direction()
    print("figures written; calm baselines (%):", {k: round(v, 1) for k, v in bases.items()})


if __name__ == "__main__":
    main()
