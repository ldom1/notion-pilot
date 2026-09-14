"""Sources & documentation — one list for the CRM home page and the cockpit.

The cockpit mirrors these URLs in web/frontend/src/features/docs/SourcesPanel.tsx;
tests/unit/web/test_doc_links_parity.py fails when the two drift. Each blurb says
why someone would open the link, not only what it is.
"""

from __future__ import annotations

from dataclasses import dataclass

REPO = "https://github.com/ldom1/notion-pilot"

SOURCES_LEDE = "Enrichment covers French companies only. Others are stored, not enriched."


@dataclass(frozen=True)
class DocLink:
    title: str
    url: str
    blurb: str


@dataclass(frozen=True)
class DocGroup:
    title: str
    links: tuple[DocLink, ...]


DOC_GROUPS: tuple[DocGroup, ...] = (
    DocGroup(
        "Where your data comes from",
        (
            DocLink(
                "Your Notion workspace",
                "https://www.notion.com/help/sharing-and-permissions",
                "Every record lives here. Who can see it is Notion’s sharing, not ours.",
            ),
            DocLink(
                "Recherche d’entreprises API",
                "https://recherche-entreprises.api.gouv.fr/docs/",
                "The French state API behind company enrichment: SIREN, sector, size, published financials.",
            ),
            DocLink(
                "Annuaire des Entreprises",
                "https://annuaire-entreprises.data.gouv.fr",
                "Check a French company by hand, from the same public data.",
            ),
            DocLink(
                "BODACC",
                "https://www.bodacc.fr",
                "Official legal announcements: creations, sales, insolvency.",
            ),
        ),
    ),
    DocGroup(
        "Connect your assistant",
        (
            DocLink(
                "Notion connector for Claude",
                "https://claude.com/connectors/notion",
                "Add Notion to Claude desktop or claude.ai.",
            ),
            DocLink(
                "Notion MCP",
                "https://www.notion.com/help/notion-mcp",
                "What an assistant can read and write in your workspace.",
            ),
            DocLink(
                "Notion MCP for developers",
                "https://developers.notion.com/guides/mcp/get-started-with-mcp",
                "Claude Code, Cursor and other clients.",
            ),
        ),
    ),
    DocGroup(
        "Go further",
        (
            DocLink(
                "crm-ops skill",
                "https://github.com/ldom1/notion-pilot-powers/tree/main/skills/crm-ops",
                "How the assistant creates leads and logs activities, preview first.",
            ),
            DocLink(
                "company-enrichment skill",
                "https://github.com/ldom1/notion-pilot-powers/tree/main/skills/company-enrichment",
                "How French companies get enriched, and when it refuses.",
            ),
            DocLink(
                "notion-pilot-powers",
                "https://github.com/ldom1/notion-pilot-powers",
                "Plugin marketplace, skills and optional local MCP.",
            ),
            DocLink(
                "Views, filters & sorts",
                "https://www.notion.com/help/views-filters-and-sorts",
                "Reshape the views on this page.",
            ),
            DocLink("Notion Pilot on GitHub", REPO, "Source, issues and changelog."),
        ),
    ),
)
