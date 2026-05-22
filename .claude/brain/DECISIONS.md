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

### 2026-05-21 — crm/ and pipelines/ coexist as separate packages
**Decision:** Keep `crm/` (batch CRM operations) and `pipelines/` (real-time event-driven handlers) as distinct packages  
**Rejected:** Merging CRM logic into pipelines/  
**Rationale:** Different execution models (batch scripts vs. async event loop), different lifecycles. Both need the Notion client but serve different concerns.

### 2026-05-22 — Deals DB uses standard databases API, not data_sources
**Decision:** `NotionDealsSyncer` uses `parent={"database_id": ...}` and raw httpx for create/patch  
**Rejected:** Inline data_sources API (used by People + Companies)  
**Rationale:** Deals DB was created via `databases.create()` — standard database, not inline. data_sources API returns 404 for programmatically-created DBs. Additionally, `notion-client 3.x` silently drops the `properties` arg on `databases.create()`; all scripts use raw httpx PATCH to apply the schema after creation.

### 2026-05-22 — Four-tier enrichment pipeline with Perplexity between Brave and LLM
**Decision:** `utils/enrichment.py` uses four tiers: Apollo.io → Brave Search → Perplexity (`sonar-pro`) → LLM inference  
**Rejected:** Three-tier (Apollo → Brave → LLM) or replacing Brave with Perplexity  
**Rationale:** Perplexity is more expensive than Brave but cheaper than pure LLM inference when used for structured lookups. Brave is kept as the cheap fast pass (regex email/linkedin); Perplexity runs only when Brave returns nothing, providing web-grounded synthesis. LLM inference remains last resort for fields that can't be found online (seniority, role_type). Both Perplexity and LLM tiers reuse `OPENROUTER_API_KEY` — no additional config key.

### 2026-05-22 — `utils/` package extracted from `crm/`
**Decision:** `dedup.py` and `enrichment.py` live in `utils/`, not `crm/`  
**Rejected:** Keeping them in `crm/`  
**Rationale:** `crm/` is strictly Notion CRM objects (reads/writes to Notion). `dedup.py` is pure rapidfuzz + normalization. `enrichment.py` calls Apollo/Brave/Perplexity/OpenRouter with zero Notion dependency. The boundary makes both packages independently testable and reusable.

### 2026-05-22 — animation checked before video in handlers
**Decision:** Always check `message.animation` before `message.video`  
**Rejected:** Relying on message type alone  
**Rationale:** Telegram sets both `animation` and `video` flags for GIFs; wrong order causes GIFs to be misclassified as videos
