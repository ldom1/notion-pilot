"""Unit tests for crm/deals.py — mocked httpx."""

from unittest.mock import AsyncMock, MagicMock

import httpx

from notion_pilot.crm.deals import DealRecord, NotionDealsSyncer


def _mock_client(create_id: str = "new-deal-id", snapshot_results: list | None = None):
    mock = AsyncMock(spec=httpx.AsyncClient)
    # POST /pages → create
    create_resp = MagicMock()
    create_resp.raise_for_status = MagicMock()
    create_resp.json.return_value = {"id": create_id}
    # POST /databases/{id}/query → load snapshot
    query_resp = MagicMock()
    query_resp.raise_for_status = MagicMock()
    query_resp.json.return_value = {
        "results": snapshot_results or [],
        "has_more": False,
    }
    # PATCH /pages/{id} → update
    patch_resp = MagicMock()
    patch_resp.raise_for_status = MagicMock()
    patch_resp.json.return_value = {"id": create_id}

    async def _post(url, **kw):
        if "databases" in url:
            return query_resp
        return create_resp

    mock.post = _post
    mock.patch = AsyncMock(return_value=patch_resp)
    return mock


async def test_create_returns_page_id():
    client = _mock_client("deal-123")
    syncer = NotionDealsSyncer(client, "token", "db-id")
    deal = DealRecord(title="HPC Deal")
    page_id = await syncer.create(deal)
    assert page_id == "deal-123"


async def test_create_sets_stage():
    captured = {}

    async def patched_post(url, **kw):
        if "databases" not in url:
            captured.update(json=kw.get("json", {}))
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": "x", "results": [], "has_more": False}
        return resp

    client = _mock_client()
    client.post = patched_post
    syncer = NotionDealsSyncer(client, "token", "db-id")
    await syncer.create(DealRecord(title="Deal", stage="Proposal"))
    assert (
        captured.get("json", {})
        .get("properties", {})
        .get("Stage", {})
        .get("select", {})
        .get("name")
        == "Proposal"
    )


async def test_upsert_creates_new_when_not_in_snapshot():
    client = _mock_client(snapshot_results=[])
    syncer = NotionDealsSyncer(client, "token", "db-id")
    await syncer.load_notion_snapshot()
    page_id, created = await syncer.upsert(DealRecord(title="New Deal"))
    assert created is True
    assert page_id == "new-deal-id"


async def test_upsert_updates_existing():
    existing_page = {
        "id": "existing-id",
        "properties": {
            "Name": {"title": [{"plain_text": "Existing Deal"}]},
        },
    }
    client = _mock_client(snapshot_results=[existing_page])
    syncer = NotionDealsSyncer(client, "token", "db-id")
    await syncer.load_notion_snapshot()
    page_id, created = await syncer.upsert(DealRecord(title="Existing Deal", stage="Proposal"))
    assert created is False
    assert page_id == "existing-id"
    client.patch.assert_called_once()


async def test_load_snapshot_populates_title_map():
    existing_page = {
        "id": "deal-abc",
        "properties": {
            "Name": {"title": [{"plain_text": "My Deal"}]},
        },
    }
    client = _mock_client(snapshot_results=[existing_page])
    syncer = NotionDealsSyncer(client, "token", "db-id")
    await syncer.load_notion_snapshot()
    assert syncer._snapshot["My Deal"] == "deal-abc"
