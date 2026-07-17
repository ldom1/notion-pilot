#!/usr/bin/env python
"""Export current Notion Companies (+ Deals) to a flat CSV for the
crystal-hpc-lead-generation-sop's exclusion-list step. Writes to the same
workspace folder that SOP already reads its own CSVs from — no cross-repo
filesystem access needed.

Usage:
    uv run python scripts/crm/dump_leads.py
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import date
from pathlib import Path

import httpx
from notion_client import AsyncClient

from notion_pilot.crm.deals import NotionDealsSyncer
from notion_pilot.crm.syncer import NotionCompanySyncer
from notion_pilot.shared.config import load_settings

_DEFAULT_OUT_DIR = Path("/home/lgiron/artelys_crystal_hpc/lead-generation")


def build_export_rows(
    company_syncer: NotionCompanySyncer, deals_syncer: NotionDealsSyncer | None
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for page_id, name in company_syncer._id_to_name.items():
        siren = company_syncer.details.get(page_id, {}).get("siren", "")
        rows.append({"type": "company", "name": name, "siren": siren})
    if deals_syncer is not None:
        for title in deals_syncer._snapshot:
            rows.append({"type": "deal", "name": title, "siren": ""})
    return rows


def write_csv(rows: list[dict[str, str]], out_path: Path) -> None:
    # `;`-delimited, UTF-8 BOM — matches the crystal-hpc SOP's own CSV format
    # (confirmed in the spec's Phase 0 audit), since this file lands in the
    # same folder the SOP already reads its own CSVs from.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "name", "siren"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


async def main(out_dir: Path = _DEFAULT_OUT_DIR) -> Path:
    settings = load_settings()
    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id or "")
    await company_syncer.load_notion_snapshot()

    deals_syncer = None
    if settings.notion_deals_database_id:
        async with httpx.AsyncClient() as http:
            deals_syncer = NotionDealsSyncer(
                http, settings.notion_token.get_secret_value(), settings.notion_deals_database_id
            )
            await deals_syncer.load_notion_snapshot()

    # Calls build_export_rows directly rather than duplicating its SIREN-lookup
    # logic inline — the first version of this task hardcoded "siren": "" in
    # both places, which meant fixing one wouldn't have fixed the other.
    rows = build_export_rows(company_syncer, deals_syncer)

    out_path = out_dir / f"notion-export-{date.today().isoformat()}.csv"
    write_csv(rows, out_path)
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    args = parser.parse_args()
    result_path = asyncio.run(main(args.out_dir))
    print(f"Wrote export to {result_path}")
