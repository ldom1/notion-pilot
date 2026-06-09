# tests/unit/test_telegram_read_commands.py
"""Unit tests for Telegram read command dispatch."""

from unittest.mock import AsyncMock, patch

import pytest

from notion_pilot.shared.config import Settings

_BASE = dict(
    notion_telegram_msg_database_id="kb-db",
    notion_token="tok",
    telegram_bot_token="tg-tok",
)


@pytest.mark.asyncio
async def test_dispatch_read_leads():
    from notion_pilot.shared.adapters.telegram import dispatch_read

    s = Settings(**_BASE, notion_deals_database_id="deals-db")
    with patch(
        "notion_pilot.shared.adapters.telegram.get_open_leads", new_callable=AsyncMock
    ) as mock_leads:
        mock_leads.return_value = [{"title": "Big Deal", "stage": "Prospect", "next_action": ""}]
        result = await dispatch_read("leads", s)
    assert "Big Deal" in result


@pytest.mark.asyncio
async def test_dispatch_read_inbox():
    from notion_pilot.shared.adapters.telegram import dispatch_read

    s = Settings(**_BASE)
    with patch(
        "notion_pilot.shared.adapters.telegram.get_inbox_items", new_callable=AsyncMock
    ) as mock_inbox:
        mock_inbox.return_value = [{"title": "RAG article"}]
        result = await dispatch_read("inbox", s)
    assert "RAG article" in result


@pytest.mark.asyncio
async def test_dispatch_read_recap():
    from notion_pilot.shared.adapters.telegram import dispatch_read

    s = Settings(**_BASE)
    with (
        patch(
            "notion_pilot.shared.adapters.telegram.get_open_leads",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "notion_pilot.shared.adapters.telegram.get_inbox_items",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "notion_pilot.shared.adapters.telegram.get_recent_people",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await dispatch_read("recap", s)
    assert "leads" in result.lower() or "Leads" in result


def test_detect_read_intent_recap_french():
    from notion_pilot.shared.adapters.telegram import _detect_read_intent

    assert _detect_read_intent("Fais moi un recap des leads intéressants") == "recap"


def test_detect_read_intent_recap_english():
    from notion_pilot.shared.adapters.telegram import _detect_read_intent

    assert _detect_read_intent("give me a recap") == "recap"


def test_detect_read_intent_recap_standalone():
    from notion_pilot.shared.adapters.telegram import _detect_read_intent

    assert _detect_read_intent("recap") == "recap"


def test_detect_read_intent_leads():
    from notion_pilot.shared.adapters.telegram import _detect_read_intent

    assert _detect_read_intent("montre moi les leads") == "leads"


def test_detect_read_intent_inbox():
    from notion_pilot.shared.adapters.telegram import _detect_read_intent

    assert _detect_read_intent("à relire") == "inbox"


def test_detect_read_intent_inbox_english():
    from notion_pilot.shared.adapters.telegram import _detect_read_intent

    assert _detect_read_intent("show inbox") == "inbox"


def test_detect_read_intent_none_for_data_entry():
    from notion_pilot.shared.adapters.telegram import _detect_read_intent

    assert _detect_read_intent("J'ai rencontré Alice Martin chez Acme") is None


def test_detect_read_intent_none_for_single_lead():
    from notion_pilot.shared.adapters.telegram import _detect_read_intent

    assert _detect_read_intent("j'ai un nouveau lead intéressant") is None
