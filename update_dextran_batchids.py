"""One-off: write Nexus Batch IDs onto the 0.4% / 1% dextran %T records in
intake_store.json, matched by (co-surfactant, polymer concentration, polymer).
Backs up the store first. Safe to re-run.
"""
import json
import re
import shutil

USER = """
B-20260722-01427 GH150 EED0 + 0.4% 3196
B-20260722-01428 GH150 EED0 + 0.4% CD2
B-20260722-01444 GH150 EED0 + 0.4% Dex-A
B-20260722-01438 GH150 EED0 + 0.4% Dex-B
B-20260722-01439 GH150 EED0 + 0.4% Dex-B*
B-20260722-01441 GH150 EED0 + 0.4% Dex-J
B-20260722-01443 GH150 EED0 + 0.4% Dex-J*
B-20260722-01445 GH150 EED0 + 0.4% Dex-K
B-20260722-01446 GH150 DDU0 + 3.6% APG + 0.4% 3196
B-20260722-01448 GH150 DDU0 + 3.6% APG + 0.4% CD2
B-20260722-01464 GH150 DDU0 + 3.6% APG + 0.4% Dex-A
B-20260722-01449 GH150 DDU0 + 3.6% APG + 0.4% Dex-B
B-20260722-01451 GH150 DDU0 + 3.6% APG + 0.4% Dex-B*
B-20260722-01452 GH150 DDU0 + 3.6% APG + 0.4% Dex-J
B-20260722-01463 GH150 DDU0 + 3.6% APG + 0.4% Dex-J*
B-20260722-01466 GH150 DDU0 + 3.6% APG + 0.4% Dex-K
B-20260722-01468 GH150 DDU0 + 3.6% LAPB + 0.4% 3196
B-20260722-01487 GH150 DDU0 + 3.6% LAPB + 0.4% CD2
B-20260722-01495 GH150 DDU0 + 3.6% LAPB + 0.4% Dex-A
B-20260722-01489 GH150 DDU0 + 3.6% LAPB + 0.4% Dex-B
B-20260722-01490 GH150 DDU0 + 3.6% LAPB + 0.4% Dex-B*
B-20260722-01491 GH150 DDU0 + 3.6% LAPB + 0.4% Dex-J
B-20260722-01494 GH150 DDU0 + 3.6% LAPB + 0.4% Dex-J*
B-20260722-01497 GH150 DDU0 + 3.6% LAPB + 0.4% Dex-K
B-20260826-00805 GH150 DDU0 + 3.6% APG + 1% CD2
B-20260826-00809 GH150 DDU0 + 3.6% APG + 1% Dex-B
B-20260826-00810 GH150 DDU0 + 3.6% APG + 1% Dex-B*
B-20260826-00818 GH150 DDU0 + 3.6% APG + 1% Dex-J
B-20260826-00819 GH150 DDU0 + 3.6% APG + 1% Dex-J*
B-20260826-00820 GH150 DDU0 + 3.6% APG + 1% Dex-A
B-20260831-00842 GH150 DDU0 + 3.6% APG + 1% Dex-K
B-20260824-01539 GH150 EED0 + 1% CD2
B-20260824-01540 GH150 EED0 + 1% Dex-B
B-20260825-00902 GH150 EED0 + 1% Dex-B*
B-20260825-00904 GH150 EED0 + 1% Dex-J
B-20260825-00907 GH150 EED0 + 1% Dex-J*
B-20260825-00920 GH150 EED0 + 1% Dex-A
B-20260825-00982 GH150 EED0 + 1% Dex-K
B-20260831-00627 GH150 DDU0 + 3.6% LAPB + 1% Dex-B*
B-20260831-00633 GH150 DDU0 + 3.6% LAPB + 1% Dex-J
B-20260831-00619 GH150 DDU0 + 3.6% LAPB + 1% CD2
B-20260831-00620 GH150 DDU0 + 3.6% LAPB + 1% Dex-B
B-20260831-00634 GH150 DDU0 + 3.6% LAPB + 1% Dex-J*
B-20260831-00637 GH150 DDU0 + 3.6% LAPB + 1% Dex-A
B-20260831-00638 GH150 DDU0 + 3.6% LAPB + 1% Dex-K
"""


def key(name):
    n = name.lower()
    cosurf = "LAPB" if "lapb" in n else ("APG" if "apg" in n else "EED0")
    conc = "0.4" if "0.4%" in n else ("1" if re.search(r"1\s*%|1percent", n) else "?")
    if "3196" in n:
        pol = "3196"
    elif "cd2" in n:
        pol = "CD2"
    else:
        m = re.search(r"dex[\s\-]*([abjk])\s*(\*?)", n)
        pol = ("DEX" + m.group(1).upper() + ("*" if m.group(2) else "")) if m else "?"
    return (cosurf, conc, pol)


umap = {}
for line in USER.strip().splitlines():
    m = re.match(r"^(B-\d{8}-\d{5})\s+(.+)$", line.strip())
    if m:
        umap[key(m.group(2))] = (m.group(1), m.group(2).strip())

s = json.load(open("intake_store.json", encoding="utf-8"))
pat = re.compile(r"dex|cd2|3196", re.I)
matched, skipped, nokey = [], [], []
for pk, troughs in s.items():
    for tk, rec in troughs.items():
        nm = rec.get("name") or rec.get("description") or ""
        if not pat.search(nm):
            continue
        if "no salt" in nm.lower():
            skipped.append((nm, "variant (No Salt) - not in list"))
            continue
        k = key(nm)
        if k in umap:
            bid, desc = umap[k]
            rec["batch_id"] = bid
            matched.append((nm, bid))
        else:
            nokey.append((nm, k))

print(f"MATCHED {len(matched)}:")
for nm, bid in sorted(matched, key=lambda x: x[1]):
    print(f"  {bid}  <-  {nm}")
if skipped:
    print(f"\nSKIPPED {len(skipped)} (left blank):")
    for nm, why in skipped:
        print(f"  {nm}  ({why})")
if nokey:
    print(f"\nNO MATCH IN LIST {len(nokey)}:")
    for nm, k in nokey:
        print(f"  {nm}  key={k}")

listed_no_record = sorted(set(umap) - {key(nm) for nm, _ in matched})
if listed_no_record:
    print(f"\nLISTED BATCHES WITH NO %T RECORD YET {len(listed_no_record)}:")
    for k in listed_no_record:
        print(f"  {umap[k][0]}  {umap[k][1]}")

shutil.copy("intake_store.json", "intake_store.backup.json")
json.dump(s, open("intake_store.json", "w", encoding="utf-8"), indent=2)
print("\nsaved intake_store.json (backup: intake_store.backup.json)")
