"""Notion OAuth helpers for the deploy wizard."""

from __future__ import annotations

import base64
from urllib.parse import urlencode

import httpx

_NOTION_AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
_NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    """Build the Notion OAuth authorization URL with required params."""
    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "owner": "user",
            "state": state,
        }
    )
    return f"{_NOTION_AUTHORIZE_URL}?{params}"


async def exchange_code_for_token(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> str:
    """Exchange an OAuth code for a Notion access token. Returns the access_token string."""
    data = await exchange_code_for_token_full(
        code=code, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri
    )
    return str(data["access_token"])


async def exchange_code_for_token_full(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange an OAuth code for a Notion access token. Returns the full response dict."""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _NOTION_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        r.raise_for_status()
        return dict(r.json())
