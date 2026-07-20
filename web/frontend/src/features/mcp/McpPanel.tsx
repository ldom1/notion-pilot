const TOOLS: { name: string; desc: string }[] = [
  { name: "upsert_people", desc: "Upsert people into the Notion People database, dedup-checked (exact email/LinkedIn match, then fuzzy name+company). Dry-run by default." },
  { name: "upsert_companies", desc: "Upsert companies into the Notion Companies database, dedup-checked; new companies get SIREN + sector/size/country enriched. Dry-run by default." },
  { name: "find_duplicates", desc: "Find likely-duplicate People/Companies pairs already in Notion via fuzzy name matching." },
  { name: "enrich_people", desc: "Enrich People records missing seniority/role/email via prosper's enrich_person MCP tool." },
  { name: "enrich_companies", desc: "Enrich Company records missing sector/size/country/LinkedIn via prosper's enrich_company MCP tool." },
  { name: "rank_contacts_for_pitch", desc: "Rank existing CRM contacts by relevance to a B2B sales pitch (LLM-powered)." },
  { name: "search_people", desc: "Fuzzy-search existing People by name/company — read-only." },
  { name: "search_companies", desc: "Fuzzy-search existing Companies by name — read-only." },
  { name: "get_recent_people", desc: "People added to Notion in the last 7 days." },
  { name: "get_open_leads", desc: "Open (non-closed) deals from the Deals database." },
  { name: "refresh_notion_snapshot", desc: "Force-reload the cached People/Companies snapshot from Notion." },
];

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
        <span className="script-cat-badge crm">stdio</span>
      </div>

      <p className="script-desc" style={{ marginBottom: "1rem" }}>
        <code>notion_pilot/mcp/</code> exposes the CRM vertical (dedup&apos;d upsert,
        enrichment, duplicate scan, pitch-based ranking, read queries) as MCP tools
        over stdio, so any MCP-aware client can ingest, dedup, enrich, and query
        Notion CRM data directly. It runs as a subprocess launched by the client —
        there is no persistent server to report live status here.
      </p>

      <div className="log-body" style={{ borderRadius: "9px", marginBottom: "1rem" }}>
        <pre className="log-line" style={{ margin: 0 }}>{CONFIG_SNIPPET}</pre>
      </div>

      <div className="wf-cards-list">
        {TOOLS.map((tool) => (
          <div className="wf-card" key={tool.name} style={{ alignItems: "flex-start" }}>
            <div className="wf-card-info">
              <div className="wf-card-name mcp-tool-name" style={{ fontSize: "0.8rem" }}>
                {tool.name}
              </div>
              <div className="wf-card-meta" style={{ marginTop: "0.3rem", lineHeight: 1.45 }}>
                {tool.desc}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
