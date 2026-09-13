# tests/unit/shared/test_crm_upgrade.py
import json

import httpx

from notion_pilot.shared.notion_views import VIEW_SPECS
from notion_pilot.shared.workspace import _plain_text, upgrade_crm_home

_VIEW_NAMES = {s.name for s in VIEW_SPECS}
_ALL_LEADS_PROPS = {
    "Stage",
    "Stale Deal",
    "Days Since Last Activity",
    "Expected Close Date",
    "Deal Temperature",
    "Weighted Value (€)",
}


def _resp(body: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status, json=body, request=httpx.Request("GET", "https://api.notion.com/v1")
    )


def _block(block_id: str, block_type: str, text: str) -> dict:
    return {"id": block_id, "type": block_type, block_type: {"rich_text": [{"plain_text": text}]}}


def _database(block_id: str, title: str) -> dict:
    return {"id": block_id, "type": "child_database", "child_database": {"title": title}}


class FakePage:
    """In-memory CRM page: top-level blocks, legacy database GET, and Views calls."""

    def __init__(self, children: list[dict], leads_props: set[str] = _ALL_LEADS_PROPS):
        self.children = children
        self.leads_props = leads_props
        self._n = 0

    def _new_id(self) -> str:
        self._n += 1
        return f"new-{self._n}"

    def _index(self, block_id: str) -> int:
        return next(i for i, b in enumerate(self.children) if b["id"] == block_id)

    async def get(self, url, params=None):
        if url.endswith("/children"):
            return _resp({"results": list(self.children), "has_more": False})
        return _resp({"properties": {name: {} for name in self.leads_props}})

    async def patch(self, url, json):
        new = [{**b, "id": self._new_id()} for b in json["children"]]
        at = self._index(json["after"]) + 1 if "after" in json else len(self.children)
        self.children[at:at] = new
        return _resp({"results": new})

    async def delete(self, url):
        block_id = url.rsplit("/", 1)[-1]
        if not any(b["id"] == block_id for b in self.children):
            return _resp({}, 404)
        self.children = [b for b in self.children if b["id"] != block_id]
        return _resp({})

    async def request(self, method, url, json=None, headers=None):
        path = url.split("/v1", 1)[1]
        if path.startswith("/databases/"):
            return _resp({"data_sources": [{"id": "ds"}]})
        if path.startswith("/data_sources/"):
            names = self.leads_props | {"Date"}
            return _resp(
                {
                    "properties": {
                        n: {"id": n, "type": "select" if n == "Stage" else "date"} for n in names
                    }
                }
            )
        linked = {**_database(self._new_id(), json["name"])}
        self.children.insert(
            self._index(json["create_database"]["position"]["block_id"]) + 1, linked
        )
        return _resp(
            {
                "id": f"view-{linked['id']}",
                "parent": {"type": "database_id", "database_id": linked["id"]},
            }
        )

    def texts(self) -> list[str]:
        return [
            b["child_database"]["title"] if b["type"] == "child_database" else _plain_text(b)
            for b in self.children
        ]


def _telegram_era_page(*, with_activities: bool = True) -> FakePage:
    children = [
        _block("v0-callout", "callout", "Start with a Company → add People → track Deals."),
        _block("v0-h2", "heading_2", "Getting started"),
        _block("v0-1", "numbered_list_item", "Add a company: /lead TechCorp"),
        _block("v0-2", "numbered_list_item", "Add contacts: /people Alice Martin, CTO @ TechCorp"),
        _block(
            "v0-3", "numbered_list_item", "Track a deal: /deal ERP Integration — TechCorp, €45k"
        ),
        _block("user-note", "paragraph", "Q4 targets: 3 new logos"),
        _database("companies", "Companies"),
        _database("people", "People"),
        _database("leads", "Deals"),
        _database("meetings", "Meetings"),
    ]
    if with_activities:
        children.append(_database("activities", "Activities"))
    return FakePage(children)


async def test_upgrade_replaces_the_telegram_template_and_keeps_everything_else():
    page = _telegram_era_page()
    result = await upgrade_crm_home(page, "crm")
    ids = [b["id"] for b in page.children]
    assert not any(i.startswith("v0-") for i in ids)
    assert {"user-note", "companies", "people", "leads", "meetings", "activities"} <= set(ids)
    assert "Telegram" not in json.dumps(page.children) and "/lead" not in json.dumps(page.children)
    assert set(result.views) == {s.key for s in VIEW_SPECS}
    assert result.warnings == []


async def test_upgrade_puts_the_pipeline_first():
    page = _telegram_era_page()
    await upgrade_crm_home(page, "crm")
    texts = page.texts()
    assert texts[0].startswith("Your CRM is ready.")
    assert texts[1:6] == ["This week", *[s.name for s in VIEW_SPECS]]


async def test_upgrade_without_activities_skips_recent_activity_and_explains():
    page = _telegram_era_page(with_activities=False)
    result = await upgrade_crm_home(page, "crm")
    assert "recent_activity" not in result.views
    assert (
        "The Activities database was not found on this page; its views were skipped."
        in result.warnings
    )
    assert "Some views need a minute in Notion" in page.texts()


async def test_upgrading_twice_leaves_one_set_of_views():
    page = _telegram_era_page()
    first = await upgrade_crm_home(page, "crm")
    await upgrade_crm_home(page, "crm", previous_views=first.views)
    assert sum(1 for t in page.texts() if t in _VIEW_NAMES) == 4
    assert page.texts().count("This week") == 1


async def test_upgrade_lists_only_the_kpis_leads_really_has():
    page = _telegram_era_page()
    page.leads_props = {"Stage", "Stale Deal", "Days Since Last Activity", "Expected Close Date"}
    await upgrade_crm_home(page, "crm")
    kpis = next(b for b in page.children if _plain_text(b) == "📐 How the numbers work")
    bullets = [_plain_text(c) for c in kpis["toggle"]["children"]]
    assert [b.split(" — ")[0] for b in bullets] == ["Days Since Last Activity", "Stale Deal"]


async def test_upgrade_without_a_template_at_the_top_appends_and_warns():
    page = FakePage([_block("user-note", "paragraph", "Mine"), _database("leads", "Leads")])
    result = await upgrade_crm_home(page, "crm")
    assert page.children[0]["id"] == "user-note"
    assert (
        "The template was added at the bottom of the page. Drag it above the databases."
        in result.warnings
    )
