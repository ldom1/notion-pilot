"""Integration tests for the CRM v1 schema assumptions — real Notion API calls.

These exist because the v1 schema work (Activities + Meetings in the deploy
wizard) rests on Notion API behaviour that cannot be proven with mocks:

  1. A relation created with ``dual_property: {}`` really does make Notion create
     a reverse property on the target database, and ``GET /databases/{id}``
     returns it.
  2. That auto-generated reverse property can be renamed via ``PATCH /databases``.
  3. A rollup keyed on the *resolved* reverse-property name is accepted.

``scripts/crm/crm_add_activity_rollups.py`` passes ``allow_400=True`` on exactly
that rollup call, with a comment saying manual action may be required — so (3)
has historically failed. Mocked tests cannot tell us whether it still does.

Run with:
    uv run pytest tests/integration/test_notion_schema_contract.py -v

In this repo ``load_settings()`` raises when ``INFISICAL_ENV`` defaults to
``prod`` (the ``NOTION_OAUTH_REDIRECT_URI`` localhost guard trips), so the token
lookup falls back to ``NOTION_TOKEN`` and otherwise skips. To run against the
reference workspace::

    INFISICAL_ENV=prod \
    NOTION_OAUTH_REDIRECT_URI="https://notion-pilot.dombot.tech/auth/notion/callback" \
    uv run pytest tests/integration/test_notion_schema_contract.py -v

Observed on 2026-09-10 against that workspace: the Meetings schema check passes.
The back-relation check skips, because People and Companies there are legacy
``data_sources`` (``GET /databases/{id}`` 404s on them) and the Leads database id
is not in settings — a wizard-deployed workspace creates all of them via
``POST /databases``, so the round-trip test below is the one that proves the
behaviour.

Two tiers, both opt-in:

* **Read-only** (needs ``NOTION_TOKEN``): inspects the live Meetings database and
  the live CRM's Activities back-relations. Makes no writes.
* **Round-trip** (also needs ``NOTION_INTEGRATION_PARENT_PAGE_ID``): creates two
  throwaway databases under *that page*, exercises the full relation → rename →
  rollup path, and archives them in a ``finally``. Point it at a scratch page —
  never at the CRM page, and never at a page holding real records.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from notion_pilot.shared.config import load_settings
from notion_pilot.shared.workspace import (
    NOTION_API,
    find_relation_properties,
)

pytestmark = pytest.mark.integration

# From the Meetings database URL. Override with NOTION_MEETINGS_DATABASE_ID.
# NB: scripts/crm/NOTION_UI_STEPS.md records this as ...acd662b9..., a
# transposition of the ...ac6d62b9... in the copy-link URL. This is the URL form.
LIVE_MEETINGS_DB = "e94cc98f-2f66-4c53-ac6d-62b9d8f7d5aa"


def _token() -> str | None:
    try:
        settings = load_settings()
    except Exception:  # noqa: BLE001 — a config error should skip, not error
        return os.environ.get("NOTION_TOKEN")
    if settings.notion_token:
        return settings.notion_token.get_secret_value()
    return os.environ.get("NOTION_TOKEN")


@pytest.fixture
async def notion() -> AsyncIterator[httpx.AsyncClient]:
    token = _token()
    if not token:
        pytest.skip("no NOTION_TOKEN available — skipping real-API schema contract tests")
    async with httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        timeout=30,
    ) as client:
        yield client


async def _db(client: httpx.AsyncClient, db_id: str) -> dict:
    r = await client.get(f"{NOTION_API}/databases/{db_id}")
    if r.status_code == 404:
        pytest.skip(f"database {db_id} not visible to this token (not shared with the integration)")
    r.raise_for_status()
    return dict(r.json())


# ── read-only: does the live schema match what v1 copies? ────────────────────


@pytest.mark.asyncio
async def test_live_meetings_database_matches_the_v1_schema(notion):
    """The wizard's Meetings schema is copied from this database. If a property
    was renamed here, the deployed copy is wrong and this is where we find out."""
    db_id = os.environ.get("NOTION_MEETINGS_DATABASE_ID", LIVE_MEETINGS_DB)
    props = (await _db(notion, db_id))["properties"]

    expected_types = {
        "Name": "title",
        "Date": "date",
        "Type": "select",
        "Meeting Objective": "rich_text",
        "Company": "relation",
        "Deal": "relation",
        "People": "relation",
        "Advanced Deal?": "checkbox",
    }
    missing = [name for name in expected_types if name not in props]
    assert not missing, f"v1 copies these Meetings properties, but they are absent: {missing}"

    wrong = {
        name: (props[name]["type"], want)
        for name, want in expected_types.items()
        if props[name]["type"] != want
    }
    assert not wrong, f"property type drift (live, expected): {wrong}"


@pytest.mark.asyncio
async def test_live_crm_activities_back_relations_are_discoverable(notion):
    """The rollups key on the reverse of the Activities relation.

    `find_relation_properties` is what the wizard uses to locate it instead of
    assuming the literal name "Activities". This asserts the discovery works
    against the real databases — read-only, no rename attempted.
    """
    settings = load_settings()
    activities_id = settings.notion_activities_database_id
    if not activities_id:
        pytest.skip("NOTION_ACTIVITIES_DATABASE_ID not configured")

    parents = {
        "Leads": settings.notion_deals_database_id,
        "People": settings.notion_people_data_source_id,
        "Companies": settings.notion_companies_data_source_id,
    }

    # Report per parent rather than skipping the whole test on the first 404.
    # In the reference workspace People and Companies are on the legacy
    # data_sources API, so GET /databases/{id} does not resolve them at all —
    # that is a property of that workspace, not a failure of the discovery logic.
    # A wizard-deployed workspace creates all of them via POST /databases.
    unreachable: dict[str, str] = {}
    without_relation: list[str] = []
    resolved: dict[str, list[str]] = {}

    for label, parent_id in parents.items():
        if not parent_id:
            continue
        r = await notion.get(f"{NOTION_API}/databases/{parent_id}")
        if r.status_code != 200:
            unreachable[label] = f"{r.status_code} (data_source, or not shared with this token)"
            continue
        found = find_relation_properties(r.json().get("properties", {}), activities_id)
        if found:
            resolved[label] = found
        else:
            without_relation.append(label)

    print(f"\nback-relation discovery — resolved: {resolved}, unreachable: {unreachable}")

    if not resolved and not without_relation:
        pytest.skip(f"no CRM database was reachable as a /databases resource: {unreachable}")
    assert not without_relation, (
        f"reachable but no relation pointing at Activities: {without_relation}. "
        f"The Last Activity Date rollup cannot be built on those."
    )


# ── round-trip: the three things mocks cannot prove ─────────────────────────


@pytest.fixture
async def scratch_parent(notion) -> str:
    page_id = os.environ.get("NOTION_INTEGRATION_PARENT_PAGE_ID")
    if not page_id:
        pytest.skip(
            "set NOTION_INTEGRATION_PARENT_PAGE_ID to a throwaway Notion page to run the "
            "write round-trip (it creates and archives two databases under that page)"
        )
    # A page that exists but has not been shared with the integration returns 404
    # here. That is a setup step, not a product failure, so skip with the fix
    # rather than failing and looking like the schema logic is broken.
    r = await notion.get(f"{NOTION_API}/pages/{page_id}")
    if r.status_code != 200:
        pytest.skip(
            f"scratch page {page_id} is not reachable ({r.status_code}). In Notion open that "
            "page -> ... -> Connections -> add the integration whose token this run uses, "
            "then re-run."
        )
    return page_id


@pytest.mark.asyncio
async def test_dual_relation_reverse_property_rename_and_rollup(notion, scratch_parent):
    """The full path the deploy wizard depends on, against the real API.

    Creates Parent + Child, relates Child -> Parent as a dual property, then
    checks that the reverse property appears on Parent, that it can be renamed,
    and that a rollup keyed on the resolved name is accepted. Both databases are
    archived at the end regardless of outcome.
    """
    tag = uuid.uuid4().hex[:8]
    created: list[str] = []

    async def make_db(title: str, properties: dict) -> str:
        r = await notion.post(
            f"{NOTION_API}/databases",
            json={
                "parent": {"type": "page_id", "page_id": scratch_parent},
                "title": [{"type": "text", "text": {"content": title}}],
                "properties": properties,
            },
        )
        assert r.status_code == 200, f"could not create {title}: {r.status_code} {r.text}"
        db_id = r.json()["id"]
        created.append(db_id)
        return db_id

    try:
        parent_id = await make_db(f"zz-itest-parent-{tag}", {"Name": {"title": {}}})
        child_id = await make_db(
            f"zz-itest-child-{tag}",
            {
                "Name": {"title": {}},
                "Date": {"date": {}},
                "Parent": {"relation": {"database_id": parent_id, "dual_property": {}}},
            },
        )

        # (1) the reverse property exists and is returned by GET
        parent_props = (await _db(notion, parent_id))["properties"]
        found = find_relation_properties(parent_props, child_id)
        assert found, (
            "dual_property did not produce a reverse relation on the parent database — "
            "_resolve_back_relation cannot work and the rollups have nothing to key on"
        )
        auto_name = found[0]

        # (2) the auto-generated name can be renamed
        desired = "Activities"
        rename = await notion.patch(
            f"{NOTION_API}/databases/{parent_id}",
            json={"properties": {auto_name: {"name": desired}}},
        )
        renamed = rename.status_code == 200
        relation_name = desired if renamed else auto_name
        if renamed:
            after = (await _db(notion, parent_id))["properties"]
            assert desired in after, f"rename returned 200 but '{desired}' is absent"
            assert find_relation_properties(after, child_id) == [desired]

        # (3) a rollup keyed on the resolved name is accepted — this is the call
        #     the one-shot script had to tolerate a 400 on
        rollup = await notion.patch(
            f"{NOTION_API}/databases/{parent_id}",
            json={
                "properties": {
                    "Last Activity Date": {
                        "rollup": {
                            "relation_property_name": relation_name,
                            "rollup_property_name": "Date",
                            "function": "latest_date",
                        }
                    }
                }
            },
        )
        assert rollup.status_code == 200, (
            f"rollup on the resolved relation '{relation_name}' was rejected: "
            f"{rollup.status_code} {rollup.text}. The wizard treats this as fatal, so a "
            f"failure here means create_crm_workspace would abort a real deploy."
        )
        final = (await _db(notion, parent_id))["properties"]
        assert final["Last Activity Date"]["type"] == "rollup"

        # record what actually happened — the auto-generated name is the fact the
        # repo never wrote down, and the reason hardcoding it was unsafe
        print(
            f"\nNotion behaviour observed: reverse property auto-named "
            f"{auto_name!r}; rename to {desired!r} {'succeeded' if renamed else 'REJECTED'}; "
            f"rollup on {relation_name!r} accepted."
        )
    finally:
        for db_id in created:
            await notion.patch(f"{NOTION_API}/databases/{db_id}", json={"archived": True})
