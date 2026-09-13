"""Notion Views API — the linked views on the CRM home page.

Kept apart from workspace.py because it speaks a newer Notion-Version than the
rest of the bootstrap, which stays on 2022-06-28 for its response shapes. Every
call here is optional: callers turn failures into warnings, never exceptions.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

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
