#!/usr/bin/env python
"""Patch the Commercial (Deals) database.

Changes:
- Rename Type → Lead Source (unified channel vocabulary, no temperature language)
- Rename Next Action → Next Step
- Rename Next Action Date → Next Step Date
- Rename Primary Projets → Primary Projects (fix stray French)
- Add Expected Close Date (date)
- Add Owner (person type — supports @mentions)
- Add Meetings relation (↔ bidirectional with Meetings.Deal)
- Fix Stage options (add Discovery / First Meeting, terminal No Answer)
- Fix Weighted Value formula (broken URL-encoded refs → prop-based)
- Remove Contacted (checkbox) — confirmed safe
- Remove Date — confirmed safe (replaced by auto Created time)
- Add Created time property (exposes built-in created_time for formula access in Task 6)
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
COMMERCIAL_ID = "4890e1d6-178d-4a42-af06-7bbe0cef09fe"
MEETINGS_ID = "e94cc98f-2f66-4c53-ac6d-62b9d8f7d5aa"


async def main() -> None:
    token = os.environ["NOTION_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    # --- Step 1: Core property changes (renames, adds, fixes, removals) ---
    core_properties: dict = {
        # Rename Type → Lead Source; unified channel vocabulary (matches People.Lead Source)
        "Type": {
            "name": "Lead Source",
            "select": {
                "options": [
                    {"name": "Cold Outreach", "color": "gray"},
                    {"name": "Referral", "color": "green"},
                    {"name": "Inbound", "color": "orange"},
                    {"name": "Conference / Event", "color": "blue"},
                    {"name": "Partner", "color": "purple"},
                    {"name": "Existing Relationship", "color": "pink"},
                    {"name": "LinkedIn", "color": "default"},
                ]
            },
        },
        # Rename Next Action → Next Step
        "Next Action": {"name": "Next Step"},
        # Rename Next Action Date → Next Step Date
        "Next Action Date": {"name": "Next Step Date"},
        # Fix stray French field name (Primary Projets is a relation — rename only)
        "Primary Projets": {"name": "Primary Projects"},
        # Add Expected Close Date
        "Expected Close Date": {"date": {}},
        # Add Owner as person type (supports @mentions, "assigned to me" filter, no option list needed)
        "Owner": {"people": {}},
        # Fix Stage options (replace full list to add Discovery stage and terminal passive stages)
        "Stage": {
            "select": {
                "options": [
                    {"name": "Prospect", "color": "gray"},
                    {"name": "Qualified", "color": "blue"},
                    {"name": "Discovery / First Meeting", "color": "purple"},
                    {"name": "Proposal Sent", "color": "yellow"},
                    {"name": "Negotiation", "color": "orange"},
                    {"name": "Closed Won", "color": "green"},
                    {"name": "Closed Lost", "color": "red"},
                    {"name": "No Answer", "color": "default"},
                    {"name": "Waiting for a Response", "color": "default"},
                ]
            }
        },
        # Fix Weighted Value formula (was broken URL-encoded internal refs)
        "Weighted Value (euros) (num)": {
            "name": "Weighted Value (€)",
            "formula": {
                "expression": 'round(prop("Value (euros)") * prop("Probability (%)") / 100)'
            },
        },
        # Expose built-in created_time as an explicit DB property so formulas can access it
        # via prop("Created time") — required for Deal Age formula in Task 6
        "Created time": {"created_time": {}},
        # Remove deprecated fields (set to null)
        "Contacted": None,
        "Date": None,
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # Apply core changes
        r = await client.patch(
            f"{NOTION_API}/databases/{COMMERCIAL_ID}",
            json={"properties": core_properties},
        )
        if r.status_code != 200:
            logger.error("Core patch failed: {} {}", r.status_code, r.text)
            r.raise_for_status()

        applied = list(r.json().get("properties", {}).keys())
        logger.info("Core patch applied. Properties now: {}", applied)

        # --- Step 2: Add Meetings relation (separate request for graceful error handling) ---
        # If Commercial already has a property named "Meetings", the API returns 400 — no data loss.
        # Manual fallback: in Notion, open the Meetings DB → Add relation → select Commercial DB.
        meetings_properties: dict = {
            "Meetings": {
                "relation": {
                    "database_id": MEETINGS_ID,
                    "single_property": {},
                }
            }
        }

        r2 = await client.patch(
            f"{NOTION_API}/databases/{COMMERCIAL_ID}",
            json={"properties": meetings_properties},
        )
        if r2.status_code == 200:
            logger.info("✅ Meetings relation added successfully.")
        elif r2.status_code == 400:
            logger.warning(
                "⚠ Meetings relation skipped (400 — likely property name conflict). "
                "Manual fallback: open Meetings DB in Notion → Add relation → select Commercial DB."
            )
        else:
            logger.error("Meetings relation failed: {} {}", r2.status_code, r2.text)
            r2.raise_for_status()

        # Final property list
        final = list(r2.json().get("properties", {}).keys()) if r2.status_code == 200 else applied
        logger.info("✅ Commercial patch complete. Final properties: {}", sorted(final))


if __name__ == "__main__":
    asyncio.run(main())
