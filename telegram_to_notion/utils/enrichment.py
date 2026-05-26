"""Four-tier person and company enrichment. Never raises; returns partial results."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from telegram_to_notion.config import Settings

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_LINKEDIN_IN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+/?")
_LINKEDIN_CO_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/company/[a-zA-Z0-9\-_%]+/?")
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_TIMEOUT = httpx.Timeout(20.0)


def _openrouter_headers(settings: Settings) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "X-Title": settings.openrouter_app_title}
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    return headers


@dataclass
class PersonEnrichment:
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    seniority: str = ""
    role_type: list[str] = field(default_factory=list)
    country: str = ""
    source: str = ""


@dataclass
class CompanyEnrichment:
    website: str = ""
    linkedin_url: str = ""
    size: str = ""
    country: str = ""
    tech_stack: list[str] = field(default_factory=list)
    crm_status: str = ""
    source: str = ""


# ── Tier 1: Apollo ────────────────────────────────────────────────────────────


async def _apollo_person(name: str, company: str, api_key: str) -> PersonEnrichment | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://api.apollo.io/v1/people/match",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"name": name, "organization_name": company},
            )
        if resp.status_code != 200:
            return None
        person = resp.json().get("person") or {}
        if not person:
            return None
        email = person.get("email", "")
        phones = person.get("phone_numbers") or []
        phone = phones[0].get("sanitized_number", "") if phones else ""
        linkedin = person.get("linkedin_url", "")
        seniority = person.get("seniority", "")
        role_type = [f for f in (person.get("functions") or []) if f]
        country = person.get("country", "")
        if not any([email, phone, linkedin]):
            return None
        return PersonEnrichment(
            email=email, phone=phone, linkedin_url=linkedin,
            seniority=seniority, role_type=role_type, country=country, source="apollo",
        )
    except Exception:  # noqa: BLE001
        return None


async def _apollo_company(name: str, api_key: str) -> CompanyEnrichment | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://api.apollo.io/v1/organizations/enrich",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"name": name},
            )
        if resp.status_code != 200:
            return None
        org = resp.json().get("organization") or {}
        if not org:
            return None
        raw_size = org.get("estimated_num_employees") or 0
        if raw_size <= 0:
            size = ""
        elif raw_size <= 10:
            size = "1-10"
        elif raw_size <= 50:
            size = "11-50"
        elif raw_size <= 200:
            size = "51-200"
        elif raw_size <= 500:
            size = "201-500"
        elif raw_size <= 1000:
            size = "501-1000"
        else:
            size = "1000+"
        linkedin = org.get("linkedin_url", "")
        website = org.get("website_url", "")
        country = org.get("country", "")
        if not any([linkedin, website]):
            return None
        return CompanyEnrichment(
            website=website, linkedin_url=linkedin, size=size,
            country=country, source="apollo",
        )
    except Exception:  # noqa: BLE001
        return None


# ── Tier 2: Brave Search ──────────────────────────────────────────────────────


async def _brave_person(name: str, company: str, api_key: str) -> PersonEnrichment | None:
    try:
        query = f'"{name}" "{company}" email OR linkedin'
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            )
        if resp.status_code != 200:
            return None
        results = resp.json().get("web", {}).get("results") or []
        text = " ".join(r.get("description", "") + " " + r.get("url", "") for r in results)
        email = next(iter(_EMAIL_RE.findall(text)), "")
        linkedin = next(iter(_LINKEDIN_IN_RE.findall(text)), "")
        if not email and not linkedin:
            return None
        return PersonEnrichment(email=email, linkedin_url=linkedin, source="brave")
    except Exception:  # noqa: BLE001
        return None


async def _brave_company(name: str, api_key: str) -> CompanyEnrichment | None:
    try:
        query = f'"{name}" company linkedin site:linkedin.com OR official website'
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            )
        if resp.status_code != 200:
            return None
        results = resp.json().get("web", {}).get("results") or []
        text = " ".join(r.get("description", "") + " " + r.get("url", "") for r in results)
        linkedin = next(iter(_LINKEDIN_CO_RE.findall(text)), "")
        if not linkedin:
            return None
        return CompanyEnrichment(linkedin_url=linkedin, source="brave")
    except Exception:  # noqa: BLE001
        return None


# ── Tier 3: Perplexity via OpenRouter ─────────────────────────────────────────


def _parse_llm_json(content: str) -> Any:
    """Parse JSON from LLM response, handling markdown code blocks."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = _JSON_BLOCK_RE.search(content)
        if m:
            return json.loads(m.group(1))
        raise


async def _perplexity_person(
    name: str, company: str, settings: Settings, model: str
) -> PersonEnrichment | None:
    api_key = settings.openrouter_api_key.get_secret_value()  # type: ignore[union-attr]
    prompt = (
        f"Find professional contact details for {name} at {company}. "
        "Return JSON with keys: email, phone, linkedin_url, seniority, role_type (list), country. "
        "Use empty string for unknown fields."
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", **_openrouter_headers(settings)},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            )
        if resp.status_code != 200:
            return None
        data = _parse_llm_json(resp.json()["choices"][0]["message"]["content"])
        if not any([data.get("email"), data.get("phone"), data.get("linkedin_url")]):
            return None
        return PersonEnrichment(
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            linkedin_url=data.get("linkedin_url", ""),
            seniority=data.get("seniority", ""),
            role_type=data.get("role_type") or [],
            country=data.get("country", ""),
            source="perplexity",
        )
    except Exception:  # noqa: BLE001
        return None


async def _perplexity_company(
    name: str, settings: Settings, model: str
) -> CompanyEnrichment | None:
    api_key = settings.openrouter_api_key.get_secret_value()  # type: ignore[union-attr]
    prompt = (
        f"Find details for the company {name}. "
        "Return JSON with keys: website, linkedin_url, size (e.g. '11-50'), "
        "country (ISO alpha-2), tech_stack (list), crm_status. "
        "Use empty string for unknown fields."
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", **_openrouter_headers(settings)},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            )
        if resp.status_code != 200:
            return None
        data = _parse_llm_json(resp.json()["choices"][0]["message"]["content"])
        if not any([data.get("website"), data.get("linkedin_url")]):
            return None
        return CompanyEnrichment(
            website=data.get("website", ""),
            linkedin_url=data.get("linkedin_url", ""),
            size=data.get("size", ""),
            country=data.get("country", ""),
            tech_stack=data.get("tech_stack") or [],
            source="perplexity",
        )
    except Exception:  # noqa: BLE001
        return None


# ── Tier 4: LLM inference ─────────────────────────────────────────────────────


async def _llm_person_infer(
    name: str, company: str, position: str, settings: Settings
) -> PersonEnrichment | None:
    api_key = settings.openrouter_api_key.get_secret_value()  # type: ignore[union-attr]
    prompt = (
        f"Infer professional attributes for {name}, {position or 'unknown role'} at {company}. "
        "Return JSON: {\"seniority\": one of [founder, c_suite, vp, director, manager, senior, mid, junior], "
        "\"role_type\": list e.g. [\"engineering\"], \"country\": ISO alpha-2 or \"\"}. "
        "Reason from company name and job title only."
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", **_openrouter_headers(settings)},
                json={
                    "model": settings.openrouter_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
        if resp.status_code != 200:
            return None
        data = _parse_llm_json(resp.json()["choices"][0]["message"]["content"])
        return PersonEnrichment(
            seniority=data.get("seniority", ""),
            role_type=data.get("role_type") or [],
            country=data.get("country", ""),
            source="llm",
        )
    except Exception:  # noqa: BLE001
        return None


# ── Tier 4: LLM inference (company) ──────────────────────────────────────────


async def _llm_company_infer(
    name: str, settings: Settings
) -> CompanyEnrichment | None:
    api_key = settings.openrouter_api_key.get_secret_value()  # type: ignore[union-attr]
    prompt = (
        f"Provide details for the company named '{name}'. "
        "Return JSON with keys: website (string), linkedin_url (string), "
        "size (one of: '1-10','11-50','51-200','201-500','501-2000','2001-10000','10000+' or ''), "
        "country (ISO alpha-2 or ''), tech_stack (list of strings). "
        "Use empty string or empty list for unknown fields."
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", **_openrouter_headers(settings)},
                json={
                    "model": settings.openrouter_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
        if resp.status_code != 200:
            return None
        data = _parse_llm_json(resp.json()["choices"][0]["message"]["content"])
        if not any([data.get("website"), data.get("linkedin_url"), data.get("size"), data.get("country")]):
            return None
        return CompanyEnrichment(
            website=data.get("website", ""),
            linkedin_url=data.get("linkedin_url", ""),
            size=data.get("size", ""),
            country=data.get("country", ""),
            tech_stack=data.get("tech_stack") or [],
            source="llm",
        )
    except Exception:  # noqa: BLE001
        return None


# ── Merge helpers ─────────────────────────────────────────────────────────────


def _merge_person(base: PersonEnrichment, add: PersonEnrichment) -> PersonEnrichment:
    return PersonEnrichment(
        email=base.email or add.email,
        phone=base.phone or add.phone,
        linkedin_url=base.linkedin_url or add.linkedin_url,
        seniority=base.seniority or add.seniority,
        role_type=base.role_type or add.role_type,
        country=base.country or add.country,
        source=base.source or add.source,
    )


def _merge_company(base: CompanyEnrichment, add: CompanyEnrichment) -> CompanyEnrichment:
    return CompanyEnrichment(
        website=base.website or add.website,
        linkedin_url=base.linkedin_url or add.linkedin_url,
        size=base.size or add.size,
        country=base.country or add.country,
        tech_stack=base.tech_stack or add.tech_stack,
        crm_status=base.crm_status or add.crm_status,
        source=base.source or add.source,
    )


# ── Public API ────────────────────────────────────────────────────────────────


async def enrich_person(
    name: str,
    company: str,
    settings: Settings,
    position: str = "",
    perplexity_model: str | None = "perplexity/sonar-pro",
) -> PersonEnrichment:
    """Four-tier person enrichment. Never raises; returns partial results."""
    result = PersonEnrichment()

    # Tier 1: Apollo
    if settings.apollo_api_key:
        apollo = await _apollo_person(name, company, settings.apollo_api_key.get_secret_value())
        if apollo:
            result = _merge_person(result, apollo)

    # Tier 2: Brave (skipped if Apollo already found contact info)
    if not any([result.email, result.phone, result.linkedin_url]) and settings.brave_api_key:
        brave = await _brave_person(name, company, settings.brave_api_key.get_secret_value())
        if brave:
            result = _merge_person(result, brave)

    # Tier 3: Perplexity (only if Brave found nothing)
    if (
        not any([result.email, result.phone, result.linkedin_url])
        and perplexity_model
        and settings.openrouter_api_key
    ):
        perp = await _perplexity_person(name, company, settings, model=perplexity_model)
        if perp:
            result = _merge_person(result, perp)

    # Tier 4: LLM inference — only when no tier found anything (cost gate: avoid LLM call when contact already enriched)
    if (
        not result.source
        and (not result.seniority or not result.role_type)
        and settings.openrouter_api_key
    ):
        llm = await _llm_person_infer(name, company, position, settings)
        if llm:
            result = _merge_person(result, llm)

    return result


async def enrich_company(
    name: str,
    settings: Settings,
    perplexity_model: str | None = "perplexity/sonar-pro",
) -> CompanyEnrichment:
    """Four-tier company enrichment. Never raises; returns partial results."""
    result = CompanyEnrichment()

    # Tier 1: Apollo
    if settings.apollo_api_key:
        apollo = await _apollo_company(name, settings.apollo_api_key.get_secret_value())
        if apollo:
            result = _merge_company(result, apollo)

    # Tier 2: Brave
    if not any([result.website, result.linkedin_url]) and settings.brave_api_key:
        brave = await _brave_company(name, settings.brave_api_key.get_secret_value())
        if brave:
            result = _merge_company(result, brave)

    # Tier 3: Perplexity
    if (
        not any([result.website, result.linkedin_url])
        and perplexity_model
        and settings.openrouter_api_key
    ):
        perp = await _perplexity_company(name, settings, model=perplexity_model)
        if perp:
            result = _merge_company(result, perp)

    # Tier 4: LLM inference (fallback when no previous tier found website/linkedin)
    if not result.source and settings.openrouter_api_key:
        llm = await _llm_company_infer(name, settings)
        if llm:
            result = _merge_company(result, llm)

    return result
