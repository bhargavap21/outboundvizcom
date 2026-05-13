"""Keyword-based signal_type and vertical_hint extraction from raw text."""
from __future__ import annotations

# Signal type keyword maps — checked in priority order
_CLIENT_WIN_KEYWORDS = {
    "new client", "excited to announce", "thrilled to announce",
    "partnering with", "welcome", "awarded", "selected by", "won the",
}
_CASE_STUDY_KEYWORDS = {
    "case study", "project spotlight", "new project", "our latest",
    "featured work", "design for", "designed for", "we designed",
    "take a look at", "check out our", "proud to share",
}

# Vertical keyword maps
_VERTICAL_KEYWORDS: dict[str, set[str]] = {
    "footwear": {"shoe", "sneaker", "boot", "footwear", "trainer", "sole", "midsole", "outsole"},
    "consumer electronics": {
        "headphone", "speaker", "earphone", "earbud", "wearable",
        "device", "gadget", "tech", "electronics", "product design",
    },
    "furniture": {"chair", "table", "desk", "seating", "furniture", "sofa", "shelf"},
    "home goods": {"kitchen", "appliance", "home", "household", "cookware", "blender"},
    "automotive": {"car", "vehicle", "automotive", "ev", "interior", "dashboard"},
    "apparel accessories": {"bag", "backpack", "luggage", "accessory", "apparel"},
}


def classify_signal_type(text: str, source: str) -> str:
    """
    Infer signal_type from raw text and source.
    Returns: new_hire | client_win | case_study | portfolio_update
    """
    if source == "linkedin_job":
        return "new_hire"

    lower = text.lower()

    if any(kw in lower for kw in _CLIENT_WIN_KEYWORDS):
        return "client_win"
    if any(kw in lower for kw in _CASE_STUDY_KEYWORDS):
        return "case_study"

    return "portfolio_update"


def extract_vertical_hint(text: str) -> str:
    """
    Return the best-matching vertical from the text, or empty string if none found.
    When multiple match, returns the one with the most keyword hits.
    """
    lower = text.lower()
    scores: dict[str, int] = {}
    for vertical, keywords in _VERTICAL_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits:
            scores[vertical] = hits

    if not scores:
        return ""
    return max(scores, key=lambda v: scores[v])
