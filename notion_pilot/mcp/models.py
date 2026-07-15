"""Pydantic models for MCP tool inputs and outputs."""

from pydantic import BaseModel, Field


class PersonRecord(BaseModel):
    """Input shape for a person to upsert into the Notion People database."""

    name: str = Field(..., description="Full name of the contact")
    company: str = Field(..., description="Company name")
    position: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    phone: str | None = None
    seniority: str | None = None
    role_type: list[str] | None = None


class CompanyRecord(BaseModel):
    """Input shape for a company to upsert into the Notion Companies database."""

    name: str = Field(..., description="Company name")
    website: str | None = None
    linkedin_url: str | None = None
    size: str | None = None
    country: str | None = None
    sector: str | None = None


class RecordResult(BaseModel):
    """Outcome of processing a single record within a batch tool call."""

    name: str
    status: str
    score: float = 0.0
    matched_name: str = ""
    matched_company: str = ""
    page_id: str = ""
    error_message: str = ""


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
