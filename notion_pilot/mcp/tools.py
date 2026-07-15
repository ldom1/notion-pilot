"""MCP tool implementations — thin wrappers around existing crm/shared logic."""

import asyncio

from rapidfuzz.fuzz import token_set_ratio, token_sort_ratio

from notion_pilot.crm.prospection import rank_contacts
from notion_pilot.crm.queries import get_open_leads, get_recent_people
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
from notion_pilot.shared.prosper_client import CompanyEnrichment, enrich_company, enrich_person
from notion_pilot.shared.siren_lookup import (
    lookup_siren_candidates,
    naf_section_to_sector,
    tranche_to_size,
)
from notion_pilot.shared.utils.dedup import (
    DedupStatus,
    DuplicatePair,
    find_company_duplicates,
    find_match,
    find_people_duplicates,
    normalize,
    normalize_domain,
    notion_page_url,
)

_RATE_LIMIT_S = 0.4  # stay under Notion's write rate limit

_DEDUP_MATCH_THRESHOLD = 85.0
_DEDUP_REVIEW_THRESHOLD = 90.0  # token_set_ratio, catches acronym/subset containment


def _company_dedup_signal(
    record: CompanyRecord,
    id_to_name: dict[str, str],
    details: dict[str, dict[str, str]],
) -> tuple[str, float, str, str, list[dict[str, object]]]:
    """4-signal decision chain, in strict precedence order — exactly one
    status comes out, never a mix: domain_match > confident name match
    (token_sort_ratio) > acronym/subset name match (token_set_ratio) >
    would_create. Returns (status, score, best_name, best_page_id, candidates)."""
    norm = normalize(record.name)

    if record.contact_email and "@" in record.contact_email:
        email_domain = normalize_domain(record.contact_email.split("@")[-1])
        for page_id, name in id_to_name.items():
            website = details.get(page_id, {}).get("website", "")
            if website and normalize_domain(website) == email_domain:
                return "matched", 100.0, name, page_id, []

    best_sort = (0.0, "", "")  # score, name, page_id
    best_set = (0.0, "", "")
    for page_id, name in id_to_name.items():
        cached_norm = normalize(name)
        sort_score = float(token_sort_ratio(norm, cached_norm))
        if sort_score > best_sort[0]:
            best_sort = (sort_score, name, page_id)
        set_score = float(token_set_ratio(norm, cached_norm))
        if set_score > best_set[0]:
            best_set = (set_score, name, page_id)

    if best_sort[0] >= _DEDUP_MATCH_THRESHOLD:
        return "matched", best_sort[0], best_sort[1], best_sort[2], []
    if best_set[0] >= _DEDUP_REVIEW_THRESHOLD:
        score, name, page_id = best_set
        return (
            "needs_review",
            score,
            name,
            page_id,
            [{"type": "notion", "page_id": page_id, "name": name, "score": score}],
        )
    return "would_create", best_sort[0], best_sort[1], best_sort[2], []


def _registry_fields(candidate: dict[str, str]) -> dict[str, str]:
    """Maps one lookup_siren_candidates() entry to the Notion fields it can
    fill: sector, size, country. Omits any that don't resolve to a usable
    value — callers only apply what's present."""
    fields: dict[str, str] = {"country": "FR"}
    sector = naf_section_to_sector(
        candidate["section_activite_principale"], candidate["activite_principale"]
    )
    if sector:
        fields["sector"] = sector
    size = tranche_to_size(candidate["tranche_effectif_salarie"])
    if size:
        fields["size"] = size
    return fields


async def upsert_people(
    session: SyncerSession, records: list[PersonRecord], confirm: bool = False
) -> BatchResult:
    await session.ensure_loaded()
    results: list[RecordResult] = []

    for i, record in enumerate(records):
        if not confirm:
            match = find_match(
                record.name, record.company, session.people_syncer._existing,
                email=record.email or "", linkedin_url=record.linkedin_url or "",
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
        if not confirm:
            status, score, best_name, best_page_id, candidates = _company_dedup_signal(
                record, session.company_syncer._id_to_name, session.company_syncer.details
            )
            reason = (
                f"name similarity to existing company {best_name!r} (score {score:.0f})"
                if status == "needs_review"
                else ""
            )

            siren = ""
            siren_candidate_name = ""
            enrichment_preview: dict[str, str] = {}
            if status == "would_create":
                try:
                    siren_candidates = await lookup_siren_candidates(record.name)
                except Exception:  # noqa: BLE001
                    siren_candidates = []
                if siren_candidates:
                    top = siren_candidates[0]
                    divergence = float(
                        token_sort_ratio(normalize(record.name), normalize(top["matched_name"]))
                    )
                    if divergence < _DEDUP_MATCH_THRESHOLD:
                        status = "needs_review"
                        reason = (
                            f"SIREN candidate {top['matched_name']!r} doesn't resemble "
                            f"{record.name!r} (score {divergence:.0f}); verify before writing"
                        )
                        candidates = [
                            {
                                "type": "siren",
                                "siren": c["siren"],
                                "matched_name": c["matched_name"],
                                "score": float(
                                    token_sort_ratio(normalize(record.name), normalize(c["matched_name"]))
                                ),
                            }
                            for c in siren_candidates
                        ]
                    else:
                        siren = top["siren"]
                        siren_candidate_name = top["matched_name"]
                        enrichment_preview = {"siren": siren, **_registry_fields(top)}

            if not record.website and not enrichment_preview.get("website") and record.contact_email:
                domain = record.contact_email.split("@")[-1]
                enrichment_preview["website"] = f"https://{domain}"

            results.append(
                RecordResult(
                    name=record.name,
                    status=status,
                    score=score,
                    matched_name=best_name,
                    siren=siren,
                    siren_candidate_name=siren_candidate_name,
                    reason=reason,
                    candidates=candidates,
                    enrichment_preview=enrichment_preview,
                )
            )
            continue

        try:
            dedup_status, dedup_score, dedup_best_name, dedup_page_id, dedup_candidates = (
                _company_dedup_signal(
                    record, session.company_syncer._id_to_name, session.company_syncer.details
                )
            )
            if dedup_status == "needs_review" and not record.force:
                results.append(
                    RecordResult(
                        name=record.name,
                        status="needs_review",
                        score=dedup_score,
                        matched_name=dedup_best_name,
                        candidates=dedup_candidates,
                        reason=f"name similarity to existing company {dedup_best_name!r} "
                        f"(score {dedup_score:.0f})",
                    )
                )
                continue

            if dedup_status == "matched":
                # Our own dedup signal (domain match or confident name match) is
                # authoritative — it always wins over get_or_create's separate,
                # weaker name-only check, so a domain match with a low name-similarity
                # score (e.g. "RTE" vs "Rte France") can't slip past it into a duplicate.
                page_id = dedup_page_id
                created_new = False
            else:
                known_before = set(session.company_syncer._id_to_name.keys())
                page_id = await session.company_syncer.get_or_create(record.name)
                created_new = page_id not in known_before

            if not created_new:
                status = "matched"
            elif dedup_status == "needs_review":  # only reachable here when record.force is True
                status = "created_with_override"
            else:
                status = "created"

            siren = ""
            siren_candidate_name = ""
            reason = (
                f"created despite name similarity to {dedup_best_name!r} (score {dedup_score:.0f})"
                if status == "created_with_override"
                else ""
            )

            if created_new:
                props: dict[str, object] = {}
                try:
                    enrichment = await enrich_company(record.name, settings)
                except Exception:  # noqa: BLE001
                    enrichment = CompanyEnrichment()
                if enrichment.sector:
                    props["Sector"] = {"select": {"name": enrichment.sector}}
                if enrichment.size:
                    props["Size"] = {"select": {"name": enrichment.size}}
                if enrichment.country:
                    props["Country"] = {"select": {"name": enrichment.country}}
                if enrichment.linkedin_url:
                    props["Linkedin"] = {"url": enrichment.linkedin_url}

                try:
                    siren_candidates = await lookup_siren_candidates(record.name)
                except Exception:  # noqa: BLE001
                    siren_candidates = []
                if siren_candidates:
                    top = siren_candidates[0]
                    divergence = float(
                        token_sort_ratio(normalize(record.name), normalize(top["matched_name"]))
                    )
                    if divergence >= _DEDUP_MATCH_THRESHOLD:
                        siren = top["siren"]
                        siren_candidate_name = top["matched_name"]
                        await session.company_syncer.ensure_siren_property()
                        props["SIREN"] = {"rich_text": [{"text": {"content": siren}}]}
                        for field, value in _registry_fields(top).items():
                            key = {"sector": "Sector", "size": "Size", "country": "Country"}[field]
                            if key not in props:
                                props[key] = {"select": {"name": value}}

                website = record.website or enrichment.website or ""
                if not website and record.contact_email:
                    website = f"https://{record.contact_email.split('@')[-1]}"
                if website:
                    props["Website"] = {"url": website}

                if props:
                    await session.company_syncer._client.pages.update(page_id, properties=props)

            results.append(
                RecordResult(
                    name=record.name,
                    status=status,
                    page_id=page_id,
                    siren=siren,
                    siren_candidate_name=siren_candidate_name,
                    reason=reason,
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
