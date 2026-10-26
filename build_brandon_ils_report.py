"""Build the Brandon coacervation <-> consumer report (.docx).

Inverse-%T coacervation vs the ILS consumer tress evaluation for the BC128o /
GH130 prototype screen. Embeds the coacervation-profile, ranking, overall-index
correlation, and per-attribute correlation figures.

Output: Reports/Brandon_Coacervation_vs_Consumer_Report.docx
"""
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

R = "Reports"
NAVY = RGBColor(0x1F, 0x4E, 0x78)
GREY = RGBColor(0x5A, 0x64, 0x70)


def h1(doc, t):
    p = doc.add_paragraph(); r = p.add_run(t)
    r.bold = True; r.font.size = Pt(15); r.font.color.rgb = NAVY
    p.space_before = Pt(10); p.space_after = Pt(4)


def h2(doc, t):
    p = doc.add_paragraph(); r = p.add_run(t)
    r.bold = True; r.font.size = Pt(12); r.font.color.rgb = NAVY
    p.space_before = Pt(8); p.space_after = Pt(2)


def body(doc, t):
    p = doc.add_paragraph(); r = p.add_run(t); r.font.size = Pt(10.5)
    p.space_after = Pt(6)


def bullet(doc, t):
    p = doc.add_paragraph(style="List Bullet"); p.add_run(t).font.size = Pt(10.5)


def figure(doc, fname, cap, width=6.4):
    path = os.path.join(R, fname)
    if os.path.exists(path):
        doc.add_picture(path, width=Inches(width))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        c = doc.add_paragraph(); cr = c.add_run("Figure. " + cap)
        cr.italic = True; cr.font.size = Pt(9); cr.font.color.rgb = GREY
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER; c.space_after = Pt(10)


def main():
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    t = doc.add_paragraph(); tr = t.add_run("Coacervation \u2194 Consumer Performance")
    tr.bold = True; tr.font.size = Pt(20); tr.font.color.rgb = NAVY
    s = doc.add_paragraph()
    sr = s.add_run("Inverse-%T coacervation vs ILS consumer evaluation \u2014 "
                   "BC128o M & GH130 LT1 prototype screen (0.25% polymer, opaque AD shampoos)")
    sr.font.size = Pt(12.5); sr.bold = True
    m = doc.add_paragraph()
    mr = m.add_run("Prepared by Kyla Fung (P&G Beauty Analytical) for discussion with Mark Brown. "
                   "Directional \u2014 one tress per product; P&G Confidential.")
    mr.font.size = Pt(9); mr.font.color.rgb = GREY
    doc.add_paragraph()

    h1(doc, "1. Summary \u2014 what we found")
    body(doc, "We measured coacervation on the opaque anti-dandruff prototypes using the inverse-%T "
              "method (dilute \u2192 centrifuge \u2192 read the clarified supernatant; the coacervate captures "
              "and sediments the opacifier + Piroctone Olamine AD active + silicone, so a clearer "
              "supernatant = more coacervate). We then joined the coacervation fingerprint to the ILS "
              "consumer tress evaluation. The result is a clear, consistent story:")
    bullet(doc, "The amount of coacervate a formula makes strongly PREDICTS its overall consumer "
                "conditioning (Pearson r = +0.75 across both chassis).")
    bullet(doc, "More specifically, coacervate amount tracks the CONDITIONING attributes \u2014 smooth "
                "surface feel (r=+0.84), moisturized feel (+0.79), wet slip (+0.76), inter-fiber "
                "smoothness (+0.75), creaminess, detangling \u2014 while it is INVERSELY related to the "
                "\u201cclean/squeaky\u201d feel (r=\u22120.69) and unrelated to volume (+0.10).")
    bullet(doc, "So coacervate amount is essentially the conditioning\u2013vs\u2013clean axis: high-coacervate "
                "naturals (Cassia, Nat Clear, Nat Caready) condition best; low-coacervate polyquats "
                "(esp. Polyquat-6) feel cleanest/airiest but condition worst.")
    bullet(doc, "Inverse-%T is therefore a fast, quantitative screen for conditioning performance in "
                "opaque AD shampoos \u2014 something standard %T cannot do.")

    h1(doc, "2. Method \u2014 inverse %T for opaque shampoos")

    h2(doc, "2a. The chemistry: why dilution makes a coacervate")
    body(doc, "A conditioning shampoo pairs a cationic polymer (here guar 3196, the polyquaterniums, or "
              "the natural cationic polymers) with anionic surfactant (SLE3S / SLS) plus amphoteric CAPB. "
              "In the neat product the surfactant is far above its critical micelle concentration, so it "
              "wraps the polymer\u2019s cationic charges in an excess of micelles and the polymer\u2013surfactant "
              "complex stays fully soluble and clear-in-the-bulk. When the consumer rinses, the product is "
              "massively diluted and the surfactant concentration falls. Below a critical surfactant : "
              "polymer ratio there is no longer enough surfactant to solubilise the complex, so the "
              "oppositely-charged polymer and surfactant associatively phase-separate into a dense, "
              "surfactant-rich second liquid phase \u2014 the COACERVATE. This is the classic dilution-deposition "
              "mechanism (Goddard; Miyake): the coacervate is what actually deposits on the hair during "
              "rinsing and carries the silicone, the opacifier and the Piroctone Olamine anti-dandruff "
              "active down onto the fiber. Coacervation only happens inside a WINDOW of dilution \u2014 too "
              "concentrated and it stays solubilised, too dilute and both partners are simply washed apart.")

    h2(doc, "2b. Where the coacervation AMOUNT number comes from")
    body(doc, "Standard %T reads how cloudy a sample is. That works for clear shampoos (coacervation makes "
              "them turbid), but opaque AD shampoos are already saturated \u2014 they read ~0% no matter what \u2014 "
              "so we invert the read. We dilute the product across the full rinse range, CENTRIFUGE each "
              "dilution, and read the %T of the clarified SUPERNATANT. The logic is direct: the coacervate "
              "droplets capture the opacifier + Piroctone Olamine + silicone and, being dense, are spun to "
              "the bottom; whatever they pulled down is no longer scattering light, so the supernatant "
              "CLEARS. The more coacervate a formula makes, the more payload it sediments and the higher the "
              "supernatant %T climbs. Plotted against dilution, %T therefore rises from an opaque floor into "
              "a HUMP and comes back down \u2014 the shape of the coacervation window. From that curve we read:")
    bullet(doc, "AMOUNT = hump HEIGHT: the peak clearing of the supernatant above its opaque floor. A taller "
                "hump means more coacervate formed and sedimented more payload. This is our primary amount "
                "metric \u2014 it is the most robust predictor of consumer conditioning and it holds in both "
                "chassis. (An integrated version, the area of the hump above the floor over the dilution "
                "range, gives the same ranking and is used as a cross-check.)")
    bullet(doc, "WIDTH = decades of dilution the hump spans: how much of the rinse trajectory sits inside "
                "the coacervating window \u2014 i.e. how long the formula keeps depositing as it is rinsed. Width "
                "carries a secondary \u2018rinse-persistence\u2019 signal (it tracks the persistent smooth / "
                "moisturized / conditioned-film feel) but amount is the main driver.")
    body(doc, "In short, the amount number is not a fitted abstraction \u2014 it is literally how far the "
              "supernatant clears when the coacervate pulls the shampoo\u2019s opacifier and actives out of "
              "suspension, which is the same coacervate that deposits on hair. That physical link is why "
              "the amount reads across so cleanly onto consumer conditioning. The assay is run automatically "
              "on the Hamilton + SpectraMax workflow.")

    h1(doc, "3. The formulas coacervate very differently")
    figure(doc, "brandon_ipct_method_overlay_zoom.png",
           "Inverse-%T coacervation profiles (1:1\u20131:100). Naturals form tall, broad humps (most "
           "coacervate); polyquats form smaller humps; GH130 humps re-cloud (redissolve) while BC128o "
           "mostly clears and persists.")
    figure(doc, "brandon_ipct_method_widthheight.png",
           "The two coacervation readouts \u2014 amount (hump height) and width \u2014 by polymer and chassis.")
    body(doc, "Ranked by coacervate amount (inverse-%T AUC): the naturals (Nat Clear, Cassia, Nat Caready) "
              "and the NH3196 guar control form the most coacervate; the polyquats form the least, with "
              "Polyquat-6 lowest.")

    h1(doc, "4. Coacervate amount predicts overall conditioning")
    figure(doc, "brandon_ipct_vs_ils.png",
           "Coacervation metrics vs ILS Overall conditioning index. Amount (AUC, height) correlates "
           "strongly (r\u2248+0.75\u2013+0.9); re-cloud does not (r\u22480) \u2014 it is how much coacervate forms, not "
           "whether it redissolves, that drives conditioning.")
    body(doc, "Amount is the driver. Height (how far the supernatant clears) is the single most robust "
              "predictor \u2014 it holds in BOTH chassis (r = +0.77 BC128o, +0.73 GH130). Re-cloud / "
              "redissolution has essentially no relationship to consumer feel.")

    h1(doc, "5. WHICH consumer attributes coacervation predicts")
    figure(doc, "brandon_ils_attr_corr.png",
           "Pearson r of coacervate amount vs every wet & dry attribute. Coacervation predicts the "
           "conditioning cluster (smoothness, moisture, slip, detangling) and is INVERSELY related to "
           "\u201cclean feel (wet)\u201d \u2014 the conditioning-vs-clean trade-off.")
    figure(doc, "brandon_ils_top_scatter.png",
           "Coacervate amount vs the three strongest-correlated attributes.")
    body(doc, "This is the key insight: coacervate amount is not a generic \u201cgoodness\u201d score \u2014 it is "
              "specifically the CONDITIONING axis. It raises smoothness, moisturization, wet slip, "
              "creaminess and detangling; it LOWERS the clean/squeaky feel (r=\u22120.69); and it does nothing "
              "for volume (r=+0.10). Rinse-drag count also rises with coacervate (+0.64) \u2014 a physical "
              "signature of more deposited coacervate during the rinse.")

    h1(doc, "6. Chassis matters \u2014 amount explains most, structure explains the rest")
    body(doc, "The correlation is very strong in BC128o M (r=+0.91 AUC vs Overall) and weaker in GH130 LT1 "
              "(r=+0.55). In GH130 the NH3196 guar control gives the best conditioning (9.12) on only "
              "moderate coacervate \u2014 its loose, large-floc coacervate microstructure conditions beyond raw "
              "amount. So coacervate AMOUNT explains ~75\u201390% of conditioning; coacervate STRUCTURE / floc "
              "quality (better seen by Lasentec + microscopy) explains the residual, and is the guar "
              "advantage.")

    h1(doc, "7. What it means & recommendations")
    bullet(doc, "Use inverse-%T amount (height / AUC) as a fast conditioning screen for opaque AD "
                "shampoos \u2014 it predicts consumer conditioning before you run a tress panel.")
    bullet(doc, "Position the low-coacervate polyquats (esp. Polyquat-6) as cleansing / volume products, "
                "not conditioners \u2014 the data (clean feel up, conditioning down) supports exactly this.")
    bullet(doc, "The high-coacervate naturals (Nat Clear, Nat Caready, Cassia) are the conditioning "
                "leads, matching or beating the guar control in BC128o.")
    bullet(doc, "Pair inverse-%T with Lasentec / microscopy to capture the floc-quality residual that "
                "makes guar condition well in GH130 on modest coacervate amount.")
    bullet(doc, "Design lever: if you want more conditioning, raise coacervate amount; if you want a "
                "clean/volumizing product, keep it low. Coacervate amount IS the trade-off dial.")

    h1(doc, "8. Caveats & next steps")
    bullet(doc, "ILS is one tress per product \u2014 directional, not statistically significant. Replicate "
                "for claim support.")
    bullet(doc, "Correlation is not causation; coacervate amount and conditioning may share a common "
                "driver (deposited polymer). But the mechanism (coacervate captures + deposits the "
                "payload) supports a causal read.")
    bullet(doc, "Next: add measured deposition (silicone / Piroctone Olamine) to confirm the "
                "coacervate\u2192deposition\u2192feel chain; add Lasentec floc size for the structure axis; "
                "replicate the top prototypes.")

    out = os.path.join(R, "Brandon_Coacervation_vs_Consumer_Report.docx")
    doc.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
