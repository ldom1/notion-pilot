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
