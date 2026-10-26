"""Render Reports/Coacervation_Poster.png -- three decision streams (slide 1.3).

Mirrors the deck's 'Our Approach': an automated capability that connects formula
screening to mechanism testing via three decision streams, each framed as
Question -> Method (website) -> Decision enabled. Deck navy + mauve palette.
"""
import os
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import FancyBboxPatch, FancyArrow
from PIL import Image

NAVY = "#0F2A4A"; NAVY2 = "#1E3A50"; TEXT = "#1D2D42"
MAUVE = "#B8909C"; PLUM = "#8D6E78"; STEEL = "#4A6B8A"; TEAL = "#1A7373"
LMAUVE = "#EDE4E9"; PANEL = "#EEF1F6"; CLOUD = "#CBD9E8"; GREY = "#5A6070"
SHOTS = os.path.join("Reports", "poster_shots")


def tint(hexc, a):
    r = int(hexc[1:3], 16); g = int(hexc[3:5], 16); b = int(hexc[5:], 16)
    r = int(r + (255 - r) * a); g = int(g + (255 - g) * a); b = int(b + (255 - b) * a)
    return f"#{r:02X}{g:02X}{b:02X}"


fig = plt.figure(figsize=(16, 9), dpi=150)
fig.patch.set_facecolor("white")
ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
ax.set_xlim(0, 100); ax.set_ylim(0, 100)
FW, FH = 100, 100


def band(x, y, w, h, fc, ec=None, r=1.0, lw=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle=f"round,pad=0,rounding_size={r}",
                 fc=fc, ec=ec or fc, lw=lw, zorder=3))


def wrapped(x, y, s, width, size, color, ha="left", weight="normal",
            style="normal", va="top", z=6):
    ax.text(x, y, textwrap.fill(s, width=width), fontsize=size, color=color,
            ha=ha, va=va, fontweight=weight, style=style, zorder=z,
            linespacing=1.18)


def arrow(x, y, dx):
    ax.add_patch(FancyArrow(x, y, dx, 0, width=0.7, head_width=2.4,
                 head_length=1.0, length_includes_head=True, fc=PLUM, ec=PLUM,
                 zorder=7))


def fit_image(path, x0, y0, w, h):
    if not os.path.exists(path):
        return
    with Image.open(path) as im:
        iw, ih = im.size
    ar = iw / ih; box_ar = (w * 16) / (h * 9)
    if ar >= box_ar:
        dw = w; dh = w * 16 / 9 / ar
    else:
        dh = h; dw = h * 9 / 16 * ar
    ix = x0 + (w - dw) / 2; iy = y0 + (h - dh) / 2
    iax = fig.add_axes([ix / FW, iy / FH, dw / FW, dh / FH], zorder=5)
    iax.imshow(mpimg.imread(path)); iax.axis("off")
    for sp in iax.spines.values():
        sp.set_visible(True); sp.set_edgecolor("#C9D4E0")


# ---- title
band(0, 91, 100, 9, NAVY, r=0, lw=0)
ax.text(2, 96.4, "Accelerating Superior Shampoo Innovation",
        fontsize=23, fontweight="bold", color="white", va="center")
ax.text(2, 92.7, "An automated capability that connects formula screening to "
        "mechanism testing       \u00b7       Kyla Fung \u00b7 R&D Beauty Analytical",
        fontsize=12, color=CLOUD, va="center")

# ---- consumer band (why)
band(2, 82.4, 96, 7.6, LMAUVE, MAUVE)
wrapped(3.5, 88.8, "It starts with the consumer \u2014 superior shampoo must deposit "
        "benefits without compromising clean feel.", width=120, size=14,
        color=NAVY, weight="bold")
wrapped(3.5, 85.7, "New materials expand the deposition mechanisms Hair Care must "
        "understand. The strategy: find which metrics predict the consumer benefit "
        "\u2014 and take charge to optimize the method when they don\u2019t.",
        width=165, size=11, color=TEXT)

# ---- three decision streams
streams = [
    (TEAL, "1 \u00b7 ACCELERATED SCREENING",
     "Which formulas show differentiated coacervation behavior?",
     "01_screen_analyze.png",
     "Automated %T + digital analysis turn curves into standardized coacervation "
     "fingerprints.",
     "Decision: accelerate the right formulas to deeper testing."),
    (STEEL, "2 \u00b7 DEEPEN UNDERSTANDING",
     "How do specific ingredients & variables impact coacervation?",
     "02_isolate_phase.png",
     "Phase diagrams map the interaction of polymer \u00d7 surfactant \u00d7 chassis "
     "\u00d7 salt.",
     "Decision: which ingredients / variables to optimize or investigate."),
    (PLUM, "3 \u00b7 CONNECT TO CONSUMER",
     "Which coacervate properties impact performance?",
     "04_connect_ptl.png",
     "Integrated characterization (microscopy, Lasentec, rheology) + PTL / ILS "
     "performance.",
     "Decision: which coacervate properties to design for."),
]
rows_top = 80.8; rows_bottom = 13.0
rh = (rows_top - rows_bottom - 2 * 1.6) / 3  # 3 rows, 1.6 gaps
for i, (accent, title, q, img, method, decision) in enumerate(streams):
    y0 = rows_top - rh - i * (rh + 1.6)
    # left: question block
    band(2, y0, 27, rh, tint(accent, 0.82), accent, r=0.9)
    ax.text(3.4, y0 + rh - 2.2, title, fontsize=12, fontweight="bold",
            color=NAVY, va="top", zorder=6)
    wrapped(3.4, y0 + rh - 5.2, q, width=30, size=11.5, color=accent,
            weight="bold")
    # arrow -> method
    arrow(29.2, y0 + rh / 2, 2.4)
    # middle: website screenshot
    band(32, y0, 30, rh, "white", accent, r=0.9)
    fit_image(os.path.join(SHOTS, img), 33, y0 + 1.2, 28, rh - 2.4)
    # arrow -> decision
    arrow(62.3, y0 + rh / 2, 2.4)
    # right: method + decision
    band(65.2, y0, 32.8, rh, PANEL, accent, r=0.9)
    wrapped(66.8, y0 + rh - 2.2, method, width=42, size=10.8, color=TEXT)
    wrapped(66.8, y0 + 6.0, decision, width=42, size=11, color=NAVY,
            weight="bold")

# ---- goal band
band(2, 2.0, 96, 9.4, NAVY, r=1.0)
ax.text(50, 8.3, "Formulation \u2192 Benefit linkage", fontsize=13,
        fontweight="bold", color=MAUVE, ha="center", va="center")
wrapped(50, 6.2, "The goal: help Product Development know what should advance, what "
        "should be optimized, and what Hair Care should design for \u2014 consumer "
        "first, to delight and grow use.", width=130, size=12.5, color="white",
        ha="center", weight="bold")

out = os.path.join("Reports", "Coacervation_Poster.png")
fig.savefig(out, dpi=150, facecolor="white")
plt.close(fig)
print("saved", out)
