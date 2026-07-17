"""Unit tests for crm/recap.py."""

from notion_pilot.crm.recap import (
    CAP_INBOX,
    CAP_LEADS,
    CAP_RECAP_SECTION,
    format_inbox,
    format_leads,
    format_recap,
)


def _make_leads(n: int) -> list[dict]:
    return [
        {"title": f"Deal {i}", "stage": "Prospect", "next_action": f"Action {i}"} for i in range(n)
    ]


def _make_inbox(n: int) -> list[dict]:
    return [{"title": f"Item {i}"} for i in range(n)]


def _make_people(n: int) -> list[dict]:
    return [{"name": f"Person {i}", "company": f"Co {i}"} for i in range(n)]


def test_format_leads_within_cap():
    result = format_leads(_make_leads(3))
    assert "Deal 0" in result
    assert "Prospect" in result
    assert "and" not in result  # no overflow


def test_format_leads_overflow():
    result = format_leads(_make_leads(CAP_LEADS + 5))
    assert "…and 5 more" in result


def test_format_leads_empty():
    assert "no open leads" in format_leads([]).lower()


def test_format_inbox_overflow():
    result = format_inbox(_make_inbox(CAP_INBOX + 3))
    assert "…and 3 more" in result


def test_format_inbox_empty():
    assert "nothing" in format_inbox([]).lower()


def test_format_recap_has_all_sections():
    result = format_recap(
        leads=_make_leads(2),
        people=_make_people(1),
        inbox=_make_inbox(2),
    )
    assert "leads" in result.lower()
    assert "people" in result.lower()
    assert "à relire" in result.lower()


def test_format_recap_next_actions_shown():
    leads = [{"title": "Big Deal", "stage": "Proposal", "next_action": "Send quote"}]
    result = format_recap(leads=leads, people=[], inbox=[])
    assert "Send quote" in result


def test_format_recap_section_capped():
    result = format_recap(leads=_make_leads(10), people=[], inbox=[])
    # Should only show CAP_RECAP_SECTION leads (5) + overflow
    assert f"…and {10 - CAP_RECAP_SECTION} more" in result
