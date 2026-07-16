"""Unit tests for mcp/tools.py upsert_people/upsert_companies — mocked Notion client."""

from unittest.mock import AsyncMock

from pydantic import SecretStr

from notion_pilot.mcp.models import CompanyRecord, PersonRecord
from notion_pilot.mcp.session import SyncerSession
from notion_pilot.mcp.tools import upsert_companies, upsert_people
from notion_pilot.shared.config import Settings
from notion_pilot.shared.prosper_client import CompanyEnrichment


def _settings() -> Settings:
    return Settings(
        notion_token=SecretStr("fake-token"),
        notion_telegram_msg_database_id="fake-db",
        notion_people_data_source_id="fake-people-ds",
        notion_companies_data_source_id="fake-companies-ds",
    )


async def _loaded_session(existing_people=None, existing_companies=None) -> SyncerSession:
    session = SyncerSession(_settings())
    monkeypatch_load = AsyncMock()
    session.company_syncer.load_notion_snapshot = monkeypatch_load
    session.people_syncer.load_notion_snapshot = monkeypatch_load
    session.company_syncer._id_to_name = dict(existing_companies or {})
    session.company_syncer._name_to_id = {
        v.lower(): k for k, v in (existing_companies or {}).items()
    }
    session.people_syncer._existing = list(existing_people or [])
    await session.ensure_loaded()
    return session


async def test_upsert_people_dry_run_does_not_write(monkeypatch):
    session = await _loaded_session()
    upsert_mock = AsyncMock()
    monkeypatch.setattr(session.people_syncer, "upsert", upsert_mock)

    result = await upsert_people(
        session, [PersonRecord(name="Jean Dupont", company="EDF")], confirm=False
    )

    upsert_mock.assert_not_called()
    assert result.results[0].status == "would_create"
    assert result.summary == {"would_create": 1}


async def test_upsert_people_dry_run_reports_existing_match():
    session = await _loaded_session(
        existing_people=[{"name": "Jean Dupont", "company": "EDF", "page_id": "p1"}]
    )

    result = await upsert_people(
        session, [PersonRecord(name="Jean Dupont", company="EDF")], confirm=False
    )

    assert result.results[0].status == "would_skip"
    assert result.results[0].matched_name == "Jean Dupont"


async def test_upsert_people_confirm_true_writes(monkeypatch):
    session = await _loaded_session()
    from notion_pilot.crm.syncer import UpsertResult

    upsert_mock = AsyncMock(return_value=UpsertResult(status="created", page_id="new-id"))
    monkeypatch.setattr(session.people_syncer, "upsert", upsert_mock)

    result = await upsert_people(
        session, [PersonRecord(name="Jean Dupont", company="EDF")], confirm=True
    )

    upsert_mock.assert_awaited_once()
    assert result.results[0].status == "created"
    assert result.results[0].page_id == "new-id"
    assert result.success_count == 1
    assert result.fail_count == 0


async def test_upsert_people_confirm_true_force_creates_with_override(monkeypatch):
    session = await _loaded_session()
    from notion_pilot.crm.syncer import UpsertResult

    upsert_mock = AsyncMock(
        return_value=UpsertResult(status="created_with_override", page_id="new-id")
    )
    monkeypatch.setattr(session.people_syncer, "upsert", upsert_mock)

    result = await upsert_people(
        session,
        [PersonRecord(name="Jean Dupont", company="EDF", force=True)],
        confirm=True,
    )

    upsert_mock.assert_awaited_once()
    assert result.results[0].status == "created_with_override"


async def test_upsert_people_batch_continues_after_one_error(monkeypatch):
    session = await _loaded_session()
    from notion_pilot.crm.syncer import UpsertResult

    async def flaky_upsert(person):
        if person.name == "Broken Record":
            raise RuntimeError("Notion API timeout")
        return UpsertResult(status="created", page_id="ok-id")

    monkeypatch.setattr(session.people_syncer, "upsert", flaky_upsert)

    result = await upsert_people(
        session,
        [
            PersonRecord(name="Broken Record", company="EDF"),
            PersonRecord(name="Fine Record", company="EDF"),
        ],
        confirm=True,
    )

    assert result.fail_count == 1
    assert result.success_count == 1
    assert result.results[0].status == "error"
    assert "Notion API timeout" in result.results[0].error_message
    assert result.results[1].status == "created"


async def test_upsert_companies_dry_run_reports_would_create(monkeypatch):
    session = await _loaded_session(existing_companies={"id-edf": "EDF"})
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates", AsyncMock(return_value=[])
    )

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="OVHcloud")], confirm=False
    )

    assert result.results[0].status == "would_create"
    assert result.results[0].siren == ""


async def test_upsert_companies_dry_run_shows_siren_candidate_and_enrichment(monkeypatch):
    session = await _loaded_session()
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates",
        AsyncMock(
            return_value=[
                {
                    "siren": "428895676",
                    "matched_name": "ARTELYS",
                    "section_activite_principale": "M",
                    "activite_principale": "70.22Z",
                    "tranche_effectif_salarie": "12",
                }
            ]
        ),
    )

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Artelys")], confirm=False
    )

    assert result.results[0].status == "would_create"
    assert result.results[0].siren == "428895676"
    assert result.results[0].siren_candidate_name == "ARTELYS"
    assert result.results[0].enrichment_preview == {
        "siren": "428895676",
        "sector": "Consulting",
        "size": "11-50",
        "country": "FR",
    }


async def test_upsert_companies_dry_run_survives_siren_lookup_failure(monkeypatch):
    session = await _loaded_session()
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates",
        AsyncMock(side_effect=RuntimeError("timeout")),
    )

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Artelys")], confirm=False
    )

    assert result.results[0].status == "would_create"
    assert result.results[0].siren == ""


async def test_upsert_companies_dry_run_reports_matched():
    # "Acme Corp." (trailing period only) reliably scores >=85 against "Acme Corp"
    # under the existing plain token_sort_ratio matcher; "EDF SA" vs "EDF" does not
    # (~67), so it isn't a valid fixture for the >=85 threshold.
    session = await _loaded_session(existing_companies={"id-acme": "Acme Corp"})

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Acme Corp.")], confirm=False
    )

    assert result.results[0].status == "matched"
    assert result.results[0].matched_name == "Acme Corp"


async def test_upsert_companies_confirm_true_writes(monkeypatch):
    session = await _loaded_session()
    get_or_create_mock = AsyncMock(return_value="new-company-id")
    monkeypatch.setattr(session.company_syncer, "get_or_create", get_or_create_mock)
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.enrich_company", AsyncMock(return_value=CompanyEnrichment())
    )

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="OVHcloud")], confirm=True
    )

    get_or_create_mock.assert_awaited_once_with("OVHcloud")
    assert result.results[0].status == "created"
    assert result.results[0].page_id == "new-company-id"
    assert result.results[0].siren == ""


async def test_upsert_companies_confirm_true_writes_siren_and_registry_fallback(monkeypatch):
    session = await _loaded_session()
    monkeypatch.setattr(
        session.company_syncer, "get_or_create", AsyncMock(return_value="new-company-id")
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates",
        AsyncMock(
            return_value=[
                {
                    "siren": "428895676",
                    "matched_name": "ARTELYS",
                    "section_activite_principale": "M",
                    "activite_principale": "70.22Z",
                    "tranche_effectif_salarie": "12",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.enrich_company", AsyncMock(return_value=CompanyEnrichment())
    )
    ensure_siren_mock = AsyncMock()
    monkeypatch.setattr(session.company_syncer, "ensure_siren_property", ensure_siren_mock)
    update_mock = AsyncMock()
    monkeypatch.setattr(session.company_syncer._client.pages, "update", update_mock)

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Artelys")], confirm=True
    )

    ensure_siren_mock.assert_awaited_once()
    update_mock.assert_awaited_once_with(
        "new-company-id",
        properties={
            "SIREN": {"rich_text": [{"text": {"content": "428895676"}}]},
            "Sector": {"select": {"name": "Consulting"}},
            "Size": {"select": {"name": "11-50"}},
            "Country": {"select": {"name": "FR"}},
        },
    )
    assert result.results[0].siren == "428895676"


async def test_upsert_companies_confirm_true_prosper_enrichment_takes_priority_over_registry(
    monkeypatch,
):
    session = await _loaded_session()
    monkeypatch.setattr(
        session.company_syncer, "get_or_create", AsyncMock(return_value="new-company-id")
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates",
        AsyncMock(
            return_value=[
                {
                    "siren": "428895676",
                    "matched_name": "ARTELYS",
                    "section_activite_principale": "M",
                    "activite_principale": "70.22Z",
                    "tranche_effectif_salarie": "12",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.enrich_company",
        AsyncMock(return_value=CompanyEnrichment(sector="Research", size="1-10")),
    )
    monkeypatch.setattr(session.company_syncer, "ensure_siren_property", AsyncMock())
    update_mock = AsyncMock()
    monkeypatch.setattr(session.company_syncer._client.pages, "update", update_mock)

    await upsert_companies(session, _settings(), [CompanyRecord(name="Artelys")], confirm=True)

    props = update_mock.call_args.kwargs["properties"]
    assert (
        props["Sector"]["select"]["name"] == "Research"
    )  # prosper wins over the "Consulting" fallback
    assert props["Size"]["select"]["name"] == "1-10"


async def test_upsert_companies_confirm_true_domain_match_wins_without_calling_get_or_create(
    monkeypatch,
):
    # Regression test for the live-incident duplicate: a domain match (highest-precedence
    # dedup signal) must be authoritative on confirm=True, never falling through to
    # get_or_create's own separate, weaker name-only check. "Rte France" vs "RTE" scores
    # well below get_or_create's internal 85 threshold on name alone — if the dedup
    # signal's "matched" result were ignored, get_or_create would create a duplicate.
    session = await _loaded_session(existing_companies={"id-rte": "RTE"})
    session.company_syncer.details["id-rte"] = {"website": "https://www.rte-france.com"}
    get_or_create_mock = AsyncMock()
    monkeypatch.setattr(session.company_syncer, "get_or_create", get_or_create_mock)

    result = await upsert_companies(
        session,
        _settings(),
        [CompanyRecord(name="Rte France", contact_email="alice.martin@rte-france.com")],
        confirm=True,
    )

    get_or_create_mock.assert_not_called()
    assert result.results[0].status == "matched"
    assert result.results[0].page_id == "id-rte"


async def test_upsert_companies_confirm_true_skips_siren_for_matched_company(monkeypatch):
    session = await _loaded_session(existing_companies={"new-company-id": "Artelys"})
    monkeypatch.setattr(
        session.company_syncer, "get_or_create", AsyncMock(return_value="new-company-id")
    )
    siren_mock = AsyncMock()
    monkeypatch.setattr("notion_pilot.crm.syncer.lookup_siren_candidates", siren_mock)

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Artelys")], confirm=True
    )

    siren_mock.assert_not_called()
    assert result.results[0].status == "matched"
    assert result.results[0].siren == ""


async def test_upsert_companies_confirm_true_blocks_needs_review_without_force(monkeypatch):
    session = await _loaded_session(existing_companies={"id-rte": "RTE"})
    get_or_create_mock = AsyncMock()
    monkeypatch.setattr(session.company_syncer, "get_or_create", get_or_create_mock)

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Rte France")], confirm=True
    )

    get_or_create_mock.assert_not_called()
    assert result.results[0].status == "needs_review"
    assert result.results[0].candidates == [
        {"type": "notion", "page_id": "id-rte", "name": "RTE", "score": 100.0}
    ]


async def test_upsert_companies_confirm_true_force_bypasses_needs_review(monkeypatch):
    session = await _loaded_session(existing_companies={"id-rte": "RTE"})
    monkeypatch.setattr(
        session.company_syncer, "get_or_create", AsyncMock(return_value="new-company-id")
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.enrich_company", AsyncMock(return_value=CompanyEnrichment())
    )

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Rte France", force=True)], confirm=True
    )

    assert result.results[0].status == "created_with_override"
    assert result.results[0].page_id == "new-company-id"
    assert "RTE" in result.results[0].reason


async def test_upsert_companies_confirm_true_force_does_not_bypass_siren_confidence_gate(
    monkeypatch,
):
    # force=True only bypasses the needs_review *dedup* block. It must never cause a
    # low-confidence SIREN candidate to be written — that gate stays enforced regardless.
    session = await _loaded_session()
    monkeypatch.setattr(
        session.company_syncer, "get_or_create", AsyncMock(return_value="new-company-id")
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates",
        AsyncMock(return_value=[{"siren": "409526167", "matched_name": "VCSP ROUTE FRANCE"}]),
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.enrich_company", AsyncMock(return_value=CompanyEnrichment())
    )
    ensure_siren_mock = AsyncMock()
    monkeypatch.setattr(session.company_syncer, "ensure_siren_property", ensure_siren_mock)

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="OVHcloud", force=True)], confirm=True
    )

    ensure_siren_mock.assert_not_called()
    assert result.results[0].status == "created"  # no dedup needs_review was ever triggered here
    assert result.results[0].siren == ""


async def test_upsert_companies_confirm_true_force_bypasses_dedup_but_not_siren_gate(monkeypatch):
    # Combined scenario: force=True lets a needs_review dedup block through (status
    # becomes created_with_override), but a diverging SIREN candidate present at the
    # same time is still independently rejected by the SIREN confidence gate — force
    # must not bleed into that separate check.
    session = await _loaded_session(existing_companies={"id-rte": "RTE"})
    monkeypatch.setattr(
        session.company_syncer, "get_or_create", AsyncMock(return_value="new-company-id")
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates",
        AsyncMock(
            return_value=[
                {
                    "siren": "409526167",
                    "matched_name": "VCSP ROUTE FRANCE",
                    "section_activite_principale": "F",
                    "activite_principale": "42.11Z",
                    "tranche_effectif_salarie": "01",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.enrich_company", AsyncMock(return_value=CompanyEnrichment())
    )
    ensure_siren_mock = AsyncMock()
    monkeypatch.setattr(session.company_syncer, "ensure_siren_property", ensure_siren_mock)

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Rte France", force=True)], confirm=True
    )

    ensure_siren_mock.assert_not_called()
    assert result.results[0].status == "created_with_override"  # force bypassed the dedup block
    assert result.results[0].siren == ""  # SIREN gate still rejected the diverging candidate


async def test_upsert_companies_dry_run_flags_acronym_as_needs_review():
    # No lookup_siren mock needed — needs_review short-circuits _dedup_signal
    # before the SIREN block is ever reached.
    session = await _loaded_session(existing_companies={"id-rte": "RTE"})

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Rte France")], confirm=False
    )

    assert result.results[0].status == "needs_review"
    assert result.results[0].candidates == [
        {"type": "notion", "page_id": "id-rte", "name": "RTE", "score": 100.0}
    ]


async def test_upsert_companies_dry_run_domain_match_wins_over_needs_review():
    # No lookup_siren mock needed — a domain match returns "matched" before the
    # SIREN block is ever reached.
    session = await _loaded_session(existing_companies={"id-rte": "RTE"})
    session.company_syncer.details["id-rte"] = {"website": "https://www.rte-france.com"}

    result = await upsert_companies(
        session,
        _settings(),
        [CompanyRecord(name="Rte France", contact_email="alice.martin@rte-france.com")],
        confirm=False,
    )

    assert result.results[0].status == "matched"
    assert result.results[0].matched_name == "RTE"


async def test_upsert_companies_dry_run_partial_word_overlap_is_not_flagged(monkeypatch):
    # "EDF Renouvelables" vs "EDF Trading" share the word "EDF" but neither name's
    # full token set is contained in the other's (unlike "RTE" vs "Rte France", where
    # "RTE" alone is 100% of a token in "Rte France"). Verified: token_set_ratio == 42.9,
    # well below the 90 needs_review floor. IMPORTANT: any single-token name that is a
    # complete subset of a longer name's tokens ALWAYS scores 100 on token_set_ratio,
    # no matter how many extra distinguishing words the longer name has — e.g. "EDF" vs
    # "EDF Trading" also scores 100, and DOES get flagged needs_review by this chain.
    # That's an accepted, deliberate trade-off: favor an extra human review over silently
    # creating a duplicate. Don't pick a single-token vs. multi-word-containing-that-token
    # pair for this "not flagged" test — it will score 100 and contradict the acronym test.
    session = await _loaded_session(existing_companies={"id-edf-r": "EDF Renouvelables"})
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates", AsyncMock(return_value=[])
    )

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="EDF Trading")], confirm=False
    )

    assert result.results[0].status == "would_create"


async def test_upsert_companies_dry_run_flags_diverging_siren_as_needs_review(monkeypatch):
    session = await _loaded_session()
    monkeypatch.setattr(
        "notion_pilot.crm.syncer.lookup_siren_candidates",
        AsyncMock(
            return_value=[
                {
                    "siren": "409526167",
                    "matched_name": "VCSP ROUTE FRANCE",
                    "section_activite_principale": "F",
                    "activite_principale": "42.11Z",
                    "tranche_effectif_salarie": "01",
                }
            ]
        ),
    )

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Rte France")], confirm=False
    )

    assert result.results[0].status == "needs_review"
    assert result.results[0].siren == ""
    assert result.results[0].candidates == [
        {
            "type": "siren",
            "siren": "409526167",
            "matched_name": "VCSP ROUTE FRANCE",
            "score": 74.07407407407408,
        }
    ]


async def test_upsert_companies_dry_run_isolates_preview_failure_per_record(monkeypatch):
    # New coverage: an unexpected exception in preview() must degrade only
    # this one record to status="error", not crash the whole dry-run batch —
    # mirrors the existing confirm=True isolation test
    # (test_upsert_people_batch_continues_after_one_error) for the preview path.
    session = await _loaded_session()
    preview_mock = AsyncMock(side_effect=RuntimeError("unexpected syncer failure"))
    monkeypatch.setattr(session.company_syncer, "preview", preview_mock)

    result = await upsert_companies(
        session, _settings(), [CompanyRecord(name="Broken Co")], confirm=False
    )

    assert result.results[0].status == "error"
    assert "unexpected syncer failure" in result.results[0].error_message


async def test_upsert_people_dry_run_matches_by_email_despite_name_mismatch():
    session = await _loaded_session(
        existing_people=[
            {
                "name": "A. Martin",
                "company": "RTE",
                "page_id": "p1",
                "email": "alice.martin@rte-france.com",
            }
        ]
    )

    result = await upsert_people(
        session,
        [
            PersonRecord(
                name="MARTIN Alice", company="Rte France", email="alice.martin@rte-france.com"
            )
        ],
        confirm=False,
    )

    assert result.results[0].status == "would_skip"
    assert result.results[0].matched_name == "A. Martin"
