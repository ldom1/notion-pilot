"""Fuzzy deduplication for people and company records. Pure — no Notion dependency."""

import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import TypedDict

from rapidfuzz.fuzz import token_sort_ratio


class _CandidateBase(TypedDict):
    name: str
    company: str
    page_id: str


class CandidateRecord(_CandidateBase, total=False):
    """Extended candidate — required: name/company/page_id; optional: prospection metadata."""

    position: str
    seniority: str
    role_type: list[str]
    linkedin_url: str
    email: str
    phone: str


class DedupStatus(Enum):
    SKIP = "skip"
    REVIEW = "review"
    NEW = "new"


@dataclass
class MatchResult:
    status: DedupStatus
    score: float
    matched_name: str = field(default="")
    matched_company: str = field(default="")


def normalize(text: str) -> str:
    """Lowercase, strip whitespace, remove diacritics."""
    nfkd = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _key(name: str, company: str) -> str:
    return normalize(f"{name} {company}")


def find_match(
    name: str,
    company: str,
    candidates: list[CandidateRecord],
) -> MatchResult:
    """Return best fuzzy match from candidates. Each must have: name, company, page_id."""
    if not candidates:
        return MatchResult(DedupStatus.NEW, 0.0)

    key = _key(name, company)
    best_score = 0.0
    best = candidates[0]

    for c in candidates:
        if c["company"]:
            score = float(token_sort_ratio(key, _key(c["name"], c["company"])))
        else:
            score = float(token_sort_ratio(normalize(name), normalize(c["name"])))
        if score > best_score:
            best_score = score
            best = c

    if best_score >= 85:
        return MatchResult(DedupStatus.SKIP, best_score, best["name"], best["company"])
    if best_score >= 75:
        return MatchResult(DedupStatus.REVIEW, best_score, best["name"], best["company"])
    return MatchResult(DedupStatus.NEW, best_score)


_NOTION_BASE_URL = "https://www.notion.so"


def notion_page_url(page_id: str) -> str:
    return f"{_NOTION_BASE_URL}/{page_id.replace('-', '')}"


@dataclass
class DuplicatePair:
    score: float
    name_a: str
    id_a: str
    name_b: str
    id_b: str
    context_a: str = field(default="")
    context_b: str = field(default="")


def find_company_duplicates(id_to_name: dict[str, str], threshold: float) -> list[DuplicatePair]:
    """Pairwise fuzzy-match every company name against every other. Pure — no Notion I/O."""
    items = [(pid, name, normalize(name)) for pid, name in id_to_name.items()]
    pairs: list[DuplicatePair] = []
    for i, (id_a, name_a, norm_a) in enumerate(items):
        for id_b, name_b, norm_b in items[i + 1 :]:
            score = float(token_sort_ratio(norm_a, norm_b))
            if score >= threshold:
                pairs.append(DuplicatePair(score, name_a, id_a, name_b, id_b))
    return sorted(pairs, key=lambda p: -p.score)


def find_people_duplicates(
    existing: list[CandidateRecord], threshold: float
) -> list[DuplicatePair]:
    """Pairwise fuzzy-match every person (name + company) against every other."""

    def key(r: CandidateRecord) -> str:
        return normalize(f"{r['name']} {r.get('company', '')}")

    records = [(r["page_id"], r["name"], r.get("company", ""), key(r)) for r in existing]
    pairs: list[DuplicatePair] = []
    for i, (id_a, name_a, co_a, key_a) in enumerate(records):
        for id_b, name_b, co_b, key_b in records[i + 1 :]:
            score = float(token_sort_ratio(key_a, key_b))
            if score >= threshold:
                pairs.append(DuplicatePair(score, name_a, id_a, name_b, id_b, co_a, co_b))
    return sorted(pairs, key=lambda p: -p.score)
