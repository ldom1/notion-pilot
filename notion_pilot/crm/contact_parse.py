"""Deterministic parsing for common contact paste formats."""

from __future__ import annotations

import re

_LINKEDIN_PERSON_PASTE_RE = re.compile(
    r"(https?://(?:www\.)?linkedin\.com/in/\S+)\s*:\s*(.+)",
    re.IGNORECASE,
)
_LINKEDIN_COMPANY_URL_RE = re.compile(
    r"(https?://(?:www\.)?linkedin\.com/company/[^/\s]+/?)(?:\s*:\s*(.+))?",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"^\[(?:PERSON_NAME|COMPANY|NAME)\]$|^<[^>]+>$",
    re.IGNORECASE,
)
_POSITION_HINT = re.compile(
    r"\b("
    r"responsable|director|directeur|manager|lead|head|cto|ceo|vp|"
    r"développement|developpement|affaires|consultant|chargé|chargee|engineer|"
    r"founder|président|president|coordinator|analyst|architect|chapter"
    r")\b",
    re.IGNORECASE,
)


def is_placeholder(value: str) -> bool:
    """Return True if value looks like a schema placeholder, not real data."""
    return bool(_PLACEHOLDER_RE.match(value.strip()))


def _slug_to_label(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def parse_linkedin_person_paste(text: str) -> dict[str, str] | None:
    """Parse ``linkedin.com/in/… : Name, Company, Position`` person pastes."""
    match = _LINKEDIN_PERSON_PASTE_RE.search(text.strip())
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


_MARKDOWN_LINK_PERSON_RE = re.compile(
    r"\[([^\]]+)\]\((https?://(?:www\.)?linkedin\.com/in/\S+?)\)\s*,\s*([^:\n]+?)\s*:",
    re.IGNORECASE,
)
_URL_ONLY_RE = re.compile(r"(https?://(?:www\.)?linkedin\.com/in/\S+)", re.IGNORECASE)


def _normalize_linkedin_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def parse_markdown_link_person_paste(text: str) -> dict[str, str] | None:
    """Parse ``[Name](linkedin_url), Company :`` with an optional repeated
    LinkedIn URL line following. If a second URL is present and differs from
    the markdown-link URL, treat the message as ambiguous and return None
    instead of guessing — the caller falls through to the LLM, which can
    ask the user rather than silently picking (possibly) the wrong URL."""
    stripped = text.strip()
    match = _MARKDOWN_LINK_PERSON_RE.search(stripped)
    if not match:
        return None
    name, linkedin_url, company = match.group(1).strip(), match.group(2), match.group(3).strip()
    if not name or is_placeholder(name) or not company or is_placeholder(company):
        return None

    remainder = stripped[match.end() :]
    other_url_match = _URL_ONLY_RE.search(remainder)
    if other_url_match:
        other_url = other_url_match.group(1)
        if _normalize_linkedin_url(other_url) != _normalize_linkedin_url(linkedin_url):
            return None  # ambiguous — differing second URL, don't guess

    return {"name": name, "company": company, "linkedin_url": linkedin_url}


def parse_linkedin_company_paste(text: str) -> dict[str, str] | None:
    """Parse ``linkedin.com/company/…`` with optional ``: Name, sector, …`` tail."""
    match = _LINKEDIN_COMPANY_URL_RE.search(text.strip())
    if not match:
        return None
    linkedin_url = match.group(1).rstrip("/")
    rest = (match.group(2) or "").strip()
    slug_match = re.search(r"/company/([^/?#]+)", linkedin_url, re.IGNORECASE)
    slug_name = _slug_to_label(slug_match.group(1)) if slug_match else ""
    if rest:
        name = rest.split(",", 1)[0].strip()
        if is_placeholder(name):
            name = slug_name
    else:
        name = slug_name
    if not name:
        return None
    return {"name": name, "linkedin_url": linkedin_url}


def parse_linkedin_paste(text: str) -> dict[str, str] | None:
    """Alias for person paste (backward compatible)."""
    return parse_linkedin_person_paste(text)


def parse_linkedin_deterministic(text: str) -> tuple[str, dict[str, str]] | None:
    """Return (inferred_type, fields) for LinkedIn /in/ or /company/ URLs."""
    person = parse_linkedin_person_paste(text)
    if person:
        return "people", person
    company = parse_linkedin_company_paste(text)
    if company:
        return "company", company
    return None


def parse_comma_contact(text: str) -> dict[str, str] | None:
    """Parse ``Name, Company, Position`` or ``Name, Position, Company`` contact lines."""
    stripped = text.strip()
    if not stripped or stripped.lower().startswith("http") or "linkedin.com" in stripped.lower():
        return None
    if stripped.count(",") < 2:
        return None
    parts = [part.strip() for part in stripped.split(",", 2)]
    if len(parts) != 3 or not parts[0] or is_placeholder(parts[0]):
        return None
    name, first, second = parts
    first_pos = bool(_POSITION_HINT.search(first))
    second_pos = bool(_POSITION_HINT.search(second))
    if first_pos and not second_pos:
        return {"name": name, "position": first, "company": second}
    if second_pos and not first_pos:
        return {"name": name, "company": first, "position": second}
    if len(first.split()) <= 3 and len(second.split()) > len(first.split()):
        return {"name": name, "company": first, "position": second}
    return None


def parse_contact_message(text: str) -> dict[str, str] | None:
    """Try deterministic person paste formats (/people command)."""
    return (
        parse_linkedin_person_paste(text)
        or parse_markdown_link_person_paste(text)
        or parse_comma_contact(text)
    )


def parse_company_message(text: str) -> dict[str, str] | None:
    """Try deterministic company paste formats (/company command)."""
    return parse_linkedin_company_paste(text)


_CONTACT_FIELDS = frozenset({"name", "company", "position", "linkedin_url", "email"})


def sanitize_extracted(
    extracted: dict[str, str], *, fallback: dict[str, str] | None = None
) -> dict[str, str]:
    """Drop placeholder values; fill gaps from fallback (e.g. regex parse)."""
    clean = {key: value for key, value in extracted.items() if value and not is_placeholder(value)}
    if not fallback:
        return clean
    if fallback.get("linkedin_url") or (fallback.get("name") and fallback.get("company")):
        for key in _CONTACT_FIELDS:
            if fallback.get(key):
                clean[key] = fallback[key]
        return clean
    for key, value in fallback.items():
        if value and not is_placeholder(value) and not clean.get(key):
            clean[key] = value
    return clean
