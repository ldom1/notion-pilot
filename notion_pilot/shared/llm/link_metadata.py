"""Fetch factual metadata for URLs found in a Telegram message — GitHub API for
github.com repos, generic og:title/og:description scraping otherwise. Every
fetch is tolerant of individual failure and destination-safety-checked before
any request is sent (SSRF guard)."""

import asyncio
import ipaddress
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from loguru import logger

# Matched against parsed.path alone (hostname is validated separately in
# fetch_link_metadata) — matching "github.com/owner/repo" against the
# concatenated "hostname + path" string would silently fail to match
# "www.github.com/owner/repo" (starts with "www.", not "github.com"),
# letting www.github.com URLs fall through to the generic fetch path
# despite being explicitly allow-listed.
_GITHUB_REPO_PATH_RE = re.compile(r"^/([^/]+)/([^/?#]+)/?$", re.IGNORECASE)
_OG_TITLE_RE = re.compile(
    r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']*)["\']', re.IGNORECASE
)
_OG_DESC_RE = re.compile(
    r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']*)["\']', re.IGNORECASE
)
_TITLE_TAG_RE = re.compile(r"<title>([^<]*)</title>", re.IGNORECASE)

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2MB
_MAX_REDIRECTS = 3
_FETCH_TIMEOUT_S = 8.0
_CONCURRENCY_LIMIT = 3


@dataclass
class LinkMetadata:
    url: str
    title: str = field(default="")
    description: str = field(default="")
    extra: dict[str, str] = field(default_factory=dict)
    error: str = field(default="")


async def _resolve_is_safe(hostname: str) -> bool:
    """Resolve hostname and reject if any address is private/loopback/link-local/reserved.

    Uses the asyncio event loop's non-blocking resolver — a plain, synchronous
    socket.getaddrinfo() call would block the entire single-threaded event
    loop for the DNS round-trip on every fetched URL, defeating the point of
    the concurrency semaphore this module otherwise uses."""
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None)
    except OSError:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


async def _fetch_github(owner: str, repo: str) -> LinkMetadata:
    url = f"https://github.com/{owner}/{repo}"
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_S) as client:
            resp = await client.get(api_url)
    except httpx.HTTPError as exc:
        logger.warning("link_metadata: GitHub fetch failed for {}: {}", url, exc)
        return LinkMetadata(url=url, error="fetch_failed")

    if resp.status_code in (403, 429):
        logger.warning(
            "link_metadata: GitHub API rate-limited fetching {} (status {})", url, resp.status_code
        )
        return LinkMetadata(url=url, error="rate_limited")
    if resp.status_code != 200:
        return LinkMetadata(url=url, error="fetch_failed")

    data = resp.json()
    return LinkMetadata(
        url=url,
        title=f"{owner}/{repo}",
        description=data.get("description") or "",
        extra={
            "stars": str(data.get("stargazers_count", "")),
            "language": data.get("language") or "",
            "topics": ", ".join(data.get("topics") or []),
        },
    )


async def _fetch_generic(url: str) -> LinkMetadata:
    """Manual redirect loop (httpx's automatic follow_redirects is NOT used
    here) — this re-runs the destination-safety check before EVERY hop,
    including redirect targets. Using follow_redirects=True would let httpx
    send the request to an unsafe redirect target before we ever get a chance
    to inspect it; a hostname that resolves safely can still redirect
    somewhere private, so each hop must be checked before it is fetched, not
    after the whole chain has already completed.

    Known accepted limitation: this closes the redirect-to-private-IP gap but
    not classic DNS-rebinding (a TOCTOU where the same hostname resolves
    differently between this check and the actual connection httpx makes
    a moment later). Closing that fully would require pinning the resolved IP
    and connecting to it directly rather than re-resolving by hostname — a
    deeper hardening step not required for this iteration's threat model
    (Telegram-supplied URLs from a small trusted user base, not adversarial
    mass input)."""
    current_url = url
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_S, follow_redirects=False) as client:
        for _hop in range(_MAX_REDIRECTS + 1):
            parsed = urlparse(current_url)
            if not parsed.hostname or not await _resolve_is_safe(parsed.hostname):
                return LinkMetadata(url=url, error="unsafe_destination")

            try:
                async with client.stream("GET", current_url) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location", "")
                        if not location:
                            return LinkMetadata(url=url, error="fetch_failed")
                        current_url = str(httpx.URL(current_url).join(location))
                        continue  # loop back — re-checks safety on the NEW host first

                    if resp.status_code != 200:
                        return LinkMetadata(url=url, error="fetch_failed")

                    content_type = resp.headers.get("content-type", "")
                    if not content_type.startswith("text/html"):
                        return LinkMetadata(url=url, error="unsupported_content_type")

                    body = b""
                    async for chunk in resp.aiter_bytes():
                        body += chunk
                        if len(body) > _MAX_RESPONSE_BYTES:
                            return LinkMetadata(url=url, error="response_too_large")
            except httpx.HTTPError as exc:
                logger.warning("link_metadata: generic fetch failed for {}: {}", url, exc)
                return LinkMetadata(url=url, error="fetch_failed")

            text = body.decode(errors="ignore")
            title_match = _OG_TITLE_RE.search(text) or _TITLE_TAG_RE.search(text)
            desc_match = _OG_DESC_RE.search(text)
            return LinkMetadata(
                url=url,
                title=(title_match.group(1).strip() if title_match else ""),
                description=(desc_match.group(1).strip() if desc_match else ""),
            )

    return LinkMetadata(url=url, error="too_many_redirects")


async def fetch_link_metadata(urls: list[str]) -> list[LinkMetadata]:
    """Fetch metadata for each URL concurrently, capped at 3 in-flight requests.
    Never raises — a failed fetch for one URL never blocks the others."""
    semaphore = asyncio.Semaphore(_CONCURRENCY_LIMIT)

    async def _one(url: str) -> LinkMetadata:
        async with semaphore:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower()
            if hostname in ("github.com", "www.github.com"):
                match = _GITHUB_REPO_PATH_RE.match(parsed.path)
                if match:
                    return await _fetch_github(match.group(1), match.group(2))
            return await _fetch_generic(url)

    return list(await asyncio.gather(*(_one(u) for u in urls)))
