type ToolKind = "write" | "read";

/** Always-on tools (token + 4 IDs). Conditional Prosper/OpenRouter tools are footnote-only. */
const TOOLS: { name: string; desc: string; kind: ToolKind }[] = [
  { name: "upsert_people", desc: "Upsert people into the Notion People database, dedup-checked (exact email/LinkedIn match, then fuzzy name+company). Dry-run by default.", kind: "write" },
  { name: "upsert_companies", desc: "Upsert companies into the Notion Companies database, dedup-checked; new companies get SIREN + sector/size/country enriched. Dry-run by default.", kind: "write" },
  { name: "find_duplicates", desc: "Find likely-duplicate People/Companies pairs already in Notion via fuzzy name matching.", kind: "read" },
  { name: "search_people", desc: "Fuzzy-search existing People by name/company.", kind: "read" },
  { name: "search_companies", desc: "Fuzzy-search existing Companies by name.", kind: "read" },
  { name: "get_recent_people", desc: "People added to Notion in the last 7 days.", kind: "read" },
  { name: "get_open_leads", desc: "Open (non-closed) deals from the Deals database.", kind: "read" },
  { name: "upsert_deal", desc: "Upsert a Deal (\"Leads\" in this cockpit) into the Deals database, matched by exact title. Dry-run by default.", kind: "write" },
  { name: "log_activity", desc: "Log an Activity (call, meeting, email...) — an append-only event. Dry-run by default.", kind: "write" },
  { name: "get_activities", desc: "Recent Activities (calls, meetings, emails...), newest first; optionally scoped to one Deal.", kind: "read" },
  { name: "refresh_notion_snapshot", desc: "Force-reload the cached People/Companies snapshot from Notion.", kind: "read" },
  { name: "lookup_siren", desc: "Look up a French company SIREN via recherche-entreprises.api.gouv.fr (name → open data).", kind: "read" },
];

const WRITE_TOOLS = TOOLS.filter((t) => t.kind === "write");
const READ_TOOLS = TOOLS.filter((t) => t.kind === "read");

export function McpPanel() {
  return (
    <section className="panel">
      <div className="panel-header">
        <span className="panel-title">MCP Server</span>
        <span style={{ display: "flex", gap: "0.35rem" }}>
          <span className="script-cat-badge crm">stdio</span>
        </span>
      </div>

      <p className="script-desc" style={{ marginBottom: "1rem" }}>
        Optional local MCP from the <code>notion-pilot-powers</code> plugin —
        upsert, scan, rank, query. Fill the plugin settings (integration token +
        the four IDs below) when you want it; the default path needs none of that.
        Runs on your machine; this site only deploys the CRM.
      </p>

      <details className="mcp-section">
        <summary className="mcp-section-label">
          <span className="mcp-chevron">▸</span> Write · confirm required ({WRITE_TOOLS.length})
        </summary>
        <div className="wf-cards-list">
          {WRITE_TOOLS.map((tool) => (
            <McpToolCard key={tool.name} tool={tool} />
          ))}
        </div>
      </details>

      <details className="mcp-section">
        <summary className="mcp-section-label">
          <span className="mcp-chevron">▸</span> Read-only ({READ_TOOLS.length})
        </summary>
        <div className="wf-cards-list">
          {READ_TOOLS.map((tool) => (
            <McpToolCard key={tool.name} tool={tool} />
          ))}
        </div>
      </details>

      <p className="script-desc" style={{ marginTop: "0.85rem", fontSize: "0.75rem" }}>
        Conditional (not registered for customers): <code>enrich_people</code> /{" "}
        <code>enrich_companies</code> need Prosper; <code>rank_contacts_for_pitch</code>{" "}
        needs OpenRouter — only when the server is launched with{" "}
        <code>--with-external</code> and those env vars.
      </p>
    </section>
  );
}

function McpToolCard({ tool }: { tool: { name: string; desc: string; kind: ToolKind } }) {
  return (
    <div className="wf-card" style={{ alignItems: "flex-start" }}>
      <div className="wf-card-info">
        <div className="mcp-tool-top">
          <div className="wf-card-name mcp-tool-name" style={{ fontSize: "0.8rem" }}>
            {tool.name}
          </div>
          <span className={`mcp-kind-badge ${tool.kind}`}>{tool.kind}</span>
        </div>
        <div className="wf-card-meta" style={{ marginTop: "0.3rem", lineHeight: 1.45 }}>
          {tool.desc}
        </div>
      </div>
    </div>
  );
}
