"""LLM-enriched pipeline → main Notion knowledge database."""

from notion_pilot.inbox.pipeline import build_pipeline
from notion_pilot.shared.adapters import MessageHandler
from notion_pilot.shared.config import Settings
from notion_pilot.shared.llm.link_metadata import fetch_link_metadata
from notion_pilot.shared.llm.openrouter import interpret_message
from notion_pilot.shared.llm.synthesis import (
    build_link_body_blocks,
    synthesize_multi_link_description,
)
from notion_pilot.shared.models import IncomingMessage, all_urls
from notion_pilot.shared.notion import NotionDatabaseWriter

_MULTI_LINK_THRESHOLD = 2


async def process_message(
    settings: Settings,
    writer: NotionDatabaseWriter,
    incoming: IncomingMessage,
) -> str:
    """Enrich message via LLM and write to Notion. Returns page_id.

    Messages with >= _MULTI_LINK_THRESHOLD URLs take the richer multi-link
    path: fetch factual metadata per link, synthesize a set-level Description,
    and write one heading+bullets group per link to the page body. Single/zero
    -URL messages are unchanged (one-shot LLM call, properties only)."""
    urls = all_urls(incoming.body)
    if len(urls) >= _MULTI_LINK_THRESHOLD:
        notion_properties = await interpret_message(settings, incoming)
        metadata = await fetch_link_metadata(urls)
        description = await synthesize_multi_link_description(settings, incoming, metadata)
        notion_properties = notion_properties.model_copy(update={"description": description})
        children = build_link_body_blocks(metadata)
        return await writer.create_page(notion_properties, children=children)

    notion_properties = await interpret_message(settings, incoming)
    return await writer.create_page(notion_properties)


def build_knowledge_pipeline(settings: Settings) -> MessageHandler:
    """Return a handler that enriches via LLM and writes to the main knowledge DB."""
    return build_pipeline(
        settings, settings.notion_telegram_msg_database_id, process_message, "knowledge"
    )
