"""Interpret Telegram payloads for Notion rows via OpenRouter chat completions."""

import json
import re
from typing import Any

import httpx
from loguru import logger

from notion_pilot.config import Settings
from notion_pilot.llm.prompt import build_openrouter_system_prompt
from notion_pilot.models import IncomingMessage, NotionDatabaseProperties


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
