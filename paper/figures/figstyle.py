"""
figstyle.py

Shared look for the paper's figures: STIX (Times-like, matching the AIAA body text),
left and bottom spines only, light horizontal grid, Okabe-Ito colors that also read in
gray, and the same color for the same quantity in every figure.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WIDTH = 6.5  # AIAA text width, inches

INK = "#222222"
MUTED = "#6b6b6b"
GRID = "#e6e6e6"
COLORS = {
    "all": INK, "fleet": "#0072B2", "private": "#D55E00", "ne": "#8c8c8c",
    "fp": INK, "spd": "#E69F00", "turn": "#009E73", "jet": "#8c8c8c",
    "overshoot": "#D55E00", "late": "#0072B2",
    "limit": "#444444", "poh": "#d9e8f3",
}
# severity bands: within tolerance, 1 to 2, 2 to 3, above 3 times the tolerance
BANDS = ["#e3f1e1", "#fbf0c9", "#f9d9bb", "#f3c0bb"]


def apply():
    plt.rcParams.update({
        "font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 9,
        "axes.titlesize": 9.5, "axes.labelsize": 9, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "axes.linewidth": 0.6, "axes.edgecolor": INK, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": INK, "ytick.color": INK, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.major.size": 3, "ytick.major.size": 3, "xtick.direction": "out", "ytick.direction": "out",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 8.5,
        "savefig.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
    })


def panel_title(ax, letter, text):
    ax.set_title(f"({letter}) {text}", loc="left", fontsize=9.5, pad=6)


def save(fig, path_stem):
    fig.savefig(path_stem + ".pdf")
    fig.savefig(path_stem + ".png")
    plt.close(fig)
