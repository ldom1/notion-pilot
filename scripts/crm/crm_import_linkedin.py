"""Batch import LinkedIn connections into the Notion People database.

Usage:
    uv run python scripts/crm_import_linkedin.py [--dry-run] [--no-enrich] [--csv PATH]

Flags:
    --dry-run     Parse and dedup, print counts, no Notion writes.
    --no-enrich   Skip Brave Search email lookup.
    --csv PATH    Path to Connections.csv (default: auto-detected from data/ dir).
"""

import asyncio
import sys
from pathlib import Path

import pandas as pd
from loguru import logger
from notion_client import AsyncClient

from notion_pilot.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer, PersonRecord
from notion_pilot.shared.config import load_settings
from notion_pilot.shared.utils.dedup import DedupStatus, find_match
from notion_pilot.shared.utils.enrichment import enrich_person

_DEFAULT_CSV = Path("data/crm/Basic_LinkedInDataExport_05-20-2026.zip/Connections.csv")
_REVIEW_CSV = Path("data/crm/import-review.csv")
_SKIPED_CSV = Path("data/crm/import-skiped.csv")

_REVIEW_FIELDS = ["score", "input_name", "input_company", "matched_name", "matched_company", "linkedin_url"]


def _parse_connections(csv_path: Path) -> list[PersonRecord]:
    text = csv_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header_idx = next(i for i, line in enumerate(lines) if line.startswith("First Name"))
    df = pd.read_csv(
        pd.io.common.StringIO("\n".join(lines[header_idx:])),
        dtype=str,
    ).fillna("")
    records = []
    for _, row in df.iterrows():
        name = f"{row['First Name'].strip()} {row['Last Name'].strip()}".strip()
        if not name:
            continue
        records.append(
            PersonRecord(
                name=name,
                company=row.get("Company", "").strip(),
                position=row.get("Position", "").strip(),
                linkedin_url=row.get("URL", "").strip(),
                email=row.get("Email Address", "").strip(),
            )
        )
    return records


_STATUS_MAP = {
    DedupStatus.SKIP: "skipped",
    DedupStatus.REVIEW: "review",
    DedupStatus.NEW: "created",
}


async def run(dry_run: bool, enrich: bool, csv_path: Path) -> None:
    settings = load_settings()

    if not settings.notion_people_data_source_id:
        logger.error("NOTION_PEOPLE_DATA_SOURCE_ID not set in .env — aborting.")
        sys.exit(1)
    if not settings.notion_companies_data_source_id:
        logger.error("NOTION_COMPANIES_DATA_SOURCE_ID not set in .env — aborting.")
        sys.exit(1)

    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id)
    people_syncer = NotionPeopleSyncer(
        client, settings.notion_people_data_source_id, company_syncer
    )

    logger.info("Loading Notion snapshots...")
    await company_syncer.load_snapshot()
    await people_syncer.load_snapshot()

    records = _parse_connections(csv_path)
    logger.info("Parsed {} connections from {}", len(records), csv_path)

    counts: dict[str, int] = {"created": 0, "skipped": 0, "review": 0, "error": 0}
    review_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for i, person in enumerate(records):
        if dry_run:
            match = find_match(person.name, person.company, people_syncer._existing)
            status = _STATUS_MAP[match.status]
            counts[status] += 1
            if match.status == DedupStatus.SKIP:
                skipped_rows.append({
                    "score": f"{match.score:.1f}",
                    "input_name": person.name,
                    "input_company": person.company,
                    "matched_name": match.matched_name,
                    "matched_company": match.matched_company,
                    "linkedin_url": person.linkedin_url,
                })
            continue

        try:
            email = person.email
            if enrich and not email:
                await asyncio.sleep(1)  # rate limit: 1 req/s
                enrichment = await enrich_person(person.name, person.company, settings)
                if enrichment.email:
                    email = enrichment.email

            result = await people_syncer.upsert(
                PersonRecord(
                    name=person.name,
                    company=person.company,
                    position=person.position,
                    linkedin_url=person.linkedin_url,
                    email=email,
                )
            )
            counts[result.status] += 1

            row = {
                "score": f"{result.score:.1f}",
                "input_name": person.name,
                "input_company": person.company,
                "matched_name": result.matched_name,
                "matched_company": result.matched_company,
                "linkedin_url": person.linkedin_url,
            }
            if result.status == "skipped":
                skipped_rows.append(row)
            elif result.status == "review":
                review_rows.append(row)

        except Exception:  # noqa: BLE001
            logger.exception("Failed to upsert {} @ {}", person.name, person.company)
            counts["error"] += 1

        if (i + 1) % 50 == 0:
            logger.info("Progress: {}/{} — {}", i + 1, len(records), counts)

    if review_rows:
        _REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(review_rows, columns=_REVIEW_FIELDS).to_csv(_REVIEW_CSV, sep=";", index=False, encoding="utf-8-sig")
        logger.info("Review {} borderline match(es) in {}", len(review_rows), _REVIEW_CSV)

    if skipped_rows:
        _SKIPED_CSV.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(skipped_rows, columns=_REVIEW_FIELDS).to_csv(_SKIPED_CSV, sep=";", index=False, encoding="utf-8-sig")

    mode = "DRY RUN" if dry_run else "LIVE"
    logger.info(
        "[{}] Done. created={} skipped={} review={} error={}",
        mode,
        counts["created"],
        counts["skipped"],
        counts["review"],
        counts["error"],
    )


def _flag(name: str) -> bool:
    return name in sys.argv


def _arg(prefix: str) -> str | None:
    for a in sys.argv:
        if a.startswith(f"{prefix}="):
            return a.split("=", 1)[1]
    return None


if __name__ == "__main__":
    csv_path = Path(_arg("--csv") or str(_DEFAULT_CSV))
    asyncio.run(
        run(
            dry_run=_flag("--dry-run"),
            enrich=not _flag("--no-enrich"),
            csv_path=csv_path,
        )
    )
