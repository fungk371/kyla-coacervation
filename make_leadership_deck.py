"""Leadership business deck: 'Coacervation \u2014 the science behind winning in hair care'.

Generates two custom explainer graphics (Coacervation 101 journey + business
value-chain), then assembles an aesthetically-polished 16:9 deck that:
  - explains coacervation to a non-expert with visuals
  - frames the BUSINESS impact (consumer delight, superiority, WIN)
  - links to Kyla's project (platform + biodegradable dextran + benchmarking)
  - proposes automation / simplification ideas and an external-imaging ask

Output: Reports/Coacervation_Leadership_Deck.pptx  (+ two PNGs)
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch, Ellipse
from PIL import Image

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

R = "Reports"
# ---- palette ----
NAVY = RGBColor(0x0B, 0x1F, 0x3A)
BLUE = RGBColor(0x2E, 0x75, 0xB6)
TEAL = RGBColor(0x14, 0x9E, 0xB8)
GOLD = RGBColor(0xC9, 0xA2, 0x27)
GREEN = RGBColor(0x2E, 0x9E, 0x5B)
CORAL = RGBColor(0xE8, 0x55, 0x6D)
LIGHT = RGBColor(0xEE, 0xF3, 0xF9)
GREY = RGBColor(0x5A, 0x64, 0x70)
DARK = RGBColor(0x1E, 0x2A, 0x36)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Abadi"

# hex for matplotlib
HNAVY, HBLUE, HTEAL, HGOLD, HGREEN, HCORAL = "#0B1F3A", "#2E75B6", "#149EB8", "#C9A227", "#2E9E5B", "#E8556D"


# =============================================================== graphics
def make_coac101(path):
    fig, ax = plt.subplots(figsize=(14, 4.9))
    ax.set_xlim(0, 14); ax.set_ylim(0, 5); ax.axis("off")

    def panel(x, title):
        ax.add_patch(FancyBboxPatch((x, 1.05), 3.5, 2.95,
                     boxstyle="round,pad=0.02,rounding_size=0.18",
                     fc="#F5F9FD", ec=HNAVY, lw=1.6))
        ax.text(x + 1.75, 4.28, title, ha="center", fontsize=13.5,
                fontweight="bold", color=HNAVY)

    def caption(x, text, color="#5A6470"):
        ax.text(x + 1.75, 0.55, text, ha="center", va="center", fontsize=9.2, color=color)

    # Stage 1 - in the bottle
    panel(0.35, "1 \u00b7 In the bottle")
    ax.text(1.55, 3.6, "cationic polymer", ha="center", fontsize=8.4, color=HCORAL, fontweight="bold")
    xx = np.linspace(0.7, 2.4, 100)
    ax.plot(xx, 3.15 + 0.20 * np.sin((xx - 0.7) * 7), color=HCORAL, lw=2.6)
    for cx, cy in [(0.95, 2.05), (1.55, 2.35), (2.15, 1.95), (2.6, 2.35), (1.3, 1.7)]:
        ax.add_patch(Circle((cx, cy), 0.16, fc=HTEAL, ec="white", lw=0.8))
    ax.text(1.75, 1.3, "surfactant micelles", ha="center", fontsize=8.4, color=HTEAL, fontweight="bold")
    caption(0.35, "clear \u2014 polymer & surfactant stay separate")

    # Stage 2 - rinse / coacervate
    panel(5.25, "2 \u00b7 You rinse (add water)")
    ax.text(7.0, 3.68, "coacervate droplets form", ha="center", fontsize=9.4, color=HNAVY, fontweight="bold")
    for ex, ey in [(6.25, 2.75), (7.55, 2.95), (6.85, 1.75), (7.8, 1.9)]:
        ax.add_patch(Ellipse((ex, ey), 0.98, 0.72, fc=HBLUE, ec=HNAVY, lw=1.1, alpha=0.92))
        for dx, dy in [(-0.19, 0.04), (0.17, 0.11), (0.02, -0.15)]:
            ax.add_patch(Circle((ex + dx, ey + dy), 0.075, fc=HGOLD, ec="white", lw=0.5))
    caption(5.25, "droplets carry conditioners & actives (gold)")

    # Stage 3 - on the hair
    panel(10.15, "3 \u00b7 On your hair")
    ax.add_patch(FancyBboxPatch((11.5, 1.35), 0.5, 2.35, boxstyle="round,pad=0.02,rounding_size=0.25",
                 fc="#8A6D3B", ec="#5b4726", lw=1.2))
    ax.add_patch(FancyBboxPatch((11.36, 1.3), 0.78, 2.45, boxstyle="round,pad=0.02,rounding_size=0.25",
                 fc="none", ec=HBLUE, lw=2.6))
    for sy in (3.35, 2.7, 2.05):
        ax.text(12.45, sy, "\u2726", fontsize=12, color=HGOLD)
    caption(10.15, "smooth, soft, conditioned layer", color=HGREEN)

    # arrows
    for ax0 in (4.05, 8.95):
        ax.add_patch(FancyArrowPatch((ax0, 2.5), (ax0 + 1.05, 2.5),
                     arrowstyle="-|>", mutation_scale=26, lw=3, color=HGOLD))
    ax.text(4.6, 2.85, "add water", ha="center", fontsize=8.6, color=HGOLD, fontweight="bold")
    ax.text(9.5, 2.85, "deposits", ha="center", fontsize=8.6, color=HGOLD, fontweight="bold")

    fig.suptitle("Coacervation in one picture: how a shampoo delivers 'conditioned' hair",
                 fontsize=15, fontweight="bold", color=HNAVY, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=170); plt.close(fig)
    print("wrote", path)


def make_valuechain(path):
    fig, ax = plt.subplots(figsize=(13.5, 3.0))
    ax.set_xlim(0, 13.5); ax.set_ylim(0, 3); ax.axis("off")
    steps = [
        ("COACERVATION", "polymer + surfactant\nassociate on dilution", HBLUE),
        ("DEPOSITION", "carries conditioners\nonto the hair fiber", HTEAL),
        ("CONSUMER FEEL", "soft, smooth, silky\n\u2014 they can feel it", HGREEN),
        ("PREFERENCE \u2192 WIN", "irresistibly superior;\nchoose us, stay with us", HGOLD),
    ]
    w = 2.9; gap = 0.55; x = 0.35
    for i, (t, s, c) in enumerate(steps):
        ax.add_patch(FancyBboxPatch((x, 0.55), w, 1.9,
                     boxstyle="round,pad=0.02,rounding_size=0.16",
                     fc=c, ec="white", lw=0))
        ax.text(x + w / 2, 1.85, t, ha="center", fontsize=12.5, fontweight="bold", color="white")
        ax.text(x + w / 2, 1.12, s, ha="center", fontsize=9.2, color="white")
        if i < 3:
            ax.add_patch(FancyArrowPatch((x + w + 0.05, 1.5), (x + w + gap - 0.02, 1.5),
                         arrowstyle="-|>", mutation_scale=22, lw=3, color="#0B1F3A"))
        x += w + gap
    fig.tight_layout()
    fig.savefig(path, dpi=170); plt.close(fig)
    print("wrote", path)


# =============================================================== pptx helpers
def _set_font(run, size=14, bold=False, color=DARK, italic=False):
    run.font.name = FONT; run.font.size = Pt(size); run.font.bold = bold
    run.font.italic = italic; run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {}); rPr.append(el)
        el.set("typeface", FONT)


def add_text(slide, l, t, w, h, lines, *, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(l, t, w, h); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(5)
        txt, o = (ln, {}) if isinstance(ln, str) else ln
        if o.get("bullet"):
            txt = "\u2022  " + txt
        r = p.add_run(); r.text = txt
        _set_font(r, size=o.get("size", 14), bold=o.get("bold", False),
                  color=o.get("color", DARK), italic=o.get("italic", False))
    return tb


def add_image(slide, path, l, t, mw, mh):
    if not os.path.exists(path):
        add_text(slide, l, t, mw, Inches(0.4), [(f"[missing {os.path.basename(path)}]", {"size": 10, "color": CORAL})])
        return
    with Image.open(path) as im:
        iw, ih = im.size
    ar = iw / ih; bar = mw / mh
    if ar >= bar:
        w = mw; h = int(mw / ar)
    else:
        h = mh; w = int(mh * ar)
    slide.shapes.add_picture(path, l + (mw - w) // 2, t + (mh - h) // 2, width=w, height=h)


prs = Presentation()
prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]; SW, SH = prs.slide_width, prs.slide_height


def title_bar(s, title, sub=None, color=NAVY):
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(1.05))
    bar.fill.solid(); bar.fill.fore_color.rgb = color; bar.line.fill.background()
    tf = bar.text_frame; tf.margin_left = Inches(0.5); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; r = p.add_run(); r.text = title
    _set_font(r, size=25, bold=True, color=WHITE)
    if sub:
        p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = sub
        _set_font(r2, size=13, color=RGBColor(0xCF, 0xDD, 0xF0))
    accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(1.05), SW, Pt(4))
    accent.fill.solid(); accent.fill.fore_color.rgb = GOLD; accent.line.fill.background()


def footer(s):
    add_text(s, Inches(0.5), Inches(7.04), Inches(12.4), Inches(0.38),
             [("P&G Hair Care  \u00b7  Coacervation measurement & automation  \u00b7  Kyla Fung",
               {"size": 9, "color": GREY})])


def card(s, l, t, w, h, header, lines, accent=BLUE, fc=LIGHT):
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    box.fill.solid(); box.fill.fore_color.rgb = fc; box.line.color.rgb = accent
    box.line.width = Pt(1.5)
    hd = [(header, {"size": 15, "bold": True, "color": NAVY})] if header else []
    add_text(s, l + Inches(0.25), t + Inches(0.16), w - Inches(0.5), h - Inches(0.3), hd + lines)


def chip(s, l, t, w, label, color):
    c = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, Inches(0.55))
    c.fill.solid(); c.fill.fore_color.rgb = color; c.line.fill.background()
    tf = c.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; _set_font(r, size=11.5, bold=True, color=WHITE)


# =============================================================== build graphics
make_coac101(f"{R}/coac101_schematic.png")
make_valuechain(f"{R}/coac_valuechain.png")

# =============================================================== slides
# ---- 1 HERO
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(2.95), Inches(3.6), Pt(4))
bar.fill.solid(); bar.fill.fore_color.rgb = GOLD; bar.line.fill.background()
add_text(s, Inches(0.9), Inches(1.7), Inches(11.6), Inches(2.4), [
    ("Coacervation", {"size": 46, "bold": True, "color": WHITE}),
    ("The invisible science behind irresistibly superior hair care", {"size": 22, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])
add_text(s, Inches(0.9), Inches(4.3), Inches(11.6), Inches(2.2), [
    ("Measuring it, automating it, and winning with it", {"size": 18, "bold": True, "color": GOLD}),
    ("Kyla Fung  \u00b7  Hair Care / Sustainable Polymers  \u00b7  Leadership review", {"size": 14, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])

# ---- 2 WHY IT MATTERS (business stakes)
s = prs.slides.add_slide(BLANK)
title_bar(s, "Why this matters \u2014 the battleground is how hair FEELS")
add_text(s, Inches(0.55), Inches(1.35), Inches(7.3), Inches(1.4), [
    ("Consumers judge a shampoo in seconds \u2014 by wet-comb, softness, smoothness, and shine. That feel is delivered by COACERVATION.",
     {"size": 15, "bullet": True, "color": DARK}),
    ("Win the coacervate \u2192 win the feel \u2192 win the consumer. It's the lever behind conditioning, deposition, and superiority.",
     {"size": 15, "bullet": True, "color": NAVY, "bold": True}),
])
card(s, Inches(0.55), Inches(3.15), Inches(6.0), Inches(3.3), "The competitive set we must beat",
     [("Dove, L'Or\u00e9al Elvive, Pantene (DMR), K\u00e9rastase Nutritive \u2014 all engineered around deposition & feel.",
       {"size": 13, "bullet": True}),
      ("Superiority is won on measurable conditioning, not marketing alone.", {"size": 13, "bullet": True}),
      ("We can now put our formulas AND theirs on one objective %T scale.", {"size": 13, "bullet": True, "color": GREEN})],
     accent=CORAL)
card(s, Inches(6.85), Inches(3.15), Inches(6.0), Inches(3.3), "And we must do it sustainably",
     [("Regulatory + consumer pressure demands readily-biodegradable polymers.",
       {"size": 13, "bullet": True}),
      ("Today's best conditioning polymers (guar / cellulose) biodegrade poorly.",
       {"size": 13, "bullet": True}),
      ("The prize: superior feel + sustainable chemistry = irresistibly superior AND future-proof.",
       {"size": 13, "bullet": True, "color": GREEN, "bold": True})],
     accent=GREEN)
footer(s)

# ---- 3 COACERVATION 101
s = prs.slides.add_slide(BLANK)
title_bar(s, "Coacervation 101 \u2014 explained in one picture",
          "No chemistry degree required")
add_image(s, f"{R}/coac101_schematic.png", Inches(0.4), Inches(1.35), Inches(12.5), Inches(4.6))
add_text(s, Inches(0.6), Inches(6.15), Inches(12.2), Inches(0.7), [
    ("Think of it as an invisible delivery truck: rinsing 'switches on' droplets that carry conditioners onto every strand.",
     {"size": 13.5, "italic": True, "color": NAVY, "bold": True})])
footer(s)

# ---- 4 WHAT IS IT (a bit deeper)
s = prs.slides.add_slide(BLANK)
title_bar(s, "What is coacervation, really?", "A tiny bit deeper \u2014 still simple")
add_text(s, Inches(0.55), Inches(1.35), Inches(12.2), Inches(1.5), [
    ("A positively-charged (cationic) polymer and negatively-charged surfactant repel water and each other's opposites \u2014 when you rinse, they associate and phase-separate into a concentrated 'coacervate' phase.",
     {"size": 14, "bullet": True}),
    ("That phase is the vehicle: it entraps and deposits silicones, anti-dandruff actives, and fragrance where they're needed.",
     {"size": 14, "bullet": True, "color": BLUE}),
])
add_image(s, f"{R}/coac_valuechain.png", Inches(0.5), Inches(3.35), Inches(12.3), Inches(2.8))
footer(s)

# ---- 5 THE LEVER FOR WINNING
s = prs.slides.add_slide(BLANK)
title_bar(s, "Coacervation is the lever for consumer delight")
card(s, Inches(0.55), Inches(1.35), Inches(6.0), Inches(5.1), "What we can already show",
     [("We benchmarked in-market & competitor shampoos on one %T scale.", {"size": 13.5, "bullet": True}),
      ("Early signal: conditioning-feel claims (silky, smooth, soft) track HIGHER coacervation; volumizing/clarifying track LOWER.",
       {"size": 13.5, "bullet": True, "color": GREEN}),
      ("That's an objective, physics-based link between a formula and how it will FEEL.",
       {"size": 13.5, "bullet": True, "bold": True, "color": NAVY}),
      ("Turns 'we think it feels better' into 'we can measure why'.", {"size": 13.5, "bullet": True})],
     accent=GREEN)
card(s, Inches(6.85), Inches(1.35), Inches(6.0), Inches(5.1), "Why leadership should care",
     [("Predict superiority BEFORE expensive consumer panels.", {"size": 13.5, "bullet": True, "color": CORAL}),
      ("De-risk formulation: know which chemistry will deposit.", {"size": 13.5, "bullet": True}),
      ("Faster, cheaper screening \u2192 more shots on goal for a winning product.",
       {"size": 13.5, "bullet": True}),
      ("Defensible IP + a sustainability story competitors can't easily match.",
       {"size": 13.5, "bullet": True, "color": GREEN})],
     accent=CORAL)
footer(s)

# ---- 6 HOW WE MEASURE: %T
s = prs.slides.add_slide(BLANK)
title_bar(s, "How we measure it today: %Transmittance (%T)",
          "Fast, quantitative \u2014 with known limits")
add_image(s, f"{R}/_eq_optics.png", Inches(0.5), Inches(1.35), Inches(7.2), Inches(4.4))
card(s, Inches(8.0), Inches(1.35), Inches(4.85), Inches(2.4), "Strengths",
     [("Cheap, fast, 96-well throughput.", {"size": 12.5, "bullet": True}),
      ("Maps the coacervation window across dilution.", {"size": 12.5, "bullet": True}),
      ("Objective number (AUC) to rank formulas.", {"size": 12.5, "bullet": True, "color": GREEN})],
     accent=GREEN)
card(s, Inches(8.0), Inches(3.95), Inches(4.85), Inches(2.5), "Limitations",
     [("Optical proxy \u2014 measures turbidity, not coacervate MASS.", {"size": 12.5, "bullet": True, "color": CORAL}),
      ("Can't tell droplet SIZE or liquid-vs-solid.", {"size": 12.5, "bullet": True}),
      ("Needs microscopy + deposition to confirm mechanism.", {"size": 12.5, "bullet": True})],
     accent=CORAL)
footer(s)

# ---- 7 AUTOMATION / HAMILTON
s = prs.slides.add_slide(BLANK)
title_bar(s, "The automation opportunity \u2014 Hamilton robot",
          "Scale %T + phase diagrams from days to hours")
add_text(s, Inches(0.55), Inches(1.35), Inches(6.1), Inches(5.1), [
    ("Today's bottleneck is SAMPLE PREP, not the read:", {"size": 14, "bold": True, "color": NAVY}),
    ("Prep: hand-pipetting dilution series & grids is slow and variable.", {"size": 13, "bullet": True}),
    ("Run: the plate read itself is fast (~15 min/plate).", {"size": 13, "bullet": True}),
    ("Analysis: now digitized \u2014 auto-parse, fit, AUC, rank.", {"size": 13, "bullet": True, "color": GREEN}),
    ("Hamilton automates the prep \u2192 more plates/day, tighter data, freed-up scientist time.",
     {"size": 13.5, "bullet": True, "bold": True, "color": CORAL}),
])
card(s, Inches(6.9), Inches(1.35), Inches(5.95), Inches(5.1), "Ways to accelerate",
     [("Robotic dilution-series + phase-grid dispensing (worklists auto-generated).",
       {"size": 12.8, "bullet": True}),
      ("Standard plate maps \u2192 auto-ingest straight into the analysis pipeline.",
       {"size": 12.8, "bullet": True}),
      ("Pre-mixed stock library + barcode tracking.", {"size": 12.8, "bullet": True}),
      ("Batch by pH / ratio to cut changeovers (2\u20134 \u2192 6\u20138 runs/day).",
       {"size": 12.8, "bullet": True, "color": GREEN}),
      ("One-click report: plate \u2192 figures \u2192 Nexus/cloud.", {"size": 12.8, "bullet": True, "color": BLUE})],
     accent=BLUE)
footer(s)

# ---- 8 PHASE DIAGRAMS
s = prs.slides.add_slide(BLANK)
title_bar(s, "Phase diagrams \u2014 from trial-and-error to a MAP",
          "Where does a formula coacervate? Draw the whole territory at once")
add_text(s, Inches(0.55), Inches(1.35), Inches(6.2), Inches(5.1), [
    ("A phase diagram maps coacervation across a 2-D composition grid \u2014 one picture shows the entire 'sweet spot'.",
     {"size": 13.5, "bullet": True}),
    ("Turns formulation from guess-and-check into predictive design.", {"size": 13.5, "bullet": True, "color": NAVY, "bold": True}),
    ("Already proven on rhamnolipid \u00d7 water-hardness \u2014 hardness reshapes the region differently per polymer.",
     {"size": 13, "bullet": True}),
    ("Next: co-surfactant phase diagrams (CAPB / NaLAA / CAPHS \u00d7 anionics \u00d7 polymers).",
     {"size": 13, "bullet": True, "color": GREEN}),
])
card(s, Inches(6.95), Inches(1.35), Inches(5.9), Inches(5.1), "Who in the business needs this?",
     [("Formulators \u2014 pick winning chassis fast, avoid dead ends.", {"size": 12.8, "bullet": True}),
      ("Sustainability \u2014 qualify biodegradable polymers vs benchmarks.", {"size": 12.8, "bullet": True, "color": GREEN}),
      ("Competitive intel \u2014 reverse-engineer why rivals feel good.", {"size": 12.8, "bullet": True, "color": CORAL}),
      ("Fragrance & actives \u2014 predict deposition of perfume / AD / silicone.", {"size": 12.8, "bullet": True, "color": BLUE}),
      ("Water-hardness / regional \u2014 design for real-world consumer water.", {"size": 12.8, "bullet": True})],
     accent=GREEN)
footer(s)

# ---- 9 COMPETITIVE BENCHMARKING
s = prs.slides.add_slide(BLANK)
title_bar(s, "Competitive benchmarking \u2014 us vs the market, one scale",
          "Objective coacervation data on the shampoos consumers actually buy")
add_image(s, f"{R}/competitor_2026090_auc.png", Inches(0.5), Inches(1.35), Inches(7.6), Inches(4.7))
card(s, Inches(8.35), Inches(1.35), Inches(4.5), Inches(5.0), "The plan",
     [("Run %T on the full competitive set: Dove, L'Or\u00e9al Elvive, Pantene DMR, K\u00e9rastase Nutritive, and more.",
       {"size": 12.8, "bullet": True, "color": NAVY}),
      ("Link to consumer data for those products \u2014 does coacervation predict what shoppers say?",
       {"size": 12.8, "bullet": True, "color": GREEN}),
      ("Read the CURVE, not just the number (e.g., T/Sal's turbidity is drug precipitation, not coacervation).",
       {"size": 12.5, "bullet": True, "italic": True}),
      ("Output: a living superiority scoreboard.", {"size": 12.8, "bullet": True, "color": CORAL, "bold": True})],
     accent=CORAL)
footer(s)

# ---- 10 MY PROJECT
s = prs.slides.add_slide(BLANK)
title_bar(s, "My project \u2014 and why it's important",
          "A digital platform + a sustainable-polymer discovery engine")
add_image(s, f"{R}/dextran_1pct_chassis_grid_fit.png", Inches(0.45), Inches(1.3), Inches(8.5), Inches(4.9))
card(s, Inches(9.05), Inches(1.3), Inches(3.8), Inches(5.1), "What I've built",
     [("A platform: upload \u2192 organize \u2192 plot \u2192 rank %T, one source of truth.",
       {"size": 12, "bullet": True}),
      ("Screened Dow biodegradable dextrans across 3 chassis \u2014 found LAPB activates coacervation & Dex-K leads.",
       {"size": 12, "bullet": True, "color": GREEN}),
      ("Benchmarked in-market & competitors; built a feel\u2194coacervation Trends view.",
       {"size": 12, "bullet": True, "color": BLUE}),
      ("Grounded it in the deposition literature (size vs type vs amount).",
       {"size": 12, "bullet": True})],
     accent=GREEN)
footer(s)

# ---- 11 IDEAS / AUTOMATE
s = prs.slides.add_slide(BLANK)
title_bar(s, "Ideas to simplify & automate \u2014 the roadmap")
card(s, Inches(0.5), Inches(1.35), Inches(4.05), Inches(5.1), "Speed",
     [("Hamilton auto-prep + auto-generated worklists.", {"size": 12.5, "bullet": True}),
      ("Robot file \u2192 pipeline with zero manual steps.", {"size": 12.5, "bullet": True}),
      ("6\u20138 runs/day via batching.", {"size": 12.5, "bullet": True, "color": GREEN})],
     accent=BLUE)
card(s, Inches(4.65), Inches(1.35), Inches(4.05), Inches(5.1), "Intelligence",
     [("Predict coacervation region from composition (model the phase map).",
       {"size": 12.5, "bullet": True}),
      ("ML on feel\u2194coacervation to forecast consumer scores.", {"size": 12.5, "bullet": True, "color": CORAL}),
      ("Auto-flag artifacts & mechanism (coacervate vs precipitate).", {"size": 12.5, "bullet": True})],
     accent=CORAL)
card(s, Inches(8.8), Inches(1.35), Inches(4.05), Inches(5.1), "Reach",
     [("Self-serve dashboard for formulators & CI.", {"size": 12.5, "bullet": True}),
      ("Auto-push results to Nexus / cloud.", {"size": 12.5, "bullet": True, "color": BLUE}),
      ("Living competitive scoreboard + sustainability tracker.", {"size": 12.5, "bullet": True, "color": GREEN})],
     accent=GREEN)
footer(s)

# ---- 12 EXTERNAL CAPABILITY ASK
s = prs.slides.add_slide(BLANK)
title_bar(s, "The missing piece: let's SEE the coacervates",
          "%T tells us how much haze \u2014 imaging tells us why")
add_text(s, Inches(0.55), Inches(1.35), Inches(7.2), Inches(5.0), [
    ("Ask: secure external imaging capability for coacervates.", {"size": 15, "bold": True, "color": CORAL}),
    ("Microscopy / cryo-TEM / confocal \u2014 measure droplet SIZE, structure, liquid-vs-solid.",
     {"size": 13.5, "bullet": True}),
    ("This closes the gap the literature says matters most: size & type drive deposition, not turbidity alone.",
     {"size": 13.5, "bullet": True, "color": NAVY, "bold": True}),
    ("Confirms our nanometric-dextran hypothesis \u2014 high deposition WITHOUT large flocs (better feel).",
     {"size": 13.5, "bullet": True, "color": GREEN}),
])
card(s, Inches(8.0), Inches(1.35), Inches(4.85), Inches(5.0), "Partner capabilities",
     [("Fragrance \u2014 perfume deposition via coacervate; joint value story.",
       {"size": 13, "bullet": True, "color": BLUE}),
      ("NMR \u2014 structural / compositional read of the coacervate phase.",
       {"size": 13, "bullet": True, "color": TEAL}),
      ("Together: %T (screen) + imaging (size) + NMR (structure) + deposition (truth) = full picture.",
       {"size": 13, "bullet": True, "bold": True, "color": NAVY})],
     accent=BLUE)
footer(s)

# ---- 13 STAKEHOLDERS
s = prs.slides.add_slide(BLANK)
title_bar(s, "Who we win with \u2014 stakeholders & collaborators")
add_text(s, Inches(0.55), Inches(1.35), Inches(12.2), Inches(0.7), [
    ("Coacervation touches many teams \u2014 this platform is the shared, objective language between them.",
     {"size": 14, "color": DARK})])
chip(s, Inches(0.6), Inches(2.4), Inches(3.0), "Formulators", BLUE)
chip(s, Inches(3.8), Inches(2.4), Inches(3.0), "Competitive Intel", CORAL)
chip(s, Inches(7.0), Inches(2.4), Inches(3.0), "Sustainability", GREEN)
chip(s, Inches(10.2), Inches(2.4), Inches(2.6), "Actives / AD", TEAL)
chip(s, Inches(0.6), Inches(3.2), Inches(3.0), "Fragrance", GOLD)
chip(s, Inches(3.8), Inches(3.2), Inches(3.0), "NMR / Analytical", NAVY)
chip(s, Inches(7.0), Inches(3.2), Inches(3.0), "Tommy Smith", BLUE)
chip(s, Inches(10.2), Inches(3.2), Inches(2.6), "Lisa Bards", CORAL)
card(s, Inches(0.6), Inches(4.15), Inches(12.25), Inches(2.3), "How we plug in",
     [("Give formulators a fast superiority read; give CI a competitor scoreboard; give Sustainability a biodegradable-polymer qualifier.",
       {"size": 13, "bullet": True}),
      ("Co-develop with Fragrance (perfume deposition) and NMR/imaging (coacervate structure & size).",
       {"size": 13, "bullet": True, "color": GREEN}),
      ("Named partners \u2014 Tommy Smith & Lisa Bards \u2014 to align scope, priorities, and external capability.",
       {"size": 13, "bullet": True, "color": NAVY})],
     accent=GREEN)
footer(s)

# ---- 14 THE ASK / WIN
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(1.75), Inches(3.6), Pt(4))
bar.fill.solid(); bar.fill.fore_color.rgb = GOLD; bar.line.fill.background()
add_text(s, Inches(0.9), Inches(0.85), Inches(11.6), Inches(1.0), [
    ("The ask \u2014 and the win", {"size": 34, "bold": True, "color": WHITE})])
add_text(s, Inches(0.9), Inches(2.05), Inches(11.6), Inches(3.2), [
    ("1.  Hamilton robot time \u2014 automate prep, scale %T + phase diagrams.", {"size": 17, "color": WHITE, "bold": True}),
    ("2.  External imaging capability \u2014 SEE coacervate size & structure.", {"size": 17, "color": WHITE, "bold": True}),
    ("3.  Competitor samples + consumer data \u2014 build the superiority scoreboard.", {"size": 17, "color": WHITE, "bold": True}),
    ("4.  Partner alignment \u2014 Fragrance, NMR, CI, Sustainability.", {"size": 17, "color": WHITE, "bold": True}),
])
add_text(s, Inches(0.9), Inches(5.5), Inches(11.6), Inches(1.4), [
    ("The prize: predict and deliver irresistibly superior, sustainable hair care \u2014",
     {"size": 18, "color": GOLD, "bold": True}),
    ("faster, cheaper, and with the science to prove we WIN.", {"size": 18, "color": GOLD, "bold": True}),
])

out = os.path.join(R, "Coacervation_Leadership_Deck.pptx")
prs.save(out)
print("wrote", out, "slides:", len(prs.slides._sldIdLst))
