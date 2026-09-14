"""Notion Pilot web server — FastAPI app with Notion OAuth and setup endpoint."""

from __future__ import annotations

import asyncio
import json as _json
import os
import pathlib
import secrets
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from notion_pilot.shared.config import Settings
from notion_pilot.shared.utils.notion_urls import page_id_from_url
from notion_pilot.shared.workspace import (
    create_crm_workspace,
    create_inbox_workspace,
    create_workspace_root_page,
    upgrade_crm_home,
)
from web.config import (
    DB_DEFS,
    NOTION_API,
    load_cockpit_cfg,
    notion_headers,
    resolve_db_ids,
    save_cockpit_cfg,
)
from web.notion_db import (
    format_notion_error,
    page_title,
    query_db_status,
)
from web.models import (
    CockpitConfigRequest,
    SetupRequest,
    SetupResponse,
)
from web.oauth import build_authorize_url, exchange_code_for_token_full
from web.utils import (
    extract_title_prop,
    notion_page_url,
)


def _oauth_error_page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Access denied — Notion Pilot</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f5f4ff;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    nav {
      display: flex;
      align-items: center;
      padding: 0 2rem;
      height: 54px;
      background: #fff;
      border-bottom: 1px solid #f0f0f0;
    }
    .logo {
      font-size: 1rem;
      font-weight: 800;
      color: #6e56cf;
      letter-spacing: -0.3px;
    }
    main {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 3rem 1.5rem;
    }
    .card {
      background: #fff;
      border-radius: 16px;
      border: 1px solid #e8e8e8;
      padding: 3rem 2.5rem;
      max-width: 440px;
      width: 100%;
      text-align: center;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 1.25rem;
    }
    .icon {
      width: 56px;
      height: 56px;
      border-radius: 14px;
      background: #f5f4ff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.75rem;
    }
    h1 {
      font-size: 1.4rem;
      font-weight: 800;
      color: #1a1a1a;
    }
    p {
      font-size: 0.9rem;
      color: #666;
      line-height: 1.6;
      max-width: 320px;
    }
    a.btn {
      display: inline-block;
      margin-top: 0.5rem;
      padding: 0.65rem 1.5rem;
      background: #6e56cf;
      color: #fff;
      border-radius: 8px;
      font-size: 0.9rem;
      font-weight: 600;
      text-decoration: none;
      transition: background 0.15s;
    }
    a.btn:hover { background: #5a45b0; }
  </style>
</head>
<body>
  <nav><span class="logo">Notion Pilot</span></nav>
  <main>
    <div class="card">
      <div class="icon">🔒</div>
      <h1>Access denied</h1>
      <p>
        The Notion authorisation was cancelled or the connection was rejected.
        You can try again from the home page.
      </p>
      <a class="btn" href="/">Back to home</a>
    </div>
  </main>
</body>
</html>"""


def _setup_parent_id(req: SetupRequest) -> str | None:
    raw = (req.parent_page_id or "").strip()
    return page_id_from_url(raw) if raw else None


async def _setup_host(
    client: httpx.AsyncClient, req: SetupRequest, parent_id: str | None
) -> tuple[str, str]:
    """Return (page to nest CRM under, CRM page title)."""
    if parent_id:
        return parent_id, req.workspace_name
    return await create_workspace_root_page(client, req.workspace_name), "CRM"


def _setup_notion_error(exc: httpx.HTTPStatusError, parent_id: str | None) -> str:
    body = exc.response.text
    msg = f"Notion API error: {body}"
    if parent_id is None and "workspace" in body.lower():
        msg += " Workspace root needs the public OAuth connection. Pick an existing page instead."
    return msg


_SETUP_SEARCH_PAGES = 50


def _is_workspace_page(page: dict) -> bool:
    if page.get("archived") or page.get("in_trash"):
        return False
    return (page.get("parent") or {}).get("type") == "workspace"


async def _list_parent_pages(client: httpx.AsyncClient) -> list[dict[str, object]]:
    """Sidebar pages only. Notion has no list-root endpoint — Search + parent filter."""
    pages: list[dict[str, object]] = []
    seen: set[str] = set()
    cursor: str | None = None
    for _ in range(_SETUP_SEARCH_PAGES):
        payload: dict = {
            "filter": {"property": "object", "value": "page"},
            "page_size": 100,
        }
        if cursor:
            payload["start_cursor"] = cursor
        r = await client.post(f"{NOTION_API}/search", json=payload)
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            break
        for page in results:
            if not _is_workspace_page(page):
                continue
            pid = str(page["id"])
            if pid in seen:
                continue
            seen.add(pid)
            title = extract_title_prop(page.get("properties") or {}) or "(Untitled)"
            pages.append({"id": pid, "name": title, "root": True})
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor:
            break
    pages.sort(key=lambda p: str(p["name"]).casefold())
    return pages


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Notion Pilot", docs_url=None, redoc_url=None)

    session_secret = (
        settings.web_session_secret.get_secret_value()
        if settings.web_session_secret
        else secrets.token_hex(32)
    )
    # Production: Secure cookie + 1h TTL (D25). Localhost redirect → http cookies for dev/tests.
    _is_prod = "localhost" not in settings.notion_oauth_redirect_uri
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        https_only=_is_prod,
        max_age=3600,
    )

    _CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "media-src 'self'; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "frame-ancestors 'none'"
    )

    class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: object) -> Response:
            response: Response = await call_next(request)  # type: ignore[operator]
            response.headers["Content-Security-Policy"] = _CSP
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            response.headers["X-Frame-Options"] = "DENY"
            fwd = request.headers.get("x-forwarded-proto", "")
            if request.url.scheme == "https" or fwd == "https":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
            path = request.url.path
            if path.startswith(("/assets/", "/film/", "/fonts/")):
                response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
            return response

    app.add_middleware(_SecurityHeadersMiddleware)

    # ── Session helpers ───────────────────────────────────────────────────────

    def _require_token(request: Request) -> str:
        token = request.session.get("notion_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )
        return str(token)

    def _workspace_id(request: Request) -> str:
        """Return workspace_id from session; fall back to 'default' for old sessions."""
        return request.session.get("workspace_id") or "default"

    def _resolve_db_ids(wid: str) -> dict:
        return resolve_db_ids(settings, wid, cockpit_only=True)

    # ── Health ────────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ── OAuth ─────────────────────────────────────────────────────────────────

    @app.get("/auth/notion")
    async def auth_notion(request: Request, next: str = "/") -> RedirectResponse:
        if not settings.notion_oauth_client_id or not settings.web_session_secret:
            raise HTTPException(status_code=500, detail="OAuth not configured")
        state = secrets.token_urlsafe(32)
        request.session["oauth_state"] = state
        request.session["oauth_next"] = next
        url = build_authorize_url(
            client_id=settings.notion_oauth_client_id,
            redirect_uri=settings.notion_oauth_redirect_uri,
            state=state,
        )
        return RedirectResponse(url)

    @app.get("/auth/notion/callback", response_model=None)
    async def auth_notion_callback(
        request: Request,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> RedirectResponse | HTMLResponse:
        if error or not code or not state:
            request.session.pop("oauth_state", None)
            request.session.pop("oauth_next", None)
            return HTMLResponse(_oauth_error_page(), status_code=200)
        if not settings.notion_oauth_client_id or not settings.notion_oauth_client_secret:
            raise HTTPException(status_code=500, detail="OAuth not configured")
        if request.session.get("oauth_state") != state:
            raise HTTPException(status_code=400, detail="Invalid OAuth state")
        try:
            token_data = await exchange_code_for_token_full(
                code=code,
                client_id=settings.notion_oauth_client_id,
                client_secret=settings.notion_oauth_client_secret.get_secret_value(),
                redirect_uri=settings.notion_oauth_redirect_uri,
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=400, detail=f"Notion OAuth error: {exc.response.text}")
        request.session["notion_token"] = token_data["access_token"]
        wid = token_data.get("workspace_id", "default")
        request.session["workspace_id"] = wid
        request.session["workspace_name"] = token_data.get("workspace_name", "My Workspace")
        owner = token_data.get("owner", {})
        if owner.get("type") == "user":
            request.session["user_name"] = owner["user"].get("name", "")
        # Persist workspace_url if not already set (use Notion workspace root as fallback)
        cfg = load_cockpit_cfg(wid)
        if not cfg.get("workspace_url") and token_data.get("workspace_id"):
            cfg.setdefault("workspace_url", "https://notion.so")
            save_cockpit_cfg(wid, cfg)
        request.session.pop("oauth_state", None)
        next_url = request.session.pop("oauth_next", "/")
        return RedirectResponse("/?connected=1" if next_url == "/" else next_url)

    @app.get("/auth/logout")
    async def auth_logout(request: Request) -> RedirectResponse:
        request.session.clear()
        return RedirectResponse("/")

    # ── Setup wizard ──────────────────────────────────────────────────────────

    @app.post("/api/setup")
    async def run_setup(req: SetupRequest, request: Request) -> SetupResponse:
        token = req.notion_token or request.session.get("notion_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not connected to Notion"
            )
        parent_id = _setup_parent_id(req)
        try:
            async with httpx.AsyncClient(headers=notion_headers(token), timeout=60) as client:
                host_id, crm_title = await _setup_host(client, req, parent_id)
                done_id = host_id
                if req.scope in ("crm", "both"):
                    crm = await create_crm_workspace(client, host_id, page_title=crm_title)
                    done_id = crm.crm_page_id
                if req.scope in ("inbox", "both"):
                    await create_inbox_workspace(client, host_id)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=400, detail=_setup_notion_error(exc, parent_id))
        return SetupResponse(notion_page_url=notion_page_url(done_id))

    @app.post("/api/setup/stream")
    async def run_setup_stream(req: SetupRequest, request: Request) -> StreamingResponse:
        token = req.notion_token or request.session.get("notion_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not connected to Notion"
            )

        wid = _workspace_id(request)

        async def _generate() -> AsyncGenerator[str, None]:
            def sse(msg_type: str, **kwargs: object) -> str:
                return f"data: {_json.dumps({'type': msg_type, **kwargs})}\n\n"

            parent_id = _setup_parent_id(req)
            try:
                async with httpx.AsyncClient(headers=notion_headers(token), timeout=120) as client:
                    if parent_id:
                        yield sse("log", message="Creating CRM under your Notion page…")
                    else:
                        yield sse("log", message="Creating workspace root page…")
                    host_id, crm_title = await _setup_host(client, req, parent_id)
                    if not parent_id:
                        yield sse("log", message="✓ Workspace root page created")

                    db_ids: dict[str, str] = {}
                    done_id = host_id
                    crm_page_id = ""
                    crm_views: dict[str, dict[str, str]] = {}

                    if req.scope in ("crm", "both"):
                        yield sse("log", message="Creating CRM page…")
                        yield sse("log", message="  → Companies database")
                        yield sse("log", message="  → People database")
                        yield sse("log", message="  → Leads database")
                        yield sse("log", message="  → Meetings database")
                        yield sse("log", message="  → Activities database")
                        yield sse("log", message="  → Rollups and pipeline formulas")
                        yield sse("log", message="  → Pipeline views on the CRM home")
                        crm = await create_crm_workspace(client, host_id, page_title=crm_title)
                        done_id = crm.crm_page_id
                        db_ids["notion_companies_data_source_id"] = crm.companies_id
                        db_ids["notion_people_data_source_id"] = crm.people_id
                        db_ids["notion_deals_database_id"] = crm.deals_id
                        db_ids["notion_meetings_database_id"] = crm.meetings_id
                        db_ids["notion_activities_database_id"] = crm.activities_id
                        crm_page_id = crm.crm_page_id
                        crm_views = crm.views
                        for warning in crm.warnings:
                            yield sse("warning", message=warning)
                        yield sse("log", message="✓ CRM ready (with demo data)")

                    if req.scope in ("inbox", "both"):
                        yield sse("log", message="Creating Knowledge page…")
                        yield sse("log", message="  → Notions database")
                        yield sse("log", message="  → Ideas database")
                        yield sse("log", message="  → Tools database")
                        yield sse("log", message="  → Data & Technology database")
                        inbox = await create_inbox_workspace(client, host_id)
                        db_ids["notion_notions_database_id"] = inbox.notions_id
                        db_ids["notion_ideas_database_id"] = inbox.ideas_id
                        db_ids["notion_tools_database_id"] = inbox.tools_id
                        db_ids["notion_data_tech_database_id"] = inbox.data_tech_id
                        yield sse("log", message="✓ Knowledge ready (with demo data)")

                    done_url = notion_page_url(done_id)
                    save_cockpit_cfg(
                        wid,
                        {
                            "databases": db_ids,
                            "workspace_url": done_url,
                            "crm_page_id": crm_page_id,
                            "crm_views": crm_views,
                        },
                    )
                    yield sse("log", message="✓ Cockpit configured")
                    yield sse("done", url=done_url)
            except httpx.HTTPStatusError as exc:
                logger.error("setup failed: {} {}", exc.response.status_code, exc.response.text)
                yield sse("error", message=_setup_notion_error(exc, parent_id))
            except Exception as exc:
                logger.error("setup failed: {}", exc)
                yield sse("error", message=str(exc))

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/setup/pages")
    async def setup_pages(request: Request) -> dict:
        token = _require_token(request)
        try:
            async with httpx.AsyncClient(headers=notion_headers(token), timeout=30) as client:
                pages = await _list_parent_pages(client)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Notion search timed out")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=400, detail=f"Notion API error: {exc.response.text}")
        return {"pages": pages}

    # ── Cockpit ───────────────────────────────────────────────────────────────

    @app.get("/api/cockpit/status")
    async def cockpit_status(request: Request) -> dict:
        token = _require_token(request)
        wid = _workspace_id(request)
        db_ids = _resolve_db_ids(wid)
        hdrs = notion_headers(token)

        async def _count_db(client: httpx.AsyncClient, db_id: str | None) -> dict:  # type: ignore[type-arg]
            if not db_id:
                return {"count": None, "configured": False, "notion_name": None}
            try:
                return await query_db_status(client, db_id)
            except Exception as exc:
                logger.warning("status query failed for {}: {}", db_id, exc)
                return {
                    "count": None,
                    "configured": True,
                    "error": format_notion_error(exc),
                    "notion_name": None,
                }

        async with httpx.AsyncClient(headers=hdrs, timeout=15) as client:
            results = await asyncio.gather(
                *[_count_db(client, db_ids.get(d["key"])) for d in DB_DEFS]
            )
        return {
            "databases": [
                {**d, "db_id": db_ids.get(d["key"]), **results[i]} for i, d in enumerate(DB_DEFS)
            ],
            "workspace_name": request.session.get("workspace_name", ""),
            "user_name": request.session.get("user_name", ""),
            "workspace_url": load_cockpit_cfg(wid).get("workspace_url", ""),
            "crm_page_id": load_cockpit_cfg(wid).get("crm_page_id") or None,
        }

    @app.post("/api/crm/refresh")
    async def refresh_crm(request: Request) -> dict:
        """Refresh the CRM home template + views on an already-deployed CRM.

        Unlike /api/setup/stream, this never creates a new CRM — it only
        rewrites Notion Pilot's own blocks and views on the page already
        linked in cockpit config (see upgrade_crm_home).
        """
        token = _require_token(request)
        wid = _workspace_id(request)
        cfg = load_cockpit_cfg(wid)
        crm_page_id = cfg.get("crm_page_id")
        if not crm_page_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No deployed CRM is linked to this workspace yet — deploy one first.",
            )
        try:
            async with httpx.AsyncClient(headers=notion_headers(token), timeout=120) as client:
                result = await upgrade_crm_home(
                    client, crm_page_id, previous_views=cfg.get("crm_views")
                )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=400, detail=format_notion_error(exc))
        cfg["crm_views"] = result.views
        save_cockpit_cfg(wid, cfg)
        return {
            "notion_page_url": notion_page_url(crm_page_id),
            "warnings": result.warnings,
            "views": result.views,
        }

    @app.get("/api/cockpit/status/{key}")
    async def cockpit_status_single(key: str, request: Request) -> dict:
        """Return status for a single database key (used after re-linking to avoid full reload)."""
        token = _require_token(request)
        wid = _workspace_id(request)
        db_ids = _resolve_db_ids(wid)
        hdrs = notion_headers(token)
        defn = next((d for d in DB_DEFS if d["key"] == key), None)
        if not defn:
            raise HTTPException(status_code=404, detail=f"Unknown key: {key}")
        db_id = db_ids.get(key)
        if not db_id:
            return {**defn, "db_id": None, "count": None, "configured": False, "notion_name": None}
        try:
            async with httpx.AsyncClient(headers=hdrs, timeout=30) as client:
                status_data = await query_db_status(client, db_id)
            return {**defn, "db_id": db_id, **status_data}
        except Exception as exc:
            logger.warning("single status query failed for {}: {}", key, exc)
            return {
                **defn,
                "db_id": db_id,
                "count": None,
                "configured": True,
                "error": format_notion_error(exc),
                "notion_name": None,
            }

    @app.get("/api/setup/capabilities")
    async def setup_capabilities(request: Request) -> dict:
        """What placements this token can actually use.

        An internal integration cannot create a workspace-level page at all, so
        the wizard has to require a parent for it. `bot.owner.type` is
        "workspace" for an internal integration and "user" for a
        public-integration OAuth token (which is what build_authorize_url
        requests). Verified for the internal case against the live API.

        Fails soft: if the probe cannot answer, claim top level is available and
        let the deploy surface Notion's own message. A broken probe must never
        block a deploy that would have worked.
        """
        token = _require_token(request)
        try:
            async with httpx.AsyncClient(headers=notion_headers(token), timeout=15) as client:
                r = await client.get(f"{NOTION_API}/users/me")
                r.raise_for_status()
                me = r.json()
        except Exception as exc:  # noqa: BLE001 — degrade, never block
            logger.warning("capabilities probe failed, assuming top level is allowed: {}", exc)
            return {"can_create_top_level": True, "owner_type": None, "workspace_name": ""}

        bot = me.get("bot", {}) or {}
        owner_type = (bot.get("owner", {}) or {}).get("type")
        return {
            "can_create_top_level": owner_type != "workspace",
            "owner_type": owner_type,
            "workspace_name": bot.get("workspace_name", "") or "",
        }

    @app.get("/api/cockpit/notion-pages")
    async def cockpit_notion_pages(request: Request, q: str = "") -> dict:
        """Pages this integration can see, as deploy-parent candidates.

        Deliberately a list rather than a free-text id field: an id the
        integration has no access to fails with Notion's "make sure the relevant
        pages are shared" 404, which is this product's most confusing error.
        Offering only reachable pages makes it unreachable.

        Bounded by *requests*, not by results. /v1/search returns pages and
        database rows together, and this filters the rows out — so on a real CRM
        (1,200 companies, 1,800 people) an unbounded walk pages through
        thousands of records to collect a handful of container pages. Measured:
        45s. One search call is 0.8s, hence the cap plus the `q` passthrough so
        the user can narrow instead of waiting.
        """
        token = _require_token(request)
        max_requests = 3
        pages: list[dict] = []
        cursor: str | None = None
        truncated = False

        async with httpx.AsyncClient(headers=notion_headers(token), timeout=25) as client:
            for attempt in range(max_requests):
                payload: dict = {
                    "filter": {"property": "object", "value": "page"},
                    "sort": {"direction": "descending", "timestamp": "last_edited_time"},
                    "page_size": 100,
                }
                if q.strip():
                    payload["query"] = q.strip()
                if cursor:
                    payload["start_cursor"] = cursor
                r = await client.post(f"{NOTION_API}/search", json=payload)
                r.raise_for_status()
                data = r.json()
                for page in data.get("results", []):
                    # Rows inside a database are records, not containers.
                    if (page.get("parent", {}) or {}).get("type") == "database_id":
                        continue
                    pages.append({"id": page["id"], "name": page_title(page)})
                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")
                if attempt == max_requests - 1:
                    truncated = True

        seen: set[str] = set()
        unique = [p for p in pages if not (p["id"] in seen or seen.add(p["id"]))]
        return {"pages": unique, "truncated": truncated}

    @app.get("/api/cockpit/notion-databases")
    async def cockpit_notion_databases(request: Request) -> dict:
        token = _require_token(request)
        databases, cursor = [], None
        async with httpx.AsyncClient(headers=notion_headers(token), timeout=20) as client:
            while True:
                payload: dict = {
                    "filter": {"property": "object", "value": "database"},
                    "sort": {"direction": "ascending", "timestamp": "last_edited_time"},
                    "page_size": 100,
                }
                if cursor:
                    payload["start_cursor"] = cursor
                r = await client.post(f"{NOTION_API}/search", json=payload)
                r.raise_for_status()
                data = r.json()
                for db in data.get("results", []):
                    name = (
                        "".join(t.get("plain_text", "") for t in db.get("title", []))
                        or "(Untitled)"
                    )
                    databases.append({"id": db["id"], "name": name})
                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")
        databases.sort(key=lambda d: d["name"].lower())
        return {"databases": databases}

    @app.get("/api/cockpit/config")
    async def cockpit_get_config(request: Request) -> dict:
        _require_token(request)
        return {
            "databases": _resolve_db_ids(_workspace_id(request)),
            "definitions": DB_DEFS,
        }

    @app.post("/api/cockpit/config")
    async def cockpit_save_config(req: CockpitConfigRequest, request: Request) -> dict:
        _require_token(request)
        wid = _workspace_id(request)
        cfg = load_cockpit_cfg(wid)
        cfg["databases"] = {k: v for k, v in req.databases.items() if v}
        if req.workspace_url:
            cfg["workspace_url"] = req.workspace_url
        save_cockpit_cfg(wid, cfg)
        return {"ok": True}

    @app.delete("/api/workspace", response_model=None)
    async def delete_workspace(request: Request) -> dict:
        """Clear cockpit config (DB links + workspace_url) for this workspace."""
        _require_token(request)
        wid = _workspace_id(request)
        save_cockpit_cfg(wid, {"databases": {}, "workspace_url": ""})
        return {"ok": True}

    # ── Static files + SPA ───────────────────────────────────────────────────

    _static = pathlib.Path(__file__).parent / "static"
    if _static.exists():
        _static_root = _static.resolve()
        # Vite bundles assets to /assets/ — mount before the catch-all
        _assets_dir = _static / "assets"
        if _assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

        # Landing page homepage films (Landing.tsx's <Film> references /film/<slug>.mp4
        # and .jpg directly, not /static/film/... — mount to match, or they 404 through
        # to the SPA catch-all below and the <video> silently shows nothing).
        _film_dir = _static / "film"
        if _film_dir.exists():
            app.mount("/film", StaticFiles(directory=str(_film_dir)), name="film")

        _fonts_dir = _static / "fonts"
        if _fonts_dir.exists():
            app.mount("/fonts", StaticFiles(directory=str(_fonts_dir)), name="fonts")

        app.mount("/static", StaticFiles(directory=str(_static)), name="static")

        def _serve_spa() -> HTMLResponse:
            index = _static / "index.html"
            if not index.exists():
                return HTMLResponse(
                    "<h1>Frontend not built</h1><p>Run <code>make build-frontend</code></p>",
                    status_code=503,
                )
            return HTMLResponse(
                index.read_text(),
                headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
            )

        def _serve_static_file(rel: str) -> FileResponse | None:
            candidate = (_static / rel).resolve()
            try:
                candidate.relative_to(_static_root)
            except ValueError:
                return None
            if not candidate.is_file():
                return None
            return FileResponse(
                candidate,
                headers={"Cache-Control": "public, max-age=3600"},
            )

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:
            return _serve_spa()

        @app.get("/robots.txt", include_in_schema=False, response_model=None)
        async def robots_txt() -> FileResponse | HTMLResponse:
            return _serve_static_file("robots.txt") or HTMLResponse(
                "User-agent: *\nDisallow:\n", media_type="text/plain"
            )

        @app.get("/sitemap.xml", include_in_schema=False, response_model=None)
        async def sitemap_xml() -> FileResponse | HTMLResponse:
            file = _serve_static_file("sitemap.xml")
            if file is None:
                raise HTTPException(status_code=404, detail="sitemap missing")
            return file

        @app.get("/og-image.jpg", include_in_schema=False, response_model=None)
        async def og_image() -> FileResponse:
            file = _serve_static_file("og-image.jpg")
            if file is None:
                raise HTTPException(status_code=404, detail="og image missing")
            return file

        @app.get("/cockpit", response_class=HTMLResponse, response_model=None)
        async def cockpit_page(request: Request) -> HTMLResponse | RedirectResponse:
            if not request.session.get("notion_token"):
                return RedirectResponse("/auth/notion?next=/cockpit")
            return _serve_spa()

        # SPA catch-all: any non-API, non-auth, non-asset path → index.html
        @app.get(
            "/{full_path:path}",
            response_class=HTMLResponse,
            include_in_schema=False,
            response_model=None,
        )
        async def spa_fallback(full_path: str) -> HTMLResponse | FileResponse:
            root = full_path.split("/", 1)[0]
            if root in {"api", "auth", "mcp"}:
                raise HTTPException(status_code=404, detail="Not found")
            if ".." not in full_path:
                file = _serve_static_file(full_path)
                if file is not None:
                    return file
            return _serve_spa()

    return app


def app_factory() -> FastAPI:
    """Factory for uvicorn --factory mode."""
    from notion_pilot.shared.config import load_settings

    return create_app(load_settings())
