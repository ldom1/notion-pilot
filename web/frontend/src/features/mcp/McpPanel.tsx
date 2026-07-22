type ToolKind = "write" | "read";

const TOOLS: { name: string; desc: string; kind: ToolKind }[] = [
  { name: "upsert_people", desc: "Upsert people into the Notion People database, dedup-checked (exact email/LinkedIn match, then fuzzy name+company). Dry-run by default.", kind: "write" },
  { name: "upsert_companies", desc: "Upsert companies into the Notion Companies database, dedup-checked; new companies get SIREN + sector/size/country enriched. Dry-run by default.", kind: "write" },
  { name: "enrich_people", desc: "Enrich People records missing seniority/role/email via prosper's enrich_person MCP tool. Dry-run by default.", kind: "write" },
  { name: "enrich_companies", desc: "Enrich Company records missing sector/size/country/LinkedIn via prosper's enrich_company MCP tool. Dry-run by default.", kind: "write" },
  { name: "find_duplicates", desc: "Find likely-duplicate People/Companies pairs already in Notion via fuzzy name matching.", kind: "read" },
  { name: "rank_contacts_for_pitch", desc: "Rank existing CRM contacts by relevance to a B2B sales pitch (LLM-powered).", kind: "read" },
  { name: "search_people", desc: "Fuzzy-search existing People by name/company.", kind: "read" },
  { name: "search_companies", desc: "Fuzzy-search existing Companies by name.", kind: "read" },
  { name: "get_recent_people", desc: "People added to Notion in the last 7 days.", kind: "read" },
  { name: "get_open_leads", desc: "Open (non-closed) deals from the Deals database.", kind: "read" },
  { name: "refresh_notion_snapshot", desc: "Force-reload the cached People/Companies snapshot from Notion.", kind: "read" },
];

const WRITE_TOOLS = TOOLS.filter((t) => t.kind === "write");
const READ_TOOLS = TOOLS.filter((t) => t.kind === "read");

const CONFIG_SNIPPET = `{
  "mcpServers": {
    "notion-crm": {
      "command": "uv",
      "args": ["--directory", "/path/to/notion-pilot", "run", "python", "-m", "notion_pilot.mcp.server"]
    }
  }
}`;

export function McpPanel() {
  return (
    <section className="panel">
      <div className="panel-header">
        <span className="panel-title">MCP Server</span>
        <span style={{ display: "flex", gap: "0.35rem" }}>
          <span className="script-cat-badge crm">stdio</span>
          <span className="script-cat-badge inbox">http (optional)</span>
        </span>
      </div>

      <p className="script-desc" style={{ marginBottom: "1rem" }}>
        <code>notion_pilot/mcp/</code> exposes the CRM vertical (dedup&apos;d upsert,
        enrichment, duplicate scan, pitch-based ranking, read queries) as MCP tools.
        By default any MCP-aware client launches it over stdio as a local subprocess —
        there is no persistent server to report live status here. When the deployment
        sets <code>MCP_BEARER_TOKEN</code>, the same tools are also reachable remotely
        over HTTP at <code>/mcp</code>, gated by that bearer token.
      </p>

      <div className="log-body" style={{ borderRadius: "9px", marginBottom: "1rem" }}>
        <pre className="log-line" style={{ margin: 0 }}>{CONFIG_SNIPPET}</pre>
      </div>

      <details className="mcp-section" open>
        <summary className="mcp-section-label">
          <span className="mcp-chevron">▸</span> Write · confirm required ({WRITE_TOOLS.length})
        </summary>
        <div className="wf-cards-list">
          {WRITE_TOOLS.map((tool) => (
            <McpToolCard key={tool.name} tool={tool} />
          ))}
        </div>
      </details>

      <details className="mcp-section" open>
        <summary className="mcp-section-label">
          <span className="mcp-chevron">▸</span> Read-only ({READ_TOOLS.length})
        </summary>
        <div className="wf-cards-list">
          {READ_TOOLS.map((tool) => (
            <McpToolCard key={tool.name} tool={tool} />
          ))}
        </div>
      </details>
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
