# tests/unit/shared/test_workspace.py
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from notion_pilot.shared.workspace import (
    NOTION_API,
    CRMWorkspaceResult,
    InboxWorkspaceResult,
    create_crm_workspace,
    create_inbox_workspace,
    create_workspace_root_page,
)


def _make_mock_client(
    named_ids: list[str],
    *,
    reverse_names: dict[str, str] | None = None,
    views_status: int = 200,
):
    """Mock httpx client for the workspace bootstrap.

    POST returns named_ids in order, then 'seeded-N' for the demo-data calls.
    GET on a database returns the reverse relation properties Notion would have
    auto-created, so _resolve_back_relation has something to discover.
    `reverse_names` maps target-db id -> the name Notion invented, letting a test
    simulate the auto-generated "Related to …" name.
    """
    call_count = 0
    patched: list[tuple[str, dict]] = []
    appended: list[dict] = []
    posted: list[dict] = []
    view_posts: list[dict] = []
    reverse = reverse_names or {}

    async def fake_post(url, **kwargs):
        nonlocal call_count
        posted.append({"url": url, "json": kwargs.get("json", {})})
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "id": named_ids[call_count] if call_count < len(named_ids) else f"seeded-{call_count}"
        }
        call_count += 1
        return resp

    async def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        props = {
            reverse.get(target, default_name): {
                "type": "relation",
                "relation": {"database_id": target},
            }
            for target, default_name in (
                ("activities-db", "Activities"),
                ("meetings-db", "Meetings"),
            )
        }
        resp.json.return_value = {"id": url.split("/")[-1], "properties": props}
        return resp

    async def fake_patch(url, **kwargs):
        body = kwargs.get("json", {})
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        if url.endswith("/children"):
            appended.append(body)
            resp.json.return_value = {
                "results": [{**b, "id": f"block-{i}"} for i, b in enumerate(body["children"])]
            }
        else:
            resp.json.return_value = {"id": url.split("/")[-1]}
            patched.append((url.split("/")[-1], body.get("properties", {})))
        return resp

    async def fake_request(method, url, json=None, headers=None):
        path = url.removeprefix(NOTION_API)
        req = httpx.Request(method, url)
        if path.startswith("/databases/"):
            return httpx.Response(200, json={"data_sources": [{"id": "ds"}]}, request=req)
        if path.startswith("/data_sources/"):
            names = ("Stage", "Stale Deal", "Days Since Last Activity", "Expected Close Date", "Date")
            props = {n: {"id": n, "type": "select" if n == "Stage" else "date"} for n in names}
            return httpx.Response(200, json={"properties": props}, request=req)
        view_posts.append(json)
        if views_status != 200:
            return httpx.Response(views_status, json={"message": "nope"}, request=req)
        n = len(view_posts)
        return httpx.Response(
            200,
            json={"id": f"view-{n}", "parent": {"type": "database_id", "database_id": f"linked-{n}"}},
            request=req,
        )

    mock_client = MagicMock()
    mock_client.post = fake_post
    mock_client.get = fake_get
    mock_client.patch = fake_patch
    mock_client.request = fake_request
    mock_client.patched = patched
    mock_client.appended = appended
    mock_client.posted = posted
    mock_client.view_posts = view_posts
    return mock_client


_CRM_IDS = [
    "crm-page",
    "companies-db",
    "people-db",
    "deals-db",
    "meetings-db",
    "activities-db",
]


@pytest.mark.asyncio
async def test_create_crm_workspace_returns_all_five_database_ids():
    """The deploy must create Activities and Meetings, not just the original three.

    log_activity hard-fails without an Activities id, and the landing page
    promises five databases.
    """
    mock_client = _make_mock_client(_CRM_IDS)
    result = await create_crm_workspace(mock_client, "parent-page-id")
    assert isinstance(result, CRMWorkspaceResult)
    assert result.crm_page_id == "crm-page"
    assert result.companies_id == "companies-db"
    assert result.people_id == "people-db"
    assert result.deals_id == "deals-db"
    assert result.meetings_id == "meetings-db"
    assert result.activities_id == "activities-db"


@pytest.mark.asyncio
async def test_rollups_key_on_the_resolved_back_relation_name():
    """Notion names the reverse of a dual relation itself, and the name is not
    requestable on create. So the rollup must key on the name read back from the
    API, never on a hardcoded guess."""
    mock_client = _make_mock_client(
        _CRM_IDS,
        reverse_names={"activities-db": "Related to Activities (Deal)"},
    )
    await create_crm_workspace(mock_client, "parent-page-id")

    rollups = [
        (db_id, props["Last Activity Date"]["rollup"])
        for db_id, props in mock_client.patched
        if "Last Activity Date" in props
    ]
    assert {db for db, _ in rollups} == {"companies-db", "people-db", "deals-db"}
    for _, cfg in rollups:
        # the discovered name, and the rename to "Activities" was attempted
        assert cfg["relation_property_name"] in {"Activities", "Related to Activities (Deal)"}
        assert cfg["rollup_property_name"] == "Date"
        assert cfg["function"] == "latest_date"

    renames = [
        props for _, props in mock_client.patched if any("name" in v for v in props.values())
    ]
    assert any(
        v.get("name") == "Activities"
        for props in renames
        for v in props.values()
        if isinstance(v, dict)
    ), "the auto-generated reverse name should be renamed to Activities"


@pytest.mark.asyncio
async def test_companies_has_no_activities_multi_select():
    """A multi_select named Activities collides with the back-relation the
    rollups depend on (it was there, and seeded, before this change)."""
    posted: list[dict] = []

    mock_client = _make_mock_client(_CRM_IDS)
    original_post = mock_client.post

    async def capture(url, **kwargs):
        posted.append({"url": url, "json": kwargs.get("json", {})})
        return await original_post(url, **kwargs)

    mock_client.post = capture
    await create_crm_workspace(mock_client, "parent-page-id")

    companies = next(
        c["json"]
        for c in posted
        if c["url"].endswith("/databases") and "Companies" in str(c["json"].get("title"))
    )
    props = companies["properties"]
    assert "Activities" not in props
    # and the French-market firmographics the enrichment skill writes are present
    for expected in ("SIREN", "CA", "Résultat net", "Marge nette %", "Année financière"):
        assert expected in props, expected


@pytest.mark.asyncio
async def test_leads_database_is_named_leads_with_english_lead_source():
    posted: list[dict] = []
    mock_client = _make_mock_client(_CRM_IDS)
    original_post = mock_client.post

    async def capture(url, **kwargs):
        posted.append({"url": url, "json": kwargs.get("json", {})})
        return await original_post(url, **kwargs)

    mock_client.post = capture
    await create_crm_workspace(mock_client, "parent-page-id")

    leads = next(
        c["json"]
        for c in posted
        if c["url"].endswith("/databases") and "Leads" in str(c["json"].get("title"))
    )
    props = leads["properties"]
    sources = {o["name"] for o in props["Lead Source"]["select"]["options"]}
    assert "Cold Outreach" in sources
    assert not any("Prospection" in s for s in sources), "French labels must not ship"
    stages = {o["name"] for o in props["Stage"]["select"]["options"]}
    assert {"Discovery / First Meeting", "Waiting for a Response"} <= stages
    products = {o["name"] for o in props["Product"]["multi_select"]["options"]}
    assert "HPC-as-a-service" not in products, "Artelys product must not ship in a generic wizard"
    for expected in ("Expected Close Date", "Primary contact", "Created time"):
        assert expected in props, expected


@pytest.mark.asyncio
async def test_create_inbox_workspace_returns_ids():
    # POST order: inbox-page, notions-db, ideas-db, tools-db, data-tech-db, then N seeding calls
    mock_client = _make_mock_client(
        ["inbox-page", "notions-db", "ideas-db", "tools-db", "data-tech-db"]
    )
    result = await create_inbox_workspace(mock_client, "parent-page-id")
    assert isinstance(result, InboxWorkspaceResult)
    assert result.inbox_page_id == "inbox-page"
    assert result.notions_id == "notions-db"
    assert result.ideas_id == "ideas-db"
    assert result.tools_id == "tools-db"
    assert result.data_tech_id == "data-tech-db"


@pytest.mark.asyncio
@respx.mock
async def test_create_workspace_root_page():
    page_id = "abcd1234efgh5678abcd1234efgh5678"
    respx.post(f"{NOTION_API}/pages").mock(return_value=httpx.Response(200, json={"id": page_id}))
    async with httpx.AsyncClient(headers={"Authorization": "Bearer token"}) as client:
        result = await create_workspace_root_page(client, "My Workspace")
    assert result == page_id
    request_body = respx.calls[0].request
    import json

    body = json.loads(request_body.content)
    assert body["parent"] == {"workspace": True}
    assert body["properties"]["title"]["title"][0]["text"]["content"] == "My Workspace"
    assert body["icon"] == {"type": "emoji", "emoji": "🚀"}
    assert "children" in body


from notion_pilot.shared.notion_views import VIEW_SPECS
from notion_pilot.shared.workspace import (
    SOURCES_TITLE,
    THIS_WEEK,
    _DEMO_DEALS,
    _plain_text,
    crm_home_blocks,
)


async def test_crm_page_is_created_empty_then_gets_the_home_template():
    mock_client = _make_mock_client(_CRM_IDS)
    await create_crm_workspace(mock_client, "parent-page-id")
    page_post = mock_client.posted[0]
    assert page_post["url"].endswith("/pages")
    assert "children" not in page_post["json"]
    assert mock_client.appended[0]["children"] == crm_home_blocks()


async def test_views_are_placed_under_this_week_and_returned():
    mock_client = _make_mock_client(_CRM_IDS)
    result = await create_crm_workspace(mock_client, "parent-page-id")
    this_week = next(i for i, b in enumerate(crm_home_blocks()) if _plain_text(b) == THIS_WEEK)
    positions = {p["create_database"]["position"]["block_id"] for p in mock_client.view_posts}
    assert positions == {f"block-{this_week}"}
    assert set(result.views) == {s.key for s in VIEW_SPECS}
    assert result.warnings == []


async def test_refused_views_do_not_abort_and_leave_manual_steps_after_sources():
    mock_client = _make_mock_client(_CRM_IDS, views_status=400)
    result = await create_crm_workspace(mock_client, "parent-page-id")
    assert result.crm_page_id == "crm-page"
    assert len(result.warnings) == 4
    sources = next(i for i, b in enumerate(crm_home_blocks()) if _plain_text(b) == SOURCES_TITLE)
    callout = mock_client.appended[1]
    assert callout["after"] == f"block-{sources}"
    assert _plain_text(callout["children"][0]) == "Some views need a minute in Notion"


def test_demo_deals_fill_every_home_view_on_day_zero():
    closing = [d for d in _DEMO_DEALS if d.get("expected_close_in_days") is not None]
    assert sorted(d["expected_close_in_days"] for d in closing) == [12, 26]
    stale = [d for d in _DEMO_DEALS if d["next_action"] is None]
    assert [d["name"] for d in stale] == ["Analytics Platform — ClearPath"]
