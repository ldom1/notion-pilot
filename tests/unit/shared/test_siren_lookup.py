from __future__ import annotations

import httpx
import pytest
import respx

from notion_pilot.shared.siren_lookup import (
    _SEARCH_URL,
    lookup_siren_candidates,
    naf_section_to_sector,
    tranche_to_size,
)


def _result(siren="428895676", nom="ARTELYS", section="M", naf="70.22Z", tranche="12"):
    return {
        "siren": siren,
        "nom_complet": nom,
        "section_activite_principale": section,
        "activite_principale": naf,
        "tranche_effectif_salarie": tranche,
    }


@pytest.mark.asyncio
@respx.mock
async def test_lookup_siren_candidates_returns_up_to_three_matches():
    respx.get(_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [_result(), _result(siren="444608442", nom="ENEDIS", section="D")]},
        )
    )

    results = await lookup_siren_candidates("Artelys")

    assert len(results) == 2
    assert results[0]["siren"] == "428895676"
    assert results[0]["matched_name"] == "ARTELYS"
    assert results[0]["section_activite_principale"] == "M"
    assert results[0]["activite_principale"] == "70.22Z"
    assert results[0]["tranche_effectif_salarie"] == "12"


@pytest.mark.asyncio
@respx.mock
async def test_lookup_siren_candidates_returns_empty_when_no_results():
    respx.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json={"results": []}))

    results = await lookup_siren_candidates("Nonexistent Corp")

    assert results == []


@pytest.mark.asyncio
@respx.mock
async def test_lookup_siren_candidates_skips_malformed_siren_but_keeps_others():
    respx.get(_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    _result(siren="not-a-siren", nom="Weird Corp"),
                    _result(siren="444608442", nom="ENEDIS"),
                ]
            },
        )
    )

    results = await lookup_siren_candidates("Weird")

    assert len(results) == 1
    assert results[0]["siren"] == "444608442"


def test_naf_section_to_sector_energy():
    assert naf_section_to_sector("D") == "Energy"
    assert naf_section_to_sector("E") == "Energy"


def test_naf_section_to_sector_telecom_vs_software():
    assert naf_section_to_sector("J", "61.10Z") == "Telecom"
    assert naf_section_to_sector("J", "62.01Z") == "Software"


def test_naf_section_to_sector_research_vs_consulting():
    assert naf_section_to_sector("M", "72.19Z") == "Research"
    assert naf_section_to_sector("M", "70.22Z") == "Consulting"


def test_naf_section_to_sector_public_and_finance():
    assert naf_section_to_sector("O") == "Public Sector"
    assert naf_section_to_sector("K") == "Finance"


def test_naf_section_to_sector_unknown_defaults_other():
    assert naf_section_to_sector("Z") == "Other"
    assert naf_section_to_sector("") == "Other"


def test_tranche_to_size_mappings():
    assert tranche_to_size("00") == "1-10"
    assert tranche_to_size("12") == "11-50"
    assert tranche_to_size("22") == "51-200"
    assert tranche_to_size("32") == "201-500"
    assert tranche_to_size("42") == "501-2000"
    assert tranche_to_size("52") == "2001-10000"
    assert tranche_to_size("53") == "10000+"


def test_tranche_to_size_unknown_returns_empty():
    assert tranche_to_size("NN") == ""
    assert tranche_to_size("") == ""
