"""Build a %T coacervation-AUC ranking for the 16-leg Polyquat/Natural screen.

AUC values pulled from the app's /samples (consumer-window AUC). T1/T2 in the
combined run files are mapped to polymers by filename order. Opaque chassis
(BC128o, GH130) use the inverse-%T method, so AUC is a relative coacervation
index within this screen. Two '_TEST' duplicate runs are excluded.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# (chassis, polymer, consumer-window AUC)
DATA = [
    ("BC128o", "NH3196 (control)", 0.444),
    ("BC128o", "Polyquat-6", 0.451),
    ("BC128o", "Polyquat-22", 0.755),
    ("BC128o", "Polyquat-47", 0.438),
    ("BC128o", "Polyquat-53", 0.291),
    ("BC128o", "Cassia", 0.288),
    ("BC128o", "Nat Clear", 0.365),
    ("BC128o", "Nat Caready", 0.548),
    ("GH130", "NH3196 (control)", 0.561),
    ("GH130", "Cassia", 0.366),
    ("GH130", "Nat Clear", 0.452),
    ("GH130", "Nat Caready", 0.603),
]
COLOR = {"BC128o": "#2E75B6", "GH130": "#2E9E5B"}

rows = sorted(DATA, key=lambda r: r[2])
labels = [f"{p}  ({c})" for c, p, _ in rows]
vals = [v for _, _, v in rows]
colors = [COLOR[c] for c, _, _ in rows]

fig, ax = plt.subplots(figsize=(10.5, 6.2), dpi=150)
y = range(len(vals))
ax.barh(list(y), vals, color=colors, edgecolor="white", height=0.78)
ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=10)
ax.set_xlabel("Consumer-window coacervation AUC  (higher = more coacervate)",
              fontsize=10)
ax.set_xlim(0, max(vals) * 1.15)
for i, v in zip(y, vals):
    ax.text(v + 0.008, i, f"{v:.3f}", va="center", fontsize=9, color="#1E2A36")
ax.set_title("%T coacervation ranking \u2014 16-leg Polyquat / Natural screen\n"
             "0.25% active, 2 chassis (opaque, inverse-%T)",
             fontsize=12.5, fontweight="bold", color="#00266A")
handles = [plt.Rectangle((0, 0), 1, 1, color=COLOR[c]) for c in COLOR]
ax.legend(handles, COLOR.keys(), title="Chassis", fontsize=9,
          title_fontsize=9.5, loc="lower right", frameon=True)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", color="#E6EAF0", linewidth=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
out = os.path.join("Reports", "coac_ranking_16leg_pctT.png")
os.makedirs("Reports", exist_ok=True)
fig.savefig(out, bbox_inches="tight")
print("saved", out)
