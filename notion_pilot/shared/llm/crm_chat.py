"""Multi-turn CRM chat with intent detection — used by the cockpit 'Ask your data' panel."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from notion_pilot.shared.config import Settings

_SCHEMA = (
    '{"action":"suggest"|"create"|"info",'
    '"message":"one sentence summary",'
    '"leads":[{'
    '"type":"existing"|"new",'
    '"name":"...",'
    '"position":"...",'
    '"company":"...",'
    '"notion_id":"<page-id for existing contacts or companies>",'
    '"reason":"<why they fit>",'
    '"deal_name":"<suggested deal title, for create action>"'
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
    "- Reply with ONLY a raw JSON object — no markdown, no code fences.\n"
    f"Schema: {_SCHEMA}"
)

# Keywords that signal the user is asking about company profiles/types, not contacts
_COMPANY_KEYWORDS = {
    "entreprise", "entreprises", "company", "companies", "société", "sociétés",
    "organisation", "organisations", "secteur", "secteurs", "industrie", "industries",
    "typologie", "typologies", "comptes", "accounts", "marché", "marchés",
    "vertical", "verticals", "structure", "structures",
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


def _rank(items: list[dict], query: str, fields: list[str], limit: int) -> list[dict]:
    keywords = {w.lower() for w in query.split() if len(w) > 3}

    def score(item: dict) -> int:
        haystack = " ".join(str(item.get(f, "")) for f in fields).lower()
        return sum(1 for kw in keywords if kw in haystack)

    return sorted(items, key=score, reverse=True)[:limit]


def _safe_parse_json(raw: str) -> dict:
    """Extract the first complete JSON object from raw LLM output."""
    text = raw.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return dict(json.loads(text[start:end + 1]))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON in LLM response: {raw[:200]!r}")


async def chat_crm(
    settings: Settings,
    query: str,
    history: list[dict[str, Any]],
    people: list[dict],
    companies: list[dict] | None = None,
    workspace_memory: str = "",
) -> dict:
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
        ranked_people = _rank(people, query, ["name", "position", "company"], 80)
        people_lines = "\n".join(
            f"- {p['name']} | {p.get('position', '')} @ {p.get('company', '')} | id:{p['id']}"
            for p in ranked_people
        )
        ctx_parts.append(f"CRM contacts ({len(people)} total, showing top {len(ranked_people)}):\n{people_lines}")

    if companies:
        ranked_cos = _rank(companies, query, ["name", "sector"], 80)
        co_lines = "\n".join(
            f"- {c['name']} | sector:{c.get('sector', '')} | id:{c['id']}"
            for c in ranked_cos
        )
        ctx_parts.append(f"CRM companies ({len(companies)} total, showing top {len(ranked_cos)}):\n{co_lines}")

    if not ctx_parts:
        ctx_parts.append("(CRM is empty — no data configured)")

    system = _SYSTEM_PROMPT
    if workspace_memory:
        system += f"\n\nWorkspace context (always apply this when finding leads):\n{workspace_memory}"

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for turn in history[-10:]:
        messages.append({"role": turn["role"], "content": str(turn["content"])})
    messages.append({
        "role": "user",
        "content": f"{query}\n\n" + "\n\n".join(ctx_parts),
    })

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.openrouter_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {key.get_secret_value()}",
                "Content-Type": "application/json",
                **({"HTTP-Referer": settings.openrouter_http_referer} if settings.openrouter_http_referer else {}),
                **({"X-Title": settings.openrouter_app_title} if settings.openrouter_app_title else {}),
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
    return result
