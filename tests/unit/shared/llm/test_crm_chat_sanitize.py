"""Tests for CRM chat lead sanitization."""

from notion_pilot.shared.llm.crm_chat import sanitize_leads

_PEOPLE = [
    {
        "id": "36d6c451-9465-8039-b5f9-cccdabea1730",
        "name": "Xavier Jeulin",
        "position": "Head of Data & AI @ Veolia Eau France",
        "company": "Veolia Eau",
    },
    {
        "id": "36d6c451-9465-8044-9ff9-e15e7e81eb13",
        "name": "Meriem Riadi",
        "position": "Directrice Générale Veolia Eau Industrie France",
        "company": "Veolia Eau",
    },
]


def test_rehydrates_name_from_notion_id_when_llm_used_placeholder():
    leads = [
        {
            "type": "existing",
            "name": "[PERSON_NAME]",
            "position": "Head of Data & AI @ Veolia Eau [ADDRESS]",
            "company": "Veolia Eau",
            "notion_id": "36d6c451-9465-8039-b5f9-cccdabea1730",
            "reason": "Data leader",
        }
    ]
    out = sanitize_leads(leads, _PEOPLE)
    assert len(out) == 1
    assert out[0]["name"] == "Xavier Jeulin"
    assert "[ADDRESS]" not in out[0]["position"]


def test_drops_leads_with_no_resolvable_name():
    leads = [{"type": "new", "name": "[PERSON_NAME]", "reason": "unknown"}]
    assert sanitize_leads(leads, _PEOPLE) == []


def test_keeps_valid_new_leads():
    leads = [{"type": "new", "name": "Alice Martin", "company": "Acme", "reason": "ICP fit"}]
    out = sanitize_leads(leads, _PEOPLE)
    assert out[0]["name"] == "Alice Martin"
