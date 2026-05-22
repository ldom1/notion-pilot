"""Create a full CRM workspace in Notion under a given parent page.

Creates three linked databases:
  - Companies   (root, no relations)
  - People      (relation → Companies)
  - Deals       (relations → Companies + People)

Usage:
    uv run python scripts/setup_crm.py --parent-id <PAGE_ID_OR_URL>
    uv run python scripts/setup_crm.py --parent-id <PAGE_ID_OR_URL> --page-title "My CRM"

Output: prints the three DB IDs to add to .env.

Note: notion-client 3.x silently drops the `properties` arg on databases.create().
This script uses raw httpx calls to ensure properties are applied correctly.
"""
import asyncio
import sys
from typing import Any

import httpx
from loguru import logger

from telegram_to_notion.config import load_settings

NOTION_VERSION = "2026-03-11"
NOTION_API = "https://api.notion.com/v1"


def _arg(name: str) -> str | None:
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(f"{name}="):
            return a.split("=", 1)[1]
    return None


def _page_id_from_url(value: str) -> str:
    """Accept a raw UUID or a Notion URL and return a hyphenated UUID."""
    value = value.split("?")[0].split("#")[0]
    segment = value.rstrip("/").rsplit("/", 1)[-1]
    raw = segment.rsplit("-", 1)[-1] if "-" in segment else segment
    if len(raw) == 32:  # noqa: PLR2004
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return raw


async def _create_page(client: httpx.AsyncClient, parent_page_id: str, title: str, emoji: str) -> str:
    r = await client.post(
        f"{NOTION_API}/pages",
        json={
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "icon": {"type": "emoji", "emoji": emoji},
            "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        },
    )
    r.raise_for_status()
    return r.json()["id"]


async def _create_db(
    client: httpx.AsyncClient,
    parent_page_id: str,
    title: str,
    properties: dict[str, Any],
    emoji: str,
) -> str:
    """Create a DB and immediately PATCH its properties (workaround for notion-client 3.x)."""
    # Step 1: create shell
    r = await client.post(
        f"{NOTION_API}/databases",
        json={
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "icon": {"type": "emoji", "emoji": emoji},
            "title": [{"type": "text", "text": {"content": title}}],
        },
    )
    r.raise_for_status()
    db_id: str = r.json()["id"]

    # Step 2: patch properties
    r2 = await client.patch(f"{NOTION_API}/databases/{db_id}", json={"properties": properties})
    r2.raise_for_status()
    return db_id


async def main(parent_id: str, page_title: str) -> None:
    settings = load_settings()
    token = settings.notion_token.get_secret_value()

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # ── 1. CRM container page ────────────────────────────────────────────
        logger.info("Creating CRM container page '{}'…", page_title)
        crm_page_id = await _create_page(client, parent_id, page_title, "🏢")
        logger.info("  page id={}", crm_page_id)

        # ── 2. Companies DB ──────────────────────────────────────────────────
        logger.info("Creating Companies DB…")
        companies_id = await _create_db(
            client,
            crm_page_id,
            "Companies",
            {
                "Name": {"title": {}},
                "Sector": {
                    "select": {
                        "options": [
                            {"name": "Energy", "color": "yellow"},
                            {"name": "Finance", "color": "green"},
                            {"name": "Industry", "color": "blue"},
                            {"name": "Public Sector", "color": "purple"},
                            {"name": "Telecom", "color": "orange"},
                            {"name": "Other", "color": "gray"},
                        ]
                    }
                },
                "Website": {"url": {}},
                "Notes": {"rich_text": {}},
            },
            "🏭",
        )
        logger.info("  Companies id={}", companies_id)

        # ── 3. People DB (relation → Companies) ─────────────────────────────
        logger.info("Creating People DB…")
        people_id = await _create_db(
            client,
            crm_page_id,
            "People",
            {
                "Name": {"title": {}},
                "Company": {"relation": {"database_id": companies_id, "single_property": {}}},
                "Position": {"rich_text": {}},
                "LinkedIn": {"url": {}},
                "Email": {"email": {}},
                "Notes": {"rich_text": {}},
            },
            "👥",
        )
        logger.info("  People id={}", people_id)

        # ── 4. Deals DB (relations → Companies + People) ─────────────────────
        logger.info("Creating Deals DB…")
        deals_id = await _create_db(
            client,
            crm_page_id,
            "Deals",
            {
                "Name": {"title": {}},
                "Company": {"relation": {"database_id": companies_id, "single_property": {}}},
                "Contact": {"relation": {"database_id": people_id, "single_property": {}}},
                "Stage": {
                    "select": {
                        "options": [
                            {"name": "Prospect", "color": "gray"},
                            {"name": "Qualified", "color": "blue"},
                            {"name": "Proposal Sent", "color": "yellow"},
                            {"name": "Negotiation", "color": "orange"},
                            {"name": "Closed Won", "color": "green"},
                            {"name": "Closed Lost", "color": "red"},
                        ]
                    }
                },
                "Product": {
                    "multi_select": {
                        "options": [
                            {"name": "HPC-as-a-service"},
                            {"name": "Consulting"},
                            {"name": "Optimization"},
                            {"name": "Training"},
                        ]
                    }
                },
                "Value (euros)": {"number": {"format": "euro"}},
                "Probability (%)": {"number": {"format": "percent"}},
                "Weighted Value (euros)": {
                    "formula": {
                        "expression": 'formatNumber(round((prop("Value (euros)") * prop("Probability (%)"))), "eur")'
                    }
                },
                "Next Action": {"rich_text": {}},
                "Next Action Date": {"date": {}},
                "Notes": {"rich_text": {}},
            },
            "💼",
        )
        logger.info("  Deals id={}", deals_id)

    logger.info("")
    logger.info("✅  CRM workspace ready — add to .env:")
    logger.info("  NOTION_COMPANIES_DATA_SOURCE_ID={}", companies_id)
    logger.info("  NOTION_PEOPLE_DATA_SOURCE_ID={}", people_id)
    logger.info("  NOTION_DEALS_DATA_SOURCE_ID={}", deals_id)


if __name__ == "__main__":
    _parent = _arg("--parent-id")
    if not _parent:
        logger.error("Usage: uv run python scripts/setup_crm.py --parent-id <PAGE_ID_OR_URL>")
        sys.exit(1)
    _title = _arg("--page-title") or "CRM"
    asyncio.run(main(_page_id_from_url(_parent), _title))
