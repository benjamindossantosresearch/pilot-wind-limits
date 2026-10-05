#!/usr/bin/env python3
"""
make_fig_angle.py

Figure 5 (exploratory X6): approach performance by crosswind strength and wind angle to the
runway in use, as three heatmaps (flight path above 2, turn to final above 1, speed above 1).
Reads the grid from q2_us_results_v31_cas/xw_angle_summary.txt (us_xw_angle.py).

    cd /home/dev/wind-limits && python3 paper/figures/make_fig_angle.py

Writes paper/figures/angle.pdf and angle.png.
"""

import os
import re
import sys

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import figstyle as fs  # noqa: E402

SRC = "q2_us_results_v31_cas/xw_angle_summary.txt"
ROWS = ["5-9", "10-14", "15-19"]
COLS = ["0-30", "30-60", "60-90", "90-180"]
COL_LABELS = ["0-30°", "30-60°", "60-90°", "over 90°"]


def read_grid():
    pat = re.compile(r"crosswind (\d+-\d+) kt, angle (\d+-\d+) deg: n=\s*([\d,]+)(.*)")
    cells = {}
    for line in open(SRC):
        m = pat.search(line)
        if not m:
            continue
        row, col, n, rest = m.group(1), m.group(2), int(m.group(3).replace(",", "")), m.group(4)
        if "too few" in rest:
            cells[(row, col)] = {"n": n}
            continue
        fp = re.search(r"flight path\s+([\d.]+)% \(\s*([\d.]+)%\)", rest)
        spd = re.search(r"speed\s+([\d.]+)%", rest)
        turn = re.search(r"turn\s+([\d.]+)%", rest)
        cells[(row, col)] = {"n": n, "fp2": float(fp.group(2)), "spd1": float(spd.group(1)), "turn1": float(turn.group(1))}
    return cells


def panel(ax, cells, key, cmap, title, letter):
    Z = np.full((len(ROWS), len(COLS)), np.nan)
    for i, r in enumerate(ROWS):
        for j, c in enumerate(COLS):
            v = cells.get((r, c), {})
            if v.get("n", 0) >= 200 and key in v:
                Z[i, j] = v[key]
    vmin, vmax = np.nanmin(Z), np.nanmax(Z)
    ax.imshow(np.ma.masked_invalid(Z), cmap=cmap, vmin=vmin - 0.15 * (vmax - vmin), vmax=vmax + 0.3 * (vmax - vmin), origin="lower", aspect="auto")
    for i, r in enumerate(ROWS):
        for j, c in enumerate(COLS):
            v = cells.get((r, c), {})
            if np.isnan(Z[i, j]):
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, color="#eeeeee", lw=0))
                ax.text(j, i, "too few", ha="center", va="center", fontsize=7, color=fs.MUTED)
                continue
            frac = (Z[i, j] - vmin) / max(vmax - vmin, 1e-9)
            mark = "*" if v["n"] < 1000 else ""
            ax.text(j, i, f"{Z[i, j]:.1f}{mark}", ha="center", va="center", fontsize=8.5,
                    color="white" if frac > 0.7 else fs.INK)
    ax.set_xticks(range(len(COLS)))
    ax.set_xticklabels(COL_LABELS, fontsize=8)
    ax.set_yticks(range(len(ROWS)))
    ax.set_yticklabels([f"{r} kt" for r in ROWS])
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(False)
    fs.panel_title(ax, letter, title)


def main():
    fs.apply()
    cells = read_grid()
    fig, axes = plt.subplots(1, 3, figsize=(fs.WIDTH, 2.7), sharey=True)
    for ax, (key, title, letter) in zip(axes, (("fp2", "Flight path above 2 (%)", "a"), ("turn1", "Turn to final above 1 (%)", "b"),
                                              ("spd1", "Speed above 1 (%)", "c"))):
        panel(ax, cells, key, "Blues", title, letter)
    axes[0].set_ylabel("Crosswind")
    axes[1].set_xlabel("Wind angle to the runway in use: 0° straight down the runway, 90° direct crosswind, over 90° from behind", fontsize=8.5, labelpad=6)
    fig.tight_layout()
    fs.save(fig, os.path.join(HERE, "angle"))
    print({k: v.get("n") for k, v in cells.items()})


if __name__ == "__main__":
    main()
