"""VP Band 5 Review deck: 'Automated Coacervation Capability: From Data to
Irresistibly Superior Hair Care' - built from Kyla Fung's real project decks
(VP Band 5 slides, DOW dextran Phase 1a/1b analysis, Impact Journey Map) plus
this platform's own generated figures (Reports/) for Lasentec, phase-diagram,
and DOW dextran charts.

Palette: user-provided pastel swatches (dusty rose / lavender-grey / mauve /
teal-blue / light cyan) - matches the app's existing subtab palette.

Output: Reports/KylaFung_Coacervation_Project_Presentation.pptx
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

R = "Reports"
FONT = "Abadi"

# ---- palette (pastel swatches provided by user) ----
ROSE = RGBColor(0xDB, 0xCD, 0xD1)      # dusty rose
LAVENDER = RGBColor(0xE3, 0xDE, 0xE2)  # light lavender-grey
MAUVE = RGBColor(0xC2, 0xA6, 0xB0)     # mauve/pink (primary accent)
TEALBLUE = RGBColor(0x8F, 0xAF, 0xBA)  # teal-blue (secondary accent)
CYAN = RGBColor(0xD2, 0xEF, 0xEE)      # light cyan
DARK = RGBColor(0x3A, 0x2E, 0x33)      # deep plum-navy (text)
GREY = RGBColor(0x6B, 0x60, 0x64)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CORAL = RGBColor(0xC0, 0x39, 0x2B)
GREEN = RGBColor(0x2E, 0x9E, 0x5B)

SECTIONS = ["Why Coacervates", "3 Pillars", "DOW Real Data", "M&S / Phase Diagram", "Future Work"]
SEC_COLORS = [ROSE, MAUVE, TEALBLUE, CYAN, LAVENDER]


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


def title_bar(s, section_idx, title, sub=None):
    color = SEC_COLORS[section_idx] if section_idx is not None else MAUVE
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(1.05))
    bar.fill.solid(); bar.fill.fore_color.rgb = color; bar.line.fill.background()
    tf = bar.text_frame; tf.margin_left = Inches(0.5); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; r = p.add_run(); r.text = title
    _set_font(r, size=24, bold=True, color=DARK)
    if sub:
        p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = sub
        _set_font(r2, size=12.5, color=DARK)
    accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(1.05), SW, Pt(4))
    accent.fill.solid(); accent.fill.fore_color.rgb = TEALBLUE; accent.line.fill.background()


def progress_bar(s, active_idx):
    """5-segment section progress bar, footer."""
    n = len(SECTIONS); gap = Pt(4); total_w = SW - Inches(1.0)
    seg_w = int((total_w - gap * (n - 1)) / n)
    x = Inches(0.5); y = Inches(7.12)
    for i, label in enumerate(SECTIONS):
        active = (i == active_idx)
        c = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, seg_w, Inches(0.3))
        c.fill.solid(); c.fill.fore_color.rgb = MAUVE if active else LAVENDER
        c.line.fill.background()
        tf = c.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = label
        _set_font(r, size=8.5, bold=active, color=WHITE if active else GREY)
        x += seg_w + gap


def footer_text(s, n):
    add_text(s, Inches(11.6), Inches(7.1), Inches(1.5), Inches(0.3),
             [(f"{n} / 29", {"size": 9, "color": GREY})], align=PP_ALIGN.RIGHT)


def new_slide(section_idx, title, sub=None, slide_num=None):
    s = prs.slides.add_slide(BLANK)
    title_bar(s, section_idx, title, sub)
    if section_idx is not None:
        progress_bar(s, section_idx)
    if slide_num:
        footer_text(s, slide_num)
    return s


def card(s, l, t, w, h, header, lines, accent=MAUVE, fc=None):
    fc = fc or WHITE
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    box.fill.solid(); box.fill.fore_color.rgb = fc; box.line.color.rgb = accent
    box.line.width = Pt(1.25)
    hd = [(header, {"size": 14.5, "bold": True, "color": DARK})] if header else []
    add_text(s, l + Inches(0.22), t + Inches(0.14), w - Inches(0.44), h - Inches(0.28), hd + lines)


def divider_slide(section_idx, title, bullets, slide_num):
    s = prs.slides.add_slide(BLANK)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    bg.fill.solid(); bg.fill.fore_color.rgb = SEC_COLORS[section_idx]; bg.line.fill.background()
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(2.55), Inches(3.6), Pt(5))
    bar.fill.solid(); bar.fill.fore_color.rgb = DARK; bar.line.fill.background()
    add_text(s, Inches(0.9), Inches(1.2), Inches(11.6), Inches(1.3), [
        (f"Section {section_idx + 1} of {len(SECTIONS)}", {"size": 14, "bold": True, "color": DARK}),
    ])
    add_text(s, Inches(0.9), Inches(2.75), Inches(11.6), Inches(1.4), [
        (title, {"size": 36, "bold": True, "color": DARK}),
    ])
    add_text(s, Inches(0.9), Inches(4.3), Inches(10.8), Inches(2.2),
             [(b, {"size": 15, "color": DARK, "bullet": True}) for b in bullets])
    progress_bar(s, section_idx)
    footer_text(s, slide_num)
    return s


# =============================================================== recreated charts (from real numbers in the source decks)
def make_floc_fragrance_chart(path):
    brands = ["Pantene\nDMR", "L'Oreal\nHyaluron Plump", "Kerastase\nNutritive", "Dove\nIntensive Repair"]
    floc = [3.8, 4.7, 5.4, 18.8]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    bars = ax.bar(brands, floc, color=["#8FAFBA", "#C2A6B0", "#C2A6B0", "#DB6B4F"])
    for b, v in zip(bars, floc):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v}\u00b5m", ha="center", fontsize=11, fontweight="bold")
    ax.set_ylabel("Floc size at 1:49 dilution (\u00b5m)", fontsize=11)
    ax.set_title("Lasentec floc-size hierarchy \u2014 4 competitive brands", fontsize=13, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=170); plt.close(fig)


def make_fragrance_t2b_chart(path):
    labels = ["10-hour top-2-box", "4\u20138 hr top-2-box"]
    pantene = [35, 41]
    dove = [61, 68]
    x = np.arange(len(labels)); w = 0.32
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    ax.bar(x - w / 2, pantene, w, label="Pantene DMR (3.8\u00b5m floc)", color="#8FAFBA")
    ax.bar(x + w / 2, dove, w, label="Dove Intensive Repair (18.8\u00b5m floc)", color="#DB6B4F")
    for xi, (p_, d_) in enumerate(zip(pantene, dove)):
        ax.text(xi - w / 2, p_ + 1.5, f"{p_}%", ha="center", fontsize=10)
        ax.text(xi + w / 2, d_ + 1.5, f"{d_}%", ha="center", fontsize=10)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10.5)
    ax.set_ylabel("Consumer fragrance longevity (%)", fontsize=11)
    ax.set_title("Floc size correlates with fragrance retention (r = 0.97)", fontsize=12.5, fontweight="bold")
    ax.legend(fontsize=9, loc="upper left"); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=170); plt.close(fig)


def make_dow_auc_window_chart(path):
    """1:1-1:20 consumer-window AUC, 0.4% vs 1%, by chassis - exact values from
    Kyla's Developmental Dextrans Coacervation Analysis deck (Sept 2026)."""
    polymers = ["CD2", "Dex-K", "3196", "Dex-A", "Dex-B", "Dex-B*", "Dex-J", "Dex-J*"]
    data = {
        "EED0 (base)": {"0.4%": [0.131, 0.066, 0.086, 0.019, 0.019, 0.019, 0.018, 0.018],
                        "1%":   [0.130, 0.084, None, 0.021, 0.018, 0.018, 0.018, 0.018]},
        "70% base + LAPB": {"0.4%": [0.113, 0.069, 0.097, 0.023, 0.018, 0.018, 0.018, 0.019],
                            "1%":   [0.192, 0.150, None, 0.031, 0.018, 0.018, 0.039, 0.153]},
        "70% base + APG": {"0.4%": [0.068, 0.049, 0.041, 0.019, 0.018, 0.018, 0.017, 0.017],
                           "1%":   [0.086, 0.064, None, 0.023, 0.018, 0.017, 0.018, 0.019]},
    }
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), sharey=True)
    x = np.arange(len(polymers)); w = 0.36
    for ax, (chassis, d) in zip(axes, data.items()):
        v04 = [v if v is not None else 0 for v in d["0.4%"]]
        v1 = [v if v is not None else 0 for v in d["1%"]]
        ax.bar(x - w / 2, v04, w, label="0.4%", color="#DB9E6B")
        ax.bar(x + w / 2, v1, w, label="1%", color="#3A5F66")
        ax.set_xticks(x); ax.set_xticklabels(polymers, rotation=45, ha="right", fontsize=9)
        ax.set_title(chassis, fontsize=12, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Coacervation AUC (1:1\u20131:20 window)", fontsize=10.5)
    axes[0].legend(fontsize=9)
    fig.suptitle("DOW Dextran Phase 1a (0.4%) vs Phase 1b (1%): coacervation AUC by chassis & polymer",
                 fontsize=13.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=170); plt.close(fig)


make_floc_fragrance_chart(f"{R}/vp_floc_fragrance.png")
make_fragrance_t2b_chart(f"{R}/vp_fragrance_t2b.png")
make_dow_auc_window_chart(f"{R}/vp_dow_auc_window.png")

# =============================================================== 1. HERO
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
bg.fill.solid(); bg.fill.fore_color.rgb = DARK; bg.line.fill.background()
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(2.95), Inches(3.6), Pt(5))
bar.fill.solid(); bar.fill.fore_color.rgb = TEALBLUE; bar.line.fill.background()
add_text(s, Inches(0.9), Inches(0.6), Inches(6), Inches(0.5), [
    ("R&D BEAUTY ANALYTICAL", {"size": 13, "bold": True, "color": CYAN}),
])
add_text(s, Inches(0.9), Inches(1.6), Inches(11.6), Inches(2.6), [
    ("Automated Coacervation Capability:", {"size": 38, "bold": True, "color": WHITE}),
    ("From Data to Irresistibly Superior Hair Care", {"size": 30, "bold": True, "color": ROSE}),
])
add_text(s, Inches(0.9), Inches(4.4), Inches(11.6), Inches(2.2), [
    ("From a one-off manual test to an automated capability that explains real", {"size": 17, "color": WHITE}),
    ("competitive gaps and de-risks sustainable innovation \u2014 with a roadmap to predictive.", {"size": 17, "color": WHITE}),
    ("Kyla Fung \u00b7 R&D Beauty Analytical \u00b7 VP Band 5 Review \u00b7 September 2026", {"size": 14, "color": CYAN, "italic": True}),
])

# =============================================================== 2. ABOUT ME
s = new_slide(None, "About Me", "R&D Beauty Analytical \u00b7 Rotation Overview", 2)
card(s, Inches(0.6), Inches(1.35), Inches(5.9), Inches(5.5), "Kyla Fung", [
    ("Rotation: R&D Beauty Analytical", {"size": 14, "bold": True}),
    ("Focus: Coacervation science, automated characterization,", {"size": 13}),
    ("and competitive/sustainable-innovation intelligence for Hair Care", {"size": 13}),
    ("", {"size": 6}),
    ("Rotation start: July 13, 2026", {"size": 13, "bullet": True}),
    ("Owns the coacervation platform end-to-end: experiment design,", {"size": 13, "bullet": True}),
    ("Hamilton/SpectraMax automation, Python analysis pipeline, Nexus", {"size": 13}),
    ("data activation, and competitive/DOW partner-facing readouts", {"size": 13}),
], accent=MAUVE, fc=CYAN)
card(s, Inches(6.75), Inches(1.35), Inches(5.95), Inches(5.5), "Rotation Timeline", [
    ("Jul 2026 \u2014 Onboarded; learned Hamilton, %T \u2192 AUC pipeline", {"size": 13, "bullet": True}),
    ("Aug 2026 \u2014 First DOW 24-formula dataset; digital-capability vision;", {"size": 13, "bullet": True}),
    ("published first Technical Report + SLR", {"size": 13}),
    ("Sep 2026 \u2014 Learned Lasentec/FBRM + light microscopy; first", {"size": 13, "bullet": True}),
    ("competitor benchmarking; second DOW presentation; M&S T2P plan", {"size": 13}),
    ("Now \u2014 VP Band 5 Review: strategic intent, learnings, and asks", {"size": 13, "bold": True, "bullet": True}),
    ("Next \u2014 Oct 2026\u2013Jul 2027: rheology method, decision tree, matched", {"size": 13, "bullet": True}),
    ("structure-property-performance dataset, digital platform pilot", {"size": 13}),
], accent=TEALBLUE, fc=LAVENDER)

# =============================================================== 3. TABLE OF CONTENTS
s = new_slide(None, "Table of Contents", "Five sections \u2014 from why coacervates matter to where we go next.", 3)
toc_items = [
    ("1", "Why Coacervates Matter", "Business case \u00b7 competitive intelligence \u00b7 the Dove/L'Oreal gaps", ROSE),
    ("2", "Three Strategic Pillars", "Automated capability \u00b7 characterization framework \u00b7 PD partnership", MAUVE),
    ("3", "DOW Dextran \u2014 Real Data", "Phase 1a (0.4%) & Phase 1b (1%): %T, AUC, salt, shake vs no-shake", TEALBLUE),
    ("4", "M&S Partnership & Phase Diagram", "T2P linkage \u00b7 phase-diagram mapping \u00b7 Tg exploration", CYAN),
    ("5", "Learnings, Impact & Future Work", "Business impact summary \u00b7 rheology gap \u00b7 ingredient-behavior plan \u00b7 asks", LAVENDER),
]
y = Inches(1.35)
for num, title, desc, color in toc_items:
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), y, Inches(12.1), Inches(1.02))
    box.fill.solid(); box.fill.fore_color.rgb = color; box.line.fill.background()
    tf = box.text_frame; tf.margin_left = Inches(0.25); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; r = p.add_run(); r.text = f"{num}   {title}"
    _set_font(r, size=17, bold=True, color=DARK)
    p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = desc
    _set_font(r2, size=12, color=DARK)
    y += Inches(1.15)

# =============================================================== SECTION 1: WHY COACERVATES MATTER
divider_slide(0, "Why Coacervates Matter", [
    "The business case for coacervate science",
    "Structure-property relationships",
    "Competitor intelligence & the Dove advantage",
], 4)

s = new_slide(0, "The Delivery Vehicle That Wins or Loses Consumers", None, 5)
card(s, Inches(0.6), Inches(1.35), Inches(7.5), Inches(1.0), None, [
    ("Coacervates are not a chemistry byproduct \u2014 they are the mechanism that deposits every", {"size": 13.5, "bold": True}),
    ("conditioning benefit onto hair, and their properties directly determine what consumers feel.", {"size": 13.5, "bold": True}),
], accent=MAUVE, fc=CYAN)
card(s, Inches(0.6), Inches(2.5), Inches(7.5), Inches(2.5), None, [
    ("When shampoo dilutes during rinsing, cationic polymer + anionic surfactant phase-", {"size": 12.5, "bullet": True}),
    ("separate into a concentrated coacervate droplet", {"size": 12.5}),
    ("The coacervate carries silicone conditioners, anti-dandruff actives (ZPT), and", {"size": 12.5, "bullet": True}),
    ("fragrance onto hair \u2014 deposition is driven by coacervate, not formulation alone", {"size": 12.5}),
    ("Amount \u00b7 Size \u00b7 Morphology \u00b7 Rheology are directly tunable via polymer MW, charge", {"size": 12.5, "bullet": True}),
    ("density, surfactant blend, and chassis \u2014 a formulation design lever, not just an outcome", {"size": 12.5}),
], accent=TEALBLUE)
card(s, Inches(0.6), Inches(5.15), Inches(7.5), Inches(1.6), "Business risk if unknown", [
    ("Competitors with better-tuned coacervates win silently on wet conditioning feel,", {"size": 12.5}),
    ("fragrance longevity, and anti-dandruff efficacy \u2014 and we cannot diagnose why", {"size": 12.5}),
    ("without this framework.", {"size": 12.5}),
], accent=CORAL, fc=RGBColor(0xF7, 0xE3, 0xDF))
card(s, Inches(8.3), Inches(1.35), Inches(4.4), Inches(5.4), "Coacervate Delivery Sequence", [
    ("1 \u00b7 In Bottle", {"size": 13, "bold": True}),
    ("Cationic polymer & anionic surfactant co-exist; conditioners/ZPT/fragrance distributed", {"size": 11.5}),
    ("2 \u00b7 Rinse", {"size": 13, "bold": True}),
    ("Water dilutes the shampoo; ionic strength & concentration shift polymer\u2013surfactant interactions", {"size": 11.5}),
    ("3 \u00b7 Phase Separation", {"size": 13, "bold": True}),
    ("Complex phase-separates into dense coacervate droplets that concentrate actives", {"size": 11.5}),
    ("4 \u00b7 Deposition on Hair", {"size": 13, "bold": True}),
    ("Coacervate adheres to negatively-charged hair; amount/size/morphology/rheology set feel", {"size": 11.5}),
], accent=MAUVE, fc=LAVENDER)

s = new_slide(0, "Why Competitor Products Outperform \u2014 The Coacervate Explanation", None, 6)
card(s, Inches(0.6), Inches(1.35), Inches(6.0), Inches(1.15), None, [
    ("Dove achieves 5\u00d7 larger coacervate flocs than Pantene, correlating almost perfectly", {"size": 13, "bold": True}),
    ("(r = 0.97) with consumer fragrance longevity advantage.", {"size": 13, "bold": True}),
], accent=CORAL, fc=RGBColor(0xF7, 0xE3, 0xDF))
add_image(s, f"{R}/vp_floc_fragrance.png", Inches(0.6), Inches(2.65), Inches(6.0), Inches(4.15))
add_image(s, f"{R}/vp_fragrance_t2b.png", Inches(6.8), Inches(2.65), Inches(5.9), Inches(4.15))
card(s, Inches(6.8), Inches(1.35), Inches(5.9), Inches(1.15), "The Dove Paradox", [
    ("Largest flocs \u2192 highest deposition \u2192 best fragrance retention, yet no-weigh-down", {"size": 11.5}),
    ("score (63%) stays competitive \u2014 decoupling deposition from feel via architecture.", {"size": 11.5}),
], accent=TEALBLUE, fc=CYAN)

s = new_slide(0, "Competitive Intelligence in Practice \u2014 Lasentec + Microscopy", None, 7)
add_image(s, f"{R}/lasentec_hyaluron_0vs7gpg.png", Inches(0.5), Inches(1.3), Inches(6.1), Inches(3.0))
add_image(s, f"{R}/lasentec_competitors_diwater.png", Inches(6.75), Inches(1.3), Inches(6.1), Inches(3.0))
card(s, Inches(0.5), Inches(4.45), Inches(12.35), Inches(2.4), "What this analysis showed", [
    ("Water hardness shifts floc population: HARD water \u2192 more, smaller particles; SOFT/DI \u2192 fewer,", {"size": 12.5, "bullet": True}),
    ("larger particles \u2014 replicated across FBRM chord-counting AND independent flow-cell optical texture", {"size": 12.5}),
    ("(PSD) analysis on L'Oreal Hyaluron Plump \u2014 a triply cross-validated mechanism", {"size": 12.5}),
    ("Freeze-fracture SEM (Stephanie Riley & Amanda Ritter) revealed L'Oreal's rich lamellar internal", {"size": 12.5, "bullet": True}),
    ("architecture (EGDS sheets, oil-rich droplets 3\u201320+\u00b5m) \u2014 structural complexity invisible any other way", {"size": 12.5}),
    ("Standard condition: 1:49 dilution in DI water; operator network established (Beth Schubert,", {"size": 12.5, "bullet": True}),
    ("Kyla Fung, Parth Shah, Maria Gomez)", {"size": 12.5}),
], accent=MAUVE, fc=WHITE)

# =============================================================== SECTION 2: THREE STRATEGIC PILLARS
divider_slide(1, "Three Strategic Pillars", [
    "Automated capability & digital analysis platform",
    "Characterization framework & competitive intelligence",
    "Strategic PD partnership & sustainable innovation",
], 8)

s = new_slide(1, "Three Pillars Organizing My Work", None, 9)
pillars = [
    ("Pillar 1", "Automated Capability & Digital Analysis Platform", [
        "Hamilton STAR + SpectraMax high-throughput %T and phase-diagram experimentation",
        "Python pipeline: raw plate data \u2192 absorbance \u2192 AUC",
        "Nexus data storage; Beauty Fast activation",
    ], "Outputs: Reusable data assets, Nexus method", ROSE),
    ("Pillar 2", "Characterization Framework & Competitive Intelligence", [
        "Connecting %T \u2192 Lasentec (size), microscopy (morphology), MMFC/flow cell",
        "Mapping internal capability vs. gaps across all 4 coacervate properties",
        "Understanding what WOWs consumers in competitor products",
    ], "Outputs: Competitor benchmarks, capability gap map", MAUVE),
    ("Pillar 3", "Strategic PD Partnership & Sustainable Innovation", [
        "DOW cationic dextran collaboration \u2014 Phase 1a and 1b complete",
        "Beauty STP new polymer screening pipeline",
        "M&S partnership with Sumanth \u2014 T2P linkage experiments",
    ], "Outputs: Sustainable polymer evidence, T2P dataset", TEALBLUE),
]
x = Inches(0.5)
for label, title, bullets, out, color in pillars:
    card(s, x, Inches(1.35), Inches(4.0), Inches(5.4), f"{label}\n{title}",
        [(b, {"size": 11.5, "bullet": True}) for b in bullets] + [("", {"size": 4})] + [(out, {"size": 10.5, "italic": True, "bold": True})],
        accent=color, fc=WHITE)
    x += Inches(4.15)

s = new_slide(1, "Pillar 1 \u2014 Automated Capability & Digital Analysis Platform", None, 10)
card(s, Inches(0.5), Inches(1.35), Inches(6.0), Inches(2.3), "Before (Old State)", [
    ("Manual Excel reformatting; raw plate-reader data required cleanup, copy-paste,", {"size": 12}),
    ("and manual plotting before interpretation. One-off deliverables trapped in local", {"size": 12}),
    ("files \u2014 no formal request pathway for PD partners.", {"size": 12}),
], accent=CORAL, fc=RGBColor(0xF7, 0xE3, 0xDF))
card(s, Inches(6.7), Inches(1.35), Inches(6.0), Inches(2.3), "Now (New Capability)", [
    ("Hamilton STAR prepares dilution/composition plates. SpectraMax captures %T at", {"size": 12}),
    ("600nm, 37\u00b0C, 0\u201315min kinetics. Python pipeline auto-parses, cleans, fits, and", {"size": 12}),
    ("transforms %T \u2192 absorbance \u2192 AUC across 48 dilution points.", {"size": 12}),
], accent=GREEN, fc=CYAN)
card(s, Inches(0.5), Inches(3.85), Inches(12.2), Inches(1.05), "Why Convert %T \u2192 Absorbance?  A = \u2212log\u2081\u2080(%T/100)", [
    ("%T is inverse and saturating (strong responses compressed near zero). Absorbance expands low-%T", {"size": 11.5}),
    ("signals: 10%T\u2192A=1, 1%T\u2192A=2 \u2014 separating strong coacervation responses instead of flattening them.", {"size": 11.5}),
], accent=TEALBLUE, fc=LAVENDER)
add_image(s, f"{R}/plate_cleaned_timecourse.png", Inches(0.5), Inches(5.05), Inches(6.0), Inches(1.9))
card(s, Inches(6.7), Inches(5.05), Inches(6.0), Inches(1.9), "Nexus Method Created", [
    ("\"Beauty ANA PercentT Coacervation\" \u2014 formulators formally submit samples via Nexus.", {"size": 12}),
    ("Working with digital team (Brennan, Andy, Alex, Trevor) to push structured outputs to", {"size": 12}),
    ("Nexus + Beauty Fast: reusable data assets instead of one-off deliverables.", {"size": 12}),
], accent=MAUVE, fc=ROSE)

s = new_slide(1, "Pillar 2 \u2014 Coacervate Characterization Framework", None, 11)
props = [
    ("Amount (%T)", "Automated \u00b7 High-throughput", [
        "Hamilton + SpectraMax: automated 48-point %T dilution profiles",
        "Gap: opaque finished shampoos need inverse %T (in development)",
    ], ROSE),
    ("Size (Lasentec/FBRM)", "Established \u00b7 Operator network", [
        "Counts chord lengths every ~3s during dilution; standard 1:49 in DI water",
        "Gap: limited throughput; chord length \u2260 true diameter",
    ], MAUVE),
    ("Morphology (Microscopy)", "Partial access \u00b7 Low-throughput SEM", [
        "Freeze-fracture SEM (Riley & Ritter): nanoscale lamellar architecture revealed",
        "Gap: sample prep can alter hydrated structure",
    ], TEALBLUE),
    ("Rheology", "CRITICAL GAP \u00b7 No routine method exists", [
        "A small but sticky coacervate can deposit strongly and feel heavy \u2014 size alone",
        "cannot explain outliers. Missing bridge between structure and consumer feel.",
    ], CORAL),
]
pos = [(Inches(0.5), Inches(1.35)), (Inches(6.75), Inches(1.35)), (Inches(0.5), Inches(4.1)), (Inches(6.75), Inches(4.1))]
for (title, status, bullets, color), (l, t) in zip(props, pos):
    fc = RGBColor(0xF7, 0xE3, 0xDF) if color == CORAL else WHITE
    card(s, l, t, Inches(6.1), Inches(2.6), f"{title}\n{status}",
        [(b, {"size": 11.5, "bullet": True}) for b in bullets], accent=color, fc=fc)

s = new_slide(1, "Pillar 3 \u2014 Strategic PD Partnership: DOW & Beauty STP", None, 12)
card(s, Inches(0.5), Inches(1.35), Inches(6.0), Inches(2.5), "Regulatory + Scientific Driver", [
    ("EU revised Urban Wastewater Treatment Directive pressures adoption of readily", {"size": 12}),
    ("biodegradable alternatives. P&G's Ambition 2030 demands irresistible superiority", {"size": 12}),
    ("that is simultaneously sustainable.", {"size": 12}),
    ("DOW's cationic dextrans: dual-quat functionality, tunable hydrophobe, shorter", {"size": 12}),
    ("persistence length than guar/cellulose \u2014 may reproduce PQ-6-like coacervation.", {"size": 12}),
], accent=MAUVE, fc=ROSE)
card(s, Inches(6.7), Inches(1.35), Inches(6.0), Inches(2.5), "My Role & Partners", [
    ("Designed and ran all %T experiments on Hamilton; developed the absorbance/AUC", {"size": 12}),
    ("pipeline; presented Phase 1a (Aug 2026) and Phase 1b (Sep 2026) to DOW.", {"size": 12}),
    ("Partners: Mark Brown (Beauty STP) \u00b7 James Wall (Formulation & Process) \u00b7 DOW", {"size": 12}),
    ("team \u2014 DOW requested the full dataset for further analysis.", {"size": 12}),
], accent=TEALBLUE, fc=CYAN)
card(s, Inches(0.5), Inches(4.05), Inches(12.2), Inches(2.9), "Study Design \u2014 3 Chassis \u00d7 8 Polymers = 24 Profiles Screened", [
    ("Chassis: GH150 EED0 (base) \u00b7 + 3.6% LAPB \u00b7 + 3.6% APG", {"size": 12.5, "bullet": True}),
    ("Polymers: Guar 3196, CD2 (benchmarks) \u00b7 Dex A/B/B*/J/J*/K (developmental dextrans)", {"size": 12.5, "bullet": True}),
    ("Beauty STP screening pipeline extends this to biosurfactants, rhamnolipids, APG/LAPB", {"size": 12.5, "bullet": True}),
    ("variants, salt/no-salt, cold-water, and water-hardness effects \u2014 every run feeds Nexus", {"size": 12.5}),
], accent=GREEN, fc=WHITE)

# =============================================================== SECTION 3: DOW REAL DATA
divider_slide(2, "DOW Dextran \u2014 Real Data", [
    "Phase 1a: 0.4% polymer, 24-formula screen, AUC ranking",
    "Phase 1b: 1% polymer, salt effect, shake vs. no-shake",
    "Chassis \u00d7 polymer structure-activity findings",
], 13)

s = new_slide(2, "Phase 1a \u2014 24-Formula Screen (0.4% Polymer)", None, 14)
card(s, Inches(0.5), Inches(1.35), Inches(12.2), Inches(1.1), "Experimental Design", [
    ("3 chassis (GH150 EED0 base / +3.6% LAPB / +3.6% APG) \u00d7 8 polymers (Guar 3196, CD2 benchmark,", {"size": 12.5}),
    ("Dex A/B/B*/J/J*/K developmental) = 24 profiles. Readout: %T at 600nm/37\u00b0C, 48 dilution points, 0\u201315min.", {"size": 12.5}),
], accent=MAUVE, fc=ROSE)
add_image(s, f"{R}/dextran_04pct_evolution_EED0.png", Inches(0.5), Inches(2.6), Inches(4.0), Inches(4.3))
add_image(s, f"{R}/dextran_04pct_evolution_LAPB.png", Inches(4.65), Inches(2.6), Inches(4.0), Inches(4.3))
add_image(s, f"{R}/dextran_04pct_evolution_APG.png", Inches(8.8), Inches(2.6), Inches(4.0), Inches(4.3))

s = new_slide(2, "Phase 1a \u2014 Key Observations", None, 15)
card(s, Inches(0.5), Inches(1.35), Inches(6.0), Inches(5.4), "Observations", [
    ("1% polymer was tested (not just 0.4%) since at 0.4% most Dex-variants showed", {"size": 12.5, "bullet": True}),
    ("no response, except Dex-K (and a little from Dex-A)", {"size": 12.5}),
    ("Base chassis: early onset (~1:1\u20131:5); CD2 leads, then guar 3196 and Dex-K", {"size": 12.5, "bullet": True}),
    ("LAPB chassis: selectively boosts guar 3196; enables weak coacervation from", {"size": 12.5, "bullet": True}),
    ("Dex-A absent in base chassis", {"size": 12.5}),
    ("APG chassis: lower AUC, shifts onset LATER into the consumer-relevant", {"size": 12.5, "bullet": True}),
    ("1:2\u20131:10 window; dextran-specific second trough appears", {"size": 12.5}),
    ("First turbidity time-course for guar vs. CD2 \u2014 kinetic view revealed differences", {"size": 12.5, "bullet": True}),
    ("invisible in a static endpoint", {"size": 12.5}),
], accent=TEALBLUE, fc=WHITE)
add_image(s, f"{R}/dextran_master_heatmap.png", Inches(6.7), Inches(1.35), Inches(6.0), Inches(5.4))

s = new_slide(2, "Phase 1b \u2014 1% Polymer: Salt Effect & Chassis Ranking", None, 16)
add_image(s, f"{R}/salt_vs_nosalt.png", Inches(0.5), Inches(1.35), Inches(6.0), Inches(3.3))
add_image(s, f"{R}/dextran_1pct_chassis_heatmap.png", Inches(6.7), Inches(1.35), Inches(6.0), Inches(3.3))
card(s, Inches(0.5), Inches(4.8), Inches(12.2), Inches(1.95), "Key Finding \u2014 Electrolyte Is Critical", [
    ("GH150 DDu0 + 3.6% APG + 1% Dex-K: WITH NaCl the trough hits ~53%T (AUC 0.064); WITHOUT NaCl it", {"size": 12.5, "bullet": True}),
    ("barely dips (min 81%T, AUC 0.026) \u2014 2.5\u00d7 LESS coacervation, and even neat product stays clear (87%T).", {"size": 12.5}),
    ("Removing salt also produced a huge viscosity difference \u2014 electrolyte governs both onset and structure.", {"size": 12.5, "bullet": True}),
], accent=CORAL, fc=RGBColor(0xF7, 0xE3, 0xDF))

s = new_slide(2, "Phase 1b \u2014 Concentration Response & AUC Window Sensitivity", None, 17)
add_image(s, f"{R}/vp_dow_auc_window.png", Inches(0.5), Inches(1.35), Inches(12.2), Inches(3.75))
card(s, Inches(0.5), Inches(5.2), Inches(12.2), Inches(1.55), "Observations", [
    ("Concentration mostly AMPLIFIES each chassis's own behavior; Dex-J* in LAPB is the exception \u2014 it", {"size": 12, "bullet": True}),
    ("forms in-situ coacervate in the neat product (cloudy at 1:1) due to high C16 hydrophobe reducing solubility", {"size": 12}),
    ("LAPB: increasing 0.4%\u21921% polymer significantly increases turbidity. Base/APG: mostly flat except Dex-K", {"size": 12, "bullet": True}),
], accent=MAUVE, fc=ROSE)

s = new_slide(2, "Phase 1b \u2014 Chassis Effect Deep-Dive & Shake vs. No-Shake", None, 18)
add_image(s, f"{R}/dextran_1pct_chassis_grid_fit.png", Inches(0.5), Inches(1.35), Inches(7.6), Inches(4.35))
card(s, Inches(8.3), Inches(1.35), Inches(4.4), Inches(2.05), "Dex-K chassis behavior", [
    ("In LAPB, Dex-K's coacervation profile now resembles CD2", {"size": 11.5, "bullet": True}),
    ("more closely than in the base chassis", {"size": 11.5}),
    ("Less time-evolution response vs. base and APG chassis", {"size": 11.5, "bullet": True}),
], accent=TEALBLUE, fc=CYAN)
add_image(s, f"{R}/noshake_vs_shake_eed0.png", Inches(8.3), Inches(3.55), Inches(4.4), Inches(2.15))

s = new_slide(2, "DOW Dextran \u2014 Findings & Business Implication", None, 19)
card(s, Inches(0.5), Inches(1.35), Inches(6.0), Inches(5.4), "Emerging Insights", [
    ("Time-Course Kinetics: Guar/3196 is more time-stable; CD2 shows a strong", {"size": 12, "bullet": True}),
    ("two-phase/time-course response. Kinetic reads prevent single-timepoint misranking.", {"size": 12}),
    ("Nanoparticle Hypothesis: some dextrans show no visible coacervation, yet DOW", {"size": 12, "bullet": True}),
    ("hypothesizes deposition may occur via smaller polymer-surfactant nanostructures.", {"size": 12}),
    ("Active Concentration Matters: developmental dextrans are only 30% active \u2014", {"size": 12, "bullet": True}),
    ("total added polymer \u2260 active dose. Future ranking must account for this.", {"size": 12}),
], accent=TEALBLUE, fc=WHITE)
card(s, Inches(6.7), Inches(1.35), Inches(6.0), Inches(5.4), "Business Implication", [
    ("Lead biodegradable dextrans reach ~80% of the CD2 (dual-quat, non-", {"size": 13, "bold": True}),
    ("biodegradable benchmark) AUC in the LAPB chassis.", {"size": 13, "bold": True}),
    ("", {"size": 8}),
    ("APG chassis + Dex-K shows coacervation shifted INTO the consumer-relevant", {"size": 12}),
    ("dilution window \u2014 if deposition is confirmed, this is a sustainable alternative", {"size": 12}),
    ("that could serve as a formulation design route.", {"size": 12}),
    ("", {"size": 8}),
    ("Phase 1a presented to DOW: Aug 2026. Phase 1b: Sep 2026. DOW requested", {"size": 12}),
    ("the full dataset for further analysis. Next: deposition + microscopy validation.", {"size": 12}),
], accent=GREEN, fc=CYAN)

# =============================================================== SECTION 4: M&S / PHASE DIAGRAM
divider_slide(3, "M&S Partnership & Phase Diagram", [
    "Linking coacervate structure to performance (T2P)",
    "Phase-diagram mapping across polymer \u00d7 surfactant space",
    "Polymer glass transition temperature (Tg) as an explanatory variable",
], 20)

s = new_slide(3, "M&S Partnership \u2014 Linking Coacervate Structure to Performance (T2P)", None, 21)
card(s, Inches(0.5), Inches(1.35), Inches(12.2), Inches(1.0), "Partnership rationale", [
    ("%T and Lasentec tell us how much coacervate forms and how big it is \u2014 but not whether it deposits", {"size": 12.5}),
    ("effectively or what consumers feel. Pairing coacervation measurements with PTL performance closes that loop.", {"size": 12.5}),
], accent=MAUVE, fc=ROSE)
steps = ["Coacervate Properties\nAmount \u00b7 Size \u00b7 Morphology \u00b7 Rheology",
         "Analytical Metrics\n%T \u00b7 AUC \u00b7 Lasentec chord \u00b7 Phase diagram",
         "PTL Performance\nWet conditioning \u00b7 SACS \u00b7 DRF \u00b7 IFF \u00b7 Silicone depo",
         "Consumer Benefit\nRinse feel \u00b7 Dry friction \u00b7 Fragrance longevity"]
x = Inches(0.5)
for i, txt in enumerate(steps):
    title, rest = txt.split("\n")
    card(s, x, Inches(2.55), Inches(2.95), Inches(1.7), title, [(rest, {"size": 10})],
        accent=[ROSE, MAUVE, TEALBLUE, CYAN][i], fc=WHITE)
    x += Inches(3.1)
card(s, Inches(0.5), Inches(4.5), Inches(6.0), Inches(2.25), "1. Role of Coacervates in Wet Conditioning", [
    ("Experimental plan created Aug 2026. Running PTL wet-conditioning panel", {"size": 12}),
    ("(SACS, DRF, IFF) alongside %T/phase data.", {"size": 12}),
    ("Goal: determine whether AUC can predict wet-conditioning score.", {"size": 12, "bold": True}),
], accent=TEALBLUE, fc=CYAN)
card(s, Inches(6.7), Inches(4.5), Inches(6.0), Inches(2.25), "2. Polymer Tg as Explanatory Variable", [
    ("Initiated Sep 2026 with Allison and Sumanth. Assessing whether polymer", {"size": 12}),
    ("Tg explains coacervation behavior or conditioning performance across", {"size": 12}),
    ("polymer classes (does a polymer above its Tg form a more cohesive coacervate?).", {"size": 12}),
], accent=MAUVE, fc=ROSE)

s = new_slide(3, "Phase Diagram Work \u2014 Mapping the Coacervation Window", None, 22)
card(s, Inches(0.5), Inches(1.35), Inches(12.2), Inches(1.05), "What phase diagrams add", [
    ("Experiment Type 2 maps WHERE coacervation occurs across polymer concentration vs. surfactant", {"size": 12.5}),
    ("concentration space \u2014 enabling formulation design decisions, not just a single dilution readout.", {"size": 12.5}),
], accent=TEALBLUE, fc=CYAN)
add_image(s, f"{R}/rhamnolipid_hardness_report/figures/contours_AMT.png", Inches(0.5), Inches(2.55), Inches(6.0), Inches(4.2))
add_image(s, f"{R}/rhamnolipid_hardness_report/figures/hardness_summary.png", Inches(6.7), Inches(2.55), Inches(6.0), Inches(4.2))

# =============================================================== SECTION 5: LEARNINGS, IMPACT & FUTURE WORK
divider_slide(4, "Learnings, Impact & Future Work", [
    "Business impact summary across all pillars",
    "The critical rheology gap",
    "Ingredient-level behavior screening plan",
    "Ask & alignment for leadership",
], 23)

s = new_slide(4, "Impact Summary \u2014 What This Work Delivers", None, 24)
rows = [
    ("Speed", "Automated 24-formula screen + scripted Python pipeline", "Faster polymer-screening decisions; less manual rework"),
    ("Quality", "AUC-standardized metrics stored in Nexus", "Apples-to-apples comparisons across projects & partners"),
    ("Competitive Intelligence", "Lasentec + microscopy benchmarking vs. Dove, Pantene, L'Oreal, Kerastase", "Explained the Dove fragrance advantage; identified what WOWs consumers"),
    ("Sustainable Innovation", "DOW dextran Phase 1a+1b; Beauty STP polymer pipeline", "Foundation for biodegradable polymer selection with formulation evidence"),
    ("Digital", "Nexus method created; Beauty Fast website in development", "Each run becomes a reusable enterprise data asset"),
    ("M&S Partnership", "T2P experiments in progress with Sumanth", "Closing the loop from analytical measurement to consumer performance"),
]
top = Inches(1.35); rh = Inches(0.92)
hdr = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), top, Inches(12.3), Inches(0.5))
hdr.fill.solid(); hdr.fill.fore_color.rgb = DARK; hdr.line.fill.background()
tf = hdr.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
p = tf.paragraphs[0]
for col, txt in zip([0, 3.4, 7.3], ["Business Lever", "Accomplishment", "Business Impact"]):
    pass
add_text(s, Inches(0.65), top + Inches(0.06), Inches(2.6), Inches(0.4), [("Business Lever", {"size": 12, "bold": True, "color": WHITE})])
add_text(s, Inches(3.3), top + Inches(0.06), Inches(4.6), Inches(0.4), [("Accomplishment", {"size": 12, "bold": True, "color": WHITE})])
add_text(s, Inches(8.1), top + Inches(0.06), Inches(4.6), Inches(0.4), [("Business Impact", {"size": 12, "bold": True, "color": WHITE})])
y = top + Inches(0.5)
for i, (lever, acc, imp) in enumerate(rows):
    fc = LAVENDER if i % 2 == 0 else WHITE
    row = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), y, Inches(12.3), rh)
    row.fill.solid(); row.fill.fore_color.rgb = fc; row.line.color.rgb = LAVENDER; row.line.width = Pt(0.5)
    add_text(s, Inches(0.65), y + Inches(0.08), Inches(2.6), rh - Inches(0.16), [(lever, {"size": 11.5, "bold": True})])
    add_text(s, Inches(3.3), y + Inches(0.08), Inches(4.6), rh - Inches(0.16), [(acc, {"size": 10.5})])
    add_text(s, Inches(8.1), y + Inches(0.08), Inches(4.6), rh - Inches(0.16), [(imp, {"size": 10.5})])
    y += rh

s = new_slide(4, "The Critical Gap \u2014 Coacervate Rheology", None, 25)
card(s, Inches(0.5), Inches(1.35), Inches(6.0), Inches(2.5), "Why Rheology Is the Gap", [
    ("Quantity, size, and morphology are measurable \u2014 but how a coacervate flows,", {"size": 12}),
    ("deforms, and resists rinse shear determines whether it deposits and what", {"size": 12}),
    ("consumers feel. A small, stiff coacervate can deposit as well as a large soft", {"size": 12}),
    ("one \u2014 with a completely different tactile experience.", {"size": 12}),
], accent=CORAL, fc=RGBColor(0xF7, 0xE3, 0xDF))
card(s, Inches(6.7), Inches(1.35), Inches(6.0), Inches(2.5), "Literature Support", [
    ("Kamo, Mori & Yoshida (2025): coacervate viscoelasticity significantly", {"size": 12, "bullet": True}),
    ("influences sensory attributes incl. conditioning and feel", {"size": 12}),
    ("Hiranuma et al. (2025): coacervate adhesion to hair directly reduces kinetic", {"size": 12, "bullet": True}),
    ("friction coefficient \u2014 rheology at the hair surface matters for performance", {"size": 12}),
], accent=TEALBLUE, fc=CYAN)
card(s, Inches(0.5), Inches(4.05), Inches(12.2), Inches(2.9), "Recommended Development Path", [
    ("1. Define use question (wet feel vs. deposition efficiency vs. rinse-shear resistance)", {"size": 12.5, "bullet": True}),
    ("2. Develop isolation strategy \u2014 only the coacervate phase has diagnostic signal (centrifugation/microfluidic)", {"size": 12.5, "bullet": True}),
    ("3. Pilot rotational viscometry + oscillatory (G', G\") on isolated phase of internal controls", {"size": 12.5, "bullet": True}),
    ("4. Benchmark with internal controls \u2014 Pantene and Dove coacervate isolates anchor known hierarchy", {"size": 12.5, "bullet": True}),
    ("5. Correlate with deposition & sensory \u2014 establish rheology as a predictive T2P variable", {"size": 12.5, "bullet": True}),
], accent=MAUVE, fc=ROSE)

s = new_slide(4, "Future Work \u2014 Ingredient-Behavior Screening Plan", None, 26)
card(s, Inches(0.5), Inches(1.35), Inches(12.2), Inches(1.0), "The idea", [
    ("Build an ingredient \u2192 coacervate-property map: systematically vary ONE ingredient/condition at a time", {"size": 12.5}),
    ("across %T, Lasentec, and phase-diagram experiments, so we know exactly what each lever does before formulating.", {"size": 12.5}),
], accent=TEALBLUE, fc=CYAN)
plan = [
    ("Surfactant + Co-surfactant", "Systematically vary surfactant/co-surfactant blends (e.g. SLES/SLS/AOS/CAPB\nratios) to map how micelle charge & packing shift coacervation onset/AUC", ROSE),
    ("Fragrance \u00d7 Coacervate", "Add fragrance as a 3rd phase-diagram variable; test H1-H3 (fragrance shifts\ncoacervation; coacervate properties change fragrance payload/release)", MAUVE),
    ("Water Hardness", "Extend the DI vs 7gpg comparison across polymers/chassis \u2014 already shows a\nreplicated, triply-validated mechanism (hard=more/finer; soft=fewer/larger)", TEALBLUE),
    ("Water Temperature", "Map coacervation onset/AUC vs. wash/rinse temperature \u2014 untested variable\nthat directly affects the real consumer-use condition", CYAN),
    ("New Surfactants (Rhamnolipids)", "Continue Beauty STP biosurfactant screening (John Kenny collaboration) \u2014\nsustainable surfactant candidates alongside sustainable polymers", ROSE),
    ("New / Developmental Polymers", "Extend structure-activity work beyond DOW dextrans \u2014 systematically vary\nMW, charge density, and hydrophobe substitution", MAUVE),
]
pos6 = [(Inches(0.5), Inches(2.55)), (Inches(4.6), Inches(2.55)), (Inches(8.7), Inches(2.55)),
        (Inches(0.5), Inches(4.85)), (Inches(4.6), Inches(4.85)), (Inches(8.7), Inches(4.85))]
for (title, desc, color), (l, t) in zip(plan, pos6):
    card(s, l, t, Inches(3.95), Inches(2.15), title,
        [(ln, {"size": 10.5}) for ln in desc.split("\n")], accent=color, fc=WHITE)

s = new_slide(4, "Ask & Alignment", None, 27)
card(s, Inches(0.5), Inches(1.5), Inches(3.95), Inches(3.6), "1. Rheology Investment", [
    ("Should coacervate rheology method development be formally prioritized as a", {"size": 12.5}),
    ("Beauty Analytical capability investment for H1 2027?", {"size": 12.5}),
], accent=ROSE, fc=WHITE)
card(s, Inches(4.7), Inches(1.5), Inches(3.95), Inches(3.6), "2. T2P Validation", [
    ("Which performance endpoint should be the PRIMARY proof point for the", {"size": 12.5}),
    ("AUC-to-performance correlation \u2014 PTL silicone deposition, wet-conditioning", {"size": 12.5}),
    ("consumer panel, or another metric?", {"size": 12.5}),
], accent=MAUVE, fc=WHITE)
card(s, Inches(8.9), Inches(1.5), Inches(3.95), Inches(3.6), "3. Ingredient-Behavior Study", [
    ("Is there appetite to fund the systematic ingredient-behavior screening plan", {"size": 12.5}),
    ("(surfactant/co-surfactant, fragrance, hardness, temperature, new", {"size": 12.5}),
    ("surfactants/polymers) as a 2027 exploratory study?", {"size": 12.5}),
], accent=TEALBLUE, fc=WHITE)
card(s, Inches(0.5), Inches(5.35), Inches(12.2), Inches(1.35), "Stakeholder Network Growth", [
    ("Connecting with Jennifer Marsh and Howard Hudson (Band 4/5 Research Fellows, Hair Care) to", {"size": 12}),
    ("showcase capability and align on where it can add the most value.", {"size": 12}),
], accent=CYAN, fc=LAVENDER)

# ---- thank you
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
bg.fill.solid(); bg.fill.fore_color.rgb = DARK; bg.line.fill.background()
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(2.95), Inches(3.6), Pt(5))
bar.fill.solid(); bar.fill.fore_color.rgb = TEALBLUE; bar.line.fill.background()
add_text(s, Inches(0.9), Inches(1.9), Inches(11.6), Inches(1.6), [
    ("Questions & Discussion", {"size": 36, "bold": True, "color": WHITE}),
])
add_text(s, Inches(0.9), Inches(3.5), Inches(11.0), Inches(2.4), [
    ("Scientific validation priorities \u2014 microscopy, deposition, dose response", {"size": 15, "color": ROSE, "bullet": True}),
    ("Digital platform strategy \u2014 Nexus data structure, Beauty Fast rollout", {"size": 15, "color": ROSE, "bullet": True}),
    ("Stakeholder & partner priorities \u2014 Jennifer Marsh, Howard Hudson, DOW team", {"size": 15, "color": ROSE, "bullet": True}),
    ("Rotation goals & future role alignment \u2014 feedback welcome", {"size": 15, "color": ROSE, "bullet": True}),
])
add_text(s, Inches(0.9), Inches(6.4), Inches(11.0), Inches(0.7), [
    ("Thank you \u2014 Kyla Fung  \u00b7  R&D Beauty Analytical  \u00b7  VP Band 5 Review \u00b7 September 2026", {"size": 14, "color": CYAN, "italic": True}),
])

out_path = f"{R}/KylaFung_Coacervation_Project_Presentation.pptx"
prs.save(out_path)
print("Slides:", len(prs.slides.__iter__.__self__._sldIdLst))
print("wrote", out_path)
