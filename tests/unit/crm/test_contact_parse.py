"""Unit tests for crm/contact_parse.py."""

from notion_pilot.crm.contact_parse import (
    is_placeholder,
    parse_comma_contact,
    parse_contact_message,
    parse_linkedin_company_paste,
    parse_linkedin_deterministic,
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


def test_parse_linkedin_company_url_only():
    result = parse_linkedin_company_paste("https://www.linkedin.com/company/altotrain/")
    assert result is not None
    assert result["name"] == "Altotrain"
    assert result["linkedin_url"] == "https://www.linkedin.com/company/altotrain"


def test_parse_linkedin_company_with_name():
    result = parse_linkedin_company_paste(
        "https://www.linkedin.com/company/altotrain/ : Alto, Rail Transportation"
    )
    assert result is not None
    assert result["name"] == "Alto"
    assert "altotrain" in result["linkedin_url"]


def test_parse_linkedin_deterministic_routes_by_path():
    person = parse_linkedin_deterministic(_OLIVIER_MSG)
    assert person is not None
    assert person[0] == "people"
    company = parse_linkedin_deterministic("https://www.linkedin.com/company/altotrain/")
    assert company is not None
    assert company[0] == "company"


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


_FICTIONAL_MD_MSG = (
    "[Jordan Belrose](https://www.linkedin.com/in/jordan-belrose-12345678/), Nordvale Energy :\n"
    "https://www.linkedin.com/in/jordan-belrose-12345678/"
)

_FICTIONAL_MD_MSG_DIFFERING_URL = (
    "[Jordan Belrose](https://www.linkedin.com/in/jordan-belrose-12345678/), Nordvale Energy :\n"
    "https://www.linkedin.com/in/jordan-belrose-stale-slug/"
)


def test_parse_markdown_link_person_paste_matches_markdown_first_format():
    from notion_pilot.crm.contact_parse import parse_markdown_link_person_paste

    result = parse_markdown_link_person_paste(_FICTIONAL_MD_MSG)
    assert result is not None
    assert result["name"] == "Jordan Belrose"
    assert result["company"] == "Nordvale Energy"
    assert result["linkedin_url"] == "https://www.linkedin.com/in/jordan-belrose-12345678/"


def test_parse_markdown_link_person_paste_returns_none_on_differing_second_url():
    from notion_pilot.crm.contact_parse import parse_markdown_link_person_paste

    assert parse_markdown_link_person_paste(_FICTIONAL_MD_MSG_DIFFERING_URL) is None


def test_parse_contact_message_routes_markdown_link_format():
    result = parse_contact_message(_FICTIONAL_MD_MSG)
    assert result is not None
    assert result["name"] == "Jordan Belrose"
    assert result["company"] == "Nordvale Energy"


def test_parse_contact_message_falls_through_to_none_on_differing_second_url():
    # Ambiguous — don't guess which URL is right; let the caller fall to the LLM.
    assert parse_contact_message(_FICTIONAL_MD_MSG_DIFFERING_URL) is None
