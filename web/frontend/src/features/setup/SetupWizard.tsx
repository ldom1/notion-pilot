import React, { useEffect, useRef, useState } from "react";
import { runSetup } from "../../api/client";
import type { SSEEvent } from "../../api/client";

type DeployState = "idle" | "deploying" | "done" | "error";

interface SetupWizardProps {
  onComplete?: (notionUrl: string | null) => void;
  onSkip?: () => void;
}

function LogLine({ line, isLast, deploying }: { line: string; isLast: boolean; deploying: boolean }) {
  const isSuccess = line.startsWith("✓");
  const isSubStep = line.startsWith("  →");
  const isError = line.startsWith("✗");
  return (
    <div
      style={{
        color: isError ? "#c0392b" : isSuccess ? "#1e7e34" : isSubStep ? "#888" : "#333",
        fontWeight: isSuccess ? 700 : "normal",
        paddingLeft: isSubStep ? "0.75rem" : undefined,
        display: "flex",
        alignItems: "center",
        gap: "0.4rem",
        fontSize: "0.78rem",
        fontFamily: "monospace",
        lineHeight: 1.5,
      }}
    >
      {isLast && deploying && <span className="log-spinner" />}
      {line}
    </div>
  );
}

export function SetupWizard({ onComplete, onSkip }: SetupWizardProps): React.ReactElement {
  const [workspaceName, setWorkspaceName] = useState("My Notion Workspace");
  const [scope, setScope] = useState<"crm" | "inbox" | "both">("both");
  const [deployState, setDeployState] = useState<DeployState>("idle");
  const [logs, setLogs] = useState<string[]>([]);
  const [notionUrl, setNotionUrl] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

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
          const url = event.url as string | null ?? null;
          setNotionUrl(url);
          setDeployState("done");
          onComplete?.(url);
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
      <div style={s.card}>
        <div style={s.successIcon}>✓</div>
        <h2 style={s.title}>Workspace ready!</h2>
        {logs.length > 0 && (
          <div style={{ ...s.logBox, maxHeight: "200px" }} ref={logRef}>
            {logs.map((l, i) => <LogLine key={i} line={l} isLast={false} deploying={false} />)}
          </div>
        )}
        <div style={s.actions}>
          {notionUrl && (
            <a className="btn-primary" href={notionUrl} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
              Open in Notion ↗
            </a>
          )}
          <button type="button" className="btn-primary" onClick={() => onSkip?.()}>
            Go to Cockpit →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={s.card}>
      <h2 style={s.title}>Set up your workspace</h2>
      <p style={s.sub}>We'll create the Notion databases for you. Takes about 10 seconds.</p>

      <div style={s.field}>
        <label style={s.label}>Workspace name</label>
        <input
          className="modal-param-input"
          style={{ width: "100%", boxSizing: "border-box" }}
          value={workspaceName}
          onChange={(e) => setWorkspaceName(e.target.value)}
          disabled={deployState === "deploying"}
          placeholder="My Notion Workspace"
        />
      </div>

      <div style={s.field}>
        <label style={s.label}>What do you need?</label>
        <div style={s.scopeRow}>
          {(["crm", "inbox", "both"] as const).map((opt) => (
            <button
              key={opt}
              type="button"
              className={`deal-wizard-opt${scope === opt ? " selected" : ""}`}
              onClick={() => setScope(opt)}
              disabled={deployState === "deploying"}
              style={{ flex: 1 }}
            >
              {opt === "crm" ? "CRM" : opt === "inbox" ? "Knowledge inbox" : "Both"}
            </button>
          ))}
        </div>
        <div style={s.scopeDesc}>
          {scope === "crm" && "People, Companies, Leads — full CRM with demo data"}
          {scope === "inbox" && "Notions, Ideas, Tools, Data & Tech databases"}
          {scope === "both" && "CRM + Knowledge inbox — the full Notion Pilot suite"}
        </div>
      </div>

      {(deployState === "deploying" || deployState === "error") && (
        <div style={s.logBox} ref={logRef}>
          {logs.length === 0
            ? <div style={{ color: "#999", fontSize: "0.78rem", fontFamily: "monospace" }}>Connecting to Notion…</div>
            : logs.map((l, i) => (
                <LogLine key={i} line={l} isLast={i === logs.length - 1} deploying={deployState === "deploying"} />
              ))
          }
        </div>
      )}

      <div style={s.actions}>
        {onSkip && (
          <button type="button" className="modal-cancel-btn" onClick={onSkip} disabled={deployState === "deploying"}>
            Skip
          </button>
        )}
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

const s: Record<string, React.CSSProperties> = {
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
    maxHeight: "160px",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: "0.2rem",
  },
  actions: { display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "0.25rem" },
  successIcon: { fontSize: "2.5rem", textAlign: "center" },
};
