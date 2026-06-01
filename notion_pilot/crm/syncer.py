"""Notion People and Company syncers with fuzzy dedup."""

from dataclasses import dataclass, field
from typing import Any, Literal, cast

import httpx
from loguru import logger
from notion_client import AsyncClient
from rapidfuzz.fuzz import token_sort_ratio

from notion_pilot.shared.utils.dedup import CandidateRecord, DedupStatus, find_match, normalize


@dataclass
class PersonRecord:
    name: str
    company: str
    position: str = field(default="")
    linkedin_url: str = field(default="")
    email: str = field(default="")
    phone: str = field(default="")
    seniority: str = field(default="")
    role_type: list[str] = field(default_factory=list)


@dataclass
class UpsertResult:
    status: Literal["created", "skipped", "review"]
    page_id: str = field(default="")
    score: float = field(default=0.0)
    matched_name: str = field(default="")
    matched_company: str = field(default="")


class NotionCompanySyncer:
    """Load Companies snapshot from Notion; resolve or create on demand.

    Auto-detects whether to use the public databases API (wizard-created DBs)
    or the internal data_sources API (legacy inline DBs) on first load.
    Override with standard_api=True/False to skip auto-detection.
    """

    def __init__(
        self, client: AsyncClient, data_source_id: str, *, standard_api: bool | None = None
    ) -> None:
        self._client = client
        self._ds_id = data_source_id
        self._standard_api: bool | None = standard_api  # None = auto-detect on first load
        self._name_to_id: dict[str, str] = {}  # normalized name → page_id
        self._id_to_name: dict[str, str] = {}  # page_id → original name
        self.details: dict[
            str, dict[str, str]
        ] = {}  # page_id → {website, linkedin_url, size, country}

    def id_to_name(self, page_id: str) -> str:
        return self._id_to_name.get(page_id, "")

    async def _detect_api(self) -> None:
        """Probe once to determine whether to use standard databases or data_sources API."""
        try:
            await self._client.databases.retrieve(self._ds_id)
            self._standard_api = True
            logger.debug("Companies {}: using standard databases API", self._ds_id[:8])
        except Exception:  # noqa: BLE001
            self._standard_api = False
            logger.debug("Companies {}: using data_sources API", self._ds_id[:8])

    def _httpx_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._client.options.auth}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    async def _query_page(self, cursor: str | None) -> dict[str, Any]:
        if self._standard_api:
            body: dict[str, object] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            async with httpx.AsyncClient(headers=self._httpx_headers(), timeout=30) as hx:
                r = await hx.post(
                    f"https://api.notion.com/v1/databases/{self._ds_id}/query", json=body
                )
                r.raise_for_status()
                return cast(dict[str, Any], r.json())
        kw: dict[str, Any] = {"page_size": 100}
        if cursor:
            kw["start_cursor"] = cursor
        return cast(dict[str, Any], await self._client.data_sources.query(self._ds_id, **kw))

    async def load_snapshot(self) -> None:
        if self._standard_api is None:
            await self._detect_api()
        cursor: str | None = None
        while True:
            result = await self._query_page(cursor)
            for page in result["results"]:
                props = page["properties"]
                name_prop = props.get("Name", {})
                if name_prop.get("title"):
                    name = name_prop["title"][0]["plain_text"]
                    page_id = page["id"]
                    self._name_to_id[normalize(name)] = page_id
                    self._id_to_name[page_id] = name
                    detail: dict[str, str] = {}
                    if props.get("Website", {}).get("url"):
                        detail["website"] = props["Website"]["url"]
                    if props.get("Linkedin", {}).get("url"):
                        detail["linkedin_url"] = props["Linkedin"]["url"]
                    if props.get("Size", {}).get("select"):
                        detail["size"] = props["Size"]["select"]["name"]
                    if props.get("Country", {}).get("select"):
                        detail["country"] = props["Country"]["select"]["name"]
                    if props.get("Sector", {}).get("select"):
                        detail["sector"] = props["Sector"]["select"]["name"]
                    icon = page.get("icon") or {}
                    if icon.get("type") == "external":
                        detail["icon_url"] = (icon.get("external") or {}).get("url", "")
                    elif icon.get("type") == "emoji":
                        detail["icon_url"] = icon.get("emoji", "")
                    self.details[page_id] = detail
            if not result.get("has_more"):
                break
            cursor = result["next_cursor"]
        logger.info("Companies snapshot: {} entries", len(self._name_to_id))

    async def get_or_create(self, name: str) -> str:
        norm = normalize(name)
        best_score = 0.0
        best_id = ""
        for cached_norm, pid in self._name_to_id.items():
            score = float(token_sort_ratio(norm, cached_norm))
            if score > best_score:
                best_score = score
                best_id = pid
        if best_score >= 85 and best_id:
            return best_id
        parent = (
            {"type": "database_id", "database_id": self._ds_id}
            if self._standard_api
            else {"type": "data_source_id", "data_source_id": self._ds_id}
        )
        page = await self._client.pages.create(
            parent=parent,
            properties={"Name": {"title": [{"text": {"content": name}}]}},
        )
        page_id: str = page["id"]
        self._name_to_id[norm] = page_id
        self._id_to_name[page_id] = name
        logger.info("Created company: {} ({})", name, page_id)
        return page_id


class NotionPeopleSyncer:
    """Load People snapshot from Notion; upsert with dedup and company resolution."""

    def __init__(
        self,
        client: AsyncClient,
        data_source_id: str,
        company_syncer: NotionCompanySyncer,
    ) -> None:
        self._client = client
        self._ds_id = data_source_id
        self._company_syncer = company_syncer
        self._existing: list[CandidateRecord] = []

    @property
    def _standard_api(self) -> bool:
        return bool(self._company_syncer._standard_api)

    async def _query_page(self, cursor: str | None) -> dict[str, Any]:
        if self._standard_api:
            body: dict[str, object] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            async with httpx.AsyncClient(
                headers=self._company_syncer._httpx_headers(), timeout=30
            ) as hx:
                r = await hx.post(
                    f"https://api.notion.com/v1/databases/{self._ds_id}/query", json=body
                )
                r.raise_for_status()
                return cast(dict[str, Any], r.json())
        kw: dict[str, Any] = {"page_size": 100}
        if cursor:
            kw["start_cursor"] = cursor
        return cast(dict[str, Any], await self._client.data_sources.query(self._ds_id, **kw))

    async def load_snapshot(self) -> None:
        """Load all existing people into memory. Call after company_syncer.load_snapshot()."""
        cursor: str | None = None
        while True:
            result = await self._query_page(cursor)
            for page in result["results"]:
                props = page["properties"]
                name_prop = props.get("Nom", {})
                name = name_prop["title"][0]["plain_text"] if name_prop.get("title") else ""
                if not name:
                    continue
                company_ids = [r["id"] for r in props.get("Company", {}).get("relation", [])]
                company = self._company_syncer.id_to_name(company_ids[0]) if company_ids else ""
                candidate: CandidateRecord = {
                    "name": name,
                    "company": company,
                    "page_id": page["id"],
                }
                position_prop = props.get("Position", {})
                if position_prop.get("rich_text"):
                    candidate["position"] = position_prop["rich_text"][0]["plain_text"]
                seniority_prop = props.get("Seniority", {})
                if seniority_prop.get("select"):
                    candidate["seniority"] = seniority_prop["select"]["name"]
                role_type_prop = props.get("Role Type", {})
                if role_type_prop.get("multi_select"):
                    candidate["role_type"] = [o["name"] for o in role_type_prop["multi_select"]]
                linkedin_prop = props.get("Linkedin", {})
                if linkedin_prop.get("url"):
                    candidate["linkedin_url"] = linkedin_prop["url"]
                email_prop = props.get("Email - pro", {})
                if email_prop.get("email"):
                    candidate["email"] = email_prop["email"]
                phone_prop = props.get("Phone", {})
                if phone_prop.get("phone_number"):
                    candidate["phone"] = phone_prop["phone_number"]
                self._existing.append(candidate)
            if not result.get("has_more"):
                break
            cursor = result["next_cursor"]
        logger.info("People snapshot: {} entries", len(self._existing))

    async def upsert(self, person: PersonRecord) -> UpsertResult:
        match = find_match(person.name, person.company, self._existing)

        if match.status == DedupStatus.SKIP:
            return UpsertResult(
                "skipped",
                score=match.score,
                matched_name=match.matched_name,
                matched_company=match.matched_company,
            )
        if match.status == DedupStatus.REVIEW:
            return UpsertResult(
                "review",
                score=match.score,
                matched_name=match.matched_name,
                matched_company=match.matched_company,
            )

        company_id = ""
        if person.company:
            company_id = await self._company_syncer.get_or_create(person.company)

        properties: dict[str, object] = {
            "Nom": {"title": [{"text": {"content": person.name}}]},
            "In my network": {"select": {"name": "Yes"}},
        }
        if person.position:
            properties["Position"] = {"rich_text": [{"text": {"content": person.position}}]}
        if person.linkedin_url:
            properties["Linkedin"] = {"url": person.linkedin_url}
        if person.email:
            properties["Email - pro"] = {"email": person.email}
        if person.phone:
            properties["Phone"] = {"phone_number": person.phone}
        if person.seniority:
            properties["Seniority"] = {"select": {"name": person.seniority}}
        if person.role_type:
            properties["Role Type"] = {"multi_select": [{"name": rt} for rt in person.role_type]}
        if company_id:
            properties["Company"] = {"relation": [{"id": company_id}]}

        parent = (
            {"type": "database_id", "database_id": self._ds_id}
            if self._standard_api
            else {"type": "data_source_id", "data_source_id": self._ds_id}
        )
        page = await self._client.pages.create(parent=parent, properties=properties)
        page_id: str = page["id"]
        self._existing.append({"name": person.name, "company": person.company, "page_id": page_id})
        logger.info("Created person: {} @ {} ({})", person.name, person.company, page_id)
        return UpsertResult("created", page_id=page_id)
