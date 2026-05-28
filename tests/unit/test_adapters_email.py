"""Unit tests for email adapter helpers — no network, no IMAP connection."""

import email as email_lib

import pytest

pytest.importorskip("imapclient")
from telegram_to_notion.adapters.email import _decode_str, _plain_body, _sender_allowed


class TestSenderAllowed:
    def test_domain_suffix_match(self):
        allowed = ["@tldr.tech", "@medium.com"]
        assert _sender_allowed("newsletter@tldr.tech", allowed)
        assert _sender_allowed("weekly@medium.com", allowed)

    def test_full_address_match(self):
        assert _sender_allowed("news@example.com", ["news@example.com"])

    def test_unknown_sender_rejected(self):
        assert not _sender_allowed("spam@other.com", ["@tldr.tech"])

    def test_partial_domain_not_matched(self):
        # "notmedium.com" should not match "@medium.com"
        assert not _sender_allowed("fake@notmedium.com", ["@medium.com"])

    def test_empty_allowlist_rejects_all(self):
        assert not _sender_allowed("anyone@example.com", [])

    def test_case_insensitive(self):
        assert _sender_allowed("User@TLDR.TECH", ["@tldr.tech"])


class TestDecodeStr:
    def test_plain_string_unchanged(self):
        assert _decode_str("Hello World") == "Hello World"

    def test_empty_string(self):
        assert _decode_str("") == ""

    def test_rfc2047_base64_encoded_header(self):
        # "Hello" encoded as =?utf-8?b?SGVsbG8=?=
        assert _decode_str("=?utf-8?b?SGVsbG8=?=") == "Hello"


class TestPlainBody:
    def test_simple_text_message(self):
        raw = (
            "From: sender@example.com\r\n"
            "Subject: Test\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n\r\n"
            "Hello, world!\r\n"
        )
        msg = email_lib.message_from_string(raw)
        assert "Hello, world!" in _plain_body(msg)

    def test_html_only_returns_empty(self):
        raw = (
            "From: sender@example.com\r\n"
            "Content-Type: text/html; charset=utf-8\r\n\r\n"
            "<html><body>Hi</body></html>\r\n"
        )
        msg = email_lib.message_from_string(raw)
        assert _plain_body(msg) == ""
