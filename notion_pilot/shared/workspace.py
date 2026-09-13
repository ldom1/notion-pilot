"""Shared Notion workspace creation logic used by CLI scripts, Telegram /setup, and web server."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import httpx
from loguru import logger

from notion_pilot.shared.doc_links import DOC_GROUPS, SOURCES_LEDE
from notion_pilot.shared.notion_views import ViewSpec, ViewsOutcome, create_home_views

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"
type JsonDict = dict[str, Any]


# --- block helpers ---

RichText = str | list[JsonDict]


def _rt(content: str) -> list[JsonDict]:
    return [{"type": "text", "text": {"content": content}}]


def _rich(content: RichText) -> list[JsonDict]:
    return _rt(content) if isinstance(content, str) else content


def _text(content: str, *, url: str | None = None, bold: bool = False) -> JsonDict:
    item: JsonDict = {"type": "text", "text": {"content": content}}
    if url:
        item["text"]["link"] = {"url": url}
    if bold:
        item["annotations"] = {"bold": True}
    return item


def _paragraph(content: str) -> JsonDict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(content)}}


def _h2(content: str) -> JsonDict:
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": _rt(content)}}


def _callout(
    content: RichText, emoji: str = "💡", children: list[JsonDict] | None = None
) -> JsonDict:
    callout: JsonDict = {"rich_text": _rich(content), "icon": {"type": "emoji", "emoji": emoji}}
    if children:
        callout["children"] = children
    return {"object": "block", "type": "callout", "callout": callout}


def _bullet(content: RichText) -> JsonDict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rich(content)},
    }


def _numbered(content: str) -> JsonDict:
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": _rt(content)},
    }


def _h3(content: str) -> JsonDict:
    return {"object": "block", "type": "heading_3", "heading_3": {"rich_text": _rt(content)}}


def _toggle(title: str, children: list[JsonDict]) -> JsonDict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {"rich_text": _rt(title), "children": children},
    }


def _code(content: str, language: str = "plain text") -> JsonDict:
    return {
        "object": "block",
        "type": "code",
        "code": {"rich_text": _rt(content), "language": language},
    }


def _plain_text(block: JsonDict) -> str:
    """Plain text of a block as we wrote it or as Notion returns it."""
    payload = block.get(block.get("type", ""), {})
    return "".join(
        item.get("plain_text") or item.get("text", {}).get("content", "")
        for item in payload.get("rich_text", [])
    )


def find_block(blocks: list[JsonDict], block_type: str, text: str) -> str:
    return str(next(b["id"] for b in blocks if b["type"] == block_type and _plain_text(b) == text))


# --- page content blocks ---

_ROOT_CHILDREN: list[JsonDict] = [
    _paragraph("Your Notion business brain, piloted by Telegram."),
    _callout(
        "👋 First time? Try: /lead TechCorp — Notion Pilot will create a company and ask you for the details.",
        "💡",
    ),
    _h2("Your workspaces"),
    _h2("Telegram quick reference"),
    _bullet("/lead — Create or update a company"),
    _bullet("/deal — Log a deal"),
    _bullet("/people — Add a contact"),
    _bullet("/notion — Save a thought, article, or link to Knowledge"),
    _bullet("/idea — Capture an idea"),
    _bullet("/knowledge — Search your knowledge base"),
]

# --- CRM home page (spec rev 6 §1) ---

THIS_WEEK = "This week"
SOURCES_TITLE = "📚 Sources & documentation"
MANUAL_VIEWS_TITLE = "Some views need a minute in Notion"

_ASSISTANT_PROMPT = (
    "Here is an email from Alice Martin at TechCorp.\n"
    "Update the CRM: log the activity and move the deal forward.\n"
    "\n"
    "<paste the email>"
)
_ASSISTANT_SETUP = (
    "claude mcp add --transport http notion https://mcp.notion.com/mcp\n"
    "/plugin marketplace add ldom1/notion-pilot\n"
    "/plugin install notion-crm@notion-pilot"
)
_KPI_BULLETS: tuple[tuple[str, str], ...] = (
    (
        "Days Since Last Activity",
        "Days since the latest activity linked to the lead. 999 means none yet; closed leads show 0.",
    ),
    (
        "Deal Temperature",
        "🔥 Hot within 7 days of an activity, 🌡 Warm within 21, ❄️ Cold after that or with none.",
    ),
    (
        "Stale Deal",
        "An open lead with no Next Step and no activity for 14 days. “Needs attention” lists these.",
    ),
    ("Weighted Value (€)", "Value × Probability."),
)

# The Telegram-era template, verbatim, so an upgrade can remove it. When the
# current template's copy changes, move the old strings here in the same change.
LEGACY_TEMPLATE_TEXTS = frozenset(
    {
        "Start with a Company → add People → track Deals.",
        "Getting started",
        "Add a company: /lead TechCorp",
        "Add contacts: /people Alice Martin, CTO @ TechCorp",
        "Track a deal: /deal ERP Integration — TechCorp, €45k",
        "💡 Tip: switch the Deals view to Board (group by Stage) for a Kanban pipeline."
        " In Notion: ··· → Add a view → Board.",
    }
)


def _sources_toggle() -> JsonDict:
    children: list[JsonDict] = [_paragraph(SOURCES_LEDE)]
    for group in DOC_GROUPS:
        children.append(_h3(group.title))
        children.extend(
            _bullet([_text(link.title, url=link.url, bold=True), _text(f" — {link.blurb}")])
            for link in group.links
        )
    return _toggle(SOURCES_TITLE, children)


def crm_home_blocks(leads_props: Collection[str] | None = None) -> list[JsonDict]:
    """The CRM home template, top to bottom, above the five databases.

    `leads_props` limits "How the numbers work" to properties Leads really has
    (an older CRM on upgrade). None means a fresh deploy, where all exist.
    """
    kpis = [
        _bullet([_text(name, bold=True), _text(f" — {meaning}")])
        for name, meaning in _KPI_BULLETS
        if leads_props is None or name in leads_props
    ]
    return [
        _callout(
            [
                _text("Your CRM is ready. Your pipeline is below.", bold=True),
                _text("\nFive related databases, filled with demo data so nothing starts empty."),
            ],
            "✅",
        ),
        _h2(THIS_WEEK),
        _h2("Update it without the fifteen clicks"),
        _paragraph("Paste this into Claude, then the email under it:"),
        _code(_ASSISTANT_PROMPT),
        _paragraph("You see every change first. Nothing is written until you reply go."),
        _toggle(
            "🔌 Connect your assistant (2 minutes)",
            [
                _paragraph(
                    "Claude desktop or claude.ai: add the Notion connector "
                    "(Settings → Connectors), authorise it, then restart the app."
                ),
                _paragraph("Claude Code:"),
                _code(_ASSISTANT_SETUP, "shell"),
                _paragraph(
                    "These run in your assistant, not in Notion. Notion MCP gives it access "
                    "to your workspace; the skills add the CRM workflow and the "
                    "preview-then-go check."
                ),
            ],
        ),
        _toggle(
            "📐 How the numbers work",
            kpis or [_paragraph("The pipeline formulas are not on this Leads database yet.")],
        ),
        _toggle(
            "🧪 About the demo data",
            [
                _paragraph(
                    "TechCorp, Optima Solutions, DataBridge, NovaSys Energy and ClearPath "
                    "Analytics are examples, with their people, leads, one meeting and one "
                    "activity. Delete them once your first real lead is in."
                )
            ],
        ),
        _sources_toggle(),
        _h2("Databases"),
    ]


def manual_views_callout(skipped: Sequence[ViewSpec]) -> JsonDict:
    children: list[JsonDict] = []
    for spec in skipped:
        children.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [_text(spec.name, bold=True)]},
            }
        )
        children.extend(_numbered(step) for step in spec.manual_steps)
    return _callout(MANUAL_VIEWS_TITLE, "⚠️", children)


async def _add_home_views(
    client: httpx.AsyncClient,
    page_id: str,
    home: list[JsonDict],
    *,
    leads_id: str | None,
    activities_id: str | None,
) -> ViewsOutcome:
    """Views under "This week"; manual steps after Sources for any view Notion refused."""
    outcome = await create_home_views(
        client,
        page_id=page_id,
        after_block_id=find_block(home, "heading_2", THIS_WEEK),
        databases={"Leads": leads_id, "Activities": activities_id},
    )
    if outcome.skipped:
        try:
            await _append_blocks(
                client,
                page_id,
                [manual_views_callout(outcome.skipped)],
                after=find_block(home, "toggle", SOURCES_TITLE),
            )
        except httpx.HTTPError as exc:
            outcome.warnings.append(f"The manual steps could not be added to the page ({exc}).")
    return outcome


def owned_template_texts() -> frozenset[str]:
    """Top-level block texts Notion Pilot wrote — the only ones an upgrade removes."""
    current = {_plain_text(block) for block in crm_home_blocks()}
    return frozenset(current | {MANUAL_VIEWS_TITLE}) | LEGACY_TEMPLATE_TEXTS


_KNOWLEDGE_CHILDREN: list[JsonDict] = [
    _callout(
        "Forward any message to the bot, or use /notion to save a link, /idea to capture a thought.",
        "📚",
    ),
    _h2("Getting started"),
    _numbered("Save an article: forward a URL to the bot"),
    _numbered("Capture an idea: /idea Build a weekly AI digest bot"),
    _numbered("Mark as read: update Status → Lu in the Notions database"),
    _numbered("Filter by interest: use the Interest filter (High / Medium / Low)"),
]


# --- demo data ---

_DEMO_COMPANIES: list[JsonDict] = [
    {
        "name": "TechCorp",
        "sector": "Software",
        "website": "https://techcorp.io",
        "linkedin": "https://linkedin.com/company/techcorp",
        "link": "https://crunchbase.com/organization/techcorp",
        "size": "51-200",
        "country": "FR",
        "crm_status": "Active",
        "tier": "1",
        "tech_stack": ["Python", "AWS", "PostgreSQL"],
        "tags": ["Key Account", "ERP"],
        "notes": "Key account — ERP opportunity Q3. Decision-maker is Alice Martin (CTO).",
    },
    {
        "name": "Optima Solutions",
        "sector": "Consulting",
        "website": "https://optima-solutions.fr",
        "linkedin": "https://linkedin.com/company/optima-solutions",
        "link": None,
        "size": "11-50",
        "country": "FR",
        "crm_status": "Prospect",
        "tier": "2",
        "tech_stack": ["SAP", "Excel", "Tableau"],
        "tags": ["Warm Lead", "Finance"],
        "notes": "Warm intro via Pierre Lambert. Finance transformation project.",
    },
    {
        "name": "DataBridge",
        "sector": "Software",
        "website": "https://databridge.eu",
        "linkedin": "https://linkedin.com/company/databridge",
        "link": "https://databridge.eu/about",
        "size": "51-200",
        "country": "GB",
        "crm_status": "Active",
        "tier": "1",
        "tech_stack": ["Python", "Spark", "dbt", "Snowflake"],
        "tags": ["Pilot", "Data"],
        "notes": "Digital Twin pilot project. Strong fit with our optimization stack.",
    },
    {
        "name": "NovaSys Energy",
        "sector": "Energy",
        "website": "https://novasys-energy.de",
        "linkedin": "https://linkedin.com/company/novasys-energy",
        "link": None,
        "size": "201-500",
        "country": "DE",
        "crm_status": "Partner",
        "tier": "1",
        "tech_stack": ["MATLAB", "Simulink", "C++"],
        "tags": ["Partner", "HPC"],
        "notes": "Strategic partner for grid optimization projects in DACH region.",
    },
    {
        "name": "ClearPath Analytics",
        "sector": "Software",
        "website": "https://clearpath.io",
        "linkedin": "https://linkedin.com/company/clearpath-analytics",
        "link": "https://clearpath.io/case-studies",
        "size": "11-50",
        "country": "US",
        "crm_status": "Prospect",
        "tier": "3",
        "tech_stack": ["Python", "BigQuery", "Looker"],
        "tags": ["Inbound", "Analytics"],
        "notes": "Inbound lead from the website. Analytics migration use case.",
    },
]

_DEMO_PEOPLE: list[JsonDict] = [
    {
        "name": "Alice Martin",
        "company": "TechCorp",
        "position": "CTO",
        "email_pro": "a.martin@techcorp.io",
        "email_private": "alice.martin@gmail.com",
        "linkedin": "https://linkedin.com/in/alice-martin",
        "phone": "+33 6 12 34 56 78",
        "in_network": "Yes",
        "seniority": "c_suite",
        "role_type": ["engineering", "product management"],
        "profile": "🔥 Key",
        "tags": ["TechCorp", "Decision Maker"],
        "notes": "Main technical decision-maker. Open to a demo in September.",
    },
    {
        "name": "Pierre Lambert",
        "company": "TechCorp",
        "position": "CEO",
        "email_pro": "p.lambert@techcorp.io",
        "email_private": None,
        "linkedin": "https://linkedin.com/in/pierre-lambert",
        "phone": "+33 6 98 76 54 32",
        "in_network": "Yes",
        "seniority": "founder",
        "role_type": ["strategy"],
        "profile": "🔥 Key",
        "tags": ["TechCorp", "Decision Maker"],
        "notes": "Co-founder. Introduced us to Optima Solutions.",
    },
    {
        "name": "Marc Dubois",
        "company": "Optima Solutions",
        "position": "CFO",
        "email_pro": "m.dubois@optima.fr",
        "email_private": None,
        "linkedin": "https://linkedin.com/in/marc-dubois-optima",
        "phone": "+33 1 42 68 10 00",
        "in_network": "Yes",
        "seniority": "c_suite",
        "role_type": ["strategy"],
        "profile": "Normal",
        "tags": ["Optima", "Finance"],
        "notes": "Budget holder for the transformation project. Risk-averse.",
    },
    {
        "name": "Sophie Chen",
        "company": "DataBridge",
        "position": "Head of Data",
        "email_pro": "s.chen@databridge.eu",
        "email_private": "sophie.chen@proton.me",
        "linkedin": "https://linkedin.com/in/sophie-chen",
        "phone": "+44 7911 123456",
        "in_network": "Yes",
        "seniority": "director",
        "role_type": ["engineering", "research"],
        "profile": "🔥 Key",
        "tags": ["DataBridge", "Data"],
        "notes": "Technical champion for the Digital Twin pilot. Very engaged.",
    },
    {
        "name": "Elena Vasquez",
        "company": "NovaSys Energy",
        "position": "VP Engineering",
        "email_pro": "e.vasquez@novasys-energy.de",
        "email_private": None,
        "linkedin": "https://linkedin.com/in/elena-vasquez",
        "phone": "+49 30 123 456 78",
        "in_network": "Yes",
        "seniority": "vp",
        "role_type": ["engineering", "project management"],
        "profile": "🔥 Key",
        "tags": ["NovaSys", "HPC", "Partner"],
        "notes": "Drives technical partnerships. Met at IEEE conference 2025.",
    },
    {
        "name": "Thomas Rémy",
        "company": "ClearPath Analytics",
        "position": "Founder & CEO",
        "email_pro": "thomas@clearpath.io",
        "email_private": "t.remy@gmail.com",
        "linkedin": "https://linkedin.com/in/thomas-remy",
        "phone": "+1 415 555 0199",
        "in_network": "Non",
        "seniority": "founder",
        "role_type": ["strategy", "product management"],
        "profile": "Normal",
        "tags": ["ClearPath", "Inbound"],
        "notes": "Reached out via website contact form. Evaluating 3 vendors.",
    },
    {
        "name": "Laura Smith",
        "company": "DataBridge",
        "position": "Lead Data Scientist",
        "email_pro": "l.smith@databridge.eu",
        "email_private": None,
        "linkedin": "https://linkedin.com/in/laura-smith-data",
        "phone": "+44 7700 900123",
        "in_network": "Yes",
        "seniority": "senior",
        "role_type": ["research", "engineering"],
        "profile": "Normal",
        "tags": ["DataBridge", "Data"],
        "notes": "End user for the pilot. Key influencer in the decision.",
    },
]

_DEMO_DEALS: list[JsonDict] = [
    {
        "name": "ERP Integration — TechCorp",
        "company": "TechCorp",
        "contacts": ["Alice Martin", "Pierre Lambert"],
        "stage": "Qualified",
        "value": 45000,
        "probability": 0.35,
        "product": ["Consulting", "Optimization"],
        "type": "Prospection chaude",
        "next_action": "Schedule technical workshop with Alice",
        "next_action_date": "2026-06-10",
        "contacted": True,
        "notes": "Validated budget €45k. Need to confirm scope with engineering team.",
    },
    {
        "name": "Digital Twin Pilot — DataBridge",
        "company": "DataBridge",
        "contacts": ["Sophie Chen", "Laura Smith"],
        "stage": "Proposal Sent",
        "value": 28000,
        "probability": 0.55,
        "product": ["Optimization"],
        "type": "Lead qualifié",
        "next_action": "Follow up on proposal — awaiting board approval",
        "next_action_date": "2026-06-05",
        "expected_close_in_days": 26,
        "contacted": True,
        "notes": "Proposal sent 2026-05-20. Strong technical fit. Competing with one other vendor.",
    },
    {
        "name": "HPC Grid Optimisation — NovaSys",
        "company": "NovaSys Energy",
        "contacts": ["Elena Vasquez"],
        "stage": "Negotiation",
        "value": 85000,
        "probability": 0.70,
        "product": ["HPC-as-a-service", "Optimization"],
        "type": "Lead qualifié",
        "next_action": "Final contract review — legal sign-off pending",
        "next_action_date": "2026-05-28",
        "expected_close_in_days": 12,
        "contacted": True,
        "notes": "Partnership deal. Recurring revenue potential after year 1.",
    },
    {
        "name": "Analytics Platform — ClearPath",
        "company": "ClearPath Analytics",
        "contacts": ["Thomas Rémy"],
        "stage": "Prospect",
        "value": 15000,
        "probability": 0.20,
        "product": ["Consulting"],
        "type": "Prospection tiède",
        "next_action": None,
        "next_action_date": None,
        "contacted": False,
        "notes": "Inbound. Early stage — needs nurturing. Decision expected Q3.",
    },
    {
        "name": "Finance Transformation — Optima",
        "company": "Optima Solutions",
        "contacts": ["Marc Dubois"],
        "stage": "Closed Lost",
        "value": 32000,
        "probability": 0.0,
        "product": ["Consulting", "Training"],
        "type": "Prospection froide",
        "next_action": "Re-engage in 6 months",
        "next_action_date": "2026-12-01",
        "contacted": True,
        "notes": "Lost to competitor on price. Keep warm for future projects.",
    },
]

_DEMO_NOTIONS: list[JsonDict] = [
    {
        "name": "The future of AI agents in enterprise software",
        "url": "https://a16z.com/ai-agents-enterprise",
        "description": "Deep dive on agentic workflows replacing SaaS point solutions",
        "source": "Web",
        "interest": "High",
        "status": "À relire",
        "tags": ["AI", "Enterprise", "Agents"],
    },
    {
        "name": "GraphQL vs REST in 2025 — when each shines",
        "url": "https://blog.graphql.org/graphql-vs-rest-2025",
        "description": "Practical guide on API design trade-offs",
        "source": "Telegram",
        "interest": "Medium",
        "status": "Lu",
        "tags": ["Dev", "APIs"],
    },
    {
        "name": "Notion API best practices for power users",
        "url": "https://developers.notion.com/docs/best-practices",
        "description": "Official Notion guide on rate limits, pagination and property types",
        "source": "Telegram",
        "interest": "High",
        "status": "À relire",
        "tags": ["Notion", "Dev"],
    },
    {
        "name": "LLM fine-tuning vs RAG — choosing the right approach",
        "url": "https://huggingface.co/blog/rag-vs-finetuning",
        "description": "When to use retrieval augmentation vs. full model fine-tuning",
        "source": "Email",
        "interest": "High",
        "status": "À relire",
        "tags": ["AI", "LLM", "RAG"],
    },
    {
        "name": "Telegram Bot API — what's new in 2025",
        "url": "https://core.telegram.org/bots/api",
        "description": "Release notes covering new message types and bot permissions",
        "source": "Web",
        "interest": "Medium",
        "status": "Lu",
        "tags": ["Telegram", "Dev", "Bots"],
    },
]

_DEMO_IDEAS: list[JsonDict] = [
    {
        "name": "Weekly AI digest bot — auto-curate from Telegram & email",
        "description": "Monitor key channels and compile a weekly digest with LLM summaries",
        "priority": "High",
        "status": "Active",
        "tags": ["AI", "Automation", "Digest"],
    },
    {
        "name": "Auto-enrich contacts from LinkedIn Sales Navigator export",
        "description": "Parse Sales Nav CSV and upsert enriched People records into the CRM",
        "priority": "Medium",
        "status": "Draft",
        "tags": ["CRM", "Enrichment", "LinkedIn"],
    },
    {
        "name": "Notion CRM deal scoring based on activity signals",
        "description": "Score deals by last contact date, stage age, and email open rates",
        "priority": "Medium",
        "status": "Draft",
        "tags": ["CRM", "AI", "Scoring"],
    },
    {
        "name": "Discord integration for knowledge capture",
        "description": "Forward pinned Discord messages to the Notions database automatically",
        "priority": "Low",
        "status": "Draft",
        "tags": ["Discord", "Automation", "Inbox"],
    },
]

_DEMO_TOOLS: list[JsonDict] = [
    {
        "name": "Apollo.io",
        "url": "https://apollo.io",
        "description": "B2B contact database with email + phone enrichment and sequences",
        "pricing": "Freemium",
        "status": "Using",
        "tags": ["Enrichment", "CRM", "Prospecting"],
    },
    {
        "name": "Brave Search API",
        "url": "https://api.search.brave.com",
        "description": "Privacy-first search API for company and person lookups",
        "pricing": "Free",
        "status": "Using",
        "tags": ["Search", "Enrichment"],
    },
    {
        "name": "OpenRouter",
        "url": "https://openrouter.ai",
        "description": "Unified API gateway for 100+ LLMs — used for message enrichment",
        "pricing": "Freemium",
        "status": "Using",
        "tags": ["LLM", "AI", "API"],
    },
    {
        "name": "Notion API",
        "url": "https://developers.notion.com",
        "description": "Official Notion REST API for database CRUD and page creation",
        "pricing": "Free",
        "status": "Using",
        "tags": ["Notion", "Dev"],
    },
    {
        "name": "Perplexity API",
        "url": "https://www.perplexity.ai/api",
        "description": "Real-time web search with LLM synthesis — used as enrichment fallback",
        "pricing": "Paid",
        "status": "Testing",
        "tags": ["Search", "LLM", "Enrichment"],
    },
]

_DEMO_DATA_TECH: list[JsonDict] = [
    {
        "name": "LLM-based entity extraction from unstructured text",
        "url": "https://arxiv.org/abs/2305.07975",
        "description": "Survey on NER and relation extraction using instruction-tuned LLMs",
        "domain": "AI",
        "status": "À relire",
        "tags": ["NLP", "LLM", "Extraction"],
    },
    {
        "name": "Vector databases compared: Pinecone vs Weaviate vs Qdrant",
        "url": "https://qdrant.tech/blog/vector-db-benchmark",
        "description": "Benchmark on recall, latency, and cost for RAG workloads",
        "domain": "Data",
        "status": "À relire",
        "tags": ["Vector DB", "RAG", "Benchmark"],
    },
    {
        "name": "Telegram MTProto protocol deep dive",
        "url": "https://core.telegram.org/mtproto",
        "description": "Technical spec of Telegram's encryption and transport layer",
        "domain": "Dev",
        "status": "Lu",
        "tags": ["Telegram", "Protocol", "Security"],
    },
]


# --- low-level helpers ---


async def create_workspace_root_page(
    client: httpx.AsyncClient, name: str, parent_page_id: str | None = None
) -> str:
    """Create the deploy root page. Returns the page ID.

    Without ``parent_page_id`` the page is created at the top level of the
    workspace, which **only works for a public-integration OAuth token**. An
    internal integration is rejected:

        "Internal integrations aren't owned by a single user, so creating
         workspace-level private pages is not supported."

    Passing a parent page makes the deploy work for either kind of token, and is
    the only way to confine a deploy — see the wizard parent-page design.
    """
    parent: dict[str, Any] = (
        {"type": "page_id", "page_id": parent_page_id} if parent_page_id else {"workspace": True}
    )
    logger.info(
        "workspace: creating root page '{}' ({})",
        name,
        f"under {parent_page_id}" if parent_page_id else "workspace top level",
    )
    r = await client.post(
        f"{NOTION_API}/pages",
        json={
            "parent": parent,
            "icon": {"type": "emoji", "emoji": "🚀"},
            "properties": {"title": {"title": [{"type": "text", "text": {"content": name}}]}},
            "children": _ROOT_CHILDREN,
        },
    )
    r.raise_for_status()
    page_id = str(r.json()["id"])
    logger.info("workspace: root page created ({})", page_id)
    return page_id


@dataclass
class CRMWorkspaceResult:
    crm_page_id: str
    companies_id: str
    people_id: str
    deals_id: str  # the Leads database (historical name)
    meetings_id: str
    activities_id: str
    views: dict[str, dict[str, str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class InboxWorkspaceResult:
    inbox_page_id: str
    notions_id: str
    ideas_id: str
    tools_id: str
    data_tech_id: str


async def _create_page(
    client: httpx.AsyncClient,
    parent_page_id: str,
    title: str,
    emoji: str,
    children: list[JsonDict] | None = None,
) -> str:
    body: dict[str, Any] = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": emoji},
        "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
    }
    if children:
        body["children"] = children
    r = await client.post(f"{NOTION_API}/pages", json=body)
    r.raise_for_status()
    return str(r.json()["id"])


async def _append_blocks(
    client: httpx.AsyncClient,
    parent_id: str,
    blocks: list[JsonDict],
    *,
    after: str | None = None,
) -> list[JsonDict]:
    """Append blocks (after `after` when given) and return the new blocks with ids."""
    body: JsonDict = {"children": blocks}
    if after:
        body["after"] = after
    r = await client.patch(f"{NOTION_API}/blocks/{parent_id}/children", json=body)
    r.raise_for_status()
    return list(r.json()["results"])


async def _list_children(client: httpx.AsyncClient, block_id: str) -> list[JsonDict]:
    blocks: list[JsonDict] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        r = await client.get(f"{NOTION_API}/blocks/{block_id}/children", params=params)
        r.raise_for_status()
        body = r.json()
        blocks.extend(body["results"])
        if not body.get("has_more"):
            return blocks
        cursor = body["next_cursor"]


async def _create_db(
    client: httpx.AsyncClient,
    parent_page_id: str,
    title: str,
    properties: dict[str, Any],
    emoji: str,
) -> str:
    logger.info("workspace: creating database '{}'", title)
    r = await client.post(
        f"{NOTION_API}/databases",
        json={
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "icon": {"type": "emoji", "emoji": emoji},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        },
    )
    r.raise_for_status()
    body = r.json()
    db_id = str(body["id"])
    # Verify that the API actually applied the requested properties.
    # Some API versions accept the payload but silently drop properties.
    if "properties" in body:
        created = set(body["properties"].keys())
        expected = set(properties.keys())
        missing = expected - created
        if missing:
            raise RuntimeError(
                f"Database '{title}' was created but properties were not applied: {sorted(missing)}. "
                "Check the Notion-Version header — the API may require a different version."
            )
    else:
        logger.warning(
            "workspace: database '{}' response has no 'properties' key — "
            "cannot verify schema (API may use data_sources model)",
            title,
        )
    logger.info("workspace: database '{}' ready ({})", title, db_id)
    return db_id


async def _patch_db(
    client: httpx.AsyncClient, db_id: str, properties: dict[str, Any], *, what: str
) -> None:
    """Add properties to an existing database."""
    r = await client.patch(f"{NOTION_API}/databases/{db_id}", json={"properties": properties})
    if r.status_code != 200:
        raise RuntimeError(f"Failed to add {what} to database {db_id}: {r.status_code} {r.text}")
    logger.info("workspace: {} applied to {}", what, db_id)


def find_relation_properties(properties: dict[str, Any], target_db_id: str) -> list[str]:
    """Names of the relation properties in `properties` that point at `target_db_id`.

    Ids are compared with dashes stripped: Notion returns them dashed from
    /databases but callers often hold the undashed form from a page URL.
    """
    target = target_db_id.replace("-", "")
    return [
        name
        for name, prop in properties.items()
        if prop.get("type") == "relation"
        and str(prop.get("relation", {}).get("database_id", "")).replace("-", "") == target
    ]


async def _resolve_back_relation(
    client: httpx.AsyncClient, parent_db_id: str, target_db_id: str, desired: str
) -> str:
    """Return the name of the property on `parent_db_id` that points at `target_db_id`.

    A dual-property relation makes Notion create the reverse property itself, and
    it names it — `synced_property_name` is read-only on create, so the name
    cannot be requested up front. The repo's own history shows what happens if
    you assume it: `crm_add_activity_rollups.py` hardcodes "Activities" with a
    "verified by probe" comment, and tolerates a 400 because the guess can be
    wrong. So: read the reverse name back, rename it to `desired` for
    readability, and return whatever name is actually live. The rollup then keys
    on a known-good property instead of a hopeful string.
    """
    r = await client.get(f"{NOTION_API}/databases/{parent_db_id}")
    r.raise_for_status()
    found = find_relation_properties(r.json().get("properties", {}), target_db_id)
    if not found:
        raise RuntimeError(
            f"No relation from database {parent_db_id} to {target_db_id} was created. "
            "The rollups that depend on it cannot be built."
        )
    current = desired if desired in found else found[0]
    if current != desired:
        rename = await client.patch(
            f"{NOTION_API}/databases/{parent_db_id}",
            json={"properties": {current: {"name": desired}}},
        )
        if rename.status_code == 200:
            logger.info("workspace: renamed '{}' -> '{}' on {}", current, desired, parent_db_id)
            return desired
        logger.warning(
            "workspace: could not rename '{}' to '{}' on {} ({}); keying on the live name",
            current,
            desired,
            parent_db_id,
            rename.status_code,
        )
    return current


async def _create_db_page(client: httpx.AsyncClient, db_id: str, properties: dict[str, Any]) -> str:
    r = await client.post(
        f"{NOTION_API}/pages",
        json={"parent": {"type": "database_id", "database_id": db_id}, "properties": properties},
    )
    r.raise_for_status()
    return str(r.json()["id"])


# --- demo data seeding ---


async def _seed_companies(client: httpx.AsyncClient, companies_id: str) -> dict[str, str]:
    logger.info("workspace: seeding {} companies", len(_DEMO_COMPANIES))
    ids: dict[str, str] = {}
    for c in _DEMO_COMPANIES:
        props: dict[str, Any] = {
            "Name": {"title": _rt(c["name"])},
            "Sector": {"select": {"name": c["sector"]}},
            "Website": {"url": c["website"]},
            "Linkedin": {"url": c["linkedin"]},
            "Size": {"select": {"name": c["size"]}},
            "Country": {"select": {"name": c["country"]}},
            "CRM Status": {"select": {"name": c["crm_status"]}},
            "Tier": {"select": {"name": c["tier"]}},
            "Tech Stack": {"multi_select": [{"name": t} for t in c["tech_stack"]]},
            "Tags": {"multi_select": [{"name": t} for t in c["tags"]]},
            "Notes": {"rich_text": _rt(c["notes"])},
        }
        if c.get("link"):
            props["Link"] = {"url": c["link"]}
        ids[c["name"]] = await _create_db_page(client, companies_id, props)
    return ids


async def _seed_people(
    client: httpx.AsyncClient,
    people_id: str,
    company_ids: dict[str, str],
) -> dict[str, str]:
    logger.info("workspace: seeding {} people", len(_DEMO_PEOPLE))
    ids: dict[str, str] = {}
    for p in _DEMO_PEOPLE:
        props: dict[str, Any] = {
            "Name": {"title": _rt(p["name"])},
            "Company": {"relation": [{"id": company_ids[p["company"]]}]},
            "Position": {"rich_text": _rt(p["position"])},
            "Linkedin": {"url": p["linkedin"]},
            "Email - pro": {"email": p["email_pro"]},
            "Phone": {"phone_number": p["phone"]},
            "Relationship": {"select": {"name": "Close" if p["in_network"] == "Yes" else "Cold"}},
            "Seniority": {"select": {"name": p["seniority"]}},
            "Role Type": {"multi_select": [{"name": r} for r in p["role_type"]]},
            "Priority": {"select": {"name": p["profile"]}},
            "Tags": {"multi_select": [{"name": t} for t in p["tags"]]},
            "Notes": {"rich_text": _rt(p["notes"])},
        }
        if p.get("email_private"):
            props["Email - private"] = {"email": p["email_private"]}
        ids[p["name"]] = await _create_db_page(client, people_id, props)
    return ids


async def _seed_deals(
    client: httpx.AsyncClient,
    deals_id: str,
    company_ids: dict[str, str],
    people_ids: dict[str, str],
) -> dict[str, str]:
    logger.info("workspace: seeding {} deals", len(_DEMO_DEALS))
    deal_ids: dict[str, str] = {}
    for d in _DEMO_DEALS:
        contacts = [{"id": people_ids[n]} for n in d["contacts"] if n in people_ids]
        props: dict[str, Any] = {
            "Name": {"title": _rt(d["name"])},
            "Client": {"relation": [{"id": company_ids[d["company"]]}]},
            "Stage": {"select": {"name": d["stage"]}},
            "Value (euros)": {"number": d["value"]},
            "Probability (%)": {"number": d["probability"]},
            "Product": {"multi_select": [{"name": p} for p in d["product"]]},
            "Lead Source": {"select": {"name": d["type"]}},
            "Notes": {"rich_text": _rt(d["notes"])},
        }
        # ClearPath has no next step on purpose: it is the demo "Needs attention" lead.
        if d["next_action"]:
            props["Next Step"] = {"rich_text": _rt(d["next_action"])}
            props["Next Step Date"] = {"date": {"start": d["next_action_date"]}}
        if d.get("expected_close_in_days") is not None:
            close = date.today() + timedelta(days=d["expected_close_in_days"])
            props["Expected Close Date"] = {"date": {"start": close.isoformat()}}
        if contacts:
            props["Contacts"] = {"relation": contacts}
        deal_ids[d["name"]] = await _create_db_page(client, deals_id, props)
    return deal_ids


async def _create_meetings_db(
    client: httpx.AsyncClient,
    crm_page_id: str,
    companies_id: str,
    people_id: str,
    deals_id: str,
) -> str:
    """Meetings — created and related, but never written by an agent (spec §3.2).

    Property names follow the live database via scripts/crm/crm_patch_meetings.py.
    `Advanced Deal?` and `Activity Created?` exist so a later operator-run sync
    has somewhere to write; nothing in v1 reads them.
    """
    return await _create_db(
        client,
        crm_page_id,
        "Meetings",
        {
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Type": {
                "select": {
                    "options": [
                        {"name": "Discovery", "color": "blue"},
                        {"name": "Demo", "color": "orange"},
                        {"name": "Follow-up", "color": "yellow"},
                        {"name": "Proposal Review", "color": "purple"},
                        {"name": "Negotiation", "color": "red"},
                        {"name": "Kick-off", "color": "green"},
                        {"name": "Internal", "color": "gray"},
                        {"name": "Conference", "color": "pink"},
                        {"name": "Interview", "color": "brown"},
                    ]
                }
            },
            "Meeting Objective": {"rich_text": {}},
            "Company": {"relation": {"database_id": companies_id, "dual_property": {}}},
            "Deal": {"relation": {"database_id": deals_id, "dual_property": {}}},
            "People": {"relation": {"database_id": people_id, "dual_property": {}}},
            "Tags": {
                "multi_select": {
                    "options": [
                        {"name": "meeting", "color": "default"},
                        {"name": "conference", "color": "blue"},
                        {"name": "internal", "color": "gray"},
                    ]
                }
            },
            "Advanced Deal?": {"checkbox": {}},
            "Activity Created?": {"checkbox": {}},
            "Notes": {"rich_text": {}},
        },
        "🤝",
    )


async def _create_activities_db(
    client: httpx.AsyncClient,
    crm_page_id: str,
    companies_id: str,
    people_id: str,
    deals_id: str,
    meetings_id: str,
) -> str:
    """Activities — the database log_activity hard-requires (spec §3.1).

    Property names and select options come from ActivityRecord._to_properties
    (notion_pilot/crm/activities.py) and scripts/crm/crm_create_activities_db.py.
    The relation to People is `Person`, not `Contact` — that is the writer's
    contract. Relations are dual so the reverse side exists for the rollups.
    """
    return await _create_db(
        client,
        crm_page_id,
        "Activities",
        {
            "Name": {"title": {}},
            "Type": {
                "select": {
                    "options": [
                        {"name": "📞 Call", "color": "blue"},
                        {"name": "📧 Email", "color": "green"},
                        {"name": "💼 LinkedIn", "color": "purple"},
                        {"name": "🎤 Demo", "color": "orange"},
                        {"name": "🤝 Meeting", "color": "yellow"},
                        {"name": "📄 Proposal", "color": "red"},
                        {"name": "🎪 Conference", "color": "pink"},
                        {"name": "📋 Other", "color": "gray"},
                    ]
                }
            },
            "Date": {"date": {}},
            "Duration (min)": {"number": {"format": "number"}},
            "Outcome": {
                "select": {
                    "options": [
                        {"name": "✅ Positive", "color": "green"},
                        {"name": "➡️ Follow-up Needed", "color": "yellow"},
                        {"name": "❌ Negative", "color": "red"},
                        {"name": "🔇 No Response", "color": "gray"},
                    ]
                }
            },
            "Deal": {"relation": {"database_id": deals_id, "dual_property": {}}},
            "Person": {"relation": {"database_id": people_id, "dual_property": {}}},
            "Company": {"relation": {"database_id": companies_id, "dual_property": {}}},
            "Meeting": {"relation": {"database_id": meetings_id, "dual_property": {}}},
            "Next Step": {"rich_text": {}},
            "Next Step Date": {"date": {}},
            "Notes": {"rich_text": {}},
            "Owner": {"people": {}},
        },
        "⚡",
    )


# Formula text is copied verbatim from scripts/crm/crm_add_activity_rollups.py —
# those expressions are the ones proven against the live workspace. Notion
# formula 1.0 (what the API speaks) cannot reference other formula properties and
# only takes 2-argument and()/or(), hence the inlining and the nesting.
_TERMINAL = (
    'or(or(prop("Stage") == "Closed Won", prop("Stage") == "Closed Lost"), '
    'prop("Stage") == "No Answer")'
)
_DAYS = 'dateBetween(now(), prop("Last Activity Date"), "days")'
_DAYS_SINCE_SIMPLE = (
    'if(empty(prop("Last Activity Date")), 999, '
    'dateBetween(now(), prop("Last Activity Date"), "days"))'
)


async def _add_activity_rollups(
    client: httpx.AsyncClient,
    *,
    deals_id: str,
    people_id: str,
    companies_id: str,
    activities_id: str,
) -> None:
    """Last Activity Date rollups + the pipeline formulas that read them.

    This is what makes one logged call show up on the deal, the contact and the
    company. Each rollup keys on the *resolved* back-relation name, so unlike the
    one-shot script this cannot 400 on a guessed property name — which is why a
    failure here is raised rather than warned about.
    """
    for db_id, label in ((deals_id, "Leads"), (people_id, "People"), (companies_id, "Companies")):
        relation = await _resolve_back_relation(client, db_id, activities_id, "Activities")
        await _patch_db(
            client,
            db_id,
            {
                "Last Activity Date": {
                    "rollup": {
                        "relation_property_name": relation,
                        "rollup_property_name": "Date",
                        "function": "latest_date",
                    }
                }
            },
            what=f"{label} Last Activity Date rollup",
        )

    await _patch_db(
        client,
        deals_id,
        {
            "Days Since Last Activity": {
                "formula": {
                    "expression": (
                        f"if({_TERMINAL}, 0, "
                        'if(empty(prop("Last Activity Date")), 999, '
                        'dateBetween(now(), prop("Last Activity Date"), "days")))'
                    )
                }
            },
            "Deal Age (days)": {
                "formula": {"expression": 'dateBetween(now(), prop("Created time"), "days")'}
            },
            "Next Step Scheduled": {
                "formula": {"expression": 'not(empty(prop("Next Step Date")))'}
            },
            "Weighted Value (€)": {
                "formula": {
                    "expression": 'round(prop("Value (euros)") * prop("Probability (%)") / 100)'
                }
            },
        },
        what="Leads base formulas",
    )

    await _patch_db(
        client,
        deals_id,
        {
            "Deal Temperature": {
                "formula": {
                    "expression": (
                        f'if({_TERMINAL}, "—", '
                        f'if(empty(prop("Last Activity Date")), "❄️ Cold", '
                        f'if({_DAYS} <= 7, "🔥 Hot", '
                        f'if({_DAYS} <= 21, "🌡 Warm", '
                        '"❄️ Cold"))))'
                    )
                }
            },
            "Stale Deal": {
                "formula": {
                    "expression": (
                        f"and(not({_TERMINAL}), "
                        f'and(empty(prop("Next Step")), '
                        f'if(empty(prop("Last Activity Date")), true, {_DAYS} > 14)))'
                    )
                }
            },
        },
        what="Leads temperature and stale formulas",
    )

    for db_id, label in ((people_id, "People"), (companies_id, "Companies")):
        await _patch_db(
            client,
            db_id,
            {"Days Since Last Activity": {"formula": {"expression": _DAYS_SINCE_SIMPLE}}},
            what=f"{label} Days Since Last Activity formula",
        )


async def _seed_meeting_and_activity(
    client: httpx.AsyncClient,
    *,
    meetings_id: str,
    activities_id: str,
    company_id: str,
    person_id: str,
    deal_id: str,
) -> None:
    """One meeting and one activity, so neither database opens as an empty shell."""
    today = date.today().isoformat()
    meeting_id = await _create_db_page(
        client,
        meetings_id,
        {
            "Name": {"title": _rt("Discovery call — Néorégie Grid")},
            "Date": {"date": {"start": today}},
            "Type": {"select": {"name": "Discovery"}},
            "Meeting Objective": {"rich_text": _rt("Qualify the need and agree a next step.")},
            "Company": {"relation": [{"id": company_id}]},
            "People": {"relation": [{"id": person_id}]},
            "Deal": {"relation": [{"id": deal_id}]},
            "Tags": {"multi_select": [{"name": "meeting"}]},
        },
    )
    await _create_db_page(
        client,
        activities_id,
        {
            "Name": {"title": _rt("Discovery call")},
            "Type": {"select": {"name": "📞 Call"}},
            "Date": {"date": {"start": today}},
            "Duration (min)": {"number": 30},
            "Outcome": {"select": {"name": "➡️ Follow-up Needed"}},
            "Deal": {"relation": [{"id": deal_id}]},
            "Person": {"relation": [{"id": person_id}]},
            "Company": {"relation": [{"id": company_id}]},
            "Meeting": {"relation": [{"id": meeting_id}]},
            "Next Step": {"rich_text": _rt("Send a short recap and propose a demo.")},
            "Next Step Date": {"date": {"start": today}},
        },
    )


async def _seed_notions(client: httpx.AsyncClient, notions_id: str) -> None:
    logger.info("workspace: seeding {} notions", len(_DEMO_NOTIONS))
    for n in _DEMO_NOTIONS:
        props: dict[str, Any] = {
            "Name": {"title": _rt(n["name"])},
            "Source": {"select": {"name": n["source"]}},
            "Interest": {"select": {"name": n["interest"]}},
            "Status": {"select": {"name": n["status"]}},
            "Tags": {"multi_select": [{"name": t} for t in n["tags"]]},
            "Description": {"rich_text": _rt(n["description"])},
        }
        if n.get("url"):
            props["URL"] = {"url": n["url"]}
        await _create_db_page(client, notions_id, props)


async def _seed_ideas(client: httpx.AsyncClient, ideas_id: str) -> None:
    logger.info("workspace: seeding {} ideas", len(_DEMO_IDEAS))
    for i in _DEMO_IDEAS:
        await _create_db_page(
            client,
            ideas_id,
            {
                "Name": {"title": _rt(i["name"])},
                "Description": {"rich_text": _rt(i["description"])},
                "Priority": {"select": {"name": i["priority"]}},
                "Status": {"select": {"name": i["status"]}},
                "Tags": {"multi_select": [{"name": t} for t in i["tags"]]},
            },
        )


async def _seed_tools(client: httpx.AsyncClient, tools_id: str) -> None:
    logger.info("workspace: seeding {} tools", len(_DEMO_TOOLS))
    for t in _DEMO_TOOLS:
        props: dict[str, Any] = {
            "Name": {"title": _rt(t["name"])},
            "Description": {"rich_text": _rt(t["description"])},
            "Pricing": {"select": {"name": t["pricing"]}},
            "Status": {"select": {"name": t["status"]}},
            "Tags": {"multi_select": [{"name": tag} for tag in t["tags"]]},
        }
        if t.get("url"):
            props["URL"] = {"url": t["url"]}
        await _create_db_page(client, tools_id, props)


async def _seed_data_tech(client: httpx.AsyncClient, data_tech_id: str) -> None:
    logger.info("workspace: seeding {} data & technology entries", len(_DEMO_DATA_TECH))
    for d in _DEMO_DATA_TECH:
        props: dict[str, Any] = {
            "Name": {"title": _rt(d["name"])},
            "Description": {"rich_text": _rt(d["description"])},
            "Domain": {"select": {"name": d["domain"]}},
            "Status": {"select": {"name": d["status"]}},
            "Tags": {"multi_select": [{"name": t} for t in d["tags"]]},
        }
        if d.get("url"):
            props["URL"] = {"url": d["url"]}
        await _create_db_page(client, data_tech_id, props)


# --- workspace builders ---


async def create_crm_workspace(
    client: httpx.AsyncClient,
    parent_page_id: str,
    page_title: str = "CRM",
) -> CRMWorkspaceResult:
    """Create CRM container page + Companies, People, Deals databases with demo data."""
    logger.info("workspace: creating CRM '{}'", page_title)
    crm_page_id = await _create_page(client, parent_page_id, page_title, "🏢")
    home = await _append_blocks(client, crm_page_id, crm_home_blocks())

    companies_id = await _create_db(
        client,
        crm_page_id,
        "Companies",
        {
            "Name": {"title": {}},
            "Website": {"url": {}},
            "Linkedin": {"url": {}},
            "Link": {"url": {}},
            "Sector": {
                "select": {
                    "options": [
                        {"name": "Energy", "color": "yellow"},
                        {"name": "Finance", "color": "green"},
                        {"name": "Industry", "color": "blue"},
                        {"name": "Public Sector", "color": "purple"},
                        {"name": "Telecom", "color": "orange"},
                        {"name": "Software", "color": "pink"},
                        {"name": "Consulting", "color": "brown"},
                        {"name": "Research", "color": "default"},
                        {"name": "Other", "color": "gray"},
                    ]
                }
            },
            "Size": {
                "select": {
                    "options": [
                        {"name": s, "color": "default"}
                        for s in [
                            "1-10",
                            "11-50",
                            "51-200",
                            "201-500",
                            "501-2000",
                            "2001-10000",
                            "10000+",
                        ]
                    ]
                }
            },
            "Country": {"select": {"options": []}},
            "CRM Status": {
                "select": {
                    "options": [
                        {"name": "Prospect", "color": "gray"},
                        {"name": "Active", "color": "green"},
                        {"name": "Partner", "color": "blue"},
                        {"name": "Churned", "color": "red"},
                    ]
                }
            },
            "Tier": {
                "select": {
                    "options": [
                        {"name": "1", "color": "red"},
                        {"name": "2", "color": "yellow"},
                        {"name": "3", "color": "gray"},
                    ]
                }
            },
            "Tech Stack": {"multi_select": {"options": []}},
            # No "Activities" property here: it is created as the reverse side of
            # Activities.Company (dual relation) and the rollups key on it. A
            # multi_select of the same name would collide.
            "Tags": {"multi_select": {"options": []}},
            # French-market core (spec §3.4) — present before first enrichment so
            # they are visible columns, not a surprise. company-open-data-enrichment
            # writes these; upsert_companies writes SIREN on create.
            "SIREN": {"rich_text": {}},
            "CA": {"number": {"format": "euro"}},
            "Résultat net": {"number": {"format": "euro"}},
            "Marge nette %": {"number": {"format": "percent"}},
            "Année financière": {"number": {"format": "number"}},
            "Notes": {"rich_text": {}},
        },
        "🏭",
    )

    people_id = await _create_db(
        client,
        crm_page_id,
        "People",
        {
            "Name": {"title": {}},
            "Company": {"relation": {"database_id": companies_id, "single_property": {}}},
            "Position": {"rich_text": {}},
            "Linkedin": {"url": {}},
            "Email - pro": {"email": {}},
            "Email - private": {"email": {}},
            "Phone": {"phone_number": {}},
            "Relationship": {
                "select": {
                    "options": [
                        {"name": "Close", "color": "green"},
                        {"name": "Warm", "color": "yellow"},
                        {"name": "Cold", "color": "blue"},
                        {"name": "None", "color": "gray"},
                    ]
                }
            },
            "Seniority": {
                "select": {
                    "options": [
                        {"name": s, "color": "default"}
                        for s in [
                            "founder",
                            "c_suite",
                            "vp",
                            "director",
                            "manager",
                            "senior",
                            "mid",
                            "junior",
                            "unknown",
                        ]
                    ]
                }
            },
            "Role Type": {"multi_select": {"options": []}},
            "Priority": {
                "select": {
                    "options": [
                        {"name": "Normal", "color": "default"},
                        {"name": "🔥 Key", "color": "red"},
                    ]
                }
            },
            "Tags": {"multi_select": {"options": []}},
            "Notes": {"rich_text": {}},
        },
        "👥",
    )

    deals_id = await _create_db(
        client,
        crm_page_id,
        "Leads",
        {
            "Name": {"title": {}},
            "Client": {"relation": {"database_id": companies_id, "single_property": {}}},
            "Contacts": {"relation": {"database_id": people_id, "single_property": {}}},
            "Stage": {
                "select": {
                    "options": [
                        {"name": "Prospect", "color": "gray"},
                        {"name": "Qualified", "color": "blue"},
                        {"name": "Discovery / First Meeting", "color": "purple"},
                        {"name": "Proposal Sent", "color": "yellow"},
                        {"name": "Negotiation", "color": "orange"},
                        {"name": "Waiting for a Response", "color": "brown"},
                        {"name": "Closed Won", "color": "green"},
                        {"name": "Closed Lost", "color": "red"},
                        {"name": "No Answer", "color": "default"},
                    ]
                }
            },
            "Value (euros)": {"number": {"format": "euro"}},
            "Probability (%)": {"number": {"format": "percent"}},
            "Next Step": {"rich_text": {}},
            "Next Step Date": {"date": {}},
            "Product": {
                "multi_select": {
                    "options": [
                        {"name": "Consulting"},
                        {"name": "Software"},
                        {"name": "Training"},
                        {"name": "Other"},
                    ]
                }
            },
            "Lead Source": {
                "select": {
                    "options": [
                        {"name": "Cold Outreach", "color": "gray"},
                        {"name": "Referral", "color": "green"},
                        {"name": "Inbound", "color": "blue"},
                        {"name": "Conference / Event", "color": "purple"},
                        {"name": "Partner", "color": "orange"},
                        {"name": "Existing Relationship", "color": "brown"},
                        {"name": "LinkedIn", "color": "pink"},
                    ]
                }
            },
            "Notes": {"rich_text": {}},
            "Expected Close Date": {"date": {}},
            "Primary contact": {"relation": {"database_id": people_id, "single_property": {}}},
            # Deal Age (days) reads prop("Created time"); the built-in is only
            # addressable from a formula once it exists as a property.
            "Created time": {"created_time": {}},
            "Owner": {"people": {}},
        },
        "💼",
    )

    # Meetings before Activities: Activities holds the relation into Meetings,
    # and its dual creates the reverse side, so Meetings must already exist.
    meetings_id = await _create_meetings_db(client, crm_page_id, companies_id, people_id, deals_id)
    activities_id = await _create_activities_db(
        client, crm_page_id, companies_id, people_id, deals_id, meetings_id
    )

    # Name the reverse side of the Meetings relations before the rollup pass, so
    # a deployed workspace reads "Meetings" rather than "Related to Meetings…".
    for parent in (deals_id, people_id, companies_id):
        await _resolve_back_relation(client, parent, meetings_id, "Meetings")

    await _add_activity_rollups(
        client,
        deals_id=deals_id,
        people_id=people_id,
        companies_id=companies_id,
        activities_id=activities_id,
    )

    company_ids = await _seed_companies(client, companies_id)
    people_ids = await _seed_people(client, people_id, company_ids)
    deal_ids = await _seed_deals(client, deals_id, company_ids, people_ids)
    if company_ids and people_ids and deal_ids:
        await _seed_meeting_and_activity(
            client,
            meetings_id=meetings_id,
            activities_id=activities_id,
            company_id=next(iter(company_ids.values())),
            person_id=next(iter(people_ids.values())),
            deal_id=next(iter(deal_ids.values())),
        )
    views = await _add_home_views(
        client, crm_page_id, home, leads_id=deals_id, activities_id=activities_id
    )
    logger.info("workspace: CRM ready — page_id={} views={}", crm_page_id, sorted(views.views))

    return CRMWorkspaceResult(
        crm_page_id=crm_page_id,
        companies_id=companies_id,
        people_id=people_id,
        deals_id=deals_id,
        meetings_id=meetings_id,
        activities_id=activities_id,
        views=views.views,
        warnings=views.warnings,
    )


@dataclass
class CRMHomeResult:
    views: dict[str, dict[str, str]]
    warnings: list[str]


async def upgrade_crm_home(
    client: httpx.AsyncClient,
    crm_page_id: str,
    *,
    previous_views: dict[str, dict[str, str]] | None = None,
) -> CRMHomeResult:
    """Refresh the CRM home template and its views in place.

    Removes only what Notion Pilot wrote — blocks whose text is a known template
    string, and views whose ids were persisted — and keeps the databases, their
    rows, and anything the user added. No re-seed, no schema change.
    """
    warnings: list[str] = []
    for view in (previous_views or {}).values():
        r = await client.delete(f"{NOTION_API}/blocks/{view['block_id']}")
        if r.status_code not in (200, 404):
            warnings.append(
                f"An old view could not be removed ({r.status_code}); delete the duplicate by hand."
            )

    children = await _list_children(client, crm_page_id)
    databases = {
        b["child_database"]["title"]: str(b["id"]) for b in children if b["type"] == "child_database"
    }
    leads_id = databases.get("Leads") or databases.get("Deals")
    activities_id = databases.get("Activities")
    for title, found in (("Leads", leads_id), ("Activities", activities_id)):
        if found is None:
            warnings.append(f"The {title} database was not found on this page; its views were skipped.")

    owned_texts = owned_template_texts()
    owned = [
        b for b in children if b["type"] != "child_database" and _plain_text(b) in owned_texts
    ]
    anchor = str(owned[0]["id"]) if owned and owned[0]["id"] == children[0]["id"] else None
    if anchor is None:
        warnings.append("The template was added at the bottom of the page. Drag it above the databases.")

    leads_props: set[str] = set()
    if leads_id:
        r = await client.get(f"{NOTION_API}/databases/{leads_id}")
        r.raise_for_status()
        leads_props = set(r.json()["properties"])

    home = await _append_blocks(client, crm_page_id, crm_home_blocks(leads_props), after=anchor)
    for block in owned:
        await client.delete(f"{NOTION_API}/blocks/{block['id']}")

    outcome = await _add_home_views(
        client, crm_page_id, home, leads_id=leads_id, activities_id=activities_id
    )
    return CRMHomeResult(views=outcome.views, warnings=warnings + outcome.warnings)


async def create_inbox_workspace(
    client: httpx.AsyncClient,
    parent_page_id: str,
    page_title: str = "Knowledge",
) -> InboxWorkspaceResult:
    """Create Knowledge container page + Notions, Ideas, Tools, Data & Technology databases with demo data."""
    logger.info("workspace: creating Knowledge '{}'", page_title)
    inbox_page_id = await _create_page(
        client, parent_page_id, page_title, "📚", _KNOWLEDGE_CHILDREN
    )

    notions_id = await _create_db(
        client,
        inbox_page_id,
        "Notions",
        {
            "Name": {"title": {}},
            "URL": {"url": {}},
            "Description": {"rich_text": {}},
            "Tags": {"multi_select": {"options": []}},
            "Source": {
                "select": {
                    "options": [
                        {"name": "Telegram"},
                        {"name": "Email"},
                        {"name": "Web"},
                        {"name": "Manual"},
                    ]
                }
            },
            "Interest": {
                "select": {
                    "options": [
                        {"name": "High", "color": "red"},
                        {"name": "Medium", "color": "yellow"},
                        {"name": "Low", "color": "gray"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "À relire", "color": "yellow"},
                        {"name": "Lu", "color": "green"},
                        {"name": "Archivé", "color": "gray"},
                    ]
                }
            },
            "Date": {"date": {}},
        },
        "💡",
    )

    ideas_id = await _create_db(
        client,
        inbox_page_id,
        "Ideas",
        {
            "Name": {"title": {}},
            "Description": {"rich_text": {}},
            "Tags": {"multi_select": {"options": []}},
            "Priority": {
                "select": {
                    "options": [
                        {"name": "High", "color": "red"},
                        {"name": "Medium", "color": "yellow"},
                        {"name": "Low", "color": "gray"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "Draft", "color": "gray"},
                        {"name": "Active", "color": "blue"},
                        {"name": "Archived", "color": "default"},
                    ]
                }
            },
        },
        "🧠",
    )

    tools_id = await _create_db(
        client,
        inbox_page_id,
        "Tools",
        {
            "Name": {"title": {}},
            "URL": {"url": {}},
            "Description": {"rich_text": {}},
            "Tags": {"multi_select": {"options": []}},
            "Pricing": {
                "select": {
                    "options": [
                        {"name": "Free", "color": "green"},
                        {"name": "Freemium", "color": "yellow"},
                        {"name": "Paid", "color": "red"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "Testing", "color": "yellow"},
                        {"name": "Using", "color": "green"},
                        {"name": "Archived", "color": "gray"},
                    ]
                }
            },
        },
        "🔧",
    )

    data_tech_id = await _create_db(
        client,
        inbox_page_id,
        "Data & Technology",
        {
            "Name": {"title": {}},
            "URL": {"url": {}},
            "Description": {"rich_text": {}},
            "Tags": {"multi_select": {"options": []}},
            "Domain": {
                "select": {
                    "options": [
                        {"name": "AI"},
                        {"name": "Data"},
                        {"name": "Dev"},
                        {"name": "Science"},
                        {"name": "Other"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "À relire", "color": "yellow"},
                        {"name": "Lu", "color": "green"},
                        {"name": "Archivé", "color": "gray"},
                    ]
                }
            },
        },
        "📊",
    )

    await _seed_notions(client, notions_id)
    await _seed_ideas(client, ideas_id)
    await _seed_tools(client, tools_id)
    await _seed_data_tech(client, data_tech_id)
    logger.info("workspace: Knowledge ready — page_id={}", inbox_page_id)

    return InboxWorkspaceResult(
        inbox_page_id=inbox_page_id,
        notions_id=notions_id,
        ideas_id=ideas_id,
        tools_id=tools_id,
        data_tech_id=data_tech_id,
    )
