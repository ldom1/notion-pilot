"""Contact pipeline → Notion people database."""

from telegram_to_notion.adapters import MessageHandler
from telegram_to_notion.config import Settings
from telegram_to_notion.models import IncomingMessage, PersonContactProperties
from telegram_to_notion.notion import NotionDatabaseWriter
from telegram_to_notion.pipelines.pipeline import build_pipeline


async def _write_contact(
    settings: Settings,
    writer: NotionDatabaseWriter,
    incoming: IncomingMessage,
) -> str:
    props = PersonContactProperties.from_incoming(incoming)
    return await writer.create_page(props)


def build_people_pipeline(settings: Settings) -> MessageHandler | None:
    """Return a handler that writes a contact row to NOTION_PEOPLE_DATABASE_ID, or None if unconfigured."""
    if not settings.notion_people_database_id:
        return None
    return build_pipeline(settings, settings.notion_people_database_id, _write_contact, "people")
