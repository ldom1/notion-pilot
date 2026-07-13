"""Unit tests for scripts/crm/dump_leads.py."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scripts.crm.dump_leads import build_export_rows, write_csv


@pytest.mark.asyncio
async def test_build_export_rows_combines_companies_and_deals():
    company_syncer = AsyncMock()
    company_syncer._id_to_name = {"pid1": "Artelys", "pid2": "OVHcloud"}
    company_syncer.details = {"pid1": {"siren": "428895676"}}  # pid2 has no SIREN yet

    deals_syncer = AsyncMock()
    deals_syncer._snapshot = {"Lead: Jean @ Artelys": "did1"}

    rows = build_export_rows(company_syncer, deals_syncer)

    assert {"type": "company", "name": "Artelys", "siren": "428895676"} in rows
    assert {"type": "company", "name": "OVHcloud", "siren": ""} in rows
    assert {"type": "deal", "name": "Lead: Jean @ Artelys", "siren": ""} in rows


def test_build_export_rows_skips_deals_loop_when_deals_syncer_is_none():
    company_syncer = AsyncMock()
    company_syncer._id_to_name = {"pid1": "Artelys"}
    company_syncer.details = {"pid1": {"siren": "428895676"}}

    rows = build_export_rows(company_syncer, None)

    assert rows == [{"type": "company", "name": "Artelys", "siren": "428895676"}]


def test_write_csv_creates_file_with_semicolon_delimiter_and_bom(tmp_path: Path):
    rows = [{"type": "company", "name": "Artelys", "siren": "428895676"}]
    out_path = tmp_path / "export.csv"

    write_csv(rows, out_path)

    raw = out_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM, matching the SOP's own CSVs

    with out_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        result = list(reader)

    assert result[0]["name"] == "Artelys"
    assert result[0]["siren"] == "428895676"
