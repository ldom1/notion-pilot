"""Smoke test for mcp/server.py — verifies all tools are registered, no network."""

import pytest

pytest.importorskip("mcp")


async def test_all_expected_tools_are_registered(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "fake-token")
    monkeypatch.setenv("NOTION_TELEGRAM_MSG_DATABASE_ID", "fake-db")
    monkeypatch.setenv("NOTION_PEOPLE_DATA_SOURCE_ID", "fake-people-ds")
    monkeypatch.setenv("NOTION_COMPANIES_DATA_SOURCE_ID", "fake-companies-ds")

    from notion_pilot.mcp.server import mcp

    tools = await mcp.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "upsert_people",
        "upsert_companies",
        "find_duplicates",
        "enrich_people",
        "enrich_companies",
        "rank_contacts_for_pitch",
        "search_people",
        "search_companies",
        "get_recent_people",
        "get_open_leads",
        "refresh_notion_snapshot",
    }
