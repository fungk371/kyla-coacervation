"""Decode the BC128 shampoo naming convention into composition.

Format (e.g. "BC128o MN2508"):
  <ChassisLetter><PolymerLetter><2-digit polymer level><2-digit silicone level>
  + a trailing active letter on the BC128 prefix ('o'/'z').

  ChassisLetter  M = 8% SLE3S, 7% SLS, 2.0% CAPB
  PolymerLetter  N = NHance 3196 Guar
  Polymer level  2 digits, polymer-specific lookup (guar "25" = 0.23%)
  Silicone level 2 digits, "08" = 0.8% Wacker DM5500 dimethicone/dimethiconol 150nm
  Active suffix  'o' = Piroctone Olamine, 'z' = ZPT AD active

Unknown codes are returned as raw codes with the % left as None so nothing is
fabricated. Extend the lookup tables as more codes are confirmed.
"""
import re

CHASSIS = {
    "M": {"label": "M chassis", "surfactant": "8% SLE3S, 7% SLS, 2.0% CAPB"},
}
POLYMER = {
    "N": "NHance 3196 Guar",
}
# polymer-level 2-digit code -> % actives, keyed by polymer letter
POLYMER_LEVEL = {
    "N": {"25": 0.23},
}
SILICONE = {
    "08": {"pct": 0.8, "material": "Wacker DM5500 dimethicone/dimethiconol 150nm emulsion"},
}
ACTIVE = {"o": "Piroctone Olamine", "z": "ZPT"}


def parse_bc128_name(name: str) -> dict:
    """Best-effort decode of a BC128 sample name -> composition dict."""
    s = str(name or "")
    out = {"raw": s, "chassis": None, "surfactant": None, "polymer": None,
           "polymer_pct": None, "polymer_level_code": None, "silicone": None,
           "silicone_pct": None, "silicone_level_code": None, "active": None,
           "perfume_pct": None, "notes": []}

    # anti-dandruff active carried on the BC128 prefix (BC128o / BC128z)
    m_prefix = re.search(r"BC128\s*([oz])", s, re.I)
    if m_prefix:
        out["active"] = ACTIVE.get(m_prefix.group(1).lower())

    # core code: <Chassis><Polymer><2 polymer-level><2 silicone-level>, e.g. MN2508
    m = re.search(r"\b([A-Z])([A-Z])(\d{2})(\d{2})\b", s)
    if m:
        ch, poly, plev, slev = m.groups()
        out["chassis"] = CHASSIS.get(ch, {}).get("label") or ch
        out["surfactant"] = CHASSIS.get(ch, {}).get("surfactant")
        out["polymer"] = POLYMER.get(poly, poly)
        out["polymer_level_code"] = plev
        out["polymer_pct"] = POLYMER_LEVEL.get(poly, {}).get(plev)
        out["silicone_level_code"] = slev
        sil = SILICONE.get(slev)
        if sil:
            out["silicone"] = sil["material"]
            out["silicone_pct"] = sil["pct"]
        if out["polymer_pct"] is None:
            out["notes"].append(f"polymer level code '{plev}' not in lookup")
        if sil is None:
            out["notes"].append(f"silicone level code '{slev}' not in lookup")

    # perfume oil, e.g. "0.50PO" / "05PO"
    m_po = re.search(r"([\d.]+)\s*PO\b", s, re.I)
    if m_po:
        v = float(m_po.group(1))
        out["perfume_pct"] = v if v >= 0.1 else v * 10  # "05PO" -> 0.5%
    return out


if __name__ == "__main__":
    for n in ["BC128o MN2508S 0.50PO 1DwC Control",
              "BC128z MN2508 0.5PO", "BC128o MN2515"]:
        d = parse_bc128_name(n)
        print(n)
        for k in ("chassis", "surfactant", "polymer", "polymer_pct",
                  "silicone", "silicone_pct", "active", "perfume_pct", "notes"):
            print(f"    {k}: {d[k]}")
        print()
