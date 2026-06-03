"""OpenRouter chat completions — Telegram enrichment and cockpit CRM queries."""

import json
import re
from typing import Any

import httpx
from loguru import logger

from notion_pilot.shared.config import Settings
from notion_pilot.shared.llm.prompt import build_openrouter_system_prompt
from notion_pilot.shared.models import IncomingMessage, NotionDatabaseProperties


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


async def interpret_message(
    settings: Settings, incoming: IncomingMessage
) -> NotionDatabaseProperties:
    """Ask OpenRouter for Notion fields; on any error fall back to heuristics."""
    base = NotionDatabaseProperties.from_incoming(incoming)
    key = settings.openrouter_api_key
    if key is None or not key.get_secret_value().strip():
        return base

    payload: dict[str, Any] = {
        "model": settings.openrouter_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": build_openrouter_system_prompt(incoming)},
            {"role": "user", "content": "Produce the JSON object now."},
        ],
    }
    headers = {
        "Authorization": f"Bearer {key.get_secret_value()}",
        "Content-Type": "application/json",
        "X-Title": settings.openrouter_app_title,
        **(
            {"HTTP-Referer": settings.openrouter_http_referer}
            if settings.openrouter_http_referer
            else {}
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions", headers=headers, json=payload
            )
            resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        return NotionDatabaseProperties.model_validate(json.loads(_strip_json_fence(raw)))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("OpenRouter enrichment failed, using heuristics: {}", exc)
        return base


async def suggest_leads(settings: Settings, query: str, people: list[dict]) -> dict:
    """Query CRM contacts to suggest leads matching a sales objective.

    Returns a dict with keys ``message`` (str) and ``leads`` (list).
    Raises ``ValueError`` if no API key is configured.
    Raises ``httpx.HTTPStatusError`` on API errors.
    """
    key = settings.openrouter_api_key
    if key is None or not key.get_secret_value().strip():
        raise ValueError("OPENROUTER_API_KEY not configured")

    people_ctx = "\n".join(
        f"- {p['name']} | {p.get('position', '')} @ {p.get('company', '')} | id:{p['id']}"
        for p in people[:80]
    ) or "(CRM is empty or not configured)"

    system_prompt = (
        "You are a CRM assistant for Notion Pilot. "
        "Given a sales objective and a list of CRM contacts, suggest the best leads. "
        "For contacts already in the CRM use type 'existing' and include their id. "
        "For new suggested leads not in the CRM use type 'new' with a reason why they fit. "
        "Reply with ONLY a raw JSON object — no markdown, no code fences, no text outside the JSON. "
        'Schema: {"message":"one sentence summary","leads":['
        '{"type":"existing","name":"...","position":"...","company":"...","notion_id":"<id>"},'
        '{"type":"new","name":"...","position":"...","company":"...","reason":"..."}'
        "]}"
    )
    user_prompt = (
        f"Sales objective: {query}\n\n"
        f"CRM contacts:\n{people_ctx}\n\n"
        "Prefer existing CRM contacts first; add new suggestions only when the CRM lacks good matches."
    )

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
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]
    return dict(json.loads(_strip_json_fence(raw)))
