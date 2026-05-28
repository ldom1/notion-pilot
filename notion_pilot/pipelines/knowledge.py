"""LLM-enriched pipeline → main Notion knowledge database."""

from notion_pilot.adapters import MessageHandler
from notion_pilot.config import Settings
from notion_pilot.llm.openrouter import interpret_message
from notion_pilot.models import IncomingMessage
from notion_pilot.notion import NotionDatabaseWriter
from notion_pilot.pipelines.pipeline import build_pipeline


async def process_message(
    settings: Settings,
    writer: NotionDatabaseWriter,
    incoming: IncomingMessage,
) -> str:
    """Enrich message via LLM and write to Notion. Returns page_id."""
    notion_properties = await interpret_message(settings, incoming)
    return await writer.create_page(notion_properties)


def build_knowledge_pipeline(settings: Settings) -> MessageHandler:
    """Return a handler that enriches via LLM and writes to the main knowledge DB."""
    return build_pipeline(settings, settings.notion_database_id, process_message, "knowledge")
