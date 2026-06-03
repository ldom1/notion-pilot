#!/usr/bin/env python
"""Batch enrichment CLI — enrich People and/or Companies records in Notion.

Usage:
    uv run python scripts/crm_enrich.py --people --limit 20 --dry-run
    uv run python scripts/crm_enrich.py --companies --limit 10
    uv run python scripts/crm_enrich.py --people --companies
"""

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from notion_client import AsyncClient

from notion_pilot.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer
from notion_pilot.shared.config import load_settings
from notion_pilot.shared.utils.enrichment import enrich_company, enrich_person

_RATE_LIMIT_S = 0.4  # seconds between Notion writes to stay under rate limit
_NOTION_BASE = "https://www.notion.so"


def _page_url(page_id: str) -> str:
    return f"{_NOTION_BASE}/{page_id.replace('-', '')}"


@dataclass
class CompanyRow:
    name: str
    page_id: str
    source: str
    linkedin: str = ""
    size: str = ""
    country: str = ""
    sector: str = ""
    logo: bool = False
    status: str = "ok"


@dataclass
class PeopleRow:
    name: str
    company: str
    page_id: str
    source: str
    email: str = ""
    seniority: str = ""
    status: str = "ok"


@dataclass
class RunReport:
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    table: str = ""
    total_candidates: int = 0
    total_in_db: int = 0
    wrote: int = 0
    skipped_no_data: int = 0
    dry_run: bool = False
    rows: list = field(default_factory=list)

    def write(self, path: Path) -> None:
        lines = [
            f"# CRM Enrichment Report — {self.table}",
            "",
            f"**Date:** {self.started_at[:19].replace('T', ' ')} UTC  ",
            f"**Mode:** {'dry-run' if self.dry_run else 'live'}  ",
            f"**DB total:** {self.total_in_db}  ",
            f"**Candidates (missing fields):** {self.total_candidates}  ",
            f"**Written:** {self.wrote}  ",
            f"**Skipped (no data):** {self.skipped_no_data}  ",
            "",
        ]

        if self.table == "Companies" and self.rows:
            enriched_rows = [r for r in self.rows if r.status == "ok"]
            no_data_rows = [r for r in self.rows if r.status == "no_data"]

            if enriched_rows:
                lines += [
                    "## Enriched",
                    "",
                    "| Company | LinkedIn | Size | Country | Sector | Logo | Source | Notion |",
                    "|---------|----------|------|---------|--------|------|--------|--------|",
                ]
                for r in enriched_rows:
                    logo = "✓" if r.logo else "-"
                    li = f"[↗]({r.linkedin})" if r.linkedin else "-"
                    lines.append(
                        f"| {r.name} | {li} | {r.size or '-'} | {r.country or '-'}"
                        f" | {r.sector or '-'} | {logo} | {r.source} | [→]({_page_url(r.page_id)}) |"
                    )
                lines.append("")

            if no_data_rows:
                lines += [
                    "## No data found",
                    "",
                    "| Company | Notion |",
                    "|---------|--------|",
                ]
                for r in no_data_rows:
                    lines.append(f"| {r.name} | [→]({_page_url(r.page_id)}) |")
                lines.append("")

        elif self.table == "People" and self.rows:
            enriched_rows = [r for r in self.rows if r.status == "ok"]
            no_data_rows = [r for r in self.rows if r.status == "no_data"]

            if enriched_rows:
                lines += [
                    "## Enriched",
                    "",
                    "| Name | Company | Email | Seniority | Source | Notion |",
                    "|------|---------|-------|-----------|--------|--------|",
                ]
                for r in enriched_rows:
                    lines.append(
                        f"| {r.name} | {r.company or '-'} | {r.email or '-'}"
                        f" | {r.seniority or '-'} | {r.source} | [→]({_page_url(r.page_id)}) |"
                    )
                lines.append("")

            if no_data_rows:
                lines += [
                    "## No data found",
                    "",
                    "| Name | Company | Notion |",
                    "|------|---------|--------|",
                ]
                for r in no_data_rows:
                    lines.append(f"| {r.name} | {r.company or '-'} | [→]({_page_url(r.page_id)}) |")
                lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Report written to {}", path)


async def enrich_people(limit: int, dry_run: bool, report_dir: Path) -> None:
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

    report = RunReport(table="People", dry_run=dry_run, total_in_db=len(people_syncer._existing))

    candidates = [
        c
        for c in people_syncer._existing
        if not (c.get("seniority") and c.get("role_type") and c.get("email"))
    ]
    report.total_candidates = len(candidates)
    logger.info(
        "{} people need enrichment (out of {})", len(candidates), len(people_syncer._existing)
    )

    for candidate in candidates[:limit]:
        name = candidate["name"]
        company = candidate.get("company", "")
        position = candidate.get("position", "")

        logger.info("Enriching {} @ {}...", name, company)
        enrichment = await enrich_person(name, company, settings, position=position)

        props: dict[str, object] = {}
        if enrichment.email and not candidate.get("email"):
            props["Email - pro"] = {"email": enrichment.email}
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
            report.skipped_no_data += 1
            report.rows.append(
                PeopleRow(
                    name, company, candidate["page_id"], enrichment.source or "", status="no_data"
                )
            )
            continue

        logger.info(
            "  Found: email={} seniority={} role_type={} source={}",
            enrichment.email or "-",
            enrichment.seniority or "-",
            enrichment.role_type or [],
            enrichment.source,
        )

        if dry_run:
            logger.info("  [DRY-RUN] would write {} props to {}", len(props), candidate["page_id"])
        else:
            await client.pages.update(candidate["page_id"], properties=props)
            await asyncio.sleep(_RATE_LIMIT_S)
            report.wrote += 1

        report.rows.append(
            PeopleRow(
                name,
                company,
                candidate["page_id"],
                enrichment.source or "",
                email=enrichment.email,
                seniority=enrichment.seniority,
            )
        )

    logger.info(
        "Done{}. processed={} wrote={} skipped(no-data)={}",
        " (dry-run)" if dry_run else "",
        len([r for r in report.rows if r.status == "ok"]),
        report.wrote,
        report.skipped_no_data,
    )

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    report.write(report_dir / f"enrich_people_{ts}.md")


async def enrich_companies(limit: int, dry_run: bool, report_dir: Path) -> None:
    settings = load_settings()
    if not settings.notion_companies_data_source_id:
        logger.error("NOTION_COMPANIES_DATA_SOURCE_ID not set")
        return

    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id)
    await company_syncer.load_snapshot()

    report = RunReport(
        table="Companies", dry_run=dry_run, total_in_db=len(company_syncer._id_to_name)
    )

    # Only process companies missing at least one key field, sector, or icon
    items = [
        (pid, name)
        for pid, name in company_syncer._id_to_name.items()
        if not all(
            [
                company_syncer.details.get(pid, {}).get("linkedin_url"),
                company_syncer.details.get(pid, {}).get("size"),
                company_syncer.details.get(pid, {}).get("country"),
                company_syncer.details.get(pid, {}).get("sector"),
                company_syncer.details.get(pid, {}).get("icon_url"),
            ]
        )
    ]
    report.total_candidates = len(items)
    logger.info(
        "{} companies need enrichment (out of {})", len(items), len(company_syncer._id_to_name)
    )

    for page_id, name in items[:limit]:
        existing = company_syncer.details.get(page_id, {})
        website = existing.get("website", "")
        domain = website.split("//")[-1].split("/")[0].removeprefix("www.") if website else ""
        logger.info("Enriching company {}{}...", name, f" (domain={domain})" if domain else "")
        enrichment = await enrich_company(name, settings, domain=domain)

        props: dict[str, object] = {}
        if enrichment.linkedin_url and not existing.get("linkedin_url"):
            props["Linkedin"] = {"url": enrichment.linkedin_url}
        if enrichment.website and not existing.get("website"):
            props["Website"] = {"url": enrichment.website}
        if enrichment.size and not existing.get("size"):
            props["Size"] = {"select": {"name": enrichment.size}}
        if enrichment.country and not existing.get("country"):
            props["Country"] = {"select": {"name": enrichment.country}}
        if enrichment.sector and not existing.get("sector"):
            props["Sector"] = {"select": {"name": enrichment.sector}}
        clean_stack = [t for t in enrichment.tech_stack if t and "," not in t]
        if clean_stack:
            props["Tech Stack"] = {"multi_select": [{"name": t} for t in clean_stack]}

        set_icon = bool(enrichment.logo_url and not existing.get("icon_url"))

        if not props and not set_icon:
            logger.info("  No data found (source={})", enrichment.source or "none")
            report.skipped_no_data += 1
            report.rows.append(CompanyRow(name, page_id, enrichment.source or "", status="no_data"))
            continue

        logger.info(
            "  Found: linkedin={} size={} country={} sector={} logo={} source={}",
            enrichment.linkedin_url or "-",
            enrichment.size or "-",
            enrichment.country or "-",
            enrichment.sector or "-",
            "yes" if set_icon else "no",
            enrichment.source,
        )

        if dry_run:
            logger.info(
                "  [DRY-RUN] would write {} props{} to {}",
                len(props),
                " + icon" if set_icon else "",
                page_id,
            )
        else:
            update_kwargs: dict[str, object] = {"properties": props}
            if set_icon:
                update_kwargs["icon"] = {
                    "type": "external",
                    "external": {"url": enrichment.logo_url},
                }
            await client.pages.update(page_id, **update_kwargs)
            await asyncio.sleep(_RATE_LIMIT_S)
            report.wrote += 1

        report.rows.append(
            CompanyRow(
                name,
                page_id,
                enrichment.source or "",
                linkedin=enrichment.linkedin_url,
                size=enrichment.size,
                country=enrichment.country,
                sector=enrichment.sector,
                logo=set_icon,
            )
        )

    logger.info(
        "Done{}. processed={} wrote={} skipped(no-data)={}",
        " (dry-run)" if dry_run else "",
        len([r for r in report.rows if r.status == "ok"]),
        report.wrote,
        report.skipped_no_data,
    )

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    report.write(report_dir / f"enrich_companies_{ts}.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch CRM enrichment")
    parser.add_argument("--people", action="store_true", help="Enrich People records")
    parser.add_argument("--companies", action="store_true", help="Enrich Company records")
    parser.add_argument(
        "--limit", type=int, default=9999, help="Max records to process (default: all)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing")
    parser.add_argument(
        "--report-dir", default="data/crm", help="Directory for the markdown report"
    )
    args = parser.parse_args()

    if not args.people and not args.companies:
        parser.error("Specify at least one of --people or --companies")

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    if args.people:
        asyncio.run(enrich_people(args.limit, args.dry_run, report_dir))
    if args.companies:
        asyncio.run(enrich_companies(args.limit, args.dry_run, report_dir))


if __name__ == "__main__":
    main()
