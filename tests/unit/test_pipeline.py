"""Unit tests for the knowledge pipeline — mocks Notion writer and LLM."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notion_pilot.shared.config import Settings
from notion_pilot.shared.models import IncomingMessage, MediaType, NotionDatabaseProperties
from notion_pilot.inbox.knowledge import process_message


def _make_incoming() -> IncomingMessage:
    return IncomingMessage(
        text="Hello pipeline",
        caption=None,
        sender="tester",
        sent_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        media_type=MediaType.TEXT,
        media=None,
        source_adapter="telegram",
    )


@pytest.mark.asyncio
async def test_process_message_returns_page_id():
    props = NotionDatabaseProperties(name="T", description="D")
    mock_settings = MagicMock(spec=Settings)
    mock_writer = AsyncMock()
    mock_writer.create_page.return_value = "page-abc"

    with patch(
        "notion_pilot.inbox.knowledge.interpret_message",
        new_callable=AsyncMock,
        return_value=props,
    ):
        result = await process_message(mock_settings, mock_writer, _make_incoming())

    assert result == "page-abc"
    mock_writer.create_page.assert_awaited_once_with(props)
