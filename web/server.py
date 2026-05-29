"""Notion Pilot web server — FastAPI app with JWT auth and setup endpoint."""

import pathlib
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from notion_pilot.shared.config import Settings
from notion_pilot.shared.utils.notion_urls import page_id_from_url
from notion_pilot.shared.workspace import create_crm_workspace, create_inbox_workspace
from web.auth import create_access_token, verify_token

_NOTION_VERSION = "2026-03-11"
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class SetupRequest(BaseModel):
    scope: Literal["crm", "inbox", "both"]
    parent_page: str
    notion_token: str | None = None


class SetupResponse(BaseModel):
    NOTION_DATABASE_ID: str | None = None
    NOTION_IDEAS_DATABASE_ID: str | None = None
    NOTION_TOOLS_DATABASE_ID: str | None = None
    NOTION_DATA_TECH_DATABASE_ID: str | None = None
    NOTION_COMPANIES_DATA_SOURCE_ID: str | None = None
    NOTION_PEOPLE_DATA_SOURCE_ID: str | None = None
    NOTION_DEALS_DATABASE_ID: str | None = None


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Notion Pilot Setup", docs_url=None, redoc_url=None)

    def _verify_token_dep(token: Annotated[str, Depends(_oauth2_scheme)]) -> str:
        secret = settings.web_secret_key
        if not secret:
            raise HTTPException(status_code=500, detail="Web secret key not configured")
        try:
            verify_token(token, secret_key=secret.get_secret_value())
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/auth/token")
    async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, str]:
        if not settings.web_admin_password or not settings.web_secret_key:
            raise HTTPException(status_code=500, detail="Web auth not configured")
        if (
            form.username != settings.web_admin_username
            or form.password != settings.web_admin_password.get_secret_value()
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = create_access_token(
            {"sub": form.username},
            secret_key=settings.web_secret_key.get_secret_value(),
            expire_minutes=settings.web_token_expire_minutes,
        )
        return {"access_token": token, "token_type": "bearer"}

    @app.post("/api/setup")
    async def run_setup(
        req: SetupRequest,
        _token: Annotated[str, Depends(_verify_token_dep)],
    ) -> SetupResponse:
        token = req.notion_token or (
            settings.notion_token.get_secret_value() if settings.notion_token else None
        )
        if not token:
            raise HTTPException(status_code=400, detail="Notion token required")

        try:
            parent_id = page_id_from_url(req.parent_page)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid parent page ID or URL")

        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }
        result = SetupResponse()
        try:
            async with httpx.AsyncClient(headers=headers, timeout=60) as client:
                if req.scope in ("crm", "both"):
                    crm = await create_crm_workspace(client, parent_id)
                    result.NOTION_COMPANIES_DATA_SOURCE_ID = crm.companies_id
                    result.NOTION_PEOPLE_DATA_SOURCE_ID = crm.people_id
                    result.NOTION_DEALS_DATABASE_ID = crm.deals_id
                if req.scope in ("inbox", "both"):
                    inbox = await create_inbox_workspace(client, parent_id)
                    result.NOTION_DATABASE_ID = inbox.notions_id
                    result.NOTION_IDEAS_DATABASE_ID = inbox.ideas_id
                    result.NOTION_TOOLS_DATABASE_ID = inbox.tools_id
                    result.NOTION_DATA_TECH_DATABASE_ID = inbox.data_tech_id
        except httpx.HTTPStatusError as exc:
            notion_msg = exc.response.text
            raise HTTPException(
                status_code=400,
                detail=f"Notion API error {exc.response.status_code}: {notion_msg}",
            )
        return result

    # Mount static files if directory exists
    _static = pathlib.Path(__file__).parent / "static"
    if _static.exists():
        app.mount("/static", StaticFiles(directory=str(_static)), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:
            return HTMLResponse((_static / "index.html").read_text())

    return app


def app_factory() -> FastAPI:
    """Factory for uvicorn --factory mode. Avoids import-time load_settings() call."""
    from notion_pilot.shared.config import load_settings

    return create_app(load_settings())
