"""Unit tests for crm/recap.py."""

from unittest.mock import AsyncMock, patch
import pytest

from notion_pilot.crm.recap import (
    format_leads,
    format_inbox,
    format_recap,
    CAP_LEADS,
    CAP_INBOX,
    CAP_RECAP_SECTION,
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


@pytest.mark.asyncio
async def test_get_recent_people_uses_databases_api():
    """Ensure get_recent_people calls databases.query, not data_sources.query."""
    from notion_pilot.crm.queries import get_recent_people
    from notion_pilot.shared.config import Settings

    settings = Settings(
        notion_token="secret_test",
        notion_telegram_msg_database_id="db-id",
        notion_people_data_source_id="people-db-id",
    )

    mock_response = {
        "results": [
            {
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Alice"}]},
                    "Company": {"type": "rich_text", "rich_text": [{"plain_text": "Acme"}]},
                }
            }
        ]
    }

    with patch("notion_pilot.crm.queries.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.databases.query = AsyncMock(return_value=mock_response)
        mock_client.data_sources.query = AsyncMock(side_effect=AssertionError("must not call data_sources"))

        result = await get_recent_people(settings)

    assert result == [{"name": "Alice", "company": "Acme"}]
    mock_client.databases.query.assert_awaited_once()
