#!/usr/bin/env python
"""Prospection CLI — rank contacts for a B2B pitch.

Usage:
    uv run python scripts/crm_prospect.py --pitch "I want to sell HPC-as-a-service to energy companies"
    uv run python scripts/crm_prospect.py --pitch "Sell optimization software" --limit 5
"""

import argparse
import asyncio

from loguru import logger
from notion_client import AsyncClient

from notion_pilot.shared.config import load_settings
from notion_pilot.crm.prospection import rank_contacts
from notion_pilot.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer


async def run(pitch: str, top_k: int) -> None:
    settings = load_settings()

    if not settings.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY not set — cannot rank contacts")
        return
    if not settings.notion_people_data_source_id:
        logger.error("NOTION_PEOPLE_DATA_SOURCE_ID not set — cannot load contacts")
        return

    logger.info("Loading People snapshot from Notion...")
    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id or "")
    people_syncer = NotionPeopleSyncer(
        client, settings.notion_people_data_source_id, company_syncer
    )
    await company_syncer.load_snapshot()
    await people_syncer.load_snapshot()

    candidates = people_syncer._existing
    logger.info("Ranking {} contacts for pitch: {}", len(candidates), pitch)
    ranked = await rank_contacts(pitch, candidates, settings, top_k=top_k)

    if not ranked:
        print("No ranked contacts returned.")
        return

    print(f"\n{'=' * 60}")
    print(f"Top {len(ranked)} contacts for: {pitch}")
    print(f"{'=' * 60}")
    for i, contact in enumerate(ranked, 1):
        linkedin = f"\n   LinkedIn: {contact.linkedin_url}" if contact.linkedin_url else ""
        print(
            f"\n{i}. {contact.name} — {contact.position or '?'} @ {contact.company}"
            f"\n   Score: {contact.score:.2f}"
            f"\n   Reason: {contact.reasoning}"
            f"{linkedin}"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank CRM contacts for a B2B pitch")
    parser.add_argument("--pitch", required=True, help="Sales pitch description")
    parser.add_argument("--limit", type=int, default=10, help="Number of contacts to return")
    args = parser.parse_args()
    asyncio.run(run(args.pitch, args.limit))


if __name__ == "__main__":
    main()
