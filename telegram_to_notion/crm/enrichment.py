"""Brave Search email enrichment — best-effort, never raises."""
import re

import httpx

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


async def find_email(name: str, company: str, api_key: str) -> str | None:
    """Query Brave for an email address. Returns first match found, or None."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                _BRAVE_URL,
                params={"q": f'"{name}" "{company}" email', "count": 5},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = " ".join(
                r.get("description", "") + " " + r.get("url", "")
                for r in data.get("web", {}).get("results", [])
            )
            m = _EMAIL_RE.search(text)
            return m.group(0) if m else None
    except Exception:  # noqa: BLE001
        return None
