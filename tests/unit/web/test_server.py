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


def test_landing_film_assets_are_served_at_the_url_the_landing_page_uses():
    """Landing.tsx's <Film> requests /film/<slug>.mp4 and .jpg directly (not
    /static/film/...). Without a dedicated mount those fall through to the SPA
    catch-all and silently return index.html — the video element gets an HTML
    document as its src and shows nothing, with no error anywhere."""
    from web.server import create_app

    client = TestClient(create_app(_make_settings()))
    r = client.get("/film/notion-pilot-pipeline.mp4")
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    r = client.get("/film/notion-pilot-pipeline.jpg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"


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

    mock_crm = MagicMock(
        companies_id="c1",
        people_id="p1",
        deals_id="d1",
        crm_page_id="pg1",
        views={},
        warnings=[],
    )
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

    mock_crm = MagicMock(
        companies_id="c1",
        people_id="p1",
        deals_id="d1",
        crm_page_id="pg1",
        views={},
        warnings=[],
    )
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
                "parent_page_id": "https://www.notion.so/Host-550e8400e29b41d4a716446655440000",
            },
        )
    assert r.status_code == 200
    assert r.json()["notion_page_url"] == "https://notion.so/pg1"
    root_mock.assert_not_called()
    crm_mock.assert_awaited_once()
    assert crm_mock.await_args.args[1] == "550e8400-e29b-41d4-a716-446655440000"
    assert crm_mock.await_args.kwargs["page_title"] == "My CRM"


def test_setup_stream_forwards_view_warnings_and_saves_views():
    from web.server import create_app

    warning = "🕘 Recent activity was not created: the Activities database was not found."
    mock_crm = MagicMock(
        companies_id="c1",
        people_id="p1",
        deals_id="d1",
        meetings_id="m1",
        activities_id="a1",
        crm_page_id="pg1",
        views={"pipeline": {"view_id": "v1", "block_id": "b1"}},
        warnings=[warning],
    )
    client = TestClient(create_app(_make_settings()))
    with (
        patch("web.server.create_workspace_root_page", new_callable=AsyncMock, return_value="root"),
        patch("web.server.create_crm_workspace", new_callable=AsyncMock, return_value=mock_crm),
        patch("web.server.save_cockpit_cfg") as save,
    ):
        r = client.post(
            "/api/setup/stream",
            json={"scope": "crm", "workspace_name": "My CRM", "notion_token": "secret_manual"},
        )
    events = [
        json.loads(line[len("data: ") :])
        for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    assert {"type": "warning", "message": warning} in events
    assert events[-1]["type"] == "done"
    cfg = save.call_args.args[1]
    assert cfg["crm_page_id"] == "pg1"
    assert cfg["crm_views"] == {"pipeline": {"view_id": "v1", "block_id": "b1"}}


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
                    "properties": {"Name": {"type": "title", "title": [{"plain_text": "A row"}]}},
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
                    "properties": {"title": {"type": "title", "title": [{"plain_text": "Zed"}]}},
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


def test_mcp_http_route_not_mounted():
    """HTTP /mcp was removed in P3 (lives in notion-pilot-powers stdio only).
    POST must not hit an MCP app — SPA catch-all is GET-only → 405.
    """
    from web.server import create_app

    client = TestClient(create_app(_make_settings()))
    r = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
    assert r.status_code == 405


def test_robots_txt_is_plain_text_not_spa():
    """SPA catch-all must not swallow /robots.txt (Lighthouse robots-txt audit)."""
    from web.server import create_app

    client = TestClient(create_app(_make_settings()))
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    assert "Sitemap:" in r.text
    assert "<!doctype html>" not in r.text.lower()


def test_sitemap_xml_is_xml_not_spa():
    """SPA catch-all must not swallow /sitemap.xml."""
    from web.server import create_app

    client = TestClient(create_app(_make_settings()))
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "")
    assert "xml" in ctype
    assert "<urlset" in r.text
    assert "<lastmod>" in r.text
    assert "https://notion-pilot.com/" in r.text
    assert "<!doctype html>" not in r.text.lower()
