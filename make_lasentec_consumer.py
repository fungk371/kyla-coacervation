"""Correlate Lasentec (FBRM) coacervate size with consumer-panel preferences.

FBRM data (1:49 dilution, DI water) comes from make_lasentec_products.load().
Consumer data are top-box (TB) scores from the blind Controls Performance
Overview (90% CL): columns DMR(=Pantene, our), L'Oreal Hya+Plump, Kerastase
Nutritive, Dove Int Repair.

Goal: test which consumer preferences track coacervate floc size / count, to
guide how Pantene (small-particle) can win vs Dove (large-floc) competitors.

Output: Reports/lasentec_consumer_correlation.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from make_lasentec_products import load, PRODUCTS

R = "Reports"

# consumer top-box scores from the slide (order = PRODUCTS order below)
# PRODUCTS order: Pantene M10, Kerastase Nutritive, L'Oreal Hyaluron, Dove
# Re-map to a fixed product order for clarity.
ORDER = ["Pantene M10", "L'Oreal Hyaluron Plump", "Kerastase Nutritive",
         "Dove Intensive Repair"]
COL = {"Pantene M10": "#2E75B6", "L'Oreal Hyaluron Plump": "#27ae60",
       "Kerastase Nutritive": "#8E44AD", "Dove Intensive Repair": "#c0392b"}

CONSUMER = {  # metric -> {product: TB score}
    "Overall system (TB)":      dict(zip(ORDER, [38, 40, 31, 42])),
    "Moisturized (TB)":         dict(zip(ORDER, [40, 38, 25, 42])),
    "No weigh-down (TB)":       dict(zip(ORDER, [37, 35, 28, 43])),
    "Fragrance first-dry":      dict(zip(ORDER, [59, 58, 53, 71])),
    "Fragrance 4-8h just-right": dict(zip(ORDER, [43, 51, 52, 60])),
    "Fragrance 10h just-right": dict(zip(ORDER, [40, 42, 48, 55])),
}


def fbrm_metrics():
    out = {}
    for label, path, col in PRODUCTS:
        d = load(label, path, col)
        m = d["mids"]
        frac30 = d["dist"][m >= 30].sum() / d["dist"].sum() * 100
        peak = m[int(np.argmax(d["dist"]))]
        out[label] = dict(frac30=frac30, peak=peak,
                          sqrwt=np.nanmean(d["sqr"][d["steady"]]))
    return out


def pearson(x, y):
    x, y = np.array(x, float), np.array(y, float)
    if x.std() == 0 or y.std() == 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def main():
    fb = fbrm_metrics()
    frac30 = [fb[p]["frac30"] for p in ORDER]

    fig, ax = plt.subplots(1, 3, figsize=(18, 5.6))

    # Panel 1: %>30um vs fragrance longevity (the clean, monotonic story)
    a = ax[0]
    for metric, mk in [("Fragrance 4-8h just-right", "o"),
                       ("Fragrance 10h just-right", "s")]:
        y = [CONSUMER[metric][p] for p in ORDER]
        r = pearson(frac30, y)
        a.plot(frac30, y, mk, ls="none", ms=11, mfc="none", mec="#333",
               label=f"{metric}  (r={r:+.2f})")
        z = np.polyfit(frac30, y, 1)
        xs = np.linspace(0, 30, 50)
        a.plot(xs, np.polyval(z, xs), "-", color="#888", lw=1, alpha=0.6)
    for p in ORDER:
        a.annotate(p.split()[0], (fb[p]["frac30"],
                   CONSUMER["Fragrance 10h just-right"][p]),
                   color=COL[p], fontsize=9, fontweight="bold",
                   xytext=(4, -2), textcoords="offset points")
    a.set_xlabel("Coacervate floc size  (% FBRM counts > 30 \u00b5m)")
    a.set_ylabel("Fragrance 'just right' (TB)")
    a.set_title("Bigger flocs \u2192 better fragrance longevity", fontweight="bold")
    a.grid(True, ls=":", alpha=0.5); a.legend(fontsize=8.5)

    # Panel 2: %>30um vs no-weigh-down (decoupled by active choice)
    a = ax[1]
    y = [CONSUMER["No weigh-down (TB)"][p] for p in ORDER]
    r = pearson(frac30, y)
    for p in ORDER:
        a.scatter(fb[p]["frac30"], CONSUMER["No weigh-down (TB)"][p],
                  s=140, color=COL[p], zorder=3, label=p.split()[0])
        a.annotate(p.split()[0], (fb[p]["frac30"], CONSUMER["No weigh-down (TB)"][p]),
                   color=COL[p], fontsize=9, fontweight="bold",
                   xytext=(5, 4), textcoords="offset points")
    a.set_xlabel("Coacervate floc size  (% FBRM counts > 30 \u00b5m)")
    a.set_ylabel("No weigh-down (TB)")
    a.set_title(f"Weigh-down NOT set by floc size (r={r:+.2f})\n"
                "Dove: big flocs + lightweight silicone film-former",
                fontweight="bold", fontsize=10)
    a.grid(True, ls=":", alpha=0.5)

    # Panel 3: strategic map -- deposition (floc size) vs feel (no weigh-down),
    # bubble = fragrance longevity. Target = top-right (Dove).
    a = ax[2]
    for p in ORDER:
        s = (CONSUMER["Fragrance 10h just-right"][p]) ** 1.7 * 0.5
        a.scatter(fb[p]["frac30"], CONSUMER["No weigh-down (TB)"][p], s=s,
                  color=COL[p], alpha=0.75, zorder=3, edgecolor="k", lw=0.7)
        a.annotate(p.split()[0], (fb[p]["frac30"], CONSUMER["No weigh-down (TB)"][p]),
                   color=COL[p], fontsize=9, fontweight="bold",
                   xytext=(6, 6), textcoords="offset points")
    # arrow: Pantene -> target (bigger flocs, keep light feel)
    pP = (fb["Pantene M10"]["frac30"], CONSUMER["No weigh-down (TB)"]["Pantene M10"])
    a.annotate("", xy=(24, 44), xytext=pP,
               arrowprops=dict(arrowstyle="->", color="#2E75B6", lw=2))
    a.text(13, 46, "Pantene target:\nbigger flocs +\nlight-feel active",
           color="#2E75B6", fontsize=9, fontweight="bold")
    a.set_xlabel("Coacervate floc size (% counts > 30 \u00b5m)  \u2192 deposition/fragrance")
    a.set_ylabel("No weigh-down (TB)  \u2192 light feel")
    a.set_title("Win map (bubble = fragrance 10h)", fontweight="bold")
    a.grid(True, ls=":", alpha=0.5)
    a.set_xlim(-2, 32); a.set_ylim(25, 48)

    fig.suptitle("Lasentec coacervate size vs consumer preference \u2014 "
                 "how Pantene can win vs Dove / L'Oreal / Kerastase",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/lasentec_consumer_correlation.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/lasentec_consumer_correlation.png")

    # console: correlation table
    print("\nPearson r vs coacervate floc size (% counts > 30 um):")
    for metric in CONSUMER:
        y = [CONSUMER[metric][p] for p in ORDER]
        print(f"  {metric:26s} r = {pearson(frac30, y):+.2f}")
    print("\nFBRM floc size (% > 30 um):")
    for p in ORDER:
        print(f"  {p:26s} {fb[p]['frac30']:5.1f}%   peak {fb[p]['peak']:.1f} um")


if __name__ == "__main__":
    main()
