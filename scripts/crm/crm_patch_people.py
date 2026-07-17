#!/usr/bin/env python
"""Patch the People database.

Changes:
- Rename Nom → Name (title property)
- Rename Profile → Priority (rename options: Normal→🧊 Cold, 🔥 Key→🔥 Hot, add 🌡 Warm)
- Rename In my network → Relationship (options: Non→Cold, Yes→Warm, add Close)
- Add Lead Source (select)
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
PEOPLE_ID = "11b5f43c-a19a-4bec-9489-7c6897ed30fb"


async def main() -> None:
    token = os.environ["NOTION_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    properties: dict = {
        # Rename title property Nom → Name
        "Nom": {"name": "Name"},
        # Rename Profile → Priority with better options
        "Profile": {
            "name": "Priority",
            "select": {
                "options": [
                    {"name": "🔥 Hot", "color": "red"},
                    {"name": "🌡 Warm", "color": "yellow"},
                    {"name": "🧊 Cold", "color": "blue"},
                ]
            },
        },
        # Rename In my network → Relationship with richer options
        "In my network": {
            "name": "Relationship",
            "select": {
                "options": [
                    {"name": "Close", "color": "green"},
                    {"name": "Warm", "color": "yellow"},
                    {"name": "Cold", "color": "blue"},
                    {"name": "None", "color": "gray"},
                ]
            },
        },
        # Add Lead Source — same 7 options as Deals.Lead Source (mirror manually if options change)
        "Lead Source": {
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
            }
        },
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.patch(
            f"{NOTION_API}/databases/{PEOPLE_ID}",
            json={"properties": properties},
        )
        if r.status_code != 200:
            logger.error("Failed: {} {}", r.status_code, r.text)
            r.raise_for_status()
        applied = list(r.json().get("properties", {}).keys())
        logger.info("✅ People patched. Properties now: {}", applied)


if __name__ == "__main__":
    asyncio.run(main())
