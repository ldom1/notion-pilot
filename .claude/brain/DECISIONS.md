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

### 2026-05-28 — Website: landing + Notion OAuth deploy wizard + chatbot
**Decision:** Build a website with three functions: (1) landing/marketing, (2) "Deploy to Notion" wizard using Notion OAuth, (3) chatbot interface to query/add to Notion DBs.  
**Rejected:** CLI-only onboarding  
**Rationale:** Target audience (small teams) needs a zero-friction setup path. Notion OAuth eliminates manual token copy-paste. Chatbot extends the Telegram interaction model to a web interface.
