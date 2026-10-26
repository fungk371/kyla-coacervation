"""Brandon inverse-%T FINGERPRINTS in the reference (centrifuged, peak-up) convention.

Coacervation = %T hump UP (coacervate captures opacifier + sediments it ->
supernatant clears). Full dilution range kept (redissolution can be late).

Per formula we report:
  floor      opaque %T at concentrated (base opacity, no coacervate yet)
  onset      1:X where %T lifts off the floor (coacervation begins)
  peak       max %T and its 1:X (max clearing = max opacifier captured)
  redis      1:X where %T falls back (coacervate redissolves, opacifier released)
  redis dep  peak%T - post-peak min %T  (re-cloud depth = coacervate-specific)
  width      decades onset -> redissolution (coacervate-forming window)
  AUC        area of the hump above floor over log-dilution (total phase sep)

Outputs:
  Reports/brandon_ipct_reference_overlay.png   (2 panels by chassis)
  Reports/brandon_ipct_amount_bars.png         (AUC by polymer x chassis)
  Reports/brandon_ipct_fingerprint_table.png   (numeric table)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

import coacervation_lasentec as clas
from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio, transmittance_to_absorbance
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis
from make_gh130_pq_new import parse_softmax_matrix
from scipy.signal import find_peaks

R = "Reports"
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


def _find(cands):
    return next((p for p in cands if os.path.exists(p)), cands[0])


def _is_matrix(path):
    """SoftMax 'matrix' export (UTF-16, 8x12 blocks) vs standard wide (Time\t...) export."""
    raw = open(path, "rb").read()
    if raw[:2] == b"\xff\xfe":
        text = raw.decode("utf-16")
    elif raw[:3] == b"\xef\xbb\xbf":
        text = raw.decode("utf-8-sig")
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
    return not any(ln.startswith("Time\t") for ln in text.splitlines()[:60])


def _load_df(path):
    if _is_matrix(path):
        return annotate_concentration(parse_softmax_matrix(path))
    return annotate_concentration(parse_kinetic_plate_file(path))


F_BC_CTRL = _find([r"raw_data\BC128o_3196_NatCaready_200uL.txt"])
F_BC_PQ0622 = _find([r"raw_data\BC128oPQ6_PQ22.txt"])
F_BC_PQ4753 = _find([r"raw_data\BC128oPQ47_PQ53.txt"])
F_BC_CASNC = _find([r"raw_data\BC128o_Cassia_NatClear.txt"])
F_GH_CTRL = _find([r"raw_data\Opaque_GH130_3196_and_Nat_Caready.txt"])
F_GH_CASNC = _find([r"raw_data\GH130_Cassia_NatClear_200uL.txt"])
F_GH_PQ0622 = _find([r"raw_data\GH130_PQ6_PQ22.txt"])
F_GH_PQ4753 = _find([r"raw_data\GH130_PQ47_PQ53.txt"])

POLY_ORDER = ["NH3196", "Polyquat-6", "Polyquat-22", "Polyquat-47", "Polyquat-53",
              "Cassia", "Nat Clear", "Nat Caready"]
CH_COL = {"BC128o M": "#2E75B6", "GH130 LT1": "#16a085"}
CH_MARK = {"BC128o M": "o", "GH130 LT1": "s"}
# highly distinct palette (no two look-alike hues — the two greens are gone)
POLY_COL = {"NH3196": "#7f7f7f",        # gray
            "Polyquat-6": "#1f77b4",     # blue
            "Polyquat-22": "#d62728",    # red
            "Polyquat-47": "#ff7f0e",    # orange
            "Polyquat-53": "#9467bd",    # purple
            "Cassia": "#2ca02c",         # green
            "Nat Clear": "#e377c2",      # pink
            "Nat Caready": "#8c564b"}    # brown
# (polymer, chassis, file, trough)
SAMPLES = [
    ("NH3196", "BC128o M", F_BC_CTRL, 1),
    ("Polyquat-6", "BC128o M", F_BC_PQ0622, 1),
    ("Polyquat-22", "BC128o M", F_BC_PQ0622, 2),
    ("Polyquat-47", "BC128o M", F_BC_PQ4753, 1),
    ("Polyquat-53", "BC128o M", F_BC_PQ4753, 2),
    ("Cassia", "BC128o M", F_BC_CASNC, 1),
    ("Nat Clear", "BC128o M", F_BC_CASNC, 2),
    ("Nat Caready", "BC128o M", F_BC_CTRL, 2),
    ("NH3196", "GH130 LT1", F_GH_CTRL, 1),
    ("Polyquat-6", "GH130 LT1", F_GH_PQ0622, 1),
    ("Polyquat-22", "GH130 LT1", F_GH_PQ0622, 2),
    ("Polyquat-47", "GH130 LT1", F_GH_PQ4753, 1),
    ("Polyquat-53", "GH130 LT1", F_GH_PQ4753, 2),
    ("Cassia", "GH130 LT1", F_GH_CASNC, 1),
    ("Nat Clear", "GH130 LT1", F_GH_CASNC, 2),
    ("Nat Caready", "GH130 LT1", F_GH_CTRL, 2),
]


def curve(path, trough, tp=0):
    df = _load_df(path)
    t = min(sorted(df["timepoint_minutes"].unique()), key=lambda z: abs(z - tp))
    sel = df[(df["trough"] == trough) & (df["timepoint_minutes"] == t)].dropna(
        subset=["formula_fraction"]).sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(sel["formula_fraction"].to_numpy(float)), float)
    y = sel["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def _recloud_from_curve(fx, fy, floor):
    """Re-cloud across the WHOLE dilution range.

    An inverse-%T curve can clear TWICE: once because the coacervate captures
    the opacifier (the hump we want) and again at extreme dilution because pure
    dilution thins everything out. The physically meaningful re-cloud is the
    interior %T TROUGH between those two — coacervate redissolving and releasing
    the opacifier. We find interior local minima, take the deepest one relative
    to the clearing peak that PRECEDES it (so the pure-dilution clear tail is
    ignored), and report depth = clearing-peak %T - trough %T.

    Returns (peak_dil, peak_pct, redis_dil, redis_depth).
    """
    n = len(fy)
    span = float(np.nanmax(fy) - floor) or 1.0
    troughs, _ = find_peaks(-fy, prominence=max(2.0, 0.04 * span), distance=3)
    troughs = [int(t) for t in troughs if 2 <= t <= n - 3]
    if not troughs:
        pi = int(np.argmax(fy))       # monotone / plateau: no re-cloud
        return float(fx[pi]), float(fy[pi]), None, 0.0
    ti = max(troughs, key=lambda t: float(fy[:t + 1].max() - fy[t]))
    pi = int(np.argmax(fy[:ti + 1]))  # clearing peak BEFORE the trough
    return float(fx[pi]), float(fy[pi]), float(fx[ti]), max(0.0, float(fy[pi] - fy[ti]))


def fingerprint(path, trough):
    """Metrics for an inverse-%T clearing curve, defined for EVERY sample.

    The %T rise IS the coacervation signal (coacervate captures + sediments the
    opacifier so the supernatant clears). We report, from the smoothed curve:
      floor   opaque %T at the concentrated end
      onset   1:X where %T lifts off the floor (phase separation begins)
      height  peak clearing above the floor  = relative AMOUNT of coacervate
      width   decades of dilution where %T >= half-max clearing = breadth of
              the phase-separation region (FWHM-style; defined for all curves)
      auc     integral area under the clearing curve above the floor over
              log-dilution (onset -> end) = ranking metric for coacervate formation
      recloud secondary: depth of the interior re-cloud trough (redissolution)
    """
    x, y = curve(path, trough)
    cx, cy, _ = clean_curve(x, y)
    fx, fy = smooth_hybrid(cx, cy)
    u = np.log10(fx)
    k = max(3, len(fy) // 10)
    floor = float(np.min(fy[:k]))
    amp = float(np.max(fy) - floor) or 1.0
    peak_i = int(np.argmax(fy))
    peak_pct = float(fy[peak_i]); peak_dil = float(fx[peak_i])
    height = max(0.0, peak_pct - floor)
    thr15 = floor + 0.15 * amp
    onset_i = next((i for i in range(len(fy)) if fy[i] >= thr15), 0)
    onset_dil = float(fx[onset_i])
    half = floor + 0.5 * amp
    ab = np.where(fy >= half)[0]
    if len(ab):
        w_lo, w_hi = float(fx[ab[0]]), float(fx[ab[-1]])
        width = float(np.log10(w_hi / w_lo)) if w_hi > w_lo else 0.0
    else:
        w_lo = w_hi = onset_dil; width = 0.0
    seg = slice(onset_i, len(fy))
    auc = float(_trapz(np.clip(fy[seg] - floor, 0, None), u[seg]))
    _pd, _pp, redis_dil, redis_depth = _recloud_from_curve(fx, fy, floor)
    return dict(rawx=x, rawy=y, fx=fx, fy=fy, cx=cx, floor=floor,
                onset=onset_dil, peak_pct=peak_pct, peak_dil=peak_dil,
                height=height, width=width, w_lo=w_lo, w_hi=w_hi,
                auc=auc, redis_dil=redis_dil, redis_depth=redis_depth)


def main():
    results = {}
    for poly, ch, path, tr in SAMPLES:
        results[(poly, ch)] = fingerprint(path, tr)

    # ---------- 1) overlay by chassis (clean smooth lines) ----------
    fig, axes = plt.subplots(1, 2, figsize=(17, 6.6))
    for ax, ch in zip(axes, ["BC128o M", "GH130 LT1"]):
        lo, hi = [], []
        for poly in POLY_ORDER:
            if (poly, ch) not in results:
                continue
            r = results[(poly, ch)]
            ax.plot(r["fx"], r["fy"], "-", color=POLY_COL[poly], lw=2.4, label=poly)
            lo.append(r["cx"].min()); hi.append(r["cx"].max())
        if lo:
            _dil_axis(ax, min(lo), max(hi), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (Water:Shampoo, 1:X)  \u2014  rinse \u2192")
        ax.set_ylabel("%T (centrifuged supernatant)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(f"{ch} chassis", fontweight="bold")
        ax.legend(fontsize=8.5, ncol=2)
    fig.suptitle("Brandon inverse %T \u2014 reference convention (centrifuged supernatant, "
                 "coacervation = %T hump up)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/brandon_ipct_reference_overlay.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_reference_overlay.png")

    # ---------- 1b) overlay WITH raw data points + smooth line ----------
    fig, axes = plt.subplots(1, 2, figsize=(17, 6.6))
    for ax, ch in zip(axes, ["BC128o M", "GH130 LT1"]):
        lo, hi = [], []
        for poly in POLY_ORDER:
            if (poly, ch) not in results:
                continue
            r = results[(poly, ch)]
            ax.plot(r["rawx"], r["rawy"], "o", color=POLY_COL[poly], ms=3.0, alpha=0.30)
            ax.plot(r["fx"], r["fy"], "-", color=POLY_COL[poly], lw=2.2, label=poly)
            lo.append(r["cx"].min()); hi.append(r["cx"].max())
        if lo:
            _dil_axis(ax, min(lo), max(hi), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (Water:Shampoo, 1:X)  \u2014  rinse \u2192")
        ax.set_ylabel("%T (centrifuged supernatant)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(f"{ch} chassis", fontweight="bold")
        ax.legend(fontsize=8.5, ncol=2)
    fig.suptitle("Brandon inverse %T \u2014 raw well readings (dots) + smoothed fit (line)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/brandon_ipct_overlay_raw.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_overlay_raw.png")

    # ---------- 2) AUC ranking: integral area = coacervate formation ----------
    ranked = sorted(results.items(), key=lambda kv: -(kv[1]["auc"] or 0))
    labels = [f"{p}  ({ch.split()[0]})" for (p, ch), _ in ranked]
    vals = [r["auc"] for _, r in ranked]
    cols = [CH_COL[ch] for (p, ch), _ in ranked]
    fig, ax = plt.subplots(figsize=(11, 8))
    ypos = np.arange(len(ranked))[::-1]
    ax.barh(ypos, vals, color=cols, edgecolor="white")
    for yp, v in zip(ypos, vals):
        ax.text(v + 1, yp, f"{v:.0f}", va="center", fontsize=8)
    ax.set_yticks(ypos); ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Inverse-%T AUC  =  integral area under the clearing curve  (%T \u00d7 decades)")
    ax.set_title("Rank order of coacervate formation \u2014 integral area under the dilution curve\n"
                 "(reference method: area under the phase-separation hump ranks the polymers)",
                 fontweight="bold", fontsize=11)
    handles = [plt.Line2D([0], [0], marker="s", ls="", mfc=CH_COL[c], mec="none",
                          ms=10, label=c) for c in ["BC128o M", "GH130 LT1"]]
    ax.legend(handles=handles, fontsize=9, loc="lower right")
    ax.grid(True, axis="x", ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(f"{R}/brandon_ipct_auc_rank.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_auc_rank.png")

    # ---------- 2b) same polymer, both chassis: HEIGHT / WIDTH / AUC ----------
    fig, axes = plt.subplots(1, 3, figsize=(17.5, 5.8))
    xp = np.arange(len(POLY_ORDER)); w = 0.4
    for ax, key, ylab, ttl in [
        (axes[0], "height", "Peak clearing height (%T above floor)",
         "HEIGHT \u2014 relative amount of coacervate"),
        (axes[1], "width", "Phase-separation width (decades, FWHM)",
         "WIDTH \u2014 breadth of the coacervation region"),
        (axes[2], "auc", "AUC (%T \u00d7 decades)",
         "AUC \u2014 total coacervate formation (ranking)"),
    ]:
        for kk, ch in enumerate(["BC128o M", "GH130 LT1"]):
            vv = [float(results[(p, ch)].get(key) or 0.0) if (p, ch) in results else 0.0
                  for p in POLY_ORDER]
            ax.bar(xp + (kk - 0.5) * w, vv, w, color=CH_COL[ch],
                   edgecolor="white", label=ch)
            for i, v in enumerate(vv):
                if v:
                    ax.text(i + (kk - 0.5) * w, v, f"{v:.0f}" if key != "width"
                            else f"{v:.1f}", ha="center", va="bottom", fontsize=6.5)
        ax.set_xticks(xp); ax.set_xticklabels(POLY_ORDER, rotation=30, ha="right", fontsize=8)
        ax.set_ylabel(ylab, fontsize=9)
        ax.set_title(ttl, fontweight="bold", fontsize=10)
        ax.grid(True, axis="y", ls=":", alpha=0.5); ax.legend(fontsize=8)
    fig.suptitle("Same polymer, both chassis \u2014 compare HEIGHT, WIDTH & AUC (inverse %T, t=0)",
                 fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/brandon_ipct_chassis_compare.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_chassis_compare.png")

    # ---------- 2c) width vs height shape map (every sample) ----------
    fig, ax = plt.subplots(figsize=(11, 7))
    for poly, ch, _p, _t in SAMPLES:
        r = results[(poly, ch)]
        wdt, hgt = r.get("width"), r.get("height")
        if wdt is None or hgt is None:
            continue
        sz = 60 + 6.0 * float(r.get("auc") or 0)
        ax.scatter(wdt, hgt, s=sz, color=POLY_COL[poly], marker=CH_MARK[ch],
                   edgecolor="#333", linewidth=0.8, alpha=0.9, zorder=3)
        ax.annotate(f"{poly}\n({ch.split()[0]})", (wdt, hgt), fontsize=7.5,
                    xytext=(5, 4), textcoords="offset points")
    ax.set_xlabel("Phase-separation WIDTH  (decades of dilution at half-max clearing)")
    ax.set_ylabel("HEIGHT of clearing  (peak %T above opaque floor = amount)")
    ax.set_title("Inverse-%T shape map \u2014 WIDTH (dilution breadth) vs HEIGHT (amount)\n"
                 "bubble size \u221d AUC   |   \u25cf BC128o M   \u25a0 GH130 LT1",
                 fontweight="bold", fontsize=11)
    ax.grid(True, ls=":", alpha=0.5)
    handles = [plt.Line2D([0], [0], marker="o", ls="", mfc=POLY_COL[p], mec="#333",
                          ms=9, label=p) for p in POLY_ORDER]
    ax.legend(handles=handles, fontsize=8.5, ncol=2, title="Polymer")
    fig.tight_layout()
    fig.savefig(f"{R}/brandon_ipct_width_height.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_width_height.png")

    # ---------- 3) numeric fingerprint table ----------
    headers = ["Polymer", "Chassis", "Floor", "Onset", "Height (%T)",
               "Peak @1:X", "Width(dec)", "AUC", "Re-cloud"]
    rows = []
    for poly, ch, _p, _t in SAMPLES:
        r = results[(poly, ch)]
        rows.append([
            poly, ch,
            f"{r['floor']:.0f}",
            f"1:{r['onset']:.1f}" if r['onset'] else "-",
            f"{r['height']:.0f}",
            f"1:{r['peak_dil']:.0f}",
            f"{r['width']:.2f}",
            f"{r['auc']:.0f}",
            f"{r['redis_depth']:.0f}" if r['redis_depth'] else "\u2013",
        ])
    fig, ax = plt.subplots(figsize=(14, 0.5 * len(rows) + 1.2))
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=headers, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1, 1.5)
    for j in range(len(headers)):
        tbl[0, j].set_facecolor("#1F4E78"); tbl[0, j].set_text_props(color="white", fontweight="bold")
    for i, (poly, ch, _p, _t) in enumerate(SAMPLES, start=1):
        tbl[i, 1].set_facecolor("#eaf3ff" if ch == "BC128o M" else "#e6f6f0")
    ax.set_title("Coacervate fingerprint \u2014 Brandon inverse %T (t=0)  "
                 "|  Height = amount, Width = breadth, AUC = ranking",
                 fontweight="bold", fontsize=12, pad=14)
    fig.tight_layout()
    fig.savefig(f"{R}/brandon_ipct_fingerprint_table.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {R}/brandon_ipct_fingerprint_table.png\n")

    print(f"{'polymer':13s} {'chassis':10s} {'floor':>5s} {'onset':>7s} "
          f"{'height':>6s} {'peak@':>8s} {'width':>6s} {'AUC':>6s} {'recloud':>7s}")
    for (poly, ch), r in ranked:
        floor = f"{r['floor']:.0f}"
        onset = f"1:{r['onset']:.1f}" if r['onset'] else "-"
        peak = f"1:{r['peak_dil']:.0f}"
        recloud = f"{r['redis_depth']:.0f}" if r['redis_depth'] else "-"
        print(f"{poly:13s} {ch:10s} {floor:>5s} {onset:>7s} {r['height']:6.0f} "
              f"{peak:>8s} {r['width']:6.2f} {r['auc']:6.0f} {recloud:>7s}")


if __name__ == "__main__":
    main()
