"""Unit tests for promotions CSV helpers."""

from scripts.inbox.process_promotions import _csv_requests_process, _one_sentence


def test_strips_css_and_prefers_subject():
    body = "@media only screen { .x { width: 1px; } } Short."
    assert _one_sentence("Real subject line here for review", body) == "Real subject line here for review"


def test_picks_first_good_body_sentence():
    body = "https://app.example.com/\n Hi, ignored.\n This is a proper summary sentence here."
    assert _one_sentence("Short", body) == "This is a proper summary sentence here."


def test_csv_process_decision_values():
    assert _csv_requests_process("Treated and archived")
    assert _csv_requests_process("process")
    assert not _csv_requests_process("Untouched")
    assert not _csv_requests_process("Auto archived")
    assert not _csv_requests_process("")
