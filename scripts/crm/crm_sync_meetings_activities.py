#!/usr/bin/env python
"""Poll Meetings for checked 'Advanced Deal?' and mirror each to Activities.

Replaces the Notion UI automation (which requires a paid plan) with a Python
polling script. Safe to run repeatedly — processed meeting IDs are stored in
data/crm_meetings_synced.json so no Activity is created twice.

Usage:
    uv run python scripts/crm/crm_sync_meetings_activities.py          # one-shot
    uv run python scripts/crm/crm_sync_meetings_activities.py --watch  # poll every 10 min
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

MEETINGS_ID   = "e94cc98f-2f66-4c53-ac6d-62b9d8f7d5aa"
ACTIVITIES_ID = os.environ.get("NOTION_ACTIVITIES_DATABASE_ID", "38f6c451-9465-8166-a862-e531d15f467f")

# Property names on the Meetings DB (verified 2026-06-30)
TRIGGER_PROP  = "Advanced Deal?"   # checkbox — the sync trigger
PEOPLE_PROP   = "People"           # relation → People DB
DEAL_PROP     = "Deal"             # relation → Deals (Commercial) DB
COMPANY_PROP  = "Company"          # relation → Companies DB
DATE_PROP     = "Date"             # date
OBJECTIVE_PROP = "Meeting Objective"  # rich_text → pre-fills Activity Notes

STATE_FILE = Path(__file__).parent.parent.parent / "data" / "crm_meetings_synced.json"
POLL_INTERVAL = 600  # seconds (10 min)


# ── State helpers ─────────────────────────────────────────────────────────────

def load_synced() -> set[str]:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_synced(ids: set[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(sorted(ids), indent=2))


# ── Notion helpers ────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


async def query_triggered_meetings(client: httpx.AsyncClient, token: str) -> list[dict]:
    """Return all Meetings pages where 'Advanced Deal?' is checked."""
    pages, cursor = [], None
    while True:
        body: dict = {
            "filter": {"property": TRIGGER_PROP, "checkbox": {"equals": True}},
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        r = await client.post(
            f"{NOTION_API}/databases/{MEETINGS_ID}/query",
            headers=_headers(token),
            json=body,
        )
        r.raise_for_status()
        data = r.json()
        pages.extend(data["results"])
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return pages


def _extract_date(props: dict, key: str) -> str | None:
    d = props.get(key, {}).get("date") or {}
    return d.get("start")


def _extract_relations(props: dict, key: str) -> list[dict]:
    return [{"id": r["id"]} for r in props.get(key, {}).get("relation", [])]


def _extract_rich_text(props: dict, key: str) -> str:
    blocks = props.get(key, {}).get("rich_text", [])
    return "".join(b.get("plain_text", "") for b in blocks)


def _extract_title(props: dict) -> str:
    blocks = props.get("Name", {}).get("title", [])
    return "".join(b.get("plain_text", "") for b in blocks)


async def create_activity(client: httpx.AsyncClient, token: str, meeting: dict) -> str:
    """Create one Activity from a Meeting page. Returns the new Activity page ID."""
    props = meeting["properties"]
    meeting_name = _extract_title(props)
    date = _extract_date(props, DATE_PROP)
    deals = _extract_relations(props, DEAL_PROP)
    people = _extract_relations(props, PEOPLE_PROP)
    companies = _extract_relations(props, COMPANY_PROP)
    notes_text = _extract_rich_text(props, OBJECTIVE_PROP)

    activity: dict = {
        "parent": {"database_id": ACTIVITIES_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": meeting_name or "Meeting"}}]},
            "Type": {"select": {"name": "🤝 Meeting"}},
        },
    }

    if date:
        activity["properties"]["Date"] = {"date": {"start": date}}
    if deals:
        activity["properties"]["Deal"] = {"relation": deals[:1]}   # single relation
    if people:
        activity["properties"]["Person"] = {"relation": people[:1]}
    if companies:
        activity["properties"]["Company"] = {"relation": companies[:1]}
    if notes_text:
        activity["properties"]["Notes"] = {
            "rich_text": [{"text": {"content": notes_text[:2000]}}]
        }

    r = await client.post(
        f"{NOTION_API}/pages",
        headers=_headers(token),
        json=activity,
    )
    if r.status_code != 200:
        logger.error("Failed to create Activity for '{}': {} {}", meeting_name, r.status_code, r.text)
        r.raise_for_status()
    return r.json()["id"]


# ── Main sync loop ────────────────────────────────────────────────────────────

async def sync_once(token: str) -> int:
    """Run one sync pass. Returns number of new Activities created."""
    synced = load_synced()
    created = 0

    async with httpx.AsyncClient(timeout=30) as client:
        meetings = await query_triggered_meetings(client, token)
        new_meetings = [m for m in meetings if m["id"] not in synced]

        if not new_meetings:
            logger.info("No new meetings to sync.")
            return 0

        logger.info("{} meeting(s) to sync.", len(new_meetings))
        for meeting in new_meetings:
            name = _extract_title(meeting["properties"])
            try:
                activity_id = await create_activity(client, token, meeting)
                synced.add(meeting["id"])
                logger.info("✅ Created Activity '{}' → {}", name, activity_id)
                created += 1
            except Exception as e:
                logger.error("❌ Skipped '{}': {}", name, e)

    save_synced(synced)
    return created


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Meetings → Activities")
    parser.add_argument("--watch", action="store_true", help=f"Poll every {POLL_INTERVAL}s")
    args = parser.parse_args()

    token = os.environ["NOTION_TOKEN"]

    if args.watch:
        logger.info("Watching Meetings every {}s. Ctrl+C to stop.", POLL_INTERVAL)
        while True:
            await sync_once(token)
            time.sleep(POLL_INTERVAL)
    else:
        n = await sync_once(token)
        logger.info("Done. {} new Activity record(s) created.", n)


if __name__ == "__main__":
    asyncio.run(main())
