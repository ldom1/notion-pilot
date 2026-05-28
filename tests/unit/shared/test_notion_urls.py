from notion_pilot.shared.utils.notion_urls import page_id_from_url


def test_raw_uuid_no_dashes():
    assert page_id_from_url("550e8400e29b41d4a716446655440000") == (
        "550e8400-e29b-41d4-a716-446655440000"
    )


def test_notion_url_with_slug():
    url = "https://www.notion.so/My-Page-550e8400e29b41d4a716446655440000"
    assert page_id_from_url(url) == "550e8400-e29b-41d4-a716-446655440000"


def test_notion_url_with_query_params():
    url = "https://www.notion.so/My-Page-550e8400e29b41d4a716446655440000?pvs=4"
    assert page_id_from_url(url) == "550e8400-e29b-41d4-a716-446655440000"


def test_already_hyphenated_uuid():
    uid = "550e8400-e29b-41d4-a716-446655440000"
    assert page_id_from_url(uid) == uid


def test_url_with_hash():
    url = "https://www.notion.so/My-Page-550e8400e29b41d4a716446655440000#heading"
    assert page_id_from_url(url) == "550e8400-e29b-41d4-a716-446655440000"
