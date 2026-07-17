"""MCP tool implementations — thin wrappers around existing crm/shared logic."""

import asyncio

from rapidfuzz.fuzz import token_sort_ratio

from notion_pilot.crm.prospection import rank_contacts
from notion_pilot.crm.queries import get_open_leads, get_recent_people
from notion_pilot.crm.syncer import CompanyRecord as SyncerCompanyRecord
from notion_pilot.crm.syncer import PersonRecord as SyncerPersonRecord
from notion_pilot.mcp.models import (
    BatchResult,
    CompanyRecord,
    PersonRecord,
    RecordResult,
    summarize,
)
from notion_pilot.mcp.session import SyncerSession
from notion_pilot.shared.config import Settings
from notion_pilot.shared.prosper_client import enrich_company, enrich_person
from notion_pilot.shared.utils.dedup import (
    DedupStatus,
    DuplicatePair,
    find_company_duplicates,
    find_match,
    find_people_duplicates,
    normalize,
    notion_page_url,
)

_RATE_LIMIT_S = 0.4  # stay under Notion's write rate limit


async def upsert_people(
    session: SyncerSession, records: list[PersonRecord], confirm: bool = False
) -> BatchResult:
    await session.ensure_loaded()
    results: list[RecordResult] = []

    for i, record in enumerate(records):
        if not confirm:
            match = find_match(
                record.name,
                record.company,
                session.people_syncer._existing,
                email=record.email or "",
                linkedin_url=record.linkedin_url or "",
            )
            if match.status == DedupStatus.SKIP:
                status = "would_skip"
            elif match.status == DedupStatus.REVIEW:
                status = "would_review"
            else:
                status = "would_create"
            results.append(
                RecordResult(
                    name=record.name,
                    status=status,
                    score=match.score,
                    matched_name=match.matched_name,
                    matched_company=match.matched_company,
                )
            )
            continue

        try:
            syncer_record = SyncerPersonRecord(
                name=record.name,
                company=record.company,
                position=record.position or "",
                linkedin_url=record.linkedin_url or "",
                email=record.email or "",
                phone=record.phone or "",
                seniority=record.seniority or "",
                role_type=record.role_type or [],
                force=record.force,
            )
            outcome = await session.people_syncer.upsert(syncer_record)
            results.append(
                RecordResult(
                    name=record.name,
                    status=outcome.status,
                    score=outcome.score,
                    matched_name=outcome.matched_name,
                    matched_company=outcome.matched_company,
                    page_id=outcome.page_id,
                )
            )
            if i < len(records) - 1:
                await asyncio.sleep(_RATE_LIMIT_S)
        except Exception as exc:  # noqa: BLE001 — never let one bad record abort the batch
            results.append(RecordResult(name=record.name, status="error", error_message=str(exc)))

    return summarize(results)


async def upsert_companies(
    session: SyncerSession, settings: Settings, records: list[CompanyRecord], confirm: bool = False
) -> BatchResult:
    await session.ensure_loaded()
    results: list[RecordResult] = []

    for i, record in enumerate(records):
        syncer_record = SyncerCompanyRecord(
            name=record.name,
            website=record.website or "",
            contact_email=record.contact_email or "",
            force=record.force,
        )

        if not confirm:
            try:
                preview = await session.company_syncer.preview(syncer_record)
                results.append(
                    RecordResult(
                        name=record.name,
                        status=preview.status,
                        score=preview.score,
                        matched_name=preview.matched_name,
                        siren=preview.siren,
                        siren_candidate_name=preview.siren_candidate_name,
                        reason=preview.reason,
                        candidates=preview.candidates,
                        enrichment_preview=preview.enrichment_preview,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                # Same isolation as the confirm=True branch below — an
                # unexpected failure in preview() (anything not already
                # swallowed internally) must degrade just this one record,
                # not crash the whole dry-run batch.
                results.append(
                    RecordResult(name=record.name, status="error", error_message=str(exc))
                )
            continue

        try:
            outcome = await session.company_syncer.upsert(syncer_record, settings=settings)
            results.append(
                RecordResult(
                    name=record.name,
                    status=outcome.status,
                    page_id=outcome.page_id,
                    score=outcome.score,
                    matched_name=outcome.matched_name,
                    siren=outcome.siren,
                    siren_candidate_name=outcome.siren_candidate_name,
                    reason=outcome.reason,
                    candidates=outcome.candidates,
                )
            )
            if i < len(records) - 1:
                await asyncio.sleep(_RATE_LIMIT_S)
        except Exception as exc:  # noqa: BLE001
            results.append(RecordResult(name=record.name, status="error", error_message=str(exc)))

    return summarize(results)


async def find_duplicates(
    session: SyncerSession, target: str, threshold: float = 85.0
) -> list[dict[str, float | str]]:
    if target not in ("people", "companies", "both"):
        raise ValueError(f"target must be 'people', 'companies', or 'both', got {target!r}")

    await session.ensure_loaded()
    pairs: list[DuplicatePair] = []
    if target in ("companies", "both"):
        pairs += find_company_duplicates(session.company_syncer._id_to_name, threshold)
    if target in ("people", "both"):
        pairs += find_people_duplicates(session.people_syncer._existing, threshold)

    return [
        {
            "score": p.score,
            "name_a": p.name_a,
            "page_id_a": p.id_a,
            "name_b": p.name_b,
            "page_id_b": p.id_b,
            "notion_url_a": notion_page_url(p.id_a),
            "notion_url_b": notion_page_url(p.id_b),
            "context_a": p.context_a,
            "context_b": p.context_b,
        }
        for p in pairs
    ]


async def enrich_people(
    session: SyncerSession,
    settings: Settings,
    page_ids: list[str] | None = None,
    limit: int = 9999,
    confirm: bool = False,
) -> BatchResult:
    await session.ensure_loaded()
    candidates = [
        c
        for c in session.people_syncer._existing
        if (page_ids is None or c["page_id"] in page_ids)
        and not (c.get("seniority") and c.get("role_type") and c.get("email"))
    ][:limit]

    results: list[RecordResult] = []
    for i, candidate in enumerate(candidates):
        try:
            enrichment = await enrich_person(
                candidate["name"],
                candidate.get("company", ""),
                settings,
                position=candidate.get("position", ""),
            )
            if not any(
                [enrichment.email, enrichment.phone, enrichment.seniority, enrichment.role_type]
            ):
                results.append(RecordResult(name=candidate["name"], status="no_data"))
                continue

            if not confirm:
                results.append(RecordResult(name=candidate["name"], status="would_enrich"))
                continue

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
            await session.people_syncer._client.pages.update(candidate["page_id"], properties=props)
            results.append(RecordResult(name=candidate["name"], status="ok"))
            if i < len(candidates) - 1:
                await asyncio.sleep(_RATE_LIMIT_S)
        except Exception as exc:  # noqa: BLE001
            results.append(
                RecordResult(name=candidate["name"], status="error", error_message=str(exc))
            )

    return summarize(results)


async def enrich_companies(
    session: SyncerSession,
    settings: Settings,
    page_ids: list[str] | None = None,
    limit: int = 9999,
    confirm: bool = False,
) -> BatchResult:
    await session.ensure_loaded()
    items = [
        (pid, name)
        for pid, name in session.company_syncer._id_to_name.items()
        if page_ids is None or pid in page_ids
    ][:limit]

    results: list[RecordResult] = []
    for i, (page_id, name) in enumerate(items):
        try:
            existing = session.company_syncer.details.get(page_id, {})
            website = existing.get("website", "")
            domain = website.split("//")[-1].split("/")[0].removeprefix("www.") if website else ""
            enrichment = await enrich_company(name, settings, domain=domain)
            if not any(
                [enrichment.linkedin_url, enrichment.sector, enrichment.size, enrichment.country]
            ):
                results.append(RecordResult(name=name, status="no_data"))
                continue

            if not confirm:
                results.append(RecordResult(name=name, status="would_enrich"))
                continue

            props: dict[str, object] = {}
            if enrichment.linkedin_url and not existing.get("linkedin_url"):
                props["Linkedin"] = {"url": enrichment.linkedin_url}
            if enrichment.size and not existing.get("size"):
                props["Size"] = {"select": {"name": enrichment.size}}
            if enrichment.country and not existing.get("country"):
                props["Country"] = {"select": {"name": enrichment.country}}
            if enrichment.sector and not existing.get("sector"):
                props["Sector"] = {"select": {"name": enrichment.sector}}
            await session.company_syncer._client.pages.update(page_id, properties=props)
            results.append(RecordResult(name=name, status="ok"))
            if i < len(items) - 1:
                await asyncio.sleep(_RATE_LIMIT_S)
        except Exception as exc:  # noqa: BLE001
            results.append(RecordResult(name=name, status="error", error_message=str(exc)))

    return summarize(results)


async def rank_contacts_for_pitch(
    session: SyncerSession,
    settings: Settings,
    pitch: str,
    top_k: int = 10,
    company: str | None = None,
    seniority: str | None = None,
    role_type: str | None = None,
) -> list[dict[str, object]]:
    await session.ensure_loaded()
    candidates = session.people_syncer._existing
    if company:
        candidates = [c for c in candidates if c.get("company") == company]
    if seniority:
        candidates = [c for c in candidates if c.get("seniority") == seniority]
    if role_type:
        candidates = [c for c in candidates if role_type in c.get("role_type", [])]

    ranked = await rank_contacts(pitch, candidates, settings, top_k=top_k)
    return [
        {
            "page_id": r.page_id,
            "name": r.name,
            "company": r.company,
            "position": r.position,
            "score": r.score,
            "reasoning": r.reasoning,
            "linkedin_url": r.linkedin_url,
        }
        for r in ranked
    ]


_SEARCH_MIN_SCORE = 60.0


async def search_companies(
    session: SyncerSession, query: str, limit: int = 10
) -> list[dict[str, object]]:
    await session.ensure_loaded()
    norm_query = normalize(query)
    scored = [
        (page_id, name, float(token_sort_ratio(norm_query, normalize(name))))
        for page_id, name in session.company_syncer._id_to_name.items()
    ]
    scored = [s for s in scored if s[2] >= _SEARCH_MIN_SCORE]
    scored.sort(key=lambda s: -s[2])
    return [{"page_id": pid, "name": name, "score": score} for pid, name, score in scored[:limit]]


async def search_people(
    session: SyncerSession, query: str, limit: int = 10
) -> list[dict[str, object]]:
    await session.ensure_loaded()
    norm_query = normalize(query)
    scored = [
        (c, float(token_sort_ratio(norm_query, normalize(f"{c['name']} {c.get('company', '')}"))))
        for c in session.people_syncer._existing
    ]
    scored = [s for s in scored if s[1] >= _SEARCH_MIN_SCORE]
    scored.sort(key=lambda s: -s[1])
    return [
        {
            "page_id": c["page_id"],
            "name": c["name"],
            "company": c.get("company", ""),
            "score": score,
        }
        for c, score in scored[:limit]
    ]


async def get_recent_people_tool(settings: Settings) -> list[dict[str, object]]:
    return await get_recent_people(settings)


async def get_open_leads_tool(settings: Settings) -> list[dict[str, object]]:
    return await get_open_leads(settings)


async def refresh_notion_snapshot(session: SyncerSession) -> dict[str, int]:
    people_count, companies_count = await session.refresh()
    return {"people_count": people_count, "companies_count": companies_count}
