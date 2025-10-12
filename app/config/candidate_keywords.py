"""Shared keyword helpers for vault candidate classification."""
from __future__ import annotations

from typing import Iterable, Optional

# Canonical keyword sets used across Teams query engine and LangGraph workflows
VAULT_ADVISOR_KEYWORDS = [
    "financial advisor",
    "wealth advisor",
    "investment advisor",
    "wealth management",
    "financial adviser",
    "private wealth",
    "advisor",
    "adviser",
    "financial consultant",
    "relationship manager",
    "portfolio manager",
    "client advisor",
    "senior advisor",
    "lead advisor",
    "associate advisor",
    "vice president",
    "vp",
    "director",
]

VAULT_EXECUTIVE_KEYWORDS = [
    "ceo",
    "chief executive",
    "cfo",
    "chief financial",
    "coo",
    "chief operating",
    "cto",
    "chief technology",
    "cio",
    "chief investment",
    "president",
    "managing director",
    "managing partner",
    "partner",
    "founder",
    "co-founder",
    "owner",
    "principal",
    "head of",
    "cbdo",
    "cgo",
    "ccdo",
    "cgrowth",
    "chief growth",
    "chief business",
]


def _title_matches_any(title: Optional[str], keywords: Iterable[str]) -> bool:
    """Return True when the provided title contains any keyword substring."""
    if not title:
        return False
    lowered = title.lower()
    return any(keyword in lowered for keyword in keywords)


def is_advisor_title(title: Optional[str]) -> bool:
    """Determine whether a job title should be treated as an advisor role."""
    return _title_matches_any(title, VAULT_ADVISOR_KEYWORDS)


def is_executive_title(title: Optional[str]) -> bool:
    """Determine whether a job title should be treated as an executive role."""
    if not title:
        return False

    lowered = title.lower()

    # Treat vice president variants as advisor-facing roles (handled upstream)
    vp_tokens = ("vice president", "vp ", " vp", "vp,", "vp.", "vp-", "(vp", "vp)", "/vp", "vp/")
    if any(token in lowered for token in vp_tokens) or lowered.startswith("vp"):
        return False
    if "svp" in lowered or "evp" in lowered or "avp" in lowered:
        return False

    return _title_matches_any(title, VAULT_EXECUTIVE_KEYWORDS)


_CANDIDATE_TYPE_SYNONYMS = {
    "advisor": "advisors",
    "adviser": "advisors",
    "advisors": "advisors",
    "advisers": "advisors",
    "financial_advisor": "advisors",
    "financial_advisors": "advisors",
    "financial_adviser": "advisors",
    "financial_advisers": "advisors",
    "wealth_advisor": "advisors",
    "wealth_advisors": "advisors",
    "advisor_candidates": "advisors",
    "advisory": "advisors",
    "executive": "c_suite",
    "executives": "c_suite",
    "c_suite": "c_suite",
    "c-suite": "c_suite",
    "c_suite_candidates": "c_suite",
    "leadership": "c_suite",
    "leaders": "c_suite",
}


def normalize_candidate_type(raw: Optional[str]) -> Optional[str]:
    """Normalize user-provided candidate_type values to canonical options."""
    if not raw:
        return None

    cleaned = raw.strip().lower().replace("-", "_")
    normalized = _CANDIDATE_TYPE_SYNONYMS.get(cleaned, cleaned)
    if normalized not in {"advisors", "c_suite"}:
        return None
    return normalized


__all__ = [
    "VAULT_ADVISOR_KEYWORDS",
    "VAULT_EXECUTIVE_KEYWORDS",
    "is_advisor_title",
    "is_executive_title",
    "normalize_candidate_type",
]
