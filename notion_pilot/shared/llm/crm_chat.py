"""Multi-turn CRM chat with intent detection — used by the cockpit 'Ask your data' panel."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from notion_pilot.crm.contact_parse import is_placeholder
from notion_pilot.shared.config import Settings

_PLACEHOLDER_FRAGMENT = re.compile(
    r"\[(?:PERSON_NAME|COMPANY|NAME|ADDRESS)\]|<[^>]+>",
    re.IGNORECASE,
)

_SCHEMA = (
    '{"action":"suggest"|"create"|"info",'
    '"message":"Found 3 contacts that match your query.",'
    '"leads":[{'
    '"type":"existing"|"new",'
    '"name":"Marie Dupont",'
    '"position":"Head of Product",'
    '"company":"Acme Corp",'
    '"notion_id":"abc123-...",'
    '"reason":"Her role focuses on product strategy, which aligns with the pitch.",'
    '"deal_name":"Acme Corp — Q3 pilot"'
    "}]}"
)

_SYSTEM_PROMPT = (
    "You are Notion Pilot, a CRM assistant. "
    "Help the user find leads and manage deals in their Notion workspace.\n\n"
    "Detect the user's intent:\n"
    "- 'suggest': find and rank the best matching contacts or companies from the CRM\n"
    "- 'create': the user explicitly wants to create deal entries in Notion "
    "(keywords: 'create', 'add', 'crée', 'ajoute', 'open deal', 'ouvre un deal')\n"
    "- 'info': answer a factual question about the data (company profiles, sectors, etc.)\n\n"
    "Rules:\n"
    "- For existing CRM entries always set type='existing' and include their Notion page ID as notion_id.\n"
    "- For suggested entries not in the CRM set type='new' and include a reason.\n"
    "- For 'create' action include deal_name on every lead.\n"
    "- When the question is about company types or sectors, use the Companies list if provided.\n"
    "- NEVER use placeholder text like [PERSON_NAME], [COMPANY], <name>, etc. "
    "Always use the real name from the data, or omit the field if unknown.\n"
    "- Reply with ONLY a raw JSON object — no markdown, no code fences.\n"
    f"Example schema (values are illustrative, replace with real data): {_SCHEMA}"
)

# Keywords that signal the user is asking about company profiles/types, not contacts
_COMPANY_KEYWORDS = {
    "entreprise",
    "entreprises",
    "company",
    "companies",
    "société",
    "sociétés",
    "organisation",
    "organisations",
    "secteur",
    "secteurs",
    "industrie",
    "industries",
    "typologie",
    "typologies",
    "comptes",
    "accounts",
    "marché",
    "marchés",
    "vertical",
    "verticals",
    "structure",
    "structures",
}


def detect_data_source(query: str) -> str:
    """Return 'companies', 'people', or 'both' based on query keywords."""
    words = {w.lower().rstrip("s") for w in re.split(r"\W+", query) if len(w) > 3}
    company_hit = bool(words & {kw.rstrip("s") for kw in _COMPANY_KEYWORDS})
    lead_hit = bool(words & {"lead", "contact", "personne", "person", "find", "trouv"})
    if company_hit and not lead_hit:
        return "companies"
    if company_hit and lead_hit:
        return "both"
    return "people"


def _rank(
    items: list[dict[str, Any]], query: str, fields: list[str], limit: int
) -> list[dict[str, Any]]:
    keywords = {w.lower() for w in query.split() if len(w) > 3}

    def score(item: dict[str, Any]) -> int:
        haystack = " ".join(str(item.get(f, "")) for f in fields).lower()
        return sum(1 for kw in keywords if kw in haystack)

    return sorted(items, key=score, reverse=True)[:limit]


def _norm_id(page_id: str) -> str:
    return page_id.replace("-", "").lower()


def _is_bad_name(name: str) -> bool:
    stripped = name.strip()
    return not stripped or is_placeholder(stripped) or bool(_PLACEHOLDER_FRAGMENT.search(stripped))


def _clean_field(value: str | None) -> str:
    if not value:
        return ""
    return _PLACEHOLDER_FRAGMENT.sub("", value).strip(" @-|")


def sanitize_leads(
    leads: list[dict[str, Any]],
    people: list[dict[str, Any]],
    companies: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rehydrate CRM fields from notion_id and drop placeholder names."""
    by_id = {_norm_id(p["id"]): p for p in people if p.get("id")}
    clean: list[dict[str, Any]] = []
    for raw in leads:
        lead = dict(raw)
        person = by_id.get(_norm_id(str(lead.get("notion_id") or "")))
        if person:
            lead["type"] = "existing"
            if _is_bad_name(str(lead.get("name", ""))):
                lead["name"] = person.get("name", "")
            if not _clean_field(str(lead.get("position") or "")):
                lead["position"] = person.get("position") or ""
            if not _clean_field(str(lead.get("company") or "")):
                lead["company"] = person.get("company") or ""
        lead["name"] = _clean_field(str(lead.get("name") or ""))
        lead["position"] = _clean_field(str(lead.get("position") or ""))
        lead["company"] = _clean_field(str(lead.get("company") or ""))
        if _is_bad_name(str(lead.get("name", ""))):
            continue
        clean.append(lead)
    return clean


def _safe_parse_json(raw: str) -> dict[str, Any]:
    """Extract the first complete JSON object from raw LLM output."""
    text = raw.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return dict(json.loads(text[start : end + 1]))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON in LLM response: {raw[:200]!r}")


async def chat_crm(
    settings: Settings,
    query: str,
    history: list[dict[str, Any]],
    people: list[dict[str, Any]],
    companies: list[dict[str, Any]] | None = None,
    workspace_memory: str = "",
) -> dict[str, Any]:
    """Multi-turn CRM chat: intent detection + lead suggestions or deal creation.

    Args:
        settings: app settings (API keys, model)
        query: current user message
        history: previous turns as [{"role": "user"|"assistant", "content": str}]
        people: CRM contacts from the People database (may be empty)
        companies: CRM companies from the Companies database (may be None/empty)
        workspace_memory: persistent user context injected into every call

    Returns:
        dict with keys: action ("suggest"|"create"|"info"), message (str), leads (list)

    Raises:
        ValueError: if OPENROUTER_API_KEY is not configured
        httpx.HTTPStatusError: on LLM API errors
    """
    key = settings.openrouter_api_key
    if key is None or not key.get_secret_value().strip():
        raise ValueError("OPENROUTER_API_KEY not configured")

    ctx_parts: list[str] = []

    if people:
        people = [p for p in people if p.get("name") and not is_placeholder(str(p["name"]))]
        ranked_people = _rank(people, query, ["name", "position", "company"], 80)
        people_lines = "\n".join(
            f"- {p['name']} | {p.get('position', '')} @ {p.get('company', '')} | id:{p['id']}"
            for p in ranked_people
        )
        ctx_parts.append(
            f"CRM contacts ({len(people)} total, showing top {len(ranked_people)}):\n{people_lines}"
        )

    if companies:
        ranked_cos = _rank(companies, query, ["name", "sector"], 80)
        co_lines = "\n".join(
            f"- {c['name']} | sector:{c.get('sector', '')} | id:{c['id']}" for c in ranked_cos
        )
        ctx_parts.append(
            f"CRM companies ({len(companies)} total, showing top {len(ranked_cos)}):\n{co_lines}"
        )

    if not ctx_parts:
        ctx_parts.append("(CRM is empty — no data configured)")

    system = _SYSTEM_PROMPT
    if workspace_memory:
        system += (
            f"\n\nWorkspace context (always apply this when finding leads):\n{workspace_memory}"
        )

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for turn in history[-10:]:
        messages.append({"role": turn["role"], "content": str(turn["content"])})
    messages.append(
        {
            "role": "user",
            "content": f"{query}\n\n" + "\n\n".join(ctx_parts),
        }
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.openrouter_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {key.get_secret_value()}",
                "Content-Type": "application/json",
                **(
                    {"HTTP-Referer": settings.openrouter_http_referer}
                    if settings.openrouter_http_referer
                    else {}
                ),
                **(
                    {"X-Title": settings.openrouter_app_title}
                    if settings.openrouter_app_title
                    else {}
                ),
            },
            json={
                "model": settings.openrouter_model,
                "messages": messages,
                "max_tokens": 2000,
            },
        )
        resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]
    result = _safe_parse_json(raw)
    result.setdefault("action", "suggest")
    result.setdefault("leads", [])
    result["leads"] = sanitize_leads(result["leads"], people, companies)
    return result
