"""Notion Activities log — standard databases API (not data_sources).

No dedup/upsert here — unlike Deals, an Activity is always a new event (a
call, a meeting, an email), never something to match against and update.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

_NOTION_VERSION = "2022-06-28"
_NOTION_BASE = "https://api.notion.com/v1"


@dataclass
class ActivityRecord:
    title: str
    type: str
    outcome: str = ""
    deal_id: str = ""
    person_id: str = ""
    company_id: str = ""
    date: str = ""
    duration_min: float | None = None
    next_action: str = ""
    next_action_date: str = ""
    notes: str = ""


def _to_properties(activity: ActivityRecord) -> dict[str, Any]:
    props: dict[str, Any] = {
        "Name": {"title": [{"text": {"content": activity.title}}]},
        "Type": {"select": {"name": activity.type}},
    }
    if activity.outcome:
        props["Outcome"] = {"select": {"name": activity.outcome}}
    if activity.deal_id:
        props["Deal"] = {"relation": [{"id": activity.deal_id}]}
    if activity.person_id:
        props["Person"] = {"relation": [{"id": activity.person_id}]}
    if activity.company_id:
        props["Company"] = {"relation": [{"id": activity.company_id}]}
    if activity.date:
        props["Date"] = {"date": {"start": activity.date}}
    if activity.duration_min is not None:
        props["Duration (min)"] = {"number": activity.duration_min}
    if activity.next_action:
        props["Next Step"] = {"rich_text": [{"text": {"content": activity.next_action}}]}
    if activity.next_action_date:
        props["Next Step Date"] = {"date": {"start": activity.next_action_date}}
    if activity.notes:
        props["Notes"] = {"rich_text": [{"text": {"content": activity.notes}}]}
    return props


class NotionActivitiesLog:
    """Create and list Activities pages. Uses raw httpx, same style as NotionDealsSyncer."""

    def __init__(self, client: httpx.AsyncClient, token: str, database_id: str) -> None:
        self._client = client
        self._database_id = database_id
        self._headers = {
            "Notion-Version": _NOTION_VERSION,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def create(self, activity: ActivityRecord) -> str:
        resp = await self._client.post(
            f"{_NOTION_BASE}/pages",
            headers=self._headers,
            json={
                "parent": {"database_id": self._database_id},
                "properties": _to_properties(activity),
            },
        )
        resp.raise_for_status()
        page_id: str = resp.json()["id"]
        return page_id

    async def list_recent(
        self, *, deal_id: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return recent activities, newest first, optionally filtered to one Deal."""
        body: dict[str, Any] = {
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            "page_size": limit,
        }
        if deal_id:
            body["filter"] = {"property": "Deal", "relation": {"contains": deal_id}}
        resp = await self._client.post(
            f"{_NOTION_BASE}/databases/{self._database_id}/query",
            headers=self._headers,
            json=body,
        )
        resp.raise_for_status()
        results = []
        for page in resp.json().get("results", []):
            props = page.get("properties", {})
            title_prop = props.get("Name", {}).get("title", [])
            title = title_prop[0]["plain_text"] if title_prop else ""
            type_prop = (props.get("Type", {}).get("select") or {}).get("name", "")
            outcome_prop = (props.get("Outcome", {}).get("select") or {}).get("name", "")
            date_prop = (props.get("Date", {}).get("date") or {}).get("start", "")
            next_step = "".join(
                p.get("plain_text", "") for p in props.get("Next Step", {}).get("rich_text", [])
            )
            next_step_date = (props.get("Next Step Date", {}).get("date") or {}).get("start", "")
            results.append(
                {
                    "page_id": page["id"],
                    "title": title,
                    "type": type_prop,
                    "outcome": outcome_prop,
                    "date": date_prop,
                    "next_step": next_step,
                    "next_step_date": next_step_date,
                }
            )
        return results
