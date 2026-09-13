"""Notion Views API — the linked views on the CRM home page.

Kept apart from workspace.py because it speaks a newer Notion-Version than the
rest of the bootstrap, which stays on 2022-06-28 for its response shapes. Every
call here is optional: callers turn failures into warnings, never exceptions.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

NOTION_API = "https://api.notion.com/v1"
DEFAULT_NOTION_VIEWS_VERSION = "2025-09-03"
_SUPPORTED_VIEWS_VERSIONS = frozenset({"2025-09-03", "2026-03-11"})
RETRY_STATUSES = frozenset({429, 500, 503, 504, 529})
MAX_RETRIES = 2
VIEWS_BUDGET_SECONDS = 20.0

JsonDict = dict[str, Any]


def get_views_api_version() -> str:
    version = os.getenv("NOTION_VIEWS_VERSION", DEFAULT_NOTION_VIEWS_VERSION)
    if version not in _SUPPORTED_VIEWS_VERSIONS:
        raise ValueError(f"Unsupported Notion Views API version: {version}")
    return version


class BudgetExhausted(Exception):
    """The wall-clock budget for optional Views work ran out."""


class Budget:
    """One budget shared by every Views call in a deploy or upgrade."""

    def __init__(
        self,
        seconds: float = VIEWS_BUDGET_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._deadline = clock() + seconds

    def exhausted(self) -> bool:
        return self._clock() >= self._deadline


async def views_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    budget: Budget,
    json: JsonDict | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> httpx.Response:
    """One Views call: configured version, bounded retries, shared budget.

    The budget is checked before every attempt, retries included. An attempt
    already in flight is allowed to finish.
    """
    headers = {"Notion-Version": get_views_api_version()}
    for attempt in range(MAX_RETRIES + 1):
        if budget.exhausted():
            raise BudgetExhausted
        r = await client.request(method, f"{NOTION_API}{path}", json=json, headers=headers)
        if r.status_code not in RETRY_STATUSES or attempt == MAX_RETRIES:
            return r
        await sleep(2**attempt)
    raise AssertionError("unreachable")


TERMINAL_STAGES = ["Closed Won", "Closed Lost", "No Answer"]


@dataclass(frozen=True)
class ViewSpec:
    key: str
    name: str
    source: Literal["Leads", "Activities"]
    type: Literal["board", "table"]
    requires: tuple[str, ...]
    manual_steps: tuple[str, ...]


# Page order, top to bottom. Manual steps are what the CRM page shows when the
# API refuses a view, so the user can add it in Notion in a minute.
VIEW_SPECS: tuple[ViewSpec, ...] = (
    ViewSpec(
        "pipeline",
        "📊 Pipeline",
        "Leads",
        "board",
        ("Stage",),
        (
            "Under “This week”, type /linked and pick Leads.",
            "Choose Board and group by Stage.",
            "Filter: Stage is not Closed Won, Closed Lost or No Answer.",
        ),
    ),
    ViewSpec(
        "needs_attention",
        "⚠️ Needs attention",
        "Leads",
        "table",
        ("Stale Deal", "Days Since Last Activity"),
        (
            "Under “This week”, type /linked and pick Leads.",
            "Choose Table. Filter: Stale Deal is checked.",
            "Sort: Days Since Last Activity, descending.",
        ),
    ),
    ViewSpec(
        "closing_soon",
        "📅 Closing in the next 30 days",
        "Leads",
        "table",
        ("Expected Close Date", "Stage"),
        (
            "Under “This week”, type /linked and pick Leads.",
            "Choose Table. Filter: Expected Close Date is within the next month, "
            "and Stage is not Closed Won, Closed Lost or No Answer.",
            "Sort: Expected Close Date, ascending.",
        ),
    ),
    ViewSpec(
        "recent_activity",
        "🕘 Recent activity",
        "Activities",
        "table",
        ("Date",),
        (
            "Under “This week”, type /linked and pick Activities.",
            "Choose Table. Filter: Date is within the past month.",
            "Sort: Date, descending.",
        ),
    ),
)


def _open_stage_filter(stage: JsonDict) -> JsonDict:
    # A wizard deploy has a select Stage; a legacy CRM may have a status one.
    return {"property": "Stage", stage["type"]: {"does_not_equal": TERMINAL_STAGES}}


def view_body(
    spec: ViewSpec,
    *,
    data_source_id: str,
    page_id: str,
    after_block_id: str,
    props: dict[str, JsonDict],
) -> JsonDict:
    """POST /v1/views body for one linked view on the CRM home page."""
    body: JsonDict = {
        "create_database": {
            "parent": {"type": "page_id", "page_id": page_id},
            "position": {"type": "after_block", "block_id": after_block_id},
        },
        "data_source_id": data_source_id,
        "name": spec.name,
        "type": spec.type,
    }
    if spec.key == "pipeline":
        stage = props["Stage"]
        group_by: JsonDict = {
            "type": stage["type"],
            "property_id": stage["id"],
            "sort": {"type": "manual"},
        }
        if stage["type"] == "status":
            group_by["group_by"] = "group"
        body["filter"] = _open_stage_filter(stage)
        body["configuration"] = {"type": "board", "group_by": group_by}
    elif spec.key == "needs_attention":
        body["filter"] = {"property": "Stale Deal", "formula": {"checkbox": {"equals": True}}}
        body["sorts"] = [{"property": "Days Since Last Activity", "direction": "descending"}]
    elif spec.key == "closing_soon":
        # Notion has no "this_month" filter, and fixed bounds would go stale the
        # next month without anyone noticing. next_month is relative.
        body["filter"] = {
            "and": [
                {"property": "Expected Close Date", "date": {"next_month": {}}},
                _open_stage_filter(props["Stage"]),
            ]
        }
        body["sorts"] = [{"property": "Expected Close Date", "direction": "ascending"}]
    elif spec.key == "recent_activity":
        body["filter"] = {"property": "Date", "date": {"past_month": {}}}
        body["sorts"] = [{"property": "Date", "direction": "descending"}]
    return body


async def resolve_data_source(
    client: httpx.AsyncClient, database_id: str, *, budget: Budget
) -> tuple[str, dict[str, JsonDict]]:
    """(data_source_id, properties by name) for a database."""
    r = await views_request(client, "GET", f"/databases/{database_id}", budget=budget)
    r.raise_for_status()
    data_source_id = str(r.json()["data_sources"][0]["id"])
    r = await views_request(client, "GET", f"/data_sources/{data_source_id}", budget=budget)
    r.raise_for_status()
    return data_source_id, r.json()["properties"]


@dataclass
class ViewsOutcome:
    views: dict[str, dict[str, str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    skipped: list[ViewSpec] = field(default_factory=list)


def _refusal(r: httpx.Response) -> str:
    try:
        message = r.json().get("message", "")
    except ValueError:
        message = r.text[:200]
    return f"Notion refused it ({r.status_code}: {message})"


async def create_home_views(
    client: httpx.AsyncClient,
    *,
    page_id: str,
    after_block_id: str,
    databases: dict[str, str | None],
    budget: Budget | None = None,
) -> ViewsOutcome:
    """Create the four linked views under one heading. Never raises for a view.

    Views are inserted in reverse, each directly after the heading, so the page
    reads in VIEW_SPECS order without knowing any view's block id.
    """
    budget = budget or Budget()
    outcome = ViewsOutcome()
    sources: dict[str, tuple[str, dict[str, JsonDict]]] = {}
    failed_sources: dict[str, str] = {}
    for spec in reversed(VIEW_SPECS):
        reason: str | None = None
        if spec.source in failed_sources:
            reason = failed_sources[spec.source]
        else:
            try:
                database_id = databases.get(spec.source)
                if database_id is None:
                    reason = f"the {spec.source} database was not found"
                else:
                    if spec.source not in sources:
                        sources[spec.source] = await resolve_data_source(
                            client, database_id, budget=budget
                        )
                    data_source_id, props = sources[spec.source]
                    missing = [name for name in spec.requires if name not in props]
                    if missing:
                        reason = f"the {', '.join(missing)} property is missing"
                    else:
                        r = await views_request(
                            client,
                            "POST",
                            "/views",
                            budget=budget,
                            json=view_body(
                                spec,
                                data_source_id=data_source_id,
                                page_id=page_id,
                                after_block_id=after_block_id,
                                props=props,
                            ),
                        )
                        if r.status_code == 200:
                            created = r.json()
                            outcome.views[spec.key] = {
                                "view_id": str(created["id"]),
                                "block_id": str(created["parent"]["database_id"]),
                            }
                        else:
                            reason = _refusal(r)
            except BudgetExhausted:
                reason = "the 20-second setup budget ran out"
            except httpx.HTTPError as exc:
                reason = f"the request failed ({exc})"
            except (IndexError, KeyError, json.JSONDecodeError) as exc:
                reason = f"malformed API response ({type(exc).__name__})"
            if (
                reason
                and databases.get(spec.source) is not None
                and spec.source not in sources
            ):
                failed_sources[spec.source] = reason
        if reason:
            outcome.warnings.append(f"{spec.name} was not created: {reason}.")
            outcome.skipped.append(spec)
    outcome.warnings.reverse()
    outcome.skipped.reverse()
    return outcome
