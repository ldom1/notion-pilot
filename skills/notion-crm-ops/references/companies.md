# Companies

Ground truth: `CompanyRecord` in `notion_pilot/mcp/models.py`; SIREN helpers in `notion_pilot/shared/siren_lookup.py`.

## Strongly expected fields (always attempt)

| Field | Notion property | Notes |
|-------|-----------------|-------|
| country | `Country` | e.g. `France` |
| sector | `Sector` | enum below |
| SIREN | `SIREN` | FR companies; **auto-resolved** — see note below |
| Website | `Website` | https URL |
| Linkedin | `Linkedin` | company page URL |
| Size | `Size` | when known |

## SIREN is not a passable field on `upsert_companies`

`CompanyRecord` (`notion_pilot/mcp/models.py`) has **no `siren` input** — the tool resolves SIREN server-side via `siren_lookup.py` and surfaces it on the result (`RecordResult.siren` / `siren_candidate_name`). So:

- **`notion-crm` path:** do not pass SIREN. Run the `upsert_companies` dry-run, then validate the auto-resolved candidate (mark `needs_review` if the name score is low — never force).
- **Notion MCP fallback path only:** set the `SIREN` property manually (registry / pappers), tagged `source=siren`.

## Sector enum (workspace)

`Energy` | `Finance` | `Industry` | `Public Sector` | `Telecom` | `Software` | `Consulting` | `Research` | `Other`

## Size enum

`1-10` | `11-50` | `51-200` | `201-500` | `501-2000` | `2001-10000` | `10000+`

## Dedup / SIREN

Prefer `notion-crm` `upsert_companies` dry-run (`confirm=false`) — surfaces SIREN candidates and `needs_review`. Do not force SIREN when name score is low unless user confirms.

If local API cannot see Companies DS, use Notion MCP create/update on the company page.

## Financials (Finance section)

Source: `company-open-data-enrichment` skill, RNE `finances` data (`recherche-entreprises.api.gouv.fr` queried by SIREN). Gated on a high-confidence SIREN — see that skill's Identity confidence gates.

| Field | Notion property | Notes |
|-------|-----------------|-------|
| CA | `CA` | Number, Euro format; raw euros, latest filed year |
| Résultat net | `Résultat net` | Number, Euro format; can be negative |
| Marge nette | `Marge nette %` | Number, Percent format; blank when CA is 0/missing, can be negative |
| Année financière | `Année financière` | Number; the filed year these three refer to |

**Write path:** these 4 properties are **Notion-MCP-only writes** — `upsert_companies` (create-time only) and `enrich_companies` (fill-empty-only, never refreshes) don't fit data that must refresh annually, so `company-open-data-enrichment` writes them directly via Notion MCP page-update instead, always overwriting with the freshest filed year (never an older one — see that skill's stale-source guard).

**Grouping:** Notion's API can't create the "Finance" section grouping itself (UI/layout-only feature) — group these 4 properties manually in the page layout builder once, after they're first created.

## Incomplete company

Related Lead/People/Activity may still write after user go. Leave missing company fields empty; list them under `needs_review`. Never invent SIREN or LinkedIn.
