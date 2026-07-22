"""Tests for web.utils Notion property helpers."""

from web.utils import extract_relation_ids, resolve_company_name


def test_resolve_company_name_from_relation():
    props = {
        "Company": {
            "type": "relation",
            "relation": [{"id": "cfc21198-9684-47ef-98ae-fc5657511998"}],
        }
    }
    names = {"cfc21198-9684-47ef-98ae-fc5657511998": "Veolia Eau"}
    assert resolve_company_name(props, names) == "Veolia Eau"


def test_extract_relation_ids_empty_when_missing():
    assert extract_relation_ids({}, "Company") == []
