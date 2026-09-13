import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchNotionPages,
  fetchSetupCapabilities,
  runSetup,
} from "../../api/client";
import type { NotionPage, SSEEvent } from "../../api/client";
import "./setup-wizard.css";

type DeployState = "idle" | "deploying" | "done" | "error";
type ParentKind = "root" | "page";

interface SetupWizardProps {
  onComplete?: (notionUrl: string | null) => void;
  onSkip?: () => void;
}

function logKind(line: string): "ok" | "bad" | "sub" | "step" {
  if (line.startsWith("✓")) return "ok";
  if (line.startsWith("✗")) return "bad";
  if (line.startsWith("  →")) return "sub";
  return "step";
}

function logText(line: string): string {
  return line.replace(/^✓\s*/, "").replace(/^✗\s*/, "").replace(/^\s*→\s*/, "");
}

function LogLine({ line, isLast, deploying }: { line: string; isLast: boolean; deploying: boolean }) {
  const kind = logKind(line);
  const pending = isLast && deploying && kind !== "ok" && kind !== "bad";
  return (
    <div className={`lp-setup-log-line is-${kind}`}>
      <span className="lp-setup-log-mark" aria-hidden="true">
        {pending ? <span className="lp-setup-tree-spin" /> : kind === "ok" ? "✓" : kind === "bad" ? "!" : kind === "sub" ? "→" : "·"}
      </span>
      <span>{logText(line)}</span>
    </div>
  );
}

function SetupLog({
  logs,
  deploying,
  failed,
  logRef,
}: {
  logs: string[];
  deploying: boolean;
  failed?: boolean;
  logRef: React.RefObject<HTMLDivElement | null>;
}): React.ReactElement {
  return (
    <div className={`lp-setup-log${failed ? " is-fail" : ""}`}>
      <div className="lp-setup-log-head">
        {deploying && <span className="lp-setup-tree-spin" aria-hidden="true" />}
        {failed ? "Failed" : deploying ? "Deploying" : "Deployed"}
      </div>
      <div className="lp-setup-log-body" ref={logRef} role="log">
        {logs.length === 0 ? (
          <div className="lp-setup-log-line is-step">
            <span className="lp-setup-log-mark" aria-hidden="true">
              <span className="lp-setup-tree-spin" />
            </span>
            <span>Connecting to Notion…</span>
          </div>
        ) : (
          logs.map((l, i) => (
            <LogLine key={i} line={l} isLast={i === logs.length - 1} deploying={deploying} />
          ))
        )}
      </div>
    </div>
  );
}

export function SetupWizard({ onComplete, onSkip }: SetupWizardProps): React.ReactElement {
  const [pageName, setPageName] = useState("");
  const [canTopLevel, setCanTopLevel] = useState<boolean | null>(null);
  const [parentKind, setParentKind] = useState<ParentKind>("root");
  const [parentPage, setParentPage] = useState("");
  const [pageQuery, setPageQuery] = useState("");
  const [pages, setPages] = useState<NotionPage[]>([]);
  const [pagesTruncated, setPagesTruncated] = useState(false);
  const [pagesState, setPagesState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [deployState, setDeployState] = useState<DeployState>("idle");
  const [logs, setLogs] = useState<string[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [notionUrl, setNotionUrl] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const caps = await fetchSetupCapabilities();
        if (cancelled) return;
        setCanTopLevel(caps.can_create_top_level);
        if (!caps.can_create_top_level) setParentKind("page");
      } catch {
        if (!cancelled) setCanTopLevel(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadPages = useCallback(async (q = "") => {
    setPagesState("loading");
    try {
      const res = await fetchNotionPages(q);
      setPages(res.pages);
      setPagesTruncated(res.truncated);
      setPagesState("ok");
    } catch {
      setPages([]);
      setPagesTruncated(false);
      setPagesState("error");
    }
  }, []);

  useEffect(() => {
    if (parentKind !== "page") return;
    const t = window.setTimeout(() => void loadPages(pageQuery), pageQuery ? 350 : 0);
    return () => window.clearTimeout(t);
  }, [parentKind, pageQuery, loadPages]);

  async function handleDeploy(): Promise<void> {
    const name = pageName.trim();
    const parent = parentKind === "page" ? parentPage.trim() : "";
    if (!name || deployState === "deploying") return;
    if (parentKind === "page" && !parent) return;
    setDeployState("deploying");
    setLogs([]);
    setWarnings([]);
    try {
      const stream = runSetup({
        scope: "crm",
        workspace_name: name,
        parent_page_id: parent || null,
      });
      for await (const event of stream as AsyncIterable<SSEEvent>) {
        if (event.type === "log") {
          setLogs((prev) => [...prev, String(event.message ?? "")]);
        } else if (event.type === "warning") {
          const message = String(event.message ?? "");
          setWarnings((prev) => [...prev, message]);
          setLogs((prev) => [...prev, `⚠ ${message}`]);
        } else if (event.type === "done") {
          const url = (event.url as string | null) ?? null;
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
      <div className="lp-setup">
        <div className="lp-setup-ok">✓</div>
        <h2 className="lp-setup-title">Your CRM is ready</h2>
        <p className="lp-setup-done-sum">
          {warnings.length === 0
            ? "Your pipeline is on the CRM home, with Companies, People, Leads, Activities and Meetings below it."
            : "Your CRM works. A few views need a minute in Notion — the steps are on the CRM home."}
        </p>
        {warnings.length > 0 && (
          <ul className="lp-setup-warnings">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
        {logs.length > 0 && <SetupLog logs={logs} deploying={false} logRef={logRef} />}
        <div className="lp-setup-actions">
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
          <button type="button" className="btn-primary" onClick={() => onSkip?.()}>
            Go to Cockpit →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="lp-setup">
      <h2 className="lp-setup-title">Deploy the CRM to Notion</h2>
      <p className="lp-setup-sub">
        A ready-to-use CRM in the workspace you share — Companies, People, Leads, Activities,
        Meetings, relations wired. You reshape it. The assistant follows.
      </p>

      <div className="lp-setup-field">
        <label className="lp-setup-label" htmlFor="lp-setup-page">
          CRM main page name
        </label>
        <input
          id="lp-setup-page"
          className="modal-param-input"
          value={pageName}
          onChange={(e) => setPageName(e.target.value)}
          disabled={deployState === "deploying"}
          placeholder="My awesome CRM"
        />
      </div>

      <fieldset className="lp-setup-field" disabled={deployState === "deploying"}>
        <legend className="lp-setup-label">Where should it be deployed?</legend>
        <div className="lp-setup-tree" role="radiogroup" aria-label="Where should it be deployed?">
          <div className="lp-setup-tree-host">Workspace</div>
          <div className="lp-setup-tree-list">
            <label
              className={`lp-setup-tree-opt${parentKind === "root" ? " is-on" : ""}${canTopLevel === false ? " is-disabled" : ""}`}
              title={
                canTopLevel === false
                  ? "Notion does not allow internal integrations to create top-level pages"
                  : undefined
              }
            >
              <input
                type="radio"
                name="lp-setup-parent"
                checked={parentKind === "root"}
                onChange={() => setParentKind("root")}
                disabled={canTopLevel === false}
              />
              <span className="lp-setup-tree-copy">
                <span className="lp-setup-tree-title">Workspace root</span>
                <span className="lp-setup-tree-hint">
                  {canTopLevel === false
                    ? "Unavailable for internal integrations"
                    : "Top of the sidebar"}
                </span>
              </span>
            </label>
            {parentKind === "root" && (
              <div className="lp-setup-tree-leaf">{pageName.trim() || "My awesome CRM"}</div>
            )}
            <label className={`lp-setup-tree-opt${parentKind === "page" ? " is-on" : ""}`}>
              <input
                type="radio"
                name="lp-setup-parent"
                checked={parentKind === "page"}
                onChange={() => setParentKind("page")}
              />
              <span className="lp-setup-tree-copy">
                <span className="lp-setup-tree-title">Under an existing page</span>
                <span className="lp-setup-tree-hint">Child of a page you pick</span>
              </span>
            </label>
            {parentKind === "page" && (
              <div className="lp-setup-tree-nest">
                <input
                  className="modal-param-input"
                  value={pageQuery}
                  onChange={(e) => setPageQuery(e.target.value)}
                  placeholder="Search your pages…"
                  aria-label="Search Notion pages"
                />
                <div className="lp-setup-tree-pages">
                  {pagesState === "loading" && (
                    <div className="lp-setup-tree-status" role="status">
                      <span className="lp-setup-tree-spin" aria-hidden="true" />
                      Searching…
                    </div>
                  )}
                  {pagesState === "error" && (
                    <div className="lp-setup-tree-status">
                      Could not load pages from Notion.{" "}
                      <button
                        type="button"
                        className="lp-setup-tree-retry"
                        onClick={() => void loadPages(pageQuery)}
                      >
                        Retry
                      </button>
                    </div>
                  )}
                  {pagesState === "ok" && pages.length === 0 && (
                    <div className="lp-setup-tree-status">
                      {pageQuery ? (
                        <>No page matches “{pageQuery}”.</>
                      ) : (
                        <>
                          No pages shared with this connection. In Notion: ··· → Connections → add
                          this integration, then retry.
                        </>
                      )}
                    </div>
                  )}
                  {pages.map((p) => (
                    <div key={p.id} className="lp-setup-tree-pagewrap">
                      <button
                        type="button"
                        className={`lp-setup-tree-page${parentPage === p.id ? " is-on" : ""}`}
                        onClick={() => setParentPage(p.id)}
                      >
                        {p.name}
                      </button>
                      {parentPage === p.id && (
                        <div className="lp-setup-tree-leaf">
                          {pageName.trim() || "My awesome CRM"}
                        </div>
                      )}
                    </div>
                  ))}
                  {pagesState === "ok" && pagesTruncated && (
                    <div className="lp-setup-tree-status">
                      Showing recent pages — type to narrow the search.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </fieldset>

      {(deployState === "deploying" || deployState === "error") && (
        <SetupLog
          logs={logs}
          deploying={deployState === "deploying"}
          failed={deployState === "error"}
          logRef={logRef}
        />
      )}

      <div className="lp-setup-actions">
        {onSkip && (
          <button
            type="button"
            className="modal-cancel-btn"
            onClick={onSkip}
            disabled={deployState === "deploying"}
          >
            Skip
          </button>
        )}
        <button
          type="button"
          className="btn-primary"
          onClick={() => void handleDeploy()}
          disabled={
            deployState === "deploying"
            || !pageName.trim()
            || (parentKind === "page" && !parentPage.trim())
          }
        >
          {deployState === "deploying"
            ? "Creating…"
            : deployState === "error"
              ? "Retry"
              : "Deploy the CRM"}
        </button>
      </div>
    </div>
  );
}
