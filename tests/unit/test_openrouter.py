"""Unit tests for OpenRouter enrichment — no real HTTP calls."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from notion_pilot.config import Settings
from notion_pilot.llm.openrouter import interpret_message
from notion_pilot.models import IncomingMessage, MediaType


def _settings(api_key: str | None = "sk-test") -> Settings:
    return Settings(
        telegram_bot_token=SecretStr("tg-test"),
        notion_token=SecretStr("notion-test"),
        notion_database_id="db-test",
        openrouter_api_key=SecretStr(api_key) if api_key else None,
    )


def _msg(text: str = "Hello world") -> IncomingMessage:
    return IncomingMessage(
        text=text,
        caption=None,
        sender="tester",
        sent_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        media_type=MediaType.TEXT,
        media=None,
        source_adapter="telegram",
    )


class TestInterpretMessage:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_heuristic_base(self):
        settings = _settings(api_key=None)
        result = await interpret_message(settings, _msg("check https://github.com/x/y"))
        assert result.label == ["telegram"]
        assert result.url == "https://github.com/x/y"
        assert result.source == "GitHub"

    @pytest.mark.asyncio
    async def test_empty_api_key_returns_heuristic_base(self):
        settings = _settings(api_key="   ")
        result = await interpret_message(settings, _msg())
        assert result.label == ["telegram"]

    @pytest.mark.asyncio
    async def test_http_error_falls_back_to_heuristics(self):
        settings = _settings()
        with patch("notion_pilot.llm.openrouter.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            result = await interpret_message(settings, _msg())
        assert result.label == ["telegram"]  # heuristic default

    @pytest.mark.asyncio
    async def test_successful_response_is_parsed_into_properties(self):
        settings = _settings()
        fake_response_body = {
            "choices": [
                {
                    "message": {
                        "content": '{"Name":"Cool tool","Label":["dev","ai"],"Type":"link",'
                        '"Link":"https://ex.com","Source":"Example",'
                        '"Description":"A great tool.","Interest":"High"}'
                    }
                }
            ]
        }
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = AsyncMock()
        mock_resp.json = lambda: fake_response_body
        with patch("notion_pilot.llm.openrouter.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_resp
            )
            result = await interpret_message(settings, _msg())
        assert result.name == "Cool tool"
        assert result.label == ["dev", "ai"]
        assert result.entry_type == "link"
        assert result.url == "https://ex.com"
        assert result.interest == "High"
