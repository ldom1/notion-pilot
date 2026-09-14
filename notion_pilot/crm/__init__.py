"""CRM vertical — Telegram commands + re-exports from notion-pilot-powers."""

from notion_pilot_powers.core.dedup import CandidateRecord, DedupStatus, MatchResult, find_match
from notion_pilot_powers.core.syncer import (
    NotionCompanySyncer,
    NotionPeopleSyncer,
    PersonRecord,
    UpsertResult,
)

__all__ = [
    "CandidateRecord",
    "DedupStatus",
    "MatchResult",
    "find_match",
    "NotionCompanySyncer",
    "NotionPeopleSyncer",
    "PersonRecord",
    "UpsertResult",
]
