"""Shared Notion workspace creation logic used by CLI scripts, Telegram /setup, and web server."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

NOTION_VERSION = "2026-03-11"
NOTION_API = "https://api.notion.com/v1"


@dataclass
class CRMWorkspaceResult:
    crm_page_id: str
    companies_id: str
    people_id: str
    deals_id: str


@dataclass
class InboxWorkspaceResult:
    inbox_page_id: str
    notions_id: str
    ideas_id: str
    tools_id: str
    data_tech_id: str


async def _create_page(client: httpx.AsyncClient, parent_page_id: str, title: str, emoji: str) -> str:
    r = await client.post(
        f"{NOTION_API}/pages",
        json={
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "icon": {"type": "emoji", "emoji": emoji},
            "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        },
    )
    r.raise_for_status()
    return str(r.json()["id"])


async def _create_db(
    client: httpx.AsyncClient,
    parent_page_id: str,
    title: str,
    properties: dict[str, Any],
    emoji: str,
) -> str:
    r = await client.post(
        f"{NOTION_API}/databases",
        json={
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "icon": {"type": "emoji", "emoji": emoji},
            "title": [{"type": "text", "text": {"content": title}}],
        },
    )
    r.raise_for_status()
    db_id: str = r.json()["id"]
    r2 = await client.patch(f"{NOTION_API}/databases/{db_id}", json={"properties": properties})
    r2.raise_for_status()
    return db_id


async def create_crm_workspace(
    client: httpx.AsyncClient,
    parent_page_id: str,
    page_title: str = "CRM",
) -> CRMWorkspaceResult:
    """Create CRM container page + Companies, People, Deals databases."""
    logger.info("workspace: creating CRM '{}'", page_title)
    crm_page_id = await _create_page(client, parent_page_id, page_title, "🏢")

    companies_id = await _create_db(client, crm_page_id, "Companies", {
        "Name": {"title": {}},
        "Sector": {"select": {"options": [
            {"name": "Energy", "color": "yellow"}, {"name": "Finance", "color": "green"},
            {"name": "Industry", "color": "blue"}, {"name": "Public Sector", "color": "purple"},
            {"name": "Telecom", "color": "orange"}, {"name": "Other", "color": "gray"},
        ]}},
        "Website": {"url": {}},
        "Notes": {"rich_text": {}},
    }, "🏭")

    people_id = await _create_db(client, crm_page_id, "People", {
        "Name": {"title": {}},
        "Company": {"relation": {"database_id": companies_id, "single_property": {}}},
        "Position": {"rich_text": {}},
        "LinkedIn": {"url": {}},
        "Email": {"email": {}},
        "Notes": {"rich_text": {}},
    }, "👥")

    deals_id = await _create_db(client, crm_page_id, "Deals", {
        "Name": {"title": {}},
        "Company": {"relation": {"database_id": companies_id, "single_property": {}}},
        "Contact": {"relation": {"database_id": people_id, "single_property": {}}},
        "Stage": {"select": {"options": [
            {"name": "Prospect", "color": "gray"}, {"name": "Qualified", "color": "blue"},
            {"name": "Proposal Sent", "color": "yellow"}, {"name": "Negotiation", "color": "orange"},
            {"name": "Closed Won", "color": "green"}, {"name": "Closed Lost", "color": "red"},
        ]}},
        "Value (euros)": {"number": {"format": "euro"}},
        "Probability (%)": {"number": {"format": "percent"}},
        "Next Action Date": {"date": {}},
        "Notes": {"rich_text": {}},
    }, "💼")

    return CRMWorkspaceResult(
        crm_page_id=crm_page_id,
        companies_id=companies_id,
        people_id=people_id,
        deals_id=deals_id,
    )


async def create_inbox_workspace(
    client: httpx.AsyncClient,
    parent_page_id: str,
    page_title: str = "Knowledge",
) -> InboxWorkspaceResult:
    """Create Knowledge container page + Notions, Ideas, Tools, Data & Technology databases."""
    logger.info("workspace: creating Knowledge '{}'", page_title)
    inbox_page_id = await _create_page(client, parent_page_id, page_title, "📚")

    notions_id = await _create_db(client, inbox_page_id, "Notions", {
        "Name": {"title": {}},
        "URL": {"url": {}},
        "Description": {"rich_text": {}},
        "Tags": {"multi_select": {}},
        "Source": {"select": {"options": [
            {"name": "Telegram"}, {"name": "Email"}, {"name": "Web"}, {"name": "Manual"},
        ]}},
        "Interest": {"select": {"options": [
            {"name": "High", "color": "red"}, {"name": "Medium", "color": "yellow"},
            {"name": "Low", "color": "gray"},
        ]}},
        "Status": {"select": {"options": [
            {"name": "À relire", "color": "yellow"}, {"name": "Lu", "color": "green"},
            {"name": "Archivé", "color": "gray"},
        ]}},
        "Date": {"date": {}},
    }, "💡")

    ideas_id = await _create_db(client, inbox_page_id, "Ideas", {
        "Name": {"title": {}},
        "Description": {"rich_text": {}},
        "Tags": {"multi_select": {}},
        "Priority": {"select": {"options": [
            {"name": "High", "color": "red"}, {"name": "Medium", "color": "yellow"},
            {"name": "Low", "color": "gray"},
        ]}},
        "Status": {"select": {"options": [
            {"name": "Draft", "color": "gray"}, {"name": "Active", "color": "blue"},
            {"name": "Archived", "color": "default"},
        ]}},
    }, "🧠")

    tools_id = await _create_db(client, inbox_page_id, "Tools", {
        "Name": {"title": {}},
        "URL": {"url": {}},
        "Description": {"rich_text": {}},
        "Tags": {"multi_select": {}},
        "Pricing": {"select": {"options": [
            {"name": "Free", "color": "green"}, {"name": "Freemium", "color": "yellow"},
            {"name": "Paid", "color": "red"},
        ]}},
        "Status": {"select": {"options": [
            {"name": "Testing", "color": "yellow"}, {"name": "Using", "color": "green"},
            {"name": "Archived", "color": "gray"},
        ]}},
    }, "🛠️")

    data_tech_id = await _create_db(client, inbox_page_id, "Data & Technology", {
        "Name": {"title": {}},
        "URL": {"url": {}},
        "Description": {"rich_text": {}},
        "Tags": {"multi_select": {}},
        "Domain": {"select": {"options": [
            {"name": "AI"}, {"name": "Data"}, {"name": "Dev"}, {"name": "Science"}, {"name": "Other"},
        ]}},
        "Status": {"select": {"options": [
            {"name": "À relire", "color": "yellow"}, {"name": "Lu", "color": "green"},
            {"name": "Archivé", "color": "gray"},
        ]}},
    }, "📊")

    return InboxWorkspaceResult(
        inbox_page_id=inbox_page_id,
        notions_id=notions_id,
        ideas_id=ideas_id,
        tools_id=tools_id,
        data_tech_id=data_tech_id,
    )
