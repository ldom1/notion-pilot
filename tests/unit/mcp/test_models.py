"""Unit tests for mcp/models.py — pure data, no I/O."""

import pytest
from pydantic import ValidationError

from notion_pilot.mcp.models import (
    ActivityInput,
    BatchResult,
    CompanyRecord,
    DealInput,
    PersonRecord,
    RecordResult,
    summarize,
)


def test_person_record_requires_name_and_company():
    record = PersonRecord(name="Jean Dupont", company="EDF")
    assert record.position is None
    assert record.role_type is None


@pytest.mark.parametrize("bad_name", ["", "   "])
def test_person_record_rejects_blank_name(bad_name):
    with pytest.raises(ValidationError):
        PersonRecord(name=bad_name, company="EDF")


@pytest.mark.parametrize("bad_company", ["", "   "])
def test_person_record_rejects_blank_company(bad_company):
    with pytest.raises(ValidationError):
        PersonRecord(name="Jean Dupont", company=bad_company)


def test_person_record_strips_surrounding_whitespace():
    record = PersonRecord(name="  Jean Dupont  ", company=" EDF ")
    assert record.name == "Jean Dupont"
    assert record.company == "EDF"


def test_company_record_rejects_blank_name():
    with pytest.raises(ValidationError):
        CompanyRecord(name="")


def test_person_record_linkedin_url_optional_but_non_empty_if_given():
    assert PersonRecord(name="Jean Dupont", company="EDF").linkedin_url is None
    with pytest.raises(ValidationError):
        PersonRecord(name="Jean Dupont", company="EDF", linkedin_url="")


@pytest.mark.parametrize("field", ["website", "linkedin_url", "country", "sector"])
def test_company_record_optional_but_non_empty_if_given(field):
    assert getattr(CompanyRecord(name="EDF"), field) is None
    with pytest.raises(ValidationError):
        CompanyRecord(name="EDF", **{field: ""})


def test_company_record_size_and_contact_email_still_accept_empty_string():
    """Unlike the fields above, these weren't flagged for the non-empty
    constraint — behavior must stay unchanged (empty string still valid)."""
    record = CompanyRecord(name="EDF", size="", contact_email="")
    assert record.size == ""
    assert record.contact_email == ""


def test_deal_input_requires_name_defaults_confirm_false():
    deal = DealInput(name="New Deal")
    assert deal.stage is None
    assert deal.confirm is False
    with pytest.raises(ValidationError):
        DealInput(name="")


@pytest.mark.parametrize(
    "field",
    [
        "stage",
        "lead_source",
        "company_name",
        "contact_page_id",
        "primary_contact_page_id",
        "expected_close_date",
        "next_step_date",
    ],
)
def test_deal_input_optional_but_non_empty_if_given(field):
    assert getattr(DealInput(name="New Deal"), field) is None
    with pytest.raises(ValidationError):
        DealInput(name="New Deal", **{field: ""})


def test_activity_input_requires_type_defaults_confirm_false():
    activity = ActivityInput(type="📞 Call")
    assert activity.title is None
    assert activity.confirm is False
    with pytest.raises(ValidationError):
        ActivityInput(type="")


@pytest.mark.parametrize(
    "field",
    [
        "title",
        "outcome",
        "deal_page_id",
        "person_page_id",
        "company_page_id",
        "date",
        "next_step_date",
    ],
)
def test_activity_input_optional_but_non_empty_if_given(field):
    assert getattr(ActivityInput(type="📞 Call"), field) is None
    with pytest.raises(ValidationError):
        ActivityInput(type="📞 Call", **{field: ""})


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
