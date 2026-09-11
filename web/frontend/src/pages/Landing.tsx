import { useEffect, useRef, useState, type ReactNode } from "react";
import { fetchStatus } from "../api/client";
import { SetupWizard } from "../features/setup/SetupWizard";
import { Spinner } from "../components/Spinner";
import "../styles/landing.css";

type CheckState = "idle" | "checking" | "authenticated" | "unauthenticated" | "setup";

const CLAUDEFORCE_URL =
  "https://www.salesforce.com/news/press-releases/2026/08/26/salesforce-and-anthropic-announce-claudeforce/";
const RESIDENCY_URL = "https://www.notion.com/help/data-residency";
const NOTION_MCP = "https://mcp.notion.com/mcp";
const NOTION_MCP_DOCS = "https://developers.notion.com/guides/mcp/get-started-with-mcp";

// ── icons ─────────────────────────────────────────────────────────────────────
// One authored set: 24px grid, 1.6 stroke, round caps. No emoji stand-ins.

const PATHS: Record<string, ReactNode> = {
  company: (
    <>
      <path d="M3 21h18M5 21V6l7-3v18M19 21V11l-7-3" />
      <path d="M8.5 9.5h0M8.5 13h0M8.5 16.5h0M15.5 14h0M15.5 17.5h0" />
    </>
  ),
  people: (
    <>
      <path d="M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-4A3.5 3.5 0 0 0 5 18.5V20" />
      <circle cx="10.5" cy="8" r="3.2" />
      <path d="M17 11.2a3 3 0 0 0 0-5.9M19 20v-1.6a3.4 3.4 0 0 0-2-3" />
    </>
  ),
  deal: (
    <>
      <path d="M3 5h18l-6.5 7.6V20L9.5 17v-4.4L3 5Z" />
    </>
  ),
  activity: (
    <>
      <path d="M3 12h3.5l2-5.5 3.5 11 2.5-7 1.8 3.5H21" />
    </>
  ),
  meeting: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2.5" />
      <path d="M3 10h18M8 3v4M16 3v4M8.5 15h3" />
    </>
  ),
  agent: (
    <>
      <rect x="4" y="7" width="16" height="12" rx="3" />
      <path d="M12 3v4M9 13h0M15 13h0M10 16.5h4M2 12h2M20 12h2" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3 5 5.6v6c0 4.2 2.9 7.6 7 9.4 4.1-1.8 7-5.2 7-9.4v-6L12 3Z" />
      <path d="m9 12 2.3 2.3L15.5 10" />
    </>
  ),
  server: (
    <>
      <rect x="3" y="4" width="18" height="7" rx="2" />
      <rect x="3" y="13" width="18" height="7" rx="2" />
      <path d="M7 7.5h0M7 16.5h0M11 7.5h4M11 16.5h4" />
    </>
  ),
  lock: (
    <>
      <rect x="4.5" y="10.5" width="15" height="10" rx="2.5" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5M12 14.5v2" />
    </>
  ),
  link: (
    <>
      <path d="M10 13.8a3.6 3.6 0 0 0 5.1 0l2.6-2.6a3.6 3.6 0 0 0-5.1-5.1L11.4 7.3" />
      <path d="M14 10.2a3.6 3.6 0 0 0-5.1 0l-2.6 2.6a3.6 3.6 0 0 0 5.1 5.1l1.2-1.2" />
    </>
  ),
  views: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <path d="M3 9h18M9 9v11M15 9v11" />
    </>
  ),
  check: (
    <>
      <path d="m4 12.5 5 5L20 6.5" />
    </>
  ),
  eye: (
    <>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12S18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4.5 4.5" />
    </>
  ),
  grow: (
    <>
      <path d="M3 20h18M6.5 20v-6M11.5 20V9M16.5 20v-9.5" />
      <path d="m13.5 5 3.5-2 2 3.5" />
    </>
  ),
  skill: (
    <>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H18v18H6.5A2.5 2.5 0 0 1 4 18.5v-13Z" />
      <path d="M8 8h6M8 12h4" />
    </>
  ),
  formula: (
    <>
      <path d="M6 20V5.5A2.5 2.5 0 0 1 8.5 3h1M4.5 11h7" />
      <path d="M14 10.5 20 19M20 10.5 14 19" />
    </>
  ),
  arrow: (
    <>
      <path d="M4 12h15m-5.5-5.5L19 12l-5.5 5.5" />
    </>
  ),
};

function Icon({ name, size = 20 }: { name: keyof typeof PATHS | string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}

function T({ tag }: { tag: Tag }) {
  return <span className={`lp-t lp-t-${tag[1]}`}>{tag[0]}</span>;
}

function Dot({ health }: { health: Health }) {
  return <i className={`lp-sd lp-sd-${health}`} />;
}

function Rec({ when, dot, rows }: { when: string; dot: Health; rows: RecRow[] }) {
  return (
    <div className="lp-rec">
      <div className="lp-rec-when">
        <Dot health={dot} />
        {when}
      </div>
      <div className="lp-rec-title">Voltaris — Platform licence</div>
      <div className="lp-rec-props">
        {rows.map((r) => (
          <div className="lp-rec-row" key={r.prop}>
            <span>
              <Icon name="formula" size={11} />
              {r.prop}
            </span>
            {r.tag ? (
              <span>
                <T tag={r.tag} />
              </span>
            ) : (
              <span className={`lp-rec-val ${r.rot ? "lp-rec-rot" : ""}`}>
                {r.dot ? (
                  <span className="lp-dot-cell">
                    <Dot health={r.dot} />
                    {r.value}
                  </span>
                ) : (
                  r.value
                )}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// Autoplay is how a silent loop earns its place next to the prose — but a reader who
// asked the OS for less motion gets a still frame and real controls instead.
function Film({ film }: { film: Film }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [still, setStill] = useState(false);

  useEffect(() => {
    const q = window.matchMedia("(prefers-reduced-motion: reduce)");
    setStill(q.matches);
    const onChange = (e: MediaQueryListEvent) => setStill(e.matches);
    q.addEventListener("change", onChange);
    return () => q.removeEventListener("change", onChange);
  }, []);

  const applyRate = () => {
    const el = videoRef.current;
    if (el && film.rate) el.playbackRate = film.rate;
  };

  return (
    <figure className="lp-film">
      <div className="lp-film-frame">
        <video
          ref={videoRef}
          className="lp-film-video"
          src={`/film/${film.slug}.mp4`}
          poster={film.poster}
          width={1920}
          height={1080}
          autoPlay={!still}
          loop={!still}
          controls={still}
          muted
          playsInline
          preload="metadata"
          aria-label={film.title}
          onLoadedMetadata={applyRate}
          onPlay={applyRate}
        />
      </div>
      <figcaption className="lp-film-copy">
        <span className="lp-film-stage">
          {film.stage}
          <span className="lp-film-dur">{film.seconds}s · no sound</span>
        </span>
        <h3 className="lp-h3">{film.title}</h3>
      </figcaption>
    </figure>
  );
}

function Logo() {
  // A page of records, with the approval mark sweeping out past its edge.
  return (
    <svg className="lp-logo" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect
        x="3.3"
        y="3.3"
        width="20.4"
        height="25.4"
        rx="4"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <path
        d="M8.4 11h8.2M8.4 15.6h5.2M8.4 20.2h3"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="m12.6 21.4 5.2 5.4L30.2 9.6"
        stroke="var(--primary)"
        strokeWidth="3.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ── content ───────────────────────────────────────────────────────────────────

const PASTED_EMAIL = `Subject: RE: optimisation platform — next steps

Thanks for Tuesday's demo. The team is convinced on the solver
side. We need a security review before signing, and our budget
window closes 15 December. Can you send a proposal for 12 licences?

— Camille Dubois, Head of Grid Analytics, Voltaris Énergie`;

const MCP_SNIPPET = `# Claude Code
claude mcp add --transport http notion ${NOTION_MCP}
# then run /mcp and complete the OAuth flow

# Cursor — .cursor/mcp.json
{ "mcpServers": { "notion": { "url": "${NOTION_MCP}" } } }`;

const INSTALL_SNIPPET = `/plugin marketplace add ldom1/notion-pilot
/plugin install notion-crm@notion-pilot`;

const TAKEAWAYS: [string, string][] = [
  [
    "People love chat and tolerate CRMs.",
    "Fifteen clicks to update an opportunity is a task nobody does on a Friday.",
  ],
  [
    "The governance survives.",
    "Permissions, workflows and audit trail stay in the system of record — no record access, no agent access.",
  ],
  [
    "But it ships with Salesforce underneath.",
    "The idea travels. The licence, the migration and the seat price do not.",
  ],
];

type Film = {
  slug: string;
  stage: string;
  title: string;
  poster: string;
  seconds: number;
  rate?: number;
};

// One film on the page: the job, after the decay beat. Agent HITL and collab
// are told in the surfaces and EU sections — a second autoplay would retell them.
const PIPELINE_FILM: Film = {
  slug: "notion-pilot-pipeline",
  stage: "The job",
  title: "One email in. Four records out. Numbers already right.",
  poster: "/film/notion-pilot-pipeline.jpg",
  seconds: 21,
  rate: 0.85,
};

const ARGUMENTS_: [string, string][] = [
  [
    "The interface was the bottleneck",
    "Nobody quits a CRM over a missing field. They quit over fifteen clicks between two meetings.",
  ],
  [
    "The process still holds",
    "The agent inherits the CRM's permissions instead of bypassing them. No access to a record, no access for the AI.",
  ],
  [
    "The idea outlives the vendor",
    "Claudeforce only works if you already pay for Salesforce. Same idea, without the estate — that is this page.",
  ],
];

type Tag = [label: string, colour: string];
type Health = "ok" | "warn" | "bad" | "idle";

const COMPANIES: {
  name: string; sector: Tag; tier: Tag; people: string; last: string; health: Health; status: Tag;
}[] = [
  { name: "Voltaris Énergie", sector: ["Energy", "yellow"], tier: ["Tier 1", "red"], people: "3 contacts", last: "2d", health: "ok", status: ["Active", "green"] },
  { name: "Néorégie Grid", sector: ["Public Sector", "purple"], tier: ["Tier 2", "blue"], people: "1 contact", last: "11d", health: "warn", status: ["Prospect", "gray"] },
  { name: "Hexalis Industries", sector: ["Industry", "blue"], tier: ["Tier 2", "blue"], people: "5 contacts", last: "34d", health: "bad", status: ["Prospect", "gray"] },
  { name: "Cerena Renouvelables", sector: ["Energy", "yellow"], tier: ["Tier 3", "gray"], people: "2 contacts", last: "6d", health: "ok", status: ["Active", "green"] },
];

const LEADS: {
  name: string; stage: Tag; value: string; prob: string; acts: string;
  last: string; health: Health; row?: string;
}[] = [
  { name: "Voltaris — Platform licence", stage: ["Proposal Sent", "orange"], value: "120 000", prob: "60 %", acts: "7 activities", last: "today", health: "ok" },
  { name: "Astria — Optimisation", stage: ["Negotiation", "purple"], value: "80 000", prob: "75 %", acts: "12 activities", last: "3d", health: "ok" },
  { name: "Cerena — Consulting", stage: ["Qualified", "blue"], value: "45 000", prob: "40 %", acts: "4 activities", last: "6d", health: "ok" },
  { name: "Hexalis — Platform licence", stage: ["Waiting for a Response", "yellow"], value: "—", prob: "10 %", acts: "2 activities", last: "34d · stale", health: "bad", row: "lp-row-risk" },
  { name: "Kaleo — Licence", stage: ["Closed Won", "green"], value: "52 000", prob: "100 %", acts: "9 activities", last: "12d", health: "idle", row: "lp-row-won" },
];

const ACTIVITIES: {
  name: string; type: Tag; outcome: Tag; next: string; when: string; fresh?: boolean;
}[] = [
  { name: "Demo follow-up", type: ["Email", "blue"], outcome: ["Follow-up Needed", "yellow"], next: "Send proposal, 12 licences", when: "logged by AI", fresh: true },
  { name: "Technical demo", type: ["Demo", "purple"], outcome: ["Positive", "green"], next: "Loop in security", when: "4d" },
  { name: "Discovery call", type: ["Call", "green"], outcome: ["Positive", "green"], next: "Book demo", when: "11d" },
];

const ENTITIES: { icon: string; name: string; props: string[]; auto: boolean }[] = [
  { icon: "company", name: "Companies", props: ["Sector", "Tier", "SIREN", "CA", "Country"], auto: true },
  { icon: "activity", name: "Activities", props: ["Type", "Date", "Outcome", "Next Step"], auto: true },
  { icon: "people", name: "People", props: ["Position", "Seniority", "Email", "LinkedIn"], auto: true },
  { icon: "meeting", name: "Meetings", props: ["Notes", "Attendees", "Linked deal"], auto: false },
];

const RELATIONS: [string, string][] = [
  ["Companies 1 → n Leads", "one client, several deals running at once"],
  ["People n → 1 Companies", "every contact sits under one organisation"],
  ["Leads n → n People", "a primary contact, plus everyone else in the loop"],
  ["Activities n → 1 Leads", "and back to the person and the company"],
  ["Meetings n → n People", "notes attached to whoever was in the room"],
];

const BOARD: {
  stage: string; n: string; dot: Health; cards: { name: string; value: string; tag: Tag }[];
}[] = [
  { stage: "Prospect", n: "3", dot: "idle", cards: [{ name: "Néorégie — Study", value: "18 000", tag: ["Cold", "gray"] }] },
  { stage: "Qualified", n: "2", dot: "ok", cards: [{ name: "Cerena — Consulting", value: "45 000", tag: ["40 %", "blue"] }] },
  { stage: "Discovery", n: "3", dot: "ok", cards: [{ name: "Vireo — Renewal", value: "64 000", tag: ["Warm", "orange"] }] },
  { stage: "Proposal Sent", n: "1", dot: "ok", cards: [{ name: "Voltaris — Platform", value: "120 000", tag: ["60 %", "orange"] }] },
  { stage: "Waiting", n: "5", dot: "bad", cards: [{ name: "Hexalis — Platform", value: "—", tag: ["Stale 34d", "red"] }] },
  { stage: "Closed Won", n: "1", dot: "ok", cards: [{ name: "Kaleo — Licence", value: "52 000", tag: ["Won", "green"] }] },
];

type RecRow = { prop: string; value: string; tag?: Tag; dot?: Health; rot?: boolean };

const REC_FRESH: RecRow[] = [
  { prop: "Stage", value: "", tag: ["Discovery / First Meeting", "blue"] },
  { prop: "Next Step", value: "Send proposal · due 20 Nov" },
  { prop: "Last Activity", value: "today", dot: "ok" },
  { prop: "Deal Age", value: "4 days" },
  { prop: "Days Since Last Activity", value: "0" },
  { prop: "Stale Deal", value: "", tag: ["No", "gray"] },
];

const REC_ROTTED: RecRow[] = [
  { prop: "Stage", value: "", tag: ["Discovery / First Meeting", "blue"] },
  { prop: "Next Step", value: "Send proposal · overdue 14 days", rot: true },
  { prop: "Last Activity", value: "34 days ago", dot: "bad", rot: true },
  { prop: "Deal Age", value: "38 days" },
  { prop: "Days Since Last Activity", value: "34", rot: true },
  { prop: "Stale Deal", value: "", tag: ["Yes", "red"] },
];

const EVOLVE: [string, string][] = [
  [
    "We deploy a ready-to-use CRM",
    "Five databases — Companies, People, Leads, Activities, Meetings — relations wired, stages filled, and the pipeline formulas already computing.",
  ],
  [
    "You reshape it",
    "A property here, a stage split there, a tier system nobody else would want. That is the whole reason to build a CRM in Notion.",
  ],
  [
    "The automation follows",
    "The assistant reads your workspace through Notion's own MCP server, so it works on the structure you grew into — not one hardcoded a year ago. Add a field on Monday, it fills it on Tuesday.",
  ],
];

const DIFF: { db: string; action: Tag; record: string; detail: string }[] = [
  { db: "Companies", action: ["matched", "gray"], record: "Voltaris Énergie", detail: "no change" },
  { db: "People", action: ["create", "green"], record: "Camille Dubois", detail: "Head of Grid Analytics · director" },
  { db: "Leads", action: ["update", "orange"], record: "Voltaris — Platform licence", detail: "Discovery → Proposal Sent · 50 → 60 % · close 15 Dec" },
  { db: "Activities", action: ["create", "green"], record: "Demo follow-up", detail: "Email · Follow-up Needed · proposal due 20 Nov" },
];

const AGENT_STEPS: [string, string, string][] = [
  ["search", "It looks before it writes", "Email, then LinkedIn, then fuzzy name plus company. An existing record gets updated, not duplicated."],
  ["eye", "Dry run is the default", "Every write comes back as a preview. The default answer to “should I write this?” is no."],
  ["check", "You approve the diff", "Exactly what changes, per database. Ambiguous matches are escalated, never guessed."],
];

const EU_MARKS: [string, string, string][] = [
  ["people", "The team already shares it", "Collaboration is native Notion — one workspace, live for everyone. Notion Pilot only does the typing."],
  ["server", "Frankfurt, not Oregon", "Notion can pin that same workspace at rest to eu-central-1 on the Enterprise plan. Confirm region and terms with Notion."],
  ["shield", "Your own machine", "The automation layer is self-hosted. No third-party SaaS sits between your team and Notion."],
  ["lock", "Your permissions", "The assistant connects as you and sees what you see. Revoke it in Notion, not in a support ticket."],
];

const SKILLS: [string, string][] = [
  ["notion-crm-ops", "Operate the CRM — create and update leads, log activities, enrich people and companies. Always shows a validation table and waits for your go."],
  ["company-open-data-enrichment", "Fill firmographics from French open data — SIREN, NAF/APE, BODACC, RNE financials — instead of typing them."],
];

// ── page ──────────────────────────────────────────────────────────────────────

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
      <div className="lp lp-setup-scene">
        <div className="lp-setup-bg" aria-hidden="true">
          <svg className="lp-setup-bg-graph" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
            <g className="lp-setup-bg-edges">
              <path d="M120 180H380L560 90H820" />
              <path d="M380 180V420H640L860 520" />
              <path d="M640 420V700H1100" />
              <path d="M820 90V300H1280" />
            </g>
            <g className="lp-setup-bg-dots">
              <circle cx="120" cy="180" r="3.5" />
              <circle cx="380" cy="180" r="3.5" />
              <circle cx="560" cy="90" r="3.5" />
              <circle cx="820" cy="90" r="3.5" />
              <circle cx="640" cy="420" r="3.5" />
              <circle cx="860" cy="520" r="3.5" />
              <circle className="lp-setup-bg-pulse" cx="1100" cy="700" r="3.5" />
              <circle className="lp-setup-bg-pulse" cx="1280" cy="300" r="3.5" />
            </g>
          </svg>
        </div>
        <nav className="lp-nav">
          <span className="lp-brand">
            <Logo /> Notion Pilot
          </span>
          <a className="lp-small" href="/auth/logout">
            Sign out
          </a>
        </nav>
        <main className="lp-wrap lp-section">
          <SetupWizard
            onComplete={() => {
              window.location.href = "/cockpit";
            }}
            onSkip={() => {
              window.location.href = "/cockpit";
            }}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="lp">
      <nav className="lp-nav">
        <a className="lp-brand" href="/">
          <Logo /> Notion Pilot
        </a>
        <div className="lp-nav-actions">
          <a className="lp-btn lp-btn-quiet" href="#model">
            The data model
          </a>
          <a className="lp-btn lp-btn-primary" href="/auth/notion">
            Deploy to Notion
          </a>
        </div>
      </nav>

      {/* ── hero ─────────────────────────────────────────────────────────── */}
      <header className="lp-hero lp-wrap">
        <div className="lp-hero-grid">
          <div>
            <h1 className="lp-display">
              Your CRM doesn't have a feature problem. It has a{" "}
              <span className="lp-stamp">data-entry problem</span>.
            </h1>
            <p className="lp-hero-sub">
              Notion Pilot is that idea for a CRM you actually own — data kept up to date by AI
              assistance, on a workspace you can host in Europe.
            </p>
            <div className="lp-btn-row" style={{ marginTop: "1.9rem" }}>
              <a className="lp-btn lp-btn-primary lp-btn-lg" href="/auth/notion">
                Deploy the CRM to Notion <Icon name="arrow" size={17} />
              </a>
              <a className="lp-btn lp-btn-quiet lp-btn-lg" href="#model">
                See the data model
              </a>
            </div>
            <div className="lp-hero-terms">
              <span className="lp-term">
                <Icon name="server" size={16} /> Self-hosted
              </span>
              <span className="lp-term">
                <Icon name="check" size={16} /> Every write needs your approval
              </span>
              <span className="lp-term">
                <Icon name="shield" size={16} /> EU data residency
              </span>
            </div>
          </div>

          <aside className="lp-dispatch">
            <span className="lp-dispatch-meta">26 August 2026 · Salesforce newsroom</span>
            <h2>Salesforce and Anthropic announce Claudeforce</h2>
            <p>
              “Salesforce in Claude” ships as a plugin with 37 prebuilt sales skills — meeting prep,
              deal-health review, pipeline review, composing emails, updating records — so sellers
              reason over live pipeline and act on it without opening the CRM.
            </p>
            <ul className="lp-takeaways">
              {TAKEAWAYS.map(([lead, rest]) => (
                <li key={lead}>
                  <b>{lead}</b> {rest}
                </li>
              ))}
            </ul>
            <p className="lp-source">
              Source: <a href={CLAUDEFORCE_URL}>Salesforce press release</a>
            </p>
          </aside>
        </div>
      </header>

      {/* ── the signal ───────────────────────────────────────────────────── */}
      <section className="lp-section lp-tint">
        <div className="lp-wrap">
          <h2 className="lp-h2">Why that announcement matters more than it looks</h2>
          <div className="lp-args">
            {ARGUMENTS_.map(([title, body]) => (
              <div className="lp-arg" key={title}>
                <h3 className="lp-h3">{title}</h3>
                <p>{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Notion is already the database ───────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-wrap">
          <div className="lp-intro">
            <h2 className="lp-h2">
              Notion is built on a database structure. It is not a CRM yet.
            </h2>
            <div className="lp-intro-copy">
              <p className="lp-lede">
                Every Notion table lives inside that structure — and a row in one table can{" "}
                <strong>relate</strong> to a row in another. A contact relates to a company. A deal
                relates to both. Rename that company once, and every deal, contact, and activity
                referencing it updates instantly — because they hold a relation, not a copy.
              </p>
              <p className="lp-lede">
                That single property is the{" "}
                <strong>entire difference between a CRM and a spreadsheet</strong>. Notion has had
                it all along.
              </p>
              <p className="lp-body">
                What Notion doesn't give you is a schema shaped like a pipeline — and someone to
                keep it current. That's exactly what we bring.
              </p>
            </div>
          </div>

          <div>
            <div className="lp-stack">
              <div className="lp-stack-head">
                <div>
                  <div className="lp-icon">
                    <Icon name="link" />
                  </div>
                  <h3 className="lp-h3">One company. One row. Everywhere.</h3>
                </div>
                <div className="lp-intro-copy">
                <p>
                  This is the thing a spreadsheet can never do, no matter how many tabs you add.
                </p>
                <div className="lp-versus">
                  <div>
                    <h4>In Excel</h4>
                    <p>
                      A client renames itself and you find-and-replace across six sheets. You will
                      miss one, and nobody will notice until the QBR.
                    </p>
                  </div>
                  <div className="lp-versus-good">
                    <h4>In Notion</h4>
                    <p>
                      You edit the company row. Every deal, contact and activity pointing at it
                      updates, because they were never copies.
                    </p>
                  </div>
                </div>
                </div>
              </div>
              <div className="lp-win">
                <div className="lp-win-bar">
                  <Icon name="company" size={16} /> Companies
                  <div className="lp-views">
                    <span className="lp-view" aria-current="true">
                      Table
                    </span>
                    <span className="lp-view">By tier</span>
                    <span className="lp-view">Map</span>
                  </div>
                </div>
                <div className="lp-x">
                  <table className="lp-grid">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Sector</th>
                        <th>Tier</th>
                        <th>People</th>
                        <th>Last activity</th>
                        <th>CRM status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {COMPANIES.map((c) => (
                        <tr key={c.name}>
                          <td>{c.name}</td>
                          <td><T tag={c.sector} /></td>
                          <td><T tag={c.tier} /></td>
                          <td>
                            <span className="lp-link">
                              <Icon name="link" size={12} />
                              {c.people}
                            </span>
                          </td>
                          <td>
                            <span className="lp-dot-cell">
                              <Dot health={c.health} />
                              <span className="lp-num">{c.last}</span>
                            </span>
                          </td>
                          <td><T tag={c.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="lp-stack">
              <div className="lp-stack-head">
                <div>
                  <div className="lp-icon">
                    <Icon name="views" />
                  </div>
                  <h3 className="lp-h3">The same rows, seen six ways</h3>
                </div>
                <div className="lp-intro-copy">
                <p>
                  A view is a lens, not a copy. Board for the Monday pipeline review, table for the
                  audit, calendar for next steps, timeline for the quarter — every one of them
                  reading the identical rows, live.
                </p>
                <p>
                  So nobody exports anything, nobody rebuilds a deck, and there is no “which version
                  is current?”. Leadership opens the view. That is the whole reporting story, and it
                  replaces the weekly spreadsheet ritual outright.
                </p>
                </div>
              </div>
              <div className="lp-win">
                <div className="lp-win-bar">
                  <Icon name="deal" size={16} /> Leads
                  <div className="lp-views">
                    <span className="lp-view">Table</span>
                    <span className="lp-view" aria-current="true">
                      Board
                    </span>
                    <span className="lp-view">Stale</span>
                    <span className="lp-view">Calendar</span>
                  </div>
                </div>
                <div className="lp-x">
                  <div className="lp-board">
                    {BOARD.map((lane) => (
                      <div className="lp-lane" key={lane.stage}>
                        <div className="lp-lane-head">
                          <b>
                            <Dot health={lane.dot} />
                            {lane.stage}
                          </b>
                          <span>{lane.n}</span>
                        </div>
                        {lane.cards.map((c) => (
                          <div className="lp-cardlet" key={c.name}>
                            <b>{c.name}</b>
                            <div className="lp-cardlet-row">
                              <span className="lp-cardlet-val">{c.value} €</span>
                              <T tag={c.tag} />
                            </div>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── pipeline + activities, joined ────────────────────────────────── */}
      <section className="lp-section lp-tint">
        <div className="lp-wrap">
          <div className="lp-intro">
            <h2 className="lp-h2">The deal, and the trail that proves it</h2>
            <div className="lp-intro-copy">
              <p className="lp-lede">
                Every lead carries its own activity trail, so “what happened on this deal?” is a
                click, not an archaeology project — and the one number every pipeline review
                actually turns on finally means something:
              </p>
              <div className="lp-propline">
                <span className="lp-propref">
                  <Icon name="formula" size={13} /> Days Since Last Activity
                </span>
                <Icon name="arrow" size={15} />
                <span>a number you can trust, instead of a guess.</span>
              </div>
            </div>
          </div>

          <div className="lp-win" style={{ marginTop: "2rem" }}>
            <div className="lp-win-bar">
              <Icon name="deal" size={16} /> Leads
              <div className="lp-views">
                <span className="lp-view" aria-current="true">
                  Table
                </span>
                <span className="lp-view">Board</span>
                <span className="lp-view">Weighted</span>
              </div>
            </div>
            <div className="lp-x">
              <table className="lp-grid">
                <thead>
                  <tr>
                    <th>Deal</th>
                    <th>Stage</th>
                    <th>Value</th>
                    <th>Prob.</th>
                    <th>Activities</th>
                    <th>Last activity</th>
                  </tr>
                </thead>
                <tbody>
                  {LEADS.map((l) => (
                    <tr key={l.name} className={l.row ?? ""}>
                      <td>{l.name}</td>
                      <td><T tag={l.stage} /></td>
                      <td className="lp-num">{l.value === "—" ? "—" : `${l.value} €`}</td>
                      <td className="lp-num">{l.prob}</td>
                      <td>
                        <span className="lp-link">
                          <Icon name="link" size={12} />
                          {l.acts}
                        </span>
                      </td>
                      <td>
                        <span className="lp-dot-cell">
                          <Dot health={l.health} />
                          <span className="lp-num">{l.last}</span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="lp-win" style={{ marginTop: "1rem" }}>
            <div className="lp-win-bar">
              <Icon name="activity" size={16} /> Activities
              <span className="lp-surface-when" style={{ marginLeft: "0.6rem" }}>
                filtered to Voltaris — Platform licence
              </span>
            </div>
            <div className="lp-x">
              <table className="lp-grid">
                <thead>
                  <tr>
                    <th>Activity</th>
                    <th>Type</th>
                    <th>Outcome</th>
                    <th>Next step</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {ACTIVITIES.map((a) => (
                    <tr key={a.name}>
                      <td>{a.name}</td>
                      <td><T tag={a.type} /></td>
                      <td>
                        <span className="lp-dot-cell">
                          <Dot health={a.outcome[0] === "Positive" ? "ok" : "warn"} />
                          <T tag={a.outcome} />
                        </span>
                      </td>
                      <td>{a.next}</td>
                      <td className="lp-num">
                        {a.fresh ? <span className="lp-tag lp-tag-new">{a.when}</span> : a.when}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* ── the model ────────────────────────────────────────────────────── */}
      <section className="lp-section" id="model">
        <div className="lp-wrap">
          <div className="lp-intro">
            <h2 className="lp-h2">Around that deal: companies, people, meetings</h2>
            <div className="lp-intro-copy">
              <p className="lp-lede">
                Everything hangs off the deal. A call logged this morning appears on the lead, on
                the contact and on the company — one row, related three ways, never three copies.
              </p>
            </div>
          </div>

          <div className="lp-schema">
            <div className="lp-ent">
              <div className="lp-ent-head">
                <Icon name="company" size={18} />
                <h4>Companies</h4>
                <span className="lp-ent-flag lp-flag-auto">auto</span>
              </div>
              <div className="lp-ent-props">
                {ENTITIES[0].props.map((p) => (
                  <span className="lp-prop" key={p}>
                    {p}
                  </span>
                ))}
              </div>
            </div>

            <div className="lp-hub">
              <div className="lp-ent lp-ent-hub">
                <div className="lp-ent-head">
                  <Icon name="deal" size={18} />
                  <h4>Leads</h4>
                  <span className="lp-ent-flag lp-flag-auto">auto</span>
                </div>
                <div className="lp-ent-props">
                  {["Stage", "Value (€)", "Probability", "Expected Close", "Deal Temperature", "Stale Deal"].map(
                    (p) => (
                      <span className="lp-prop" key={p}>
                        {p}
                      </span>
                    ),
                  )}
                </div>
                <p className="lp-small" style={{ margin: 0 }}>
                  The pipeline everything points at.
                </p>
              </div>
            </div>

            {ENTITIES.slice(1).map((e) => (
              <div className={`lp-ent ${e.auto ? "" : "lp-ent-manual"}`} key={e.name}>
                <div className="lp-ent-head">
                  <Icon name={e.icon} size={18} />
                  <h4>{e.name}</h4>
                  <span className={`lp-ent-flag ${e.auto ? "lp-flag-auto" : "lp-flag-manual"}`}>
                    {e.auto ? "auto" : "manual"}
                  </span>
                </div>
                <div className="lp-ent-props">
                  {e.props.map((p) => (
                    <span className="lp-prop" key={p}>
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="lp-relations">
            {RELATIONS.map(([rel, note]) => (
              <div className="lp-relation" key={rel}>
                <b>{rel}</b>
                <span>{note}</span>
              </div>
            ))}
          </div>

          <p className="lp-small" style={{ marginTop: "1.4rem" }}>
            <span className="lp-ent-flag lp-flag-auto">auto</span> Notion Pilot reads and writes
            these four. <span className="lp-ent-flag lp-flag-manual">manual</span> Meetings lives in
            Notion and stays yours.
          </p>
        </div>
      </section>

      {/* ── the turn ─────────────────────────────────────────────────────── */}
      <section className="lp-section lp-tint lp-turn">
        <div className="lp-wrap">
          <div className="lp-intro">
            <h2 className="lp-h2">But who keeps all of this up to date?</h2>
            <div className="lp-intro-copy">
              <p className="lp-lede">
                Building the schema is one good afternoon. Keeping it true is every afternoon after
                that. Here is the same deal record, and nobody touched it in between.
              </p>
            </div>
          </div>

          <div className="lp-pair">
            <Rec when="DAY 0 · straight after the demo" dot="ok" rows={REC_FRESH} />
            <div className="lp-gap">
              <span className="lp-gap-line" />
              <b>+34 days</b>
              <span>one busy quarter, four other deals</span>
              <span className="lp-gap-line" />
            </div>
            <Rec when="DAY 34 · nothing logged since" dot="bad" rows={REC_ROTTED} />
          </div>

          <p className="lp-punch">
            Nothing here is broken. Every formula is still correct — they were simply{" "}
            <em>never fed</em>. A CRM that runs on discipline decays at the speed of your busiest
            week.
          </p>

          <ol className="lp-evolve">
            {EVOLVE.map(([title, body]) => (
              <li key={title}>
                <b>{title}</b>
                <span>{body}</span>
              </li>
            ))}
          </ol>

          <p className="lp-feedback">
            <Icon name="grow" size={17} />
            <span>
              And when it gets something wrong, tell us — an awkward property, a stage the matcher
              misreads, a report you still rebuild by hand. Feedback from real pipelines is what
              shapes this roadmap.
            </span>
            <a href="https://github.com/ldom1/notion-pilot/issues">Open an issue →</a>
          </p>
        </div>
      </section>

      {/* ── the job, on film — answers the decay beat, once ──────────────── */}
      <section className="lp-section" id="film">
        <div className="lp-wrap">
          <div className="lp-intro">
            <h2 className="lp-h2">Nobody opened Notion. The pipeline still moved.</h2>
          </div>
          <Film film={PIPELINE_FILM} />
        </div>
      </section>

      {/* ── the assistant ────────────────────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-wrap">
          <div className="lp-intro">
            <h2 className="lp-h2">Notion Pilot does the typing. You keep the judgement.</h2>
            <div className="lp-intro-copy">
              <p className="lp-lede">
                Your AI assistant reads the thread, searches the CRM, and shows a preview.{" "}
                <strong>Nothing reaches Notion that you haven't approved.</strong>
              </p>
            </div>
          </div>

          <div className="lp-surfaces">
            <div className="lp-surface">
              <div className="lp-surface-head">
                <Icon name="agent" />
                <h3 className="lp-h3">Your AI assistant</h3>
                <span className="lp-surface-when">paste · preview · go</span>
              </div>
              <p>
                The film above is this path. Paste a thread; get a preview; you only approve.
              </p>
              <div className="lp-chat">
                <div className="lp-bubble lp-bubble-me">
                  <span className="lp-who">Pasted from your inbox</span>
                  <pre className="lp-pre">{PASTED_EMAIL}</pre>
                </div>
                <div className="lp-bubble lp-bubble-bot">
                  <span className="lp-who">Searched the CRM · nothing written yet</span>
                  <table className="lp-diff">
                    <thead>
                      <tr>
                        <th>Database</th>
                        <th>Action</th>
                        <th>Record</th>
                      </tr>
                    </thead>
                    <tbody>
                      {DIFF.map((d) => (
                        <tr key={d.db}>
                          <td>{d.db}</td>
                          <td><T tag={d.action} /></td>
                          <td>
                            <b>{d.record}</b>
                            <br />
                            <span className="lp-small">{d.detail}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="lp-approve">
                    <span className="lp-key">go</span>
                    <span className="lp-small">
                      2 created, 1 updated, 1 matched · 120 k€ moved to Proposal Sent
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="lp-steps">
            {AGENT_STEPS.map(([icon, title, body]) => (
              <div key={title}>
                <b>
                  <Icon name={icon} size={17} /> {title}
                </b>
                <span>{body}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── europe ───────────────────────────────────────────────────────── */}
      <section className="lp-section lp-tint">
        <div className="lp-wrap">
          <div className="lp-eu">
            <div>
              <span className="lp-region">
                <Icon name="shield" size={16} /> eu-central-1 · Frankfurt
              </span>
              <h2 className="lp-h2">European by deployment, not by promise</h2>
              <p className="lp-body" style={{ marginTop: "1.1rem" }}>
                The CRM lives in the Notion workspace your team share. Collaboration is
                Notion's — that is the point. Both halves of the rest of this system are hosted
                independently, and both can sit inside the EU. Data residency is{" "}
                <strong>an option on the Notion Enterprise plan</strong>, free of charge; an
                existing workspace can be migrated into the EU region on request.
              </p>
              <p className="lp-small" style={{ marginTop: "0.9rem" }}>
                Confirm the current region list and contractual terms with{" "}
                <a href={RESIDENCY_URL}>Notion</a> for your own agreement.
              </p>
            </div>
            <div className="lp-eu-marks">
              {EU_MARKS.map(([icon, title, body]) => (
                <div className="lp-eu-mark" key={title}>
                  <Icon name={icon} />
                  <b>{title}</b>
                  <span>{body}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── get started ──────────────────────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-wrap">
          <div className="lp-intro">
            <h2 className="lp-h2">Deploy the CRM, then teach your assistant to run it</h2>
            <div className="lp-intro-copy">
              <p className="lp-lede">
                Nothing to migrate, nothing to sign. Deploy writes the CRM into your Notion. Claude
                then reaches those same pages through Notion's official MCP — a second OAuth, same
                workspace — and the skills in this repo tell it how to run the pipeline.
              </p>
            </div>
          </div>

          <div className="lp-stack">
            <div className="lp-stack-head">
              <div>
                <div className="lp-icon">
                  <Icon name="skill" />
                </div>
                <h3 className="lp-h3">The skills are the product</h3>
              </div>
              <div className="lp-intro-copy">
              <p>
                An MCP connection alone just gives an assistant hands. These are the instructions
                that make it useful on a CRM — search before write, dedup, a validation table, and a
                hard stop until you approve.
              </p>
              <div className="lp-skills">
                {SKILLS.map(([name, what]) => (
                  <div className="lp-skill" key={name}>
                    <Icon name="skill" size={16} />
                    <span>
                      <b>{name}</b>
                      <br />
                      <span>{what}</span>
                    </span>
                  </div>
                ))}
              </div>
              </div>
            </div>

            <div className="lp-install">
              <div>
                <h4 className="lp-install-h">
                  <span className="lp-step-n">1</span> Install the skills
                </h4>
                <p className="lp-small">
                  Two lines in Claude Code. Add the marketplace, install the plugin — both skills
                  arrive together and update with the repo. No clone, no symlinks, no config file.
                </p>
                <pre className="lp-code">{INSTALL_SNIPPET}</pre>
              </div>
              <div>
                <h4 className="lp-install-h">
                  <span className="lp-step-n">2</span> Connect Notion
                </h4>
                <p className="lp-small">
                  Notion's hosted MCP, not the wizard's integration. Complete its OAuth once — it
                  sees the pages you can see, including the CRM you just deployed. Restart the
                  assistant and the skills trigger on their own.{" "}
                  <a href={NOTION_MCP_DOCS}>Notion MCP setup</a>.
                </p>
                <pre className="lp-code">{MCP_SNIPPET}</pre>
              </div>
            </div>

            <div className="lp-btn-row" style={{ marginTop: "1.6rem" }}>
              <a className="lp-btn lp-btn-primary" href="/auth/notion">
                Deploy to Notion <Icon name="arrow" size={17} />
              </a>
              <a className="lp-btn lp-btn-quiet" href="https://github.com/ldom1/notion-pilot">
                Read the source
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ── close ────────────────────────────────────────────────────────── */}
      <section className="lp-close lp-wrap">
        <h2 className="lp-h2">Run your next real deal through it</h2>
        <p>
          One channel, one database, a week of real emails. Then look at the pipeline on Monday and
          decide whether you believe it.
        </p>
        <div className="lp-btn-row">
          <a className="lp-btn lp-btn-primary lp-btn-lg" href="/auth/notion">
            Deploy the CRM to Notion <Icon name="arrow" size={17} />
          </a>
          <a className="lp-btn lp-btn-quiet lp-btn-lg" href="#model">
            See the data model again
          </a>
        </div>
      </section>

      <footer className="lp-wrap">
        <div className="lp-foot">
          <span className="lp-brand" style={{ fontSize: "0.92rem" }}>
            <Logo /> Notion Pilot
          </span>
          <span>Self-hosted CRM automation for Notion · human-in-the-loop by default</span>
          <a href="/auth/notion?next=/cockpit">Sign in</a>
          <p className="lp-scope">
            <Icon name="shield" size={16} />
            <span>
              A CRM for teams working with <strong>French companies</strong> — every company
              enriches automatically from open company data (SIRENE registry, financial filings).
              Companies outside France are skipped, not enriched.
            </span>
          </p>
        </div>
      </footer>
    </div>
  );
}
