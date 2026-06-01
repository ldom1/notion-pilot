"""Shared Notion workspace creation logic used by CLI scripts, Telegram /setup, and web server."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"
type JsonDict = dict[str, Any]


# --- block helpers ---


def _rt(content: str) -> list[JsonDict]:
    return [{"type": "text", "text": {"content": content}}]


def _paragraph(content: str) -> JsonDict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(content)}}


def _h2(content: str) -> JsonDict:
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": _rt(content)}}


def _callout(content: str, emoji: str = "💡") -> JsonDict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": _rt(content),
            "icon": {"type": "emoji", "emoji": emoji},
        },
    }


def _bullet(content: str) -> JsonDict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rt(content)},
    }


def _numbered(content: str) -> JsonDict:
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": _rt(content)},
    }


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
    _bullet("/enrich — Enrich a contact or company with Apollo / Brave Search"),
    _bullet("/people — Add a contact"),
    _bullet("/notion — Save a thought, article, or link to Knowledge"),
    _bullet("/idea — Capture an idea"),
    _bullet("/knowledge — Search your knowledge base"),
]

_CRM_CHILDREN: list[JsonDict] = [
    _callout(
        "Start with a Company → add People → track Deals → /enrich to auto-fill details.",
        "🏢",
    ),
    _h2("Getting started"),
    _numbered("Add a company: /lead TechCorp"),
    _numbered("Add contacts: /people Alice Martin, CTO @ TechCorp"),
    _numbered("Track a deal: /deal ERP Integration — TechCorp, €45k"),
    _numbered("Enrich a contact: /enrich Alice Martin"),
    _paragraph(
        "💡 Tip: switch the Deals view to Board (group by Stage) for a Kanban pipeline."
        " In Notion: ··· → Add a view → Board."
    ),
]

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
        "activities": ["R&D & Consulting", "Energy"],
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
        "activities": ["R&D & Consulting"],
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
        "activities": ["Data & IA"],
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
        "activities": ["Energy", "R&D & Consulting"],
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
        "activities": ["Data & IA"],
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
        "next_action": "Send case study on analytics migration",
        "next_action_date": "2026-06-15",
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


async def create_workspace_root_page(client: httpx.AsyncClient, name: str) -> str:
    """Create a top-level page in the user's Notion workspace. Returns the page ID."""
    logger.info("workspace: creating root page '{}'", name)
    r = await client.post(
        f"{NOTION_API}/pages",
        json={
            "parent": {"workspace": True},
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
    deals_id: str


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
            "Activities": {"multi_select": [{"name": a} for a in c["activities"]]},
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
            "Nom": {"title": _rt(p["name"])},
            "Company": {"relation": [{"id": company_ids[p["company"]]}]},
            "Position": {"rich_text": _rt(p["position"])},
            "Linkedin": {"url": p["linkedin"]},
            "Email - pro": {"email": p["email_pro"]},
            "Phone": {"phone_number": p["phone"]},
            "In my network": {"select": {"name": p["in_network"]}},
            "Seniority": {"select": {"name": p["seniority"]}},
            "Role Type": {"multi_select": [{"name": r} for r in p["role_type"]]},
            "Profile": {"select": {"name": p["profile"]}},
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
) -> None:
    logger.info("workspace: seeding {} deals", len(_DEMO_DEALS))
    for d in _DEMO_DEALS:
        contacts = [{"id": people_ids[n]} for n in d["contacts"] if n in people_ids]
        props: dict[str, Any] = {
            "Name": {"title": _rt(d["name"])},
            "Client": {"relation": [{"id": company_ids[d["company"]]}]},
            "Stage": {"select": {"name": d["stage"]}},
            "Value (euros)": {"number": d["value"]},
            "Probability (%)": {"number": d["probability"]},
            "Product": {"multi_select": [{"name": p} for p in d["product"]]},
            "Type": {"select": {"name": d["type"]}},
            "Next Action": {"rich_text": _rt(d["next_action"])},
            "Next Action Date": {"date": {"start": d["next_action_date"]}},
            "Contacted": {"checkbox": d["contacted"]},
            "Notes": {"rich_text": _rt(d["notes"])},
        }
        if contacts:
            props["Contacts"] = {"relation": contacts}
        await _create_db_page(client, deals_id, props)


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
    crm_page_id = await _create_page(client, parent_page_id, page_title, "🏢", _CRM_CHILDREN)

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
            "Activities": {"multi_select": {"options": []}},
            "Tags": {"multi_select": {"options": []}},
            "Notes": {"rich_text": {}},
        },
        "🏭",
    )

    people_id = await _create_db(
        client,
        crm_page_id,
        "People",
        {
            "Nom": {"title": {}},
            "Company": {"relation": {"database_id": companies_id, "single_property": {}}},
            "Position": {"rich_text": {}},
            "Linkedin": {"url": {}},
            "Email - pro": {"email": {}},
            "Email - private": {"email": {}},
            "Phone": {"phone_number": {}},
            "In my network": {
                "select": {
                    "options": [
                        {"name": "Yes", "color": "green"},
                        {"name": "Non", "color": "gray"},
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
            "Profile": {
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
        "Deals",
        {
            "Name": {"title": {}},
            "Client": {"relation": {"database_id": companies_id, "single_property": {}}},
            "Contacts": {"relation": {"database_id": people_id, "single_property": {}}},
            "Stage": {
                "select": {
                    "options": [
                        {"name": "Prospect", "color": "gray"},
                        {"name": "Qualified", "color": "blue"},
                        {"name": "Proposal Sent", "color": "yellow"},
                        {"name": "Negotiation", "color": "orange"},
                        {"name": "Closed Won", "color": "green"},
                        {"name": "Closed Lost", "color": "red"},
                        {"name": "No answer", "color": "default"},
                    ]
                }
            },
            "Value (euros)": {"number": {"format": "euro"}},
            "Probability (%)": {"number": {"format": "percent"}},
            "Next Action": {"rich_text": {}},
            "Next Action Date": {"date": {}},
            "Product": {
                "multi_select": {
                    "options": [
                        {"name": "HPC-as-a-service"},
                        {"name": "Consulting"},
                        {"name": "Optimization"},
                        {"name": "Training"},
                    ]
                }
            },
            "Type": {
                "select": {
                    "options": [
                        {"name": "Prospection froide", "color": "gray"},
                        {"name": "Prospection tiède", "color": "yellow"},
                        {"name": "Prospection chaude", "color": "orange"},
                        {"name": "Lead qualifié", "color": "green"},
                    ]
                }
            },
            "Contacted": {"checkbox": {}},
            "Notes": {"rich_text": {}},
        },
        "💼",
    )

    company_ids = await _seed_companies(client, companies_id)
    people_ids = await _seed_people(client, people_id, company_ids)
    await _seed_deals(client, deals_id, company_ids, people_ids)
    logger.info("workspace: CRM ready — page_id={}", crm_page_id)

    return CRMWorkspaceResult(
        crm_page_id=crm_page_id,
        companies_id=companies_id,
        people_id=people_id,
        deals_id=deals_id,
    )


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
            "Tags": {"multi_select": {}},
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
            "Tags": {"multi_select": {}},
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
            "Tags": {"multi_select": {}},
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
        "🛠️",
    )

    data_tech_id = await _create_db(
        client,
        inbox_page_id,
        "Data & Technology",
        {
            "Name": {"title": {}},
            "URL": {"url": {}},
            "Description": {"rich_text": {}},
            "Tags": {"multi_select": {}},
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
