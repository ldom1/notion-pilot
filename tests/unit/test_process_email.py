"""Unit tests for process_email helpers."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest


def _settings() -> SimpleNamespace:
    token = MagicMock()
    token.get_secret_value.return_value = "notion-token"
    return SimpleNamespace(
        notion_token=token,
        notion_people_data_source_id="people-ds",
        notion_telegram_msg_database_id="db",
        imap_promotions_folder="Promotions",
        imap_inbox="INBOX",
        imap_since_days=7,
    )


class TestParseInboxArg:
    def test_single_folder(self):
        from scripts.inbox.process_email import _parse_inbox_arg

        assert _parse_inbox_arg("INBOX") == ["INBOX"]

    def test_multiple_folders(self):
        from scripts.inbox.process_email import _parse_inbox_arg

        assert _parse_inbox_arg("INBOX,Promotions") == ["INBOX", "Promotions"]

    def test_strips_whitespace(self):
        from scripts.inbox.process_email import _parse_inbox_arg

        assert _parse_inbox_arg("INBOX, Promotions") == ["INBOX", "Promotions"]

    def test_empty_string_returns_empty(self):
        from scripts.inbox.process_email import _parse_inbox_arg

        assert _parse_inbox_arg("") == []


class TestApplyReviewSurvivesEnrichmentFailure:
    """--apply-review upserts a human-approved person even when enrichment raises.

    Regression guard for the resilience regression identified in the whole-branch
    review: notion_pilot.shared.prosper_client.enrich_person no longer swallows its
    own exceptions (unlike the deleted enrichment.py cascade), so process_email.py
    must catch failures at the call site instead — matching the pattern already
    used in scripts/crm/crm_import_linkedin.py.
    """

    @pytest.mark.asyncio
    async def test_upsert_completes_when_enrich_person_raises(self):
        from scripts.inbox.process_email import _apply_review

        review_df = pd.DataFrame(
            [
                {
                    "email": "bob@corp.com",
                    "display_name": "Bob Corp",
                    "domain": "corp.com",
                    "folder": "Promotions",
                    "people_list": "yes",
                    "enriched": "",
                    "linkedin": "",
                    "seniority": "",
                    "role_type": "",
                    "dedup_status": "",
                    "dedup_score": "",
                    "matched_name": "",
                    "decision": "people",
                }
            ]
        )

        people_syncer = AsyncMock()
        people_syncer.upsert.return_value = SimpleNamespace(
            status="created", score=0.0, matched_name="", matched_company="", page_id="p1"
        )

        sender_config_path = MagicMock()
        sender_config_path.exists.return_value = True
        sender_config_path.read_text.return_value = "allowed: []\nauto_archive: []\npeople: []\n"

        people_review_path = MagicMock()
        people_review_path.exists.return_value = True

        with (
            patch("scripts.inbox.process_email._PEOPLE_REVIEW_CSV", people_review_path),
            patch("scripts.inbox.process_email._SENDER_CONFIG", sender_config_path),
            patch("scripts.inbox.process_email._yaml_append_to_section"),
            patch("yaml.safe_load", return_value={"allowed": [], "auto_archive": [], "people": []}),
            patch("pandas.read_csv", return_value=review_df),
            patch("scripts.inbox.process_email.load_settings", return_value=_settings()),
            patch(
                "scripts.inbox.process_email._build_people_syncer",
                new=AsyncMock(return_value=people_syncer),
            ),
            patch(
                "scripts.inbox.process_email.enrich_person",
                new=AsyncMock(side_effect=RuntimeError("prosper unreachable")),
            ),
        ):
            await _apply_review()

        people_syncer.upsert.assert_awaited_once()
        written_person = people_syncer.upsert.await_args.args[0]
        assert written_person.name == "Bob Corp"
        assert written_person.email == "bob@corp.com"
        assert written_person.company == "corp.com"
        assert written_person.linkedin_url == ""
        assert written_person.position == ""


class TestRunPeopleCandidatesSurviveEnrichmentFailure:
    """The main email-processing loop still upserts a people-list sender to Notion
    even when enrich_person raises — enrichment is supplementary, the write is not."""

    @pytest.mark.asyncio
    async def test_upsert_completes_when_enrich_person_raises(self):
        from scripts.inbox.process_email import run

        raw = SimpleNamespace(
            uid=1,
            sender="alice@risky.com",
            subject="Hello",
            body="Some email body",
            sent_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        adapter = MagicMock()
        adapter.fetch_messages.return_value = [raw]

        people_syncer = AsyncMock()
        people_syncer.upsert.return_value = SimpleNamespace(
            status="created", score=0.0, matched_name="", matched_company="", page_id="p1"
        )

        with (
            patch("scripts.inbox.process_email.load_settings", return_value=_settings()),
            patch("scripts.inbox.process_email.EmailAdapter", return_value=adapter),
            patch(
                "scripts.inbox.process_email._load_sender_config",
                return_value=(["someone-else@example.com"], [], ["alice@risky.com"]),
            ),
            patch(
                "scripts.inbox.process_email._load_notion_keys",
                new=AsyncMock(return_value=(set(), set())),
            ),
            patch("scripts.inbox.process_email.build_knowledge_pipeline", return_value=AsyncMock()),
            patch(
                "scripts.inbox.process_email._build_people_syncer",
                new=AsyncMock(return_value=people_syncer),
            ),
            patch(
                "scripts.inbox.process_email.enrich_person",
                new=AsyncMock(side_effect=RuntimeError("prosper unreachable")),
            ),
            patch("scripts.inbox.process_email._write_people_csv"),
            patch("scripts.inbox.process_email._write_review_csv"),
        ):
            await run(dry_run=False, from_csv=False, since_days=0, limit=0, inbox=["Promotions"])

        people_syncer.upsert.assert_awaited_once()
        written_person = people_syncer.upsert.await_args.args[0]
        assert written_person.name == "Alice"
        assert written_person.email == "alice@risky.com"
        assert written_person.linkedin_url == ""
        assert written_person.seniority == ""
        assert written_person.role_type == []
