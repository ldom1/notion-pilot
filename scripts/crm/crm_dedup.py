#!/usr/bin/env python
"""Find potential duplicates in People or Companies Notion databases.

Compares all records pairwise using fuzzy name matching and reports pairs
above the review threshold. Use the Notion URLs to inspect and merge manually.

Usage:
    uv run python scripts/crm_dedup.py --companies
    uv run python scripts/crm_dedup.py --people
    uv run python scripts/crm_dedup.py --people --companies --threshold 80
"""

import argparse
import asyncio

from loguru import logger
from notion_client import AsyncClient

from notion_pilot.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer
from notion_pilot.shared.config import load_settings
from notion_pilot.shared.utils.dedup import (
    DuplicatePair,
    find_company_duplicates,
    find_people_duplicates,
    notion_page_url,
)

_DEFAULT_THRESHOLD = 85


def _print_pairs(pairs: list[DuplicatePair], label: str) -> None:
    if not pairs:
        logger.info("No duplicates found in {}", label)
        return
    logger.info("{} potential duplicates found in {}:", len(pairs), label)
    for p in pairs:
        ctx_a = f" ({p.context_a})" if p.context_a else ""
        ctx_b = f" ({p.context_b})" if p.context_b else ""
        print(
            f"  [{p.score:.0f}]  {p.name_a}{ctx_a}\n"
            f"         {notion_page_url(p.id_a)}\n"
            f"       vs {p.name_b}{ctx_b}\n"
            f"         {notion_page_url(p.id_b)}"
        )


async def dedup_companies(threshold: float) -> None:
    settings = load_settings()
    if not settings.notion_companies_data_source_id:
        logger.error("NOTION_COMPANIES_DATA_SOURCE_ID not set")
        return
    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id)
    await syncer.load_snapshot()
    logger.info(
        "Scanning {} companies for duplicates (threshold={})...", len(syncer._id_to_name), threshold
    )
    pairs = find_company_duplicates(syncer._id_to_name, threshold)
    _print_pairs(pairs, "Companies")


async def dedup_people(threshold: float) -> None:
    settings = load_settings()
    if not settings.notion_people_data_source_id:
        logger.error("NOTION_PEOPLE_DATA_SOURCE_ID not set")
        return
    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id or "")
    people_syncer = NotionPeopleSyncer(
        client, settings.notion_people_data_source_id, company_syncer
    )
    await company_syncer.load_snapshot()
    await people_syncer.load_snapshot()
    existing = [dict(r) for r in people_syncer._existing]
    logger.info("Scanning {} people for duplicates (threshold={})...", len(existing), threshold)
    pairs = find_people_duplicates(existing, threshold)
    _print_pairs(pairs, "People")


def main() -> None:
    parser = argparse.ArgumentParser(description="Find CRM duplicates")
    parser.add_argument("--people", action="store_true")
    parser.add_argument("--companies", action="store_true")
    parser.add_argument(
        "--threshold",
        type=float,
        default=_DEFAULT_THRESHOLD,
        help="Minimum similarity score 0-100 (default: %(default)s)",
    )
    args = parser.parse_args()
    if not args.people and not args.companies:
        parser.error("Specify at least one of --people or --companies")
    if args.companies:
        asyncio.run(dedup_companies(args.threshold))
    if args.people:
        asyncio.run(dedup_people(args.threshold))


if __name__ == "__main__":
    main()
