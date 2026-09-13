"""Refresh the CRM home page of an existing CRM in place.

Replaces Notion Pilot's own template blocks and views; keeps the databases, their
rows, and anything you added. View ids are kept in data/crm_views/<page-id>.json
so the next run replaces its views instead of duplicating them.

Usage:
    uv run python scripts/crm/crm_upgrade_home.py --crm-page-id <PAGE_ID_OR_URL>
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
from loguru import logger

from notion_pilot.shared.config import load_settings
from notion_pilot.shared.utils.notion_urls import page_id_from_url
from notion_pilot.shared.workspace import NOTION_VERSION, upgrade_crm_home

VIEWS_DIR = Path("data/crm_views")


async def main(crm_page_id: str) -> None:
    token = load_settings().notion_token.get_secret_value()
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    views_file = VIEWS_DIR / f"{crm_page_id}.json"
    previous = json.loads(views_file.read_text()) if views_file.exists() else None
    async with httpx.AsyncClient(headers=headers, timeout=60) as client:
        result = await upgrade_crm_home(client, crm_page_id, previous_views=previous)
    VIEWS_DIR.mkdir(parents=True, exist_ok=True)
    views_file.write_text(json.dumps(result.views, indent=2))
    logger.info("CRM home refreshed — {} of 4 views created", len(result.views))
    for warning in result.warnings:
        logger.warning(warning)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--crm-page-id":
        logger.error("Usage: uv run python scripts/crm/crm_upgrade_home.py --crm-page-id <PAGE_ID_OR_URL>")
        sys.exit(1)
    asyncio.run(main(page_id_from_url(sys.argv[2])))
