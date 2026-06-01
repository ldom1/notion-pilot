"""CRM command registry for Telegram. Adding a command = one new COMMANDS entry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx
from loguru import logger

from notion_pilot.crm.conv_state import ConvState
from notion_pilot.shared.config import Settings


@dataclass
class FieldDef:
    name: str
    prompt: str
    required: bool = True


@dataclass
class CommandDef:
    name: str
    description: str
    fields: list[FieldDef]
    llm_prompt: str
    handler: Callable[[dict[str, str], Settings], Awaitable[str]]


def _notion_token(settings: Settings) -> str:
    if settings.notion_token is None:
        raise ValueError("NOTION_TOKEN is required for CRM commands")
    return settings.notion_token.get_secret_value()


# ── Handlers ──────────────────────────────────────────────────────────────────


async def _handle_people(collected: dict[str, str], settings: Settings) -> str:
    from notion_client import AsyncClient

    from notion_pilot.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer, PersonRecord

    client = AsyncClient(auth=_notion_token(settings))
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id or "")
    people_syncer = NotionPeopleSyncer(
        client, settings.notion_people_data_source_id or "", company_syncer
    )
    await company_syncer.load_snapshot()
    await people_syncer.load_snapshot()

    record = PersonRecord(
        name=collected["name"],
        company=collected.get("company", ""),
        position=collected.get("position", ""),
        email=collected.get("email", ""),
        linkedin_url=collected.get("linkedin_url", ""),
    )
    result = await people_syncer.upsert(record)
    action = "Already in Notion" if result.status in ("skipped", "review") else "Added to Notion"
    return f"✓ {action}: {record.name} @ {record.company}"


async def _handle_company(collected: dict[str, str], settings: Settings) -> str:
    from notion_client import AsyncClient

    from notion_pilot.crm.syncer import NotionCompanySyncer

    client = AsyncClient(auth=_notion_token(settings))
    syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id or "")
    await syncer.load_snapshot()
    page_id = await syncer.get_or_create(collected["name"])
    return f"✓ Company in Notion: {collected['name']} (id: {page_id[:8]}…)"


async def _handle_deal(collected: dict[str, str], settings: Settings) -> str:
    import httpx as _httpx

    from notion_pilot.crm.deals import DealRecord, NotionDealsSyncer

    if not settings.notion_deals_database_id:
        return "⚠ NOTION_DEALS_DATABASE_ID not set — cannot create deal."

    async with _httpx.AsyncClient() as http:
        syncer = NotionDealsSyncer(http, _notion_token(settings), settings.notion_deals_database_id)
        deal = DealRecord(
            title=collected["title"],
            stage=collected.get("stage", "Prospect"),
            notes=collected.get("notes", ""),
        )
        _page_id, created = await syncer.upsert(deal)
    action = "Created" if created else "Updated"
    return f"✓ {action} deal: {deal.title}"


async def _handle_lead(collected: dict[str, str], settings: Settings) -> str:
    """Create a person + a deal linked to them."""
    person_msg = await _handle_people(collected, settings)
    if settings.notion_deals_database_id:
        deal_collected = {
            "title": f"Lead: {collected['name']} @ {collected.get('company', '')}",
            "notes": collected.get("notes", ""),
        }
        deal_msg = await _handle_deal(deal_collected, settings)
        return f"{person_msg}\n{deal_msg}"
    return person_msg


async def _handle_enrich(collected: dict[str, str], settings: Settings) -> str:
    from notion_pilot.shared.utils.enrichment import enrich_person

    enrichment = await enrich_person(collected["name"], collected.get("company", ""), settings)
    parts = []
    if enrichment.email:
        parts.append(f"email: {enrichment.email}")
    if enrichment.phone:
        parts.append(f"phone: {enrichment.phone}")
    if enrichment.linkedin_url:
        parts.append(f"linkedin: {enrichment.linkedin_url}")
    if enrichment.seniority:
        parts.append(f"seniority: {enrichment.seniority}")
    if not parts:
        return f"No enrichment data found for {collected['name']}."
    return f"✓ Enriched {collected['name']}:\n" + "\n".join(f"  • {p}" for p in parts)


async def _handle_knowledge(_collected: dict[str, str], _settings: Settings) -> str:
    return "__KNOWLEDGE__"  # sentinel: caller routes to knowledge pipeline


# ── Field extraction via LLM ──────────────────────────────────────────────────


async def extract_fields_from_text(
    text: str, cmd: CommandDef, settings: Settings
) -> dict[str, str]:
    """Extract command fields from free-form text using OpenRouter LLM."""
    if not settings.openrouter_api_key:
        return {}
    field_names = [f.name for f in cmd.fields]
    prompt = (
        f"{cmd.llm_prompt}\n\n"
        f"Text: {text}\n\n"
        f"Return JSON with keys: {', '.join(field_names)}. "
        "Use empty string for any field not found in the text."
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openrouter_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
        resp.raise_for_status()
        data = json.loads(resp.json()["choices"][0]["message"]["content"])
        return {k: str(v) for k, v in data.items() if v}
    except Exception:  # noqa: BLE001
        logger.warning("commands: LLM field extraction failed")
        return {}


def get_next_prompt(cmd: CommandDef, state: ConvState) -> str | None:
    """Return the prompt for the next required field missing from state, or None if complete."""
    for f in cmd.fields:
        if f.required and not state.collected.get(f.name):
            return f.prompt
    return None


# ── Command registry ──────────────────────────────────────────────────────────


COMMANDS: dict[str, CommandDef] = {
    "lead": CommandDef(
        name="lead",
        description="Add a new sales lead (person + deal)",
        fields=[
            FieldDef("name", "What is the lead's full name?"),
            FieldDef("company", "Which company do they work for?"),
            FieldDef("position", "What is their role/position?", required=False),
            FieldDef("notes", "Any notes about this lead?", required=False),
        ],
        llm_prompt=(
            "Extract the name, company, position, and notes from this message about a sales lead. "
            "name and company are most important."
        ),
        handler=_handle_lead,
    ),
    "people": CommandDef(
        name="people",
        description="Add or update a contact in the People database",
        fields=[
            FieldDef("name", "Full name of the person?"),
            FieldDef("company", "Which company?"),
            FieldDef("position", "Their role/title?", required=False),
            FieldDef("email", "Email address?", required=False),
            FieldDef("linkedin_url", "LinkedIn URL?", required=False),
        ],
        llm_prompt=(
            "Extract the person's name, company, position, email, and LinkedIn URL "
            "from this message."
        ),
        handler=_handle_people,
    ),
    "company": CommandDef(
        name="company",
        description="Add or update a company in the Companies database",
        fields=[
            FieldDef("name", "Company name?"),
            FieldDef("website", "Website URL?", required=False),
            FieldDef("country", "Country (ISO code)?", required=False),
        ],
        llm_prompt="Extract the company name, website, and country from this message.",
        handler=_handle_company,
    ),
    "deal": CommandDef(
        name="deal",
        description="Add or update a deal in the Deals database",
        fields=[
            FieldDef("title", "Deal name/title?"),
            FieldDef(
                "stage",
                "Stage? (Prospect / Qualification / Proposal / Negotiation)",
                required=False,
            ),
            FieldDef("notes", "Any notes?", required=False),
        ],
        llm_prompt="Extract the deal title, stage, and notes from this message.",
        handler=_handle_deal,
    ),
    "enrich": CommandDef(
        name="enrich",
        description="Look up enrichment data for a person",
        fields=[
            FieldDef("name", "Person's full name?"),
            FieldDef("company", "Which company?"),
        ],
        llm_prompt="Extract the person's name and company from this message.",
        handler=_handle_enrich,
    ),
    "knowledge": CommandDef(
        name="knowledge",
        description="Route this message to the knowledge pipeline (default behaviour)",
        fields=[],
        llm_prompt="",
        handler=_handle_knowledge,
    ),
}
