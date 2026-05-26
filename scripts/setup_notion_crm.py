#!/usr/bin/env python
"""Add new CRM properties to existing People and Companies databases.

Safe to re-run: existing properties are left untouched.

Usage:
    uv run python scripts/setup_notion_crm.py
"""
import asyncio
import sys

import httpx
from loguru import logger

from telegram_to_notion.config import load_settings

_NOTION_VERSION = "2026-03-11"
_NOTION_BASE = "https://api.notion.com/v1"

_PEOPLE_NEW_PROPS = {
    "Phone": {"phone_number": {}},
    "Seniority": {
        "select": {
            "options": [
                {"name": "founder", "color": "red"},
                {"name": "c_suite", "color": "orange"},
                {"name": "vp", "color": "yellow"},
                {"name": "director", "color": "green"},
                {"name": "manager", "color": "blue"},
                {"name": "senior", "color": "purple"},
                {"name": "mid", "color": "pink"},
                {"name": "junior", "color": "gray"},
            ]
        }
    },
    "Role Type": {"multi_select": {"options": []}},
}

_COMPANIES_NEW_PROPS = {
    "Size": {
        "select": {
            "options": [
                {"name": s, "color": "default"}
                for s in ["1-10", "11-50", "51-200", "201-500", "501-2000", "2001-10000", "10000+"]
            ]
        }
    },
    "CRM Status": {
        "select": {
            "options": [
                {"name": s, "color": "default"}
                for s in ["Prospect", "Active", "Partner", "Churned"]
            ]
        }
    },
    "Tier": {
        "select": {
            "options": [{"name": t, "color": "default"} for t in ["1", "2", "3"]]
        }
    },
    "Tech Stack": {"multi_select": {"options": []}},
    "Country": {"select": {"options": []}},
}


async def _patch_database(client: httpx.AsyncClient, token: str, db_id: str, props: dict) -> None:
    resp = await client.patch(
        f"{_NOTION_BASE}/databases/{db_id}",
        headers={
            "Notion-Version": _NOTION_VERSION,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"properties": props},
    )
    if resp.status_code == 200:
        logger.info("Updated database {}", db_id)
    else:
        logger.error("Failed to update {}: {} {}", db_id, resp.status_code, resp.text)
        resp.raise_for_status()


async def main() -> None:
    settings = load_settings()
    token = settings.notion_token.get_secret_value()

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        if settings.notion_people_data_source_id:
            logger.info("Patching People DB ({})...", settings.notion_people_data_source_id)
            await _patch_database(client, token, settings.notion_people_data_source_id, _PEOPLE_NEW_PROPS)
        else:
            logger.warning("NOTION_PEOPLE_DATA_SOURCE_ID not set — skipping People DB")

        if settings.notion_companies_data_source_id:
            logger.info("Patching Companies DB ({})...", settings.notion_companies_data_source_id)
            await _patch_database(client, token, settings.notion_companies_data_source_id, _COMPANIES_NEW_PROPS)
        else:
            logger.warning("NOTION_COMPANIES_DATA_SOURCE_ID not set — skipping Companies DB")


if __name__ == "__main__":
    asyncio.run(main())
