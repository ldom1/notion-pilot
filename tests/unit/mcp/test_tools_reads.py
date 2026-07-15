"""Unit tests for mcp/tools.py get_recent_people_tool/get_open_leads_tool/refresh_notion_snapshot."""

from unittest.mock import AsyncMock

from pydantic import SecretStr

from notion_pilot.mcp.session import SyncerSession
from notion_pilot.mcp.tools import (
    get_open_leads_tool,
    get_recent_people_tool,
    refresh_notion_snapshot,
)
from notion_pilot.shared.config import Settings


def _settings() -> Settings:
    return Settings(
        notion_token=SecretStr("fake-token"),
        notion_telegram_msg_database_id="fake-db",
        notion_people_data_source_id="fake-people-ds",
        notion_companies_data_source_id="fake-companies-ds",
    )


async def test_get_recent_people_tool_delegates(monkeypatch):
    mock = AsyncMock(return_value=[{"name": "Jean Dupont", "company": "EDF"}])
    monkeypatch.setattr("notion_pilot.mcp.tools.get_recent_people", mock)

    result = await get_recent_people_tool(_settings())

    mock.assert_awaited_once()
    assert result == [{"name": "Jean Dupont", "company": "EDF"}]


async def test_get_open_leads_tool_delegates(monkeypatch):
    mock = AsyncMock(return_value=[{"title": "Deal X", "stage": "Negotiation"}])
    monkeypatch.setattr("notion_pilot.mcp.tools.get_open_leads", mock)

    result = await get_open_leads_tool(_settings())

    mock.assert_awaited_once()
    assert result == [{"title": "Deal X", "stage": "Negotiation"}]


async def test_refresh_notion_snapshot_returns_counts(monkeypatch):
    session = SyncerSession(_settings())
    refresh_mock = AsyncMock(return_value=(5, 3))
    monkeypatch.setattr(session, "refresh", refresh_mock)

    result = await refresh_notion_snapshot(session)

    assert result == {"people_count": 5, "companies_count": 3}
