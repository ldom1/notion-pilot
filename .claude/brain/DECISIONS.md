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
