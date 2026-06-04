# tests/unit/test_telegram_inference.py
"""Unit tests for smart routing inference in TelegramAdapter."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from notion_pilot.shared.config import Settings

_BASE = dict(
    notion_telegram_msg_database_id="kb-db",
    notion_token="tok",
    telegram_bot_token="tg-tok",
    openrouter_api_key="or-key",
)


@pytest.mark.asyncio
async def test_infer_type_people_returns_confirmation():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**_BASE)
    llm_payload = json.dumps(
        {"type": "people", "name": "Jean Dupont", "company": "Artelys", "position": "CTO"}
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": llm_payload}}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("notion_pilot.shared.adapters.telegram.httpx.AsyncClient", return_value=mock_client):
        result = await infer_and_confirm("Met Jean Dupont from Artelys, CTO", s)

    assert result is not None
    inferred_type, confirmation_text, extracted = result
    assert inferred_type == "people"
    assert "Jean Dupont" in confirmation_text
    assert extracted["name"] == "Jean Dupont"


@pytest.mark.asyncio
async def test_infer_type_knowledge_returns_none():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**_BASE)
    llm_payload = json.dumps({"type": "knowledge", "name": ""})
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": llm_payload}}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("notion_pilot.shared.adapters.telegram.httpx.AsyncClient", return_value=mock_client):
        result = await infer_and_confirm("Interesting article about embeddings", s)

    assert result is None


@pytest.mark.asyncio
async def test_infer_no_llm_key_returns_none():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**{**_BASE, "openrouter_api_key": None})
    result = await infer_and_confirm("Some text", s)
    assert result is None


def test_handle_confirm_yes():
    from notion_pilot.shared.adapters.telegram import _resolve_confirmation

    assert _resolve_confirmation("yes") == "yes"
    assert _resolve_confirmation("oui") == "yes"
    assert _resolve_confirmation("YES") == "yes"


def test_handle_confirm_no():
    from notion_pilot.shared.adapters.telegram import _resolve_confirmation

    assert _resolve_confirmation("no") == "no"
    assert _resolve_confirmation("non") == "no"
    assert _resolve_confirmation("/knowledge") == "no"


def test_handle_confirm_unknown():
    from notion_pilot.shared.adapters.telegram import _resolve_confirmation

    assert _resolve_confirmation("maybe") == "unknown"
