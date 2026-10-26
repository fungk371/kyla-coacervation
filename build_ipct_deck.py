"""Assemble Reports/Inverse_PctT_Guide.pptx (16:9).

Imported at the end of make_ipct_deck.py once the figures are generated.
Teaching + data deck: how to read inverse %T, the metrics to compare, the data
so far (Cassia/Nat Clear, 3196/Nat Caready, overlay, method notes, microscopy
validation plan), and OPEN slots for the rest of Brandon's 16 samples.
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
AMBER = RGBColor(0xB9, 0x77, 0x00)
PURPLE = RGBColor(0x8E, 0x44, 0xAD)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DASH = RGBColor(0x9A, 0xA5, 0xB1)

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
    tf = bar.text_frame; tf.margin_left = Inches(0.45)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; r = p.add_run(); r.text = title
    _set_font(r, size=25, bold=True, color=WHITE)
    if sub:
        p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = sub
        _set_font(r2, size=13, color=RGBColor(0xCF, 0xDD, 0xF0))


def footer(slide, n):
    add_text(slide, Inches(0.45), Inches(7.06), Inches(12.4), Inches(0.36),
             [("Inverse %T method guide  \u00b7  Kyla Fung  \u00b7  Beauty Analytical",
               {"size": 9, "color": GREY})])
    add_text(slide, Inches(12.5), Inches(7.06), Inches(0.7), Inches(0.36),
             [(str(n), {"size": 9, "color": GREY})], align=PP_ALIGN.RIGHT)


def add_image(slide, path, left, top, max_w, max_h):
    if not os.path.exists(path):
        add_text(slide, left, top, max_w, Inches(0.4),
                 [(f"[missing figure: {os.path.basename(path)}]",
                   {"size": 11, "color": RED})])
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


def placeholder(slide, left, top, width, height, label):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xF6, 0xF8, 0xFB)
    box.line.color.rgb = DASH; box.line.width = Pt(1.5)
    ln = box.line._get_or_add_ln()
    d = ln.makeelement(qn("a:prstDash"), {"val": "dash"}); ln.append(d)
    add_text(slide, left, top, width, height,
             [("\u2795", {"size": 26, "color": DASH}),
              (label, {"size": 13, "bold": True, "color": GREY})],
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


# ==================================================================== 1: title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
add_text(s, Inches(0.9), Inches(1.7), Inches(11.6), Inches(2.4), [
    ("Reading the Inverse %T Curve", {"size": 40, "bold": True, "color": WHITE}),
    ("A screening method for coacervation in opaque shampoos \u2014 what the curve means & how to compare formulas",
     {"size": 18, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])
accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(3.05), Inches(3.4), Pt(3))
accent.fill.solid(); accent.fill.fore_color.rgb = BLUE; accent.line.fill.background()
add_text(s, Inches(0.9), Inches(4.5), Inches(11.5), Inches(2.2), [
    ("Kyla Fung  \u00b7  Beauty Analytical", {"size": 17, "bold": True, "color": WHITE}),
    ("Worked examples: GH130 chassis \u00b7 Cassia, Nat Clear, Nhance 3196, Nat Caready (0.25% polymer, 200 \u00b5L read)",
     {"size": 14, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
    ("September 2026", {"size": 13, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])

# ==================================================================== 2: what/why
s = prs.slides.add_slide(BLANK)
title_bar(s, "What the inverse %T method measures", "Coacervation screening for OPAQUE formulas")
card(s, Inches(0.5), Inches(1.35), Inches(6.05), Inches(3.1), "The idea", [
    ("Cationic conditioning polymer + surfactant phase-separate (coacervate) as the shampoo is diluted during rinse.", {"size": 13, "bullet": True}),
    ("Coacervate scatters light. We track well turbidity (%T) across a 48-point dilution series (1:1 \u2192 1:539).", {"size": 13, "bullet": True}),
    ("Read in-well (no spin): LOW %T = more scatterers = MORE coacervate.", {"size": 13, "bullet": True, "bold": True, "color": NAVY}),
], accent=BLUE)
card(s, Inches(6.75), Inches(1.35), Inches(6.05), Inches(3.1), "Why 'inverse'", [
    ("Clear formulas: coacervation shows as a %T DROP from a clear baseline.", {"size": 13, "bullet": True}),
    ("Opaque formulas start cloudy, so we first watch the base clarify, THEN catch the coacervation re-turbidity on top.", {"size": 13, "bullet": True}),
    ("Same physics, read 'in reverse' against an opaque background.", {"size": 13, "bullet": True}),
    ("Centrifuged-supernatant variant flips the sign (more coacervate = clearer) \u2014 know which you ran.", {"size": 12, "italic": True, "color": GREY, "bullet": True}),
], accent=GREEN)
card(s, Inches(0.5), Inches(4.65), Inches(12.3), Inches(2.0), "Dilution axis \u2248 rinse timeline", [
    ("Concentrated (left) = product as applied / lathering  \u2192  high dilution (right) = progressive rinse-out.", {"size": 13, "bullet": True}),
    ("Rough anchors: wash ~1:10  \u00b7  early rinse ~1:20  \u00b7  late rinse 1:30+.  WHERE the dip sits = WHEN it deposits.", {"size": 13, "bullet": True, "bold": True, "color": NAVY}),
], accent=NAVY)
footer(s, 2)

# ==================================================================== 3: how to read (annotated)
s = prs.slides.add_slide(BLANK)
title_bar(s, "How to read the curve", "Every feature, on a real curve (Cassia)")
add_image(s, f"{R}/ipct_howto_annotated.png", Inches(0.35), Inches(1.15), Inches(8.9), Inches(5.9))
card(s, Inches(9.45), Inches(1.2), Inches(3.45), Inches(5.7), "The 5 regions", [
    ("Opaque floor \u2014 formula base opacity (not coacervate).", {"size": 12, "bullet": True}),
    ("Clarification \u2014 base dilutes out, %T rises.", {"size": 12, "bullet": True}),
    ("Peak clarity \u2014 quiet window before coacervation.", {"size": 12, "bullet": True, "color": GREEN}),
    ("Coacervation DIP \u2014 re-turbidity = max coacervate.", {"size": 12, "bullet": True, "bold": True, "color": RED}),
    ("Redissolution \u2014 over-dilution dissolves it back.", {"size": 12, "bullet": True}),
    ("DEPTH = amount \u00b7 POSITION = rinse timing \u00b7 WIDTH = robustness.", {"size": 12, "bold": True, "color": NAVY}),
], accent=PURPLE)
footer(s, 3)

# ==================================================================== 4: metrics to compare
s = prs.slides.add_slide(BLANK)
title_bar(s, "Key metrics to compare across formulas", "Turn the curve into 4 numbers")
add_image(s, f"{R}/ipct_metrics_bars.png", Inches(0.35), Inches(1.2), Inches(9.1), Inches(4.6))
card(s, Inches(9.55), Inches(1.2), Inches(3.35), Inches(5.7), "Read-out", [
    ("DEPTH (%T drop) = how much coacervate forms.", {"size": 12, "bullet": True, "bold": True}),
    ("POSITION (1:X of dip) = when in rinse it deposits. Low 1:X = early/heavy; high 1:X = late/light.", {"size": 12, "bullet": True}),
    ("WIDTH (decades) = how robust across the rinse.", {"size": 12, "bullet": True}),
    ("AUC (area of dip) = single total-coacervate ranking number.", {"size": 12, "bullet": True}),
    ("Also note: onset dilution, and whether it redissolves (reversible).", {"size": 12, "bullet": True, "color": GREY}),
    ("No dip = little/no coacervation (e.g. Nat Clear).", {"size": 12, "bold": True, "color": NAVY}),
], accent=AMBER)
footer(s, 4)

# ==================================================================== 5: overlay
s = prs.slides.add_slide(BLANK)
title_bar(s, "Formulas so far \u2014 overlay", "GH130 chassis, 0.25% polymer, 200 \u00b5L read")
add_image(s, f"{R}/ipct_formula_overlay.png", Inches(0.35), Inches(1.2), Inches(9.1), Inches(5.7))
card(s, Inches(9.55), Inches(1.2), Inches(3.35), Inches(5.7), "So far", [
    ("Cassia \u2014 strong, well-defined dip (~1:48). Deposits late-rinse.", {"size": 12, "bullet": True, "color": PURPLE}),
    ("Nhance 3196 / Nat Caready \u2014 clarify with a broad shoulder; moderate signal.", {"size": 12, "bullet": True}),
    ("Nat Clear \u2014 flat/high, no real dip = little coacervation.", {"size": 12, "bullet": True, "color": GREEN}),
    ("\u25bc marks each coacervation dip.", {"size": 12, "italic": True, "color": GREY}),
], accent=BLUE)
footer(s, 5)

# ==================================================================== 6: Cassia + Nat Clear detail
s = prs.slides.add_slide(BLANK)
title_bar(s, "Cassia vs Nat Clear", "Strong coacervator vs. clarifies-and-stays-clear")
add_image(s, f"{R}/opaque_ipct_cassia_natclear.png", Inches(0.3), Inches(1.2), Inches(9.4), Inches(5.7))
card(s, Inches(9.8), Inches(1.2), Inches(3.1), Inches(5.7), "Contrast", [
    ("Cassia: floor ~1%T \u2192 peak ~88%T @1:12 \u2192 DIP ~57%T @1:48 \u2192 recovers.", {"size": 12, "bullet": True, "color": PURPLE}),
    ("Nat Clear: clears by ~1:5 and stays 85\u201390%T \u2014 no coacervation dip.", {"size": 12, "bullet": True, "color": GREEN}),
    ("Same chassis \u2014 the polymer is the difference.", {"size": 12, "bold": True, "color": NAVY}),
], accent=PURPLE)
footer(s, 6)

# ==================================================================== 7: 3196 + Nat Caready
s = prs.slides.add_slide(BLANK)
title_bar(s, "Nhance 3196 & Nat Caready", "First opaque runs on GH130")
add_image(s, f"{R}/opaque_ipct_gh130.png", Inches(0.3), Inches(1.2), Inches(9.4), Inches(5.7))
card(s, Inches(9.8), Inches(1.2), Inches(3.1), Inches(5.7), "Notes", [
    ("Both clarify from an opaque floor with a broad re-turbidity shoulder.", {"size": 12, "bullet": True}),
    ("Caveat: these did not clearly redissolve at the dilute end \u2014 check whether the read was direct vs. centrifuged.", {"size": 12, "bullet": True, "color": AMBER}),
    ("Use as the baseline pair for Brandon's polymer series.", {"size": 12, "bullet": True, "color": NAVY}),
], accent=BLUE)
footer(s, 7)

# ==================================================================== 8: method controls (volume)
s = prs.slides.add_slide(BLANK)
title_bar(s, "Method control \u2014 read volume matters", "100 \u00b5L vs 200 \u00b5L (path length)")
add_image(s, f"{R}/opaque_ipct_volume_compare.png", Inches(0.3), Inches(1.2), Inches(9.4), Inches(5.7))
card(s, Inches(9.8), Inches(1.2), Inches(3.1), Inches(5.7), "Rule", [
    ("200 \u00b5L = deeper floor + sharper dip (better contrast).", {"size": 12, "bullet": True}),
    ("100 \u00b5L = shorter path \u2192 higher %T, shallower dip, cleaner supernatant.", {"size": 12, "bullet": True}),
    ("Never mix volumes in one comparison; %T & AUC are not comparable across path lengths.", {"size": 12, "bold": True, "color": RED, "bullet": True}),
    ("Lock final volume + reader settings during qualification.", {"size": 12, "bullet": True, "color": NAVY}),
], accent=AMBER)
footer(s, 8)

# ==================================================================== 9: microscopy validation
s = prs.slides.add_slide(BLANK)
title_bar(s, "Validating the dip = coacervate", "Minimum microscopy set (Cassia)")
card(s, Inches(0.5), Inches(1.35), Inches(12.3), Inches(2.35), "3-picture proof", [
    ("D6 (1:53, the dip) \u2014 should be FULL of spherical coacervate droplets (the scatterers).", {"size": 13, "bullet": True, "color": RED}),
    ("C5 (1:12.5, peak clarity) \u2014 same formula, nearly EMPTY field \u2192 droplets appear WITH the dip.", {"size": 13, "bullet": True, "color": GREEN}),
    ("D6 no-polymer control \u2014 EMPTY \u2192 droplets are polymer coacervate, not surfactant/pearlizer.", {"size": 13, "bullet": True, "color": NAVY}),
    ("(+ optional D9, 1:97, recovered \u2014 droplets gone = reversible.)", {"size": 12, "italic": True, "color": GREY, "bullet": True}),
], accent=GREEN)
card(s, Inches(0.5), Inches(3.95), Inches(6.05), Inches(2.7), "How to shoot", [
    ("Same magnification & exposure for every frame.", {"size": 12, "bullet": True}),
    ("Crossed polarizers to tell liquid coacervate (dark) from birefringent EGDS/mesophase (Maltese cross).", {"size": 12, "bullet": True}),
    ("Sample from the well of interest; keep prep identical.", {"size": 12, "bullet": True}),
], accent=BLUE)
placeholder(s, Inches(6.75), Inches(3.95), Inches(6.05), Inches(2.7),
            "DROP MICROSCOPY IMAGES HERE\n(D6 dip \u00b7 C5 clear \u00b7 D6 control)")
footer(s, 9)

# ==================================================================== 10: plate map
s = prs.slides.add_slide(BLANK)
title_bar(s, "Plate map \u2014 well \u2192 dilution", "2 troughs/plate; rows A\u2013D = sample 1, E\u2013H = sample 2")
card(s, Inches(0.5), Inches(1.35), Inches(12.3), Inches(3.2), "Same column = same dilution in both troughs (1:X)", [
    ("Row A/E:  1:1 \u00b7 1:1.1 \u00b7 1:1.2 \u00b7 1:1.3 \u00b7 1:1.5 \u00b7 1:1.6 \u00b7 1:1.8 \u00b7 1:2.0 \u00b7 1:2.3 \u00b7 1:2.5 \u00b7 1:2.9 \u00b7 1:3.3", {"size": 12, "bullet": True}),
    ("Row B/F:  1:3.5 \u00b7 1:3.7 \u00b7 1:4.0 \u00b7 1:4.2 \u00b7 1:4.6 \u00b7 1:4.9 \u00b7 1:5.4 \u00b7 1:5.8 \u00b7 1:6.4 \u00b7 1:7.1 \u00b7 1:7.9 \u00b7 1:8.8", {"size": 12, "bullet": True}),
    ("Row C/G:  1:9.4 \u00b7 1:10 \u00b7 1:10.7 \u00b7 1:11.6 \u00b7 1:12.5 \u00b7 1:13.6 \u00b7 1:14.9 \u00b7 1:16.4 \u00b7 1:18.3 \u00b7 1:20.6 \u00b7 1:23.5 \u00b7 1:27.4", {"size": 12, "bullet": True}),
    ("Row D/H:  1:29.9 \u00b7 1:32.8 \u00b7 1:36.2 \u00b7 1:40.5 \u00b7 1:46 \u00b7 1:53 \u00b7 1:62.5 \u00b7 1:76 \u00b7 1:97 \u00b7 1:134 \u00b7 1:215 \u00b7 1:539", {"size": 12, "bullet": True}),
], accent=NAVY)
card(s, Inches(0.5), Inches(4.75), Inches(12.3), Inches(1.9), "Microscopy wells (Cassia example)", [
    ("Neat A1 (1:1) \u00b7 onset A9 (1:2.3) \u00b7 peak clarity C5 (1:12.5) \u00b7 DIP D5/D6 (1:46\u201353) \u00b7 redissolution D9 (1:97).", {"size": 13, "bullet": True, "bold": True, "color": NAVY}),
    ("Trough 2 (Nat Clear) = same columns in rows E\u2013H.", {"size": 12, "bullet": True, "color": GREY}),
], accent=PURPLE)
footer(s, 10)

# ==================================================================== 11: Brandon open
s = prs.slides.add_slide(BLANK)
title_bar(s, "Brandon's polymer series \u2014 to run", "Rank all 16 by depth / position / width / AUC")
card(s, Inches(0.5), Inches(1.35), Inches(4.0), Inches(5.3), "Plan", [
    ("Two chassis (BC128o M, GH130 LT1) \u00d7 8 polymers @ 0.25%.", {"size": 13, "bullet": True}),
    ("Controls: NH3196 (no cationic polymer benchmark).", {"size": 13, "bullet": True}),
    ("Polymers: Pq-6/22/47/53, Cassia, Nat Clear, Nat Caready.", {"size": 13, "bullet": True}),
    ("Done so far: 3196, Nat Caready, Cassia, Nat Clear (GH130).", {"size": 13, "bullet": True, "color": GREEN}),
    ("Each: run inverse %T + microscopy at the dip + no-polymer control.", {"size": 13, "bullet": True, "color": NAVY}),
], accent=BLUE)
placeholder(s, Inches(4.75), Inches(1.35), Inches(8.05), Inches(5.3),
            "OPEN \u2014 cross-formula ranking chart\n(depth \u00b7 dip position \u00b7 width \u00b7 AUC)\nto be filled as runs complete")
footer(s, 11)

# ==================================================================== 12: takeaways
s = prs.slides.add_slide(BLANK)
title_bar(s, "Takeaways", "How to use this deck")
card(s, Inches(0.5), Inches(1.4), Inches(12.3), Inches(5.2), "", [
    ("The dip is the signal: deeper = more coacervate, its 1:X = when it deposits, its width = how robust.", {"size": 15, "bullet": True, "bold": True, "color": NAVY}),
    ("Compare formulas on 4 numbers: DEPTH, POSITION, WIDTH, AUC (+ redissolution).", {"size": 15, "bullet": True}),
    ("Opaque floor is formula base, not coacervate \u2014 don't confuse it with the dip.", {"size": 15, "bullet": True}),
    ("Lock read volume, final volume, and reader settings; never mix volumes in one comparison.", {"size": 15, "bullet": True}),
    ("Validate with microscopy at the dip + a no-polymer control; a clear read is (100\u2212%T) minus that control.", {"size": 15, "bullet": True}),
    ("Cassia coacervates strongly (late rinse); Nat Clear barely does \u2014 a clean worked contrast.", {"size": 15, "bullet": True, "color": PURPLE}),
], accent=GREEN)
footer(s, 12)

out = f"{R}/Inverse_PctT_Guide.pptx"
prs.save(out)
print(f"\nwrote {out}  ({len(prs.slides._sldIdLst)} slides)")
