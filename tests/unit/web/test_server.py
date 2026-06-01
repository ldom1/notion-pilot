# tests/unit/web/test_server.py
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


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
