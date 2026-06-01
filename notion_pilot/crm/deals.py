"""Notion Deals syncer — standard databases API (not data_sources)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

_NOTION_VERSION = "2022-06-28"
_NOTION_BASE = "https://api.notion.com/v1"


@dataclass
class DealRecord:
    title: str
    stage: str = "Prospect"
    product: list[str] = field(default_factory=list)
    value_euros: float | None = None
    probability_pct: int | None = None
    next_action: str = ""
    next_action_date: str = ""
    notes: str = ""
    people_ids: list[str] = field(default_factory=list)
    company_ids: list[str] = field(default_factory=list)


@dataclass
class DealUpsertResult:
    page_id: str
    created: bool


class NotionDealsSyncer:
    """Create and update Deals pages. Uses raw httpx — Deals DB created via databases.create()."""

    def __init__(self, client: httpx.AsyncClient, token: str, database_id: str) -> None:
        self._client = client
        self._database_id = database_id
        self._headers = {
            "Notion-Version": _NOTION_VERSION,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._snapshot: dict[str, str] = {}  # title → page_id

    def _to_properties(self, deal: DealRecord) -> dict[str, Any]:
        props: dict[str, Any] = {
            "Name": {"title": [{"text": {"content": deal.title}}]},
        }
        if deal.stage:
            props["Stage"] = {"select": {"name": deal.stage}}
        if deal.product:
            props["Product"] = {"multi_select": [{"name": p} for p in deal.product]}
        if deal.value_euros is not None:
            props["Value (euros)"] = {"number": deal.value_euros}
        if deal.probability_pct is not None:
            props["Probability (%)"] = {"number": deal.probability_pct}
        if deal.next_action:
            props["Next Action"] = {"rich_text": [{"text": {"content": deal.next_action}}]}
        if deal.next_action_date:
            props["Next Action Date"] = {"date": {"start": deal.next_action_date}}
        if deal.notes:
            props["Notes"] = {"rich_text": [{"text": {"content": deal.notes}}]}
        if deal.people_ids:
            props["Contacts"] = {"relation": [{"id": pid} for pid in deal.people_ids]}
        if deal.company_ids:
            props["Client"] = {"relation": [{"id": cid} for cid in deal.company_ids]}
        return props

    async def create(self, deal: DealRecord) -> str:
        resp = await self._client.post(
            f"{_NOTION_BASE}/pages",
            headers=self._headers,
            json={
                "parent": {"database_id": self._database_id},
                "properties": self._to_properties(deal),
            },
        )
        resp.raise_for_status()
        page_id: str = resp.json()["id"]
        self._snapshot[deal.title] = page_id
        return page_id

    async def _patch(self, page_id: str, deal: DealRecord) -> None:
        resp = await self._client.patch(
            f"{_NOTION_BASE}/pages/{page_id}",
            headers=self._headers,
            json={"properties": self._to_properties(deal)},
        )
        resp.raise_for_status()

    async def upsert(self, deal: DealRecord) -> tuple[str, bool]:
        """Return (page_id, created). Matches on exact title."""
        if deal.title in self._snapshot:
            page_id = self._snapshot[deal.title]
            await self._patch(page_id, deal)
            return page_id, False
        page_id = await self.create(deal)
        return page_id, True

    async def load_snapshot(self) -> None:
        """Load existing deals into memory. Call once at startup."""
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            resp = await self._client.post(
                f"{_NOTION_BASE}/databases/{self._database_id}/query",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            for page in data["results"]:
                name_prop = page["properties"].get("Name", {})
                if name_prop.get("title"):
                    title = name_prop["title"][0]["plain_text"]
                    self._snapshot[title] = page["id"]
            if not data.get("has_more"):
                break
            cursor = data["next_cursor"]
