#!/usr/bin/env python
"""Create the Activities database under the CRM parent page.

Run once. Prints the new DB ID — add to .env as NOTION_ACTIVITIES_DATABASE_ID.
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
COMPANIES_ID = "cfc21198-9684-47ef-98ae-fc5657511998"
PEOPLE_ID = "11b5f43c-a19a-4bec-9489-7c6897ed30fb"
CRM_PARENT_PAGE_ID = "36d6c451-9465-80b7-af00-d80250f0974c"


async def main() -> None:
    token = os.environ["NOTION_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    payload = {
        "parent": {"type": "page_id", "page_id": CRM_PARENT_PAGE_ID},
        "icon": {"type": "emoji", "emoji": "⚡"},
        "title": [{"type": "text", "text": {"content": "Activities"}}],
        "properties": {
            "Name": {"title": {}},
            "Type": {
                "select": {
                    "options": [
                        {"name": "📞 Call", "color": "blue"},
                        {"name": "📧 Email", "color": "green"},
                        {"name": "💼 LinkedIn", "color": "purple"},
                        {"name": "🎤 Demo", "color": "orange"},
                        {"name": "🤝 Meeting", "color": "yellow"},
                        {"name": "📄 Proposal", "color": "red"},
                        {"name": "🎪 Conference", "color": "pink"},
                        {"name": "📋 Other", "color": "gray"},
                    ]
                }
            },
            "Date": {"date": {}},
            "Duration (min)": {"number": {"format": "number"}},
            "Deal": {
                "relation": {
                    "database_id": COMMERCIAL_ID,
                    "single_property": {},
                }
            },
            "Person": {
                "relation": {
                    "database_id": PEOPLE_ID,
                    "single_property": {},
                }
            },
            "Company": {
                "relation": {
                    "database_id": COMPANIES_ID,
                    "single_property": {},
                }
            },
            "Outcome": {
                "select": {
                    "options": [
                        {"name": "✅ Positive", "color": "green"},
                        {"name": "➡️ Follow-up Needed", "color": "yellow"},
                        {"name": "❌ Negative", "color": "red"},
                        {"name": "🔇 No Response", "color": "gray"},
                    ]
                }
            },
            "Notes": {"rich_text": {}},
            "Next Step": {"rich_text": {}},
            "Next Step Date": {"date": {}},
            "Owner": {
                "people": {}
            },  # person type — supports @mentions, no manual option list needed
        },
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{NOTION_API}/databases", json=payload)
        if r.status_code != 200:
            logger.error("Failed: {} {}", r.status_code, r.text)
            r.raise_for_status()
        db_id = r.json()["id"]
        logger.info("✅ Activities DB created: {}", db_id)
        logger.info("Add to .env: NOTION_ACTIVITIES_DATABASE_ID={}", db_id)


if __name__ == "__main__":
    asyncio.run(main())
