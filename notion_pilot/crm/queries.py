"""Async Notion read queries for Telegram read commands."""

from __future__ import annotations

from notion_client import AsyncClient

from notion_pilot.shared.config import Settings


def _token(settings: Settings) -> str:
    if settings.notion_token is None:
        raise ValueError("NOTION_TOKEN required")
    return settings.notion_token.get_secret_value()


def _title(page: dict) -> str:
    for prop in page.get("properties", {}).values():
        if "title" in prop:
            parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in parts)
    return "(untitled)"


def _rich_text(prop: dict) -> str:
    return "".join(p.get("plain_text", "") for p in prop.get("rich_text", []))


async def get_open_leads(settings: Settings) -> list[dict]:
    """Return open deals from the Deals DB (stage not Closed-Won/Lost)."""
    if not settings.notion_deals_database_id:
        return []
    client = AsyncClient(auth=_token(settings))
    resp = await client.databases.query(
        database_id=settings.notion_deals_database_id,
        filter={
            "and": [
                {"property": "Stage", "select": {"does_not_equal": "Closed - Won"}},
                {"property": "Stage", "select": {"does_not_equal": "Closed - Lost"}},
            ]
        },
        sorts=[{"timestamp": "last_edited_time", "direction": "descending"}],
        page_size=50,
    )
    results = []
    for page in resp.get("results", []):
        props = page.get("properties", {})
        stage_prop = props.get("Stage", {})
        stage = (stage_prop.get("select") or {}).get("name", "")
        next_action = _rich_text(props.get("Next action", {}))
        results.append({
            "title": _title(page),
            "stage": stage,
            "next_action": next_action,
        })
    return results


async def get_inbox_items(settings: Settings) -> list[dict]:
    """Return knowledge items with status 'Not analysed'."""
    client = AsyncClient(auth=_token(settings))
    resp = await client.databases.query(
        database_id=settings.notion_telegram_msg_database_id,
        filter={"property": "Status", "status": {"equals": "Not analysed"}},
        sorts=[{"timestamp": "created_time", "direction": "descending"}],
        page_size=50,
    )
    return [{"title": _title(page)} for page in resp.get("results", [])]


async def get_recent_people(settings: Settings) -> list[dict]:
    """Return people added in the last 7 days."""
    if not settings.notion_people_data_source_id:
        return []
    client = AsyncClient(auth=_token(settings))
    resp = await client.databases.query(
        database_id=settings.notion_people_data_source_id,
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
