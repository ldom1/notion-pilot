# tests/unit/web/test_server.py
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import respx
from fastapi.testclient import TestClient
from httpx import Response
from itsdangerous import TimestampSigner


def _make_settings(session_secret="sessionsecret"):
    s = MagicMock()
    s.notion_token = None
    s.notion_oauth_client_id = "test_client_id"
    s.notion_oauth_client_secret = MagicMock()
    s.notion_oauth_client_secret.get_secret_value.return_value = "test_client_secret"
    s.notion_oauth_redirect_uri = "http://localhost:8080/auth/notion/callback"
    s.web_session_secret = MagicMock()
    s.web_session_secret.get_secret_value.return_value = session_secret
    return s


def _session_cookie(data: dict, secret: str = "sessionsecret") -> str:
    signer = TimestampSigner(secret)
    payload = base64.b64encode(json.dumps(data).encode()).decode()
    return signer.sign(payload).decode()


def _make_settings_no_oauth():
    s = MagicMock()
    s.notion_token = None
    s.notion_oauth_client_id = None
    s.notion_oauth_client_secret = None
    s.web_session_secret = None
    return s


def test_health():
    from web.server import create_app

    client = TestClient(create_app(_make_settings()))
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_auth_notion_redirect():
    from web.server import create_app

    client = TestClient(create_app(_make_settings()), follow_redirects=False)
    r = client.get("/auth/notion")
    assert r.status_code in (302, 307)
    assert "api.notion.com/v1/oauth/authorize" in r.headers["location"]
    assert "client_id=test_client_id" in r.headers["location"]


def test_auth_notion_redirect_missing_oauth_config():
    from web.server import create_app

    client = TestClient(create_app(_make_settings_no_oauth()), follow_redirects=False)
    r = client.get("/auth/notion")
    assert r.status_code == 500


def test_setup_with_manual_token():
    from web.server import create_app

    mock_crm = MagicMock(companies_id="c1", people_id="p1", deals_id="d1", crm_page_id="pg1")
    mock_page_id = "root_page_id"
    client = TestClient(create_app(_make_settings()))
    with (
        patch(
            "web.server.create_workspace_root_page",
            new_callable=AsyncMock,
            return_value=mock_page_id,
        ),
        patch("web.server.create_crm_workspace", new_callable=AsyncMock, return_value=mock_crm),
    ):
        r = client.post(
            "/api/setup",
            json={"scope": "crm", "workspace_name": "My CRM", "notion_token": "secret_manual"},
        )
    assert r.status_code == 200
    assert r.json()["notion_page_url"].startswith("https://notion.so/")


def test_setup_under_existing_page():
    from web.server import create_app

    mock_crm = MagicMock(companies_id="c1", people_id="p1", deals_id="d1", crm_page_id="pg1")
    client = TestClient(create_app(_make_settings()))
    with (
        patch(
            "web.server.create_workspace_root_page",
            new_callable=AsyncMock,
        ) as root_mock,
        patch(
            "web.server.create_crm_workspace",
            new_callable=AsyncMock,
            return_value=mock_crm,
        ) as crm_mock,
    ):
        r = client.post(
            "/api/setup",
            json={
                "scope": "crm",
                "workspace_name": "My CRM",
                "notion_token": "secret_manual",
                "parent_page": "https://www.notion.so/Host-550e8400e29b41d4a716446655440000",
            },
        )
    assert r.status_code == 200
    assert r.json()["notion_page_url"] == "https://notion.so/pg1"
    root_mock.assert_not_called()
    crm_mock.assert_awaited_once()
    assert crm_mock.await_args.args[1] == "550e8400-e29b-41d4-a716-446655440000"
    assert crm_mock.await_args.kwargs["page_title"] == "My CRM"


@respx.mock
def test_setup_pages_lists_workspace_pages():
    from web.server import create_app

    respx.post("https://api.notion.com/v1/search").mock(
        return_value=Response(
            200,
            json={
                "results": [
                    {
                        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "parent": {"type": "workspace", "workspace": True},
                        "properties": {
                            "title": {"type": "title", "title": [{"plain_text": "Home"}]}
                        },
                    },
                    {
                        "id": "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "parent": {"type": "workspace", "workspace": True},
                        "properties": {
                            "title": {"type": "title", "title": [{"plain_text": "About"}]}
                        },
                    },
                    {
                        "id": "row-id",
                        "parent": {"type": "database_id", "database_id": "db"},
                        "properties": {
                            "Name": {"type": "title", "title": [{"plain_text": "A row"}]}
                        },
                    },
                    {
                        "id": "nested-id",
                        "parent": {
                            "type": "page_id",
                            "page_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        },
                        "properties": {
                            "title": {"type": "title", "title": [{"plain_text": "Notes"}]}
                        },
                    },
                ],
                "has_more": False,
            },
        )
    )
    client = TestClient(create_app(_make_settings()))
    client.cookies.set(
        "session",
        _session_cookie({"notion_token": "ntn_test", "workspace_id": "ws"}),
    )
    r = client.get("/api/setup/pages")
    assert r.status_code == 200
    assert r.json()["pages"] == [
        {"id": "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee", "name": "About", "root": True},
        {"id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "name": "Home", "root": True},
    ]


@respx.mock
def test_setup_pages_paginates_until_workspace_roots_found():
    from web.server import create_app

    page1 = Response(
        200,
        json={
            "results": [
                {
                    "id": "row-id",
                    "parent": {"type": "database_id", "database_id": "db"},
                    "properties": {
                        "Name": {"type": "title", "title": [{"plain_text": "A row"}]}
                    },
                }
            ],
            "has_more": True,
            "next_cursor": "c2",
        },
    )
    page2 = Response(
        200,
        json={
            "results": [
                {
                    "id": "cccccccc-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "parent": {"type": "workspace", "workspace": True},
                    "properties": {
                        "title": {"type": "title", "title": [{"plain_text": "Zed"}]}
                    },
                }
            ],
            "has_more": False,
        },
    )
    respx.post("https://api.notion.com/v1/search").mock(side_effect=[page1, page2])
    client = TestClient(create_app(_make_settings()))
    client.cookies.set(
        "session",
        _session_cookie({"notion_token": "ntn_test", "workspace_id": "ws"}),
    )
    r = client.get("/api/setup/pages")
    assert r.status_code == 200
    assert r.json()["pages"] == [
        {"id": "cccccccc-bbbb-cccc-dddd-eeeeeeeeeeee", "name": "Zed", "root": True},
    ]


def test_setup_pages_requires_session():
    from web.server import create_app

    r = TestClient(create_app(_make_settings())).get("/api/setup/pages")
    assert r.status_code == 401


def test_setup_no_token_returns_401():
    from web.server import create_app

    client = TestClient(create_app(_make_settings()))
    r = client.post(
        "/api/setup",
        json={"scope": "crm", "workspace_name": "My CRM"},
    )
    assert r.status_code == 401


def test_setup_invalid_scope_returns_422():
    from web.server import create_app

    client = TestClient(create_app(_make_settings()))
    r = client.post(
        "/api/setup",
        json={"scope": "invalid", "workspace_name": "My CRM", "notion_token": "secret_x"},
    )
    assert r.status_code == 422


def test_mcp_not_mounted_without_bearer_token():
    """Default settings (no MCP_BEARER_TOKEN) must not expose /mcp at all —
    falls through to the SPA catch-all (GET-only), so POST is 405, not a
    response from the MCP app."""
    from web.server import create_app

    settings = _make_settings()
    settings.mcp_bearer_token = None
    client = TestClient(create_app(settings))
    r = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
    assert r.status_code == 405


def test_mcp_mounted_and_gated_when_configured(monkeypatch):
    """When both notion_token and mcp_bearer_token are set, /mcp is mounted
    and rejects requests without the correct bearer token.

    Not entered as a `with TestClient(...)` context: the MCP session manager
    is a process-wide singleton whose lifespan can only be entered once ever
    (see tests/unit/mcp/test_server.py::test_build_http_app_bearer_auth,
    which already exercises the live lifespan). The bearer-token middleware
    rejects unauthenticated requests before touching that session state, so
    it doesn't need the lifespan running to verify the 401s here.
    """
    monkeypatch.setenv("NOTION_TOKEN", "fake-token-for-mcp-import")
    monkeypatch.setenv("NOTION_TELEGRAM_MSG_DATABASE_ID", "fake-db")
    monkeypatch.setenv("NOTION_PEOPLE_DATA_SOURCE_ID", "fake-people-ds")
    monkeypatch.setenv("NOTION_COMPANIES_DATA_SOURCE_ID", "fake-companies-ds")

    from web.server import create_app

    settings = _make_settings()
    settings.notion_token = MagicMock()
    settings.mcp_bearer_token = MagicMock()
    settings.mcp_bearer_token.get_secret_value.return_value = "right-token"

    client = TestClient(create_app(settings))

    no_auth = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
    assert no_auth.status_code == 401

    wrong_auth = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        headers={"Authorization": "Bearer nope"},
    )
    assert wrong_auth.status_code == 401
