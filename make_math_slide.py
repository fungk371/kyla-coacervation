"""One-slide deck: the mathematics behind %T -> Absorbance -> Coacervation AUC.
Theme matches the coacervation capability / Tea deck (Navy P&G, Abadi, 16:9).
Equations are rendered as crisp math PNGs via matplotlib mathtext and embedded.
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FONT = "Abadi"
NAVY = RGBColor(0x00, 0x26, 0x6A)
BLUE = RGBColor(0x2E, 0x75, 0xB6)
LIGHT = RGBColor(0xEE, 0xF3, 0xF9)
GREY = RGBColor(0x5A, 0x64, 0x70)
DARK = RGBColor(0x1E, 0x2A, 0x36)
GREEN = RGBColor(0x2E, 0x9E, 0x5B)
RED = RGBColor(0xC0, 0x39, 0x2B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
NAVY_HEX = "#00266A"
R = "Reports"
os.makedirs(R, exist_ok=True)

# --------------------------------------------------------- equation PNGs
def render_eqs(lines, path, fontsize=21, color=NAVY_HEX, w=6.2, line_h=0.62):
    n = len(lines)
    fig = plt.figure(figsize=(w, line_h * n + 0.1), dpi=300)
    for i, ln in enumerate(lines):
        y = 1 - (i + 0.5) / n
        fig.text(0.02, y, ln, fontsize=fontsize, color=color, va="center", ha="left")
    fig.savefig(path, transparent=True, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    return path

opt_png = os.path.join(R, "_eq_optics.png")
auc_png = os.path.join(R, "_eq_auc.png")
fp_png = os.path.join(R, "_eq_fp.png")

render_eqs([
    r"$T \;=\; e^{-\tau \ell}$   (Beer$-$Lambert attenuation)",
    r"$A \;=\; -\log_{10} T \;=\; \dfrac{\tau\,\ell}{\ln 10}\;\propto\;\tau\;\propto\;N\sigma$",
], opt_png, fontsize=20)

render_eqs([
    r"$\mathrm{AUC}(t)=\int_{f_{lo}}^{f_{hi}}\hat{A}(f,t)\,df$",
    r"$\mathrm{AUC}_{persist}=\int_{t_0}^{t_1}\!\!\int_{f_{lo}}^{f_{hi}}\hat{A}(f,t)\,df\,dt$",
], auc_png, fontsize=22, line_h=0.72)

render_eqs([
    r"$S=A_{max}-A_{base}$      $R=\dfrac{A_{max}-A_{end}}{A_{max}-A_{base}}$      $m=\dfrac{d\,\mathrm{AUC}}{dt}$",
], fp_png, fontsize=17, w=6.4, line_h=0.55)

# --------------------------------------------------------- deck
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height


def _set_font(run, size=13, bold=False, color=DARK, italic=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {}); rPr.append(el)
        el.set("typeface", FONT)


def add_text(slide, left, top, width, height, lines, *, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(3)
        txt, opts = (ln, {}) if isinstance(ln, str) else ln
        if opts.get("bullet"):
            txt = "•  " + txt
        r = p.add_run(); r.text = txt
        _set_font(r, size=opts.get("size", 13), bold=opts.get("bold", False),
                  color=opts.get("color", DARK), italic=opts.get("italic", False))
    return tb


def section(slide, left, top, width, label, color=NAVY):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, Inches(0.34))
    bar.fill.solid(); bar.fill.fore_color.rgb = color; bar.line.fill.background()
    tf = bar.text_frame; tf.margin_left = Inches(0.12); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; r = p.add_run(); r.text = label
    _set_font(r, size=13, bold=True, color=WHITE)


s = prs.slides.add_slide(BLANK)

# title bar
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(0.95))
bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
tf = bar.text_frame; tf.margin_left = Inches(0.45); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
p = tf.paragraphs[0]; r = p.add_run()
r.text = "From %T to Absorbance — the Mathematics Behind Coacervation AUC"
_set_font(r, size=23, bold=True, color=WHITE)

# accent
acc = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.45), Inches(0.9), Inches(3.0), Pt(3))
acc.fill.solid(); acc.fill.fore_color.rgb = BLUE; acc.line.fill.background()

# ---------------- LEFT column: optics / why absorbance
section(s, Inches(0.45), Inches(1.15), Inches(6.05), "1 · Optical transform — why absorbance, not %T")
s.shapes.add_picture(opt_png, Inches(0.55), Inches(1.62), width=Inches(5.8))
add_text(s, Inches(0.55), Inches(3.02), Inches(5.95), Inches(0.3),
         [("T = transmitted fraction = %T / 100    ·    600 nm    ·    τ = turbidity, ℓ = path, Nσ = (particle count × scattering cross-section)",
           {"size": 10, "italic": True, "color": GREY})])
add_text(s, Inches(0.55), Inches(3.5), Inches(5.95), Inches(2.4), [
    ("%T depends exponentially on turbidity; the log makes A linear in τ, additive, and integrable.",
     {"size": 12.5, "bullet": True, "color": DARK}),
    ("A is proportional to TURBIDITY (optical density) — a linear, benchmark-comparable proxy for coacervation.",
     {"size": 12.5, "bullet": True, "color": NAVY, "bold": True}),
    ("Not a proven measure of coacervate mass: scattering also depends on particle size & refractive-index contrast, "
     "so use for relative screening within comparable systems + validate with microscopy/deposition.",
     {"size": 12, "bullet": True, "color": RED}),
])

# ---------------- RIGHT column: %T compression table
section(s, Inches(6.75), Inches(1.15), Inches(6.1), "2 · Why %T is compressed")
rows = [("Cloudiness", "%T", "A = −log₁₀(%T/100)"),
        ("Clear", "100", "0.00"),
        ("Barely hazy", "91", "0.04"),
        ("Lightly cloudy", "50", "0.30"),
        ("Cloudy", "10", "1.00"),
        ("Very cloudy", "1", "2.00")]
tbl_shape = s.shapes.add_table(len(rows), 3, Inches(6.85), Inches(1.6),
                               Inches(5.9), Inches(2.0))
table = tbl_shape.table
table.columns[0].width = Inches(2.7); table.columns[1].width = Inches(1.1)
table.columns[2].width = Inches(2.1)
for ri, row in enumerate(rows):
    for ci, val in enumerate(row):
        cell = table.cell(ri, ci)
        cell.margin_top = Pt(1); cell.margin_bottom = Pt(1)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        para = cell.text_frame.paragraphs[0]
        para.alignment = PP_ALIGN.CENTER if ci else PP_ALIGN.LEFT
        run = para.add_run(); run.text = val
        header = (ri == 0)
        _set_font(run, size=11.5, bold=header, color=WHITE if header else DARK)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY if header else (LIGHT if ri % 2 else WHITE)
add_text(s, Inches(6.85), Inches(3.75), Inches(6.0), Inches(0.9), [
    ("Two equal 9-point %T steps ≠ equal cloudiness: 100→91 %T is A 0→0.04 (nothing); "
     "10→1 %T is A 1.0→2.0 (a 10× jump in blocked light).", {"size": 12, "color": DARK}),
    ("The log un-squishes the low-%T corner where all the strong coacervation lives.",
     {"size": 12, "bold": True, "color": NAVY}),
])

# ---------------- bottom band: AUC + fingerprint
section(s, Inches(0.45), Inches(4.95), Inches(12.4), "3 · Coacervation AUC & fingerprint (integrating the absorbance curve)")
s.shapes.add_picture(auc_png, Inches(0.6), Inches(5.4), width=Inches(4.5))
add_text(s, Inches(5.35), Inches(5.42), Inches(7.5), Inches(1.0), [
    ("AUC = area under the fitted absorbance–concentration curve over a chosen dilution window "
     "(full-curve vs consumer-window, e.g. 1:1–1:20). Persistence AUC adds the time axis.",
     {"size": 12, "color": DARK}),
    ("Window is chosen by the decision, not by the highest number.",
     {"size": 12, "bold": True, "color": NAVY}),
])
s.shapes.add_picture(fp_png, Inches(0.6), Inches(6.55), width=Inches(5.0))
add_text(s, Inches(5.8), Inches(6.58), Inches(7.1), Inches(0.5), [
    ("S = strength (peak above baseline) · R = recovery/clearing · m = build(+)/decay(−) kinetics · "
     "plus onset & breadth.", {"size": 11, "color": GREY})])

# footer
add_text(s, Inches(0.45), Inches(7.16), Inches(12.4), Inches(0.3),
         [("Procter & Gamble Proprietary Information  ·  Coacervation %T Platform  ·  Kyla Fung",
           {"size": 9, "color": GREY})])

out = os.path.join(R, "Coacervation_AUC_Math_Onepager.pptx")
prs.save(out)
print("wrote", out)
