import httpx
import pytest

from notion_pilot.shared.notion_views import (
    NOTION_API,
    Budget,
    BudgetExhausted,
    get_views_api_version,
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
