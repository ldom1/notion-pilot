import React, { useEffect, useState } from "react";
import { fetchStatus } from "../api/client";

type CheckState = "idle" | "checking" | "authenticated" | "unauthenticated";

export default function Landing() {
  const [checkState, setCheckState] = useState<CheckState>("idle");

  useEffect(() => {
    setCheckState("checking");
    fetchStatus()
      .then(() => {
        setCheckState("authenticated");
        window.location.href = "/cockpit";
      })
      .catch(() => {
        setCheckState("unauthenticated");
      });
  }, []);

  if (checkState === "idle" || checkState === "checking") {
    return (
      <div style={styles.center}>
        <div style={styles.spinner} />
      </div>
    );
  }

  if (checkState === "authenticated") {
    // Will redirect via window.location — show spinner while navigating
    return (
      <div style={styles.center}>
        <div style={styles.spinner} />
      </div>
    );
  }

  const startDeploy = () => { window.location.href = "/auth/notion?next=/cockpit"; };

  // unauthenticated — show landing hero
  return (
    <div style={styles.page}>
      <nav style={styles.nav}>
        <div style={styles.navLeft}>
          <span className="hdr-logo">Notion Pilot</span>
          <span className="hdr-badge">BETA</span>
        </div>
        <div style={styles.navRight}>
          <button className="nav-deploy" onClick={startDeploy}>
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
            onClick={() => {
              window.location.href = "/auth/notion?next=/cockpit";
            }}
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
  center: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  spinner: {
    width: "32px",
    height: "32px",
    border: "3px solid #ece8ff",
    borderTopColor: "#6e56cf",
    borderRadius: "50%",
    animation: "spin 0.7s linear infinite",
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
