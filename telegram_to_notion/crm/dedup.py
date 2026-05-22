"""Fuzzy deduplication for people and company records."""
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import TypedDict

from rapidfuzz.fuzz import token_sort_ratio


class CandidateRecord(TypedDict):
    """Type for candidate records in dedup matching."""
    name: str
    company: str
    page_id: str


class DedupStatus(Enum):
    SKIP = "skip"      # score >= 85 — definite duplicate
    REVIEW = "review"  # score 75–84 — uncertain, log for human review
    NEW = "new"        # score < 75 — treat as new record


@dataclass
class MatchResult:
    status: DedupStatus
    score: float
    matched_name: str = field(default="")
    matched_company: str = field(default="")


def normalize(text: str) -> str:
    """Lowercase, strip whitespace, remove diacritics for comparison."""
    nfkd = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _key(name: str, company: str) -> str:
    return normalize(f"{name} {company}")


def find_match(
    name: str,
    company: str,
    candidates: list[CandidateRecord],
) -> MatchResult:
    """Return best fuzzy match from candidates list.

    Each candidate dict must have keys: name, company, page_id.
    """
    if not candidates:
        return MatchResult(DedupStatus.NEW, 0.0)

    key = _key(name, company)
    best_score = 0.0
    best = candidates[0]

    for c in candidates:
        if c["company"]:
            score = float(token_sort_ratio(key, _key(c["name"], c["company"])))
        else:
            # Candidate has no company — compare name-only to avoid long company strings
            # diluting what is effectively a name-only match.
            score = float(token_sort_ratio(normalize(name), normalize(c["name"])))
        if score > best_score:
            best_score = score
            best = c

    if best_score >= 85:
        return MatchResult(DedupStatus.SKIP, best_score, best["name"], best["company"])
    if best_score >= 75:
        return MatchResult(DedupStatus.REVIEW, best_score, best["name"], best["company"])
    return MatchResult(DedupStatus.NEW, best_score)
