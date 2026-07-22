"""Notion database access helpers for the web cockpit (OAuth token + databases API)."""

from __future__ import annotations

import httpx

from web.config import NOTION_API


def _title_from_db(data: dict) -> str | None:
    parts = data.get("title") or []
    name = "".join(t.get("plain_text", "") for t in parts)
    return name or data.get("name") or None


async def query_db_status(client: httpx.AsyncClient, db_id: str) -> dict:
    """Return count + name for a Notion database id (from OAuth search / cockpit link)."""
    db_r = await client.get(f"{NOTION_API}/databases/{db_id}")
    db_r.raise_for_status()
    notion_name = _title_from_db(db_r.json())

    q_r = await client.post(
        f"{NOTION_API}/databases/{db_id}/query",
        json={"page_size": 100},
    )
    q_r.raise_for_status()
    data = q_r.json()
    return {
        "count": len(data.get("results", [])),
        "has_more": bool(data.get("has_more")),
        "configured": True,
        "notion_name": notion_name,
    }


async def query_all_pages(client: httpx.AsyncClient, db_id: str) -> list[dict]:
    """Fetch all pages from a Notion database id."""
    rows: list[dict] = []
    cursor: str | None = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = await client.post(f"{NOTION_API}/databases/{db_id}/query", json=body)
        r.raise_for_status()
        data = r.json()
        rows.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return rows


def format_notion_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return (
            "Integration cannot access this database — re-link it in Workspace "
            "or add Notion Pilot under Connections on the database page"
        )
    return str(exc)
