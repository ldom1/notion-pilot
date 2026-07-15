"""MCP server entrypoint — stdio transport, registers the notion-pilot CRM tools."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from notion_pilot.mcp import tools as t
from notion_pilot.mcp.models import BatchResult, CompanyRecord, PersonRecord
from notion_pilot.mcp.session import SyncerSession
from notion_pilot.shared.config import load_settings

_settings = load_settings()
_session = SyncerSession(_settings)


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    # start_prewarm() creates an asyncio.Task, which requires a running event
    # loop — FastMCP's lifespan runs inside one, unlike module import time.
    # See session.py / design §2 "Cold-start latency".
    _session.start_prewarm()
    yield


mcp = FastMCP("notion-crm", lifespan=_lifespan)


@mcp.tool()
async def upsert_people(records: list[PersonRecord], confirm: bool = False) -> BatchResult:
    """Upsert people into the Notion People database, dedup-checked. Defaults
    to a dry-run preview (confirm=False) — pass confirm=True to actually write."""
    return await t.upsert_people(_session, records, confirm)


@mcp.tool()
async def upsert_companies(records: list[CompanyRecord], confirm: bool = False) -> BatchResult:
    """Upsert companies into the Notion Companies database, dedup-checked.
    Defaults to a dry-run preview (confirm=False) — pass confirm=True to write."""
    return await t.upsert_companies(_session, records, confirm)


@mcp.tool()
async def find_duplicates(
    target: str = "both", threshold: float = 85.0
) -> list[dict[str, float | str]]:
    """Find likely-duplicate People/Companies pairs already in Notion via fuzzy
    name matching. target: 'people', 'companies', or 'both'."""
    return await t.find_duplicates(_session, target, threshold)


@mcp.tool()
async def enrich_people(
    page_ids: list[str] | None = None, limit: int = 9999, confirm: bool = False
) -> BatchResult:
    """Enrich People records missing seniority/role/email via the Apollo →
    Brave → Perplexity → LLM waterfall. Defaults to a dry-run preview."""
    return await t.enrich_people(_session, _settings, page_ids, limit, confirm)


@mcp.tool()
async def enrich_companies(
    page_ids: list[str] | None = None, limit: int = 9999, confirm: bool = False
) -> BatchResult:
    """Enrich Company records missing sector/size/country/LinkedIn via the same
    waterfall as enrich_people. Defaults to a dry-run preview."""
    return await t.enrich_companies(_session, _settings, page_ids, limit, confirm)


@mcp.tool()
async def rank_contacts_for_pitch(
    pitch: str,
    top_k: int = 10,
    company: str | None = None,
    seniority: str | None = None,
    role_type: str | None = None,
) -> list[dict[str, object]]:
    """Rank existing CRM contacts by relevance to a B2B sales pitch (LLM-powered)."""
    return await t.rank_contacts_for_pitch(
        _session, _settings, pitch, top_k, company, seniority, role_type
    )


@mcp.tool()
async def search_people(query: str, limit: int = 10) -> list[dict[str, object]]:
    """Fuzzy-search existing People by name/company — read-only, no write."""
    return await t.search_people(_session, query, limit)


@mcp.tool()
async def search_companies(query: str, limit: int = 10) -> list[dict[str, object]]:
    """Fuzzy-search existing Companies by name — read-only, no write."""
    return await t.search_companies(_session, query, limit)


@mcp.tool(name="get_recent_people")
async def get_recent_people_endpoint() -> list[dict[str, object]]:
    """People added to Notion in the last 7 days."""
    return await t.get_recent_people_tool(_settings)


@mcp.tool(name="get_open_leads")
async def get_open_leads_endpoint() -> list[dict[str, object]]:
    """Open (non-closed) deals from the Deals database."""
    return await t.get_open_leads_tool(_settings)


@mcp.tool()
async def refresh_notion_snapshot() -> dict[str, int]:
    """Force-reload the cached People/Companies snapshot from Notion (use if
    the Telegram bot or web cockpit may have written since this session started)."""
    return await t.refresh_notion_snapshot(_session)


if __name__ == "__main__":
    mcp.run()
