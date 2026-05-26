"""Unit tests for crm/syncer.py — mocked Notion client."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from telegram_to_notion.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer, PersonRecord


def _make_company_page(page_id: str, name: str) -> dict:
    return {
        "id": page_id,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": name}]}
        },
    }


def _mock_ds_query(pages: list[dict]):
    mock = AsyncMock()
    mock.data_sources = MagicMock()
    mock.data_sources.query = AsyncMock(
        return_value={"results": pages, "has_more": False}
    )
    mock.pages = MagicMock()
    mock.pages.create = AsyncMock(return_value={"id": "new-company-id"})
    return mock


class TestNotionCompanySyncer:
    async def test_load_snapshot_populates_cache(self):
        client = _mock_ds_query([
            _make_company_page("id-edf", "EDF"),
            _make_company_page("id-rte", "RTE"),
        ])
        syncer = NotionCompanySyncer(client, "fake-ds-id")
        await syncer.load_snapshot()

        assert syncer.id_to_name("id-edf") == "EDF"
        assert syncer.id_to_name("id-rte") == "RTE"
        assert syncer.id_to_name("unknown") == ""

    async def test_get_or_create_returns_existing_on_exact_match(self):
        client = _mock_ds_query([_make_company_page("id-edf", "EDF")])
        syncer = NotionCompanySyncer(client, "fake-ds-id")
        await syncer.load_snapshot()

        page_id = await syncer.get_or_create("EDF")
        assert page_id == "id-edf"
        client.pages.create.assert_not_called()

    async def test_get_or_create_returns_existing_on_fuzzy_match(self):
        client = _mock_ds_query([_make_company_page("id-edf", "EDF S.A.")])
        syncer = NotionCompanySyncer(client, "fake-ds-id")
        await syncer.load_snapshot()

        page_id = await syncer.get_or_create("EDF SA")
        assert page_id == "id-edf"
        client.pages.create.assert_not_called()

    async def test_get_or_create_creates_new_company(self):
        client = _mock_ds_query([_make_company_page("id-edf", "EDF")])
        syncer = NotionCompanySyncer(client, "fake-ds-id")
        await syncer.load_snapshot()

        page_id = await syncer.get_or_create("OVHcloud")
        assert page_id == "new-company-id"
        client.pages.create.assert_called_once()
        call_kwargs = client.pages.create.call_args.kwargs
        assert call_kwargs["parent"]["data_source_id"] == "fake-ds-id"
        assert call_kwargs["properties"]["Name"]["title"][0]["text"]["content"] == "OVHcloud"

    async def test_get_or_create_caches_new_company(self):
        client = _mock_ds_query([])
        syncer = NotionCompanySyncer(client, "fake-ds-id")
        await syncer.load_snapshot()

        await syncer.get_or_create("NewCorp")
        await syncer.get_or_create("NewCorp")  # second call — should not create again

        assert client.pages.create.call_count == 1


def _make_people_page(page_id: str, name: str, company_page_ids: list[str] | None = None) -> dict:
    return {
        "id": page_id,
        "properties": {
            "Nom": {"type": "title", "title": [{"plain_text": name}]},
            "Entreprise": {
                "type": "relation",
                "relation": [{"id": cid} for cid in (company_page_ids or [])],
            },
        },
    }


def _mock_people_client(people_pages: list[dict], company_pages: list[dict]):
    mock = AsyncMock()
    mock.data_sources = MagicMock()

    # query returns people or companies based on data_source_id arg
    async def _query(data_source_id, **kw):
        if data_source_id == "fake-companies-ds":
            return {"results": company_pages, "has_more": False}
        return {"results": people_pages, "has_more": False}

    mock.data_sources.query = _query
    mock.pages = MagicMock()
    mock.pages.create = AsyncMock(return_value={"id": "new-person-id"})
    return mock


class TestNotionPeopleSyncer:
    async def _make_syncer(self, people_pages, company_pages):
        client = _mock_people_client(people_pages, company_pages)
        company_syncer = NotionCompanySyncer(client, "fake-companies-ds")
        await company_syncer.load_snapshot()
        people_syncer = NotionPeopleSyncer(client, "fake-people-ds", company_syncer)
        await people_syncer.load_snapshot()
        return people_syncer, client

    async def test_upsert_skips_exact_duplicate(self):
        people = [_make_people_page("p1", "Jean Dupont", ["c1"])]
        companies = [_make_company_page("c1", "EDF")]
        syncer, client = await self._make_syncer(people, companies)

        result = await syncer.upsert(PersonRecord(name="Jean Dupont", company="EDF"))
        assert result.status == "skipped"
        client.pages.create.assert_not_called()

    async def test_upsert_creates_new_person(self):
        people = [_make_people_page("p1", "Alice Martin", ["c1"])]
        companies = [_make_company_page("c1", "Engie")]
        syncer, client = await self._make_syncer(people, companies)

        result = await syncer.upsert(PersonRecord(name="Bob Bernard", company="OVHcloud", position="CTO"))
        assert result.status == "created"
        assert result.page_id == "new-person-id"
        client.pages.create.assert_called()

    async def test_upsert_review_range_does_not_create(self):
        # borderline match — same name, completely different company string
        people = [_make_people_page("p1", "Jean Dupont", [])]
        companies = []
        syncer, client = await self._make_syncer(people, companies)

        result = await syncer.upsert(PersonRecord(name="Jean Dupont", company="Zzz Corp Far Far Away XYZ"))
        # could be REVIEW or SKIP depending on score — must NOT be "created"
        assert result.status in ("skipped", "review")
        client.pages.create.assert_not_called()

    async def test_upsert_sets_linkedin_and_email(self):
        syncer, client = await self._make_syncer([], [])

        await syncer.upsert(PersonRecord(
            name="New Person",
            company="NewCorp",
            linkedin_url="https://linkedin.com/in/newperson",
            email="new@newcorp.com",
        ))
        props = client.pages.create.call_args.kwargs["properties"]
        assert props["Linkedin"]["url"] == "https://linkedin.com/in/newperson"
        assert props["E-mail pro"]["email"] == "new@newcorp.com"

    async def test_upsert_sets_dans_mon_reseau(self):
        syncer, client = await self._make_syncer([], [])
        await syncer.upsert(PersonRecord(name="X", company="Y"))
        props = client.pages.create.call_args.kwargs["properties"]
        assert props["Dans mon réseau ?"]["select"]["name"] == "Yes"

    async def test_upsert_sets_phone_seniority_role_type(self):
        syncer, client = await TestNotionPeopleSyncer._make_syncer(TestNotionPeopleSyncer, [], [])
        await syncer.upsert(PersonRecord(
            name="New Person",
            company="NewCorp",
            phone="+33612345678",
            seniority="vp",
            role_type=["engineering", "management"],
        ))
        props = client.pages.create.call_args.kwargs["properties"]
        assert props["Phone"]["phone_number"] == "+33612345678"
        assert props["Seniority"]["select"]["name"] == "vp"
        assert {"name": "engineering"} in props["Role Type"]["multi_select"]
        assert {"name": "management"} in props["Role Type"]["multi_select"]


async def test_load_snapshot_reads_optional_fields():
    client = _mock_people_client(
        people_pages=[{
            "id": "p1",
            "properties": {
                "Nom": {"title": [{"plain_text": "Alice Martin"}]},
                "Entreprise": {"relation": []},
                "Fonction": {"rich_text": [{"plain_text": "VP Engineering"}]},
                "Seniority": {"select": {"name": "vp"}},
                "Role Type": {"multi_select": [{"name": "engineering"}]},
                "Linkedin": {"url": "https://linkedin.com/in/alice"},
            },
        }],
        company_pages=[],
    )
    company_syncer = NotionCompanySyncer(client, "fake-companies-ds")
    await company_syncer.load_snapshot()
    people_syncer = NotionPeopleSyncer(client, "fake-people-ds", company_syncer)
    await people_syncer.load_snapshot()

    assert len(people_syncer._existing) == 1
    candidate = people_syncer._existing[0]
    assert candidate.get("position") == "VP Engineering"
    assert candidate.get("seniority") == "vp"
    assert candidate.get("role_type") == ["engineering"]
    assert "linkedin.com/in/alice" in candidate.get("linkedin_url", "")
