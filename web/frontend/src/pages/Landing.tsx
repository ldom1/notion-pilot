import React, { useEffect, useRef, useState } from "react";
import { fetchStatus, runSetup } from "../api/client";
import type { SSEEvent } from "../api/client";
import { Spinner } from "../components/Spinner";

type CheckState = "idle" | "checking" | "authenticated" | "unauthenticated" | "setup";
type DeployState = "idle" | "deploying" | "done" | "error";

// ── Setup Wizard ──────────────────────────────────────────────────────────────

function SetupWizard(): React.ReactElement {
  const [workspaceName, setWorkspaceName] = useState("My Notion Workspace");
  const [scope, setScope] = useState<"crm" | "inbox" | "both">("crm");
  const [deployState, setDeployState] = useState<DeployState>("idle");
  const [logs, setLogs] = useState<string[]>([]);
  const [notionUrl, setNotionUrl] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  // Auto-scroll log box whenever logs update
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  async function handleDeploy(): Promise<void> {
    if (!workspaceName.trim() || deployState === "deploying") return;
    setDeployState("deploying");
    setLogs([]);
    try {
      const stream = runSetup({ scope, workspace_name: workspaceName.trim() });
      for await (const event of stream as AsyncIterable<SSEEvent>) {
        if (event.type === "log") {
          setLogs((prev) => [...prev, String(event.message ?? "")]);
        } else if (event.type === "done") {
          setNotionUrl(event.url ?? null);
          setDeployState("done");
        } else if (event.type === "error") {
          setLogs((prev) => [...prev, `✗ ${String(event.message ?? "Unknown error")}`]);
          setDeployState("error");
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setLogs((prev) => [...prev, `✗ ${msg}`]);
      setDeployState("error");
    }
  }

  if (deployState === "done") {
    return (
      <div style={wizardStyles.card}>
        <div style={wizardStyles.successIcon}>✓</div>
        <h2 style={wizardStyles.title}>Workspace ready!</h2>
        {logs.length > 0 && (
          <div style={{ ...wizardStyles.logBox, maxHeight: "200px" }} ref={logRef}>
            {logs.map((l, i) => (
              <div key={i} style={wizardStyles.logLine}>{l}</div>
            ))}
          </div>
        )}
        <div style={wizardStyles.actions}>
          {notionUrl && (
            <a
              className="btn-primary"
              href={notionUrl}
              target="_blank"
              rel="noreferrer"
              style={{ textDecoration: "none" }}
            >
              Open in Notion ↗
            </a>
          )}
          <button
            type="button"
            className="btn-primary"
            onClick={() => { window.location.href = "/cockpit"; }}
          >
            Go to Cockpit →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={wizardStyles.card}>
      <h2 style={wizardStyles.title}>Set up your workspace</h2>
      <p style={wizardStyles.sub}>
        We'll create the Notion databases for you. Takes about 10 seconds.
      </p>

      <div style={wizardStyles.field}>
        <label style={wizardStyles.label}>Workspace name</label>
        <input
          className="modal-param-input"
          style={{ width: "100%", boxSizing: "border-box" }}
          value={workspaceName}
          onChange={(e) => setWorkspaceName(e.target.value)}
          disabled={deployState === "deploying"}
          placeholder="My Notion Workspace"
        />
      </div>

      <div style={wizardStyles.field}>
        <label style={wizardStyles.label}>What do you need?</label>
        <div style={wizardStyles.scopeRow}>
          {(["crm", "inbox", "both"] as const).map((s) => (
            <button
              key={s}
              type="button"
              className={`deal-wizard-opt${scope === s ? " selected" : ""}`}
              onClick={() => setScope(s)}
              disabled={deployState === "deploying"}
              style={{ flex: 1 }}
            >
              {s === "crm" ? "CRM" : s === "inbox" ? "Knowledge inbox" : "Both"}
            </button>
          ))}
        </div>
        <div style={wizardStyles.scopeDesc}>
          {scope === "crm" && "People, Companies, Leads — full CRM with demo data"}
          {scope === "inbox" && "Notions, Ideas, Tools, Data & Tech databases"}
          {scope === "both" && "CRM + Knowledge inbox — the full Notion Pilot suite"}
        </div>
      </div>

      {(deployState === "deploying" || deployState === "error") && (
        <div style={wizardStyles.logBox} ref={logRef}>
          {logs.length === 0
            ? <div style={{ ...wizardStyles.logLine, color: "#999" }}>Connecting to Notion…</div>
            : logs.map((l, i) => <div key={i} style={wizardStyles.logLine}>{l}</div>)
          }
          {deployState === "deploying" && <div style={{ ...wizardStyles.logLine, color: "#999" }}>▌</div>}
        </div>
      )}

      <div style={wizardStyles.actions}>
        <button
          type="button"
          className="modal-cancel-btn"
          onClick={() => { window.location.href = "/cockpit"; }}
          disabled={deployState === "deploying"}
        >
          Skip, go to cockpit
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void handleDeploy()}
          disabled={deployState === "deploying" || !workspaceName.trim()}
        >
          {deployState === "deploying" ? "Creating…" : deployState === "error" ? "Retry" : "Deploy"}
        </button>
      </div>
    </div>
  );
}

const wizardStyles: Record<string, React.CSSProperties> = {
  card: {
    background: "#fff",
    borderRadius: "12px",
    border: "1px solid #e8e8e8",
    padding: "2rem",
    maxWidth: "480px",
    width: "100%",
    display: "flex",
    flexDirection: "column",
    gap: "1.25rem",
  },
  title: { fontSize: "1.4rem", fontWeight: 800, color: "#1a1a1a", margin: 0 },
  sub: { fontSize: "0.9rem", color: "#666", margin: 0, lineHeight: 1.5 },
  field: { display: "flex", flexDirection: "column", gap: "0.5rem" },
  label: { fontSize: "0.85rem", fontWeight: 600, color: "#444" },
  scopeRow: { display: "flex", gap: "0.5rem" },
  scopeDesc: { fontSize: "0.8rem", color: "#888", minHeight: "1.2em" },
  logBox: {
    background: "#f7f7f7",
    borderRadius: "6px",
    padding: "0.75rem",
    fontSize: "0.78rem",
    fontFamily: "monospace",
    maxHeight: "160px",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: "0.2rem",
  },
  logLine: { color: "#333" },
  actions: { display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "0.25rem" },
  successIcon: { fontSize: "2.5rem", textAlign: "center" },
};

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
      <div style={styles.page}>
        <nav style={styles.nav}>
          <span className="hdr-logo">Notion Pilot</span>
          <a href="/auth/logout" style={{ fontSize: "0.85rem", color: "#888" }}>Sign out</a>
        </nav>
        <main style={{ ...styles.hero, alignItems: "flex-start", paddingTop: "3rem" }}>
          <div style={{ maxWidth: "480px", width: "100%", margin: "0 auto" }}>
            <SetupWizard />
          </div>
        </main>
      </div>
    );
  }

  // unauthenticated — show landing hero
  return (
    <div style={styles.page}>
      <nav style={styles.nav}>
        <div style={styles.navLeft}>
          <span className="hdr-logo">Notion Pilot</span>
        </div>
        <div style={styles.navRight}>
          <button className="nav-deploy" onClick={() => { window.location.href = "/auth/notion"; }}>
            Deploy to Notion
          </button>
          <a className="nav-login" href="/auth/notion?next=/cockpit">
            Sign in
          </a>
        </div>
      </nav>

      <main style={styles.hero}>
        <div style={styles.heroInner}>
          <h1 style={styles.heading}>Your Notion workspace,<br />on autopilot.</h1>
          <p style={styles.tagline}>
            Sync contacts, manage deals, and automate your inbox — with built-in automation, IA and Telegram integration.
          </p>

          <button
            className="btn-primary"
            style={styles.cta}
            onClick={() => { window.location.href = "/auth/notion"; }}
          >
            Deploy your workspace
          </button>

          <ul style={styles.featureList}>
            <li style={styles.featureItem}>
              <span style={styles.featureDot} />
              <span>
                <strong>CRM</strong> — people, companies, deals and enrichment synced to Notion
              </span>
            </li>
            <li style={styles.featureItem}>
              <span style={styles.featureDot} />
              <span>
                <strong>Inbox</strong> — capture from Telegram, email, and Discord with LLM enrichment
              </span>
            </li>
            <li style={styles.featureItem}>
              <span style={styles.featureDot} />
              <span>
                <strong>Automation</strong> — compose and schedule workflows from the cockpit
              </span>
            </li>
          </ul>
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    background: "#f5f4ff",
  },
  nav: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 2rem",
    height: "54px",
    background: "#fff",
    borderBottom: "1px solid #f0f0f0",
    position: "sticky",
    top: 0,
    zIndex: 100,
  },
  navLeft: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
  },
  navRight: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
  },
  hero: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "4rem 1.5rem",
  },
  heroInner: {
    maxWidth: "520px",
    width: "100%",
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: "1.5rem",
  },
  heading: {
    fontSize: "2.25rem",
    fontWeight: 900,
    lineHeight: 1.15,
    color: "#1a1a1a",
    letterSpacing: "-0.5px",
  },
  tagline: {
    fontSize: "1rem",
    color: "#555",
    lineHeight: 1.6,
    marginTop: "-0.5rem",
  },
  cta: {
    fontSize: "1rem",
    padding: "0.75rem 1.75rem",
    borderRadius: "8px",
  },
  featureList: {
    listStyle: "none",
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
    marginTop: "0.5rem",
    padding: 0,
  },
  featureItem: {
    display: "flex",
    alignItems: "flex-start",
    gap: "0.65rem",
    fontSize: "0.9rem",
    color: "#444",
    lineHeight: 1.5,
  },
  featureDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    background: "#6e56cf",
    flexShrink: 0,
    marginTop: "0.35rem",
  },
};
