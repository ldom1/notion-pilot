from __future__ import annotations

import httpx
import pytest
import respx

from notion_pilot.shared.siren_lookup import _SEARCH_URL, lookup_siren


@pytest.mark.asyncio
@respx.mock
async def test_lookup_siren_returns_top_match():
    respx.get(_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"siren": "428895676", "nom_complet": "ARTELYS"}]},
        )
    )

    result = await lookup_siren("Artelys")

    assert result == {"siren": "428895676", "matched_name": "ARTELYS"}


@pytest.mark.asyncio
@respx.mock
async def test_lookup_siren_returns_none_when_no_results():
    respx.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json={"results": []}))

    result = await lookup_siren("Nonexistent Corp")

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_lookup_siren_rejects_malformed_siren():
    respx.get(_SEARCH_URL).mock(
        return_value=httpx.Response(
            200, json={"results": [{"siren": "not-a-siren", "nom_complet": "Weird Corp"}]}
        )
    )

    result = await lookup_siren("Weird Corp")

    assert result is None
