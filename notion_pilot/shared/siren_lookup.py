"""SIREN lookup by company name via the French government's free company
search API (no key required) — https://recherche-entreprises.api.gouv.fr."""

from __future__ import annotations

import httpx

_SEARCH_URL = "https://recherche-entreprises.api.gouv.fr/search"
_SIREN_LEN = 9


async def lookup_siren(name: str) -> dict[str, str] | None:
    """Returns the top match as {"siren": ..., "matched_name": ...}, or None
    if there's no match or the API's identifier isn't SIREN-shaped."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(_SEARCH_URL, params={"q": name, "per_page": 1})
        response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        return None
    top = results[0]
    siren = top.get("siren", "")
    if len(siren) != _SIREN_LEN:
        return None
    return {"siren": siren, "matched_name": top.get("nom_complet", "")}
