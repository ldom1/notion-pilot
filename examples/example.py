"""End-to-end example: Telegram-style message → OpenRouter enrichment → Notion page.

Run with:
    uv run python examples/example.py
"""

import asyncio
from datetime import datetime, timezone

from loguru import logger
from notion_client import AsyncClient as NotionClient

from notion_pilot.config import load_settings
from notion_pilot.llm.openrouter import interpret_message
from notion_pilot.models import IncomingMessage, MediaType
from notion_pilot.notion import NotionDatabaseWriter


async def main() -> None:
    settings = load_settings()

    # Step 1 — Build a normalized inbound message (what the bot produces from Telegram).
    incoming = IncomingMessage(
        text="J'ai trouvé un nouvel outil hyper intéressant: https://github.com/ldom1/telegram-to-notion",
        caption=None,
        sender="example.py",
        sent_at=datetime.now(timezone.utc),
        media_type=MediaType.TEXT,
        media=None,
    )
    logger.info(f"[1/3] Incoming message: {incoming.name!r}")

    # Step 2 — Ask OpenRouter to enrich it into structured Notion properties.
    properties = await interpret_message(settings, incoming)
    logger.info(f"[2/3] Generate notion properties: {properties!r}")

    # Step 3 — Write a page to the Notion database.
    client = NotionClient(auth=settings.notion_token.get_secret_value())
    writer = NotionDatabaseWriter(client=client, database_id=settings.notion_database_id)
    page_id = await writer.create_page(properties)
    logger.info(f"[3/3] Notion page created: {page_id}")


if __name__ == "__main__":
    asyncio.run(main())
