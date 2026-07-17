---
type: decisions
updated:
---

# Decisions

<!-- Append-only ADR log. Never delete entries. -->

### 2026-04-17 — Long polling only, no webhook server
**Decision:** Use `python-telegram-bot` long polling exclusively  
**Rejected:** Webhook server requiring a public HTTPS endpoint  
**Rationale:** Simpler infra, no reverse proxy needed, runs fine as a single systemd user service on a home server

### 2026-04-17 — Notion file_upload API for media
**Decision:** Upload media files to Notion via the file_upload API  
**Rejected:** Storing ephemeral Telegram CDN URLs directly in Notion  
**Rationale:** Telegram URLs expire; file_upload gives permanent storage in Notion (requires `notion-client>=2.2.1`)

### 2026-04-17 — asyncio.to_thread for Notion SDK
**Decision:** Wrap all `notion-client` calls in `asyncio.to_thread`  
**Rejected:** Running a separate thread pool or switching SDK  
**Rationale:** The Notion SDK is synchronous; `asyncio.to_thread` is the minimal-friction bridge with no extra dependencies

### 2026-04-17 — OpenRouter for LLM enrichment with heuristics fallback
**Decision:** OpenRouter as the LLM gateway (default: `google/gemini-2.5-flash-lite`); URL/platform heuristics if no API key  
**Rejected:** Hard-requiring an LLM API key  
**Rationale:** Keeps the bot functional with zero config; LLM is a progressive enhancement

### 2026-04-17 — faster-whisper for on-device transcription
**Decision:** `faster-whisper` as the voice transcription engine (optional install group)  
**Rejected:** Cloud STT APIs  
**Rationale:** No data leaves the server; no API key; aligns with self-hosted, privacy-first positioning

### 2026-04-17 — animation checked before video in handlers
**Decision:** Always check `message.animation` before `message.video`  
**Rejected:** Relying on message type alone  
**Rationale:** Telegram sets both `animation` and `video` flags for GIFs; wrong order causes GIFs to be misclassified as videos

### 2026-05-28 — Rename to Notion Pilot, mono-repo with two verticals
**Decision:** Rename repo/package to `notion-pilot` / `notion_pilot`. Keep mono-repo. Organize as two verticals (`crm/` and `inbox/`) sharing a common core (`shared/`).  
**Rejected:** Two separate repos (`notion-crm` + `notion-inbox`)  
**Rationale:** Single developer, real shared infrastructure (adapters, LLM, Notion client, config). Splitting repos creates duplication and sync overhead. Can publish as separate PyPI packages later without splitting the repo.

### 2026-05-28 — Two products: notion-crm + notion-inbox
**Decision:** Treat CRM (People/Companies/Deals) and Knowledge inbox as two independent products with distinct target audiences, but sharing the same codebase.  
**Rejected:** Single undifferentiated product  
**Rationale:** CRM targets small sales teams (2-10 people); inbox targets personal knowledge management. Different setup, different enrichment, different Telegram commands. Separating concerns in code structure makes each product easier to document, sell, and onboard independently.

### 2026-06-02 — Human review gate before any People DB write (email pipeline)
**Decision:** No email sender is ever upserted into the Notion People DB without an explicit human decision in the review CSV. The full gate is: dry-run → human edits `email-import-people-review.csv` → `--apply-review` triggers YAML update + Notion upsert for `decision=people` rows.  
**Rejected:** Heuristic auto-classification of senders (e.g. "is this a real person?") that bypasses human review  
**Rationale:** False positives (automated senders, noreply addresses) would pollute the People DB silently. The CSV review step is cheap; a polluted CRM is expensive to clean up. The `--apply-review` command is the only code path that writes a new person from an email sender into Notion.

### 2026-06-02 — pandas as the standard data manipulation library
**Decision:** Use `pandas` for all CSV, JSON, and tabular data I/O across the codebase. No raw `csv` module, no hand-rolled delimiter sniffing.  
**Rejected:** stdlib `csv`, `json.load` + list comprehensions for tabular data  
**Rationale:** `pd.read_csv(sep=None, engine="python")` auto-detects delimiters (handles `,` vs `;` from Excel without hacks). `utf-8-sig` BOM ensures correct opening in French/European Excel. Uniform API across CSV, JSON, Parquet if needed. Eliminates the `_write_review_row` append-per-row anti-pattern in favour of collect-then-write.  
**How to apply:** Any new script reading or writing tabular data must use pandas. Replace any remaining `import csv` found during refactors.

### 2026-06-03 — Customer deployment model: hosted wizard + shared bot + file-upload cockpit

**Context:** The cockpit runs scripts server-side. Scripts read local files (`data/crm/linkedin/`, SQLite state). Customers who set up via the hosted wizard have no SSH access to Louis's server. The Telegram bot is currently a systemd service tied to one user's config.

**Decision:** Three-tier hosted model, in order of implementation:

**Tier 1 — Hosted wizard (done):** Louis runs `notion-pilot.com`. Any customer OAuth with Notion → workspace created in their account. No server-side data yet.

**Tier 2 — Multi-customer cockpit:** The cockpit becomes multi-tenant with two additions:
- `data/` namespaced by Notion workspace_id: `data/{workspace_id}/crm/linkedin/`, `data/{workspace_id}/conv_state.db`, etc.
- `/api/cockpit/upload` endpoint for LinkedIn CSV and future files — eliminates the need for SSH access entirely
- Scripts receive the workspace's data dir and stored Notion token; run in isolation per customer
- OAuth token stored (encrypted) server-side per workspace_id (needed to run scripts on behalf of the customer)

**Tier 3 — Shared Telegram bot:** Louis runs one bot for all customers. Customers link it from the cockpit:
- Cockpit shows a "Connect Telegram" button → generates a one-time token deep link (`t.me/NotionPilotBot?start=<token>`)
- Customer clicks the link in Telegram → bot receives `/start <token>` → maps `telegram_user_id → workspace_id` in a registry
- All subsequent bot messages from that user are dispatched to their workspace (token + db_ids looked up from the registry)
- Registry: small SQLite table `{telegram_user_id, workspace_id, linked_at}` — no per-customer bot token needed

**Alternative for power users:** customers who want their own private bot (or want self-hosted) can still deploy via Docker Compose with their own `TELEGRAM_BOT_TOKEN`. The self-hosted path is fully supported as a second deployment option.

**Rejected:** Per-customer separate bot process (too many systemd units, unmanageable)  
**Rejected:** CLI-only / manual VPS setup without Docker (too high friction for target audience)  
**Rejected:** Full multi-tenant SaaS immediately (too complex before single-user experience is solid)

**Rationale:** Telegram user ID is already a unique, stable identity. One bot + a user→workspace registry is the minimal delta to serve N customers from a single process. The cockpit file upload removes the last SSH-requiring step. Data namespacing by workspace_id is the only structural change needed in `data/`.

---

### 2026-05-28 — Website: landing + Notion OAuth deploy wizard + chatbot
**Decision:** Build a website with three functions: (1) landing/marketing, (2) "Deploy to Notion" wizard using Notion OAuth, (3) chatbot interface to query/add to Notion DBs.  
**Rejected:** CLI-only onboarding  
**Rationale:** Target audience (small teams) needs a zero-friction setup path. Notion OAuth eliminates manual token copy-paste. Chatbot extends the Telegram interaction model to a web interface.

### 2026-06-03 — Deal creation: client-side wizard, not server-side auto-create
**Decision:** When LLM returns `action=create`, the server emits the leads list without creating anything. The client fetches the live Deals DB schema, runs a wizard (clickable option buttons per property), then calls `POST /api/cockpit/create-deal` only after user confirmation.  
**Rejected:** Server auto-creating deals on `action=create` intent  
**Rationale:** User must validate the lead before committing to Notion. Auto-create produced a false "✓ created" badge with nothing in Notion. Wizard also collects Product/Type/Stage which the server can't infer.

### 2026-06-03 — web/config.py naming: keep module name, rename directory
**Decision:** `web/config.py` (Python module) and `web/workspaces/` (per-workspace data directory). Previously named `web/cfg.py` + `web/config/` to avoid collision.  
**Rejected:** Keeping `cfg.py` abbreviation  
**Rationale:** `config.py` is the natural Python module name. A file and directory can't share the same name in the same folder, so the directory was renamed to `workspaces/` which is also more descriptive of its content.

### 2026-06-03 — Automation: List view default + Graph view for composition
**Decision:** Automation panel has two views: List (default, Operations + Workflows sub-tabs) and Graph (React Flow, connectable for workflow composition). Workflows saved from Graph appear in the List Workflows tab.  
**Rejected:** Graph-only view, or hiding workflow management in a separate page  
**Rationale:** Most interactions are single-script runs (list view is faster). Graph is an advanced feature for composing sequential pipelines. Separating by view keeps the default UX uncluttered.

### 2026-06-04 — Lead creation modal: single form, not step-by-step wizard
**Decision:** Deal/Lead creation modal shows all fields at once. Select-type fields render as chip buttons; text/number fields as plain inputs. Single "Create lead" button.  
**Rejected:** Step-by-step wizard (one question per screen with progress bar)  
**Rationale:** Wizard UX felt like a quiz for a simple form. Single-screen form is standard and faster. Fields are few enough (3-5 typically) that one screen is fine.

### 2026-06-04 — Workspace single-DB refresh after re-link
**Decision:** After saving a new DB link, only the changed DB is re-fetched via `GET /api/cockpit/status/{key}`, not all 8.  
**Rejected:** Full `loadStatus()` reload on every save  
**Rationale:** With pagination enabled (up to 18 Notion API calls for a 1800-row DB × 8 DBs), full reload after every edit was too slow. Single-key endpoint makes re-linking snappy.

### 2026-06-04 — Company auto-linking on lead creation
**Decision:** When creating a lead, `company_name` is sent to the backend. Backend searches Companies DB by exact title, auto-detects the relation property in Deals DB pointing to Companies DB, and sets the relation silently.  
**Rejected:** Requiring the user to manually select the company in the modal  
**Rationale:** The company name is already on the lead card. Auto-detection of the relation property avoids hardcoding property names. Silent failure (skip, don't error) if name doesn't match exactly.

### 2026-06-30 — CRM schema: Activities as operational core, Meetings as separate tool
**Decision:** Activities DB is the CRM's event log (what happened, next step). Meetings stays as a separate personal tool; linking is optional via "Advanced Deal?" checkbox → Notion automation creates the Activity automatically.
**Rejected:** Mandatory mirroring (every meeting must create an Activity), or merging Meetings into Activities
**Rationale:** Mandatory mirroring causes double-entry friction. Self-enforcing incentive: checking "Advanced Deal?" auto-creates the Activity, so the dashboard stays accurate only if the checkbox is used. Meetings retains its personal use outside CRM flow.

### 2026-06-30 — CRM formulas: Notion Formula 1.0 API constraints
**Decision:** All formula expressions submitted via PATCH /databases use binary-only `or()`/`and()` nesting and inline dateBetween expressions (no cross-formula property references).
**Rejected:** Using the Formula 2.0 syntax from the Notion UI editor (`or(A, B, C)`, `prop("Days Since Last Activity")`)
**Rationale:** Notion Formula 1.0 API returns 400 on: `or()`/`and()` with 3+ args, and formula properties referencing other formula properties. The binary nesting and inlining produce semantically identical results.

### 2026-06-30 — CRM "No Answer" as terminal stage
**Decision:** "No Answer" is a terminal stage (Days Since = 0, Temperature = "—", excluded from Stale Deal). "Waiting for a Response" is active (ball in their court, still tracked).
**Rejected:** Treating "No Answer" as just another waiting state
**Rationale:** No Answer means "stopped trying — 3 unanswered attempts". It is an explicit decision to park the deal, not a passive state. Keeping it active corrupts the pipeline and temperature metrics.

### 2026-07-02 — Company enrichment: SIREN property + Notion page icon for logo
**Decision:** Added a `SIREN` (rich_text) property to the Companies DB, populated whenever a company is matched in Prosper. Company logos are stored as the Notion page `icon` (external URL, Clearbit favicon lookup on the company's website domain) rather than a dedicated Logo property.
**Rejected:** Adding a dedicated `Logo` URL property; leaving SIREN unstored and re-searching Prosper on every enrichment pass.
**Rationale:** SIREN is the durable key for re-enriching a company later without re-disambiguating between similarly-named entities (a real pain point — many searches returned 5-15 candidates for common names). Notion's native page icon renders in the UI immediately with zero schema change, and Prosper itself has no logo data (only French SIREN/NAF/financial registry data) — Clearbit lookup on Website is the practical fallback.
**How to apply:** Any future company enrichment should check `SIREN` first before re-querying Prosper; only search when it's empty.

### 2026-07-13 — MCP server wraps existing CRM code as a thin translation layer
**Decision:** New `notion_pilot/mcp/` package exposes the CRM vertical (upsert, dedup, enrichment, ranking, read queries) as MCP tools over stdio via `FastMCP`. `tools.py` calls straight into existing `crm/syncer.py`, `shared/utils/dedup.py`, `shared/utils/enrichment.py`, `crm/prospection.py`, `crm/queries.py` — zero duplicated business logic. Required one prerequisite refactor: `scripts/crm/crm_dedup.py`'s private pairwise duplicate-finder moved into `shared/utils/dedup.py` (as `find_company_duplicates`/`find_people_duplicates`/`notion_page_url`) so both the CLI script and the new `find_duplicates` tool share the same code.
**Rejected:** Reimplementing dedup/enrichment/ranking logic inside the MCP layer; an HTTP/SSE transport (deferred — stdio matches the existing `code-index`/`qmd` local MCP server pattern already in use, no auth surface to design for a single-user local tool).
**Rationale:** notion-pilot's CRM logic (fuzzy dedup thresholds, 4-tier enrichment waterfall, LLM ranking) is already proven; the only new thing an MCP interface adds is exposing it to any MCP-aware client instead of only Telegram/CLI.
**Affects:** [Key Modules](ARCHITECTURE.md#key-modules), [Non-Obvious Decisions](ARCHITECTURE.md#non-obvious-decisions)

### 2026-07-13 — Every MCP write tool defaults to confirm=false (dry-run)
**Decision:** `upsert_people`, `upsert_companies`, `enrich_people`, `enrich_companies` all default to `confirm=false`: compute and return the outcome (dedup status, matched record, fields that would be filled) without calling any Notion write endpoint. Caller reviews the preview, then re-calls with `confirm=true` to actually write.
**Rejected:** Always-write tools with no preview step; a separate explicit "preview" tool duplicating each write tool's logic.
**Rationale:** Mirrors `crm_enrich.py`'s existing `--dry-run` flag, generalized to every write tool. An LLM caller (e.g. Claude) can show the user what would happen before committing an irreversible Notion write.
**Affects:** [Non-Obvious Decisions](ARCHITECTURE.md#non-obvious-decisions)

### 2026-07-09 — Enrichment migrated to prosper; /enrich removed from Telegram
**Decision:** Move the four-tier Apollo/Brave/Perplexity/LLM enrichment cascade (person and company) from `notion_pilot/shared/utils/enrichment.py` to prosper, exposed as `enrich_person`/`enrich_company` MCP tools. Remove the `/enrich` Telegram command entirely rather than rewire it to call prosper live.
**Rejected:** Keeping enrichment logic in notion-pilot; rewiring `/enrich` to call prosper's MCP server directly from the bot (would introduce a live network dependency into the Telegram interaction path with no fallback story)
**Rationale:** Prosper is becoming the company-intelligence/lead-gen platform; centralizing all external enrichment-provider calls there avoids duplicating Apollo/Brave integration across two repos. Removing `/enrich` rather than rewiring it sidesteps a reliability question entirely — enrichment is now invoked by calling prosper's MCP tools directly (from a Claude session or a script), not through the bot. See [[prosper]] and the CRM responsibility rationalization spec for the full design.

### 2026-07-14 — Rebase feat/mcp-crm-server onto feat/crm-rationalization-notion-pilot rather than defer
**Decision:** As soon as the enrichment.py→prosper_client migration (2026-07-09 entry above) was confirmed to break the uncommitted `feat/mcp-crm-server` branch, rebase it immediately (stash uncommitted work → move branch pointer to the new tip, since it had zero commits → pop stash → fix the one mechanical import) rather than leave the branches to diverge further.
**Rejected:** Leaving `feat/mcp-crm-server` on its stale base and deferring reconciliation to whenever it's actually merged.
**Rationale:** The two branches touch overlapping code (`shared/utils/dedup.py`, the enrichment call path) and were going to need reconciliation eventually regardless; doing it immediately, while both sets of changes were still fresh in context, was cheaper and lower-risk than an open-ended deferral where the branches could drift further apart.
**Affects:** [Non-Obvious Decisions](ARCHITECTURE.md#non-obvious-decisions)

### 2026-07-15 — Do not auto-patch the live People DB schema on discovering the Nom/Name mismatch
**Decision:** When live-testing the newly merged MCP server found that `NotionPeopleSyncer.upsert()` writes to `"Nom"`/`"In my network"` properties that don't exist on the real People data source (which has `"Name"` as its title property and no `"In my network"` at all — blocking person creation on every code path), leave the live schema untouched and surface the finding + two remediation options to the user rather than picking one and patching production data.
**Rejected:** Silently patching the live Notion database schema (rename title property, add missing select) to unblock the test; silently changing the code to match this DB's schema instead.
**Rationale:** A title-property rename or schema change on a live, in-use Notion database is a real structural change with consequences the agent can't fully see (existing views/filters/formulas referencing `"Name"`), and picking "fix the code" vs. "fix the DB" has architecture-wide consequences (`shared/workspace.py` creates new workspaces with `Nom`/`In my network`, so fixing only the code would diverge new-workspace behavior from this DB). See `[[2026-07-15-mcp-server-test]]` for the full investigation.
**Affects:** [Non-Obvious Decisions](ARCHITECTURE.md#non-obvious-decisions)

### 2026-07-16 — People DB schema mismatch: change the code, not the live database

**Decision:** Resolve the 2026-07-15 "Nom"/"Name" schema mismatch (see entry above) by changing `NotionPeopleSyncer` to write `"Name"` and drop `"In my network"`, and aligning `shared/workspace.py`'s People DB template (both `_seed_people()` and `create_crm_workspace()`) to the same schema — not by patching the live Notion database.
**Rejected:** Patching the live People DB (rename `Name`→`Nom`, add `In my network` back).
**Rationale:** User's explicit call when presented with both options. `"Name"` already matches every other DB template in `workspace.py`; changing the code is the smaller, safer surface area and needs no live-data schema migration.
**Affects:** [Key Modules](ARCHITECTURE.md#key-modules)

### 2026-07-16 — Company dedup: 4-signal decision chain, `token_set_ratio` acronym trade-off accepted as-is

**Decision:** `upsert_companies` dedup now runs a strict chain — domain match (contact email domain vs. an existing company's Website domain) → `token_sort_ratio >= 85` → `token_set_ratio >= 90` (catches acronym/subset containment, e.g. "RTE" vs "Rte France") → else create. `needs_review` carries typed `candidates`. Enforced identically on `confirm=true`, not just in preview.
**Rejected:** Word-stripping name normalization and a separate acronym-length heuristic (proposed during review, verified empirically to be either redundant with `token_set_ratio` or based on a wrong premise about the codebase's dedup scan behavior).
**Rationale:** `token_set_ratio` scoring 100 for any full-token-subset pair (e.g. "EDF" vs "EDF Trading") is a deliberate accepted trade-off, not a bug to engineer around — it's exactly the containment signal needed to catch the "Rte France"/"RTE" incident, and the false-positive risk (unrelated names sharing one word) was verified low (e.g. "EDF Group" vs "EDF Trading" scores far below threshold).
**Affects:** [Non-Obvious Decisions](ARCHITECTURE.md#non-obvious-decisions)

### 2026-07-16 — SIREN confidence gate + `force` never bypasses it

**Decision:** `lookup_siren_candidates` returns top-3 registry matches instead of top-1. Before attaching SIREN/enrichment data, gate on `token_sort_ratio(record.name, candidate.matched_name) >= 85` — below that, skip the entire registry-derived block (SIREN and sector/size/country) and return `needs_review` with the candidates, rather than silently attaching a wrong-but-confident SIREN. `force=True` bypasses only the Notion-dedup `needs_review` block; it never bypasses this SIREN gate, since a wrong SIREN match corrupts data regardless of dedup intent.
**Rejected:** A length-ratio-only SIREN check; letting `force=True` skip every gate uniformly.
**Rationale:** Directly fixes the "Rte France" → wrong-SIREN incident (real SIREN belonged to an unrelated "VCSP ROUTE FRANCE"). Keeping the SIREN gate independent of `force` means overriding a flagged duplicate can never also silently corrupt enrichment data.
**Affects:** [Non-Obvious Decisions](ARCHITECTURE.md#non-obvious-decisions)

### 2026-07-16 — Never commit real third-party PII as test-fixture data

**Decision:** Test fixtures must use fictional placeholder people/companies, never a real name or email copied from a live incident report or production data, even when it's convenient for realism.
**Rejected:** Using the real contact from `[[2026-07-15-mcp-server-test]]`'s incident report as literal fixture data (what actually happened this session — caught only by the harness's permission classifier after it was already committed and pushed to a public repo, not by self-review).
**Rationale:** Real PII in fixtures ends up in git history, pushed to remotes, and referenced in PRs — a privacy exposure that requires a disruptive history rewrite + force-push to fix once discovered, versus zero cost to use a fictional name upfront. See `[[2026-07-16-mcp-crm-fixes]]` for the full incident and remediation.

## Template
<!-- added by ai-dotfiles upgrade -->
