"""Unit tests for shared/llm/synthesis.py — no live network."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from notion_pilot.shared.config import Settings
from notion_pilot.shared.llm.link_metadata import LinkMetadata
from notion_pilot.shared.llm.synthesis import (
    build_link_body_blocks,
    synthesize_multi_link_description,
)
from notion_pilot.shared.models import IncomingMessage, MediaType


def _settings(api_key: str | None = "sk-test") -> Settings:
    return Settings(
        notion_telegram_msg_database_id="db-test",
        openrouter_api_key=SecretStr(api_key) if api_key else None,
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


def test_build_link_body_blocks_one_group_per_link_with_factual_bullets():
    items = [
        LinkMetadata(
            url="https://github.com/example-org/repo-a",
            title="example-org/repo-a",
            description="A scraping tool.",
            extra={"stars": "100", "language": "Python", "topics": "scraping"},
        ),
        LinkMetadata(
            url="https://github.com/example-org/repo-b",
            title="example-org/repo-b",
            description="Another scraping tool.",
            extra={"stars": "50", "language": "Rust", "topics": ""},
        ),
    ]
    blocks = build_link_body_blocks(items)

    headings = [b for b in blocks if b["type"] == "heading_3"]
    assert len(headings) == 2
    bullets = [b for b in blocks if b["type"] == "bulleted_list_item"]
    assert len(bullets) >= 4  # at least 2 bullets per link
    all_text = str(blocks)
    assert "100" in all_text and "Python" in all_text
    assert "50" in all_text and "Rust" in all_text


def test_build_link_body_blocks_never_fabricates_missing_metadata():
    items = [LinkMetadata(url="https://example.com/broken", error="fetch_failed")]
    blocks = build_link_body_blocks(items)

    all_text = str(blocks)
    assert "example.com/broken" in all_text
    # No fabricated star counts, descriptions, or language for a failed fetch
    assert "stars" not in all_text.lower()


@pytest.mark.asyncio
async def test_synthesize_multi_link_description_calls_openrouter():
    items = [LinkMetadata(url="https://github.com/example-org/repo-a", description="A tool.")]
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = AsyncMock()
    mock_resp.json = lambda: {
        "choices": [{"message": {"content": "A set of scraping tools for AI agents."}}]
    }
    with patch("notion_pilot.shared.llm.synthesis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        description = await synthesize_multi_link_description(
            _settings(), _msg("check these tools"), items
        )

    assert description == "A set of scraping tools for AI agents."


@pytest.mark.asyncio
async def test_synthesize_multi_link_description_falls_back_on_llm_failure():
    items = [LinkMetadata(url="https://github.com/example-org/repo-a", title="example-org/repo-a")]
    with patch("notion_pilot.shared.llm.synthesis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=RuntimeError("boom"))
        mock_cls.return_value = mock_client

        description = await synthesize_multi_link_description(
            _settings(), _msg("check these tools"), items
        )

    assert "example-org/repo-a" in description
