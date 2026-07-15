"""Thin MCP client for prosper's company resolution and enrichment tools.
Return dataclasses deliberately mirror the shape of the enrichment cascade
that used to live locally in notion_pilot.shared.utils.enrichment, so
existing call sites need only change their import line."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from notion_pilot.shared.config import Settings


@dataclass
class PersonEnrichment:
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    seniority: str = ""
    role_type: list[str] = field(default_factory=list)
    country: str = ""
    source: str = ""


@dataclass
class CompanyEnrichment:
    website: str = ""
    linkedin_url: str = ""
    size: str = ""
    country: str = ""
    sector: str = ""
    tech_stack: list[str] = field(default_factory=list)
    crm_status: str = ""
    logo_url: str = ""
    source: str = ""


async def _call_prosper_tool(settings: Settings, tool_name: str, **kwargs: Any) -> dict[str, Any]:
    """Low-level MCP tool call, isolated here so tests can mock it directly
    without standing up a real MCP session."""
    async with sse_client(settings.prosper_mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=kwargs)
            return result.structuredContent or {}


async def enrich_person(
    name: str,
    company: str,
    settings: Settings,
    position: str = "",
    perplexity_model: str | None = "perplexity/sonar-pro",
) -> PersonEnrichment:
    """Calls prosper's enrich_person MCP tool. position/perplexity_model are
    accepted for call-site compatibility but unused — prosper's tool doesn't
    take them."""
    result = await _call_prosper_tool(settings, "enrich_person", name=name, company_context=company)
    return PersonEnrichment(**result)


async def enrich_company(
    name: str,
    settings: Settings,
    domain: str = "",
    perplexity_model: str | None = "perplexity/sonar-pro",
) -> CompanyEnrichment:
    """Calls prosper's enrich_company MCP tool. perplexity_model is accepted
    for call-site compatibility but unused."""
    result = await _call_prosper_tool(settings, "enrich_company", name=name, domain=domain)
    return CompanyEnrichment(**result)


async def resolve_company(name: str, settings: Settings) -> dict[str, Any]:
    """Calls prosper's resolve_company MCP tool. Returns the raw dict shape
    ({matches, best_match, confidence_level}) — callers decide their own
    confidence threshold, matching prosper's design contract."""
    return await _call_prosper_tool(settings, "resolve_company", name=name)
