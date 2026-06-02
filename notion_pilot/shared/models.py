"""Pydantic data models for internal message flow."""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field

from notion_pilot.shared.llm.source_hints import infer_source_label

_URL_RE = re.compile(r"https?://[^\s<>\[\]()]+", re.IGNORECASE)


def _first_url(text: str) -> str | None:
    """Return the first HTTP(S) URL in ``text``, with trailing punctuation trimmed."""
    match = _URL_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(").,]\\\"'")


class MediaType(str, Enum):
    """Kind of Telegram content we persist to Notion."""

    TEXT = "text"
    PHOTO = "photo"
    VOICE = "voice"


class MediaPayload(BaseModel):
    """Downloaded file bytes plus filename and MIME type for Notion upload."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    content: bytes
    filename: str
    mime_type: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def size_bytes(self) -> int:
        """Length of ``content`` in bytes."""
        return len(self.content)


class IncomingMessage(BaseModel):
    """Normalized inbound message: text/caption, sender, time, media."""

    model_config = ConfigDict(frozen=True)

    text: str | None
    caption: str | None
    sender: str
    sent_at: datetime
    media_type: MediaType
    media: MediaPayload | None
    source_adapter: str = Field(..., min_length=1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> str:
        """First line of text or caption (trimmed, max 200 chars), else ``[media_type]``."""
        source = self.text or self.caption
        if source:
            first_line = source.strip().splitlines()[0]
            return first_line[:200] or f"[{self.media_type.value}]"
        return f"[{self.media_type.value}]"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def body(self) -> str:
        """Full text or caption for the page body (empty string if neither)."""
        return self.text or self.caption or ""


class NotionDatabaseProperties(BaseModel):
    """Structured row fields for Notion Database Properties (from OpenRouter or heuristics)."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, populate_by_name=True)

    name: str = Field(default="", alias="Name", description="Concise page title (≤ 10 words).")
    label: str | list[str] = Field(
        default="",
        alias="Label",
        description=(
            "Tag that best categorises the message (e.g. work, dev, finance, idea, "
            "health, learning, news, project). Can be a list of tags separated by commas."
        ),
    )
    entry_type: str = Field(
        default="",
        alias="Type",
        description="Exactly one of: note | Task | Link | Media | Question | Other.",
    )
    url: str | None = Field(
        default=None,
        alias="Link",
        description="The primary URL found in the message, or null if none.",
    )
    source: str | None = Field(
        default=None,
        alias="Source",
        description=(
            "Platform or origin if identifiable from the URL or context "
            "(e.g. Instagram, LinkedIn, YouTube, GitHub, arXiv); otherwise null."
        ),
    )
    description: str = Field(
        default="",
        alias="Description",
        description=(
            "1–3 sentences summarising the message for a human reader. "
            "Focus on what the content *is about*, not on the fact that it was sent via Telegram."
        ),
    )
    interest: str = Field(
        default="",
        alias="Interest",
        description=(
            "Exactly one of: Low | Medium | High. "
            "Assess based on apparent novelty, actionability, or personal relevance."
        ),
    )
    status: str = "Not analysed"

    @classmethod
    def from_incoming(cls, msg: IncomingMessage) -> Self:
        """Heuristic mapping when Agent is disabled or fails."""
        body = msg.body
        url = _first_url(body) if body else None
        desc = body if body else msg.name
        src = infer_source_label(body) if body else None
        return cls(
            name=msg.name,
            label=[msg.source_adapter],
            entry_type=msg.media_type.value,
            url=url,
            source=src,
            description=desc[:8000],
            interest="Medium",
            status="Not analysed",
        )

    def to_notion_properties(self) -> dict[str, Any]:  # noqa: PLR0912
        """Return a Notion-API-ready properties payload."""
        labels = (
            self.label if isinstance(self.label, list) else ([self.label] if self.label else [])
        )
        props: dict[str, Any] = {
            "Name": {"title": [{"text": {"content": self.name[:2000]}}]},
            "Label": {"multi_select": [{"name": lbl} for lbl in labels if lbl]},
            "Description": {"rich_text": [{"text": {"content": self.description[:2000]}}]},
        }
        if self.entry_type:
            props["Type"] = {"select": {"name": self.entry_type}}
        if self.interest:
            props["Interest"] = {"select": {"name": self.interest}}
        if self.status:
            props["Status"] = {"status": {"name": self.status}}
        if self.url:
            props["Link"] = {"url": self.url}
        if self.source:
            props["Source"] = {"select": {"name": self.source}}
        return props
