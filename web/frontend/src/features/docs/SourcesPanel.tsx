// Mirrors notion_pilot/shared/doc_links.py — tests/unit/web/test_doc_links_parity.py
// fails when the URLs drift. Write every URL out in full (no template strings) so
// the test can read them.

const SOURCES_LEDE = "Enrichment covers French companies only. Others are stored, not enriched.";

const GROUPS = [
  {
    title: "Where your data comes from",
    links: [
      {
        title: "Your Notion workspace",
        url: "https://www.notion.com/help/sharing-and-permissions",
        blurb: "Every record lives here. Who can see it is Notion’s sharing, not ours.",
      },
      {
        title: "Recherche d’entreprises API",
        url: "https://recherche-entreprises.api.gouv.fr/docs/",
        blurb: "The French state API behind company enrichment: SIREN, sector, size, published financials.",
      },
      {
        title: "Annuaire des Entreprises",
        url: "https://annuaire-entreprises.data.gouv.fr",
        blurb: "Check a French company by hand, from the same public data.",
      },
      {
        title: "BODACC",
        url: "https://www.bodacc.fr",
        blurb: "Official legal announcements: creations, sales, insolvency.",
      },
    ],
  },
  {
    title: "Connect your assistant",
    links: [
      {
        title: "Notion connector for Claude",
        url: "https://claude.com/connectors/notion",
        blurb: "Add Notion to Claude desktop or claude.ai.",
      },
      {
        title: "Notion MCP",
        url: "https://www.notion.com/help/notion-mcp",
        blurb: "What an assistant can read and write in your workspace.",
      },
      {
        title: "Notion MCP for developers",
        url: "https://developers.notion.com/guides/mcp/get-started-with-mcp",
        blurb: "Claude Code, Cursor and other clients.",
      },
    ],
  },
  {
    title: "Go further",
    links: [
      {
        title: "notion-crm-ops skill",
        url: "https://github.com/ldom1/notion-pilot/tree/develop/skills/notion-crm-ops",
        blurb: "How the assistant creates leads and logs activities, preview first.",
      },
      {
        title: "company-open-data-enrichment skill",
        url: "https://github.com/ldom1/notion-pilot/tree/develop/skills/company-open-data-enrichment",
        blurb: "How French companies get enriched, and when it refuses.",
      },
      {
        title: "Views, filters & sorts",
        url: "https://www.notion.com/help/views-filters-and-sorts",
        blurb: "Reshape the views on this page.",
      },
      {
        title: "Notion Pilot on GitHub",
        url: "https://github.com/ldom1/notion-pilot",
        blurb: "Source, issues and changelog.",
      },
    ],
  },
] as const;

export function SourcesPanel() {
  return (
    <section className="panel" aria-labelledby="sources-title">
      <div className="panel-header">
        <span className="panel-title" id="sources-title">
          Sources &amp; documentation
        </span>
      </div>
      <p className="setup-lede">
        Where the data in your CRM comes from, and where to read more. {SOURCES_LEDE}
      </p>
      <div className="docs-grid">
        {GROUPS.map((group) => (
          <div className="docs-group" key={group.title}>
            <h3>{group.title}</h3>
            <ul>
              {group.links.map((link) => (
                <li key={link.url}>
                  <a href={link.url} target="_blank" rel="noopener noreferrer">
                    {link.title} <span aria-hidden="true">↗</span>
                  </a>
                  <p>{link.blurb}</p>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
