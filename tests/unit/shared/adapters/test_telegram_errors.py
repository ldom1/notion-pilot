"""Unit tests for telegram.py's sanitized CRM error-message formatting."""

import httpx
from notion_client.errors import APIResponseError


def test_format_handler_error_shows_class_name_for_plain_exception():
    from notion_pilot.shared.adapters.telegram import _format_handler_error

    msg = _format_handler_error(ValueError("Company relation target not configured"))
    assert msg.startswith("⚠ Failed to save to Notion: ValueError")
    assert "Company relation target not configured" in msg


def test_format_handler_error_caps_plain_exception_message_length():
    from notion_pilot.shared.adapters.telegram import _format_handler_error

    long_message = "x" * 500
    msg = _format_handler_error(ValueError(long_message))
    assert len(msg) < 200  # class name + prefix + capped message, well under the raw 500 chars
    assert "..." in msg or msg.count("x") <= 120


def test_format_handler_error_hides_raw_notion_sdk_message():
    from notion_pilot.shared.adapters.telegram import _format_handler_error

    # Real APIResponseError signature (verified against the installed notion_client
    # package): __init__(self, code, status, message, headers, raw_body_text,
    # additional_data=None, request_id=None) — NOT (response, message, code=...).
    exc = APIResponseError(
        code="validation_error",
        status=400,
        message="page_id abc-123-def in database xyz-789 is not shared",
        headers=httpx.Headers({}),
        raw_body_text="{}",
    )
    msg = _format_handler_error(exc)
    assert "abc-123-def" not in msg
    assert "xyz-789" not in msg
    assert "APIResponseError" in msg
    assert "Notion API error" in msg


def test_format_handler_error_hides_other_notion_client_exception_types_too():
    # Regression guard: NotionClientErrorBase, not just APIResponseError, is
    # the real base class — a timeout from the SDK must get the same generic
    # treatment, not fall through to the "plain exception" branch and leak
    # its raw message.
    from notion_client.errors import RequestTimeoutError

    from notion_pilot.shared.adapters.telegram import _format_handler_error

    exc = RequestTimeoutError("timed out calling https://api.notion.com/v1/pages/abc-123-def")
    msg = _format_handler_error(exc)
    assert "abc-123-def" not in msg
    assert "RequestTimeoutError" in msg
    assert "Notion API error" in msg
