"""Build a Lasentec (FBRM) + microscopy competitor-analysis deck (16:9).

Covers: method (FBRM at 1:49 dilution), competitor size-distribution overlay,
diagnostic panels, water-hardness (0 vs 7 gpg L'Oreal), and the coacervate-size
vs consumer-preference correlation with a Pantene win strategy. Includes OPEN
placeholder slides for incoming microscopy images, more competitors, and
internal benchmark shampoos.

Reuses figures in Reports/. Output: Reports/Lasentec_Competitor_Analysis.pptx
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
             [("Lasentec + microscopy competitor analysis  \u00b7  Kyla Fung  \u00b7  Beauty Analytical",
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
    """A dashed 'drop your result here' box."""
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
add_text(s, Inches(0.9), Inches(1.8), Inches(11.6), Inches(2.4), [
    ("Coacervate Characterization of Competitor Shampoos", {"size": 36, "bold": True, "color": WHITE}),
    ("Lasentec (FBRM) + microscopy \u2014 linking coacervate size to consumer preference",
     {"size": 18, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])
accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(3.05), Inches(3.4), Pt(3))
accent.fill.solid(); accent.fill.fore_color.rgb = BLUE; accent.line.fill.background()
add_text(s, Inches(0.9), Inches(4.4), Inches(11.5), Inches(2.2), [
    ("Kyla Fung  \u00b7  Beauty Analytical", {"size": 17, "bold": True, "color": WHITE}),
    ("Pantene vs. Dove Intensive Repair, L'Oreal Hyaluron Plump, Kerastase Nutritive  \u00b7  measured at 1:49 dilution",
     {"size": 14, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
    ("September 2026", {"size": 13, "color": RGBColor(0xCF, 0xDD, 0xF0)}),
])

# ==================================================================== 2: objective / method
s = prs.slides.add_slide(BLANK)
title_bar(s, "Objective & method", "Why we measure coacervate size, and how")
card(s, Inches(0.5), Inches(1.35), Inches(6.05), Inches(2.6), "What & why", [
    ("Coacervates form when cationic conditioning polymer + surfactant phase-separate on dilution (rinsing).", {"size": 13, "bullet": True}),
    ("Coacervate deposits conditioning actives + fragrance onto hair \u2014 size/amount drive the benefit.", {"size": 13, "bullet": True}),
    ("Goal: fingerprint competitor coacervate structure and link it to what consumers actually notice.", {"size": 13, "bullet": True}),
], accent=BLUE)
card(s, Inches(6.75), Inches(1.35), Inches(6.05), Inches(2.6), "How (Lasentec / FBRM)", [
    ("FBRM = focused-beam reflectance; counts particle chord lengths (size proxy) every ~3 s.", {"size": 13, "bullet": True}),
    ("Measured at 1:49 dilution in DI water (rinse-relevant, matches internal SLR method).", {"size": 13, "bullet": True}),
    ("Report distribution shape, counts by size bin, and % counts > 30 \u00b5m (large-floc proxy).", {"size": 13, "bullet": True}),
    ("Chord length \u2248 0.6\u20130.8\u00d7 true diameter.", {"size": 12, "italic": True, "color": GREY}),
], accent=GREEN)
card(s, Inches(0.5), Inches(4.15), Inches(12.3), Inches(2.5), "Samples in this deck", [
    ("Pantene M10 (our product)  \u00b7  Dove Intensive Repair  \u00b7  L'Oreal Hyaluron Plump  \u00b7  Kerastase Nutritive", {"size": 14, "bold": True, "bullet": True}),
    ("All at 1:49 dilution in DI (0 gpg) water; L'Oreal Hyaluron also run at 7 gpg (hard water) for hardness effect.", {"size": 13, "bullet": True}),
    ("More competitors and internal benchmark shampoos to be added (see open slides).", {"size": 13, "italic": True, "color": GREY, "bullet": True}),
], accent=NAVY)
footer(s, 2)

# ==================================================================== 3: overlay
s = prs.slides.add_slide(BLANK)
title_bar(s, "Coacervate size distributions \u2014 all competitors", "Normalized chord-length overlay at 1:49 dilution")
add_image(s, f"{R}/lasentec_overlay_normalized.png", Inches(0.4), Inches(1.2), Inches(8.3), Inches(5.7))
card(s, Inches(8.95), Inches(1.25), Inches(3.95), Inches(5.5), "Read-out", [
    ("Peak chord length (size):", {"size": 13, "bold": True}),
    ("Pantene 3.8 \u00b5m (smallest)", {"size": 12, "bullet": True, "color": BLUE}),
    ("L'Oreal 4.7 \u00b5m", {"size": 12, "bullet": True, "color": GREEN}),
    ("Kerastase 5.4 \u00b5m", {"size": 12, "bullet": True, "color": RGBColor(0x8E,0x44,0xAD)}),
    ("Dove 18.8 \u00b5m (largest)", {"size": 12, "bullet": True, "color": RED}),
    ("All UNIMODAL at 1:49 \u2014 no bimodal agglomeration (that emerges only at \u2265 0.4% polymer in model systems).", {"size": 12}),
    ("Pantene = many tiny particles; Dove = few large flocs.", {"size": 12, "bold": True, "color": NAVY}),
], accent=BLUE)
footer(s, 3)

# ==================================================================== 4: diagnostic panels
s = prs.slides.add_slide(BLANK)
title_bar(s, "Counts, size bins & equilibrium", "Diagnostic panels \u2014 how much, how big, how stable")
add_image(s, f"{R}/lasentec_competitors_diwater.png", Inches(0.4), Inches(1.2), Inches(9.2), Inches(5.7))
card(s, Inches(9.85), Inches(1.25), Inches(3.05), Inches(5.5), "Notes", [
    ("Total counts (particles): Pantene ~32k \u226b Kerastase 23k > L'Oreal 12k \u226b Dove ~3.4k.", {"size": 12, "bullet": True}),
    ("% counts > 30 \u00b5m (flocs): Pantene 1.3% < L'Oreal 6.3% < Kerastase 9.8% < Dove 26.4%.", {"size": 12, "bullet": True}),
    ("Total counts cropped to post-addition equilibrium; all runs stable / reproducible.", {"size": 12, "bullet": True}),
    ("Trade-off: many-small (Pantene) vs few-large (Dove).", {"size": 12, "bold": True, "color": NAVY}),
], accent=GREEN)
footer(s, 4)

# ==================================================================== 5: water hardness
s = prs.slides.add_slide(BLANK)
title_bar(s, "Water hardness effect \u2014 L'Oreal Hyaluron Plump", "0 gpg (soft / DI) vs 7 gpg (hard) water")
add_image(s, f"{R}/lasentec_hyaluron_0vs7gpg.png", Inches(0.4), Inches(1.2), Inches(8.6), Inches(5.7))
card(s, Inches(9.25), Inches(1.25), Inches(3.65), Inches(5.5), "Finding", [
    ("Hard water (7 gpg) = MORE particles (~+70% counts) but SMALLER.", {"size": 13, "bullet": True}),
    ("More < 10 \u00b5m & 10\u2013100 \u00b5m, FEWER > 100 \u00b5m; square-wt mean 33 vs 44 \u00b5m.", {"size": 12, "bullet": True}),
    ("Ca/Mg promote many fine nuclei, less growth/coalescence.", {"size": 12, "bullet": True}),
    ("Hard water alone adds a small tiny-particle background (lime-soap) \u2014 baseline-subtract.", {"size": 12, "bullet": True}),
    ("Implication: hardness changes coacervate deposition \u2014 test all competitors at 7 gpg too.", {"size": 12, "bold": True, "color": NAVY}),
], accent=AMBER)
footer(s, 5)

# ==================================================================== 6: consumer correlation (the story)
s = prs.slides.add_slide(BLANK)
title_bar(s, "Coacervate size vs consumer preference", "Blind Controls study (top-box) correlated with FBRM floc size")
add_image(s, f"{R}/lasentec_consumer_correlation.png", Inches(0.35), Inches(1.15), Inches(9.4), Inches(4.4))
card(s, Inches(9.95), Inches(1.2), Inches(2.95), Inches(5.6), "Correlations\n(r vs % > 30 \u00b5m)", [
    ("Fragrance 10h  +0.97", {"size": 13, "bold": True, "color": RED, "bullet": True}),
    ("Fragrance 4\u20138h  +0.95", {"size": 13, "bold": True, "color": RED, "bullet": True}),
    ("Fragrance first-dry  +0.79", {"size": 12, "bullet": True}),
    ("No weigh-down  +0.56", {"size": 12, "bullet": True}),
    ("Overall system  +0.39", {"size": 12, "bullet": True}),
    ("Moisturized  +0.23", {"size": 12, "bullet": True}),
    ("n = 4 products = directional, not proof.", {"size": 11, "italic": True, "color": GREY}),
], accent=RED)
add_text(s, Inches(0.5), Inches(5.75), Inches(9.2), Inches(1.2), [
    ("Bigger coacervate flocs \u2192 fragrance deposits & lasts (r \u2248 0.97). Pantene (smallest flocs) is statistically WORST on 4\u20138h/10h fragrance; Dove (biggest flocs) WINS every fragrance touchpoint.",
     {"size": 13, "bold": True, "color": NAVY})])
footer(s, 6)

# ==================================================================== 7: interpretation / win strategy
s = prs.slides.add_slide(BLANK)
title_bar(s, "How Pantene can win", "The Dove playbook: big flocs + light-feel active")
card(s, Inches(0.5), Inches(1.3), Inches(6.05), Inches(2.55), "Why Dove wins (and how it dodges heavy feel)", [
    ("Largest flocs (26% > 30 \u00b5m) \u2192 best fragrance longevity & deposition.", {"size": 12, "bullet": True}),
    ("Yet wins No-Weigh-Down \u2014 uses a LIGHTWEIGHT silicone film-former (dimethiconol / silsesquioxane).", {"size": 12, "bullet": True}),
    ("= decouples deposition (big flocs) from heavy feel (light active).", {"size": 12, "bold": True, "color": NAVY}),
    ("Kerastase: mid flocs but loses on everything \u2192 size is necessary, not sufficient.", {"size": 12, "italic": True, "color": GREY, "bullet": True}),
], accent=RED)
card(s, Inches(6.75), Inches(1.3), Inches(6.05), Inches(2.55), "Pantene's gap", [
    ("Smallest particles (3.8 \u00b5m), fewest flocs (1.3% > 30 \u00b5m).", {"size": 12, "bullet": True}),
    ("Light feel (parity) but weak coacervate carrier \u2192 loses fragrance longevity to Dove.", {"size": 12, "bullet": True}),
    ("Opportunity: gain deposition/fragrance WITHOUT adding weigh-down.", {"size": 12, "bold": True, "color": NAVY}),
], accent=BLUE)
card(s, Inches(0.5), Inches(4.05), Inches(12.3), Inches(2.6), "Four ideas to win", [
    ("1.  Grow the flocs \u2014 push cationic polymer toward agglomeration (\u2265 0.4%), higher MW / charge density, or chassis that boosts dilution-triggered coacervation.", {"size": 13, "bullet": True}),
    ("2.  Copy Dove's decoupling \u2014 pair bigger flocs with a lightweight film-former so deposition rises but feel stays light (avoid the Kerastase heavy-feel trap).", {"size": 13, "bullet": True}),
    ("3.  Coacervate as a fragrance delivery system \u2014 co-deposit fragrance with the coacervate to attack Dove's strongest win (through-the-day scent).", {"size": 13, "bullet": True}),
    ("4.  Validate payload + feel + microscopy \u2014 don't chase size blindly; confirm we land in Dove's quadrant, not Kerastase's.", {"size": 13, "bullet": True}),
], accent=GREEN)
footer(s, 7)

# ==================================================================== 8: OPEN microscopy
s = prs.slides.add_slide(BLANK)
title_bar(s, "Microscopy \u2014 coacervate morphology", "OPEN \u00b7 drop optical/DIC images as they come in")
placeholder(s, Inches(0.5), Inches(1.35), Inches(3.9), Inches(3.4), "Pantene M10\n(microscopy image)")
placeholder(s, Inches(4.6), Inches(1.35), Inches(3.9), Inches(3.4), "Dove Intensive Repair\n(microscopy image)")
placeholder(s, Inches(8.7), Inches(1.35), Inches(4.1), Inches(3.4), "L'Oreal / Kerastase\n(microscopy image)")
card(s, Inches(0.5), Inches(4.95), Inches(12.3), Inches(1.75), "What to look for", [
    ("Confirm FBRM size story visually: Dove = large discrete flocs; Pantene = fine dispersed droplets.", {"size": 13, "bullet": True}),
    ("Match scale bars; note morphology (droplets vs networked/lamellar), and any agglomeration on dilution.", {"size": 13, "bullet": True}),
], accent=NAVY)
footer(s, 8)

# ==================================================================== 9: OPEN more competitors
s = prs.slides.add_slide(BLANK)
title_bar(s, "More competitor shampoos", "OPEN \u00b7 add FBRM overlays + bins as runs complete")
placeholder(s, Inches(0.5), Inches(1.35), Inches(7.7), Inches(5.4), "Competitor size-distribution overlay\n(drop updated lasentec_overlay figure)")
card(s, Inches(8.45), Inches(1.35), Inches(4.4), Inches(5.4), "Queue / to run", [
    ("Add each new competitor to PRODUCTS in make_lasentec_products.py, re-run to refresh overlay.", {"size": 12, "bullet": True}),
    ("Candidates: ______________", {"size": 13, "bold": True}),
    ("\u2022  ____________________", {"size": 12}),
    ("\u2022  ____________________", {"size": 12}),
    ("\u2022  ____________________", {"size": 12}),
    ("Run each at 0 gpg AND 7 gpg (hardness effect).", {"size": 12, "italic": True, "color": GREY}),
], accent=BLUE)
footer(s, 9)

# ==================================================================== 10: OPEN internal benchmarks
s = prs.slides.add_slide(BLANK)
title_bar(s, "Internal benchmark shampoos", "OPEN \u00b7 how our best formulas compare on coacervate size")
placeholder(s, Inches(0.5), Inches(1.35), Inches(7.7), Inches(5.4), "Internal benchmark overlay\n(drop FBRM figure)")
card(s, Inches(8.45), Inches(1.35), Inches(4.4), Inches(5.4), "Why benchmark internally", [
    ("Anchor competitor sizes against our known-good formulas \u2014 where does Pantene sit vs our best?", {"size": 12, "bullet": True}),
    ("Benchmarks to run: ____________", {"size": 13, "bold": True}),
    ("\u2022  ____________________", {"size": 12}),
    ("\u2022  ____________________", {"size": 12}),
    ("\u2022  ____________________", {"size": 12}),
    ("Tie back to deposition + consumer data where available.", {"size": 12, "italic": True, "color": GREY}),
], accent=GREEN)
footer(s, 10)

# ==================================================================== 11: summary / next steps
s = prs.slides.add_slide(BLANK)
title_bar(s, "Summary & next steps")
card(s, Inches(0.5), Inches(1.3), Inches(6.05), Inches(5.2), "What we learned", [
    ("Coacervate size differs sharply across competitors at 1:49: Pantene many-small \u2192 Dove few-large.", {"size": 13, "bullet": True}),
    ("Floc size (% > 30 \u00b5m) correlates almost perfectly with fragrance longevity (r \u2248 0.97).", {"size": 13, "bullet": True}),
    ("Dove wins by pairing big flocs with a lightweight film-former \u2014 deposition without weigh-down.", {"size": 13, "bullet": True}),
    ("Hard water shifts coacervate to more/smaller particles \u2014 hardness matters for deposition.", {"size": 13, "bullet": True}),
    ("Size alone isn't enough (Kerastase) \u2014 payload + feel decide liking.", {"size": 13, "bullet": True}),
], accent=BLUE)
card(s, Inches(6.75), Inches(1.3), Inches(6.05), Inches(5.2), "Next steps", [
    ("Add microscopy images to confirm morphology.", {"size": 13, "bullet": True}),
    ("Run remaining competitors + internal benchmarks (0 & 7 gpg).", {"size": 13, "bullet": True}),
    ("Prototype: grow Pantene flocs + lightweight film-former; measure FBRM + feel.", {"size": 13, "bullet": True}),
    ("Explore coacervate-fragrance co-deposition to attack Dove's scent win.", {"size": 13, "bullet": True}),
    ("Get deposition + fragrance-load data to firm up the correlation (n > 4).", {"size": 13, "bullet": True}),
    ("Contact: Kyla Fung  \u00b7  fung.k.1@pg.com", {"size": 12, "italic": True, "color": GREY}),
], accent=GREEN)
footer(s, 11)

out = f"{R}/Lasentec_Competitor_Analysis.pptx"
prs.save(out)
print(f"wrote {out}  ({len(prs.slides._sldIdLst)} slides)")
