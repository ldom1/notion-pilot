"""SIREN lookup by company name via the French government's free company
search API (no key required) — https://recherche-entreprises.api.gouv.fr.
Also maps that API's NAF/headcount fields onto this project's Notion select
options, since the two are only ever used together."""

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


async def lookup_siren_candidates(name: str, per_page: int = 3) -> list[dict[str, str]]:
    """Returns up to `per_page` registry matches, best first. Each dict has
    siren, matched_name, section_activite_principale (NAF section letter),
    activite_principale (full NAF code), tranche_effectif_salarie (INSEE
    headcount bracket). Entries whose identifier isn't SIREN-shaped are
    skipped. Empty list if there's no match at all."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(_SEARCH_URL, params={"q": name, "per_page": per_page})
        response.raise_for_status()
    results = response.json().get("results") or []
    candidates: list[dict[str, str]] = []
    for top in results:
        siren = top.get("siren", "")
        if len(siren) != _SIREN_LEN:
            continue
        candidates.append(
            {
                "siren": siren,
                "matched_name": top.get("nom_complet", ""),
                "section_activite_principale": top.get("section_activite_principale", ""),
                "activite_principale": top.get("activite_principale", ""),
                "tranche_effectif_salarie": top.get("tranche_effectif_salarie", ""),
            }
        )
    return candidates


_SECTOR_BY_NAF_SECTION = {
    "A": "Industry",
    "B": "Industry",
    "C": "Industry",
    "D": "Energy",
    "E": "Energy",
    "F": "Industry",
    "G": "Other",
    "H": "Industry",
    "I": "Other",
    "K": "Finance",
    "L": "Other",
    "N": "Consulting",
    "O": "Public Sector",
    "P": "Public Sector",
    "Q": "Public Sector",
    "R": "Other",
    "S": "Other",
    "T": "Other",
    "U": "Other",
}


def naf_section_to_sector(section: str, naf_code: str = "") -> str:
    """Maps an INSEE NAF section letter (Rev.2) to one of this project's
    Notion Companies "Sector" select options. J (info/comm) and M
    (professional/scientific/technical) get a division-level split since
    they otherwise span very different businesses (software vs. telecom;
    consulting vs. R&D)."""
    if section == "J":
        return "Telecom" if naf_code.startswith("61") else "Software"
    if section == "M":
        return "Research" if naf_code.startswith("72") else "Consulting"
    return _SECTOR_BY_NAF_SECTION.get(section, "Other")


_SIZE_BY_TRANCHE = {
    "00": "1-10",
    "01": "1-10",
    "02": "1-10",
    "03": "1-10",
    "11": "11-50",
    "12": "11-50",
    "21": "51-200",
    "22": "51-200",
    "31": "201-500",
    "32": "201-500",
    "41": "501-2000",
    "42": "501-2000",
    "51": "2001-10000",
    "52": "2001-10000",
    "53": "10000+",
}


def tranche_to_size(tranche: str) -> str:
    """Maps an INSEE headcount-bracket code to one of this project's Notion
    Companies "Size" select options. Returns "" for "NN"/unknown/unrecognized
    codes — leave the field blank rather than guess."""
    return _SIZE_BY_TRANCHE.get(tranche, "")
