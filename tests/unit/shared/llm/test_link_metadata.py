"""Unit tests for shared/llm/link_metadata.py — no live network."""

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from loguru import logger as _loguru_logger

from notion_pilot.shared.llm.link_metadata import fetch_link_metadata


class _PropagateHandler(logging.Handler):
    """Bridges loguru records into stdlib `logging` so pytest's `caplog`
    fixture can see them — loguru doesn't propagate to stdlib logging by
    default, and this repo has no such bridge configured globally."""

    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger(record.name).handle(record)


@pytest.fixture(autouse=True)
def _propagate_loguru_to_caplog():
    handler_id = _loguru_logger.add(_PropagateHandler(), format="{message}")
    yield
    _loguru_logger.remove(handler_id)


def _github_response(description: str, stars: int = 10, language: str = "Python") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "description": description,
            "stargazers_count": stars,
            "language": language,
            "topics": ["scraping"],
        },
        request=httpx.Request("GET", "https://api.github.com/repos/example-org/repo-a"),
    )


def _html_response(title: str, description: str) -> httpx.Response:
    body = (
        f'<html><head><meta property="og:title" content="{title}">'
        f'<meta property="og:description" content="{description}"></head></html>'
    )
    return httpx.Response(
        200,
        content=body.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        request=httpx.Request("GET", "https://example.com/page"),
    )


@pytest.mark.asyncio
async def test_fetch_github_url_returns_repo_metadata():
    with patch("notion_pilot.shared.llm.link_metadata.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(
            return_value=_github_response("A great scraping tool", stars=42)
        )
        mock_cls.return_value = mock_client

        results = await fetch_link_metadata(["https://github.com/example-org/repo-a"])

    assert len(results) == 1
    assert results[0].description == "A great scraping tool"
    assert results[0].extra["stars"] == "42"
    assert results[0].error == ""


class _StreamCM:
    """Fake async context manager standing in for httpx.AsyncClient.stream()."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    async def __aenter__(self) -> httpx.Response:
        return self._response

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _stream_sequence(responses: list[httpx.Response]):
    """Return a stream() stub that yields each response in order across calls
    (one call per redirect hop)."""
    remaining = list(responses)

    def _stream(method, url, **kwargs):
        return _StreamCM(remaining.pop(0))

    return _stream


@pytest.mark.asyncio
async def test_fetch_generic_url_parses_og_tags():
    with patch("notion_pilot.shared.llm.link_metadata.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = _stream_sequence([_html_response("Example Page", "A cool page")])
        mock_cls.return_value = mock_client

        with patch("notion_pilot.shared.llm.link_metadata._resolve_is_safe", return_value=True):
            results = await fetch_link_metadata(["https://example.com/page"])

    assert results[0].title == "Example Page"
    assert results[0].description == "A cool page"


@pytest.mark.asyncio
async def test_fetch_generic_rejects_non_200_status():
    # Regression guard: a dead/moved link serving a 404 error page as text/html must not
    # have that error page's <title>/description treated as real, successfully-fetched
    # link metadata.
    with patch("notion_pilot.shared.llm.link_metadata.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        not_found = httpx.Response(
            404,
            content=b"<html><head><title>404 Not Found</title></head></html>",
            headers={"content-type": "text/html"},
            request=httpx.Request("GET", "https://example.com/gone"),
        )
        mock_client.stream = _stream_sequence([not_found])
        mock_cls.return_value = mock_client

        with patch("notion_pilot.shared.llm.link_metadata._resolve_is_safe", return_value=True):
            results = await fetch_link_metadata(["https://example.com/gone"])

    assert results[0].error == "fetch_failed"
    assert results[0].title == ""


@pytest.mark.asyncio
async def test_fetch_github_rate_limit_logs_distinct_warning(caplog):
    with patch("notion_pilot.shared.llm.link_metadata.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(
            return_value=httpx.Response(
                403,
                json={"message": "rate limit exceeded"},
                request=httpx.Request("GET", "https://api.github.com/repos/example-org/repo-a"),
            )
        )
        mock_cls.return_value = mock_client

        results = await fetch_link_metadata(["https://github.com/example-org/repo-a"])

    assert results[0].error == "rate_limited"
    assert any("rate" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_fetch_www_github_url_still_uses_github_api():
    # Regression guard: matching the GitHub-repo regex against a concatenated
    # "hostname + path" string (e.g. "www.github.com/owner/repo") never
    # matches, since the pattern starts with "github.com/" not "www.github.com/"
    # — despite www.github.com being explicitly allow-listed. If this
    # regresses, the call below silently falls through to _fetch_generic
    # (which would try — and fail — to resolve/stream from api.github.com
    # never being called, and _resolve_is_safe never being patched here).
    with patch("notion_pilot.shared.llm.link_metadata.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=_github_response("A great scraping tool"))
        mock_cls.return_value = mock_client

        results = await fetch_link_metadata(["https://www.github.com/example-org/repo-a"])

    mock_client.get.assert_awaited_once_with("https://api.github.com/repos/example-org/repo-a")
    assert results[0].description == "A great scraping tool"
    assert results[0].error == ""


@pytest.mark.asyncio
async def test_fetch_rejects_oversized_response():
    with patch("notion_pilot.shared.llm.link_metadata.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        big_body = b"<html>" + (b"x" * (3 * 1024 * 1024)) + b"</html>"
        mock_client.stream = _stream_sequence(
            [
                httpx.Response(
                    200,
                    content=big_body,
                    headers={"content-type": "text/html"},
                    request=httpx.Request("GET", "https://example.com/big"),
                )
            ]
        )
        mock_cls.return_value = mock_client

        with patch("notion_pilot.shared.llm.link_metadata._resolve_is_safe", return_value=True):
            results = await fetch_link_metadata(["https://example.com/big"])

    assert results[0].error == "response_too_large"


@pytest.mark.asyncio
async def test_fetch_rejects_non_html_content_type():
    with patch("notion_pilot.shared.llm.link_metadata.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = _stream_sequence(
            [
                httpx.Response(
                    200,
                    content=b"%PDF-1.4 ...",
                    headers={"content-type": "application/pdf"},
                    request=httpx.Request("GET", "https://example.com/file.pdf"),
                )
            ]
        )
        mock_cls.return_value = mock_client

        with patch("notion_pilot.shared.llm.link_metadata._resolve_is_safe", return_value=True):
            results = await fetch_link_metadata(["https://example.com/file.pdf"])

    assert results[0].error == "unsupported_content_type"


@pytest.mark.asyncio
async def test_fetch_rejects_private_ip_destination():
    with patch("notion_pilot.shared.llm.link_metadata._resolve_is_safe", return_value=False):
        results = await fetch_link_metadata(["http://169.254.169.254/latest/meta-data/"])

    assert results[0].error == "unsafe_destination"


@pytest.mark.asyncio
async def test_fetch_rejects_redirect_to_private_ip_on_second_hop():
    """The original URL's host resolves safely, but it 302-redirects to a
    second host that resolves to a private/link-local IP. The second hop must
    be rejected BEFORE that request is ever sent, not just detected after."""
    with patch("notion_pilot.shared.llm.link_metadata.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        redirect_response = httpx.Response(
            302,
            headers={"location": "http://169.254.169.254/latest/meta-data/"},
            request=httpx.Request("GET", "https://example.com/redirector"),
        )
        # Only ONE response is ever queued — if the code tried to fetch the
        # second (unsafe) hop, _stream_sequence would raise IndexError on an
        # empty list, failing the test loudly instead of silently passing.
        mock_client.stream = _stream_sequence([redirect_response])
        mock_cls.return_value = mock_client

        def _safe_first_hop_only(hostname: str) -> bool:
            return hostname == "example.com"

        with patch(
            "notion_pilot.shared.llm.link_metadata._resolve_is_safe",
            side_effect=_safe_first_hop_only,
        ):
            results = await fetch_link_metadata(["https://example.com/redirector"])

    assert results[0].error == "unsafe_destination"


@pytest.mark.asyncio
async def test_fetch_tolerates_individual_failure_without_raising():
    with patch("notion_pilot.shared.llm.link_metadata.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        def _raise_stream(method, url, **kwargs):
            raise httpx.ConnectTimeout("timeout")

        mock_client.stream = _raise_stream
        mock_cls.return_value = mock_client

        with patch("notion_pilot.shared.llm.link_metadata._resolve_is_safe", return_value=True):
            results = await fetch_link_metadata(["https://slow.example.com/"])

    assert results[0].error == "fetch_failed"
