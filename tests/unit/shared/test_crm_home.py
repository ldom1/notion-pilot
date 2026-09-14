# tests/unit/shared/test_crm_home.py
import json
import re

from notion_pilot.shared.doc_links import DOC_GROUPS
from notion_pilot.shared.notion_views import VIEW_SPECS
from notion_pilot.shared.workspace import (
    LEGACY_TEMPLATE_TEXTS,
    SOURCES_TITLE,
    THIS_WEEK,
    _plain_text,
    crm_home_blocks,
    find_block,
    manual_views_callout,
    owned_template_texts,
)

_TELEGRAM_COMMAND = re.compile(r'(?:^|[\s"])/(?:lead|people|deal|notion)\b')


def test_home_has_no_telegram_era_strings():
    text = json.dumps(crm_home_blocks(), ensure_ascii=False)
    assert "Telegram" not in text
    assert "message the bot" not in text
    assert not _TELEGRAM_COMMAND.search(text)


def test_home_reads_pipeline_first_and_databases_last():
    blocks = crm_home_blocks()
    headings = [_plain_text(b) for b in blocks if b["type"] == "heading_2"]
    assert headings == [THIS_WEEK, "Update it without the fifteen clicks", "Databases"]
    assert blocks[0]["type"] == "callout"
    assert _plain_text(blocks[0]).startswith("Your CRM is ready. Your pipeline is below.")
    assert _plain_text(blocks[-1]) == "Databases"


def test_prompt_uses_seeded_names_and_promises_a_preview():
    text = json.dumps(crm_home_blocks(), ensure_ascii=False)
    assert "Here is an email from Alice Martin at TechCorp." in text
    assert "Nothing is written until you reply go." in text
    assert "These run in your assistant, not in Notion." in text
    assert "/plugin marketplace add ldom1/notion-pilot-powers" in text
    assert "/plugin install notion-pilot-powers@notion-pilot-powers" in text
    assert "notion-crm@notion-pilot" not in text


def test_legacy_keeps_old_plugin_install_for_refresh():
    assert any("notion-crm@notion-pilot" in t for t in LEGACY_TEMPLATE_TEXTS)
    assert any("marketplace add ldom1/notion-pilot\n" in t for t in LEGACY_TEMPLATE_TEXTS)

def test_sources_toggle_links_every_doc_link():
    blocks = crm_home_blocks()
    sources = next(b for b in blocks if b["type"] == "toggle" and _plain_text(b) == SOURCES_TITLE)
    links = {
        item["text"]["link"]["url"]
        for child in sources["toggle"]["children"]
        for item in child[child["type"]]["rich_text"]
        if item["text"].get("link")
    }
    assert links == {link.url for group in DOC_GROUPS for link in group.links}


def test_nesting_stays_within_two_levels():
    for block in crm_home_blocks() + [manual_views_callout(VIEW_SPECS)]:
        for child in block[block["type"]].get("children", []):
            assert "children" not in child[child["type"]]


def test_kpi_bullets_only_list_existing_properties():
    blocks = crm_home_blocks({"Stale Deal"})
    kpis = next(b for b in blocks if _plain_text(b) == "📐 How the numbers work")
    texts = [_plain_text(c) for c in kpis["toggle"]["children"]]
    assert len(texts) == 1 and texts[0].startswith("Stale Deal")


def test_manual_callout_lists_steps_for_each_skipped_view():
    callout = manual_views_callout(VIEW_SPECS[:1])
    texts = [_plain_text(c) for c in callout["callout"]["children"]]
    assert texts == ["📊 Pipeline", *VIEW_SPECS[0].manual_steps]


def test_owned_texts_cover_current_and_telegram_era_template():
    owned = owned_template_texts()
    assert {_plain_text(b) for b in crm_home_blocks()} <= owned
    assert "Some views need a minute in Notion" in owned
    assert "Add a company: /lead TechCorp" in LEGACY_TEMPLATE_TEXTS <= owned


def test_find_block_returns_the_id_of_a_heading():
    blocks = [{**b, "id": f"b{i}"} for i, b in enumerate(crm_home_blocks())]
    assert find_block(blocks, "heading_2", THIS_WEEK) == "b1"
