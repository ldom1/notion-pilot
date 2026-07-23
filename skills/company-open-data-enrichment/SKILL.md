---
name: company-open-data-enrichment
description: >-
  Enriches Artelys Notion CRM Companies with French open company data (SIREN,
  NAF/APE, BODACC, RNE financials, dirigeants). Use when enriching or creating a
  company record from public sources, verifying SIREN, checking BODACC/RNE, or
  filling firmographics in notion-pilot. Always French validation table + go
  before write; follow notion-crm-ops write discipline.
---

# company-open-data-enrichment

Project-only skill for **Artelys CRM Companies** in this repo. Owns resolve → gather → propose. Does not invent values and does not change the Companies schema beyond the 4 fixed Finance properties (`CA`, `Résultat net`, `Marge nette %`, `Année financière` — see Fields below).

## Prerequisites (hard)

1. **Notion MCP** authenticated to the Artelys CRM workspace. If missing → stop and ask the user to connect it.
2. **Any Notion write** must follow **`notion-crm-ops` write discipline** (French preview table, explicit `go`, never invent LinkedIn/SIREN/financials/dirigeants, prefer `notion-crm` tools then Notion MCP fallback). Read that skill for tooling preference; do not reinvent write logic here.
3. **Prosper MCP** preferred (`PROSPER_MCP_URL`, default `http://localhost:8090/sse`) for profile / BODACC / RNE / dirigeants — but **prosper is early-stage and not reliably live**. Treat it as an accelerator, not a dependency: try it first, and on any error/timeout/unreachable fall through to the **direct API fallback** (below) without asking the user to fix Prosper first. Whichever path is used, missing sources must still appear as SKIP rows (never silently omitted).
4. Ground field shapes in `notion_pilot/mcp/models.py` (`CompanyRecord`), `notion_pilot/shared/siren_lookup.py`, `notion_pilot/shared/prosper_client.py`, and `skills/notion-crm-ops/references/companies.md` + `crm-ids.md`.

## Scope

- **In:** create or update one Companies row from name / domain / SIREN; SIREN, NAF/APE→Sector, Size, Country, Website, Linkedin; BODACC / dirigeants into Notes; RNE financials (`CA`, `Résultat net`, `Marge nette %`, `Année financière`) as real Notion properties — see Finance section below.
- **Out:** open-ended schema migrations beyond the 4 named Finance properties; person enrichment; Prosper pipeline ingest; inventing URLs or financials; ad hoc web search solely to manufacture identity corroboration.

## Identity confidence

Costliest failure mode — use these gates, not vibes. Aligns with `syncer.py` (`token_sort_ratio >= 85`) and Prosper `resolve_company` buckets (`high` / `medium` / `low`).

### High (may UPDATE/CREATE SIREN without `needs_review`)

Any one of:

1. User-supplied exact 9-digit SIREN.
2. Prosper `resolve_company` → `confidence_level == "high"`.
3. Registry top candidate `token_sort_ratio(normalize(input), normalize(legal_name)) >= 85` **and** ≥1 corroborating signal:
   - exact website/domain match **only if** domain was already supplied by user or existing Notion row — **do not fetch a website to invent corroboration**;
   - matching département / code postal from registry; **or**
   - exact legal name after normalize (accent/case/punctuation stripped).

### Same gates for existing Notion row search

- High-confidence existing match → UPDATE.
- Ambiguous Notion matches → table row(s) `needs_review` with candidates; **never treat as absent and CREATE**.
- CREATE only when search finds no plausible match. Prefer `upsert_companies(confirm=false)` so Notion dedup surfaces candidates.

### `needs_review` (show candidates; never force SIREN / CREATE)

- Fuzzy ≥85 with no corroboration, or score <85.
- Prosper `medium` / `low`.
- Near-equal candidates (prosper gap < 0.10, or competing registry names).
- Prosper SIREN ≠ registry SIREN → disagreement row (below).
- Ambiguous existing Notion company match.

### Never

- Force a SIREN when Prosper and registry disagree.
- Invent LinkedIn, website, financials, dirigeants.
- Treat CRM `would_skip` / matched as "fields complete."
- Treat a fuzzy Notion near-match as "not found."

Tag every proposed value: `source=notion|prosper|registry|bodacc|rne|user`.

## Source priority

1. Existing Notion Companies row (inventory gaps; matched ≠ complete).
2. `notion-crm` `upsert_companies(confirm=false)` when resolving/creating.
3. Prosper MCP: `resolve_company`, `get_company`, `get_company_rne`, `get_company_dirigeants`, `enrich_company`, `get_data_status`.
4. **Direct API fallback** (below) for SIREN / BODACC / RNE when Prosper is unreachable — same open-data sources Prosper itself calls, no key, no MCP required.
5. Notion MCP page patch only if local `notion-crm` cannot write Companies DS.

## Direct API fallback (Prosper unreachable — no key required)

Three ordered steps. Run 1 first — its SIREN feeds 2 and 3. Do not re-resolve the SIREN per step. All three hosts are free, unauthenticated, open-data APIs (no `Authorization` header, no token) — fetch with `WebFetch` or `curl`, one request per field per company.

### 1. SIREN — resolve identity by name/domain

`GET https://recherche-entreprises.api.gouv.fr/search?q={name-or-domain}&page=1&per_page=3`

- **Expected data:** `results[]`, each with `siren` (9 digits), `nom_complet`, `section_activite_principale` (NAF section letter), `activite_principale` (full NAF code), `tranche_effectif_salarie` (INSEE headcount bracket). Empty `results` → no match, do not force a SIREN.
- Map to Notion: `section_activite_principale`/`activite_principale` → `Sector` via `naf_section_to_sector`; `tranche_effectif_salarie` → `Size` via `tranche_to_size` (both in `notion_pilot/shared/siren_lookup.py`).
- This mirrors `notion_pilot/shared/siren_lookup.py::lookup_siren_candidates` exactly — same URL, same params.

```bash
curl -s "https://recherche-entreprises.api.gouv.fr/search?q=Danone&page=1&per_page=3"
```

### 2. BODACC — insolvency signals for the resolved SIREN

`GET https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records?where=registre like "{siren}"&limit=10&order_by=dateparution desc&select=registre,dateparution,typeavis,familleavis_lib,tribunal,commercant`

- **Expected data:** `total_count` + `results[]` of announcements (most recent first). `total_count == 0` → no BODACC history for this SIREN; that is a valid outcome, not a failure — tag the row SKIP with "no BODACC record", never omit it.
- Read `familleavis_lib` to classify: contains "liquidation" → `LIQUIDATION`; "redressement" → `REDRESSEMENT`; "sauvegarde" → `SAUVEGARDE` — same keyword rules as `prosper/sync/bodacc.py::_extract_famille_procedure`. Surface the most recent matching procedure + its `dateparution` in the Notes `RNE`/`BODACC` line.
- **Do not** use the `/exports/json` variant of this dataset — that is prosper's bulk nightly-sync endpoint (whole date ranges, no per-SIREN filter, can return 10k+ rows). `/records` with a `where=registre like "…"` filter is the correct per-company lookup and is what must be queried here.

```bash
curl -s "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records?where=registre%20like%20%22552032534%22&limit=10&order_by=dateparution%20desc&select=registre,dateparution,typeavis,familleavis_lib,tribunal,commercant"
```

Verified live against SIREN `552032534` (Danone) — returns `total_count: 106` and a `results[]` array of announcements.

### 3. RNE — dirigeants + finances for the resolved SIREN

`GET https://recherche-entreprises.api.gouv.fr/search?q={siren}&page=1&per_page=1`

- Same host/path as step 1, but queried by the exact 9-digit SIREN instead of a name — returns one richer per-company record instead of fuzzy candidates.
- **Expected data:** `results[0].dirigeants[]` — each entry `nom`, `prenoms`, `qualite` (e.g. "Directeur Général", "Administrateur"), `date_de_naissance`, `type_dirigeant` (`personne physique`/`personne morale`), `nationalite`; personne morale entries carry `siren`/`denomination` instead of `nom`/`prenoms`. And `results[0].finances` — dict keyed by year, e.g. `{"2024": {"ca": 27376000000, "resultat_net": 0}}`; absent/empty when no accounts have been filed.
- `results` empty, or `results[0].siren != siren` → SIREN not found in this registry; tag SKIP, do not fabricate dirigeants/finances.
- Mirrors prosper's own RNE fetch: `prosper/intelligence/rne_cache.py::fetch_rne` (same URL, `q=siren&per_page=1`) and `prosper/models/rne.py::RneEntreprise` (same `dirigeants`/`finances` shape) — Prosper does not have a separate INPI/RNE endpoint, it caches this exact call.

```bash
curl -s "https://recherche-entreprises.api.gouv.fr/search?q=552032534&page=1&per_page=1"
```

Verified live against the same SIREN — `results[0].finances` returns `{"2024": {"ca": 27376000000, "resultat_net": 0}}`.

Margin computation (guards `ca == 0`/missing — never fabricates a ratio):

```python
def compute_margin(finances: dict) -> tuple[int, float | None]:
    """Returns (year, margin) from an RNE `finances` dict. margin is None
    when ca is 0 or missing — never fabricate a ratio."""
    year = max(int(y) for y in finances.keys())
    entry = finances[str(year)]
    ca = entry.get("ca") or 0
    resultat_net = entry.get("resultat_net")
    if not ca or resultat_net is None:
        return year, None
    return year, resultat_net / ca
```

## Fields

**Writable properties:** `SIREN`, `Sector`, `Size`, `Country`, `Website`, `Linkedin`, `Notes`, `CA`, `Résultat net`, `Marge nette %`, `Année financière`.

**Extras** (NAF label, BODACC, dirigeants, freshness) → single Notes block only. Do not add Notion properties beyond the fixed set above — no open-ended schema evolution.

### Finance properties (`CA` / `Résultat net` / `Marge nette %` / `Année financière`)

Sourced from RNE step 3's `finances` dict (Direct API fallback, above), gated on a **high-confidence SIREN** (Identity confidence, above) — no confident SIREN means the whole Finance section is skipped and shown as an explicit SKIP row, never fetched off a name-only match.

| Property | Type | Format | Source |
|---|---|---|---|
| `CA` | Number | Euro | `finances[year].ca`, raw euros, no scaling |
| `Résultat net` | Number | Euro | `finances[year].resultat_net` — can be negative (a loss), write as-is |
| `Marge nette %` | Number | Percent | `resultat_net / ca`; **blank** (not `0`) when `ca` is `0`/missing — never fabricate a ratio; can be negative |
| `Année financière` | Number | plain | the year key itself, e.g. `2024` |

`year` = `max(int(y) for y in finances.keys())` — a numeric max over year keys, never dict iteration order.

**Write path:** Notion MCP directly (not `notion-crm`'s `upsert_companies`/`enrich_companies` — those only write at CREATE time or fill-empty, neither fits data that must refresh annually). Values are **always overwritten** with the freshest year found — same REPLACE philosophy as the Notes block — subject to the two guards below.

**Ensure Finance properties exist (idempotent, once per workspace):**

1. Read the Companies DB schema via Notion MCP.
2. For each of the 4 properties: if missing, create it with the type/format in the table above (same idempotent check-then-create idea as `ensure_siren_property` in `notion_pilot/crm/syncer.py:156-167`, issued as a Notion MCP call instead of new Python).
3. If a property with that name **already exists with the wrong type** (e.g. `CA` hand-created as `Text`): do **not** write into it. Surface an ERROR row instead — `CA | — | type conflict: existing "CA" property is Text, expected Number | rne | n/a | ERROR — fix property type manually before retrying`.

**Stale-source guard (before writing values):**

1. Read the existing `Année financière` value on the Notion page, if any.
2. If `fetched_year < existing_year`: skip the write entirely (RNE lags/caches — an older year is a stale fetch, not a real regression) and add a stale-source row: `Finance (all 4) | 2024 (current) | 2023 (rne, stale) — RNE returned an older year than already on file | rne | n/a | SKIP — stale source`.
3. Otherwise (`fetched_year >= existing_year`, including equal) proceed with the write.

### Notes `[open-data]` (replace, never append)

```text
[open-data]
SIREN: …
NAF: … (label)
BODACC: …
RNE: …
Dirigeants: …
Sources: prosper|registry|… · refreshed YYYY-MM-DD
[/open-data]
```

On re-run: if `[open-data]…[/open-data]` exists, **replace** that block only. In the post-write report, flag: previous open-data block replaced — verify no manual edits were lost.

## Workflow

1. Search existing Notion Companies row with high/`needs_review` gates.
2. Resolve SIREN identity (domain corroboration only if domain already known).
3. Gather Prosper then registry; record each source as ok / empty / unreachable.
4. Build proposal + `[open-data]` REPLACE plan.
5. French validation table (below).
6. Wait for explicit `go` (`ok`, `go`, `parfait`, …).
7. Write via `notion-crm-ops` discipline.
8. Report written fields, Notes REPLACE (human-edit warning), unresolved / unavailable sources.

## Validation table (required before write)

```markdown
### Enrichissement société — à valider

| Champ | Valeur actuelle | Valeur proposée | Source | Confiance | Action |
|---|---|---|---|---|---|
| Notion match | … | ambiguous candidates … | notion | needs_review | SKIP (no CREATE) |
| SIREN | … | … | prosper/registry | high | UPDATE/CREATE |
| SIREN | — | 2 candidates disagree (prosper: …, registry: …) | prosper+registry | needs_review | SKIP |
| Sector | … | … | naf/prosper | high | UPDATE |
| Size | … | … | registry/prosper | medium | UPDATE |
| Website | … | … | prosper | medium | UPDATE |
| Notes `[open-data]` | present/absent | replace block … | bodacc/rne/… | high | REPLACE |
| RNE | — | not available (Prosper unreachable) | prosper | n/a | SKIP |
| BODACC | — | not in Prosper catalog | prosper | n/a | SKIP |

Réponds **go** pour écrire, ou corrige les lignes.
```

Every run must include: property/CREATE rows, identity/`needs_review` (Notion match, SIREN, prosper↔registry disagreement when relevant), Notes REPLACE plan, and **explicit missing/unreachable source rows** (must appear, must not disappear).
