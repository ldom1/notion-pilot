"""Contact pipeline → Notion people database."""

from loguru import logger
from notion_client import APIResponseError
from notion_client import AsyncClient as NotionClient

from telegram_to_notion.adapters import MessageHandler
from telegram_to_notion.config import Settings
from telegram_to_notion.models import IncomingMessage, PersonContactProperties
from telegram_to_notion.notion import NotionDatabaseWriter


def build_people_pipeline(settings: Settings) -> MessageHandler | None:
    """Return a handler that writes a contact row to NOTION_PEOPLE_DATABASE_ID, or None if unconfigured."""
    if not settings.notion_people_database_id:
        return None
    notion_client = NotionClient(auth=settings.notion_token.get_secret_value())
    writer = NotionDatabaseWriter(
        client=notion_client, database_id=settings.notion_people_database_id
    )

    async def _handler(incoming: IncomingMessage) -> str | None:
        try:
            props = PersonContactProperties.from_incoming(incoming)
            page_id = await writer.create_page(props)
            logger.info("Wrote people page {} for {}", page_id, incoming.sender)
            return page_id
        except APIResponseError as exc:
            logger.error("notion API error (people): {}", exc)
            return None
        except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
            logger.exception("failed to write contact to notion")
            return None

    return _handler
