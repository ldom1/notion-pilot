"""Unit tests for crm/contact_parse.py."""

from notion_pilot.crm.contact_parse import (
    is_placeholder,
    parse_comma_contact,
    parse_contact_message,
    parse_linkedin_paste,
    sanitize_extracted,
)

_OLIVIER_MSG = (
    "https://www.linkedin.com/in/ocoussau/ : "
    "Olivier Coussau, Veolia, Chapter Lead Appel d'Offres et Développement"
)


def test_parse_linkedin_paste_olivier_coussau():
    result = parse_linkedin_paste(_OLIVIER_MSG)
    assert result is not None
    assert result["name"] == "Olivier Coussau"
    assert result["company"] == "Veolia"
    assert result["position"] == "Chapter Lead Appel d'Offres et Développement"
    assert result["linkedin_url"] == "https://www.linkedin.com/in/ocoussau/"


def test_parse_linkedin_paste_no_match():
    assert parse_linkedin_paste("Met Jean Dupont from Artelys, CTO") is None


def test_parse_comma_contact_name_position_company():
    result = parse_comma_contact(
        "Lisa Schwob, Responsable d'affaires Digital pour Veolia Eau France, Veolia"
    )
    assert result is not None
    assert result["name"] == "Lisa Schwob"
    assert result["company"] == "Veolia"
    assert "Responsable d'affaires" in result["position"]


def test_parse_comma_contact_name_company_position():
    result = parse_comma_contact(
        "Olivier Coussau, Veolia, Chapter Lead Appel d'Offres et Développement"
    )
    assert result is not None
    assert result["name"] == "Olivier Coussau"
    assert result["company"] == "Veolia"
    assert "Chapter Lead" in result["position"]


def test_parse_contact_message_prefers_linkedin():
    assert parse_contact_message(_OLIVIER_MSG) is not None
    assert (
        parse_contact_message(
            "Lisa Schwob, Responsable d'affaires Digital pour Veolia Eau France, Veolia"
        )["company"]
        == "Veolia"
    )


def test_is_placeholder():
    assert is_placeholder("[PERSON_NAME]")
    assert is_placeholder("[COMPANY]")
    assert is_placeholder("<name>")
    assert not is_placeholder("Olivier Coussau")


def test_sanitize_extracted_drops_placeholders_and_uses_fallback():
    llm = {
        "name": "[PERSON_NAME]",
        "company": "Appel d'Offres et Développement",
        "position": "Chapter Lead",
    }
    fallback = parse_linkedin_paste(_OLIVIER_MSG)
    clean = sanitize_extracted(llm, fallback=fallback)
    assert clean["name"] == "Olivier Coussau"
    assert clean["company"] == "Veolia"
    assert clean["position"] == "Chapter Lead Appel d'Offres et Développement"
    assert clean["linkedin_url"] == "https://www.linkedin.com/in/ocoussau/"
