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
        "upsert_deal",
        "log_activity",
        "get_activities",
    }


def _fake_notion_env(monkeypatch) -> None:
    monkeypatch.setenv("NOTION_TOKEN", "fake-token")
    monkeypatch.setenv("NOTION_TELEGRAM_MSG_DATABASE_ID", "fake-db")
    monkeypatch.setenv("NOTION_PEOPLE_DATA_SOURCE_ID", "fake-people-ds")
    monkeypatch.setenv("NOTION_COMPANIES_DATA_SOURCE_ID", "fake-companies-ds")


def test_build_http_app_bearer_auth(monkeypatch):
    """Covers reject (no/wrong token) and accept (right token) in one test —
    the underlying StreamableHTTPSessionManager singleton can only have its
    lifespan entered once per process, so this can't be split across tests
    that each open their own `with TestClient(...)` context."""
    from starlette.testclient import TestClient

    _fake_notion_env(monkeypatch)
    from notion_pilot.mcp.server import build_http_app

    app = build_http_app("right-token")
    with TestClient(app) as client:
        no_auth = client.post("/", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
        assert no_auth.status_code == 401

        wrong_auth = client.post(
            "/",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert wrong_auth.status_code == 401

        r = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
            headers={
                "Authorization": "Bearer right-token",
                "Accept": "application/json, text/event-stream",
            },
        )
        assert r.status_code == 200
        assert '"serverInfo"' in r.text
