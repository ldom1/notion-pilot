import httpx
import pytest

from notion_pilot.shared.notion_views import (
    NOTION_API,
    Budget,
    BudgetExhausted,
    TERMINAL_STAGES,
    VIEW_SPECS,
    create_home_views,
    get_views_api_version,
    view_body,
    views_request,
)


def _resp(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=body or {}, request=httpx.Request("GET", NOTION_API))


class ScriptedClient:
    """Returns the scripted statuses in order and records every request."""

    def __init__(self, statuses: list[int]):
        self.statuses = statuses
        self.calls: list[dict] = []

    async def request(self, method, url, json=None, headers=None):
        self.calls.append({"method": method, "url": url, "json": json, "headers": headers or {}})
        return _resp(self.statuses[len(self.calls) - 1])


async def _no_sleep(_: float) -> None:
    return None


def test_views_version_defaults_to_2025_09_03(monkeypatch):
    monkeypatch.delenv("NOTION_VIEWS_VERSION", raising=False)
    assert get_views_api_version() == "2025-09-03"


def test_views_version_accepts_allowlisted_override(monkeypatch):
    monkeypatch.setenv("NOTION_VIEWS_VERSION", "2026-03-11")
    assert get_views_api_version() == "2026-03-11"


def test_views_version_rejects_unknown(monkeypatch):
    monkeypatch.setenv("NOTION_VIEWS_VERSION", "2022-06-28")
    with pytest.raises(ValueError, match="Unsupported Notion Views API version"):
        get_views_api_version()


async def test_views_request_sends_the_configured_version(monkeypatch):
    monkeypatch.setenv("NOTION_VIEWS_VERSION", "2026-03-11")
    client = ScriptedClient([200])
    await views_request(client, "GET", "/views/v1", budget=Budget())
    assert client.calls[0]["headers"]["Notion-Version"] == "2026-03-11"
    assert client.calls[0]["url"] == f"{NOTION_API}/views/v1"


async def test_views_request_retries_server_errors_twice_then_returns():
    client = ScriptedClient([503, 503, 503])
    r = await views_request(client, "POST", "/views", budget=Budget(), sleep=_no_sleep)
    assert r.status_code == 503
    assert len(client.calls) == 3


async def test_views_request_does_not_retry_client_errors():
    client = ScriptedClient([400])
    r = await views_request(client, "POST", "/views", budget=Budget(), sleep=_no_sleep)
    assert r.status_code == 400
    assert len(client.calls) == 1


async def test_budget_is_checked_before_a_retry():
    now = [0.0]
    budget = Budget(seconds=20.0, clock=lambda: now[0])
    client = ScriptedClient([503, 200])

    async def slow_sleep(_: float) -> None:
        now[0] = 21.0

    with pytest.raises(BudgetExhausted):
        await views_request(client, "POST", "/views", budget=budget, sleep=slow_sleep)
    assert len(client.calls) == 1


SPECS = {spec.key: spec for spec in VIEW_SPECS}
PROPS = {
    "Stage": {"id": "stg", "type": "select"},
    "Stale Deal": {"id": "stl", "type": "formula"},
    "Days Since Last Activity": {"id": "dsl", "type": "formula"},
    "Expected Close Date": {"id": "ecd", "type": "date"},
    "Date": {"id": "dt", "type": "date"},
}


def _body(key: str, props: dict = PROPS) -> dict:
    return view_body(
        SPECS[key], data_source_id="ds", page_id="page", after_block_id="heading", props=props
    )


def test_view_specs_are_in_page_order():
    assert [s.key for s in VIEW_SPECS] == [
        "pipeline",
        "needs_attention",
        "closing_soon",
        "recent_activity",
    ]


def test_every_view_is_a_linked_view_placed_after_the_heading():
    for key in SPECS:
        body = _body(key)
        assert body["create_database"] == {
            "parent": {"type": "page_id", "page_id": "page"},
            "position": {"type": "after_block", "block_id": "heading"},
        }
        assert body["data_source_id"] == "ds"


def test_pipeline_board_groups_by_the_resolved_select_stage():
    body = _body("pipeline")
    assert body["type"] == "board"
    assert body["configuration"]["group_by"] == {
        "type": "select",
        "property_id": "stg",
        "sort": {"type": "manual"},
    }
    assert body["filter"] == {"property": "Stage", "select": {"does_not_equal": TERMINAL_STAGES}}


def test_pipeline_board_on_a_status_stage_groups_by_group():
    body = _body("pipeline", PROPS | {"Stage": {"id": "stg", "type": "status"}})
    assert body["configuration"]["group_by"]["group_by"] == "group"
    assert body["filter"] == {"property": "Stage", "status": {"does_not_equal": TERMINAL_STAGES}}


def test_needs_attention_filters_on_the_stale_deal_formula():
    body = _body("needs_attention")
    assert body["filter"] == {"property": "Stale Deal", "formula": {"checkbox": {"equals": True}}}
    assert body["sorts"] == [{"property": "Days Since Last Activity", "direction": "descending"}]


def test_closing_soon_uses_a_relative_date_never_fixed_bounds():
    body = _body("closing_soon")
    date_filter, stage_filter = body["filter"]["and"]
    assert date_filter == {"property": "Expected Close Date", "date": {"next_month": {}}}
    assert stage_filter["select"]["does_not_equal"] == TERMINAL_STAGES
    assert "on_or_after" not in str(body) and "before" not in str(body)


def test_recent_activity_shows_the_past_month_newest_first():
    body = _body("recent_activity")
    assert body["filter"] == {"property": "Date", "date": {"past_month": {}}}
    assert body["sorts"] == [{"property": "Date", "direction": "descending"}]


class FakeViewsApi:
    """Answers the three Views calls create_home_views makes."""

    def __init__(self, *, props: dict = PROPS, post_status: int = 200):
        self.props = props
        self.post_status = post_status
        self.posts: list[dict] = []

    async def request(self, method, url, json=None, headers=None):
        path = url.removeprefix(NOTION_API)
        if method == "GET" and path.startswith("/databases/"):
            return _resp(200, {"data_sources": [{"id": f"ds-{path.rsplit('/', 1)[-1]}"}]})
        if method == "GET" and path.startswith("/data_sources/"):
            return _resp(200, {"properties": self.props})
        self.posts.append(json)
        if self.post_status != 200:
            return _resp(self.post_status, {"message": "Invalid filter"})
        n = len(self.posts)
        return _resp(
            200,
            {"id": f"view-{n}", "parent": {"type": "database_id", "database_id": f"linked-{n}"}},
        )


async def test_create_home_views_inserts_in_reverse_so_the_page_reads_in_order():
    api = FakeViewsApi()
    outcome = await create_home_views(
        api,
        page_id="page",
        after_block_id="heading",
        databases={"Leads": "leads", "Activities": "acts"},
    )
    assert [p["name"] for p in api.posts] == [s.name for s in reversed(VIEW_SPECS)]
    assert {p["create_database"]["position"]["block_id"] for p in api.posts} == {"heading"}
    assert outcome.warnings == []
    assert outcome.views["recent_activity"] == {"view_id": "view-1", "block_id": "linked-1"}
    assert set(outcome.views) == set(SPECS)


async def test_missing_activities_skips_only_recent_activity():
    api = FakeViewsApi()
    outcome = await create_home_views(
        api,
        page_id="page",
        after_block_id="heading",
        databases={"Leads": "leads", "Activities": None},
    )
    assert set(outcome.views) == {"pipeline", "needs_attention", "closing_soon"}
    assert [s.key for s in outcome.skipped] == ["recent_activity"]
    assert outcome.warnings == [
        "🕘 Recent activity was not created: the Activities database was not found."
    ]


async def test_missing_property_skips_the_view_with_a_specific_warning():
    props = {k: v for k, v in PROPS.items() if k != "Expected Close Date"}
    outcome = await create_home_views(
        FakeViewsApi(props=props),
        page_id="page",
        after_block_id="heading",
        databases={"Leads": "leads", "Activities": "acts"},
    )
    assert outcome.warnings == [
        "📅 Closing in the next 30 days was not created: the Expected Close Date property is missing."
    ]


async def test_refused_views_become_warnings_in_page_order():
    api = FakeViewsApi(post_status=400)
    outcome = await create_home_views(
        api,
        page_id="page",
        after_block_id="heading",
        databases={"Leads": "leads", "Activities": "acts"},
    )
    assert outcome.views == {}
    assert [s.key for s in outcome.skipped] == [s.key for s in VIEW_SPECS]
    assert (
        outcome.warnings[0]
        == "📊 Pipeline was not created: Notion refused it (400: Invalid filter)."
    )
    assert len(api.posts) == 4  # no retry on 400


class EmptyDataSourcesClient:
    """Returns empty data_sources for Leads; Activities resolve normally."""

    def __init__(self, props: dict = PROPS):
        self.props = props
        self.database_gets: list[str] = []

    async def request(self, method, url, json=None, headers=None):
        path = url.removeprefix(NOTION_API)
        if method == "GET" and path.startswith("/databases/"):
            db_id = path.rsplit("/", 1)[-1]
            self.database_gets.append(db_id)
            if db_id == "leads":
                return _resp(200, {"data_sources": []})
            return _resp(200, {"data_sources": [{"id": f"ds-{db_id}"}]})
        if method == "GET" and path.startswith("/data_sources/"):
            return _resp(200, {"properties": self.props})
        return _resp(
            200, {"id": "view-1", "parent": {"type": "database_id", "database_id": "linked-1"}}
        )


async def test_empty_data_sources_does_not_raise_and_warns():
    client = EmptyDataSourcesClient()
    outcome = await create_home_views(
        client,
        page_id="page",
        after_block_id="heading",
        databases={"Leads": "leads", "Activities": "acts"},
    )
    assert set(outcome.views) == {"recent_activity"}
    assert [s.key for s in outcome.skipped] == ["pipeline", "needs_attention", "closing_soon"]
    assert all("Notion returned an unexpected response" in w for w in outcome.warnings[:3])
    assert client.database_gets.count("leads") == 1
