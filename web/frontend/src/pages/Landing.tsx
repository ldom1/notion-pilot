import { useEffect, useState } from "react";
import { fetchStatus } from "../api/client";
import { SetupWizard } from "../features/setup/SetupWizard";
import { Spinner } from "../components/Spinner";
import "../styles/landing.css";

type CheckState = "idle" | "checking" | "authenticated" | "unauthenticated" | "setup";

const CLAUDEFORCE_URL =
  "https://www.salesforce.com/news/press-releases/2026/08/26/salesforce-and-anthropic-announce-claudeforce/";
const NOTION_MCP_URL = "https://mcp.notion.com/mcp";

// Preformatted blocks: template literals, because JSX collapses whitespace at
// line boundaries and would eat the indentation.
const PASTED_EMAIL = `Subject: RE: optimisation platform — next steps

Hi, thanks for Tuesday's demo. The team is convinced on the solver
side. We need a security review before signing, and our budget
window closes 15 December. Can you send a proposal for 12 licences?

— Camille Dubois, Head of Grid Analytics, Voltaris Énergie`;

const MCP_SNIPPET = `# Claude Code
claude mcp add --transport http notion ${NOTION_MCP_URL}
# then run /mcp and complete the OAuth flow

# Cursor — .cursor/mcp.json
{ "mcpServers": { "notion": { "url": "${NOTION_MCP_URL}" } } }`;

const COMPANIES = [
  ["Voltaris Énergie", "Energy", "Tier 1", "lp-pill-amber", "843 219 004", "412 M€", "3 contacts", "2 days ago", "Active", "lp-pill-teal"],
  ["Néorégie Grid", "Public Sector", "Tier 2", "lp-pill-grey", "512 008 771", "96 M€", "1 contact", "11 days ago", "Prospect", ""],
  ["Hexalis Industries", "Industry", "Tier 2", "lp-pill-grey", "779 431 250", "1.2 Md€", "5 contacts", "34 days ago", "Prospect", ""],
  ["Cerena Renouvelables", "Energy", "Tier 3", "lp-pill-grey", "901 774 663", "28 M€", "2 contacts", "6 days ago", "Active", "lp-pill-teal"],
];

const ENTITIES: { icon: string; name: string; props: string; auto: boolean }[] = [
  { icon: "🏭", name: "Companies", props: "Sector · Tier · SIREN · CA · Country", auto: true },
  { icon: "⚡", name: "Activities", props: "Type · Date · Outcome · Next Step · Duration", auto: true },
  { icon: "👥", name: "People", props: "Position · Seniority · Email pro · LinkedIn · Role Type", auto: true },
  { icon: "🤝", name: "Meetings", props: "Notes · Attendees · Linked deal", auto: false },
];

const RELATIONS = [
  ["Companies 1 → n Leads", "a client can run several deals at once"],
  ["People n → 1 Companies", "every contact sits under one organisation"],
  ["Leads n → n People", "Primary contact plus everyone else in the loop"],
  ["Activities n → 1 Leads", "and back to the person and the company"],
  ["Meetings n → n People", "meeting notes attached to whoever was in the room"],
];

const BOARD: { stage: string; count: string; deals: [string, string][]; won?: boolean }[] = [
  { stage: "Prospect", count: "3", deals: [["Hexalis — Platform licence", "—  ·  cold"], ["Néorégie — Study", "18 k€"]] },
  { stage: "Qualified", count: "2", deals: [["Cerena — Consulting", "45 k€  ·  40 %"]] },
  { stage: "Discovery / First Meeting", count: "3", deals: [["Voltaris — Platform licence", "120 k€  ·  50 %"]] },
  { stage: "Proposal Sent", count: "1", deals: [["Astria — Optimisation", "80 k€  ·  60 %"]] },
  { stage: "Negotiation", count: "1", deals: [["Vireo — Renewal", "64 k€  ·  75 %"]] },
  { stage: "Closed Won", count: "—", deals: [["Kaleo — Licence", "52 k€  ·  ✅"]], won: true },
];

const DECAY = [
  ["Deal Age (days)", "Computes perfectly — from a stage nobody moved."],
  ["Days Since Last Activity", "Computes perfectly — from an activity nobody logged."],
  ["Stale Deal", "Flags everything, because everything looks stale."],
];

const AGENT_STEPS = [
  ["Search before write", "Every proposal starts with a lookup — email, LinkedIn, then fuzzy name plus company — so an existing record gets updated instead of duplicated."],
  ["Dry run by default", "Write tools return a preview unless you pass confirm=true. The default answer to “should I write this?” is no."],
  ["You approve the diff", "A table of exactly what changes, per database. Ambiguous matches are escalated instead of guessed."],
  ["Same for calls", "Dictate or paste your notes after a call. Type 📞 Call, an outcome, a next step with a date — the follow-up stops living in your head."],
];

// ── Landing page ──────────────────────────────────────────────────────────────

export default function Landing() {
  const [checkState, setCheckState] = useState<CheckState>("idle");
  const isSetup = new URLSearchParams(window.location.search).get("connected") === "1";

  useEffect(() => {
    setCheckState("checking");
    fetchStatus()
      .then(() => {
        // Authenticated — show setup wizard if coming from OAuth, else go straight to cockpit
        setCheckState(isSetup ? "setup" : "authenticated");
        if (!isSetup) window.location.href = "/cockpit";
      })
      .catch(() => {
        setCheckState("unauthenticated");
      });
  }, [isSetup]);

  if (checkState === "idle" || checkState === "checking" || checkState === "authenticated") {
    return <Spinner fullPage />;
  }

  if (checkState === "setup") {
    return (
      <div className="lp">
        <nav className="lp-nav">
          <div className="lp-brand">
            <span className="lp-mark">P</span> Notion Pilot
          </div>
          <a href="/auth/logout" className="lp-hero-note">
            Sign out
          </a>
        </nav>
        <main className="lp-wrap lp-section">
          <div style={{ maxWidth: 480, margin: "0 auto" }}>
            <SetupWizard
              onComplete={() => {
                window.location.href = "/cockpit";
              }}
              onSkip={() => {
                window.location.href = "/cockpit";
              }}
            />
          </div>
        </main>
      </div>
    );
  }

  // unauthenticated — the marketing homepage
  return (
    <div className="lp">
      <nav className="lp-nav">
        <div className="lp-brand">
          <span className="lp-mark">P</span> Notion Pilot
        </div>
        <div className="lp-navlinks">
          <a className="lp-btn lp-btn-ghost" href="#model">
            The data model
          </a>
          <a className="lp-btn lp-btn-primary" href="/auth/notion">
            Deploy to Notion
          </a>
        </div>
      </nav>

      {/* ── hero ────────────────────────────────────────────────────────── */}
      <header className="lp-hero">
        <div className="lp-wrap lp-hero-grid">
          <div>
            <span className="lp-eyebrow">Notion CRM · AI-maintained · EU-hosted</span>
            <h1 className="lp-h1">
              Your CRM doesn't have a feature problem.
              <br />
              <em>It has a data-entry problem.</em>
            </h1>
            <p>
              Salesforce just conceded the point. In August 2026 it put its entire CRM inside Claude
              so that sellers never have to open Salesforce again. The lesson isn't about Salesforce
              — it's that <strong>a CRM never dies of missing features. It dies of nobody updating
              it.</strong>
            </p>
            <p className="lp-mt">
              Notion Pilot is that idea for a CRM you actually own: five Notion databases, kept
              current from Telegram or straight from your AI assistant, on a workspace you can host
              in Europe.
            </p>
            <div className="lp-cta-row">
              <a className="lp-btn lp-btn-primary lp-btn-lg" href="/auth/notion">
                Deploy the CRM to Notion
              </a>
              <a className="lp-btn lp-btn-ghost lp-btn-lg" href="#model">
                See the data model
              </a>
            </div>
            <p className="lp-hero-note">
              Self-hosted · every write needs your confirmation · Notion stays the source of truth
            </p>
          </div>

          <aside className="lp-news">
            <span className="lp-news-date">26 August 2026 · Salesforce newsroom</span>
            <h3>Salesforce and Anthropic announce Claudeforce</h3>
            <p>
              “Salesforce in Claude” ships as a plugin with 37 prebuilt sales skills — meeting prep,
              deal-health review, pipeline review, composing emails, updating records — so sellers
              reason over live pipeline and act on it without opening the CRM. Open beta from
              September.
            </p>
            <ul>
              <li>
                <span className="lp-tick">1</span>
                <span>
                  <strong>People love chat and tolerate CRMs.</strong> Fifteen clicks to update an
                  opportunity is a task nobody does on a Friday.
                </span>
              </li>
              <li>
                <span className="lp-tick">2</span>
                <span>
                  <strong>The governance survives.</strong> Permissions, workflows and audit trail
                  stay in the system of record — no record access, no agent access.
                </span>
              </li>
            </ul>
            <p className="lp-src">
              Source: <a href={CLAUDEFORCE_URL}>Salesforce press release</a>. Framing inspired by a
              public post from Samuel Cherubin (Kokoro).
            </p>
          </aside>
        </div>
      </header>

      {/* ── why it matters ──────────────────────────────────────────────── */}
      <section className="lp-section lp-section-tint">
        <div className="lp-wrap">
          <span className="lp-eyebrow">The signal</span>
          <h2 className="lp-h2">Why that announcement matters more than it looks</h2>
          <p className="lp-lede">
            Two things happened at once, and the second one is the reason this page exists.
          </p>
          <div className="lp-cards">
            <div className="lp-card">
              <div className="lp-card-num">1</div>
              <h3>The interface was the bottleneck</h3>
              <p>
                Nobody abandons a CRM because it lacks a field. They abandon it because updating one
                opportunity costs fifteen clicks between two meetings. Dictating three sentences on
                the way to the car park costs nothing — so that is the interaction that actually
                happens.
              </p>
            </div>
            <div className="lp-card">
              <div className="lp-card-num">2</div>
              <h3>The process still holds</h3>
              <p>
                The agent inherits the CRM's permissions rather than bypassing them. No access to a
                record means no access for the AI either. Workflows, business rules and audit trail
                all survive — which is what makes it usable in a company rather than a demo.
              </p>
            </div>
            <div className="lp-card">
              <div className="lp-card-num">3</div>
              <h3>But it needs Salesforce underneath</h3>
              <p>
                Claudeforce is only available if you already pay for the CRM it sits on. The
                interesting question is what happens when your system of record is something you
                already own, shape yourself, and can keep inside the EU.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── step 1 · Notion ─────────────────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-wrap">
          <span className="lp-eyebrow">Step 1 — the system of record</span>
          <h2 className="lp-h2">Start with Notion. You already have it.</h2>
          <p className="lp-lede">
            Notion is a relational database wearing the interface of a document. Your team already
            knows how to use it, every seat can read the pipeline without a per-seat CRM licence, and{" "}
            <strong>on the Enterprise plan your data sits in Frankfurt, not Oregon.</strong>
          </p>

          <div className="lp-cards lp-mb-xl">
            <div className="lp-card">
              <h3>Real relations</h3>
              <p>
                A contact belongs to a company; a deal points at both. Rollups and formulas
                recompute on every edit — no VLOOKUP, no rebuild.
              </p>
            </div>
            <div className="lp-card">
              <h3>Views, not reports</h3>
              <p>
                Board, table, calendar and timeline are the same rows seen differently. Leadership
                gets a shared view instead of an emailed export.
              </p>
            </div>
            <div className="lp-card">
              <h3>Shaped by you</h3>
              <p>
                Add <code>SIREN</code>, <code>Deal Temperature</code> or <code>Weighted Value</code>{" "}
                in a click. No admin, no consultant, no change request.
              </p>
            </div>
            <div className="lp-card">
              <h3>European by choice</h3>
              <p>
                Enterprise workspaces can pin data at rest to the EU region. Free of charge, and
                existing workspaces can be migrated on request.
              </p>
            </div>
          </div>

          <div className="lp-frame">
            <div className="lp-frame-bar">
              <span className="lp-dot" /> 🏭 Companies
              <div className="lp-tabs">
                <span className="lp-tab is-on">Table</span>
                <span className="lp-tab">Board</span>
                <span className="lp-tab">By tier</span>
              </div>
            </div>
            <div className="lp-scroll">
              <table className="lp-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Sector</th>
                    <th>Tier</th>
                    <th>SIREN</th>
                    <th>CA</th>
                    <th>People</th>
                    <th>Last activity</th>
                    <th>CRM status</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPANIES.map(([name, sector, tier, tierCls, siren, ca, people, last, status, statusCls]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>
                        <span className="lp-pill">{sector}</span>
                      </td>
                      <td>
                        <span className={`lp-pill ${tierCls}`}>{tier}</span>
                      </td>
                      <td>{siren}</td>
                      <td>{ca}</td>
                      <td>
                        <span className="lp-rel">{people}</span>
                      </td>
                      <td>{last}</td>
                      <td>
                        <span className={`lp-pill ${statusCls}`}>{status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="lp-hero-note">
            Firmographics like <code>SIREN</code>, <code>CA</code> and <code>Résultat net</code> are
            filled from French open data — no manual lookup.
          </p>
        </div>
      </section>

      {/* ── step 2 · the data model ─────────────────────────────────────── */}
      <section className="lp-section lp-section-tint" id="model">
        <div className="lp-wrap">
          <span className="lp-eyebrow">Step 2 — the data model</span>
          <h2 className="lp-h2">Five databases. One relational spine.</h2>
          <p className="lp-lede">
            Everything hangs off the deal. A call logged this morning shows up on the lead, on the
            contact and on the company — because it is one row related three ways, not three copies.
          </p>

          <div className="lp-schema">
            <div className="lp-node">
              <h4>
                {ENTITIES[0].icon} {ENTITIES[0].name}{" "}
                <span className="lp-badge lp-badge-auto">Automated</span>
              </h4>
              <p className="lp-node-props">{ENTITIES[0].props}</p>
            </div>

            <div className="lp-node lp-node-hub lp-schema-mid">
              <h4>
                💼 Leads <span className="lp-badge lp-badge-auto">Automated</span>
              </h4>
              <p className="lp-node-props">
                Stage · Value (€) · Probability · Deal Temperature · Expected Close · Stale Deal
              </p>
              <p className="lp-hub-note">← the pipeline everything points at</p>
            </div>

            {ENTITIES.slice(1).map((e) => (
              <div className="lp-node" key={e.name}>
                <h4>
                  {e.icon} {e.name}{" "}
                  <span className={`lp-badge ${e.auto ? "lp-badge-auto" : "lp-badge-manual"}`}>
                    {e.auto ? "Automated" : "Manual today"}
                  </span>
                </h4>
                <p className="lp-node-props">{e.props}</p>
              </div>
            ))}
          </div>

          <div className="lp-rels">
            {RELATIONS.map(([rel, note]) => (
              <span key={rel}>
                <code>{rel}</code> · {note}
              </span>
            ))}
          </div>

          <div className="lp-legend">
            <span>
              <span className="lp-badge lp-badge-auto">Automated</span> Notion Pilot reads and
              writes these four
            </span>
            <span>
              <span className="lp-badge lp-badge-manual">Manual today</span> Meetings lives in
              Notion; Notion Pilot does not write to it yet
            </span>
          </div>

          <h3 className="lp-h3-mid">And the pipeline it produces</h3>
          <div className="lp-frame">
            <div className="lp-frame-bar">
              <span className="lp-dot" /> 💼 Leads — pipeline
              <div className="lp-tabs">
                <span className="lp-tab">Table</span>
                <span className="lp-tab is-on">Board</span>
                <span className="lp-tab">Stale</span>
              </div>
            </div>
            <div className="lp-board">
              {BOARD.map((col) => (
                <div className="lp-col" key={col.stage}>
                  <div className="lp-col-head">
                    <b>{col.stage}</b>
                    <span>{col.count}</span>
                  </div>
                  {col.deals.map(([title, meta]) => (
                    <div className={`lp-deal ${col.won ? "lp-deal-won" : ""}`} key={title}>
                      <b>{title}</b>
                      <span>{meta}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── the question ────────────────────────────────────────────────── */}
      <section className="lp-band">
        <div className="lp-wrap">
          <h2 className="lp-h2">But who keeps all of this up to date?</h2>
          <p>
            Building that schema is one good afternoon. Then reality starts: every property on the
            diagram has to be filled in by someone who has just walked out of a meeting, with four
            emails waiting and a train to catch.
          </p>
          <div className="lp-band-cols">
            {DECAY.map(([prop, note]) => (
              <div className="lp-band-col" key={prop}>
                <b>
                  <code>{prop}</code>
                </b>
                <span>{note}</span>
              </div>
            ))}
          </div>
          <p className="lp-band-note">
            A CRM that depends on discipline decays at the speed of your busiest week.
          </p>
        </div>
      </section>

      {/* ── step 3 · two ways in ────────────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-wrap">
          <span className="lp-eyebrow">Step 3 — keeping it alive</span>
          <h2 className="lp-h2">Notion Pilot does the typing. You keep the judgement.</h2>
          <p className="lp-lede">
            Two ways in, both ending in the same place: a preview you approve before a single row
            changes. <strong>Nothing is written that you haven't seen.</strong>
          </p>
          <div className="lp-cards">
            <div className="lp-card">
              <h3>💬 Telegram — for the thirty-second update</h3>
              <p className="lp-mb">
                Between two meetings, on the phone, no laptop. <code>/lead</code>,{" "}
                <code>/people</code>, <code>/company</code>, <code>/deal</code> — the bot asks for
                whatever you skipped and shows the preview before writing.
              </p>
              <div className="lp-frame lp-frame-flat">
                <div className="lp-chat lp-chat-compact">
                  <div className="lp-msg lp-msg-user lp-msg-sm">/lead</div>
                  <div className="lp-msg lp-msg-bot lp-msg-sm">Company? Contact? Source?</div>
                  <div className="lp-msg lp-msg-user lp-msg-sm">Voltaris · C. Dubois · inbound</div>
                  <div className="lp-msg lp-msg-bot lp-msg-sm">
                    Preview: 1 new Lead, 1 matched Company. Confirm?
                  </div>
                </div>
              </div>
            </div>
            <div className="lp-card lp-card-accent">
              <h3>🤖 AI assistant — for everything else</h3>
              <p>
                This is the one that changes the job. Your assistant already reads your inbox and
                your call notes. Give it access to the CRM and the pipeline stops being something
                you maintain — it becomes something you approve.
              </p>
              <p className="lp-mt-sm">
                Works in Claude, Claude Code and Cursor over MCP: it searches the CRM first, dedups
                against what exists, then proposes a diff.
              </p>
              <p className="lp-teaser">Keep reading — this is the interesting part. ↓</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── agent deep dive ─────────────────────────────────────────────── */}
      <section className="lp-section lp-section-tint">
        <div className="lp-wrap">
          <span className="lp-eyebrow">The AI agent workflow</span>
          <h2 className="lp-h2">Paste the email. Approve the diff. The funnel moves.</h2>
          <p className="lp-lede">
            One real interaction — a reply to a demo — normally touches four databases and nine
            properties. Here it costs one paste and one word.
          </p>

          <div className="lp-frame">
            <div className="lp-frame-bar">
              <span className="lp-dot" /> Claude · notion-crm MCP connected
            </div>
            <div className="lp-chat">
              <div className="lp-msg lp-msg-user">
                <span className="lp-msg-label">You — pasted from your inbox</span>
                <span className="lp-mono">{PASTED_EMAIL}</span>
              </div>

              <div className="lp-msg lp-msg-bot">
                <span className="lp-msg-label">
                  Claude — searched the CRM first, nothing written yet
                </span>
                Voltaris Énergie already exists (SIREN 843 219 004) and has an open lead at{" "}
                <em>Discovery / First Meeting</em>. Camille Dubois is not in People. Here is what I
                propose:
                <table className="lp-valid">
                  <thead>
                    <tr>
                      <th>Database</th>
                      <th>Action</th>
                      <th>Record</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Companies</td>
                      <td>
                        <span className="lp-pill lp-pill-grey">matched</span>
                      </td>
                      <td>Voltaris Énergie</td>
                      <td>no change</td>
                    </tr>
                    <tr>
                      <td>People</td>
                      <td>
                        <span className="lp-pill lp-pill-teal">create</span>
                      </td>
                      <td>Camille Dubois</td>
                      <td>
                        Head of Grid Analytics · seniority <code>director</code> · linked to
                        Voltaris
                      </td>
                    </tr>
                    <tr>
                      <td>Leads</td>
                      <td>
                        <span className="lp-pill lp-pill-amber">update</span>
                      </td>
                      <td>Voltaris — Platform licence</td>
                      <td>
                        Stage → <b>Proposal Sent</b> · Probability 50 → 60 % · Expected close{" "}
                        <b>15 Dec</b> · Primary contact → C. Dubois
                      </td>
                    </tr>
                    <tr>
                      <td>Activities</td>
                      <td>
                        <span className="lp-pill lp-pill-teal">create</span>
                      </td>
                      <td>Demo follow-up</td>
                      <td>
                        Type <code>📧 Email</code> · Outcome <code>➡️ Follow-up Needed</code> · Next
                        step “send proposal, 12 licences” due 20 Nov
                      </td>
                    </tr>
                  </tbody>
                </table>
                <p className="lp-note-sm">
                  Blocker noted in the deal notes: security review required before signature. Reply{" "}
                  <b>go</b> to write, or tell me what to change.
                </p>
              </div>

              <div className="lp-msg lp-msg-user">go</div>

              <div className="lp-msg lp-msg-bot">
                <span className="lp-msg-label">Claude — written with confirm=true</span>✅ 2
                created, 1 updated, 1 matched. Nothing duplicated.
                <br />
                Your pipeline moved 120 k€ from Discovery to Proposal Sent, and{" "}
                <code>Days Since Last Activity</code> reset to 0.
              </div>
            </div>
          </div>

          <div className="lp-steps">
            {AGENT_STEPS.map(([title, body]) => (
              <div className="lp-step" key={title}>
                <b>{title}</b>
                <span>{body}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── EU + trust ──────────────────────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-wrap">
          <span className="lp-eyebrow">Where the data lives</span>
          <h2 className="lp-h2">European by deployment, not by promise</h2>
          <p className="lp-lede">
            The two halves of this system are hosted independently — and both can sit in Europe.
          </p>

          <div className="lp-eu lp-mb-lg">
            <div className="lp-eu-flag">★★★</div>
            <div>
              <h3>Your CRM data: Notion Enterprise, EU region</h3>
              <p>
                Notion offers data residency in <strong>eu-central-1 (Frankfurt)</strong>. It is{" "}
                <strong>free of charge on the Enterprise plan</strong>, and Enterprise customers can
                request that an existing workspace be migrated into the EU region. Region-specific
                ingestion pipelines keep downstream processing inside that region too. GDPR-relevant
                terms and the current region list should be confirmed with Notion for your contract.
              </p>
            </div>
          </div>

          <div className="lp-cards">
            <div className="lp-card">
              <h3>The automation layer: your server</h3>
              <p>
                Notion Pilot is self-hosted — Docker or systemd, your infrastructure, your Notion
                token. It holds no copy of your CRM beyond a runtime cache, and there is no
                third-party SaaS between your team and your workspace.
              </p>
            </div>
            <div className="lp-card">
              <h3>Human in the loop, by default</h3>
              <p>
                Writes are dry-run unless explicitly confirmed. The AI proposes, you validate,
                Notion remains the source of truth. That order is enforced in the tools, not just in
                the documentation.
              </p>
            </div>
            <div className="lp-card">
              <h3>Your permissions, not the agent's</h3>
              <p>
                The assistant reaches Notion through your own connection and inherits what you can
                see. Access is revoked by disconnecting the integration in Notion — no separate key
                to chase.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── get started ─────────────────────────────────────────────────── */}
      <section className="lp-section lp-section-tint" id="deploy">
        <div className="lp-wrap">
          <span className="lp-eyebrow">Get started</span>
          <h2 className="lp-h2">Two commands and a workspace</h2>
          <p className="lp-lede">
            Deploy the databases, then point your assistant at them. Nothing to migrate, nothing to
            sign.
          </p>

          <div className="lp-cards lp-cards-start">
            <div className="lp-card">
              <div className="lp-card-num">1</div>
              <h3>Deploy the CRM into your Notion</h3>
              <p className="lp-mb">
                Connect with Notion and Notion Pilot creates the CRM page with Companies, People and
                Leads — relations wired, select options filled, demo rows included so the views make
                sense on day one.
              </p>
              <a className="lp-btn lp-btn-primary" href="/auth/notion">
                Deploy to Notion
              </a>
            </div>
            <div className="lp-card">
              <div className="lp-card-num">2</div>
              <h3>Connect your AI assistant</h3>
              <p className="lp-mb">
                Use Notion's official MCP server to let Claude or Cursor read and write your
                workspace over your own OAuth connection.
              </p>
              <pre className="lp-code">{MCP_SNIPPET}</pre>
            </div>
          </div>
        </div>
      </section>

      {/* ── final CTA ───────────────────────────────────────────────────── */}
      <section className="lp-final">
        <div className="lp-wrap">
          <h2 className="lp-h2">Run your next real deal through it</h2>
          <p>
            Pick one channel and one database. Put a week of real emails through it and see whether
            the pipeline still looks right on Monday morning.
          </p>
          <div className="lp-cta-row lp-center">
            <a className="lp-btn lp-btn-primary lp-btn-lg" href="/auth/notion">
              Deploy to Notion
            </a>
            <a className="lp-btn lp-btn-ghost lp-btn-lg" href="#model">
              See the data model again
            </a>
          </div>
        </div>
      </section>

      <footer className="lp-foot">
        <div className="lp-wrap lp-foot-row">
          <div className="lp-brand lp-brand-sm">
            <span className="lp-mark">P</span> Notion Pilot
          </div>
          <span>Self-hosted CRM automation for Notion · human-in-the-loop by default</span>
          <span>
            <a href="/auth/notion?next=/cockpit">Sign in</a>
          </span>
        </div>
      </footer>
    </div>
  );
}
