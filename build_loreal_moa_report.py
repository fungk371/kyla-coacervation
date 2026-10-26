"""Build the L'Oreal vs Pantene MOA report (DOCX) from:
  - Kyla's Lasentec/FBRM store (lasentec_store.json)  [plots generated here]
  - Geoff Reynolds' deposition / PTL data             [values digitized from deck]
  - Amanda Ritter's flow-cell microscopy              [interpreted findings]

Microscopy photos live only in the source deck, not the workspace, so they are
summarized in text; drop the image files in img/ and re-run to embed them.
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

HERE = Path(__file__).parent
OUT_DIR = HERE / "Reports"
IMG_DIR = OUT_DIR / "loreal_moa_assets"
IMG_DIR.mkdir(parents=True, exist_ok=True)
DOCX = OUT_DIR / "Loreal_vs_Pantene_MOA_Report.docx"

NAVY = RGBColor(0x0F, 0x2B, 0x46)
ORANGE = RGBColor(0xE0, 0x6A, 0x2B)
BLUE = "#2E75B6"
RED = "#C0392B"

# ---------------------------------------------------------------- load data
store = json.load(open(HERE / "lasentec_store.json"))
by_name = {r.get("name", ""): r for r in store}


def rec(sub):
    for n, r in by_name.items():
        if sub.lower() in n.lower():
            return r
    raise KeyError(sub)


def mids_of(r):
    m = r.get("metrics", {}).get("mids")
    if m:
        return np.array(m, float)
    # fallback: shared instrument bins from any record that has them
    for rr in store:
        if rr.get("metrics", {}).get("mids"):
            return np.array(rr["metrics"]["mids"], float)
    return np.logspace(0, 3, 100)


def dist_of(r):
    return np.array(r["metrics"]["dist"], float)


loreal_49 = rec("L'Oreal Hyaluron Plump (7gpg, 1:49)")
pantene_m10 = rec("Pantene M10 (7gpg, 1:49)")
loreal_0gpg = rec("L'Oreal Hyaluron Plump (DI water/0gpg, 1:9)")
loreal_7gpg = rec("L'Oreal Hyaluron Plump (7gpg, 1:9)")
pantene_dmr = rec("Pantene DMR")

# ---------------------------------------------------------------- plots
def plot_overlay_matched():
    mids = mids_of(loreal_49)
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    ax.plot(mids, dist_of(loreal_49), "-", color=BLUE, lw=2.4,
            label="L'Oreal Hyaluron Plump")
    ax.plot(mids, dist_of(pantene_m10), "-", color=RED, lw=2.4,
            label="Pantene M10")
    ax.set_xscale("log")
    ax.set_xlabel("Chord length (\u00b5m)")
    ax.set_ylabel("Mean counts / s (steady state)")
    ax.set_title("Chord-length distribution \u2014 matched 7 gpg, 1:49 (raw counts)",
                 fontweight="bold", fontsize=11)
    ax.axvspan(10, 100, color="#f5c57a", alpha=0.25, lw=0,
               label="mid-size 10\u2013100 \u00b5m")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.legend(fontsize=9)
    fig.tight_layout()
    p = IMG_DIR / "overlay_matched.png"
    fig.savefig(p, dpi=150); plt.close(fig)
    return p


def plot_overlay_normalized():
    mids = mids_of(loreal_49)
    lo = dist_of(loreal_49); pa = dist_of(pantene_m10)
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    ax.plot(mids, pa / pa.max(), "-", color=RED, lw=2.4, label="Pantene M10")
    ax.plot(mids, lo / lo.max(), "-", color=BLUE, lw=2.4,
            label="L'Oreal Hyaluron Plump")
    ax.set_xscale("log")
    ax.set_xlabel("Chord length (\u00b5m)")
    ax.set_ylabel("Counts (normalized to peak)")
    ax.set_title("Distribution SHAPE \u2014 matched 7 gpg, 1:49 (peak-normalized)",
                 fontweight="bold", fontsize=11)
    ax.axvspan(10, 100, color="#f5c57a", alpha=0.25, lw=0,
               label="mid-size 10\u2013100 \u00b5m")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.legend(fontsize=9)
    fig.tight_layout()
    p = IMG_DIR / "overlay_normalized.png"
    fig.savefig(p, dpi=150); plt.close(fig)
    return p


def plot_hardness():
    mids = mids_of(loreal_7gpg)
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    ax.plot(mids, dist_of(loreal_0gpg), "-", color="#2E75B6", lw=2.4,
            label="0 gpg (DI water)")
    ax.plot(mids, dist_of(loreal_7gpg), "--", color="#B9770E", lw=2.4,
            label="7 gpg (hard water)")
    ax.set_xscale("log")
    ax.set_xlabel("Chord length (\u00b5m)")
    ax.set_ylabel("Mean counts / s (steady state)")
    ax.set_title("L'Oreal Hyaluron Plump \u2014 hardness series (1:9)",
                 fontweight="bold", fontsize=11)
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.legend(fontsize=9)
    fig.tight_layout()
    p = IMG_DIR / "hardness_series.png"
    fig.savefig(p, dpi=150); plt.close(fig)
    return p


def plot_size_bins():
    cats = ["Fine\n<10 \u00b5m", "Mid\n10\u2013100 \u00b5m", "Coarse\n\u2265100 \u00b5m"]
    lo = [loreal_49["metrics"][k] for k in ("bin_fine", "bin_med", "bin_coarse")]
    pa = [pantene_m10["metrics"][k] for k in ("bin_fine", "bin_med", "bin_coarse")]
    x = np.arange(len(cats)); w = 0.38
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    b1 = ax.bar(x - w / 2, lo, w, color=BLUE, label="L'Oreal Hyaluron Plump")
    b2 = ax.bar(x + w / 2, pa, w, color=RED, label="Pantene M10")
    ax.set_xticks(x); ax.set_xticklabels(cats)
    ax.set_ylabel("Mean counts / s")
    ax.set_title("Coacervate size populations \u2014 matched 7 gpg, 1:49",
                 fontweight="bold", fontsize=11)
    for b in list(b1) + list(b2):
        ax.annotate(f"{b.get_height():.0f}", (b.get_x() + b.get_width() / 2,
                    b.get_height()), ha="center", va="bottom", fontsize=8)
    ax.legend(fontsize=9); ax.grid(True, axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    p = IMG_DIR / "size_bins.png"
    fig.savefig(p, dpi=150); plt.close(fig)
    return p


# Geoff Reynolds' Si deposition (5 cycles) -- values digitized from deck slide 8
SI_DEPO = [
    ("Control", 20, "#7f8c8d"),
    ("L'Oreal SH", 394, BLUE),
    ("Pantene MT-10 SH", 38, RED),
    ("L'Oreal SH + CN", 685, BLUE),
    ("Pantene MT SH\n+ Goldie CN", 183, RED),
    ("Pantene MT SH\n+ L'Oreal CN", 468, "#8e44ad"),
    ("L'Oreal SH\n+ Goldie CN", 170, "#8e44ad"),
]


def plot_si_depo():
    labels = [s[0] for s in SI_DEPO]
    vals = [s[1] for s in SI_DEPO]
    cols = [s[2] for s in SI_DEPO]
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    bars = ax.bar(range(len(vals)), vals, color=cols)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8, rotation=0)
    ax.set_ylabel("Relative Si deposition (a.u.)")
    ax.set_title("Silicone deposition on hair \u2014 5 cycles (Geoff Reynolds, SEM-EDS)",
                 fontweight="bold", fontsize=11)
    for b, v in zip(bars, vals):
        ax.annotate(f"{v}", (b.get_x() + b.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=8, fontweight="bold")
    ax.grid(True, axis="y", ls=":", alpha=0.5)
    fig.text(0.01, 0.01, "Values digitized from deck figure \u2014 relative, not absolute.",
             fontsize=7, color="#666")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    p = IMG_DIR / "si_deposition.png"
    fig.savefig(p, dpi=150); plt.close(fig)
    return p


p_overlay = plot_overlay_matched()
p_overlay_norm = plot_overlay_normalized()
p_hard = plot_hardness()
p_bins = plot_size_bins()
p_si = plot_si_depo()

# ---------------------------------------------------------------- docx helpers
doc = Document()
styles = doc.styles["Normal"]
styles.font.name = "Calibri"
styles.font.size = Pt(10.5)


def h1(t):
    p = doc.add_heading(t, level=1)
    for r in p.runs:
        r.font.color.rgb = NAVY
    return p


def h2(t):
    p = doc.add_heading(t, level=2)
    for r in p.runs:
        r.font.color.rgb = ORANGE
    return p


def para(t, bold=False, italic=False, size=10.5):
    p = doc.add_paragraph()
    r = p.add_run(t); r.bold = bold; r.italic = italic; r.font.size = Pt(size)
    return p


def bullet(t, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        r = p.add_run(bold_lead); r.bold = True
        p.add_run(t)
    else:
        p.add_run(t)
    return p


def add_img(path, width=6.3, caption=None):
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caption:
        c = doc.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = c.add_run(caption); r.italic = True; r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, hd in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(hd); run.bold = True; run.font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v)); run.font.size = Pt(9)
    return t


# ---------------------------------------------------------------- content
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.LEFT
tr = title.add_run("L'Oreal Hyaluron Plump vs. Pantene \u2014 Mechanism-of-Action Review")
tr.bold = True; tr.font.size = Pt(18); tr.font.color.rgb = NAVY
sub = doc.add_paragraph()
sr = sub.add_run("Why L'Oreal is winning: triangulating Lasentec coacervation, "
                 "flow-cell microscopy, and silicone deposition")
sr.italic = True; sr.font.size = Pt(11); sr.font.color.rgb = ORANGE
meta = doc.add_paragraph()
mr = meta.add_run("Data sources: Kyla Fung (Lasentec/FBRM) \u00b7 Amanda Ritter "
                  "(flow-cell microscopy) \u00b7 Geoff Reynolds (SEM-EDS deposition, PTL)  "
                  "| Business Use")
mr.font.size = Pt(8.5); mr.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

# Executive summary
h1("Executive summary")
para("At matched rinse conditions (7 gpg, 1:49 dilution), L'Oreal Hyaluron Plump "
     "shifts its coacervate distribution strongly toward the mid-size band: 41% of "
     "its counts fall in 10\u2013100 \u00b5m vs only 7% for Pantene M10 (a 5.6x higher "
     "SHARE, independent of total counts), and it peaks larger (4.7 vs 3.1 \u00b5m) "
     "with a much heavier tail. In absolute terms it also forms ~11x more total "
     "particles. Those mid-size, silicone-cored, water-rich complexes are retained "
     "on-fiber by flow-cell microscopy (Ritter) and deliver ~4x more silicone to "
     "hair by SEM-EDS (Reynolds). Three independent methods converge on one "
     "mechanism: L'Oreal wins by forming an abundant, hardness-robust coacervate "
     "that deposits and retains more silicone, driving the real sensory signal "
     "\u2014 even though combing/friction (PTL) shows no gap.",
     )

# Section 1 - Lasentec
h1("1. Lasentec / FBRM \u2014 coacervate formation on dilution (Kyla Fung)")
para("FBRM measures chord-length counts as product is diluted into the rinse. "
     "Size bins: fine <10 \u00b5m, mid 10\u2013100 \u00b5m, coarse \u2265100 \u00b5m.",
     italic=True, size=9)

h2("1a. Matched head-to-head (7 gpg, 1:49)")
# shape (fraction) metrics -- robust to run-to-run total-count scaling
lo_d = dist_of(loreal_49); lo_mids = mids_of(loreal_49)
pa_d = dist_of(pantene_m10)
def share(d, mids, lo_, hi_):
    return 100.0 * d[(mids >= lo_) & (mids < hi_)].sum() / d.sum()
lo_med_pct = share(lo_d, lo_mids, 10, 100); pa_med_pct = share(pa_d, lo_mids, 10, 100)
lo_fine_pct = share(lo_d, lo_mids, 0, 10); pa_fine_pct = share(pa_d, lo_mids, 0, 10)

para("Distribution SHAPE (fraction of counts) \u2014 independent of total-count "
     "scaling; this is what the peak-normalized overlay shows:", bold=True, size=9.5)
table(["Shape metric", "L'Oreal Hyaluron Plump", "Pantene M10", "L'Oreal / Pantene"],
      [["Mid-size share (10\u2013100 \u00b5m)", f"{lo_med_pct:.1f}%", f"{pa_med_pct:.1f}%",
        f"{lo_med_pct/pa_med_pct:.1f}x"],
       ["Fine share (<10 \u00b5m)", f"{lo_fine_pct:.1f}%", f"{pa_fine_pct:.1f}%", "\u2014"],
       ["% \u2265 30 \u00b5m", f"{loreal_49['metrics']['frac_gt30']}%",
        f"{pantene_m10['metrics']['frac_gt30']}%",
        f"{loreal_49['metrics']['frac_gt30']/pantene_m10['metrics']['frac_gt30']:.1f}x"],
       ["Peak chord (\u00b5m)", f"{loreal_49['metrics']['peak_um']}",
        f"{pantene_m10['metrics']['peak_um']}", "larger"]])

para("Absolute counts (secondary \u2014 valid only if total counts are comparable; "
     "the ratios below also carry the ~11x total-count difference):", bold=True, size=9.5)
table(["Raw metric", "L'Oreal Hyaluron Plump", "Pantene M10", "Ratio"],
      [["Total counts/s", f"{loreal_49['metrics']['total_counts']:.0f}",
        f"{pantene_m10['metrics']['total_counts']:.0f}",
        f"{loreal_49['metrics']['total_counts']/pantene_m10['metrics']['total_counts']:.1f}x"],
       ["Mid-size counts (10\u2013100 \u00b5m)", f"{loreal_49['metrics']['bin_med']:.0f}",
        f"{pantene_m10['metrics']['bin_med']:.0f}",
        f"{loreal_49['metrics']['bin_med']/pantene_m10['metrics']['bin_med']:.0f}x"],
       ["Fine counts (<10 \u00b5m)", f"{loreal_49['metrics']['bin_fine']:.0f}",
        f"{pantene_m10['metrics']['bin_fine']:.0f}",
        f"{loreal_49['metrics']['bin_fine']/pantene_m10['metrics']['bin_fine']:.1f}x"]])

add_img(p_overlay_norm, caption="Figure 1. Peak-normalized distributions (SHAPE). "
        "L'Oreal's distribution sits higher and broader through the mid-size band "
        "(shaded); Pantene is a narrow fine peak. Robust to total-count scaling.")
add_img(p_overlay, caption="Figure 2. Same data, raw counts \u2014 shows L'Oreal also "
        "forms far more particles in absolute terms.")
add_img(p_bins, caption="Figure 3. Size-binned raw counts.")
para("Interpretation: ", bold=True)
bullet("Robust claim (shape): L'Oreal puts ~5.6x more of its distribution in the "
       "mid-size 10\u2013100 \u00b5m band (41% vs 7%) and peaks larger (4.7 vs 3.1 \u00b5m) "
       "with a heavier \u226530 \u00b5m tail. This holds regardless of total-count "
       "scaling and matches the peak-normalized overlay.")
bullet("Secondary (magnitude): at matched dilution L'Oreal also forms ~11x more "
       "total particles; the 59x raw mid-size figure combines the shape shift with "
       "that total-count difference, so quote it carefully.")
bullet("Pantene's high square-weighted mean (162.8 \u00b5m) is an artifact of very low "
       "counts (a few large chords dominate) \u2014 not a real abundant large-particle "
       "population. Do not over-interpret it.")

h2("1b. Hardness robustness (L'Oreal, 1:9)")
table(["Condition", "Total counts/s", "Mid-size (10\u2013100 \u00b5m)", "Peak (\u00b5m)"],
      [["0 gpg (DI)", f"{loreal_0gpg['metrics']['total_counts']:.0f}",
        f"{loreal_0gpg['metrics']['bin_med']:.0f}", f"{loreal_0gpg['metrics']['peak_um']}"],
       ["7 gpg (hard)", f"{loreal_7gpg['metrics']['total_counts']:.0f}",
        f"{loreal_7gpg['metrics']['bin_med']:.0f}", f"{loreal_7gpg['metrics']['peak_um']}"]])
add_img(p_hard, caption="Figure 3. L'Oreal coacervation is essentially unchanged "
        "from 0 to 7 gpg \u2014 hardness-insensitive.")
para("Interpretation: ", bold=True)
bullet("L'Oreal deposits consistently regardless of water hardness, so it performs "
       "across consumer segments/conditions; Pantene is more hardness- and "
       "dilution-sensitive. This helps explain why the two P&G consumer studies "
       "(2024 L'Oreal superior, 2026 flat) diverged across different segments.")

# Section 2 - Geoff
h1("2. Silicone deposition & PTL (Geoff Reynolds)")
add_img(p_si, caption="Figure 4. Relative silicone deposition after 5 cycles "
        "(digitized from deck). L'Oreal SH+CN deposits far more Si than any "
        "Pantene combination; the SH+CN benefit is additive.")
para("Interpretation: ", bold=True)
bullet("L'Oreal SH+CN deposits ~4x more silicone than the Pantene system; L'Oreal "
       "SH alone deposits ~10x Pantene SH. The two products stack (additive).")
bullet("L'Oreal silicone survives an extra wash (10.5 cycles) \u2014 deposits are "
       "durable and cumulative.")
bullet("PTL / SACS / IFF show no significant friction or combing gap. So L'Oreal "
       "is NOT winning on detangling mechanics \u2014 the win is deposition and sensory.")

# Section 3 - Amanda
h1("3. Flow-cell microscopy & microstructure (Amanda Ritter)")
para("Microscopy images reside in the source deck (BM&I); summarized here. Drop "
     "the image files into Reports/loreal_moa_assets/ and re-run to embed them.",
     italic=True, size=9)
para("Key observations:", bold=True)
bullet("L'Oreal CN forms large complex structures on dilution that are attracted to "
       "hair in the flow cell and remain after rinsing.")
bullet("Those structures are silicone-cored, surrounded by water-rich droplets "
       "(~3\u201320+ \u00b5m) \u2014 consistent with attraction to damaged (anionic) hair.")
bullet("L'Oreal SH contains EGDS sheets with silicone associated (primes the fiber); "
       "L'Oreal CN shows large, well-formed lamellar regions and oil-rich droplets.")
bullet("On dilution the conditioner's lamellar order is lost (fatty-alcohol sheets, "
       "no longer lamellar per SAXS) with Si droplets near the sheets.")
para("Interpretation: ", bold=True)
bullet("The flow cell shows on-fiber RETENTION of exactly the mid-size structures "
       "Lasentec quantifies in bulk \u2014 and they carry the silicone Geoff measures.")

# Section 4 - triangulation
h1("4. Triangulation \u2014 one mechanism, three methods")
table(["Method (owner)", "What it measures", "Finding"],
      [["Lasentec/FBRM (Fung)", "Coacervate formation on dilution",
        "~5.6x higher mid-size share (41% vs 7%), ~11x more total; hardness-robust"],
       ["Flow cell (Ritter)", "On-fiber structure retention",
        "Large Si-cored complexes retained after rinse"],
       ["SEM-EDS (Reynolds)", "Deposited silicone payload",
        "~4x more Si; additive SH+CN; survives extra wash"]])
para("The mid-size population (Lasentec) = the on-fiber complexes (microscopy) = the "
     "silicone carrier (deposition). The methods independently converge.", bold=True)

# Section 5 - hypotheses
h1("5. Hypotheses \u2014 why L'Oreal is winning")
for lead, body in [
    ("H1 \u2014 Dilution-triggered coacervate is the delivery vehicle. ",
     "On rinse dilution L'Oreal shifts strongly to mid-size, silicone-cored "
     "complexes (~5.6x higher mid-size share, 41% vs 7%; ~11x more in absolute "
     "counts) that deposit ~4x more silicone (Reynolds). Pantene lacks the carrier, "
     "so it deposits little."),
    ("H2 \u2014 Two-step prime-then-deliver system. ",
     "L'Oreal SH (EGDS sheets + Si) primes the fiber; the CN delivers lamellar/"
     "oil-rich silicone droplets. Deposition is additive; the system wins, not one "
     "product."),
    ("H3 \u2014 Hardness-robust deposition wins across segments. ",
     "Coacervation is unchanged 0\u21927 gpg (Lasentec). L'Oreal delivers "
     "consistently across water conditions while Pantene falls off at high "
     "dilution/hardness \u2014 explaining the divergent consumer studies."),
    ("H4 \u2014 The win is sensory, not mechanical. ",
     "PTL shows no friction gap. The abundant mid-size coacervate + thick silicone "
     "film is the physical substrate for the 'intense hydration / lightweight / "
     "smooth / pleasant scent' perception consumers report."),
    ("H5 \u2014 Durable, cumulative deposits (double-edged). ",
     "Si survives an extra wash and builds over cycles \u2014 driving lasting feel "
     "and loyalty, but also the minority 'sticky film / buildup / weighed-down' "
     "complaint, consistent with amodimethicone thick deposits contradicting its "
     "'resists buildup' claim."),
]:
    bullet(body, bold_lead=lead)

# Section 6 - caveats
h1("6. Caveats")
bullet("FBRM measures chord length, not true particle size; counts are relative and "
       "dilution-dependent. The matched 1:49 comparison is the fair one.")
bullet("Pantene's high square-weighted mean is a low-count artifact, not large "
       "coacervate.")
bullet("Geoff's deposition values here are digitized from the deck figure "
       "(relative, not absolute).")
bullet("Microscopy images are summarized, not embedded (files not in workspace).")
bullet("Lasentec is an in-vitro bulk proxy; its strength is agreement with on-fiber "
       "microscopy and actual Si deposition.")

# Section 7 - next work
h1("7. Recommended next work")
bullet("Screen Pantene prototypes engineered to form an abundant, hardness-robust "
       "mid-size (10\u2013100 \u00b5m) coacervate that is retained on-fiber.")
bullet("Use Lasentec mid-size count + hardness-insensitivity as the fast screening "
       "readout before committing to SEM / flow-cell / deposition.")
bullet("Resolve why high Si deposition does not register in PTL (sensory vs. "
       "friction decoupling).")

doc.save(str(DOCX))
print("WROTE", DOCX)
print("assets:", IMG_DIR)
