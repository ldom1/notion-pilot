"""Async Notion read queries for Telegram read commands."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from notion_client import AsyncClient

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


def _rich_text(prop: dict[str, Any]) -> str:
    return "".join(p.get("plain_text", "") for p in prop.get("rich_text", []))


async def get_open_leads(settings: Settings) -> list[dict[str, Any]]:
    """Return open deals from the Deals DB with primary contact name resolved."""
    if not settings.notion_deals_database_id:
        return []
    token = _token(settings)
    async with httpx.AsyncClient(headers=_headers(token), timeout=30) as client:
        resp = await client.post(
            f"{_NOTION_BASE}/databases/{settings.notion_deals_database_id}/query",
            json={
                "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
                "page_size": 50,
            },
        )
        resp.raise_for_status()

        results: list[dict[str, Any]] = []
        contact_ids_per_result: list[list[str]] = []

        for page in resp.json().get("results", []):
            props = page.get("properties", {})
            stage_prop = props.get("Stage", {})
            stage = (stage_prop.get("select") or {}).get("name", "")
            if stage in ("Closed - Won", "Closed - Lost"):
                continue
            next_action = _rich_text(props.get("Next action", {}))
            page_id = page.get("id", "").replace("-", "")
            url = f"https://notion.so/{page_id}" if page_id else None
            contact_ids = [r["id"] for r in props.get("Contacts", {}).get("relation", [])]
            results.append(
                {"title": _title(page), "stage": stage, "next_action": next_action, "url": url}
            )
            contact_ids_per_result.append(contact_ids)

        # Resolve first contact name for each lead in parallel
        all_ids = {cid for cids in contact_ids_per_result for cid in cids[:1]}
        person_names: dict[str, str] = {}

        async def _fetch_name(cid: str) -> None:
            r = await client.get(f"{_NOTION_BASE}/pages/{cid}")
            if r.is_success:
                person_names[cid] = _title(r.json())

        if all_ids:
            await asyncio.gather(*[_fetch_name(cid) for cid in all_ids])

        for result, cids in zip(results, contact_ids_per_result):
            if cids and cids[0] in person_names:
                result["person_name"] = person_names[cids[0]]

        return results


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


async def get_recent_people(settings: Settings) -> list[dict[str, Any]]:
    """Return people added in the last 7 days."""
    if not settings.notion_people_data_source_id:
        return []
    token = _token(settings)
    client = AsyncClient(auth=token)
    resp = await client.databases.query(
        settings.notion_people_data_source_id,
        filter={"timestamp": "created_time", "created_time": {"past_week": {}}},
        sorts=[{"timestamp": "created_time", "direction": "descending"}],
        page_size=20,
    )
    results = []
    for page in resp.get("results", []):
        props = page.get("properties", {})
        company = _rich_text(props.get("Company", {}))
        results.append({"name": _title(page), "company": company})
    return results
