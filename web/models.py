"""Pydantic request/response models for the Notion Pilot web server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SetupRequest(BaseModel):
    scope: Literal["crm", "inbox", "both"]
    workspace_name: str
    notion_token: str | None = None
    # Where to put the deploy. None means the top level of the workspace, which
    # Notion only permits for public-integration OAuth tokens.
    parent_page_id: str | None = None


class SetupResponse(BaseModel):
    notion_page_url: str


class CockpitConfigRequest(BaseModel):
    databases: dict[str, str]
    workspace_url: str | None = None


class RunScriptRequest(BaseModel):
    script_id: str
    extra_args: list[str] = []


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    query: str
    history: list[ChatMessage] = []
    session_id: str | None = None


class UpdateMemoryRequest(BaseModel):
    text: str


class CreateLeadRequest(BaseModel):
    name: str
    position: str = ""
    company: str = ""


class CreateDealRequest(BaseModel):
    deal_name: str
    notion_id: str | None = None  # existing People page to link
    new_person: CreateLeadRequest | None = None  # create person first if no notion_id
    extra_fields: dict | None = None  # wizard-collected property values
    summary: str | None = None  # chat analysis that led to this deal
    company_name: str | None = None  # company to link as relation


class LogActivityRequest(BaseModel):
    """Log one CRM activity through the browser's own OAuth session.

    The MCP `log_activity` tool acts on the operator's static NOTION_TOKEN, so a
    first-time user who deployed through the wizard cannot reach their own
    Activities database with it. This request is the session-token path.
    """

    title: str
    type: str = "📞 Call"
    outcome: str | None = None
    date: str | None = None  # ISO date; defaults to today
    duration_min: int | None = None
    deal_page_id: str | None = None
    person_page_id: str | None = None
    company_page_id: str | None = None
    next_step: str | None = None
    next_step_date: str | None = None
    notes: str | None = None


# ── Workflow composition ──────────────────────────────────────────────────────


class WorkflowNode(BaseModel):
    id: str  # matches a script id from scripts.yaml
    position: dict  # {x, y} for React Flow layout


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str


class WorkflowDef(BaseModel):
    id: str  # uuid generated client-side
    name: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class SaveWorkflowRequest(BaseModel):
    workflow: WorkflowDef


class RunWorkflowRequest(BaseModel):
    workflow_id: str
