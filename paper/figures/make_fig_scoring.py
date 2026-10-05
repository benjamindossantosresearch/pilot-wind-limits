#!/usr/bin/env python3
"""
make_fig_scoring.py

Figure 1: how an approach is scored. Side view (glide path) and top view (centerline)
of the last 1.2 nm of a final approach, with the tolerance bands shaded and a made-up
approach (the paper shows no individual flight).

    cd /home/dev/wind-limits && python3 paper/figures/make_fig_scoring.py

Writes paper/figures/scoring.pdf and scoring.png.
"""

import math
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as fs  # noqa: E402

FT_PER_NM = 6076.12
TAN3 = math.tan(math.radians(3.0))
TCH = 50.0
GATE, FLOOR = 300.0, 100.0
X_MAX = 1.25


def path_h(d):
    return TCH + d * FT_PER_NM * TAN3


def d_at(h):
    return (h - TCH) / (FT_PER_NM * TAN3)


def example():
    de = np.linspace(1.2, 0.04, 200)
    dev = 140 * np.exp(-((de - 0.55) / 0.22) ** 2) - 40 * np.exp(-((de - 0.2) / 0.08) ** 2)
    lat = 60 * np.exp(-((de - 1.0) / 0.15) ** 2) - 260 * np.exp(-((de - 0.6) / 0.14) ** 2) + 15
    return de, dev, lat


def shade(ax, d, center, step):
    for k in range(3, -1, -1):
        hi = (k + 1) * step if k < 3 else 20 * step
        ax.fill_between(d, center - hi, center + hi, color=fs.BANDS[k], lw=0, zorder=0)


def segment_marks(ax, d_gate, d_floor, y_top, with_text):
    for x in (d_gate, d_floor):
        ax.axvline(x, color=fs.MUTED, lw=0.7, zorder=2)
    if with_text:
        box = dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9)
        ax.annotate("", (d_floor, y_top), (d_gate, y_top), arrowprops=dict(arrowstyle="<->", lw=0.7, color=fs.INK), zorder=3)
        ax.text((d_gate + d_floor) / 2, y_top, "scored from 300 ft down to 100 ft", ha="center", va="center", fontsize=8, bbox=box, zorder=4)


def main():
    fs.apply()
    de, dev, lat = example()
    d_gate, d_floor = d_at(GATE), d_at(FLOOR)
    inseg = (de <= d_gate) & (de >= d_floor)
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(fs.WIDTH, 5.4), sharex=True, gridspec_kw={"height_ratios": [1.1, 1]})

    # side view
    d = np.linspace(0, X_MAX, 300)
    shade(ax, d, path_h(d), 100)
    ax.plot(d, path_h(d), color=fs.INK, lw=0.9, ls="--", zorder=2)
    segment_marks(ax, d_gate, d_floor, 640, True)
    ax.add_patch(Rectangle((-0.2, -6), 0.2, 12, color=fs.INK, lw=0, zorder=3, clip_on=False))
    ax.text(-0.1, 22, "runway", fontsize=7.5, ha="center", va="bottom", color=fs.INK)
    ax.plot(de, path_h(de) + dev, color="#1f4e79", lw=1.8, zorder=5)
    k = np.argmax(np.where(inseg, dev, -1e9))
    ax.plot(de[k], path_h(de[k]) + dev[k], "o", color="#1f4e79", ms=4.5, zorder=6)
    ax.annotate(f"worst point: {dev[k]:.0f} ft high\n{dev[k]:.0f} / 100 = ratio {dev[k] / 100:.1f}", (de[k], path_h(de[k]) + dev[k]),
                xytext=(0.93, 70), fontsize=8, ha="left", va="bottom",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.75", lw=0.5),
                arrowprops=dict(arrowstyle="-", lw=0.6, color=fs.INK), zorder=7)
    ax.set_ylim(0, 700)
    ax.set_ylabel("Height above threshold (ft)")
    ax.grid(False)
    fs.panel_title(ax, "a", "Side view: glide path, tolerance 100 ft")

    # top view
    shade(bx, d, 0 * d, 200)
    bx.axhline(0, color=fs.INK, lw=0.9, ls="--", zorder=2)
    bx.text(1.12, -40, "extended centerline", fontsize=8, ha="center", va="top")
    bx.text(-0.1, 0, "runway", fontsize=7.5, ha="center", va="center", color="white", zorder=4)
    segment_marks(bx, d_gate, d_floor, 0, False)
    bx.add_patch(Rectangle((-0.2, -75), 0.2, 150, color=fs.INK, lw=0, zorder=3))
    bx.plot(de, lat, color="#1f4e79", lw=1.8, zorder=5)
    k2 = np.argmax(np.where(inseg, np.abs(lat), -1e9))
    bx.plot(de[k2], lat[k2], "o", color="#1f4e79", ms=4.5, zorder=6)
    bx.annotate(f"worst point: {abs(lat[k2]):.0f} ft off the centerline\n{abs(lat[k2]):.0f} / 200 = ratio {abs(lat[k2]) / 200:.1f}",
                (de[k2], lat[k2]), xytext=(0.93, -620), fontsize=8, ha="left", va="bottom",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.75", lw=0.5),
                arrowprops=dict(arrowstyle="-", lw=0.6, color=fs.INK), zorder=7)
    bx.set_ylim(-750, 750)
    bx.set_yticks([-600, -400, -200, 0, 200, 400, 600])
    bx.set_ylabel("Offset from centerline (ft)")
    bx.set_xlim(X_MAX, -0.22)
    bx.set_xticks([1.2, 1.0, 0.8, 0.6, 0.4, 0.2, 0.0])
    bx.set_xlabel("Distance to the runway threshold (nm)")
    bx.grid(False)
    fs.panel_title(bx, "b", "Top view: centerline, tolerance 200 ft")

    s = max(dev[k] / 100, abs(lat[k2]) / 200)
    # glide path label, rotated to the path as drawn
    fig.canvas.draw()
    p0, p1 = ax.transData.transform([(0.45, path_h(0.45)), (0.25, path_h(0.25))])
    ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    ax.text(0.35, path_h(0.35) - 28, "3° reference path", fontsize=8, rotation=ang, rotation_mode="anchor", ha="center", va="top")
    handles = [Patch(color=c) for c in fs.BANDS] + [plt.Line2D([0], [0], color="#1f4e79", lw=1.8)]
    labels = ["within tolerance", "1 to 2 times the tolerance", "2 to 3 times", "more than 3 times", "example approach"]
    fig.legend(handles, labels, loc="upper center", ncol=5, fontsize=8, bbox_to_anchor=(0.5, 1.02), handlelength=1.6, columnspacing=1.2)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fs.save(fig, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scoring"))
    print(f"worst glide path {dev[k]:.0f} ft, worst lateral {abs(lat[k2]):.0f} ft, S_fp {s:.2f}")


if __name__ == "__main__":
    main()
