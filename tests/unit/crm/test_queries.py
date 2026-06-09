"""Unit tests for crm/queries.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notion_pilot.crm.queries import get_inbox_items, get_open_leads, get_recent_people
from notion_pilot.shared.config import Settings

_BASE = dict(notion_telegram_msg_database_id="kb-db", notion_token="tok")


def _make_httpx_mock(json_data: dict) -> MagicMock:
    """Return a mock httpx.AsyncClient context manager returning json_data."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = json_data
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


@pytest.mark.asyncio
async def test_get_open_leads_returns_list():
    s = Settings(**_BASE, notion_deals_database_id="deals-db")
    mock_client = _make_httpx_mock(
        {
            "results": [
                {
                    "id": "p1",
                    "properties": {
                        "Name": {"type": "title", "title": [{"plain_text": "Artelys HPC"}]},
                        "Stage": {"select": {"name": "Prospect"}},
                        "Next action": {"rich_text": [{"plain_text": "Call CEO"}]},
                    },
                }
            ]
        }
    )
    with patch("notion_pilot.crm.queries.httpx.AsyncClient", return_value=mock_client):
        result = await get_open_leads(s)
    assert len(result) == 1
    assert result[0]["title"] == "Artelys HPC"
    assert result[0]["stage"] == "Prospect"
    assert result[0]["next_action"] == "Call CEO"


@pytest.mark.asyncio
async def test_get_open_leads_no_db_returns_empty():
    s = Settings(**_BASE)  # notion_deals_database_id not set
    result = await get_open_leads(s)
    assert result == []


@pytest.mark.asyncio
async def test_get_inbox_items_filters_not_analysed():
    s = Settings(**_BASE)
    mock_client = _make_httpx_mock(
        {
            "results": [
                {
                    "id": "p2",
                    "properties": {
                        "Name": {"type": "title", "title": [{"plain_text": "Article on RAG"}]},
                        "Status": {"status": {"name": "Not analysed"}},
                    },
                }
            ]
        }
    )
    with patch("notion_pilot.crm.queries.httpx.AsyncClient", return_value=mock_client):
        result = await get_inbox_items(s)
    assert len(result) == 1
    assert result[0]["title"] == "Article on RAG"


@pytest.mark.asyncio
async def test_get_recent_people_returns_list():
    from unittest.mock import AsyncMock, MagicMock, patch

    from notion_pilot.crm.queries import get_recent_people
    from notion_pilot.shared.config import Settings

    settings = Settings(
        notion_token="secret_test",
        notion_telegram_msg_database_id="db-id",
        notion_people_data_source_id="people-db-id",
    )

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Alice"}]},
                    "Company": {"type": "rich_text", "rich_text": [{"plain_text": "Acme"}]},
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("notion_pilot.crm.queries.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        result = await get_recent_people(settings)

    assert result == [{"name": "Alice", "company": "Acme"}]
    mock_client.post.assert_awaited_once()
    call_args = mock_client.post.call_args
    assert "people-db-id" in call_args[0][0]  # URL contains the DB id
    assert call_args[1]["json"]["filter"]["timestamp"] == "created_time"


@pytest.mark.asyncio
async def test_get_recent_people_no_db_returns_empty():
    s = Settings(**_BASE)  # notion_people_data_source_id not set
    result = await get_recent_people(s)
    assert result == []
