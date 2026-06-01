"""Contact pipeline → Notion people database."""

from notion_pilot.inbox.pipeline import build_pipeline
from notion_pilot.shared.adapters import MessageHandler
from notion_pilot.shared.config import Settings
from notion_pilot.shared.models import IncomingMessage, PersonContactProperties
from notion_pilot.shared.notion import NotionDatabaseWriter


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
