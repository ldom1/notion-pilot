import type { ReactNode } from "react";

const NOTION_MCP = "https://mcp.notion.com/mcp";
const NOTION_MCP_DOCS = "https://developers.notion.com/guides/mcp/get-started-with-mcp";
const NOTION_MCP_HELP = "https://www.notion.com/help/notion-mcp";
const CLAUDE_CONNECTOR = "https://claude.com/connectors/notion";
const REPO = "https://github.com/ldom1/notion-pilot-powers";

const MCP_SNIPPET = `# Claude Code
claude mcp add --transport http notion ${NOTION_MCP}
# then run /mcp and complete the OAuth flow

# Cursor — .cursor/mcp.json
{
  "mcpServers": {
    "notion": { "url": "${NOTION_MCP}" }
  }
}`;

const INSTALL_SNIPPET = `/plugin marketplace add ldom1/notion-pilot-powers
/plugin install notion-pilot-powers@notion-pilot-powers`;

const SKILLS = [
  {
    name: "crm-ops",
    href: `${REPO}/tree/main/skills/crm-ops`,
    body: "Operate the CRM — create and update leads, log activities, enrich people and companies. Always a validation table, then wait for your go.",
  },
  {
    name: "company-enrichment",
    href: `${REPO}/tree/main/skills/company-enrichment`,
    body: "Fill French firmographics from open data (SIREN, NAF/APE, BODACC, RNE) instead of typing them. Same preview-then-go discipline.",
  },
] as const;

function ForTheDev({ children }: { children: ReactNode }) {
  return (
    <details className="mcp-section">
      <summary className="mcp-section-label">
        <span className="mcp-chevron">▸</span> For the dev
      </summary>
      {children}
    </details>
  );
}

export function AssistantSetupPanel() {
  return (
    <section className="panel" aria-labelledby="assistant-setup-title">
      <div className="panel-header">
        <span className="panel-title" id="assistant-setup-title">Your AI assistant</span>
      </div>

      <p className="setup-lede">
        The CRM lives in Notion. Connect your assistant from Notion&apos;s own
        settings, then install the Pilot plugin so every write is a preview until
        you approve.
      </p>

      <div className="setup-steps">
        <div className="setup-step">
          <h3>1. Connect Notion</h3>
          <p>
            In Notion, open Settings → Connections → Notion MCP. Pick Claude,
            Mistral, ChatGPT or Cursor, sign in once, then restart the assistant.
            It sees the pages you can see, including this CRM.
          </p>
          <div className="setup-docs">
            <a href={NOTION_MCP_HELP} target="_blank" rel="noopener noreferrer">
              Notion Help →
            </a>
            <a href={CLAUDE_CONNECTOR} target="_blank" rel="noopener noreferrer">
              Claude connector →
            </a>
          </div>
          <ForTheDev>
            <div className="log-body">
              <pre className="log-line">{MCP_SNIPPET}</pre>
            </div>
            <div className="setup-docs">
              <a href={NOTION_MCP_DOCS} target="_blank" rel="noopener noreferrer">
                Developer setup →
              </a>
            </div>
          </ForTheDev>
        </div>

        <div className="setup-step">
          <h3>2. Install the plugin</h3>
          <p>
            An MCP connection only gives hands — the plugin skills are the
            instructions. In Claude Code, run the two commands below (marketplace
            add, then install).
          </p>
          <ForTheDev>
            <div className="log-body">
              <pre className="log-line">{INSTALL_SNIPPET}</pre>
            </div>
            <div className="setup-docs">
              <a href={REPO} target="_blank" rel="noopener noreferrer">
                notion-pilot-powers →
              </a>
            </div>
          </ForTheDev>
        </div>
      </div>

      <div className="setup-skills">
        {SKILLS.map((s) => (
          <div className="setup-skill" key={s.name}>
            <b>{s.name}</b>
            <p>{s.body}</p>
            <a href={s.href} target="_blank" rel="noopener noreferrer">
              Skill docs →
            </a>
          </div>
        ))}
      </div>
    </section>
  );
}
