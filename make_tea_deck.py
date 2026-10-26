"""Build the Tea Saponin coacervation %T pilot slide deck (16:9, Abadi font)."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
import os
import csv

FONT = "Abadi"
NAVY = RGBColor(0x00, 0x26, 0x6A)     # P&G-ish deep blue
BLUE = RGBColor(0x2E, 0x75, 0xB6)
LIGHT = RGBColor(0xEE, 0xF3, 0xF9)
GREY = RGBColor(0x5A, 0x64, 0x70)
DARK = RGBColor(0x1E, 0x2A, 0x36)
GREEN = RGBColor(0x2E, 0x9E, 0x5B)
RED = RGBColor(0xC0, 0x39, 0x2B)
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
    # ensure east-asian/complex also use Abadi
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
        p.space_after = Pt(4)
        txt, opts = (ln, {}) if isinstance(ln, str) else ln
        if opts.get("bullet"):
            txt = "•  " + txt
        r = p.add_run(); r.text = txt
        _set_font(r, size=opts.get("size", 14), bold=opts.get("bold", False),
                  color=opts.get("color", DARK), italic=opts.get("italic", False))
    return tb


def title_bar(slide, title, sub=None):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(1.05))
    bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
    tf = bar.text_frame; tf.margin_left = Inches(0.45); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; r = p.add_run(); r.text = title
    _set_font(r, size=26, bold=True, color=WHITE)
    if sub:
        p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = sub
        _set_font(r2, size=13, color=RGBColor(0xCF, 0xDD, 0xF0))


def footer(slide):
    add_text(slide, Inches(0.45), Inches(7.02), Inches(12.4), Inches(0.4),
             [("Coacervation %T Platform Pilot  ·  Nexus WS-20251111-01082  ·  Contacts: Kyla Fung, Camille England",
               {"size": 9, "color": GREY})])


# ---------------------------------------------------------------- Slide 1: title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
add_text(s, Inches(0.9), Inches(2.1), Inches(11.5), Inches(2.2), [
    ("Digitizing Coacervation %T Data", {"size": 40, "bold": True, "color": WHITE}),
    ("A platform pilot — upload, organize, plot & push past %T data to Nexus", {"size": 18, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])
accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(3.05), Inches(3.2), Pt(3))
accent.fill.solid(); accent.fill.fore_color.rgb = BLUE; accent.line.fill.background()
add_text(s, Inches(0.9), Inches(4.2), Inches(11.5), Inches(2.2), [
    ("Case Study 1:  Tea Saponin Analysis — 5.8/5.8/2.4 GH150 (R2510, N22510S)", {"size": 20, "bold": True, "color": WHITE}),
    ("Nexus Worksheet ID:  WS-20251111-01082", {"size": 15, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
    ("Contacts:  Kyla Fung  ·  Camille England", {"size": 15, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])

# ---------------------------------------------------------------- Slide 2: problem/objective
s = prs.slides.add_slide(BLANK)
title_bar(s, "Problem & Objective")
# problem
box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.45), Inches(1.35), Inches(12.4), Inches(1.35))
box.fill.solid(); box.fill.fore_color.rgb = LIGHT; box.line.color.rgb = BLUE
add_text(s, Inches(0.7), Inches(1.5), Inches(12.0), Inches(1.1), [
    ("Problem", {"size": 16, "bold": True, "color": NAVY}),
    ("Past %T coacervation data lives in scattered per-plate spreadsheets and manual sample-info blocks — hard to search, compare, plot, or push to Nexus. No single, digital source of truth.", {"size": 14, "color": DARK}),
])
add_text(s, Inches(0.55), Inches(2.95), Inches(6.1), Inches(3.6), [
    ("Objective — Platform", {"size": 16, "bold": True, "color": BLUE}),
    ("Build a digital platform to upload → organize → plot %T data and push to Nexus.", {"size": 14, "bullet": True}),
    ("Use real past data to pressure-test and improve the interface (upload, organize, plot).", {"size": 14, "bullet": True}),
    ("Digitize the workflow: one source of truth, searchable, typo-proof.", {"size": 14, "bullet": True}),
])
add_text(s, Inches(6.9), Inches(2.95), Inches(6.0), Inches(3.6), [
    ("Objective — Science", {"size": 16, "bold": True, "color": GREEN}),
    ("Tea Saponin has shown increased silicone (Si) deposition in shampoo.", {"size": 14, "bullet": True}),
    ("Use %Transmittance to investigate the mechanism of action (coacervate change).", {"size": 14, "bullet": True}),
    ("MoA understanding → intellectual property, deeper botanical insight, and finding other botanicals with similar performance.", {"size": 14, "bullet": True}),
])
footer(s)

# ---------------------------------------------------------------- Slide 3: background
s = prs.slides.add_slide(BLANK)
title_bar(s, "Background — Tea Saponin", "A natural co-surfactant that also boosts conditioning & silicone deposition")
add_text(s, Inches(0.55), Inches(1.35), Inches(7.6), Inches(5.3), [
    ("Natural surfactant (saponins) from de-oiled camellia seed — a repurposed waste stream; low GHG (0.04 kg CO₂e / kg).", {"size": 14, "bullet": True}),
    ("Mild co-surfactant: cleaning & lather on par with conventional co-surfactants (1:1 replacement).", {"size": 14, "bullet": True}),
    ("NEW finding: also enhances conditioning and small-particle silicone (DM5500) deposition — even at 0.25–1.0%.", {"size": 14, "bullet": True, "color": GREEN}),
    ("Mechanism appears to alter the coacervate: a shift in the %T 2-phase region; SEM shows a film on the cuticle with small-particle silicone (not with large-particle).", {"size": 14, "bullet": True}),
    ("% Tea Saponin added does not change the shift significantly.", {"size": 14, "bullet": True, "italic": True}),
])
card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.4), Inches(1.5), Inches(4.5), Inches(4.9))
card.fill.solid(); card.fill.fore_color.rgb = LIGHT; card.line.color.rgb = BLUE
add_text(s, Inches(8.7), Inches(1.7), Inches(3.9), Inches(4.6), [
    ("Why %T?", {"size": 16, "bold": True, "color": NAVY}),
    ("Coacervation forms as shampoo is diluted in rinsing.", {"size": 13, "bullet": True}),
    ("It drives deposition of conditioning agents and actives (silicone, ZPT, PO).", {"size": 13, "bullet": True}),
    ("%T vs. dilution reveals the coacervate 2-phase region — and how Tea Saponin shifts it.", {"size": 13, "bullet": True}),
    ("DM5500 (small particle) deposits via coacervation; LP base via filtration → Tea Saponin acts on the coacervation route.", {"size": 13, "bullet": True}),
])
footer(s)

# ---------------------------------------------------------------- Slide 4: sample set
s = prs.slides.add_slide(BLANK)
title_bar(s, "Sample Set & What We Compare", "11 formulas run by %T on the Hamilton — from Camille England")
rows_data = [
    ("#", "Batch ID", "Chassis", "Tea Sap %", "Silicone", "Group"),
    ("1", "B-20251020-01013", "5.8/5.8/2.4 (2% CAPB)", "0%", "—", "Control"),
    ("2", "B-20251020-01014", "5.8/5.8/2.4 (2.4% CAPB)", "0%", "0.5% DM5500", "Silicone control"),
    ("3", "B-20251020-01015", "5.8/5.8/1.4 (1.4% CAPB)", "1.0%", "0.5% DM5500", "Tea replaces CAPB"),
    ("4", "B-20251023-00844", "GH150 16% R2510", "0%", "—", "R2510 dose"),
    ("5", "B-20251023-00845", "GH150 16% R2510", "0.25%", "—", "R2510 dose"),
    ("6", "B-20251023-00846", "GH150 16% R2510", "0.5%", "—", "R2510 dose"),
    ("7", "B-20251023-00847", "GH150 16% R2510", "1.0%", "—", "R2510 dose"),
    ("8", "B-20251023-00849", "GH150 16% N22510S", "0%", "—", "N22510S dose"),
    ("9", "B-20251023-00850", "GH150 16% N22510S", "0.25%", "—", "N22510S dose"),
    ("10", "B-20251023-00851", "GH150 16% N22510S", "0.5%", "—", "N22510S dose"),
    ("11", "B-20251023-00852", "GH150 16% N22510S", "1.0%", "—", "N22510S dose"),
]
tbl_w = Inches(8.5)
tbl = s.shapes.add_table(len(rows_data), 6, Inches(0.45), Inches(1.35), tbl_w, Inches(5.2)).table
widths = [0.5, 2.1, 2.3, 1.0, 1.3, 1.3]
for i, w in enumerate(widths):
    tbl.columns[i].width = Inches(w)
for ri, row in enumerate(rows_data):
    for ci, val in enumerate(row):
        cell = tbl.cell(ri, ci)
        cell.margin_left = Inches(0.05); cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]; run = p.add_run(); run.text = val
        if ri == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
            _set_font(run, size=10.5, bold=True, color=WHITE)
        else:
            cell.fill.solid(); cell.fill.fore_color.rgb = WHITE if ri % 2 else LIGHT
            _set_font(run, size=10, color=DARK)
add_text(s, Inches(9.15), Inches(1.35), Inches(3.9), Inches(5.2), [
    ("Being observed", {"size": 15, "bold": True, "color": NAVY}),
    ("%T vs. dilution profile — the coacervate 2-phase region.", {"size": 12.5, "bullet": True}),
    ("", {"size": 4}),
    ("Being compared", {"size": 15, "bold": True, "color": BLUE}),
    ("Chassis: R2510 vs N22510S", {"size": 12.5, "bullet": True}),
    ("Tea Saponin dose: 0 → 0.25 → 0.5 → 1.0%", {"size": 12.5, "bullet": True}),
    ("Coacervate shift: control vs +silicone vs +silicone+Tea Saponin (samples 1–3)", {"size": 12.5, "bullet": True}),
])
footer(s)

# ---------------------------------------------------------------- Slide 4b: experimental design
s = prs.slides.add_slide(BLANK)
title_bar(s, "Experimental Design", "How the %T coacervation assay is run on the Hamilton")
# three method cards
cards = [
    ("Plate & dilution", NAVY, [
        "96-well plate; 2 samples/plate (trough 1 = rows A-D, trough 2 = E-H).",
        "Each sample = 48-point serial dilution series (formula fraction 0.5 -> 0.0019).",
        "X-axis = dilution 1:X, plotted most -> least concentrated.",
    ]),
    ("Read & kinetics", BLUE, [
        "% Transmittance read at 37 degC every 1 min, 0 -> 15 min (16 timepoints).",
        "Turbidity from coacervate droplets lowers %T in the 2-phase region.",
        "Absorbance A = 2 - log10(%T); AUC over the 1:2 - 1:20 window = coacervation strength.",
    ]),
    ("Comparisons", GREEN, [
        "Silicone shift: control vs +DM5500 vs +DM5500 +1.0% Tea Saponin.",
        "Dose response: 0 / 0.25 / 0.5 / 1.0% Tea Saponin in R2510 and N22510S.",
        "Chassis: R2510 vs N22510S at matched Tea Saponin dose.",
    ]),
]
cw = Inches(4.06); ch = Inches(3.7); x0 = Inches(0.45); gap = Inches(0.2); y0 = Inches(1.4)
for i, (h, col, bullets) in enumerate(cards):
    bx = Emu(int(x0) + i * (int(cw) + int(gap)))
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, y0, cw, ch)
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT; box.line.color.rgb = col
    hdr = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, y0, cw, Inches(0.55))
    hdr.fill.solid(); hdr.fill.fore_color.rgb = col; hdr.line.fill.background()
    tf = hdr.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE; tf.margin_left = Inches(0.15)
    p = tf.paragraphs[0]; r = p.add_run(); r.text = h; _set_font(r, size=14, bold=True, color=WHITE)
    add_text(s, Emu(int(bx) + int(Inches(0.18))), Emu(int(y0) + int(Inches(0.7))),
             Emu(int(cw) - int(Inches(0.36))), Emu(int(ch) - int(Inches(0.85))),
             [(b, {"size": 11.5, "bullet": True}) for b in bullets])
# controls / variables strip
strip = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.45), Inches(5.35), Inches(12.45), Inches(1.35))
strip.fill.solid(); strip.fill.fore_color.rgb = RGBColor(0xF3, 0xF7, 0xFB); strip.line.color.rgb = GREY
add_text(s, Inches(0.7), Inches(5.5), Inches(12.0), Inches(1.1), [
    ("Design controls", {"size": 13.5, "bold": True, "color": NAVY}),
    ("Held constant: chassis backbone (GH150 16%), water hardness (7 gpg), read temperature (37 degC), "
     "dilution grid, HHS shake protocol.   Varied: silicone (DM5500), Tea Saponin dose, polymer (R2510 vs N22510S).   "
     "Replication: full 0-15 min kinetic curve per sample (16 reads) + 48-point dilution series.",
     {"size": 12, "color": DARK}),
])
footer(s)

# ---------------------------------------------------------------- Slide 5: workflow
s = prs.slides.add_slide(BLANK)
title_bar(s, "Digital Workflow — the Platform Pilot")
steps = [
    ("1  Upload", "Raw .txt plate files\n(2 samples / plate)", BLUE),
    ("2  Organize", "Confirm Batch ID + Description\n→ auto-split chassis / component / %", NAVY),
    ("3  Plot", "%T vs. dilution (1:X)\nbimodal-accurate fit", GREEN),
    ("4  Nexus", "Push curated results\n(WS-20251111-01082)", RED),
]
x = Inches(0.6); y = Inches(2.4); bw = Inches(2.75); bh = Inches(1.9); gap = Inches(0.35)
for i, (h, body, col) in enumerate(steps):
    bx = Emu(int(x) + i * (int(bw) + int(gap)))
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, y, bw, bh)
    box.fill.solid(); box.fill.fore_color.rgb = col; box.line.fill.background()
    tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = h
    _set_font(r, size=17, bold=True, color=WHITE)
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER; r2 = p2.add_run(); r2.text = body
    _set_font(r2, size=11.5, color=WHITE)
    if i < 3:
        ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Emu(int(bx) + int(bw) + Emu(int(Inches(0.02)))), Inches(3.05), Inches(0.32), Inches(0.5))
        ar.fill.solid(); ar.fill.fore_color.rgb = GREY; ar.line.fill.background()
add_text(s, Inches(0.6), Inches(4.7), Inches(12.2), Inches(2.0), [
    ("What the platform improves", {"size": 16, "bold": True, "color": NAVY}),
    ("Search by experiment name (rename raw files); one source of truth.", {"size": 13.5, "bullet": True}),
    ("Auto-parses Batch ID + Description → chassis / component / % and catches typos on review (e.g. 10% → 1.0%).", {"size": 13.5, "bullet": True}),
    ("Consistent coacervation fingerprint (onset / peak / recovery / width) + bimodal-accurate curve fit.", {"size": 13.5, "bullet": True}),
])
footer(s)

# ---------------------------------------------------------------- Slide 6: result
s = prs.slides.add_slide(BLANK)
title_bar(s, "Result — Tea Saponin Shifts the Coacervate", "%T vs. dilution, 5.8/5.8/2.4 GH150 (5 min)")
if os.path.exists(f"{R}/tea_shift.png"):
    s.shapes.add_picture(f"{R}/tea_shift.png", Inches(0.4), Inches(1.35), height=Inches(5.2))
add_text(s, Inches(8.4), Inches(1.5), Inches(4.6), Inches(5.1), [
    ("What we see", {"size": 16, "bold": True, "color": NAVY}),
    ("Adding small-particle silicone (DM5500) deepens coacervation.", {"size": 13, "bullet": True, "color": RED}),
    ("Adding Tea Saponin shifts the 2-phase region — a distinct second dip (~1:5).", {"size": 13, "bullet": True, "color": GREEN}),
    ("The bimodal (two-trough) shape is now captured by the improved curve fit.", {"size": 13, "bullet": True}),
    ("Dose (0.25–1.0%) does not change the shift much — consistent with the SLR.", {"size": 13, "bullet": True, "italic": True}),
    ("", {"size": 6}),
    ("Interpretation: Tea Saponin acts on the coacervation route (small-particle silicone), consistent with the observed deposition/conditioning boost.", {"size": 12.5, "color": DARK}),
])
footer(s)

# ---------------------------------------------------------------- Slide: dose series (%T)
s = prs.slides.add_slide(BLANK)
title_bar(s, "Tea Saponin Dose Series — %Transmittance", "R2510 vs N22510S, %T vs dilution (5 min)")
if os.path.exists(f"{R}/tea_R2510.png"):
    s.shapes.add_picture(f"{R}/tea_R2510.png", Inches(0.35), Inches(1.5), width=Inches(6.35))
if os.path.exists(f"{R}/tea_N22510S.png"):
    s.shapes.add_picture(f"{R}/tea_N22510S.png", Inches(6.75), Inches(1.5), width=Inches(6.35))
add_text(s, Inches(0.45), Inches(6.35), Inches(12.4), Inches(0.6), [
    ("Both chassis show the coacervate 2-phase dip; Tea Saponin dose (0.25–1.0%) shifts/steepens the region but dose has a modest effect — consistent with the SLR.",
     {"size": 12, "color": DARK}),
])
footer(s)

# ---------------------------------------------------------------- Slide: absorbance
s = prs.slides.add_slide(BLANK)
title_bar(s, "Absorbance View — A = 2 − log₁₀ %T", "Turbidity (absorbance) vs dilution highlights the coacervate peak")
if os.path.exists(f"{R}/tea_shift_abs.png"):
    s.shapes.add_picture(f"{R}/tea_shift_abs.png", Inches(0.3), Inches(1.5), width=Inches(4.25))
if os.path.exists(f"{R}/tea_R2510_abs.png"):
    s.shapes.add_picture(f"{R}/tea_R2510_abs.png", Inches(4.55), Inches(1.5), width=Inches(4.25))
if os.path.exists(f"{R}/tea_N22510S_abs.png"):
    s.shapes.add_picture(f"{R}/tea_N22510S_abs.png", Inches(8.8), Inches(1.5), width=Inches(4.25))
add_text(s, Inches(0.45), Inches(6.15), Inches(12.4), Inches(0.8), [
    ("Absorbance flips the curve so the coacervate 2-phase region reads as a peak; higher/broader peak = stronger coacervation.", {"size": 12.5, "bullet": True}),
    ("+Silicone +Tea Saponin (green, left) shows the tallest, shifted peak — the clearest coacervate change.", {"size": 12.5, "bullet": True, "color": GREEN}),
])
footer(s)

# ---------------------------------------------------------------- Slide: AUC
s = prs.slides.add_slide(BLANK)
title_bar(s, "Coacervation Strength — AUC Ranking", "Area under the absorbance curve (window 1:2 – 1:20)")
if os.path.exists(f"{R}/tea_auc.png"):
    s.shapes.add_picture(f"{R}/tea_auc.png", Inches(0.35), Inches(1.4), height=Inches(5.1))
add_text(s, Inches(8.7), Inches(1.5), Inches(4.3), Inches(5.1), [
    ("Why AUC?", {"size": 16, "bold": True, "color": NAVY}),
    ("Single number for coacervation strength — integrates absorbance across the 2-phase region.", {"size": 12.5, "bullet": True}),
    ("+DM5500 +1.0% Tea Saponin ranks highest → strongest coacervation.", {"size": 12.5, "bullet": True, "color": GREEN}),
    ("Adding silicone raises AUC vs the CAPB control; Tea Saponin raises it further.", {"size": 12.5, "bullet": True, "color": RED}),
    ("Within a chassis, dose (0.25→1.0%) barely changes AUC — the shift, not the amount, matters.", {"size": 12.5, "bullet": True, "italic": True}),
])
footer(s)

# ---------------------------------------------------------------- Slide: AUC numeric table + conclusions
def _read_auc_rows():
    path = f"{R}/tea_auc_values.csv"
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

auc_rows = _read_auc_rows()
s = prs.slides.add_slide(BLANK)
title_bar(s, "AUC — Numeric Values & Insights", "Coacervation AUC (absorbance × decade, window 1:2–1:20)")
if auc_rows:
    hdr = ["Group", "Sample", "t=1", "t=5", "t=15", "Peak", "Kinetics"]
    keys = ["group", "sample", "AUC_t1", "AUC_t5", "AUC_t15", "AUC_peak", "kinetics"]
    tbl = s.shapes.add_table(len(auc_rows) + 1, len(hdr), Inches(0.4), Inches(1.3),
                             Inches(8.6), Inches(0.3 + 0.34 * len(auc_rows))).table
    for i, w in enumerate([2.0, 2.7, 0.75, 0.75, 0.75, 0.8, 0.95]):
        tbl.columns[i].width = Inches(w)
    for ci, h in enumerate(hdr):
        c = tbl.cell(0, ci); c.fill.solid(); c.fill.fore_color.rgb = NAVY
        c.margin_left = Inches(0.04); c.margin_top = Inches(0.01); c.margin_bottom = Inches(0.01)
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        rr = c.text_frame.paragraphs[0].add_run(); rr.text = h; _set_font(rr, size=9.5, bold=True, color=WHITE)
    kin_col = {"builds": GREEN, "decays": RED, "stable": BLUE}
    for ri, row in enumerate(auc_rows, start=1):
        for ci, k in enumerate(keys):
            c = tbl.cell(ri, ci)
            c.margin_left = Inches(0.04); c.margin_top = Inches(0.01); c.margin_bottom = Inches(0.01)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid(); c.fill.fore_color.rgb = WHITE if ri % 2 else LIGHT
            val = row[k]
            col = DARK
            if k == "kinetics":
                col = kin_col.get(val, DARK)
            rr = c.text_frame.paragraphs[0].add_run(); rr.text = val
            _set_font(rr, size=8.8, bold=(k == "kinetics"), color=col)
add_text(s, Inches(9.15), Inches(1.35), Inches(3.9), Inches(5.4), [
    ("What the numbers say", {"size": 15, "bold": True, "color": NAVY}),
    ("Silicone raises AUC vs the CAPB control (0.055 → 0.064); +Tea Saponin raises it further to 0.077 — the strongest coacervation in the set.", {"size": 11.5, "bullet": True, "color": GREEN}),
    ("R2510 doses are statistically flat (~0.054) — dose does not change strength.", {"size": 11.5, "bullet": True}),
    ("N22510S is the only chassis where AUC BUILDS over 0–15 min (0.061 → 0.087).", {"size": 11.5, "bullet": True, "color": BLUE}),
    ("Full per-timepoint table exported to Reports/tea_auc_values.csv.", {"size": 10.5, "italic": True, "color": GREY}),
])
footer(s)

# ---------------------------------------------------------------- Slide: AUC kinetics (over time)
s = prs.slides.add_slide(BLANK)
title_bar(s, "New Insight — Coacervation Kinetics (AUC vs Time)", "A single timepoint hides this; the AUC-over-time view reveals it")
if os.path.exists(f"{R}/tea_auc_time.png"):
    s.shapes.add_picture(f"{R}/tea_auc_time.png", Inches(0.35), Inches(1.45), width=Inches(9.1))
add_text(s, Inches(9.6), Inches(1.4), Inches(3.5), Inches(5.4), [
    ("Three distinct signatures", {"size": 14, "bold": True, "color": NAVY}),
    ("Shift set: clear, stable separation — Tea Saponin sits highest and barely decays (most robust coacervate).", {"size": 11.5, "bullet": True, "color": GREEN}),
    ("R2510: all doses overlap and slowly decay → coacervate forms fast, then relaxes; dose-independent.", {"size": 11.5, "bullet": True}),
    ("N22510S: AUC climbs the whole 15 min → a slow-building coacervate, distinct kinetic class.", {"size": 11.5, "bullet": True, "color": BLUE}),
    ("Takeaway: the method separates formulas by HOW coacervation evolves, not just its 5-min value — a new screening axis.", {"size": 11.5, "color": DARK}),
])
footer(s)

# ---------------------------------------------------------------- Slide: correlate AUC to conditioning (SLR Table 1)
s = prs.slides.add_slide(BLANK)
title_bar(s, "Correlating AUC to Conditioning Data (SLR Table 1)",
          "Measured friction/IFM vs Tea Saponin dose, alongside coacervation AUC")
if os.path.exists(f"{R}/tea_friction_auc.png"):
    s.shapes.add_picture(f"{R}/tea_friction_auc.png", Inches(0.35), Inches(1.45), width=Inches(8.7))
add_text(s, Inches(9.25), Inches(1.4), Inches(3.8), Inches(5.5), [
    ("What correlates", {"size": 15, "bold": True, "color": NAVY}),
    ("Measured conditioning improves strongly with Tea Saponin dose: dry total friction r = −0.97, dry detangling r = −0.93 (lower = better).", {"size": 11.5, "bullet": True, "color": GREEN}),
    ("Across TREATMENTS, coacervation AUC tracks deposition: Control 0.055 < +DM5500 0.064 < +DM5500 +Tea Saponin 0.077 — same direction as the SEM film / deposition boost.", {"size": 11.5, "bullet": True}),
    ("But across DOSE, AUC is flat while friction keeps dropping — the SLR itself notes %T shift is dose-insensitive.", {"size": 11.5, "bullet": True, "color": RED}),
    ("So AUC marks that the coacervate shifted (on/off); the dose-graded deposition amount rides on top of it.", {"size": 11.5, "italic": True}),
])
footer(s)

# ---------------------------------------------------------------- Slide: the answer + data to request
s = prs.slides.add_slide(BLANK)
title_bar(s, "Answering: Can AUC Predict Deposition — and What to Request Next",
          "A sample-matched correlation needs the measured silicone-deposition numbers")
# left: what we can say now
box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.45), Inches(1.35), Inches(6.1), Inches(2.7))
box.fill.solid(); box.fill.fore_color.rgb = LIGHT; box.line.color.rgb = GREEN
add_text(s, Inches(0.7), Inches(1.5), Inches(5.65), Inches(2.45), [
    ("What we can say now", {"size": 15, "bold": True, "color": GREEN}),
    ("AUC correlates with conditioning DIRECTION (higher AUC → more deposition / lower friction) across treatments.", {"size": 11.5, "bullet": True}),
    ("AUC is a coacervate-shift ON/OFF marker — great for triage/screening.", {"size": 11.5, "bullet": True}),
    ("It is NOT (yet) a dose-quantitative deposition predictor — AUC is flat across 0.25–1.0% while friction improves.", {"size": 11.5, "bullet": True}),
])
# right: the gap that blocks a hard number
box2 = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.75), Inches(1.35), Inches(6.15), Inches(2.7))
box2.fill.solid(); box2.fill.fore_color.rgb = RGBColor(0xFB, 0xF0, 0xEE); box2.line.color.rgb = RED
add_text(s, Inches(7.0), Inches(1.5), Inches(5.7), Inches(2.45), [
    ("The gap (why r isn’t final yet)", {"size": 15, "bold": True, "color": RED}),
    ("Friction Table 1 is the GH150 16% full-formula DM5500 ADDITIVE series; my %T plates are the CAPB-replacement shift set + R2510 / N22510S silicones — different formulas.", {"size": 11, "bullet": True}),
    ("The report says silicone DEPOSITION was measured, but those numeric values (µg/cm²) aren’t in the dataset.", {"size": 11, "bullet": True}),
    ("Without sample-matched deposition + %T, a hard Pearson r can’t be locked.", {"size": 11, "bullet": True}),
])
# bottom: the ask
strip = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.45), Inches(4.3), Inches(12.45), Inches(2.25))
strip.fill.solid(); strip.fill.fore_color.rgb = NAVY; strip.line.fill.background()
add_text(s, Inches(0.75), Inches(4.45), Inches(11.9), Inches(2.0), [
    ("Yes — request the deposition data (the report confirms it was measured).  Ask Camille England for:", {"size": 14, "bold": True, "color": WHITE}),
    ("1.  Measured small-particle-silicone (DM5500) deposition per Batch ID — µg Si/cm² (XRF/EDX/ICP) — for samples 5–8 and the shift set.", {"size": 12, "bullet": True, "color": WHITE}),
    ("2.  The %T raw plate files for those SAME deposition samples (so AUC and deposition are sample-matched).", {"size": 12, "bullet": True, "color": WHITE}),
    ("3.  Then: join on Batch ID → deposition vs AUC (and AUC-peak, kinetics) → report R² / Pearson r → validate AUC as a deposition screen.", {"size": 12, "bullet": True, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])
footer(s)

# ---------------------------------------------------------------- Slide: time-course panel
s = prs.slides.add_slide(BLANK)
title_bar(s, "Time-Course Panel (0–15 min)", "One panel per sample, curves colored by time — like the 24-shampoo set")
if os.path.exists(f"{R}/tea_timecourse.png"):
    s.shapes.add_picture(f"{R}/tea_timecourse.png", Inches(0.25), Inches(1.25), width=Inches(11.4))
add_text(s, Inches(0.45), Inches(6.95), Inches(12.4), Inches(0.4), [
    ("Coacervate dip deepens over the 0–15 min read; N22510S panels show the clearest time-resolved 2-phase region.",
     {"size": 11.5, "color": DARK}),
])
footer(s)

# ---------------------------------------------------------------- Slide 7: status/next
s = prs.slides.add_slide(BLANK)
title_bar(s, "Status & Next Steps")
add_text(s, Inches(0.55), Inches(1.4), Inches(6.1), Inches(5.0), [
    ("Platform (done in this pilot)", {"size": 16, "bold": True, "color": BLUE}),
    ("Digitized %T ingest: upload raw → organize → plot.", {"size": 13.5, "bullet": True}),
    ("Auto-parse Batch ID + Description; rename plates to searchable names.", {"size": 13.5, "bullet": True}),
    ("Bimodal-accurate curve fit; 1:X dilution axis.", {"size": 13.5, "bullet": True}),
    ("Nexus-ready export (flex-driver / nexus_xy).", {"size": 13.5, "bullet": True}),
])
add_text(s, Inches(6.9), Inches(1.4), Inches(6.0), Inches(5.0), [
    ("Next", {"size": 16, "bold": True, "color": GREEN}),
    ("Request measured silicone deposition (µg/cm²) + matching %T plates → lock the AUC↔deposition correlation.", {"size": 13.5, "bullet": True}),
    ("Push WS-20251111-01082 results to Nexus.", {"size": 13.5, "bullet": True}),
    ("Add remaining plates + backfill past %T studies.", {"size": 13.5, "bullet": True}),
    ("Quantify the shift (Δ onset / Δ trough vs the 0% control).", {"size": 13.5, "bullet": True}),
    ("Extend platform to phase-diagram experiments.", {"size": 13.5, "bullet": True}),
])
footer(s)

out = f"{R}/Tea_Saponin_Coacervation_Pilot.pptx"
prs.save(out)
print("saved", out, "slides:", len(prs.slides._sldIdLst))
