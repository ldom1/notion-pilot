"""Unit tests for inbox/knowledge.py multi-link enrichment routing — no live network."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from notion_pilot.inbox.knowledge import process_message
from notion_pilot.shared.config import Settings
from notion_pilot.shared.llm.link_metadata import LinkMetadata
from notion_pilot.shared.models import IncomingMessage, MediaType, NotionDatabaseProperties


def _settings() -> Settings:
    return Settings(
        notion_telegram_msg_database_id="db-test",
        openrouter_api_key=SecretStr("sk-test"),
    )


def _msg(text: str) -> IncomingMessage:
    return IncomingMessage(
        text=text,
        caption=None,
        sender="tester",
        sent_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
        media_type=MediaType.TEXT,
        media=None,
        source_adapter="telegram",
    )


_FIXTURE_MESSAGE = (
    "IA agent interaction with the internet :\n"
    "- https://github.com/example-org/repo-a\n"
    "- https://github.com/example-org/repo-b\n"
    "- https://github.com/example-org/repo-c\n"
    "- https://github.com/example-org/repo-d\n"
    "- https://github.com/example-org/repo-e\n"
    "- https://github.com/example-org/repo-f"
)


def _fake_interpreted_properties() -> NotionDatabaseProperties:
    """A stand-in for interpret_message()'s return value — every test in this
    file patches interpret_message with this so none of them ever make a real
    OpenRouter HTTP call, matching Task C7 Step 2's "no live network" goal."""
    return NotionDatabaseProperties(
        name="Placeholder title",
        label=["telegram"],
        entry_type="Link",
        url="https://github.com/example-org/repo-a",
        source="GitHub",
        description="placeholder one-shot description",
        interest="Medium",
        status="Not analysed",
    )


@pytest.mark.asyncio
async def test_multi_link_message_writes_body_blocks_and_set_level_description():
    writer = AsyncMock()
    writer.create_page = AsyncMock(return_value="page-id-1")

    fake_metadata = [
        LinkMetadata(
            url=f"https://github.com/example-org/repo-{c}",
            title=f"example-org/repo-{c}",
            description=f"Tool {c}.",
            extra={"stars": "10", "language": "Python", "topics": ""},
        )
        for c in "abcdef"
    ]

    with (
        patch(
            "notion_pilot.inbox.knowledge.interpret_message",
            AsyncMock(return_value=_fake_interpreted_properties()),
        ),
        patch(
            "notion_pilot.inbox.knowledge.fetch_link_metadata",
            AsyncMock(return_value=fake_metadata),
        ),
        patch(
            "notion_pilot.inbox.knowledge.synthesize_multi_link_description",
            AsyncMock(return_value="A set of six internet-interaction tools for AI agents."),
        ),
    ):
        await process_message(_settings(), writer, _msg(_FIXTURE_MESSAGE))

    _, kwargs = writer.create_page.call_args
    children = kwargs.get("children") or writer.create_page.call_args.args[1]
    heading_count = len([b for b in children if b["type"] == "heading_3"])
    assert heading_count == 6

    properties_arg = writer.create_page.call_args.args[0]
    assert properties_arg.description == "A set of six internet-interaction tools for AI agents."
    assert properties_arg.status == "Not analysed"


@pytest.mark.asyncio
async def test_single_link_message_behaves_as_before_no_enrichment():
    writer = AsyncMock()
    writer.create_page = AsyncMock(return_value="page-id-2")

    with (
        patch(
            "notion_pilot.inbox.knowledge.interpret_message",
            AsyncMock(return_value=_fake_interpreted_properties()),
        ),
        patch("notion_pilot.inbox.knowledge.fetch_link_metadata", AsyncMock()) as fetch_mock,
    ):
        await process_message(
            _settings(), writer, _msg("check https://github.com/example-org/repo-a")
        )

    fetch_mock.assert_not_called()
    _, kwargs = writer.create_page.call_args
    assert "children" not in kwargs or not kwargs["children"]


@pytest.mark.asyncio
async def test_two_link_message_also_triggers_enrichment_path():
    writer = AsyncMock()
    writer.create_page = AsyncMock(return_value="page-id-3")
    fake_metadata = [
        LinkMetadata(url="https://github.com/example-org/repo-a", title="example-org/repo-a"),
        LinkMetadata(url="https://github.com/example-org/repo-b", title="example-org/repo-b"),
    ]

    with (
        patch(
            "notion_pilot.inbox.knowledge.interpret_message",
            AsyncMock(return_value=_fake_interpreted_properties()),
        ),
        patch(
            "notion_pilot.inbox.knowledge.fetch_link_metadata",
            AsyncMock(return_value=fake_metadata),
        ),
        patch(
            "notion_pilot.inbox.knowledge.synthesize_multi_link_description",
            AsyncMock(return_value="Two example tools."),
        ),
    ):
        await process_message(
            _settings(),
            writer,
            _msg(
                "two tools: https://github.com/example-org/repo-a "
                "https://github.com/example-org/repo-b"
            ),
        )

    _, kwargs = writer.create_page.call_args
    children = kwargs.get("children") or writer.create_page.call_args.args[1]
    assert len([b for b in children if b["type"] == "heading_3"]) == 2
