"""Unit tests for crm/queries.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from notion_pilot.crm.queries import get_open_leads, get_inbox_items, get_recent_people
from notion_pilot.shared.config import Settings

_BASE = dict(notion_telegram_msg_database_id="kb-db", notion_token="tok")


@pytest.mark.asyncio
async def test_get_open_leads_returns_list():
    s = Settings(**_BASE, notion_deals_database_id="deals-db")
    mock_client = AsyncMock()
    mock_client.databases.query.return_value = {
        "results": [
            {"id": "p1", "properties": {
                "Name": {"title": [{"plain_text": "Artelys HPC"}]},
                "Stage": {"select": {"name": "Prospect"}},
                "Next action": {"rich_text": [{"plain_text": "Call CEO"}]},
            }}
        ]
    }
    with patch("notion_pilot.crm.queries.AsyncClient", return_value=mock_client):
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
    mock_client = AsyncMock()
    mock_client.databases.query.return_value = {
        "results": [
            {"id": "p2", "properties": {
                "Name": {"title": [{"plain_text": "Article on RAG"}]},
                "Status": {"status": {"name": "Not analysed"}},
            }}
        ]
    }
    with patch("notion_pilot.crm.queries.AsyncClient", return_value=mock_client):
        result = await get_inbox_items(s)
    assert len(result) == 1
    assert result[0]["title"] == "Article on RAG"


@pytest.mark.asyncio
async def test_get_recent_people_returns_list():
    s = Settings(**_BASE, notion_people_data_source_id="ppl-db")
    mock_client = AsyncMock()
    mock_client.databases.query.return_value = {
        "results": [
            {"id": "p3", "properties": {
                "Name": {"title": [{"plain_text": "Jean Dupont"}]},
                "Company": {"rich_text": [{"plain_text": "Artelys"}]},
            }}
        ]
    }
    with patch("notion_pilot.crm.queries.AsyncClient", return_value=mock_client):
        result = await get_recent_people(s)
    assert result[0]["name"] == "Jean Dupont"
    assert result[0]["company"] == "Artelys"


@pytest.mark.asyncio
async def test_get_recent_people_no_db_returns_empty():
    s = Settings(**_BASE)  # notion_people_data_source_id not set
    result = await get_recent_people(s)
    assert result == []
