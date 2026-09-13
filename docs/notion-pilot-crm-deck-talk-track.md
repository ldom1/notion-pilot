# Talk track — Notion Pilot CRM executive deck

Companion sheet for `docs/notion-pilot-crm-executive-deck.pptx` (15 main slides + 4 appendix).
Copy lives in `docs/marketing/crm-deck-content.json`; rebuild with `uv run python scripts/marketing/generate_crm_deck.py`. See `docs/marketing/README.md`.

**Audience** — management / decision-makers currently running an Excel-based CRM.
**Duration** — 20 min main path + 10 min Q&A. Appendix only on demand.
**Thesis** — a CRM does not fail because the tool is bad; it fails because nobody updates it. Notion fixes *where* the CRM lives; Notion Pilot fixes *how it stays current*.

**Ground rules for the speaker**
- Sell adoption and data freshness, never feature count.
- Every claim on screen is verifiable in the repo. Do not add numbers that aren't.
- Say the trade-offs out loud (S13) — that slide is what buys the pilot.
- The slides carry no speaker scaffolding — each slide's purpose is the first line of its PowerPoint notes.

---

## Part 1 — the foundation

**S1 · Stop maintaining your CRM. Start trusting it.** *(60s)*
Open: "Everyone here has watched a CRM go stale. Not because the tool was wrong — because keeping it current was somebody's third priority."
- Read the spine once: capture anywhere → structure in Notion → maintain with AI under human control.
- Promise: a pipeline you trust on Monday morning, without turning the team into data entry clerks.
→ "Let me start where you are today."

**S2 · Your pipeline is a spreadsheet nobody trusts after Tuesday** *(90s)*
Open: "Excel isn't wrong. It never crashes. It just quietly goes out of date — and that's the harder problem, because it never announces itself."
- Walk rows 1–4: one owner, no relations, copies emailed around, reporting rebuilt by hand.
- The real cost isn't the tool, it's leadership quietly stopping to trust the numbers.
- Last row is the **bridge**, not the point: swapping in a heavyweight CRM stalls on cost and rigidity, and you're stale again.
→ "So the answer is a CRM where the team already works."

**S3 · Notion is already a database. Let's make it your CRM.** *(75s)*
Open: "Notion is already a relational database. We just have to shape it like a CRM."
- Companies / People / Deals, linked by relations, with notes and context on the same page.
- No CRM training curve — people already know Notion. No per-seat CRM licence to widen visibility.
- If asked: in the Artelys deployment the Deals database is labelled **Leads**. Same object.
→ "Here's the whole model on one slide."

**S4 · Five databases, one relational spine** *(90s)*
Open: "This is the entire data model. Five tables, and everything hangs off the deal."
- Left to centre: a company has many deals, a contact has many deals. Right: a deal has many activities, and meeting notes attach to those.
- Read the badges out loud — they are the honest part. **Four are automated. Meetings is human.**
- If asked where meetings live: they are their own database *and* `🤝 Meeting` is an Activity type. Both are true — the activity row is the timeline entry, the meeting page holds the notes.
- The callout also concedes that the one-click deploy creates only three of the five. Say it before someone finds it.
→ "Five tables, one workspace — and here's what that unlocks."

**S5 · One workspace. Every deal, with its whole story attached.** *(60s)*
Open: "Pipeline, projects and customer context stop being three tools."
- Each deal carries its own linked timeline — history is where you look for it.
→ "Which brings us to the thing you'd miss most from Excel."

**S6 · The weekly report that builds itself** *(90s)*
Open: "The honest objection to leaving Excel is the charts. So let's take it head on."
- Four KPIs, each with its Notion mechanic: rollups, formulas, grouped views. Point at the mechanic, not the metric — that's what makes it credible.
- Land the callout: every edit recomputes the numbers, no manual rebuild.
- Say the limit out loud: chart blocks and dashboards are **configuration work**, not something shipped by default. This is not a BI product.
→ "One more question that always comes up before anyone commits."

**S7 · Your data, in your region, under your IT's rules** *(75s)*
Open: "Where does the data actually live, and who controls access?"
- Storage region first — it's usually the blocker: **EU data residency is a Notion Enterprise option, to be confirmed with Notion.** Say "to be confirmed", not "guaranteed".
- Then SSO / SCIM / audit log: access governance sits with IT, not inside the CRM.
- Teamspaces scope who sees which pipeline.
→ "That's the foundation. Now the part Notion alone does not solve."

## Part 2 — the acceleration

**S8 · The challenge is not managing a CRM. It is keeping the CRM alive.** *(90s)*
Open: "Notion solves collaboration. Notion does *not* solve maintenance."
- Customer data is born in a call, an email, a Telegram thread — never in a database form.
- Four failure modes on screen; the root cause is the same 5–10 minutes of retyping nobody pays.
→ "That gap is exactly what Notion Pilot fills."

**S9 · Notion Pilot does the typing. You keep the judgement.** *(75s)*
Read the quote out loud, slowly: **"The AI proposes. The operator validates. Notion remains the source of truth."**
- Walk the four stages left to right; the highlighted middle box is the only new thing in your stack.
- Self-hosted: your server, your Notion token. Not a SaaS, not an autonomous sales agent.
→ "So where does capture actually happen?"

**S10 · The CRM comes to your team, not the other way round** *(90s)*
Open: "Nobody changes tools. The CRM comes to them."
- Telegram, the most mature surface: `/lead`, `/people`, `/company`, `/deal` — conversational, the bot asks for the fields you skipped.
- AI assistants over MCP: Claude or Cursor can search the CRM and prepare updates from a call note or an email thread.
- Web cockpit for deploy/inspect; email routing optional.
- **Do not say `/enrich`** — enrichment runs through the MCP tools and the open-data skill, not a Telegram command.
- The conversation panel on the right is a **stylised illustration**, labelled as such on the slide. If someone asks to see the real thing, open Telegram — don't let it pass for a screenshot.
→ "Speed only helps if the data is clean."

**S11 · Fast automation that creates duplicates is just faster mess** *(75s)*
Open: "Automation that creates duplicates makes the problem worse. So this comes before speed."
- Exact matching on email and LinkedIn; fuzzy name + company match to catch near-misses *before* the write.
- Duplicate scans surface conflicts for a human, they don't silently merge.
- French open-data enrichment (SIREN, NAF/APE, BODACC, RNE financials) where configured — deployment-specific, not a universal default.
→ "Here's what that looks like on one real deal."

**S12 · One message on Monday. A closed deal with its whole history.** *(90s)*
Open: "One deal, end to end, in the words a salesperson would actually type."
- Walk the five chevrons; pause on **Review** — the operator sees the preview before anything is written.
- Then contrast the two panels: one sentence typed on the left, four linked records on the right. That contrast is the whole product.
- Close: Won *and* Lost both keep their context. Next year, "why did we lose this" is a search, not a memory.
→ "Before the ask, what you'd actually be adopting."

**S13 · Nothing gets written that you haven't seen** *(75s)*
Open: "I want to be precise about the trade-offs."
- Left column then right column. Every write is a dry-run preview first; a real write needs explicit confirmation.
- Say the cost out loud: operator-owned and configurable means someone owns config, secrets and monitoring. That is not zero-config.
→ "Which is why I'm proposing something small."

## Part 3 — close

**S14 · One channel. One entity. Four weeks.** *(75s)*
Open: "One channel, one entity type, two to four weeks."
- Walk the three step cards. Success criterion: one pipeline view leadership trusts without asking sales to reconcile it.
→ "So here's exactly what that costs you, and what you get."

**S15 · Let's run your next real deal through it** *(90s — do not rush this slide)*
Open: "One scoping call, then a four-week pilot on your own workspace. Nothing to migrate, nothing to sign."
- Left panel: what you need from them. Keep it deliberately small — a workspace, one channel, one owner, two hours of a rep's time. If they hesitate, shrink it further rather than defending it.
- Right panel: what they hold at the end. Read the last item slowly — *a pipeline view leadership trusts* — it is the whole promise from S1, delivered.
- **The ask:** name a date for the scoping call before the room breaks up. A "send me something" is not a yes.
- Check the booking link is filled in before you ever present this.

---

## Appendix triggers

| Question from the room | Jump to |
|---|---|
| "How does the AI actually write to Notion?" | A1 — MCP toolset, dry-run / confirm |
| "Where is it hosted? Is it secure?" | A2 — self-hosted stack, secrets |
| "Has anyone actually run this?" | A3 — Artelys deployment pattern |
| "What's optional vs default?" | A4 — what the deploy creates vs what it doesn't |

## Objection handling

**"Notion isn't a CRM."** Correct — not out of the box. It's a relational database with views. What makes it a CRM is the schema plus a maintenance layer. That's the proposal.

**"Where's the Meetings database?"** Back to **S4** — it's there, on the right, marked *manual*. Meetings is a real database holding notes and attendees, related from both Activities and People; `🤝 Meeting` is *also* an Activity type, which is the timeline entry for it. Notion Pilot does not write to Meetings, and Notion's own MCP server exposes `notion-query-meeting-notes` if you want an agent reading them.

**"Does our data stay in the EU?"** Back to **S7**. The records live in your own Notion workspace under your Notion plan; a choice of storage region is a Notion Enterprise option, and the current terms should be confirmed with Notion directly before anyone commits. Notion Pilot itself runs on your infrastructure and keeps no copy beyond a runtime cache. Never assert a certification or a residency guarantee from this deck.

**"Can the AI corrupt the CRM?"** Write tools default to dry-run; a real write requires an explicit confirmation flag. Ambiguous matches are escalated to a human instead of resolved automatically.

**"What about KPIs and forecasting?"** Back to **S6** — pipeline by stage, win rate, ageing and activity volume all come from rollups, formulas and grouped views. Dashboards and chart blocks are configuration work. No BI product is in scope.

**"How does it compare to Salesforce / HubSpot?"** Different philosophy, not feature parity. If you need territory management or CPQ, this isn't it. If your CRM dies of neglect, this is.

**"Who maintains it?"** Someone owns config, secrets and monitoring. Name that person as part of the pilot.

**"What does it cost?"** Notion seats you likely already hold, plus your own hosting. No per-seat CRM licence.

## Never say

- Invented metrics, ROI figures or customer counts.
- Certification or data-residency **guarantees** — S7 says "to be confirmed with Notion", so should you.
- "Replaces Salesforce."
- "There is no Meetings database" — there is; see S4. What's true is that Notion Pilot doesn't write to it, and the one-click deploy doesn't create it.
- `/enrich` as a Telegram command.
- "Here's a screenshot" for the S10 conversation panel — it's an illustration.
