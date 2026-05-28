"""LLM-enriched pipeline → main Notion knowledge database."""

from telegram_to_notion.adapters import MessageHandler
from telegram_to_notion.config import Settings
from telegram_to_notion.llm.openrouter import interpret_message
from telegram_to_notion.models import IncomingMessage
from telegram_to_notion.notion import NotionDatabaseWriter
from telegram_to_notion.pipelines.pipeline import build_pipeline


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
