#!/usr/bin/env python
"""Batch enrichment CLI — enrich People and/or Companies records in Notion.

Usage:
    uv run python scripts/enrich_crm.py --people --limit 20 --dry-run
    uv run python scripts/enrich_crm.py --companies --limit 10
    uv run python scripts/enrich_crm.py --people --companies
"""
import argparse
import asyncio

from loguru import logger
from notion_client import AsyncClient

from telegram_to_notion.config import load_settings
from telegram_to_notion.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer, PersonRecord
from telegram_to_notion.utils.enrichment import enrich_company, enrich_person


async def enrich_people(limit: int, dry_run: bool) -> None:
    settings = load_settings()
    if not settings.notion_people_data_source_id:
        logger.error("NOTION_PEOPLE_DATA_SOURCE_ID not set")
        return

    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id or "")
    people_syncer = NotionPeopleSyncer(client, settings.notion_people_data_source_id, company_syncer)
    await company_syncer.load_snapshot()
    await people_syncer.load_snapshot()

    enriched = 0
    for candidate in people_syncer._existing[:limit]:
        name = candidate["name"]
        company = candidate.get("company", "")
        position = candidate.get("position", "")
        if candidate.get("seniority") and candidate.get("role_type"):
            logger.info("Skipping {} @ {} — already enriched", name, company)
            continue

        logger.info("Enriching {} @ {}...", name, company)
        enrichment = await enrich_person(name, company, settings, position=position)

        if dry_run:
            logger.info(
                "  [DRY-RUN] email={} phone={} seniority={} role_type={}",
                enrichment.email, enrichment.phone, enrichment.seniority, enrichment.role_type,
            )
        else:
            logger.info(
                "  Enriched: email={} seniority={} source={}",
                enrichment.email, enrichment.seniority, enrichment.source,
            )
        enriched += 1

    logger.info("Done. Enriched {} / {} people{}", enriched, limit, " (dry-run)" if dry_run else "")


async def enrich_companies(limit: int, dry_run: bool) -> None:
    settings = load_settings()
    if not settings.notion_companies_data_source_id:
        logger.error("NOTION_COMPANIES_DATA_SOURCE_ID not set")
        return

    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id)
    await company_syncer.load_snapshot()

    enriched = 0
    for page_id, name in list(company_syncer._id_to_name.items())[:limit]:
        logger.info("Enriching company {}...", name)
        enrichment = await enrich_company(name, settings)
        if dry_run:
            logger.info(
                "  [DRY-RUN] linkedin={} size={} country={} source={}",
                enrichment.linkedin_url, enrichment.size, enrichment.country, enrichment.source,
            )
        else:
            logger.info(
                "  Enriched: linkedin={} size={} source={}",
                enrichment.linkedin_url, enrichment.size, enrichment.source,
            )
        enriched += 1

    logger.info("Done. Enriched {} / {} companies{}", enriched, limit, " (dry-run)" if dry_run else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch CRM enrichment")
    parser.add_argument("--people", action="store_true", help="Enrich People records")
    parser.add_argument("--companies", action="store_true", help="Enrich Company records")
    parser.add_argument("--limit", type=int, default=50, help="Max records to process")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing")
    args = parser.parse_args()

    if not args.people and not args.companies:
        parser.error("Specify at least one of --people or --companies")

    if args.people:
        asyncio.run(enrich_people(args.limit, args.dry_run))
    if args.companies:
        asyncio.run(enrich_companies(args.limit, args.dry_run))


if __name__ == "__main__":
    main()
