"""Unit tests for remaining cockpit endpoints (P4 surface).

Design rules:
- Zero real network calls (httpx mocked via respx).
- Zero Notion writes (all POST/PATCH/DELETE to notion.com are mocked).
"""

from __future__ import annotations

import base64
import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import respx
from fastapi.testclient import TestClient
from httpx import Response
from itsdangerous import TimestampSigner

# ── Helpers ────────────────────────────────────────────────────────────────────

SESSION_SECRET = "unit-test-secret-x1"


def _make_settings():
    s = MagicMock()
    s.notion_token = None
    s.notion_oauth_client_id = "cid"
    s.notion_oauth_client_secret = MagicMock()
    s.notion_oauth_client_secret.get_secret_value.return_value = "csecret"
    s.notion_oauth_redirect_uri = "http://localhost/auth/notion/callback"
    s.web_session_secret = MagicMock()
    s.web_session_secret.get_secret_value.return_value = SESSION_SECRET
    for attr in [
        "notion_people_data_source_id",
        "notion_companies_data_source_id",
        "notion_deals_database_id",
        "notion_telegram_msg_database_id",
        "notion_notions_database_id",
        "notion_ideas_database_id",
        "notion_tools_database_id",
        "notion_data_tech_database_id",
        "notion_activities_database_id",
        "notion_meetings_database_id",
    ]:
        setattr(s, attr, None)
    return s


def _signed_session(data: dict) -> str:
    """Return a Starlette-compatible signed session cookie value."""
    signer = TimestampSigner(SESSION_SECRET)
    payload = base64.b64encode(json.dumps(data).encode()).decode()
    return signer.sign(payload).decode()


def _authed_client(settings=None, workspace_id: str = "ws_test", notion_token: str = "ntn_test"):
    """TestClient with a valid session cookie injected."""
    from web.server import create_app

    app = create_app(settings or _make_settings())
    client = TestClient(app, raise_server_exceptions=True)
    session_data = {
        "notion_token": notion_token,
        "workspace_id": workspace_id,
        "workspace_name": "Test WS",
        "user_name": "Tester",
    }
    client.cookies.set("session", _signed_session(session_data))
    return client


# ── Auth guard ────────────────────────────────────────────────────────────────


def test_cockpit_status_unauthenticated():
    from web.server import create_app

    client = TestClient(create_app(_make_settings()))
    r = client.get("/api/cockpit/status")
    assert r.status_code == 401


def test_cockpit_page_unauthenticated_redirects(tmp_path):
    from web.server import create_app

    settings = _make_settings()
    app = create_app(settings)
    pathlib.Path(__file__).parents[3] / "web" / "static"
    client = TestClient(app, follow_redirects=False)
    r = client.get("/cockpit")
    assert r.status_code in (302, 307)
    assert "/auth/notion" in r.headers["location"]


# ── /api/cockpit/status ───────────────────────────────────────────────────────


@respx.mock
def test_cockpit_status_with_unconfigured_dbs():
    with patch("web.config.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client()
        r = client.get("/api/cockpit/status")

    assert r.status_code == 200
    data = r.json()
    assert "databases" in data
    assert all(not db["configured"] for db in data["databases"])
    assert data["workspace_name"] == "Test WS"
    assert data["user_name"] == "Tester"


@respx.mock
def test_cockpit_status_with_configured_db():
    settings = _make_settings()
    settings.notion_people_data_source_id = "db-people-id"

    respx.get("https://api.notion.com/v1/databases/db-people-id").mock(
        return_value=Response(200, json={"title": [{"plain_text": "People"}]})
    )
    respx.post("https://api.notion.com/v1/databases/db-people-id/query").mock(
        return_value=Response(200, json={"results": [{}, {}], "has_more": False})
    )
    for attr in [
        "notion_companies_data_source_id",
        "notion_deals_database_id",
        "notion_telegram_msg_database_id",
        "notion_notions_database_id",
        "notion_ideas_database_id",
        "notion_tools_database_id",
        "notion_data_tech_database_id",
    ]:
        setattr(settings, attr, None)

    with patch(
        "web.config.load_cockpit_cfg",
        return_value={"databases": {"notion_people_data_source_id": "db-people-id"}},
    ):
        client = _authed_client(settings=settings)
        r = client.get("/api/cockpit/status")

    assert r.status_code == 200
    people_db = next(d for d in r.json()["databases"] if d["key"] == "notion_people_data_source_id")
    assert people_db["configured"] is True
    assert people_db["count"] == 2
    assert people_db["notion_name"] == "People"


def test_cockpit_status_reports_the_linked_crm_page():
    with patch(
        "web.server.load_cockpit_cfg",
        return_value={"databases": {}, "crm_page_id": "crm-page-1"},
    ):
        client = _authed_client()
        r = client.get("/api/cockpit/status")

    assert r.status_code == 200
    assert r.json()["crm_page_id"] == "crm-page-1"


def test_cockpit_status_has_no_crm_page_before_a_crm_is_deployed():
    with patch("web.server.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client()
        r = client.get("/api/cockpit/status")

    assert r.json()["crm_page_id"] is None


# ── /api/crm/refresh ──────────────────────────────────────────────────────────


def test_refresh_crm_without_a_deployed_crm_returns_400():
    with patch("web.server.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client()
        r = client.post("/api/crm/refresh")

    assert r.status_code == 400
    assert "deploy one first" in r.json()["detail"]


def test_refresh_crm_refreshes_the_linked_page_and_persists_its_views():
    mock_result = MagicMock(
        views={"pipeline": {"view_id": "v2", "block_id": "b2"}},
        warnings=["🕘 Recent activity was not created: the Activities database was not found."],
    )
    with (
        patch(
            "web.server.load_cockpit_cfg",
            return_value={
                "databases": {},
                "crm_page_id": "crm-page-1",
                "crm_views": {"pipeline": {"view_id": "v1", "block_id": "b1"}},
            },
        ),
        patch(
            "web.server.upgrade_crm_home", new_callable=AsyncMock, return_value=mock_result
        ) as upgrade,
        patch("web.server.save_cockpit_cfg") as save,
    ):
        client = _authed_client()
        r = client.post("/api/crm/refresh")

    assert r.status_code == 200
    body = r.json()
    assert body["notion_page_url"] == "https://notion.so/crmpage1"
    assert body["warnings"] == mock_result.warnings
    assert body["views"] == mock_result.views

    assert upgrade.call_args.args[1] == "crm-page-1"
    assert upgrade.call_args.kwargs["previous_views"] == {
        "pipeline": {"view_id": "v1", "block_id": "b1"}
    }
    saved_cfg = save.call_args.args[1]
    assert saved_cfg["crm_views"] == mock_result.views
    assert saved_cfg["crm_page_id"] == "crm-page-1"


# ── /api/cockpit/config ───────────────────────────────────────────────────────


def test_cockpit_config_save_and_load(tmp_path):
    with (
        patch("web.server.load_cockpit_cfg", return_value={"databases": {}}),
        patch("web.server.save_cockpit_cfg") as mock_save,
    ):
        client = _authed_client()
        r = client.post(
            "/api/cockpit/config",
            json={
                "databases": {"notion_people_data_source_id": "abc-123"},
            },
        )

    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_save.assert_called_once()
    saved_cfg = mock_save.call_args[0][1]
    assert saved_cfg["databases"]["notion_people_data_source_id"] == "abc-123"


# ── Removed surfaces return 404/405 (not SPA HTML) ────────────────────────────


def test_removed_cockpit_get_endpoints_are_404():
    client = _authed_client()
    for path in (
        "/api/cockpit/scripts",
        "/api/cockpit/conversations",
        "/api/cockpit/memory",
        "/api/cockpit/workflows",
        "/api/cockpit/deals-properties",
        "/api/telegram/status",
    ):
        r = client.get(path)
        assert r.status_code == 404, path
        assert "text/html" not in r.headers.get("content-type", "")


def test_removed_cockpit_post_endpoints_are_405():
    client = _authed_client()
    for path in (
        "/api/cockpit/chat",
        "/api/cockpit/run-script",
        "/api/cockpit/stop-script",
        "/api/cockpit/create-deal",
        "/api/cockpit/create-lead",
        "/api/cockpit/log-activity",
        "/api/cockpit/run-workflow",
        "/api/telegram/ping",
    ):
        r = client.post(path, json={})
        assert r.status_code == 405, path
