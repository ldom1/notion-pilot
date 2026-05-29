# tests/unit/web/test_oauth.py
import pytest
import httpx
import respx

from web.oauth import build_authorize_url, exchange_code_for_token

NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"


def test_build_authorize_url_contains_required_params():
    url = build_authorize_url(
        client_id="my_client",
        redirect_uri="http://localhost:8080/auth/notion/callback",
        state="random_state_123",
    )
    assert "https://api.notion.com/v1/oauth/authorize" in url
    assert "client_id=my_client" in url
    assert "response_type=code" in url
    assert "owner=user" in url
    assert "state=random_state_123" in url


@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_for_token_returns_access_token():
    respx.post(NOTION_TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "notion_access_token_abc",
                "workspace_name": "My Team",
                "workspace_id": "ws123",
                "token_type": "bearer",
            },
        )
    )
    token = await exchange_code_for_token(
        code="auth_code_xyz",
        client_id="my_client",
        client_secret="my_secret",
        redirect_uri="http://localhost:8080/auth/notion/callback",
    )
    assert token == "notion_access_token_abc"


@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_for_token_raises_on_error():
    respx.post(NOTION_TOKEN_URL).mock(
        return_value=httpx.Response(400, json={"error": "invalid_grant"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await exchange_code_for_token(
            code="bad_code",
            client_id="my_client",
            client_secret="my_secret",
            redirect_uri="http://localhost:8080/auth/notion/callback",
        )
