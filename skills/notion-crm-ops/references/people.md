# People

Ground truth shapes: `notion_pilot/mcp/models.py` → `PersonRecord`; writes via `NotionPeopleSyncer` / Notion MCP.

## Required vs strongly expected

| Field | Notion property | Required |
|-------|-----------------|----------|
| name | `Name` (title) | **yes** |
| company | `Company` (relation) | **yes** (resolve/create company first) |
| email | `Email - pro` | strongly expected |
| linkedin_url | `Linkedin` | strongly expected |
| position | `Position` | strongly expected |
| seniority | `Seniority` (select) | strongly expected |
| role_type | `Role Type` (multi_select) | strongly expected |
| phone | `Phone` | strongly expected |

## Seniority enum

`founder` | `c_suite` | `vp` | `director` | `manager` | `senior` | `mid` | `junior`

Map titles: Directeur/Director → `director`; CEO/CTO → `c_suite` or `founder`; Manager → `manager`; etc. If unsure → propose + `needs_review`.

`PersonRecord.seniority` is a free `str` — the tool does **not** validate the enum, so an out-of-set value writes silently. Enforce the enum here before writing.

## Dedup

Prefer `notion-crm` `upsert_people` / `search_people` (email/LinkedIn exact, then fuzzy name+company). On Notion MCP only: search by name + company; do not create duplicates when score is high — UPDATE instead.

Upsert **skip** on exact match does **not** fill empty LinkedIn/position — patch missing fields explicitly after match.

## Enrichment

Web/LinkedIn research for missing strongly-expected fields. Label `source=web|user`. Never invent URLs.
