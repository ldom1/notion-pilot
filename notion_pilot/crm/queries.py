"""Async Notion read queries kept in the platform (inbox)."""

from __future__ import annotations

from typing import Any

import httpx

from notion_pilot.shared.config import Settings

_NOTION_BASE = "https://api.notion.com/v1"


def _token(settings: Settings) -> str:
    if settings.notion_token is None:
        raise ValueError("NOTION_TOKEN required")
    return settings.notion_token.get_secret_value()


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }


def _title(page: dict[str, Any]) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in parts)
    return "(untitled)"


async def get_inbox_items(settings: Settings) -> list[dict[str, Any]]:
    """Return knowledge items with status 'Not analysed'."""
    if not settings.notion_token:
        return []
    token = _token(settings)
    async with httpx.AsyncClient(headers=_headers(token), timeout=30) as client:
        resp = await client.post(
            f"{_NOTION_BASE}/databases/{settings.notion_telegram_msg_database_id}/query",
            json={
                "filter": {"property": "Status", "status": {"equals": "Not analysed"}},
                "sorts": [{"timestamp": "created_time", "direction": "descending"}],
                "page_size": 50,
            },
        )
    resp.raise_for_status()
    return [{"title": _title(page)} for page in resp.json().get("results", [])]
