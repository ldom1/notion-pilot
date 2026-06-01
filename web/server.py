"""Notion Pilot web server — FastAPI app with Notion OAuth and setup endpoint."""

from __future__ import annotations

import json as _json
import pathlib
import secrets
from typing import AsyncGenerator, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from notion_pilot.shared.config import Settings
from notion_pilot.shared.workspace import (
    create_crm_workspace,
    create_inbox_workspace,
    create_workspace_root_page,
)
from web.oauth import build_authorize_url, exchange_code_for_token

_NOTION_VERSION = "2022-06-28"


class SetupRequest(BaseModel):
    scope: Literal["crm", "inbox", "both"]
    workspace_name: str
    notion_token: str | None = None


class SetupResponse(BaseModel):
    notion_page_url: str


def _notion_page_url(page_id: str) -> str:
    return f"https://notion.so/{page_id.replace('-', '')}"


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Notion Pilot", docs_url=None, redoc_url=None)

    session_secret = (
        settings.web_session_secret.get_secret_value()
        if settings.web_session_secret
        else secrets.token_hex(32)
    )
    app.add_middleware(SessionMiddleware, secret_key=session_secret, https_only=False)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/auth/notion")
    async def auth_notion(request: Request) -> RedirectResponse:
        if not settings.notion_oauth_client_id or not settings.web_session_secret:
            raise HTTPException(status_code=500, detail="OAuth not configured")
        state = secrets.token_urlsafe(32)
        request.session["oauth_state"] = state
        url = build_authorize_url(
            client_id=settings.notion_oauth_client_id,
            redirect_uri=settings.notion_oauth_redirect_uri,
            state=state,
        )
        return RedirectResponse(url)

    @app.get("/auth/notion/callback")
    async def auth_notion_callback(request: Request, code: str, state: str) -> RedirectResponse:
        if not settings.notion_oauth_client_id or not settings.notion_oauth_client_secret:
            raise HTTPException(status_code=500, detail="OAuth not configured")
        stored_state = request.session.get("oauth_state")
        if not stored_state or stored_state != state:
            raise HTTPException(status_code=400, detail="Invalid OAuth state")
        try:
            token = await exchange_code_for_token(
                code=code,
                client_id=settings.notion_oauth_client_id,
                client_secret=settings.notion_oauth_client_secret.get_secret_value(),
                redirect_uri=settings.notion_oauth_redirect_uri,
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=400, detail=f"Notion OAuth error: {exc.response.text}")
        request.session["notion_token"] = token
        request.session.pop("oauth_state", None)
        return RedirectResponse("/?connected=1")

    @app.post("/api/setup")
    async def run_setup(req: SetupRequest, request: Request) -> SetupResponse:
        token = req.notion_token or request.session.get("notion_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not connected to Notion. Please authorize via /auth/notion first.",
            )
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(headers=headers, timeout=60) as client:
                root_page_id = await create_workspace_root_page(client, req.workspace_name)
                if req.scope in ("crm", "both"):
                    await create_crm_workspace(client, root_page_id)
                if req.scope in ("inbox", "both"):
                    await create_inbox_workspace(client, root_page_id)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Notion API error {exc.response.status_code}: {exc.response.text}",
            )
        return SetupResponse(notion_page_url=_notion_page_url(root_page_id))

    @app.post("/api/setup/stream")
    async def run_setup_stream(req: SetupRequest, request: Request) -> StreamingResponse:
        token = req.notion_token or request.session.get("notion_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not connected to Notion. Please authorize via /auth/notion first.",
            )
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

        async def _generate() -> AsyncGenerator[str, None]:
            def sse(msg_type: str, **kwargs: object) -> str:
                return f"data: {_json.dumps({'type': msg_type, **kwargs})}\n\n"

            try:
                async with httpx.AsyncClient(headers=headers, timeout=120) as client:
                    yield sse("log", message="Creating root page…")
                    root_page_id = await create_workspace_root_page(client, req.workspace_name)
                    yield sse("log", message="✓ Root page created")

                    if req.scope in ("crm", "both"):
                        yield sse("log", message="Creating CRM page…")
                        yield sse("log", message="  → Companies database")
                        yield sse("log", message="  → People database")
                        yield sse("log", message="  → Deals database")
                        await create_crm_workspace(client, root_page_id)
                        yield sse("log", message="✓ CRM ready (with demo data)")

                    if req.scope in ("inbox", "both"):
                        yield sse("log", message="Creating Knowledge page…")
                        yield sse("log", message="  → Notions database")
                        yield sse("log", message="  → Ideas database")
                        yield sse("log", message="  → Tools database")
                        yield sse("log", message="  → Data & Technology database")
                        await create_inbox_workspace(client, root_page_id)
                        yield sse("log", message="✓ Knowledge ready (with demo data)")

                    yield sse("done", url=_notion_page_url(root_page_id))
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "workspace setup failed: {} {}", exc.response.status_code, exc.response.text
                )
                yield sse("error", message=f"Notion API error: {exc.response.text}")
            except Exception as exc:
                logger.error("workspace setup failed: {}", exc)
                yield sse("error", message=str(exc))

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    _static = pathlib.Path(__file__).parent / "static"
    if _static.exists():
        app.mount("/static", StaticFiles(directory=str(_static)), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:
            return HTMLResponse((_static / "index.html").read_text())

    return app


def app_factory() -> FastAPI:
    """Factory for uvicorn --factory mode."""
    from notion_pilot.shared.config import load_settings

    return create_app(load_settings())
