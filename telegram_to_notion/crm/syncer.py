"""Notion People and Company syncers with fuzzy dedup."""
from dataclasses import dataclass, field
from typing import Literal

from loguru import logger
from notion_client import AsyncClient
from rapidfuzz.fuzz import token_sort_ratio

from telegram_to_notion.utils.dedup import CandidateRecord, DedupStatus, find_match, normalize


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
    """Load Companies snapshot from Notion; resolve or create on demand."""

    def __init__(self, client: AsyncClient, data_source_id: str) -> None:
        self._client = client
        self._ds_id = data_source_id
        self._name_to_id: dict[str, str] = {}  # normalized name → page_id
        self._id_to_name: dict[str, str] = {}  # page_id → original name
        self.details: dict[str, dict[str, str]] = {}  # page_id → {website, linkedin_url, size, country}

    def id_to_name(self, page_id: str) -> str:
        return self._id_to_name.get(page_id, "")

    async def load_snapshot(self) -> None:
        cursor: str | None = None
        while True:
            kw: dict[str, object] = dict(data_source_id=self._ds_id, page_size=100)
            if cursor:
                kw["start_cursor"] = cursor
            result = await self._client.data_sources.query(**kw)
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
        for cached_norm, page_id in self._name_to_id.items():
            score = float(token_sort_ratio(norm, cached_norm))
            if score > best_score:
                best_score = score
                best_id = page_id
        if best_score >= 85 and best_id:
            return best_id
        page = await self._client.pages.create(
            parent={"type": "data_source_id", "data_source_id": self._ds_id},
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

    async def load_snapshot(self) -> None:
        """Load all existing people into memory. Call after company_syncer.load_snapshot()."""
        cursor: str | None = None
        while True:
            kw: dict[str, object] = dict(data_source_id=self._ds_id, page_size=100)
            if cursor:
                kw["start_cursor"] = cursor
            result = await self._client.data_sources.query(**kw)
            for page in result["results"]:
                props = page["properties"]
                name_prop = props.get("Nom", {})
                name = name_prop["title"][0]["plain_text"] if name_prop.get("title") else ""
                if not name:
                    continue
                company_ids = [r["id"] for r in props.get("Entreprise", {}).get("relation", [])]
                company = self._company_syncer.id_to_name(company_ids[0]) if company_ids else ""
                candidate: CandidateRecord = {
                    "name": name,
                    "company": company,
                    "page_id": page["id"],
                }
                position_prop = props.get("Fonction", {})
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
                email_prop = props.get("E-mail pro", {})
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
            return UpsertResult("skipped", score=match.score,
                                matched_name=match.matched_name, matched_company=match.matched_company)
        if match.status == DedupStatus.REVIEW:
            return UpsertResult("review", score=match.score,
                                matched_name=match.matched_name, matched_company=match.matched_company)

        company_id = ""
        if person.company:
            company_id = await self._company_syncer.get_or_create(person.company)

        properties: dict[str, object] = {
            "Nom": {"title": [{"text": {"content": person.name}}]},
            "Dans mon réseau ?": {"select": {"name": "Yes"}},
        }
        if person.position:
            properties["Fonction"] = {"rich_text": [{"text": {"content": person.position}}]}
        if person.linkedin_url:
            properties["Linkedin"] = {"url": person.linkedin_url}
        if person.email:
            properties["E-mail pro"] = {"email": person.email}
        if person.phone:
            properties["Phone"] = {"phone_number": person.phone}
        if person.seniority:
            properties["Seniority"] = {"select": {"name": person.seniority}}
        if person.role_type:
            properties["Role Type"] = {
                "multi_select": [{"name": rt} for rt in person.role_type]
            }
        if company_id:
            properties["Entreprise"] = {"relation": [{"id": company_id}]}

        page = await self._client.pages.create(
            parent={"type": "data_source_id", "data_source_id": self._ds_id},
            properties=properties,
        )
        page_id: str = page["id"]
        self._existing.append({"name": person.name, "company": person.company, "page_id": page_id})
        logger.info("Created person: {} @ {} ({})", person.name, person.company, page_id)
        return UpsertResult("created", page_id=page_id)
