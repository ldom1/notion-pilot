"""Create a full Knowledge workspace in Notion under a given parent page.

Creates four linked databases:
  - Notions  (💡)
  - Ideas    (🧠)
  - Tools    (🛠️)
  - Data & Technology (📊)

Usage:
    uv run python scripts/inbox/setup_workspace.py --parent-id <PAGE_ID_OR_URL>
    uv run python scripts/inbox/setup_workspace.py --parent-id <URL> --page-title "My Knowledge"

Output: prints the four DB IDs to add to .env.
"""

import asyncio
import sys

import httpx
from loguru import logger

from notion_pilot.shared.config import load_settings
from notion_pilot.shared.utils.notion_urls import page_id_from_url
from notion_pilot.shared.workspace import create_inbox_workspace

NOTION_VERSION = "2026-03-11"


def _arg(name: str) -> str | None:
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(f"{name}="):
            return a.split("=", 1)[1]
    return None


async def main(parent_id: str, page_title: str) -> None:
    settings = load_settings()
    token = settings.notion_token.get_secret_value()

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        result = await create_inbox_workspace(client, parent_id, page_title)

    logger.info("")
    logger.info("✅  Knowledge workspace ready — add to .env:")
    logger.info("  NOTION_DATABASE_ID={}", result.notions_id)
    logger.info("  NOTION_IDEAS_DATABASE_ID={}", result.ideas_id)
    logger.info("  NOTION_TOOLS_DATABASE_ID={}", result.tools_id)
    logger.info("  NOTION_DATA_TECH_DATABASE_ID={}", result.data_tech_id)


if __name__ == "__main__":
    _parent = _arg("--parent-id")
    if not _parent:
        logger.error("Usage: uv run python scripts/inbox/setup_workspace.py --parent-id <PAGE_ID_OR_URL>")
        sys.exit(1)
    _title = _arg("--page-title") or "Knowledge"
    asyncio.run(main(page_id_from_url(_parent), _title))
