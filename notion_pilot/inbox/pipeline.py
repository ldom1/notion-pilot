"""Generic Notion pipeline factory."""

from collections.abc import Awaitable, Callable

from loguru import logger
from notion_client import APIResponseError
from notion_client import AsyncClient as NotionClient

from notion_pilot.shared.adapters import MessageHandler
from notion_pilot.shared.config import Settings
from notion_pilot.shared.models import IncomingMessage
from notion_pilot.shared.notion import NotionDatabaseWriter

Extract = Callable[[Settings, NotionDatabaseWriter, IncomingMessage], Awaitable[str]]


def build_pipeline(
    settings: Settings,
    database_id: str,
    extract: Extract,
    log_label: str,
) -> MessageHandler:
    """Return a MessageHandler that writes to ``database_id`` using ``extract``."""
    if settings.notion_token is None:
        raise ValueError("NOTION_TOKEN is required for Notion writes")
    notion_client = NotionClient(auth=settings.notion_token.get_secret_value())
    writer = NotionDatabaseWriter(client=notion_client, database_id=database_id)

    async def _handler(incoming: IncomingMessage) -> str | None:
        try:
            page_id = await extract(settings, writer, incoming)
            logger.info("Wrote {} page {} for {}", log_label, page_id, incoming.sender)
            return page_id
        except APIResponseError as exc:
            logger.error("notion API error ({}): {}", log_label, exc)
            return None
        except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
            logger.exception("failed to write {} to notion", log_label)
            return None

    return _handler
