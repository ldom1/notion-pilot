"""Unit tests for process_email helpers."""


class TestIsAutomated:
    def test_noreply_blocked(self):
        from scripts.inbox.process_email import _is_automated
        assert _is_automated("noreply@company.com")
        assert _is_automated("no-reply@service.com")

    def test_donotreply_blocked(self):
        from scripts.inbox.process_email import _is_automated
        assert _is_automated("donotreply@company.com")
        assert _is_automated("do-not-reply@company.com")

    def test_support_info_postmaster_blocked(self):
        from scripts.inbox.process_email import _is_automated
        assert _is_automated("support@company.com")
        assert _is_automated("info@newsletter.com")
        assert _is_automated("postmaster@domain.com")
        assert _is_automated("bounce@service.com")
        assert _is_automated("mailer-daemon@mail.com")

    def test_normal_person_allowed(self):
        from scripts.inbox.process_email import _is_automated
        assert not _is_automated("alice.smith@gmail.com")
        assert not _is_automated("john@company.com")
        assert not _is_automated("bob.jones@custom-domain.com")


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
