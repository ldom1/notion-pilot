"""Shared enrichment + Notion write pipeline."""

from collections.abc import Awaitable, Callable

from loguru import logger
from notion_client import APIResponseError, AsyncClient as NotionClient

from telegram_to_notion.config import Settings
from telegram_to_notion.llm.openrouter import interpret_message
from telegram_to_notion.models import IncomingMessage
from telegram_to_notion.notion import NotionDatabaseWriter

MessageHandler = Callable[[IncomingMessage], Awaitable[str | None]]


async def process_message(
    settings: Settings,
    writer: NotionDatabaseWriter,
    incoming: IncomingMessage,
) -> str:
    """Enrich message via LLM and write to Notion. Returns page_id."""
    notion_properties = await interpret_message(settings, incoming)
    return await writer.create_page(notion_properties)


def build_pipeline(settings: Settings) -> MessageHandler:
    """Return a ready-to-use async handler: IncomingMessage → page_id | None."""
    notion_client = NotionClient(auth=settings.notion_token.get_secret_value())
    writer = NotionDatabaseWriter(
        client=notion_client, database_id=settings.notion_database_id
    )

    async def pipeline(incoming: IncomingMessage) -> str | None:
        try:
            page_id = await process_message(settings, writer, incoming)
            logger.info("Wrote notion page {} from {}", page_id, incoming.sender)
            return page_id
        except APIResponseError as exc:
            logger.error("notion API error: {}", exc)
            return None
        except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
            logger.exception("failed to forward message to notion")
            return None

    return pipeline
