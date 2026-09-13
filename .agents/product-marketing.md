# Product Marketing Context

**Document version:** v3
**Last updated:** 2026-09-11

## Product Overview
**One-liner:** A self-hosted CRM you actually own — Notion as the system of record, AI doing the typing, every write waiting for your go.
**What it does:** Deploys a relational CRM into the customer's Notion workspace (Companies, People, Leads, Activities, Meetings), then keeps it current from the team's existing AI assistant (Notion MCP). French companies enrich automatically from open data (SIRENE, filings); companies outside France are skipped. Nothing is written without a human preview. Telegram capture exists in the product; it is not the homepage story.
**Product category:** CRM / Notion CRM / AI-assisted sales ops (customers search "CRM in Notion", "Salesforce alternative Europe", "AI update CRM").
**Product type:** Self-hosted software + public Notion integration (OAuth deploy wizard), not multi-tenant SaaS.
**Business model:** Open-source (MIT). No seat price. Customer brings Notion (Enterprise if they want EU data residency) and their own host.

## Target Audience
**Target companies:** Small sales / BD teams (≈2–10) working with **French companies**, already in Notion or willing to put the CRM there, often EU-sensitive (data residency, no US CRM estate).
**Decision-makers:** Head of sales / BD, founder-operator, IT or security on Enterprise Notion (residency, SSO). Champion is usually the person who already lives in Notion and hates the CRM.
**Primary use case:** Keep the pipeline true without fifteen clicks between meetings.
**Jobs to be done:**
- Hire it so one email becomes four correct records — I only approve
- Hire it so the CRM I own in Notion does not rot the week I get busy
- Hire it so my existing assistant (Claude, Cursor) can operate the pipeline without opening Notion
**Use cases:**
- Paste a client email into Claude/Cursor; approve the diff
- Enrich a French company from SIREN / RNE instead of typing firmographics

## Personas
| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| User (AE / BD) | Speed, not opening the CRM | Fifteen clicks; Friday pipeline is a lie | Paste the thread; approve; done |
| Champion (Notion-native ops) | Schema they can reshape | Notion is a database, not a CRM, and nobody feeds it | Deployed schema + automation that follows their properties |
| Decision maker (sales lead) | A pipeline they can believe on Monday | Dashboards on stale rows | Formulas that stay fed |
| Financial buyer | No new seat estate | Salesforce/HubSpot price + migration | Notion they already pay for; Pilot is self-hosted |
| Technical / security | EU region, permissions, HITL | Shadow AI writing into the CRM | Self-hosted; assistant sees what you see; dry-run default; residency is Notion Enterprise — confirm with Notion |

## Problems & Pain Points
**Core problem:** CRMs don't fail on missing features. They fail on data entry. The schema is built in an afternoon; keeping it true is every afternoon after that.
**Why alternatives fall short:**
- Salesforce + Claudeforce: the idea (chat over live pipeline) ships under a licence, a migration, and a seat price
- Spreadsheets: no relations — rename a company, miss a tab
- Notion alone: collaboration and databases exist; maintenance does not
- Autopilot AI CRMs: write without a preview
**What it costs them:** Stale stages, overdue next steps, Monday reviews on fiction, hours re-typing what was already in the email.
**Emotional tension:** Shame that the CRM is a lie; fear of an agent writing the wrong thing; fatigue of being the person who "just update Salesforce".

## Competitive Landscape
**Direct:** Other Notion CRM templates / consultancies — schema without a feeder; no HITL agent loop.
**Secondary:** Salesforce / HubSpot + AI plugins (Claudeforce) — same job, vendor estate underneath.
**Indirect:** "We'll be better about updating the CRM" / a shared spreadsheet / an EA — discipline that decays at the speed of the busiest week.

## Differentiation
**Key differentiators:**
- System of record is the customer's Notion, not ours
- Human-in-the-loop by default (preview, then `go`)
- Self-hosted automation; EU residency is a Notion Enterprise option (never a Pilot guarantee)
- French open-data enrichment (SIRENE / filings); non-FR skipped
**How we do it differently:** We deploy the schema, then the assistant reads *their* properties through Notion MCP — add a field Monday, it can fill it Tuesday.
**Why that's better:** They keep governance, collaboration, and the workspace they already share. We only do the typing.
**Why customers choose us:** They want Claudeforce's idea without Salesforce; they already live in Notion; they cannot send pipeline data to a US SaaS.

## Objections
| Objection | Response |
|-----------|----------|
| "Does our data stay in the EU?" | Records live in their Notion workspace. Region is a **Notion Enterprise option, to confirm with Notion**. Pilot runs on their infrastructure and keeps no copy beyond a runtime cache. Never certify or guarantee residency. |
| "Will the AI write garbage into the CRM?" | Dry-run is the default. Every write is a preview until they say go. Ambiguous matches escalate. |
| "We don't only sell to French companies." | FR firms enrich from open data. Others can be stored; they are not auto-enriched. Be explicit — this is a scoped CRM, not a global Dun & Bradstreet. |
| "Isn't this just a Notion template?" | The template is the afternoon. The product is keeping it true. |

**Anti-persona:** Teams that need a global enrichment graph, a multi-tenant SaaS CRM, or an agent that writes without approval. Teams not on Notion and unwilling to move.

## Switching Dynamics
**Push:** CRM is stale; Claudeforce made the chat-shaped CRM feel inevitable; Salesforce quote landed.
**Pull:** Own the database; approve every write; host in Europe; French companies fill themselves.
**Habit:** Fifteen clicks they already skip; "we'll update it on Friday".
**Anxiety:** Agent writes the wrong company; Notion isn't "a real CRM"; Enterprise residency is not automatic.

## Customer Language
**How they describe the problem:**
- "Fifteen clicks to update an opportunity"
- "Nobody updates the CRM"
- "Which version is current?"
**How they describe us:**
- (sparse — early) "CRM you actually own"
- "Nothing reaches Notion that you haven't approved"
**Words to use:** system of record, preview, go, pipeline, stale, self-hosted, approve, relations (not "spreadsheet tabs")
**Words to avoid:** confirm=true / MCP jargon on the marketing page; residency **guarantees**; invented ROI; "Meetings is just an activity type" (it is a real database); claiming collaboration is a Pilot feature (it is native Notion)
**Glossary:**
| Term | Meaning |
|------|---------|
| HITL | Human-in-the-loop — preview then approve |
| Dry run | Write tools return a preview until confirmed |
| Leads | The deals pipeline database |
| Open data | French public registries (SIRENE, BODACC, RNE) |

## Brand Voice
**Tone:** Direct, adult, slightly dry. No hype, no exclamation marks.
**Style:** Specific scenes (Friday 17:42, Voltaris) over adjectives. Show the record, don't claim "powerful AI".
**Personality:** Precise, sceptical of CRM theatre, respectful of Notion, honest about scope (France, Enterprise residency to confirm).

## Proof Points
**Metrics:** None invented. Film timings (21s pipeline) and schema facts only.
**Customers:** Not for public use yet. Artelys exists in internal deck appendix — do not put on the site without approval.
**Testimonials:** None on the marketing site yet.
**Value themes:**
| Theme | Proof |
|-------|-------|
| HITL | Assistant preview / go; dry-run default |
| Own the DB | OAuth deploy into *their* Notion |
| France | SIRENE/RNE enrichment; non-FR skipped (footer) |
| EU | Notion Enterprise region — confirm with Notion; Pilot self-hosted |
| Collaboration | Native Notion workspace, not a Pilot feature |

## Goals
**Business goal:** Qualified deploys by EU/FR sales teams who will run a real deal through it for a week.
**Conversion action:** Deploy the CRM to Notion (`/auth/notion`).
**Current metrics:** Not instrumented on the landing page.

## Changelog
*Newest first. One line per revision: what changed and why.*
- v3 (2026-09-11) — Wizard public-integration OAuth ≠ Notion official MCP OAuth; Claude reaches the deployed CRM via a second connection to the same workspace.
- v2 (2026-09-11) — Homepage capture is the AI assistant only; Telegram is a product capability, not the landing story.
- v1 (2026-09-11) — Initial context, auto-drafted from landing, README, talk-track "never say" list, and CRM objectives (FR enrichment, HITL, Notion-as-SoR).
