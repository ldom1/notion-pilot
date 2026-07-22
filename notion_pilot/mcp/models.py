"""Pydantic models for MCP tool inputs and outputs."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# Rejects missing, empty, and whitespace-only values — not just "field present".
# A plain `str = Field(...)` only requires the key to exist; a client (LLM or
# otherwise) can still pass "" and create a blank Notion page.
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PersonRecord(BaseModel):
    """Input shape for a person to upsert into the Notion People database."""

    name: NonEmptyStr = Field(..., description="Full name of the contact")
    company: NonEmptyStr = Field(..., description="Company name")
    position: str | None = None
    linkedin_url: NonEmptyStr | None = None
    email: str | None = None
    phone: str | None = None
    seniority: str | None = None
    role_type: list[str] | None = None
    force: bool = Field(
        default=False,
        description="Bypass a needs_review dedup block on confirm=true (never bypasses other gates)",
    )


class CompanyRecord(BaseModel):
    """Input shape for a company to upsert into the Notion Companies database."""

    name: NonEmptyStr = Field(..., description="Company name")
    website: NonEmptyStr | None = None
    linkedin_url: NonEmptyStr | None = None
    size: str | None = None
    country: NonEmptyStr | None = None
    sector: NonEmptyStr | None = None
    contact_email: str | None = Field(
        default=None,
        description="Email of a known contact at this company — used as a dedup domain signal and, "
        "if no other source provides one, to derive a website guess",
    )
    force: bool = Field(
        default=False,
        description="Bypass a needs_review dedup block on confirm=true (never bypasses the SIREN "
        "confidence gate)",
    )


class DealInput(BaseModel):
    """Input shape for upsert_deal — matched against existing Deals by exact title."""

    name: NonEmptyStr = Field(..., description="Deal title")
    stage: NonEmptyStr | None = Field(default=None, description="Defaults to 'Prospect' if omitted")
    lead_source: NonEmptyStr | None = None
    company_name: NonEmptyStr | None = Field(
        default=None, description="Resolved to the Client relation via company dedup"
    )
    contact_page_id: NonEmptyStr | None = Field(
        default=None, description="Existing People page id — linked as Contacts"
    )
    primary_contact_page_id: NonEmptyStr | None = Field(
        default=None, description="Existing People page id — linked as Primary contact"
    )
    value_eur: float | None = None
    probability_pct: float | None = None
    expected_close_date: NonEmptyStr | None = Field(default=None, description="ISO date")
    next_step: str | None = None
    next_step_date: NonEmptyStr | None = Field(default=None, description="ISO date")
    notes: str | None = None
    product: list[str] | None = None
    confirm: bool = Field(
        default=False,
        description="Dry-run preview by default; pass confirm=true to actually write",
    )


class ActivityInput(BaseModel):
    """Input shape for log_activity — Activities are an append-only event log, no dedup."""

    type: NonEmptyStr = Field(..., description="e.g. '📞 Call', '🤝 Meeting', '📧 Email'")
    title: NonEmptyStr | None = Field(default=None, description="Defaults to `type` if omitted")
    outcome: NonEmptyStr | None = None
    deal_page_id: NonEmptyStr | None = None
    person_page_id: NonEmptyStr | None = None
    company_page_id: NonEmptyStr | None = None
    date: NonEmptyStr | None = Field(default=None, description="ISO date; defaults to today")
    duration_min: float | None = None
    next_step: str | None = None
    next_step_date: NonEmptyStr | None = Field(default=None, description="ISO date")
    notes: str | None = None
    confirm: bool = Field(
        default=False,
        description="Dry-run preview by default; pass confirm=true to actually write",
    )


class RecordResult(BaseModel):
    """Outcome of processing a single record within a batch tool call."""

    name: str
    status: str
    score: float = 0.0
    matched_name: str = ""
    matched_company: str = ""
    page_id: str = ""
    error_message: str = ""
    siren: str = ""
    siren_candidate_name: str = Field(
        default="",
        description="Registry match name, kept separate from matched_name (Notion dedup)",
    )
    reason: str = Field(default="", description="Explanation for needs_review or a force override")
    candidates: list[dict[str, str | float]] = Field(
        default_factory=list,
        description='Actionable near-matches: {"type": "notion", page_id, name, score} or '
        '{"type": "siren", siren, matched_name, score}',
    )
    enrichment_preview: dict[str, str] = Field(
        default_factory=dict,
        description="Fields that would be written on confirm=true (siren, sector, size, country, website)",
    )


class BatchResult(BaseModel):
    """Envelope returned by every batch tool: headline counts + per-record detail."""

    success_count: int
    fail_count: int
    summary: dict[str, int]
    results: list[RecordResult]


def summarize(results: list[RecordResult]) -> BatchResult:
    """Build the summary envelope from a flat list of per-record results."""
    fail_count = sum(1 for r in results if r.status == "error")
    summary: dict[str, int] = {}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    return BatchResult(
        success_count=len(results) - fail_count,
        fail_count=fail_count,
        summary=summary,
        results=results,
    )
