# tests/unit/web/test_server.py
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _make_settings(username="admin", password="secret", secret_key="testkey"):
    s = MagicMock()
    s.web_admin_username = username
    s.web_admin_password = MagicMock()
    s.web_admin_password.get_secret_value.return_value = password
    s.web_secret_key = MagicMock()
    s.web_secret_key.get_secret_value.return_value = secret_key
    s.web_token_expire_minutes = 60
    s.notion_token = MagicMock()
    s.notion_token.get_secret_value.return_value = "secret_test"
    return s


def _get_token(client, password="secret"):
    r = client.post("/auth/token", data={"username": "admin", "password": password})
    return r.json()["access_token"]


def test_health():
    settings = _make_settings()
    from web.server import create_app

    client = TestClient(create_app(settings))
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_login_success():
    settings = _make_settings()
    from web.server import create_app

    client = TestClient(create_app(settings))
    r = client.post("/auth/token", data={"username": "admin", "password": "secret"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password():
    settings = _make_settings()
    from web.server import create_app

    client = TestClient(create_app(settings))
    r = client.post("/auth/token", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_setup_endpoint_requires_auth():
    settings = _make_settings()
    from web.server import create_app

    client = TestClient(create_app(settings))
    r = client.post(
        "/api/setup", json={"scope": "crm", "parent_page": "550e8400e29b41d4a716446655440000"}
    )
    assert r.status_code == 401


def test_setup_endpoint_crm_with_valid_token():
    settings = _make_settings()
    mock_crm = MagicMock(companies_id="c1", people_id="p1", deals_id="d1", crm_page_id="pg1")
    from web.server import create_app

    client = TestClient(create_app(settings))
    token = _get_token(client)
    with patch("web.server.create_crm_workspace", new_callable=AsyncMock, return_value=mock_crm):
        r = client.post(
            "/api/setup",
            json={"scope": "crm", "parent_page": "550e8400e29b41d4a716446655440000"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.json()["NOTION_COMPANIES_DATA_SOURCE_ID"] == "c1"


def test_setup_endpoint_invalid_scope():
    settings = _make_settings()
    from web.server import create_app

    client = TestClient(create_app(settings))
    token = _get_token(client)
    r = client.post(
        "/api/setup",
        json={"scope": "invalid", "parent_page": "550e8400e29b41d4a716446655440000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
