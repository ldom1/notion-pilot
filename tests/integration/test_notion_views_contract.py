"""Live contract for the Views calls the CRM home makes. Opt-in.

Needs NOTION_TOKEN and NOTION_INTEGRATION_PARENT_PAGE_ID (a scratch page shared
with the integration — never the CRM page). Creates a throwaway page with two
small databases and archives it in `finally`.

    uv run pytest tests/integration/test_notion_views_contract.py -v -s

Record what it proves in the spec's §7 table.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from notion_pilot.shared.notion_views import VIEW_SPECS, create_home_views
from notion_pilot.shared.workspace import (
    NOTION_API,
    NOTION_VERSION,
    THIS_WEEK,
    _append_blocks,
    _create_db,
    _create_page,
    _list_children,
    _plain_text,
    crm_home_blocks,
    find_block,
)

pytestmark = pytest.mark.integration


def _bare(block_id: str) -> str:
    return block_id.replace("-", "")


async def test_crm_home_views_contract():
    token = os.getenv("NOTION_TOKEN")
    parent = os.getenv("NOTION_INTEGRATION_PARENT_PAGE_ID")
    if not (token and parent):
        pytest.skip("needs NOTION_TOKEN and NOTION_INTEGRATION_PARENT_PAGE_ID (a scratch page)")
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(headers=headers, timeout=60) as client:
        page_id = await _create_page(client, parent, f"views-contract-{uuid.uuid4().hex[:6]}", "🧪")
        try:
            # Append returns only the new blocks, in order, with nesting ≤ 2.
            home = await _append_blocks(client, page_id, crm_home_blocks())
            assert [_plain_text(b) for b in home] == [_plain_text(b) for b in crm_home_blocks()]

            leads_id = await _create_db(
                client,
                page_id,
                "Leads",
                {
                    "Name": {"title": {}},
                    "Stage": {
                        "select": {
                            "options": [
                                {"name": s}
                                for s in ("Prospect", "Closed Won", "Closed Lost", "No Answer")
                            ]
                        }
                    },
                    "Next Step": {"rich_text": {}},
                    "Expected Close Date": {"date": {}},
                    "Stale Deal": {"formula": {"expression": 'empty(prop("Next Step"))'}},
                    "Days Since Last Activity": {"formula": {"expression": "0"}},
                },
                "💼",
            )
            activities_id = await _create_db(
                client, page_id, "Activities", {"Name": {"title": {}}, "Date": {"date": {}}}, "⚡"
            )

            this_week = find_block(home, "heading_2", THIS_WEEK)
            outcome = await create_home_views(
                client,
                page_id=page_id,
                after_block_id=this_week,
                databases={"Leads": leads_id, "Activities": activities_id},
            )
            # Board on a select Stage, formula checkbox, next_month, past_month all accepted.
            assert outcome.warnings == [], outcome.warnings

            children = await _list_children(client, page_id)
            order = [_bare(b["id"]) for b in children]
            at = order.index(_bare(this_week))
            placed = [_bare(outcome.views[s.key]["block_id"]) for s in VIEW_SPECS]
            # parent.database_id is the linked block, and reverse insertion gives page order.
            assert order[at + 1 : at + 5] == placed

            linked = [b for b in children if _bare(b["id"]) in placed]
            print(
                "linked view blocks as listed on 2022-06-28:",
                [(b["type"], b.get(b["type"])) for b in linked],
            )

            r = await client.delete(f"{NOTION_API}/blocks/{outcome.views['pipeline']['block_id']}")
            # An upgrade can remove a linked view with the legacy client.
            assert r.status_code == 200
        finally:
            await client.patch(f"{NOTION_API}/pages/{page_id}", json={"archived": True})
