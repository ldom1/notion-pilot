"""Deterministic parsing for common contact paste formats."""

from __future__ import annotations

import re

_LINKEDIN_PASTE_RE = re.compile(
    r"(https?://(?:www\.)?linkedin\.com/in/\S+)\s*:\s*(.+)",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"^\[(?:PERSON_NAME|COMPANY|NAME)\]$|^<[^>]+>$",
    re.IGNORECASE,
)


def is_placeholder(value: str) -> bool:
    """Return True if value looks like a schema placeholder, not real data."""
    return bool(_PLACEHOLDER_RE.match(value.strip()))


def parse_linkedin_paste(text: str) -> dict[str, str] | None:
    """Parse ``URL : Name, Company, Position`` LinkedIn contact pastes."""
    match = _LINKEDIN_PASTE_RE.search(text.strip())
    if not match:
        return None
    linkedin_url, rest = match.group(1), match.group(2).strip()
    parts = [part.strip() for part in rest.split(",", 2)]
    if len(parts) < 2 or not parts[0] or is_placeholder(parts[0]):
        return None
    result = {
        "name": parts[0],
        "company": parts[1],
        "position": parts[2] if len(parts) > 2 else "",
        "linkedin_url": linkedin_url,
    }
    return {key: value for key, value in result.items() if value and not is_placeholder(value)}


_CONTACT_FIELDS = frozenset({"name", "company", "position", "linkedin_url", "email"})


def sanitize_extracted(
    extracted: dict[str, str], *, fallback: dict[str, str] | None = None
) -> dict[str, str]:
    """Drop placeholder values; fill gaps from fallback (e.g. regex parse)."""
    clean = {key: value for key, value in extracted.items() if value and not is_placeholder(value)}
    if not fallback:
        return clean
    if fallback.get("linkedin_url"):
        for key in _CONTACT_FIELDS:
            if fallback.get(key):
                clean[key] = fallback[key]
        return clean
    for key, value in fallback.items():
        if value and not is_placeholder(value) and not clean.get(key):
            clean[key] = value
    return clean
