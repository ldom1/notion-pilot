"""Unit tests for process_email helpers."""


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
