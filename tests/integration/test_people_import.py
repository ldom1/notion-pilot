"""Integration test — dry-run import against real Notion (reads only, no writes)."""
from pathlib import Path

import pytest

from scripts.crm_import_linkedin import _parse_connections, run

pytestmark = pytest.mark.integration

CSV_PATH = Path("data/Basic_LinkedInDataExport_05-20-2026.zip/Connections.csv")


def test_parse_connections_returns_records():
    records = _parse_connections(CSV_PATH)
    assert len(records) > 1700
    assert all(r.name for r in records)
    assert all(r.linkedin_url.startswith("https://") for r in records if r.linkedin_url)


async def test_dry_run_completes_without_error():
    from telegram_to_notion.config import load_settings
    settings = load_settings()
    if not settings.notion_people_data_source_id:
        pytest.skip("NOTION_PEOPLE_DATA_SOURCE_ID not set")
    await run(dry_run=True, enrich=False, csv_path=CSV_PATH)
