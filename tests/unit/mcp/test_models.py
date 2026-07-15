"""Unit tests for mcp/models.py — pure data, no I/O."""

from notion_pilot.mcp.models import BatchResult, PersonRecord, RecordResult, summarize


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
