#!/usr/bin/env python
"""Patch the Companies database.

Changes:
- Add Revenue Potential (select)
- Fix Size: remove duplicate / non-standard buckets (keep only 7 standard)
- Rationalize Sector: replace 100+ LinkedIn-imported values with 11-value clean taxonomy
- Remove Link (generic unused url field)

NOTE: Market Segment already exists as multi_select (no rename needed).
NOTE: Activities is a relation field — unrelated to Market Segment, left untouched.
NOTE: Sector rationalization adds clean options. Existing pages with old sector
values will not break — Notion keeps old tags on pages, they just won't appear
in the new options list. Manually re-tag via Notion UI filter after migration.
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
COMPANIES_ID = "cfc21198-9684-47ef-98ae-fc5657511998"


async def main() -> None:
    token = os.environ["NOTION_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    properties: dict = {
        # Add Revenue Potential
        "Revenue Potential": {
            "select": {
                "options": [
                    {"name": "High", "color": "green"},
                    {"name": "Medium", "color": "yellow"},
                    {"name": "Low", "color": "gray"},
                ]
            }
        },
        # Rationalize Sector taxonomy (replaces messy LinkedIn-imported list)
        # Existing page values outside this list are preserved on pages but hidden from dropdown
        # Colors are omitted: Notion rejects color changes on existing options — let it
        # keep existing colors for matches and auto-assign for new entries.
        "Sector": {
            "select": {
                "options": [
                    {"name": "Energy & Utilities"},
                    {"name": "Software & SaaS"},
                    {"name": "IT Services & Consulting"},
                    {"name": "Manufacturing & Industrial"},
                    {"name": "Financial Services"},
                    {"name": "Government & Public Sector"},
                    {"name": "Research & Academia"},
                    {"name": "Defense & Aerospace"},
                    {"name": "Healthcare & Life Sciences"},
                    {"name": "Infrastructure & Transport"},
                    {"name": "Other"},
                ]
            }
        },
        # Fix Size: remove non-standard buckets (keep only 7 standard)
        # Colors omitted for the same reason as Sector — Notion rejects color changes on existing options.
        "Size": {
            "select": {
                "options": [
                    {"name": "1-10"},
                    {"name": "11-50"},
                    {"name": "51-200"},
                    {"name": "201-500"},
                    {"name": "501-2000"},
                    {"name": "2001-10000"},
                    {"name": "10000+"},
                ]
            }
        },
        # Remove generic Link field
        "Link": None,
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.patch(
            f"{NOTION_API}/databases/{COMPANIES_ID}",
            json={"properties": properties},
        )
        if r.status_code != 200:
            logger.error("Failed: {} {}", r.status_code, r.text)
            r.raise_for_status()
        applied = list(r.json().get("properties", {}).keys())
        logger.info("✅ Companies patched. Properties now: {}", applied)


if __name__ == "__main__":
    asyncio.run(main())
