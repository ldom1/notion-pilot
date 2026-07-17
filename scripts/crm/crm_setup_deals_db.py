"""One-off script: add properties to the existing Deals database in Notion.

The DB shell was created via databases.create() but notion-client 3.x silently
drops the properties arg. This script patches them in via raw httpx.
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

DEALS_ID = "4890e1d6-178d-4a42-af06-7bbe0cef09fe"
NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"

COMPANIES_ID = os.environ.get("NOTION_COMPANIES_DATA_SOURCE_ID", "")
PEOPLE_ID = os.environ.get("NOTION_PEOPLE_DATA_SOURCE_ID", "")


async def main() -> None:
    token = os.environ["NOTION_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    properties: dict = {
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
        "Next Step": {"rich_text": {}},
        "Next Step Date": {"date": {}},
        "Notes": {"rich_text": {}},
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.patch(
            f"{NOTION_API}/databases/{DEALS_ID}",
            json={"properties": properties},
        )
        r.raise_for_status()
        props = r.json().get("properties", {})
        logger.info("Properties applied ({}):", len(props))
        for name, prop in sorted(props.items()):
            logger.info("  {}: {}", name, prop.get("type", "?"))
        logger.info("Add to .env: NOTION_DEALS_DATA_SOURCE_ID={}", DEALS_ID)


if __name__ == "__main__":
    asyncio.run(main())
