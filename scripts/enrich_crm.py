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
from telegram_to_notion.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer
from telegram_to_notion.utils.enrichment import enrich_company, enrich_person

_RATE_LIMIT_S = 0.4  # seconds between Notion writes to stay under rate limit


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

    enriched = skipped = wrote = 0
    candidates = [
        c for c in people_syncer._existing
        if not (c.get("seniority") and c.get("role_type") and c.get("email"))
    ]
    logger.info("{} people need enrichment (out of {})", len(candidates), len(people_syncer._existing))

    for candidate in candidates[:limit]:
        name = candidate["name"]
        company = candidate.get("company", "")
        position = candidate.get("position", "")

        logger.info("Enriching {} @ {}...", name, company)
        enrichment = await enrich_person(name, company, settings, position=position)

        props: dict[str, object] = {}
        if enrichment.email and not candidate.get("email"):
            props["E-mail pro"] = {"email": enrichment.email}
        if enrichment.phone and not candidate.get("phone"):
            props["Phone"] = {"phone_number": enrichment.phone}
        if enrichment.seniority and not candidate.get("seniority"):
            props["Seniority"] = {"select": {"name": enrichment.seniority}}
        if enrichment.role_type and not candidate.get("role_type"):
            props["Role Type"] = {"multi_select": [{"name": rt} for rt in enrichment.role_type]}
        if enrichment.linkedin_url and not candidate.get("linkedin_url"):
            props["Linkedin"] = {"url": enrichment.linkedin_url}

        if not props:
            logger.info("  No data found (source={})", enrichment.source or "none")
            skipped += 1
            continue

        logger.info(
            "  Found: email={} seniority={} role_type={} source={}",
            enrichment.email or "-", enrichment.seniority or "-",
            enrichment.role_type or [], enrichment.source,
        )

        if dry_run:
            logger.info("  [DRY-RUN] would write {} props to {}", len(props), candidate["page_id"])
        else:
            await client.pages.update(candidate["page_id"], properties=props)
            await asyncio.sleep(_RATE_LIMIT_S)
            wrote += 1

        enriched += 1

    logger.info(
        "Done{}. processed={} wrote={} skipped(no-data)={}",
        " (dry-run)" if dry_run else "", enriched, wrote, skipped,
    )


async def enrich_companies(limit: int, dry_run: bool) -> None:
    settings = load_settings()
    if not settings.notion_companies_data_source_id:
        logger.error("NOTION_COMPANIES_DATA_SOURCE_ID not set")
        return

    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id)
    await company_syncer.load_snapshot()

    enriched = skipped = wrote = 0
    items = list(company_syncer._id_to_name.items())
    logger.info("{} companies to process", len(items))

    for page_id, name in items[:limit]:
        logger.info("Enriching company {}...", name)
        enrichment = await enrich_company(name, settings)

        props: dict[str, object] = {}
        if enrichment.linkedin_url:
            props["Linkedin"] = {"url": enrichment.linkedin_url}
        if enrichment.website:
            props["Website"] = {"url": enrichment.website}
        if enrichment.size:
            props["Size"] = {"select": {"name": enrichment.size}}
        if enrichment.country:
            props["Country"] = {"select": {"name": enrichment.country}}
        if enrichment.tech_stack:
            props["Tech Stack"] = {"multi_select": [{"name": t} for t in enrichment.tech_stack]}

        if not props:
            logger.info("  No data found (source={})", enrichment.source or "none")
            skipped += 1
            continue

        logger.info(
            "  Found: linkedin={} size={} country={} source={}",
            enrichment.linkedin_url or "-", enrichment.size or "-",
            enrichment.country or "-", enrichment.source,
        )

        if dry_run:
            logger.info("  [DRY-RUN] would write {} props to {}", len(props), page_id)
        else:
            await client.pages.update(page_id, properties=props)
            await asyncio.sleep(_RATE_LIMIT_S)
            wrote += 1

        enriched += 1

    logger.info(
        "Done{}. processed={} wrote={} skipped(no-data)={}",
        " (dry-run)" if dry_run else "", enriched, wrote, skipped,
    )


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
