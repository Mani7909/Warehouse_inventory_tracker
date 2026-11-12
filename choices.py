"""Preloaded dropdown values (no Streamlit dependency, so easy to test)."""

UNIT_PRESETS = ["pcs", "kg", "g", "litre", "ml", "box", "packet", "carton", "bag", "bottle",
                "dozen", "pair", "set", "roll", "meter", "tonne"]
CATEGORY_PRESETS = ["Grocery", "Electronics", "Hardware", "Stationery", "Clothing", "Packaging",
                    "Raw material", "Spare parts", "Household", "Other"]


def merge_choices(*lists):
    """Combine lists, dropping blanks and case-insensitive duplicates, keeping first-seen order."""
    seen, out = set(), []
    for lst in lists:
        for v in lst:
            v = (v or "").strip()
            if v and v.lower() not in seen:
                seen.add(v.lower())
                out.append(v)
    return out
