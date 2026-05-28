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

# LinkedIn industry taxonomy — used as controlled vocabulary for the sector field
LINKEDIN_INDUSTRIES = (
    "Accounting,Airlines/Aviation,Alternative Dispute Resolution,Alternative Medicine,"
    "Animation,Apparel & Fashion,Architecture & Planning,Arts & Crafts,Automotive,"
    "Aviation & Aerospace,Banking,Biotechnology,Broadcast Media,Building Materials,"
    "Business Supplies & Equipment,Capital Markets,Chemicals,Civic & Social Organization,"
    "Civil Engineering,Commercial Real Estate,Computer & Network Security,Computer Games,"
    "Computer Hardware,Computer Networking,Computer Software,Construction,"
    "Consumer Electronics,Consumer Goods,Consumer Services,Cosmetics,Dairy,Defense & Space,"
    "Design,E-learning,Education Management,Electrical/Electronic Manufacturing,Entertainment,"
    "Environmental Services,Events Services,Executive Office,Facilities Services,Farming,"
    "Financial Services,Fine Art,Fishery,Food & Beverages,Food Production,Fund-Raising,"
    "Furniture,Gambling & Casinos,Glass Ceramics & Concrete,Government Administration,"
    "Government Relations,Graphic Design,Health Wellness & Fitness,Higher Education,"
    "Hospital & Health Care,Hospitality,Human Resources,Import & Export,"
    "Individual & Family Services,Industrial Automation,Information Services,"
    "Information Technology & Services,Insurance,International Affairs,"
    "International Trade & Development,Internet,Investment Banking,Investment Management,"
    "Judiciary,Law Enforcement,Law Practice,Legal Services,Legislative Office,"
    "Leisure Travel & Tourism,Libraries,Logistics & Supply Chain,Luxury Goods & Jewelry,"
    "Machinery,Management Consulting,Maritime,Market Research,Marketing & Advertising,"
    "Mechanical or Industrial Engineering,Media Production,Medical Devices,Medical Practice,"
    "Mental Health Care,Military,Mining & Metals,Motion Pictures & Film,"
    "Museums & Institutions,Music,Nanotechnology,Newspapers,"
    "Non-profit Organization Management,Oil & Energy,Online Media,Outsourcing/Offshoring,"
    "Package/Freight Delivery,Packaging & Containers,Paper & Forest Products,"
    "Performing Arts,Pharmaceuticals,Philanthropy,Photography,Plastics,"
    "Political Organization,Primary/Secondary Education,Printing,"
    "Professional Training & Coaching,Program Development,Public Policy,"
    "Public Relations & Communications,Public Safety,Publishing,Railroad Manufacture,"
    "Ranching,Real Estate,Recreational Facilities & Services,Religious Institutions,"
    "Renewables & Environment,Research,Restaurants,Retail,Security & Investigations,"
    "Semiconductors,Shipbuilding,Sporting Goods,Sports,Staffing & Recruiting,Supermarkets,"
    "Telecommunications,Textiles,Think Tanks,Tobacco,Translation & Localization,"
    "Transportation/Trucking/Railroad,Utilities,Venture Capital & Private Equity,Veterinary,"
    "Warehousing,Wholesale,Wine & Spirits,Wireless,Writing & Editing"
)


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
    sector: str = ""
    tech_stack: list[str] = field(default_factory=list)
    crm_status: str = ""
    logo_url: str = ""
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


_VALID_SIZES = {"1-10", "11-50", "51-200", "201-500", "501-2000", "2001-10000", "10000+"}


def _employees_to_size(n: int) -> str:
    if n <= 0:
        return ""
    if n <= 10:
        return "1-10"
    if n <= 50:
        return "11-50"
    if n <= 200:
        return "51-200"
    if n <= 500:
        return "201-500"
    if n <= 2000:
        return "501-2000"
    if n <= 10000:
        return "2001-10000"
    return "10000+"


def _normalize_size(raw: str) -> str:
    """Map any LLM size variant to a valid Notion select option."""
    if not raw:
        return ""
    if raw in _VALID_SIZES:
        return raw
    # Strip commas and spaces then try again (e.g. "10,001+" → "10001+")
    cleaned = raw.replace(",", "").replace(" ", "")
    # Extract leading number to bucket
    digits = re.sub(r"[^\d]", "", cleaned.split("-")[0].split("+")[0])
    if digits:
        return _employees_to_size(int(digits))
    return ""


async def _apollo_company(name: str, api_key: str, domain: str = "") -> CompanyEnrichment | None:
    payload: dict[str, str] = {"domain": domain} if domain else {"name": name}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://api.apollo.io/v1/organizations/enrich",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
            )
        if resp.status_code != 200:
            return None
        org = resp.json().get("organization") or {}
        if not org:
            return None
        size = _employees_to_size(org.get("estimated_num_employees") or 0)
        linkedin = org.get("linkedin_url", "")
        website = org.get("website_url", "")
        country = org.get("country", "")
        tech_stack = [t.get("name", "") for t in (org.get("technology_names") or []) if t.get("name")]
        logo_url = org.get("logo_url", "")
        if not any([linkedin, website, size, country]):
            return None
        return CompanyEnrichment(
            website=website, linkedin_url=linkedin, size=size,
            country=country, tech_stack=tech_stack, logo_url=logo_url, source="apollo",
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
        f"Find details for the company '{name}'. "
        "Return JSON with keys: website (string), linkedin_url (string), "
        "size (one of: '1-10','11-50','51-200','201-500','501-2000','2001-10000','10000+' or ''), "
        "country (ISO alpha-2 or ''), "
        f"sector (one exact value from this list or '': {LINKEDIN_INDUSTRIES}), "
        "tech_stack (list of strings). "
        "Use empty string or empty list for unknown fields."
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
            size=_normalize_size(data.get("size", "")),
            country=data.get("country", ""),
            sector=data.get("sector", ""),
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
        "country (ISO alpha-2 or ''), "
        f"sector (one exact value from this list or '': {LINKEDIN_INDUSTRIES}), "
        "tech_stack (list of strings). "
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
            size=_normalize_size(data.get("size", "")),
            country=data.get("country", ""),
            sector=data.get("sector", ""),
            tech_stack=data.get("tech_stack") or [],
            source="llm",
        )
    except Exception:  # noqa: BLE001
        return None


# ── Logo ──────────────────────────────────────────────────────────────────────


def _domain_from_url(url: str) -> str:
    return url.split("//")[-1].split("/")[0].removeprefix("www.") if url else ""


async def _logo_for_domain(domain: str) -> str:
    """Return a logo URL for the given domain via icon.horse, else empty."""
    if not domain:
        return ""
    url = f"https://icon.horse/icon/{domain}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0), follow_redirects=True) as client:
            resp = await client.head(url)
        return url if resp.status_code == 200 else ""
    except Exception:  # noqa: BLE001
        return ""


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
        sector=base.sector or add.sector,
        tech_stack=base.tech_stack or add.tech_stack,
        crm_status=base.crm_status or add.crm_status,
        logo_url=base.logo_url or add.logo_url,
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
    domain: str = "",
    perplexity_model: str | None = "perplexity/sonar-pro",
) -> CompanyEnrichment:
    """Four-tier company enrichment. Never raises; returns partial results."""
    result = CompanyEnrichment()

    # Tier 1: Apollo (domain lookup is much more reliable than name lookup)
    if settings.apollo_api_key:
        apollo = await _apollo_company(name, settings.apollo_api_key.get_secret_value(), domain=domain)
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

    # Logo: icon.horse from domain (Apollo may already have set logo_url)
    if not result.logo_url:
        resolved_domain = domain or _domain_from_url(result.website)
        if resolved_domain:
            result.logo_url = await _logo_for_domain(resolved_domain)

    return result
