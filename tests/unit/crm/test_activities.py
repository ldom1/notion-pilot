"""Unit tests for crm/activities.py — mocked httpx."""

from unittest.mock import AsyncMock, MagicMock

import httpx

from notion_pilot.crm.activities import ActivityRecord, NotionActivitiesLog


def _mock_client(create_id: str = "new-activity-id", query_results: list | None = None):
    mock = AsyncMock(spec=httpx.AsyncClient)
    create_resp = MagicMock()
    create_resp.raise_for_status = MagicMock()
    create_resp.json.return_value = {"id": create_id}
    query_resp = MagicMock()
    query_resp.raise_for_status = MagicMock()
    query_resp.json.return_value = {"results": query_results or []}

    async def _post(url, **kw):
        if "databases" in url:
            return query_resp
        return create_resp

    mock.post = _post
    return mock


async def test_create_returns_page_id():
    client = _mock_client("activity-123")
    log = NotionActivitiesLog(client, "token", "db-id")
    activity = ActivityRecord(title="Call with Jean", type="📞 Call")
    page_id = await log.create(activity)
    assert page_id == "activity-123"


async def test_create_sets_type_and_relations():
    captured = {}

    async def patched_post(url, **kw):
        if "databases" not in url:
            captured.update(json=kw.get("json", {}))
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": "x", "results": []}
        return resp

    client = _mock_client()
    client.post = patched_post
    log = NotionActivitiesLog(client, "token", "db-id")
    await log.create(
        ActivityRecord(title="Call", type="📞 Call", deal_id="deal-1", person_id="person-1")
    )
    props = captured["json"]["properties"]
    assert props["Type"]["select"]["name"] == "📞 Call"
    assert props["Deal"]["relation"] == [{"id": "deal-1"}]
    assert props["Person"]["relation"] == [{"id": "person-1"}]


async def test_create_omits_unset_optional_fields():
    captured = {}

    async def patched_post(url, **kw):
        if "databases" not in url:
            captured.update(json=kw.get("json", {}))
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": "x", "results": []}
        return resp

    client = _mock_client()
    client.post = patched_post
    log = NotionActivitiesLog(client, "token", "db-id")
    await log.create(ActivityRecord(title="Call", type="📞 Call"))
    props = captured["json"]["properties"]
    assert "Deal" not in props
    assert "Outcome" not in props
    assert "Duration (min)" not in props


async def test_list_recent_parses_results():
    page = {
        "id": "activity-abc",
        "properties": {
            "Name": {"title": [{"plain_text": "Call with Jean"}]},
            "Type": {"select": {"name": "📞 Call"}},
            "Outcome": {"select": {"name": "✅ Positive"}},
            "Date": {"date": {"start": "2026-07-20"}},
            "Next Step": {"rich_text": [{"plain_text": "Follow up next week"}]},
            "Next Step Date": {"date": {"start": "2026-07-27"}},
        },
    }
    client = _mock_client(query_results=[page])
    log = NotionActivitiesLog(client, "token", "db-id")
    results = await log.list_recent()
    assert results == [
        {
            "page_id": "activity-abc",
            "title": "Call with Jean",
            "type": "📞 Call",
            "outcome": "✅ Positive",
            "date": "2026-07-20",
            "next_step": "Follow up next week",
            "next_step_date": "2026-07-27",
        }
    ]


async def test_list_recent_filters_by_deal_id():
    captured = {}

    async def patched_post(url, **kw):
        captured.update(json=kw.get("json", {}))
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"results": []}
        return resp

    client = _mock_client()
    client.post = patched_post
    log = NotionActivitiesLog(client, "token", "db-id")
    await log.list_recent(deal_id="deal-42")
    assert captured["json"]["filter"] == {"property": "Deal", "relation": {"contains": "deal-42"}}
