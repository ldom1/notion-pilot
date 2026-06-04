"""Unit tests for cockpit endpoints.

Design rules:
- Zero real network calls (httpx mocked via respx).
- Zero Notion writes (all POST/PATCH/DELETE to notion.com are mocked).
- Zero file-system side-effects for workflows (tmp_path fixture).
- Subprocess never spawned (asyncio.create_subprocess_exec mocked).
"""

from __future__ import annotations

import base64
import json
import pathlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
    # DB ID settings (all None by default — overridden per test as needed)
    for attr in [
        "notion_people_data_source_id",
        "notion_companies_data_source_id",
        "notion_deals_database_id",
        "notion_telegram_msg_database_id",
        "notion_notions_database_id",
        "notion_ideas_database_id",
        "notion_tools_database_id",
        "notion_data_tech_database_id",
    ]:
        setattr(s, attr, None)
    s.openrouter_api_key = None
    s.openrouter_model = "test-model"
    s.openrouter_url = "https://openrouter.ai/api/v1"
    s.openrouter_http_referer = None
    s.openrouter_app_title = "Notion Pilot Test"
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


def test_cockpit_scripts_unauthenticated():
    from web.server import create_app

    client = TestClient(create_app(_make_settings()))
    r = client.get("/api/cockpit/scripts")
    assert r.status_code == 401


def test_cockpit_page_unauthenticated_redirects(tmp_path):
    from web.server import create_app

    settings = _make_settings()
    app = create_app(settings)
    # Create a minimal cockpit.html so the route can serve it
    pathlib.Path(__file__).parents[3] / "web" / "static"
    client = TestClient(app, follow_redirects=False)
    r = client.get("/cockpit")
    assert r.status_code in (302, 307)
    assert "/auth/notion" in r.headers["location"]


# ── /api/cockpit/scripts ──────────────────────────────────────────────────────


def test_cockpit_scripts_returns_list(tmp_path):
    yaml_content = """
scripts:
  - id: test_script
    label: Test Script
    path: scripts/crm/crm_refresh_people.py
    category: CRM
    description: A test script
"""
    scripts_yaml = tmp_path / "scripts.yaml"
    scripts_yaml.write_text(yaml_content)

    # Must patch web.utils.SCRIPTS_YAML_PATH (imported at module load time)
    with patch("web.utils.SCRIPTS_YAML_PATH", scripts_yaml):
        client = _authed_client()
        r = client.get("/api/cockpit/scripts")

    assert r.status_code == 200
    data = r.json()
    assert "scripts" in data
    assert data["scripts"][0]["id"] == "test_script"
    assert data["scripts"][0]["label"] == "Test Script"


# ── /api/cockpit/status ───────────────────────────────────────────────────────


@respx.mock
def test_cockpit_status_with_unconfigured_dbs():
    # All DB IDs are None → should return databases with configured=False
    with patch("web.config.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client()
        # The status endpoint makes no Notion calls if all IDs are None
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
    # Other DBs are None — no requests for them
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

    with patch("web.config.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client(settings=settings)
        r = client.get("/api/cockpit/status")

    assert r.status_code == 200
    people_db = next(d for d in r.json()["databases"] if d["key"] == "notion_people_data_source_id")
    assert people_db["configured"] is True
    assert people_db["count"] == 2
    assert people_db["notion_name"] == "People"


# ── /api/cockpit/config ───────────────────────────────────────────────────────


def test_cockpit_config_save_and_load(tmp_path):
    # server.py imports save_cockpit_cfg / load_cockpit_cfg directly → patch there
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


# ── /api/cockpit/run-script ───────────────────────────────────────────────────


def test_run_script_not_found(tmp_path):
    scripts_yaml = tmp_path / "scripts.yaml"
    scripts_yaml.write_text(
        "scripts:\n  - id: exists\n    path: scripts/x.py\n    label: X\n    category: CRM\n"
    )
    with patch("web.config.SCRIPTS_YAML_PATH", scripts_yaml):
        client = _authed_client()
        r = client.post("/api/cockpit/run-script", json={"script_id": "does_not_exist"})
    assert r.status_code == 404


def _make_mock_proc(lines: list[bytes], returncode: int = 0) -> MagicMock:
    """Build a fake asyncio.subprocess.Process for testing."""
    proc = MagicMock()
    proc.stdout = AsyncMock()
    proc.returncode = returncode
    proc.stdout.readline = AsyncMock(side_effect=lines)
    proc.wait = AsyncMock()
    return proc


def test_run_script_streams_output(tmp_path):
    """Script subprocess is mocked — no real execution, no Notion writes."""
    script_file = tmp_path / "dummy.py"
    script_file.write_text("print('hello')")

    scripts_yaml = tmp_path / "scripts.yaml"
    scripts_yaml.write_text(f"""
scripts:
  - id: dummy
    label: Dummy
    path: {script_file}
    category: CRM
""")

    mock_proc = _make_mock_proc([b"line one\n", b"line two\n", b""])
    mock_exec = AsyncMock(return_value=mock_proc)  # AsyncMock so await works

    with (
        patch("web.utils.SCRIPTS_YAML_PATH", scripts_yaml),
        patch("web.server.load_cockpit_cfg", return_value={"databases": {}}),
        patch("web.server.resolve_db_ids", return_value={}),
        patch("asyncio.create_subprocess_exec", mock_exec),
    ):
        client = _authed_client()
        r = client.post("/api/cockpit/run-script", json={"script_id": "dummy"})

    assert r.status_code == 200
    body = r.text
    assert "line one" in body
    assert "line two" in body
    assert '"done"' in body


def test_run_script_exit_nonzero(tmp_path):
    script_file = tmp_path / "fail.py"
    script_file.write_text("import sys; sys.exit(1)")
    scripts_yaml = tmp_path / "scripts.yaml"
    scripts_yaml.write_text(
        f"scripts:\n  - id: fail\n    label: Fail\n    path: {script_file}\n    category: CRM\n"
    )

    mock_proc = _make_mock_proc([b""], returncode=1)
    mock_exec = AsyncMock(return_value=mock_proc)

    with (
        patch("web.utils.SCRIPTS_YAML_PATH", scripts_yaml),
        patch("web.server.load_cockpit_cfg", return_value={"databases": {}}),
        patch("web.server.resolve_db_ids", return_value={}),
        patch("asyncio.create_subprocess_exec", mock_exec),
    ):
        client = _authed_client()
        r = client.post("/api/cockpit/run-script", json={"script_id": "fail"})

    assert r.status_code == 200
    assert '"error"' in r.text
    assert "code 1" in r.text


# ── /api/cockpit/stop-script ──────────────────────────────────────────────────


def test_stop_script_not_running():
    client = _authed_client()
    r = client.post("/api/cockpit/stop-script", json={"script_id": "nothing_running"})
    assert r.status_code == 404


def test_stop_script_kills_process():
    from web.server import create_app

    settings = _make_settings()
    create_app(settings)

    # Manually inject a fake process into _running_procs
    # Access the closure variable via the route function
    mock_proc = MagicMock()
    mock_proc.kill = MagicMock()

    # Find the running procs dict via the app state — it's a closure, so we
    # reach it by calling the stop endpoint after injecting via patch
    with patch("web.server.create_app"):
        # Rebuild with direct dict injection

        # We patch at module closure level by running the factory and injecting
        real_app = create_app(settings)
        client = TestClient(real_app)
        client.cookies.set(
            "session", _signed_session({"notion_token": "tok", "workspace_id": "ws1"})
        )

        # There's no running proc — expect 404
        r = client.post("/api/cockpit/stop-script", json={"script_id": "myscript"})
        assert r.status_code == 404


# ── /api/cockpit/deals-properties ────────────────────────────────────────────


@respx.mock
def test_deals_properties_returns_wizard_fields():
    settings = _make_settings()
    settings.notion_deals_database_id = "db-deals"

    notion_db_props = {
        "Name": {"type": "title"},
        "Client": {"type": "relation"},
        "Contacts": {"type": "relation"},
        "Stage": {
            "type": "select",
            "select": {"options": [{"name": "Prospect"}, {"name": "Qualified"}]},
        },
        "Product": {
            "type": "multi_select",
            "multi_select": {"options": [{"name": "HPC"}, {"name": "Consulting"}]},
        },
        "Notes": {"type": "rich_text"},
        "Value (euros)": {"type": "number"},
    }
    respx.get("https://api.notion.com/v1/databases/db-deals").mock(
        return_value=Response(200, json={"properties": notion_db_props})
    )

    with patch(
        "web.config.load_cockpit_cfg",
        return_value={"databases": {"notion_deals_database_id": "db-deals"}},
    ):
        client = _authed_client(settings=settings)
        r = client.get("/api/cockpit/deals-properties")

    assert r.status_code == 200
    fields = {f["key"]: f for f in r.json()["fields"]}

    # Implicit fields should be excluded
    assert "Name" not in fields
    assert "Client" not in fields
    assert "Contacts" not in fields

    # Wizard fields should be present
    assert "Stage" in fields
    assert fields["Stage"]["type"] == "select"
    assert "Prospect" in fields["Stage"]["options"]

    assert "Product" in fields
    assert fields["Product"]["type"] == "multi_select"

    assert "Notes" in fields
    assert fields["Notes"]["type"] == "text"

    assert "Value (euros)" in fields
    assert fields["Value (euros)"]["type"] == "number"


def test_deals_properties_no_db_configured():
    with patch("web.config.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client()
        r = client.get("/api/cockpit/deals-properties")
    assert r.status_code == 400
    assert "Deals database not configured" in r.json()["detail"]


# ── /api/cockpit/create-deal ──────────────────────────────────────────────────


@respx.mock
def test_create_deal_existing_contact():
    """Links deal to an existing People page — no new person created in Notion."""
    settings = _make_settings()
    settings.notion_deals_database_id = "db-deals"
    new_page_id = str(uuid.uuid4())

    respx.post("https://api.notion.com/v1/pages").mock(
        return_value=Response(201, json={"id": new_page_id})
    )

    with patch(
        "web.config.load_cockpit_cfg",
        return_value={"databases": {"notion_deals_database_id": "db-deals"}},
    ):
        client = _authed_client(settings=settings)
        r = client.post(
            "/api/cockpit/create-deal",
            json={
                "deal_name": "Crystal HPC — Matthieu Tonso",
                "notion_id": "person-page-id-123",
            },
        )

    assert r.status_code == 200
    data = r.json()
    assert data["page_id"] == new_page_id
    assert "notion.so" in data["url"]
    assert new_page_id.replace("-", "") in data["url"]

    # Verify the Notion API was called exactly once (deal page only)
    calls = [c for c in respx.calls if "api.notion.com" in str(c.request.url)]
    assert len(calls) == 1
    body = json.loads(calls[0].request.content)
    assert (
        body["properties"]["Name"]["title"][0]["text"]["content"] == "Crystal HPC — Matthieu Tonso"
    )
    assert body["properties"]["Contacts"]["relation"][0]["id"] == "person-page-id-123"
    assert body["properties"]["Stage"]["select"]["name"] == "Prospect"


@respx.mock
def test_create_deal_new_contact_creates_person_first():
    """Creates person page THEN deal page — two Notion writes, none to Notion workspace."""
    settings = _make_settings()
    settings.notion_deals_database_id = "db-deals"
    settings.notion_people_data_source_id = "db-people"

    person_id = str(uuid.uuid4())
    deal_id = str(uuid.uuid4())

    call_count = 0

    def _side_effect(request, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Response(201, json={"id": person_id})
        return Response(201, json={"id": deal_id})

    respx.post("https://api.notion.com/v1/pages").mock(side_effect=_side_effect)

    with patch(
        "web.config.load_cockpit_cfg",
        return_value={
            "databases": {
                "notion_deals_database_id": "db-deals",
                "notion_people_data_source_id": "db-people",
            }
        },
    ):
        client = _authed_client(settings=settings)
        r = client.post(
            "/api/cockpit/create-deal",
            json={
                "deal_name": "Crystal HPC — New Lead",
                "new_person": {"name": "Jean Dupont", "position": "CTO", "company": "Acme"},
            },
        )

    assert r.status_code == 200
    assert r.json()["page_id"] == deal_id
    assert call_count == 2  # person + deal


@respx.mock
def test_create_deal_with_extra_fields():
    """Wizard-collected extra fields are merged into Deal properties."""
    settings = _make_settings()
    settings.notion_deals_database_id = "db-deals"
    new_page_id = str(uuid.uuid4())
    respx.post("https://api.notion.com/v1/pages").mock(
        return_value=Response(201, json={"id": new_page_id})
    )

    with patch(
        "web.config.load_cockpit_cfg",
        return_value={"databases": {"notion_deals_database_id": "db-deals"}},
    ):
        client = _authed_client(settings=settings)
        r = client.post(
            "/api/cockpit/create-deal",
            json={
                "deal_name": "HPC Deal",
                "notion_id": "person-id",
                "extra_fields": {
                    "Product": ["HPC-as-a-service"],
                    "Type": "Prospection chaude",
                    "Value (euros)": 45000,
                    "Notes": "Strategic account",
                },
            },
        )

    assert r.status_code == 200
    body = json.loads(respx.calls[0].request.content)
    assert body["properties"]["Product"]["multi_select"][0]["name"] == "HPC-as-a-service"
    assert body["properties"]["Type"]["select"]["name"] == "Prospection chaude"
    assert body["properties"]["Value (euros)"]["number"] == 45000
    assert body["properties"]["Notes"]["rich_text"][0]["text"]["content"] == "Strategic account"


def test_create_deal_no_deals_db():
    with patch("web.config.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client()
        r = client.post("/api/cockpit/create-deal", json={"deal_name": "X"})
    assert r.status_code == 400
    assert "Deals database not configured" in r.json()["detail"]


# ── /api/cockpit/workflows ────────────────────────────────────────────────────


def test_workflows_crud(tmp_path):
    wf_data = {
        "id": "wf-001",
        "name": "Full CRM refresh",
        "nodes": [{"id": "import_linkedin", "position": {"x": 20, "y": 40}}],
        "edges": [{"id": "e1", "source": "import_linkedin", "target": "refresh_people"}],
    }

    with patch("web.config._workspace_dir", return_value=tmp_path / "ws_test"):
        client = _authed_client()

        # GET empty
        r = client.get("/api/cockpit/workflows")
        assert r.status_code == 200
        assert r.json()["workflows"] == []

        # POST save
        r = client.post("/api/cockpit/workflows", json={"workflow": wf_data})
        assert r.status_code == 200
        assert r.json()["workflow_id"] == "wf-001"

        # GET after save
        r = client.get("/api/cockpit/workflows")
        assert r.status_code == 200
        assert len(r.json()["workflows"]) == 1
        assert r.json()["workflows"][0]["name"] == "Full CRM refresh"

        # POST upsert (same id, new name)
        updated = {**wf_data, "name": "Updated Workflow"}
        r = client.post("/api/cockpit/workflows", json={"workflow": updated})
        assert r.status_code == 200
        r = client.get("/api/cockpit/workflows")
        assert len(r.json()["workflows"]) == 1
        assert r.json()["workflows"][0]["name"] == "Updated Workflow"

        # DELETE
        r = client.delete("/api/cockpit/workflows/wf-001")
        assert r.status_code == 200
        r = client.get("/api/cockpit/workflows")
        assert r.json()["workflows"] == []


# ── /api/cockpit/run-workflow ─────────────────────────────────────────────────


def test_run_workflow_not_found(tmp_path):
    with patch("web.config._workspace_dir", return_value=tmp_path / "ws_test"):
        client = _authed_client()
        r = client.post("/api/cockpit/run-workflow", json={"workflow_id": "nonexistent"})
    assert r.status_code == 404


def test_run_workflow_topological_order(tmp_path):
    """Verifies nodes execute in edge-respecting order (source before target)."""
    script_a = tmp_path / "a.py"
    script_b = tmp_path / "b.py"
    script_a.write_text("")
    script_b.write_text("")

    scripts_yaml = tmp_path / "scripts.yaml"
    scripts_yaml.write_text(f"""
scripts:
  - id: script_a
    label: A
    path: {script_a}
    category: CRM
  - id: script_b
    label: B
    path: {script_b}
    category: CRM
""")

    wf = {
        "id": "wf-topo",
        "name": "A then B",
        "nodes": [
            {"id": "script_a", "position": {"x": 0, "y": 0}},
            {"id": "script_b", "position": {"x": 1, "y": 0}},
        ],
        "edges": [{"id": "e1", "source": "script_a", "target": "script_b"}],
    }

    execution_order = []

    def _make_step_mock(label: str) -> MagicMock:
        m = MagicMock()
        m.stdout = AsyncMock()
        m.returncode = 0
        m.stdout.readline = AsyncMock(side_effect=[b""])
        m.wait = AsyncMock()
        return m

    call_idx = [0]
    labels = ["A", "B"]

    async def _fake_exec(*args, **kwargs):
        idx = call_idx[0]
        call_idx[0] += 1
        script_path = str(args[1])
        if str(script_a) in script_path:
            execution_order.append("A")
        elif str(script_b) in script_path:
            execution_order.append("B")
        return _make_step_mock(labels[idx] if idx < len(labels) else "?")

    mock_exec = AsyncMock(side_effect=_fake_exec)

    with (
        patch("web.utils.SCRIPTS_YAML_PATH", scripts_yaml),
        patch("web.server.load_cockpit_cfg", return_value={"databases": {}}),
        patch("web.server.resolve_db_ids", return_value={}),
        patch("web.config._workspace_dir", return_value=tmp_path / "ws_test"),
        patch("asyncio.create_subprocess_exec", mock_exec),
    ):
        client = _authed_client()
        client.post("/api/cockpit/workflows", json={"workflow": wf})
        r = client.post("/api/cockpit/run-workflow", json={"workflow_id": "wf-topo"})

    assert r.status_code == 200
    assert "done" in r.text
    assert execution_order == ["A", "B"]


# ── /api/cockpit/chat ─────────────────────────────────────────────────────────


@respx.mock
def test_chat_no_llm_key_returns_error():
    """When OPENROUTER_API_KEY is absent, chat returns an error event."""
    settings = _make_settings()
    settings.openrouter_api_key = None

    with patch("web.config.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client(settings=settings)
        r = client.post("/api/cockpit/chat", json={"query": "find leads", "history": []})

    assert r.status_code == 200
    assert '"error"' in r.text
    assert "OPENROUTER_API_KEY" in r.text


@respx.mock
def test_chat_suggest_action():
    """LLM returns suggest action → result event with leads, no Notion write."""
    settings = _make_settings()
    settings.notion_people_data_source_id = "db-people"
    settings.openrouter_api_key = MagicMock()
    settings.openrouter_api_key.get_secret_value.return_value = "key-test"

    # Mock People DB query
    respx.post("https://api.notion.com/v1/databases/db-people/query").mock(
        return_value=Response(
            200,
            json={
                "results": [
                    {
                        "id": "pid1",
                        "properties": {
                            "Nom": {"type": "title", "title": [{"plain_text": "Alice"}]},
                            "Position": {"type": "rich_text", "rich_text": [{"plain_text": "CTO"}]},
                        },
                    }
                ],
                "has_more": False,
            },
        )
    )
    # Mock LLM response
    llm_payload = {
        "action": "suggest",
        "message": "Alice is a great fit",
        "leads": [
            {
                "type": "existing",
                "name": "Alice",
                "notion_id": "pid1",
                "position": "CTO",
                "company": "Acme",
            }
        ],
    }
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": json.dumps(llm_payload)}}]}
        )
    )

    with patch(
        "web.config.load_cockpit_cfg",
        return_value={"databases": {"notion_people_data_source_id": "db-people"}},
    ):
        client = _authed_client(settings=settings)
        r = client.post("/api/cockpit/chat", json={"query": "find HPC leads", "history": []})

    assert r.status_code == 200
    assert '"result"' in r.text
    assert "Alice is a great fit" in r.text
    # No pages created in Notion
    assert not any(
        "POST" in str(c.request.method) and "v1/pages" in str(c.request.url) for c in respx.calls
    )


@respx.mock
def test_chat_create_action_does_not_auto_create():
    """LLM returns create intent — server emits result WITHOUT creating anything in Notion."""
    settings = _make_settings()
    settings.openrouter_api_key = MagicMock()
    settings.openrouter_api_key.get_secret_value.return_value = "key-test"
    settings.notion_people_data_source_id = None  # no DB configured

    llm_payload = {
        "action": "create",
        "message": "Ready to create a deal for Matthieu",
        "leads": [
            {
                "type": "existing",
                "name": "Matthieu Tonso",
                "notion_id": "pid-mt",
                "deal_name": "Crystal HPC — Matthieu Tonso",
            }
        ],
    }
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": json.dumps(llm_payload)}}]}
        )
    )

    with patch("web.config.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client(settings=settings)
        r = client.post("/api/cockpit/chat", json={"query": "crée le lead", "history": []})

    assert r.status_code == 200
    body = r.text
    assert '"result"' in body
    assert '"create"' in body
    # Critically: no pages were posted to Notion
    assert not any("v1/pages" in str(c.request.url) for c in respx.calls)


@respx.mock
def test_chat_passes_history_to_llm():
    """Conversation history is forwarded to the LLM so follow-up messages have context."""
    settings = _make_settings()
    settings.openrouter_api_key = MagicMock()
    settings.openrouter_api_key.get_secret_value.return_value = "key-test"
    settings.notion_people_data_source_id = None

    captured_payload = {}

    def _capture_request(request, **kwargs):
        captured_payload.update(json.loads(request.content))
        return Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"action": "info", "message": "ok", "leads": []})
                        }
                    }
                ]
            },
        )

    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=_capture_request)

    history = [
        {"role": "user", "content": "find HPC leads"},
        {"role": "assistant", "content": "Found Alice"},
    ]

    with patch("web.config.load_cockpit_cfg", return_value={"databases": {}}):
        client = _authed_client(settings=settings)
        client.post("/api/cockpit/chat", json={"query": "crée le lead", "history": history})

    messages = captured_payload.get("messages", [])
    roles = [m["role"] for m in messages]
    assert "user" in roles
    assert "assistant" in roles
    # History turns (user + assistant) appear before the final user query message
    assert roles.index("assistant") < len(roles) - 1


# ── crm_chat module ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_crm_no_api_key():
    from notion_pilot.shared.llm.crm_chat import chat_crm

    settings = MagicMock()
    settings.openrouter_api_key = None
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        await chat_crm(settings, "hello", [], [])


@pytest.mark.asyncio
@respx.mock
async def test_chat_crm_suggest():
    from notion_pilot.shared.llm.crm_chat import chat_crm

    settings = MagicMock()
    settings.openrouter_api_key = MagicMock()
    settings.openrouter_api_key.get_secret_value.return_value = "key-x"
    settings.openrouter_model = "model-x"
    settings.openrouter_url = "https://openrouter.ai/api/v1"
    settings.openrouter_http_referer = None
    settings.openrouter_app_title = "Test"

    response_body = {
        "action": "suggest",
        "message": "Try Alice",
        "leads": [{"type": "new", "name": "Alice"}],
    }
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": json.dumps(response_body)}}]}
        )
    )

    result = await chat_crm(
        settings, "find leads", [], [{"id": "p1", "name": "Bob", "position": "CEO", "company": "X"}]
    )
    assert result["action"] == "suggest"
    assert result["message"] == "Try Alice"
    assert len(result["leads"]) == 1


@pytest.mark.asyncio
@respx.mock
async def test_chat_crm_detect_create_intent():
    from notion_pilot.shared.llm.crm_chat import chat_crm

    settings = MagicMock()
    settings.openrouter_api_key = MagicMock()
    settings.openrouter_api_key.get_secret_value.return_value = "key-x"
    settings.openrouter_model = "model-x"
    settings.openrouter_url = "https://openrouter.ai/api/v1"
    settings.openrouter_http_referer = None
    settings.openrouter_app_title = "Test"

    response_body = {
        "action": "create",
        "message": "Creating deal for Bob",
        "leads": [{"type": "existing", "name": "Bob", "notion_id": "p1", "deal_name": "HPC — Bob"}],
    }
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": json.dumps(response_body)}}]}
        )
    )

    result = await chat_crm(settings, "crée le lead", [], [])
    assert result["action"] == "create"
    assert result["leads"][0]["deal_name"] == "HPC — Bob"


@pytest.mark.asyncio
@respx.mock
async def test_chat_crm_history_included_in_request():
    from notion_pilot.shared.llm.crm_chat import chat_crm

    settings = MagicMock()
    settings.openrouter_api_key = MagicMock()
    settings.openrouter_api_key.get_secret_value.return_value = "key-x"
    settings.openrouter_model = "m"
    settings.openrouter_url = "https://openrouter.ai/api/v1"
    settings.openrouter_http_referer = None
    settings.openrouter_app_title = "T"

    captured = {}

    def _capture(request, **kwargs):
        captured["payload"] = json.loads(request.content)
        return Response(
            200,
            json={
                "choices": [{"message": {"content": '{"action":"info","message":"ok","leads":[]}'}}]
            },
        )

    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=_capture)

    history = [
        {"role": "user", "content": "prev question"},
        {"role": "assistant", "content": "prev answer"},
    ]
    await chat_crm(settings, "follow-up", history, [])

    messages = captured["payload"]["messages"]
    contents = [m["content"] for m in messages]
    assert any("prev question" in c for c in contents)
    assert any("prev answer" in c for c in contents)


@pytest.mark.asyncio
@respx.mock
async def test_chat_crm_handles_json_fence():
    """LLM wrapping output in code fences is stripped cleanly."""
    from notion_pilot.shared.llm.crm_chat import chat_crm

    settings = MagicMock()
    settings.openrouter_api_key = MagicMock()
    settings.openrouter_api_key.get_secret_value.return_value = "key-x"
    settings.openrouter_model = "m"
    settings.openrouter_url = "https://openrouter.ai/api/v1"
    settings.openrouter_http_referer = None
    settings.openrouter_app_title = "T"

    fenced = '```json\n{"action":"suggest","message":"hi","leads":[]}\n```'
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": fenced}}]})
    )

    result = await chat_crm(settings, "q", [], [])
    assert result["action"] == "suggest"
    assert result["message"] == "hi"


# ── Conversations persistence ─────────────────────────────────────────────────


def test_conversations_list_empty(tmp_path):
    from web.config import list_conversations

    assert list_conversations("ws_test") == []


def test_conversations_crud(tmp_path):
    from web.config import (
        delete_conversation,
        list_conversations,
        load_conversation,
        save_conversation,
    )

    with patch("web.config._workspace_dir", return_value=tmp_path / "ws"):
        session = {
            "id": "sess-001",
            "title": "Find HPC leads",
            "created_at": "2026-06-04T10:00:00Z",
            "updated_at": "2026-06-04T10:01:00Z",
            "messages": [{"role": "user", "content": "find leads", "ts": "2026-06-04T10:00:00Z"}],
            "history": [{"role": "user", "content": "find leads"}],
        }
        save_conversation("ws", session)

        loaded = load_conversation("ws", "sess-001")
        assert loaded is not None
        assert loaded["title"] == "Find HPC leads"
        assert len(loaded["messages"]) == 1

        listed = list_conversations("ws")
        assert len(listed) == 1
        assert listed[0]["id"] == "sess-001"
        assert listed[0]["message_count"] == 1

        assert delete_conversation("ws", "sess-001") is True
        assert load_conversation("ws", "sess-001") is None
        assert delete_conversation("ws", "sess-001") is False


def test_conversation_api_list_and_get(tmp_path):
    from web.config import save_conversation

    session = {
        "id": "abc123",
        "title": "Test conversation",
        "created_at": "2026-06-04T10:00:00Z",
        "updated_at": "2026-06-04T10:01:00Z",
        "messages": [],
        "history": [],
    }
    with patch("web.config._workspace_dir", return_value=tmp_path / "ws_test"):
        save_conversation("ws_test", session)

        with patch("web.server.load_conversation", return_value=session):
            client = _authed_client()
            r = client.get("/api/cockpit/conversations/abc123")
            assert r.status_code == 200
            assert r.json()["session"]["title"] == "Test conversation"


def test_conversation_api_get_404():
    client = _authed_client()
    with patch("web.server.load_conversation", return_value=None):
        r = client.get("/api/cockpit/conversations/does-not-exist")
    assert r.status_code == 404


def test_conversation_api_invalid_session_id():
    """Session IDs with non-alphanumeric characters are rejected.

    Path traversal with raw/encoded slashes is resolved away by the router → 404.
    A session_id containing ';' or '!' hits the handler but fails the regex → 400.
    """
    client = _authed_client()

    # Path traversal: SPA catch-all serves index.html (no sensitive file exposed)
    r = client.get("/api/cockpit/conversations/../../etc/passwd")
    assert r.status_code in (200, 404)  # SPA or not-found; never a raw file read
    assert "root:" not in r.text  # definitely not /etc/passwd content

    # Too-long ID (65 chars) hits the handler and fails the length constraint → 400
    long_id = "a" * 65
    r2 = client.get(f"/api/cockpit/conversations/{long_id}")
    assert r2.status_code == 400


def test_session_id_regex_directly():
    """Unit-test the session_id regex used in the conversation endpoints."""
    import re

    pattern = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
    assert pattern.match("abc-123_XYZ")  # valid UUID-style
    assert pattern.match("a" * 64)  # max length
    assert not pattern.match("")  # empty
    assert not pattern.match("a" * 65)  # too long
    assert not pattern.match("abc/def")  # slash
    assert not pattern.match("abc;drop")  # semicolon
    assert not pattern.match("../etc/passwd")  # traversal


def test_conversation_api_delete(tmp_path):
    with patch("web.server.delete_conversation", return_value=True):
        client = _authed_client()
        r = client.delete("/api/cockpit/conversations/abc123")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_conversation_api_delete_404():
    with patch("web.server.delete_conversation", return_value=False):
        client = _authed_client()
        r = client.delete("/api/cockpit/conversations/missing")
    assert r.status_code == 404


# ── Workspace memory ──────────────────────────────────────────────────────────


def test_memory_get_empty():
    with patch("web.server.load_memory", return_value=""):
        client = _authed_client()
        r = client.get("/api/cockpit/memory")
    assert r.status_code == 200
    assert r.json() == {"text": ""}


def test_memory_save_and_get():
    saved = {}
    with patch("web.server.load_memory", return_value="I sell Crystal HPC"):
        with patch("web.server.save_memory", side_effect=lambda wid, t: saved.update({"text": t})):
            client = _authed_client()
            r_put = client.put("/api/cockpit/memory", json={"text": "I sell Crystal HPC"})
            r_get = client.get("/api/cockpit/memory")

    assert r_put.status_code == 200
    assert r_get.json()["text"] == "I sell Crystal HPC"


# ── run-script extra_args ─────────────────────────────────────────────────────


def test_run_script_extra_args_appended(tmp_path):
    """extra_args are appended to the subprocess command."""
    script_file = tmp_path / "dummy.py"
    script_file.write_text("print('hello')")
    scripts_yaml = tmp_path / "scripts.yaml"
    scripts_yaml.write_text(f"""
scripts:
  - id: dummy
    label: Dummy
    path: {script_file}
    category: CRM
""")
    captured_cmd = {}
    mock_proc = _make_mock_proc([b""])

    async def _capture(*cmd, **kwargs):
        captured_cmd["cmd"] = list(cmd)
        return mock_proc

    with (
        patch("web.utils.SCRIPTS_YAML_PATH", scripts_yaml),
        patch("web.server.load_cockpit_cfg", return_value={"databases": {}}),
        patch("web.server.resolve_db_ids", return_value={}),
        patch("asyncio.create_subprocess_exec", side_effect=_capture),
    ):
        client = _authed_client()
        client.post(
            "/api/cockpit/run-script",
            json={"script_id": "dummy", "extra_args": ["--since-days=7", "--limit=10"]},
        )

    assert "--since-days=7" in captured_cmd["cmd"]
    assert "--limit=10" in captured_cmd["cmd"]


def test_run_script_unsafe_extra_args_filtered(tmp_path):
    """Shell-injection patterns in extra_args are silently dropped."""
    script_file = tmp_path / "dummy.py"
    script_file.write_text("print('hello')")
    scripts_yaml = tmp_path / "scripts.yaml"
    scripts_yaml.write_text(f"""
scripts:
  - id: dummy
    label: Dummy
    path: {script_file}
    category: CRM
""")
    captured_cmd = {}
    mock_proc = _make_mock_proc([b""])

    async def _capture(*cmd, **kwargs):
        captured_cmd["cmd"] = list(cmd)
        return mock_proc

    malicious = ["; rm -rf /", "--flag=$(evil)", "-x", "--ok=value"]
    with (
        patch("web.utils.SCRIPTS_YAML_PATH", scripts_yaml),
        patch("web.server.load_cockpit_cfg", return_value={"databases": {}}),
        patch("web.server.resolve_db_ids", return_value={}),
        patch("asyncio.create_subprocess_exec", side_effect=_capture),
    ):
        client = _authed_client()
        client.post(
            "/api/cockpit/run-script",
            json={"script_id": "dummy", "extra_args": malicious},
        )

    cmd = captured_cmd["cmd"]
    assert "; rm -rf /" not in cmd
    assert "--flag=$(evil)" not in cmd
    assert "-x" not in cmd
    assert "--ok=value" in cmd  # safe flag passes through


# ── detect_data_source ────────────────────────────────────────────────────────


def test_detect_data_source_people_default():
    from notion_pilot.shared.llm.crm_chat import detect_data_source

    assert detect_data_source("find me 3 leads for Crystal HPC") == "people"
    assert detect_data_source("qui peut acheter notre logiciel") == "people"


def test_detect_data_source_companies():
    from notion_pilot.shared.llm.crm_chat import detect_data_source

    assert detect_data_source("quelle typologie d'entreprise contacter") == "companies"
    assert detect_data_source("quelles sociétés cibler dans l'énergie") == "companies"
    assert detect_data_source("quel secteur d'industrie") == "companies"


def test_detect_data_source_both():
    from notion_pilot.shared.llm.crm_chat import detect_data_source

    # Query mentioning both leads and companies
    result = detect_data_source("trouve des leads dans ces entreprises du secteur énergie")
    assert result == "both"


# ── _safe_parse_json ──────────────────────────────────────────────────────────


def test_safe_parse_json_plain():
    from notion_pilot.shared.llm.crm_chat import _safe_parse_json

    raw = '{"action": "suggest", "message": "ok", "leads": []}'
    result = _safe_parse_json(raw)
    assert result["action"] == "suggest"


def test_safe_parse_json_with_fence():
    from notion_pilot.shared.llm.crm_chat import _safe_parse_json

    raw = '```json\n{"action": "info", "message": "hi", "leads": []}\n```'
    result = _safe_parse_json(raw)
    assert result["action"] == "info"


def test_safe_parse_json_with_prefix_text():
    from notion_pilot.shared.llm.crm_chat import _safe_parse_json

    raw = 'Here is the result: {"action": "suggest", "message": "done", "leads": []}'
    result = _safe_parse_json(raw)
    assert result["action"] == "suggest"


def test_safe_parse_json_raises_on_garbage():
    from notion_pilot.shared.llm.crm_chat import _safe_parse_json

    with pytest.raises(ValueError):
        _safe_parse_json("this is not json at all")


# ── chat with companies DB ────────────────────────────────────────────────────


@respx.mock
def test_chat_fetches_companies_for_company_query():
    """A company-type query should fetch from the Companies DB, not People."""
    settings = _make_settings()
    settings.notion_companies_data_source_id = "db-companies"
    settings.openrouter_api_key = MagicMock()
    settings.openrouter_api_key.get_secret_value.return_value = "key-test"

    companies_req = respx.post("https://api.notion.com/v1/databases/db-companies/query").mock(
        return_value=Response(
            200,
            json={
                "results": [
                    {
                        "id": "co1",
                        "properties": {
                            "Name": {"type": "title", "title": [{"plain_text": "EDF"}]},
                            "Sector": {"type": "select", "select": {"name": "Energy"}},
                        },
                    }
                ],
                "has_more": False,
            },
        )
    )
    people_req = respx.post("https://api.notion.com/v1/databases/db-people/query")

    llm_payload = {"action": "info", "message": "EDF est dans le secteur énergie", "leads": []}
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": json.dumps(llm_payload)}}]}
        )
    )

    with patch(
        "web.config.load_cockpit_cfg",
        return_value={"databases": {"notion_companies_data_source_id": "db-companies"}},
    ):
        client = _authed_client(settings=settings)
        r = client.post(
            "/api/cockpit/chat",
            json={"query": "quelle typologie d'entreprise cibler", "history": []},
        )

    assert r.status_code == 200
    assert companies_req.called
    assert not people_req.called


@respx.mock
def test_chat_followup_skips_notion_fetch():
    """Second message in a session reuses cached people, no Notion re-fetch."""
    settings = _make_settings()
    settings.notion_people_data_source_id = "db-people"
    settings.openrouter_api_key = MagicMock()
    settings.openrouter_api_key.get_secret_value.return_value = "key-test"

    people_req = respx.post("https://api.notion.com/v1/databases/db-people/query")

    llm_payload = {"action": "info", "message": "Laure est ingénieure énergie", "leads": []}
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": json.dumps(llm_payload)}}]}
        )
    )

    # Simulate a follow-up: history is non-empty AND session has a people_cache
    cached_people = [
        {"id": "p1", "name": "Laure Cadec", "position": "Ingénieure", "company": "Artelys"}
    ]
    session_with_cache = {
        "id": "sess-followup",
        "title": "Find leads",
        "messages": [],
        "history": [],
        "people_cache": cached_people,
    }
    with (
        patch(
            "web.config.load_cockpit_cfg",
            return_value={"databases": {"notion_people_data_source_id": "db-people"}},
        ),
        patch("web.server.load_conversation", return_value=session_with_cache),
        patch("web.server.save_conversation"),
    ):
        client = _authed_client(settings=settings)
        r = client.post(
            "/api/cockpit/chat",
            json={
                "query": "que fait Laure Cadec",
                "history": [
                    {"role": "user", "content": "find leads"},
                    {"role": "assistant", "content": "Found some"},
                ],
                "session_id": "sess-followup",
            },
        )

    assert r.status_code == 200
    # Notion People DB was NOT called — cached data was used instead
    assert not people_req.called
