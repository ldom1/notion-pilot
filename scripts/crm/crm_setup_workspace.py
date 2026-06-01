"""Create a full CRM workspace in Notion under a given parent page.

Creates three linked databases:
  - Companies  (🏭)
  - People     (👥, relation → Companies)
  - Deals      (💼, relations → Companies + People)

Usage:
    uv run python scripts/crm/crm_setup_workspace.py --parent-id <PAGE_ID_OR_URL>
    uv run python scripts/crm/crm_setup_workspace.py --parent-id <URL> --with-inbox
    uv run python scripts/crm/crm_setup_workspace.py --parent-id <URL> --page-title "My CRM"

Output: prints the DB IDs to add to .env.
"""

import asyncio
import sys

import httpx
from loguru import logger

from notion_pilot.shared.config import load_settings
from notion_pilot.shared.utils.notion_urls import page_id_from_url
from notion_pilot.shared.workspace import create_crm_workspace, create_inbox_workspace

NOTION_VERSION = "2022-06-28"


def _arg(name: str) -> str | None:
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(f"{name}="):
            return a.split("=", 1)[1]
    return None


def _flag(name: str) -> bool:
    return name in sys.argv


async def main(parent_id: str, page_title: str, with_inbox: bool) -> None:
    settings = load_settings()
    token = settings.notion_token.get_secret_value()
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        crm = await create_crm_workspace(client, parent_id, page_title)
        logger.info("")
        logger.info("✅  CRM workspace ready — add to .env:")
        logger.info("  NOTION_COMPANIES_DATA_SOURCE_ID={}", crm.companies_id)
        logger.info("  NOTION_PEOPLE_DATA_SOURCE_ID={}", crm.people_id)
        logger.info("  NOTION_DEALS_DATABASE_ID={}", crm.deals_id)

        if with_inbox:
            inbox = await create_inbox_workspace(client, parent_id)
            logger.info("")
            logger.info("✅  Knowledge workspace ready — add to .env:")
            logger.info("  NOTION_DATABASE_ID={}", inbox.notions_id)
            logger.info("  NOTION_IDEAS_DATABASE_ID={}", inbox.ideas_id)
            logger.info("  NOTION_TOOLS_DATABASE_ID={}", inbox.tools_id)
            logger.info("  NOTION_DATA_TECH_DATABASE_ID={}", inbox.data_tech_id)


if __name__ == "__main__":
    _parent = _arg("--parent-id")
    if not _parent:
        logger.error(
            "Usage: uv run python scripts/crm/crm_setup_workspace.py --parent-id <URL> [--with-inbox]"
        )
        sys.exit(1)
    _title = _arg("--page-title") or "CRM"
    asyncio.run(main(page_id_from_url(_parent), _title, _flag("--with-inbox")))
