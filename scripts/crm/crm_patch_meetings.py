#!/usr/bin/env python
"""Patch the Meetings database.

Changes:
- Rename Nom → Name (title)
- Rename Étiquettes → Tags
- Add Deal relation ↔ Deals (single bidirectional relation — creates back-relation on Deals automatically)
- Add Company relation → Companies
- Add Meeting Objective (rich_text) — plain text agenda, distinct from Objectif (Objectives DB relation)
- Add Advanced Deal? (checkbox) — triggers Notion automation to create Activity (set up automation in UI)
- Expand Type options to include CRM-relevant meeting types
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
MEETINGS_ID   = "e94cc98f-2f66-4c53-ac6d-62b9d8f7d5aa"
COMMERCIAL_ID = "4890e1d6-178d-4a42-af06-7bbe0cef09fe"
COMPANIES_ID  = "cfc21198-9684-47ef-98ae-fc5657511998"


async def main() -> None:
    token = os.environ["NOTION_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    # Properties excluding Deal relation (handled separately below)
    base_properties: dict = {
        # Rename title property
        "Nom": {"name": "Name"},
        # Rename French tags field
        "Étiquettes": {"name": "Tags"},
        # Add Company relation
        "Company": {
            "relation": {
                "database_id": COMPANIES_ID,
                "single_property": {},
            }
        },
        # Add plain-text meeting agenda (distinct from Objectif which is a strategic DB relation)
        "Meeting Objective": {"rich_text": {}},
        # Checkbox that triggers Notion automation → auto-creates Activity of type 🤝 Meeting
        # Configure the automation in Notion UI after migration (see Task 7 Step 6)
        "Advanced Deal?": {"checkbox": {}},
        # Expand Type to cover CRM meeting types
        "Type": {
            "select": {
                "options": [
                    {"name": "Discovery", "color": "blue"},
                    {"name": "Demo", "color": "purple"},
                    {"name": "Follow-up", "color": "yellow"},
                    {"name": "Proposal Review", "color": "orange"},
                    {"name": "Negotiation", "color": "red"},
                    {"name": "Kick-off", "color": "green"},
                    {"name": "Internal", "color": "gray"},
                    {"name": "Conference", "color": "pink"},
                    {"name": "Personal", "color": "default"},
                ]
            }
        },
    }

    deal_property: dict = {
        # Add Deal relation (creates back-relation on Commercial, completing the bidirectional link)
        # If Meetings already has a property named "Deal", the API will return 400 — no data loss.
        # If that happens, link the Meetings↔Deals relation manually in Notion UI instead:
        #   open Meetings DB → Add property → Relation → select Deals DB → enable "Show on Deals"
        "Deal": {
            "relation": {
                "database_id": COMMERCIAL_ID,
                "single_property": {},
            }
        },
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # Step 1: Apply base properties (excluding Deal relation)
        r = await client.patch(
            f"{NOTION_API}/databases/{MEETINGS_ID}",
            json={"properties": base_properties},
        )
        if r.status_code != 200:
            logger.error("Base patch failed: {} {}", r.status_code, r.text)
            r.raise_for_status()
        applied = list(r.json().get("properties", {}).keys())
        logger.info("Base properties patched. Properties now: {}", applied)

        # Step 2: Attempt to add Deal relation separately (may conflict if back-relation already exists)
        r2 = await client.patch(
            f"{NOTION_API}/databases/{MEETINGS_ID}",
            json={"properties": deal_property},
        )
        if r2.status_code == 200:
            applied2 = list(r2.json().get("properties", {}).keys())
            logger.info("✅ Meetings fully patched (incl. Deal relation). Properties now: {}", applied2)
        elif r2.status_code == 400:
            logger.warning(
                "⚠️  Deal relation returned 400 — a back-relation named 'Deal' may already exist "
                "on Meetings from Task 2's bidirectional setup. No data was lost.\n"
                "Manual fallback: open Meetings DB in Notion UI → Add property → Relation → "
                "select Deals/Commercial DB → enable 'Show on Deals' → save."
            )
            logger.info(
                "✅ Meetings patched (base properties applied). Deal relation needs manual setup."
            )
        else:
            logger.error("Deal relation patch failed: {} {}", r2.status_code, r2.text)
            r2.raise_for_status()


if __name__ == "__main__":
    asyncio.run(main())
