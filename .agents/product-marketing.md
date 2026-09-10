# Product Marketing Context

**Document version:** v1
**Last updated:** 2026-09-10

## Product Overview
**One-liner:** A CRM you actually own — five Notion databases kept current by AI, on a workspace you can host in Europe.

**What it does:** Notion Pilot deploys a working B2B CRM into your own Notion workspace, then keeps it up to date without data entry. Sales updates arrive by Telegram message or straight from an AI assistant (Claude, Claude Code, Cursor) over MCP; the assistant searches the CRM, dedups against what exists, and proposes a diff you approve before anything is written.

**Product category:** Self-hosted CRM automation for Notion. Adjacent shelves customers search: "Notion CRM template", "Notion CRM automation", "AI CRM data entry", "MCP CRM server".

**Product type:** Open-source, self-hosted software (MIT). Python 3.12 · uv · Docker/systemd · FastAPI cockpit. Optional hosted deploy wizard.

**Business model:** Free and open source; you run it. No per-seat licence. Costs are your own hosting plus whatever Notion plan you already pay for.

## Target Audience
**Target companies:** Small-to-mid B2B teams (roughly 3–30 people touching sales) who already live in Notion. Strong fit: European companies — especially French — where data residency is a procurement question. Engineering-adjacent businesses: consultancies, deep-tech, energy/industrial software, agencies.

**Decision-makers:** Founder / commercial director (buys it), sales lead (uses it daily), and a technically-comfortable operator (runs it — often a founder or the one engineer who likes infra).

**Primary use case:** Replace a spreadsheet CRM — or an abandoned Salesforce/HubSpot seat — with a Notion CRM that stays current because AI does the typing.

**Jobs to be done:**
- "Give me a pipeline I can trust on Monday morning without nagging the team."
- "Stop me retyping the same email thread into three databases."
- "Keep our customer data in Europe, on infrastructure we control."

**Use cases:**
- After a call or a meeting: log the activity, move the stage, set the next step — from a phone, in 30 seconds.
- Inbound email thread: create the contact, match the company, advance the deal, log the activity — one paste, one approval.
- Company enrichment: SIREN, NAF/APE, BODACC, RNE financials pulled from French open data instead of typed.
- Weekly pipeline review off shared Notion views rather than a rebuilt spreadsheet.

## Personas
| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| Sales lead (user) | Not doing admin | Updating the CRM costs 15 clicks nobody spends on a Friday | Dictate three sentences; the funnel moves |
| Founder / commercial director (champion + decision maker) | A pipeline they can trust | Numbers are stale, so forecasting is guesswork | A pipeline view that is current without policing anyone |
| Operator / engineer (technical influencer) | Not owning a fragile black box | Another SaaS to integrate and audit | Self-hosted, MIT, dry-run writes, no webhook |
| Buyer in a regulated/EU-sensitive org (financial + risk) | Where the data sits | Vendor can't answer the residency question | Notion Enterprise EU region; automation layer on your own server |

## Problems & Pain Points
**Core problem:** The CRM is not too simple or too complex — it is too tedious to keep current. So it goes stale, and once it is stale nobody trusts it, which removes the last reason to update it.

**Why alternatives fall short:**
- **Spreadsheet CRM:** no relations, one owner keeping it alive, copies emailed around, reports rebuilt by hand.
- **Salesforce / HubSpot:** per-seat cost limits who can even see the pipeline; rigid workflows; still requires the same manual updates, so it stalls for the same reason.
- **Notion CRM templates:** beautiful schema, zero maintenance story — the template is the easy afternoon.
- **Zapier / Make:** fire-and-forget automations with no dedup and no human review, so they create duplicates and erode trust faster than manual entry.
- **Claudeforce (Salesforce + Anthropic, Aug 2026):** validates the thesis exactly — but only if you already pay for Salesforce underneath.

**What it costs them:** 5–10 minutes per customer interaction that nobody actually pays, so the cost lands instead as a pipeline leadership silently stops believing. Forecasts become anecdote; follow-ups get missed; deals rot in a stage nobody moved.

**Emotional tension:** Quiet guilt about the CRM being behind. Low-grade dread before a pipeline review. The suspicion that the expensive tool was never the problem.

## Competitive Landscape
**Direct:** Notion CRM templates + manual upkeep — falls short because the schema was never the hard part.
**Direct:** Salesforce / HubSpot / Pipedrive — fall short on per-seat visibility, rigidity, and the same unpaid data-entry tax.
**Secondary:** Zapier / Make / n8n glue — falls short with no dedup, no matching, no human-in-the-loop, so data quality degrades.
**Secondary:** Claudeforce / "Salesforce in Claude" — right idea, requires the Salesforce estate; no self-hosting, no EU-by-default story.
**Indirect:** Excel / Google Sheets, or no CRM at all — falls short the moment more than one person needs the truth.

## Differentiation
**Key differentiators:**
- **You own the system of record.** It is your Notion workspace, your schema, your data — not a vendor's database.
- **EU hosting is real, not a promise.** Notion Enterprise pins data at rest to eu-central-1 (Frankfurt), free on that plan; the automation layer runs on your own server.
- **Human-in-the-loop is enforced in the tools**, not in the docs: write tools return a dry-run preview unless `confirm=true`.
- **Dedup before write** — email and LinkedIn exact match, then fuzzy name + company. Ambiguous matches escalate to a human.
- **French open-data enrichment** built in (SIREN, NAF/APE, BODACC, RNE financials).
- **Two capture surfaces nobody else pairs:** Telegram for the 30-second update, MCP for the AI assistant.
- **The schema evolves with you.** Deploy a standard CRM, then reshape it in Notion; an agent with Notion MCP adapts to the structure you grew into.

**How we do it differently:** We do not replace the CRM interface — we remove the need to open it. The assistant proposes, the human approves, Notion stays the source of truth.

**Why that's better:** Adoption stops depending on discipline. The data stays clean because matching happens before the write, not after.

**Why customers choose us:** They already trust Notion, they refuse another per-seat SaaS, and someone in the building cares where the data lives.

## Objections
| Objection | Response |
|-----------|----------|
| "Notion isn't a CRM." | Correct, not out of the box. It is a relational database with views. The schema plus a maintenance layer is what makes it a CRM — that is the product. |
| "Can the AI corrupt our data?" | Writes are dry-run by default and need an explicit confirmation. Ambiguous matches are escalated, never guessed. |
| "Who maintains it?" | You do — it is self-hosted, and that is a real cost. Name the owner during the pilot. We say this on the page rather than hiding it. |
| "Where does our data live?" | Your Notion workspace (EU region available on Enterprise) plus your own server. No third-party SaaS in the path. |
| "How does this compare to Salesforce?" | Different philosophy, not feature parity. Need territory management or CPQ? Not this. CRM dying of neglect? This. |
| "It's a one-person open-source project." | MIT licensed, CI-gated, and you host it — worst case you keep the databases and the code. Feedback shapes the roadmap directly. |

**Anti-persona:** Teams needing CPQ, quote approval chains, territory management or a certified vendor of record. Non-technical solo users with nobody to run a container. Companies not already on Notion — the migration cost swamps the benefit.

## Switching Dynamics
**Push:** The spreadsheet is out of date and everyone knows it. A pipeline review went badly. An abandoned CRM seat is being paid for.
**Pull:** "I can keep using Notion, and the updates just happen." Data stays in Europe. No per-seat cost to widen visibility.
**Habit:** The spreadsheet works well enough for the one person maintaining it; the CRM tab is already open; nobody wants to re-teach a team.
**Anxiety:** "Will the AI write nonsense into my pipeline?" "Am I signing up to run infrastructure?" "Is this abandoned in six months?"

## Customer Language
**How they describe the problem:**
- "Nobody updates it."
- "The CRM is always behind."
- "I don't trust the pipeline numbers."
- "It's 15 clicks to update one opportunity."
- "Opening the tool was a chore, every day."

**How they describe us:**
- "The CRM updates itself."
- "I just paste the email and say go."
- "It's our Notion, not someone else's database."

**Words to use:** own, current, up to date, approve, preview, your workspace, Europe, relations, self-hosted, no data entry, source of truth.
**Words to avoid:** autonomous, fully automatic, set-and-forget, AI-powered (empty), enterprise-grade (unearned), guaranteed, GDPR-compliant (as a claim about us), replaces Salesforce, seamless, revolutionary.

**Glossary:**
| Term | Meaning |
|------|---------|
| Leads / Deals | Same database; the pipeline. Labelled "Leads" in the reference deployment |
| Activities | Timeline entries — call, email, meeting, demo, proposal — linked to deal, person and company |
| Meetings | Separate Notion database holding meeting notes; related from Activities and People. Human-maintained |
| MCP | Model Context Protocol — how an AI assistant gets tools to read/write the CRM |
| Dry run | A write tool returning a preview instead of writing; the default |
| Cockpit | The self-hosted web UI for deploy, inspection and chat |

## Brand Voice
**Tone:** Candid and technical without jargon. Says the trade-off out loud before you find it.
**Style:** Direct, concrete, specific. Short sentences. Real property names and real numbers over adjectives. Never hypes.
**Personality:** Honest, precise, unfussy, quietly opinionated, engineer-to-engineer.

## Proof Points
**Metrics:** None published — and none should be invented. Do not cite ROI, adoption or time-saved figures until measured.
**Customers:** One real reference deployment (Artelys — B2B energy/optimisation consultancy): 1,281 companies, 1,859 people, 30 open leads, 47 logged activities. Naming approval required before external use.
**Testimonials:** None yet. Collect from the first three pilot users.
**Value themes:**
| Theme | Proof |
|-------|-------|
| Human-in-the-loop is real | `confirm=false` is the default in every write tool (`notion_pilot/mcp/tools.py`) |
| Dedup before write | Email/LinkedIn exact match, then fuzzy name + company; duplicate scans surfaced for review |
| EU hosting | Notion data residency eu-central-1, free on Enterprise; automation layer self-hosted |
| No third-party SaaS | No webhook, no relay; Notion API called directly from your server |
| Open source | MIT, CI-gated, public repo |

## Goals
**Business goal:** Move from single-operator dogfooding to a handful of real external users who deploy the CRM and connect an assistant.
**Conversion action:** Click **Deploy to Notion** and complete the OAuth deploy; secondary action is connecting an AI assistant over MCP.
**Current metrics:** Unknown — no analytics on the landing page yet. Worth adding before any launch push.

## Known gaps to fix before a launch push
Documented in `docs/notion-pilot-crm-readiness-audit.md`: the deploy creates 3 of 5 databases (no Activities, so activity logging fails on a fresh workspace), `Companies.Activities` is a multi-select rather than a relation, the bootstrapped schema lacks the pipeline formula properties, and OAuth tokens are not persisted so background automation cannot serve a connected workspace. The homepage should not promise past these.

## Changelog
*Newest first. One line per revision: what changed and why.*
- v1 (2026-09-10) — Initial context, auto-drafted from the codebase, README, executive deck and the readiness audit; positioning centred on "a CRM you actually own, kept current by AI, hostable in Europe".
