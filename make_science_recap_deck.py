"""Build a manager-facing science recap deck (16:9) of the coacervation work to date.

Covers: what coacervation is & why %T, the SpectraMax protocol, the biodegradable
dextran screen (Dow collab) with chassis/concentration/kinetics observations, the
in-market + competitor benchmarking, the optics/AUC method, and the platform tooling.

Reuses figures already in Reports/. Output: Reports/Coacervation_Science_Recap.pptx
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from PIL import Image

FONT = "Abadi"
NAVY = RGBColor(0x00, 0x26, 0x6A)
BLUE = RGBColor(0x2E, 0x75, 0xB6)
LIGHT = RGBColor(0xEE, 0xF3, 0xF9)
GREY = RGBColor(0x5A, 0x64, 0x70)
DARK = RGBColor(0x1E, 0x2A, 0x36)
GREEN = RGBColor(0x2E, 0x9E, 0x5B)
RED = RGBColor(0xC0, 0x39, 0x2B)
AMBER = RGBColor(0xB9, 0x7A, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height
R = "Reports"


def _set_font(run, size=14, bold=False, color=DARK, italic=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", FONT)


def add_text(slide, left, top, width, height, lines, *, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(5)
        txt, opts = (ln, {}) if isinstance(ln, str) else ln
        if opts.get("bullet"):
            txt = "\u2022  " + txt
        r = p.add_run(); r.text = txt
        _set_font(r, size=opts.get("size", 14), bold=opts.get("bold", False),
                  color=opts.get("color", DARK), italic=opts.get("italic", False))
    return tb


def title_bar(slide, title, sub=None):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(1.05))
    bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
    tf = bar.text_frame; tf.margin_left = Inches(0.45); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; r = p.add_run(); r.text = title
    _set_font(r, size=25, bold=True, color=WHITE)
    if sub:
        p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = sub
        _set_font(r2, size=13, color=RGBColor(0xCF, 0xDD, 0xF0))


def footer(slide):
    add_text(slide, Inches(0.45), Inches(7.04), Inches(12.4), Inches(0.38),
             [("Coacervation science recap  \u00b7  Kyla Fung  \u00b7  %T platform + biodegradable-polymer screen",
               {"size": 9, "color": GREY})])


def add_image(slide, path, left, top, max_w, max_h):
    """Add an image fit within (max_w, max_h) box, centered, preserving aspect."""
    if not os.path.exists(path):
        add_text(slide, left, top, max_w, Inches(0.4),
                 [(f"[missing figure: {os.path.basename(path)}]", {"size": 11, "color": RED})])
        return
    with Image.open(path) as im:
        iw, ih = im.size
    ar = iw / ih
    box_ar = max_w / max_h
    if ar >= box_ar:
        w = max_w; h = int(max_w / ar)
    else:
        h = max_h; w = int(max_h * ar)
    l = left + (max_w - w) // 2
    t = top + (max_h - h) // 2
    slide.shapes.add_picture(path, l, t, width=w, height=h)


def card(slide, left, top, width, height, header, lines, accent=BLUE):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT; box.line.color.rgb = accent
    hdr = [(header, {"size": 15, "bold": True, "color": NAVY})] if header else []
    add_text(slide, left + Inches(0.25), top + Inches(0.18),
             width - Inches(0.5), height - Inches(0.3), hdr + lines)


# ==================================================================== 1: title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
add_text(s, Inches(0.9), Inches(1.9), Inches(11.6), Inches(2.4), [
    ("Coacervation Science: Learnings & Observations", {"size": 38, "bold": True, "color": WHITE}),
    ("What %T coacervation tells us about biodegradable conditioning polymers \u2014 and the tooling built to analyze it",
     {"size": 18, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])
accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(3.15), Inches(3.4), Pt(3))
accent.fill.solid(); accent.fill.fore_color.rgb = BLUE; accent.line.fill.background()
add_text(s, Inches(0.9), Inches(4.5), Inches(11.5), Inches(2.2), [
    ("Kyla Fung  \u00b7  Hair Care / Sustainable Polymers", {"size": 17, "bold": True, "color": WHITE}),
    ("Biodegradable cationic dextran screen (Dow collaboration)  +  in-market benchmarking  +  %T analysis platform",
     {"size": 14, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
    ("September 2026", {"size": 13, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])

# ==================================================================== 2: what I've been doing
s = prs.slides.add_slide(BLANK)
title_bar(s, "What I've been working on", "Three connected threads: science, benchmarking, and tooling")
card(s, Inches(0.45), Inches(1.35), Inches(4.05), Inches(5.4), "1 \u00b7 Science",
     [("Screen biodegradable cationic dextrans (Dow collab) for shampoo conditioning via coacervation.",
       {"size": 13, "bullet": True}),
      ("Learn how surfactant chassis, polymer architecture, concentration, and time change the coacervate.",
       {"size": 13, "bullet": True}),
      ("Build mechanistic intuition (why %T behaves the way it does).", {"size": 13, "bullet": True, "color": GREEN})],
     accent=GREEN)
card(s, Inches(4.65), Inches(1.35), Inches(4.05), Inches(5.4), "2 \u00b7 Benchmarking",
     [("Place our formulas against in-market and competitor shampoos on the same %T scale.",
       {"size": 13, "bullet": True}),
      ("Register each plate + product so results are searchable and comparable.", {"size": 13, "bullet": True}),
      ("Correlate coacervation strength with claimed consumer feel.", {"size": 13, "bullet": True, "color": BLUE})],
     accent=BLUE)
card(s, Inches(8.85), Inches(1.35), Inches(4.05), Inches(5.4), "3 \u00b7 Tooling",
     [("A platform to upload \u2192 organize \u2192 plot %T data (no more scattered spreadsheets).",
       {"size": 13, "bullet": True}),
      ("Consistent, reproducible fitting / AUC so every sample is measured the same way.",
       {"size": 13, "bullet": True}),
      ("Foundation to push results to Nexus / cloud.", {"size": 13, "bullet": True, "color": AMBER})],
     accent=AMBER)
footer(s)

# ==================================================================== 3: background - why %T
s = prs.slides.add_slide(BLANK)
title_bar(s, "Background \u2014 what coacervation is & why we measure %T",
          "Coacervation drives deposition of conditioning agents during rinse")
add_text(s, Inches(0.55), Inches(1.35), Inches(7.5), Inches(5.3), [
    ("As shampoo is diluted during rinsing, the cationic polymer + anionic surfactant associate and phase-separate into a coacervate.",
     {"size": 14, "bullet": True}),
    ("That coacervate carries conditioning actives (silicone, anti-dandruff, perfume) onto hair \u2014 it is the deposition vehicle.",
     {"size": 14, "bullet": True}),
    ("Coacervate droplets scatter light, so the mix turns cloudy \u2014 lower % Transmittance (%T) = more coacervate signal.",
     {"size": 14, "bullet": True, "color": BLUE}),
    ("Sweeping a dilution series maps WHERE (at what dilution) and HOW MUCH coacervate forms \u2014 the 'coacervation window'.",
     {"size": 14, "bullet": True}),
    ("Goal: find readily-biodegradable polymers that coacervate as well as today's guar/synthetic benchmarks.",
     {"size": 14, "bullet": True, "color": GREEN}),
])
card(s, Inches(8.35), Inches(1.5), Inches(4.55), Inches(4.9), "The consumer-relevant window",
     [("In use, shampoo is diluted roughly 1:1 to 1:20 with water at the scalp.",
       {"size": 13, "bullet": True}),
      ("We integrate the coacervation response across that window (AUC) as the headline strength metric.",
       {"size": 13, "bullet": True}),
      ("Deeper / broader trough in that window = more deposition potential.", {"size": 13, "bullet": True})],
     accent=BLUE)
footer(s)

# ==================================================================== 4: method / protocol
s = prs.slides.add_slide(BLANK)
title_bar(s, "Method \u2014 SpectraMax %T read protocol", "Automated 96-well kinetic turbidity across a dilution series")
add_text(s, Inches(0.55), Inches(1.35), Inches(6.5), Inches(5.4), [
    ("Read: 600 nm transmittance, 37 \u00b0C (in-use temperature).", {"size": 14, "bullet": True}),
    ("Kinetic: 15 min total, one read every 1 min; plate shaken ~37 s between reads (stays homogeneous).",
     {"size": 14, "bullet": True}),
    ("Each row = one formula diluted across 12+ steps (a full dilution series per sample).",
     {"size": 14, "bullet": True}),
    ("Convert to absorbance  A = \u2212log10(%T/100)  so signal is proportional to coacervate load (Beer\u2013Lambert).",
     {"size": 14, "bullet": True, "color": BLUE}),
    ("Fit a smooth curve, then integrate AUC over the consumer window for a single comparable number.",
     {"size": 14, "bullet": True}),
    ("Artifact cleaning removes isolated single-well bubble spikes but keeps real multi-well troughs.",
     {"size": 13, "bullet": True, "italic": True}),
])
card(s, Inches(7.3), Inches(1.5), Inches(5.55), Inches(2.2), "Why absorbance, not raw %T?",
     [("%T is bounded 0\u2013100, inverse, and non-additive.", {"size": 13, "bullet": True}),
      ("A = \u2212log10(%T/100) is unbounded, direct, additive \u2014 peak height \u2248 amount, area \u2248 total load.",
       {"size": 13, "bullet": True})], accent=GREEN)
add_image(s, f"{R}/_eq_optics.png", Inches(7.3), Inches(3.85), Inches(5.55), Inches(2.9))
footer(s)

# ==================================================================== 5: dextran screen design
s = prs.slides.add_slide(BLANK)
title_bar(s, "Experiment \u2014 biodegradable cationic dextran screen", "Dow collaboration: 3 surfactant chassis \u00d7 8 polymers")
add_text(s, Inches(0.55), Inches(1.35), Inches(6.4), Inches(5.4), [
    ("Chassis (surfactant environment):", {"size": 14, "bold": True, "color": NAVY}),
    ("GH150 EED0 \u2014 base sulfate chassis", {"size": 13, "bullet": True}),
    ("GH150 DDu0 + 3.6% LAPB \u2014 amphoteric co-surfactant", {"size": 13, "bullet": True}),
    ("GH150 DDu0 + 3.6% APG \u2014 nonionic co-surfactant", {"size": 13, "bullet": True}),
    ("Polymers:", {"size": 14, "bold": True, "color": NAVY}),
    ("3196 = guar benchmark;  CD2 = cationic-dextran benchmark", {"size": 13, "bullet": True}),
    ("Dex A / B / B* / J / J* / K = developmental biodegradable dextrans", {"size": 13, "bullet": True}),
    ("Run at 0.4% and 1% polymer; %T kinetics 0\u201315 min.", {"size": 13, "bullet": True, "color": BLUE}),
])
card(s, Inches(7.25), Inches(1.5), Inches(5.6), Inches(5.0), "The question",
     [("Can a readily-biodegradable dextran match guar / synthetic cationic benchmarks for coacervation \u2014 and does it depend on the surfactant chassis?",
       {"size": 14, "bullet": True}),
      ("If yes, we get a sustainable conditioning polymer without sacrificing deposition.",
       {"size": 14, "bullet": True, "color": GREEN}),
      ("Readout is an optical proxy \u2014 confirm hits with microscopy + deposition before mechanistic claims.",
       {"size": 12.5, "bullet": True, "italic": True, "color": GREY})], accent=BLUE)
footer(s)

# ==================================================================== 6: 1% overlay figure
s = prs.slides.add_slide(BLANK)
title_bar(s, "Observation \u2014 %T dilution curves (1% polymer, APG chassis)",
          "Each polymer's coacervation window, most \u2192 least concentrated")
add_image(s, f"{R}/dextran_1pct_pct.png", Inches(0.5), Inches(1.2), Inches(8.6), Inches(5.6))
card(s, Inches(9.25), Inches(1.3), Inches(3.6), Inches(5.3), "Read-out",
     [("CD2 (benchmark) coacervates strongest & broadest.", {"size": 12.5, "bullet": True}),
      ("Dex-K is the clear lead developmental dextran.", {"size": 12.5, "bullet": True, "color": GREEN}),
      ("Dex-A/B/J are weak \u2014 architecture matters, not just 'dextran'.", {"size": 12.5, "bullet": True}),
      ("APG shows a distinctive bimodal shape (two troughs) \u2014 see later slide.",
       {"size": 12.5, "bullet": True, "color": AMBER})], accent=GREEN)
footer(s)

# ==================================================================== 7: chassis flips ranking
s = prs.slides.add_slide(BLANK)
title_bar(s, "Key finding \u2014 the surfactant chassis flips the ranking",
          "Total coacervation response (summed absorbance AUC, 0\u201315 min)")
# mini table
rows = [
    ("Polymer", "EED0", "LAPB", "APG", True),
    ("CD2 (dextran benchmark)", "0.60", "0.50", "0.18", False),
    ("3196 (guar benchmark)", "0.30", "0.50", "0.10", False),
    ("Dex-K (lead developmental)", "0.27", "0.27", "0.12", False),
    ("Dex-A (weak developmental)", "0.00", "0.02", "0.01", False),
]
top = Inches(1.5)
for ri, (a, b, c, d, hdr) in enumerate(rows):
    y = top + Inches(0.55) * ri
    fill = NAVY if hdr else (LIGHT if ri % 2 else WHITE)
    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.55), y, Inches(6.5), Inches(0.52))
    box.fill.solid(); box.fill.fore_color.rgb = fill; box.line.color.rgb = RGBColor(0xD5, 0xDD, 0xE5)
    col = WHITE if hdr else DARK
    for cx, (txt, w) in enumerate([(a, 3.4), (b, 1.03), (c, 1.03), (d, 1.03)]):
        left = Inches(0.65 + (0 if cx == 0 else 3.4 + (cx - 1) * 1.03))
        add_text(s, left, y + Inches(0.06), Inches(w), Inches(0.42),
                 [(txt, {"size": 12.5, "bold": hdr, "color": col})],
                 anchor=MSO_ANCHOR.MIDDLE)
add_text(s, Inches(0.55), Inches(4.35), Inches(6.6), Inches(0.4),
         [("Higher = more total coacervate signal (optical proxy).", {"size": 11, "italic": True, "color": GREY})])
card(s, Inches(7.3), Inches(1.5), Inches(5.55), Inches(5.0), "What it means",
     [("CD2 is strongest in every chassis (best in the base sulfate EED0).", {"size": 13, "bullet": True}),
      ("Guar (3196) matches CD2 in LAPB but collapses in the nonionic APG chassis.",
       {"size": 13, "bullet": True, "color": RED}),
      ("APG suppresses total response \u2014 but lets CD2 and Dex-K out-perform guar.",
       {"size": 13, "bullet": True, "color": GREEN}),
      ("Chassis + polymer chemistry JOINTLY control coacervation \u2014 you cannot rank a polymer without naming the chassis.",
       {"size": 13, "bullet": True, "bold": True, "color": NAVY})], accent=BLUE)
footer(s)

# ==================================================================== 8: Dex-K chassis figure
s = prs.slides.add_slide(BLANK)
title_bar(s, "Observation \u2014 Dex-K is chassis-sensitive (APG vs LAPB)",
          "Same lead dextran, two co-surfactants: LAPB ~2.4\u00d7 the windowed AUC of APG")
add_image(s, f"{R}/dextran_dexk_chassis.png", Inches(0.5), Inches(1.25), Inches(12.3), Inches(5.4))
footer(s)

# ==================================================================== 9: bimodal second trough
s = prs.slides.add_slide(BLANK)
title_bar(s, "Observation \u2014 the APG 'second trough' is real (bimodal)",
          "Not an artifact: re-entrant associative phase separation on dilution")
add_image(s, f"{R}/dextran_1pct_timecourse.png", Inches(0.5), Inches(1.2), Inches(8.5), Inches(5.6))
card(s, Inches(9.15), Inches(1.3), Inches(3.7), Inches(5.4), "Why it's real",
     [("The dip spans 5+ neighbouring dilution wells \u2014 a bubble is a single isolated well.",
       {"size": 12, "bullet": True}),
      ("A rock-stable CLEAR plateau sits between the two troughs (can't happen by noise).",
       {"size": 12, "bullet": True}),
      ("Mechanism: the dilution line crosses the coacervate region twice; nonionic APG opens a 2nd precipitation window at high dilution.",
       {"size": 12, "bullet": True, "color": AMBER}),
      ("Fit is bimodal so both troughs resolve.", {"size": 12, "bullet": True, "color": GREEN})], accent=AMBER)
footer(s)

# ==================================================================== 10: 1% vs 0.4%
s = prs.slides.add_slide(BLANK)
title_bar(s, "Observation \u2014 concentration effect (1% vs 0.4% polymer)",
          "More polymer deepens the trough, but turbidity scales sub-linearly")
add_image(s, f"{R}/dextran_1pct_vs_04pct.png", Inches(0.5), Inches(1.2), Inches(8.6), Inches(5.6))
card(s, Inches(9.25), Inches(1.3), Inches(3.6), Inches(5.3), "Read-out",
     [("Solid = 1%, dashed = 0.4% (same APG chassis).", {"size": 12.5, "bullet": True}),
      ("CD2 & Dex-K: ~1.3\u00d7 higher AUC at 1% \u2014 real dose response.", {"size": 12.5, "bullet": True, "color": GREEN}),
      ("Weak dextrans: ~1.0\u00d7 \u2014 still near baseline even at 1%.", {"size": 12.5, "bullet": True}),
      ("Sub-linear scaling hints the coacervate coarsens \u2014 %T under-reports true load (next slide).",
       {"size": 12.5, "bullet": True, "color": AMBER})], accent=BLUE)
footer(s)

# ==================================================================== 11: kinetics mechanism
s = prs.slides.add_slide(BLANK)
title_bar(s, "Observation \u2014 why the signal changes over 0\u201315 min",
          "It is NOT settling (plate is shaken every read) \u2014 the coacervate is maturing")
add_text(s, Inches(0.55), Inches(1.35), Inches(7.4), Inches(5.4), [
    ("%T is a scattering proxy: signal = droplet number \u00d7 size \u00d7 contrast \u2014 NOT coacervate mass.",
     {"size": 14, "bullet": True, "color": NAVY}),
    ("Fresh mix (t=0) = many tiny droplets near the 600 nm scattering optimum \u2192 deepest trough.",
     {"size": 14, "bullet": True}),
    ("Over time they coalesce / Ostwald-ripen into fewer, larger, denser droplets that scatter LESS per gram \u2192 %T recovers.",
     {"size": 14, "bullet": True, "color": BLUE}),
    ("Shaking ACCELERATES this (collisions drive coalescence) \u2014 so mixing works against turbidity, not for it.",
     {"size": 14, "bullet": True}),
    ("Dextran coacervates are fluid \u2192 coarsen fast (signal fades); guar forms a networked gel \u2192 persists.",
     {"size": 14, "bullet": True, "color": GREEN}),
    ("Implication: rank at a fixed early timepoint (t=0 or 3 min); treat the decay slope as its own 'kinetic stability' signal.",
     {"size": 13.5, "bullet": True, "bold": True, "color": NAVY}),
])
card(s, Inches(8.2), Inches(1.5), Inches(4.65), Inches(4.9), "The mechanisms",
     [("Coalescence \u2014 droplets merge on contact.", {"size": 13, "bullet": True}),
      ("Ostwald ripening \u2014 large droplets grow at the expense of small.", {"size": 13, "bullet": True}),
      ("Densification / syneresis \u2014 complex expels water, compacts.", {"size": 13, "bullet": True}),
      ("Confirm with microscopy / droplet sizing + PTL deposition before claiming coacervate mass.",
       {"size": 12.5, "bullet": True, "italic": True, "color": GREY})], accent=GREEN)
footer(s)

# ==================================================================== 12: in-market benchmarking
s = prs.slides.add_slide(BLANK)
title_bar(s, "Benchmarking \u2014 in-market & competitor shampoos on one scale",
          "Same %T method places our formulas against products consumers actually buy")
add_image(s, f"{R}/inmarket_auc.png", Inches(0.5), Inches(1.25), Inches(8.4), Inches(5.5))
card(s, Inches(9.05), Inches(1.3), Inches(3.8), Inches(5.4), "Why it matters",
     [("Turns an abstract %T number into a competitive position.", {"size": 12.5, "bullet": True}),
      ("Each plate + product is registered \u2192 searchable, comparable over time.", {"size": 12.5, "bullet": True}),
      ("Competitor spread is wide (e.g. strong clarifying vs light volumizing products).",
       {"size": 12.5, "bullet": True}),
      ("Feeds a correlation of coacervation strength vs claimed consumer feel.",
       {"size": 12.5, "bullet": True, "color": BLUE})], accent=BLUE)
footer(s)

# ============================================ 12b: phase-diagram method
s = prs.slides.add_slide(BLANK)
title_bar(s, "Related work \u2014 phase-diagram mapping (2D coacervation windows)",
          "Instead of one dilution line, map %T across a full surfactant \u00d7 polymer grid")
add_image(s, f"{R}/rhamnolipid_hardness_report/figures/contours_AMT.png",
          Inches(0.5), Inches(1.2), Inches(8.7), Inches(5.6))
card(s, Inches(9.35), Inches(1.3), Inches(3.5), Inches(5.4), "How to read it",
     [("Axes = rhamnolipid (biosurfactant) \u00d7 cationic polymer concentration.",
       {"size": 12, "bullet": True}),
      ("Color = %T; orange = cloudy (coacervate/precipitate), green = clear.",
       {"size": 12, "bullet": True}),
      ("Black contour = coacervation threshold \u2014 the boundary of the 2-phase region.",
       {"size": 12, "bullet": True, "color": AMBER}),
      ("Left = soft (0 gpg), right = hard (7 gpg) water \u2014 same polymer, the region moves.",
       {"size": 12, "bullet": True, "color": BLUE})], accent=AMBER)
footer(s)

# ============================================ 12c: hardness summary
s = prs.slides.add_slide(BLANK)
title_bar(s, "Observation \u2014 water hardness reshapes the coacervation region",
          "Rhamnolipid + cationic polymers: precipitation load & well-fraction, soft vs hard")
add_image(s, f"{R}/rhamnolipid_hardness_report/figures/hardness_summary.png",
          Inches(0.5), Inches(1.25), Inches(8.5), Inches(5.4))
card(s, Inches(9.15), Inches(1.3), Inches(3.7), Inches(5.4), "What it shows",
     [("Hardness effect is polymer-specific, not universal.", {"size": 12.5, "bullet": True, "bold": True, "color": NAVY}),
      ("AMT (PQ-76): strong in soft water, drops sharply in hard.", {"size": 12.5, "bullet": True, "color": RED}),
      ("DADMAC (PQ-6): essentially hardness-insensitive.", {"size": 12.5, "bullet": True}),
      ("KG-30M: precipitates MORE in hard water.", {"size": 12.5, "bullet": True, "color": GREEN}),
      ("No-polymer control precipitates in hard water (rhamnolipid + Ca\u00b2\u207a) \u2014 a baseline to subtract.",
       {"size": 12, "bullet": True, "italic": True, "color": GREY})], accent=BLUE)
footer(s)

# ============================================ 12d: 1% dextran across 3 chassis
s = prs.slides.add_slide(BLANK)
title_bar(s, "Result \u2014 1% dextran across all three chassis",
          "The surfactant chassis controls whether (and where) a dextran coacervates")
add_image(s, f"{R}/dextran_1pct_chassis_grid_fit.png", Inches(0.45), Inches(1.2), Inches(8.9), Inches(5.6))
card(s, Inches(9.45), Inches(1.3), Inches(3.4), Inches(5.4), "Findings (1% AUC)",
     [("LAPB (amphoteric) is a coacervation ACTIVATOR \u2014 strongest for CD2 (0.19) & Dex-K (0.15).",
       {"size": 12, "bullet": True, "color": GREEN}),
      ("APG (nonionic) DELAYS coacervation to rinse-relevant dilutions (~1:5).",
       {"size": 12, "bullet": True, "color": AMBER}),
      ("Dex-J* is chassis-gated: ~baseline in EED0/APG, but 0.15 in LAPB \u2014 nearly CD2-level.",
       {"size": 12, "bullet": True, "bold": True, "color": NAVY}),
      ("Dex-B/B* stay inert in every chassis \u2014 architecture, again.", {"size": 12, "bullet": True})],
     accent=GREEN)
footer(s)

# ============================================ 12e: competitors + T/Sal caveat
s = prs.slides.add_slide(BLANK)
title_bar(s, "Competitor benchmarking \u2014 and a measurement caveat",
          "Same %T method; but not all turbidity is coacervation")
add_image(s, f"{R}/competitor_2026090_pct.png", Inches(0.5), Inches(1.25), Inches(8.2), Inches(5.4))
card(s, Inches(8.85), Inches(1.3), Inches(4.0), Inches(5.4), "Read carefully",
     [("Neutrogena T/Sal reads huge turbidity \u2014 but that's SALICYLIC ACID precipitating on dilution, NOT coacervation.",
       {"size": 12, "bullet": True, "color": RED}),
      ("Act+Acre: mostly in-bottle opacity (pearlized) clearing on dilution.", {"size": 12, "bullet": True}),
      ("NATIVE Scalp Detox & Crown Volumizing: genuinely weak \u2014 light-feel / volumizing positioning.",
       {"size": 12, "bullet": True}),
      ("Solu: a real mild coacervation trough.", {"size": 12, "bullet": True, "color": GREEN}),
      ("Lesson: always read the CURVE SHAPE, not just the AUC number.",
       {"size": 12, "bullet": True, "bold": True, "color": NAVY})], accent=RED)
footer(s)

# ==================================================================== 13: platform / tooling
s = prs.slides.add_slide(BLANK)
title_bar(s, "Tooling \u2014 a %T analysis platform behind the science",
          "Consistent, reproducible, searchable \u2014 not scattered spreadsheets")
card(s, Inches(0.45), Inches(1.35), Inches(6.1), Inches(5.4), "What it does",
     [("Upload raw plate files \u2192 auto-parse dilution series & timepoints.", {"size": 13, "bullet": True}),
      ("One consistent fit + AUC so every sample is measured identically.", {"size": 13, "bullet": True}),
      ("Organize samples/products; look up ingredients & reviews; import product data.",
       {"size": 13, "bullet": True}),
      ("Trends view: correlate coacervation features with claimed consumer feel.",
       {"size": 13, "bullet": True, "color": BLUE}),
      ("Cloud + Nexus connectors staged for pushing results to shared storage.",
       {"size": 13, "bullet": True, "color": AMBER})], accent=BLUE)
card(s, Inches(6.75), Inches(1.35), Inches(6.1), Inches(5.4), "Why it helps the team",
     [("One digital source of truth \u2014 searchable and typo-proof.", {"size": 13, "bullet": True}),
      ("Apples-to-apples comparisons across polymers, chassis, and competitors.",
       {"size": 13, "bullet": True}),
      ("New data slots straight into the same figures & rankings.", {"size": 13, "bullet": True, "color": GREEN}),
      ("Scientific guardrails built in (artifact cleaning, fixed-timepoint ranking, optical-proxy caveats).",
       {"size": 13, "bullet": True})], accent=GREEN)
footer(s)

# ==================================================================== 14: learnings & next steps
s = prs.slides.add_slide(BLANK)
title_bar(s, "Summary \u2014 learnings & next steps")
card(s, Inches(0.45), Inches(1.35), Inches(6.3), Inches(5.4), "What I've learned",
     [("Chassis + polymer chemistry jointly control coacervation \u2014 rank polymers only within a chassis.",
       {"size": 13, "bullet": True}),
      ("Dex-K is the standout biodegradable dextran (beats guar in APG); most other dextrans are weak \u2014 architecture matters.",
       {"size": 13, "bullet": True, "color": GREEN}),
      ("The APG second trough is a real re-entrant phase-separation feature, not noise.",
       {"size": 13, "bullet": True}),
      ("%T is an optical proxy: it changes over time via coacervate coarsening, not settling.",
       {"size": 13, "bullet": True, "color": BLUE})], accent=GREEN)
card(s, Inches(6.95), Inches(1.35), Inches(5.9), Inches(5.4), "Next steps",
     [("Repeat top hits at active-equivalent dosing (dextrans are ~30% active).", {"size": 13, "bullet": True}),
      ("Confirm mechanism: microscopy / droplet sizing + PTL deposition on Dex-K & CD2.",
       {"size": 13, "bullet": True, "color": NAVY}),
      ("Add a kinetic-stability (decay-rate) metric alongside AUC.", {"size": 13, "bullet": True}),
      ("Grow the competitor library so the feel\u2013coacervation correlation strengthens.",
       {"size": 13, "bullet": True}),
      ("Push registered results to Nexus / cloud once connectors are credentialed.",
       {"size": 13, "bullet": True, "color": AMBER})], accent=BLUE)
footer(s)

out = os.path.join(R, "Coacervation_Science_Recap.pptx")
prs.save(out)
print("wrote", out, "slides:", len(prs.slides._sldIdLst))
