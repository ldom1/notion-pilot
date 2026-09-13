const NOTION_MCP = "https://mcp.notion.com/mcp";
const NOTION_MCP_DOCS = "https://developers.notion.com/guides/mcp/get-started-with-mcp";
const NOTION_MCP_HELP = "https://www.notion.com/help/notion-mcp";
const REPO = "https://github.com/ldom1/notion-pilot";

const MCP_SNIPPET = `# Claude Code
claude mcp add --transport http notion ${NOTION_MCP}
# then run /mcp and complete the OAuth flow

# Cursor — .cursor/mcp.json
{ "mcpServers": { "notion": { "url": "${NOTION_MCP}" } } }`;

const INSTALL_SNIPPET = `/plugin marketplace add ldom1/notion-pilot
/plugin install notion-crm@notion-pilot`;

const SKILLS = [
  {
    name: "notion-crm-ops",
    href: `${REPO}/tree/develop/skills/notion-crm-ops`,
    body: "Operate the CRM — create and update leads, log activities, enrich people and companies. Always a validation table, then wait for your go.",
  },
  {
    name: "company-open-data-enrichment",
    href: `${REPO}/tree/develop/skills/company-open-data-enrichment`,
    body: "Fill French firmographics from open data (SIREN, NAF/APE, BODACC, RNE) instead of typing them. Same preview-then-go discipline.",
  },
] as const;

export function AssistantSetupPanel() {
  return (
    <section className="panel">
      <div className="panel-header">
        <span className="panel-title">Your AI assistant</span>
      </div>

      <p className="setup-lede">
        The CRM lives in Notion. Claude or Cursor does the typing — connect
        Notion&apos;s hosted MCP, then install the Pilot skills so every write is a
        preview until you approve.
      </p>

      <div className="setup-steps">
        <div className="setup-step">
          <h3>1. Connect Notion MCP</h3>
          <p>
            Notion&apos;s hosted server, not this app&apos;s integration. Complete OAuth once
            — it sees the pages you can see, including the CRM you deployed. Restart
            the assistant afterwards.
          </p>
          <pre>{MCP_SNIPPET}</pre>
          <div className="setup-docs">
            <a href={NOTION_MCP_DOCS} target="_blank" rel="noopener noreferrer">
              Developer setup →
            </a>
            <a href={NOTION_MCP_HELP} target="_blank" rel="noopener noreferrer">
              Notion Help →
            </a>
          </div>
        </div>

        <div className="setup-step">
          <h3>2. Install the skills</h3>
          <p>
            Two lines in Claude Code. Both skills arrive together and update with
            the repo. An MCP connection alone only gives hands — the skills are the
            instructions.
          </p>
          <pre>{INSTALL_SNIPPET}</pre>
          <div className="setup-docs">
            <a href={`${REPO}#agent-skills-artelys-crm`} target="_blank" rel="noopener noreferrer">
              Skills in the repo →
            </a>
          </div>
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
