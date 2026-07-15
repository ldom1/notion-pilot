"""Unit tests for mcp/models.py — pure data, no I/O."""

from notion_pilot.mcp.models import BatchResult, CompanyRecord, PersonRecord, RecordResult, summarize


def test_person_record_requires_name_and_company():
    record = PersonRecord(name="Jean Dupont", company="EDF")
    assert record.position is None
    assert record.role_type is None


def test_summarize_counts_by_status():
    results = [
        RecordResult(name="A", status="created"),
        RecordResult(name="B", status="created"),
        RecordResult(name="C", status="skipped", matched_name="A"),
        RecordResult(name="D", status="error", error_message="timeout"),
    ]
    batch = summarize(results)
    assert isinstance(batch, BatchResult)
    assert batch.success_count == 3
    assert batch.fail_count == 1
    assert batch.summary == {"created": 2, "skipped": 1, "error": 1}
    assert batch.results == results


def test_summarize_empty_list():
    batch = summarize([])
    assert batch.success_count == 0
    assert batch.fail_count == 0
    assert batch.summary == {}
    assert batch.results == []


def test_person_record_defaults_force_false():
    record = PersonRecord(name="Jean Dupont", company="EDF")
    assert record.force is False


def test_company_record_accepts_contact_email_and_force():
    record = CompanyRecord(name="RTE", contact_email="alice.martin@rte-france.com", force=True)
    assert record.contact_email == "alice.martin@rte-france.com"
    assert record.force is True


def test_record_result_new_fields_default_empty():
    result = RecordResult(name="RTE", status="needs_review")
    assert result.siren_candidate_name == ""
    assert result.reason == ""
    assert result.candidates == []
    assert result.enrichment_preview == {}


def test_record_result_candidates_and_enrichment_preview_are_independent_per_instance():
    a = RecordResult(name="A", status="needs_review")
    b = RecordResult(name="B", status="needs_review")
    a.candidates.append({"type": "notion", "page_id": "p1", "name": "RTE", "score": 100.0})
    a.enrichment_preview["siren"] = "444619258"
    assert b.candidates == []
    assert b.enrichment_preview == {}
