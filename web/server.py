"""Notion Pilot web server — FastAPI app with Notion OAuth and setup endpoint."""

from __future__ import annotations

import asyncio
import datetime
import json as _json
import os
import pathlib
import re
import secrets
import sys
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.middleware.sessions import SessionMiddleware

from notion_pilot.shared.config import Settings
from notion_pilot.shared.llm.crm_chat import chat_crm, detect_data_source
from notion_pilot.shared.workspace import (
    create_crm_workspace,
    create_inbox_workspace,
    create_workspace_root_page,
)
from web.config import (
    DB_DEFS,
    NOTION_API,
    delete_conversation,
    list_conversations,
    load_cockpit_cfg,
    load_conversation,
    load_memory,
    load_workflows,
    notion_headers,
    resolve_db_ids,
    save_cockpit_cfg,
    save_conversation,
    save_memory,
    save_workflows,
)
from web.models import (
    ChatRequest,
    CockpitConfigRequest,
    CreateDealRequest,
    CreateLeadRequest,
    RunScriptRequest,
    RunWorkflowRequest,
    SaveWorkflowRequest,
    SetupRequest,
    SetupResponse,
    UpdateMemoryRequest,
)
from web.oauth import build_authorize_url, exchange_code_for_token_full
from web.utils import (
    extract_text_prop,
    extract_title_prop,
    load_scripts,
    notion_page_url,
)


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Notion Pilot", docs_url=None, redoc_url=None)

    session_secret = (
        settings.web_session_secret.get_secret_value()
        if settings.web_session_secret
        else secrets.token_hex(32)
    )
    app.add_middleware(SessionMiddleware, secret_key=session_secret, https_only=False)

    # ── Session helpers ───────────────────────────────────────────────────────

    def _require_token(request: Request) -> str:
        token = request.session.get("notion_token")
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        return str(token)

    def _workspace_id(request: Request) -> str:
        """Return workspace_id from session; fall back to 'default' for old sessions."""
        return request.session.get("workspace_id") or "default"

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

    @app.get("/auth/notion/callback")
    async def auth_notion_callback(request: Request, code: str, state: str) -> RedirectResponse:
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
        request.session["workspace_id"] = token_data.get("workspace_id", "default")
        request.session["workspace_name"] = token_data.get("workspace_name", "My Workspace")
        owner = token_data.get("owner", {})
        if owner.get("type") == "user":
            request.session["user_name"] = owner["user"].get("name", "")
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
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not connected to Notion")
        try:
            async with httpx.AsyncClient(headers=notion_headers(token), timeout=60) as client:
                root_page_id = await create_workspace_root_page(client, req.workspace_name)
                if req.scope in ("crm", "both"):
                    await create_crm_workspace(client, root_page_id)
                if req.scope in ("inbox", "both"):
                    await create_inbox_workspace(client, root_page_id)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=400, detail=f"Notion API error: {exc.response.text}")
        return SetupResponse(notion_page_url=notion_page_url(root_page_id))

    @app.post("/api/setup/stream")
    async def run_setup_stream(req: SetupRequest, request: Request) -> StreamingResponse:
        token = req.notion_token or request.session.get("notion_token")
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not connected to Notion")

        async def _generate() -> AsyncGenerator[str, None]:
            def sse(msg_type: str, **kwargs: object) -> str:
                return f"data: {_json.dumps({'type': msg_type, **kwargs})}\n\n"

            try:
                async with httpx.AsyncClient(headers=notion_headers(token), timeout=120) as client:
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
                    yield sse("done", url=notion_page_url(root_page_id))
            except httpx.HTTPStatusError as exc:
                logger.error("setup failed: {} {}", exc.response.status_code, exc.response.text)
                yield sse("error", message=f"Notion API error: {exc.response.text}")
            except Exception as exc:
                logger.error("setup failed: {}", exc)
                yield sse("error", message=str(exc))

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Cockpit ───────────────────────────────────────────────────────────────

    @app.get("/api/cockpit/status")
    async def cockpit_status(request: Request) -> dict:
        token = _require_token(request)
        wid = _workspace_id(request)
        db_ids = resolve_db_ids(settings, wid)
        hdrs = notion_headers(token)

        async def _count_db(db_id: str | None) -> dict:
            if not db_id:
                return {"count": None, "configured": False, "notion_name": None}
            try:
                async with httpx.AsyncClient(headers=hdrs, timeout=15) as client:
                    db_r, q_r = await asyncio.gather(
                        client.get(f"{NOTION_API}/databases/{db_id}"),
                        client.post(f"{NOTION_API}/databases/{db_id}/query", json={"page_size": 100}),
                    )
                    db_r.raise_for_status()
                    q_r.raise_for_status()
                    title_parts = db_r.json().get("title", [])
                    notion_name = "".join(t.get("plain_text", "") for t in title_parts) or None
                    data = q_r.json()
                    return {
                        "count": len(data.get("results", [])),
                        "has_more": data.get("has_more", False),
                        "configured": True,
                        "notion_name": notion_name,
                    }
            except Exception as exc:
                logger.warning("status query failed for {}: {}", db_id, exc)
                return {"count": None, "configured": True, "error": str(exc), "notion_name": None}

        results = await asyncio.gather(*[_count_db(db_ids.get(d["key"])) for d in DB_DEFS])
        return {
            "databases": [{**d, "db_id": db_ids.get(d["key"]), **results[i]} for i, d in enumerate(DB_DEFS)],
            "workspace_name": request.session.get("workspace_name", ""),
            "user_name": request.session.get("user_name", ""),
            "workspace_url": load_cockpit_cfg(wid).get("workspace_url", ""),
        }

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
                    name = "".join(t.get("plain_text", "") for t in db.get("title", [])) or "(Untitled)"
                    databases.append({"id": db["id"], "name": name})
                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")
        databases.sort(key=lambda d: d["name"].lower())
        return {"databases": databases}

    @app.get("/api/cockpit/config")
    async def cockpit_get_config(request: Request) -> dict:
        _require_token(request)
        return {"databases": resolve_db_ids(settings, _workspace_id(request)), "definitions": DB_DEFS}

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

    @app.get("/api/cockpit/scripts")
    async def cockpit_scripts(request: Request) -> dict:
        _require_token(request)
        return {"scripts": load_scripts()}

    # Tracks running subprocesses by script_id; cleared on finish or stop
    _running_procs: dict[str, asyncio.subprocess.Process] = {}

    @app.post("/api/cockpit/run-script")
    async def cockpit_run_script(req: RunScriptRequest, request: Request) -> StreamingResponse:
        token = _require_token(request)
        wid = _workspace_id(request)
        scripts = load_scripts()
        script = next((s for s in scripts if s["id"] == req.script_id), None)
        if not script:
            raise HTTPException(status_code=404, detail=f"Script '{req.script_id}' not found")
        repo_root = pathlib.Path(__file__).parent.parent
        script_path = repo_root / script["path"]
        if not script_path.exists():
            raise HTTPException(status_code=404, detail=f"Script file not found: {script['path']}")

        env = os.environ.copy()
        env["NOTION_TOKEN"] = token
        for k, v in resolve_db_ids(settings, wid).items():
            if v:
                env[k.upper()] = v

        cmd = [sys.executable, str(script_path)] + list(script.get("args") or [])

        async def _generate() -> AsyncGenerator[str, None]:
            def sse(msg_type: str, **kwargs: object) -> str:
                return f"data: {_json.dumps({'type': msg_type, **kwargs})}\n\n"

            display = f"$ python {script['path']}" + (
                " " + " ".join(script.get("args") or []) if script.get("args") else ""
            )
            yield sse("log", message=display)
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    env=env,
                    cwd=str(repo_root),
                )
                _running_procs[req.script_id] = proc
                assert proc.stdout is not None
                while line := await proc.stdout.readline():
                    yield sse("log", message=line.decode().rstrip())
                await proc.wait()
                if proc.returncode == 0:
                    yield sse("done", message="Completed successfully")
                else:
                    yield sse("error", message=f"Exited with code {proc.returncode}")
            except Exception as exc:
                logger.error("script run failed: {}", exc)
                yield sse("error", message=str(exc))
            finally:
                _running_procs.pop(req.script_id, None)

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/cockpit/stop-script")
    async def cockpit_stop_script(req: RunScriptRequest, request: Request) -> dict:
        _require_token(request)
        proc = _running_procs.get(req.script_id)
        if not proc:
            raise HTTPException(status_code=404, detail=f"'{req.script_id}' is not running")
        proc.kill()
        return {"ok": True}

    @app.post("/api/cockpit/chat")
    async def cockpit_chat(req: ChatRequest, request: Request) -> StreamingResponse:
        token = _require_token(request)
        wid = _workspace_id(request)
        db_ids = resolve_db_ids(settings, wid)
        workspace_memory = load_memory(wid)

        # Validate session_id — must be safe for use as a filename
        sid = req.session_id
        if sid and not re.match(r'^[a-zA-Z0-9_-]{1,64}$', sid):
            sid = None

        # Decide which Notion DB(s) to query based on query intent
        data_source = detect_data_source(req.query)

        # Load session cache — reuse fetched data for follow-ups
        existing_session = load_conversation(wid, sid) if sid else None
        cached_people: list[dict] | None = existing_session.get("people_cache") if existing_session else None
        cached_companies: list[dict] | None = existing_session.get("companies_cache") if existing_session else None

        need_people = data_source in ("people", "both") and cached_people is None
        need_companies = data_source in ("companies", "both") and cached_companies is None
        # On follow-ups, skip fetch if we already have the right cache
        if req.history:
            need_people = need_people and cached_people is None
            need_companies = need_companies and cached_companies is None

        async def _fetch_all_pages(client: httpx.AsyncClient, db_id: str) -> list[dict]:
            rows: list[dict] = []
            cursor: str | None = None
            while True:
                body: dict = {"page_size": 100}
                if cursor:
                    body["start_cursor"] = cursor
                r = await client.post(f"{NOTION_API}/databases/{db_id}/query", json=body)
                r.raise_for_status()
                data = r.json()
                rows.extend(data.get("results", []))
                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")
            return rows

        async def _generate() -> AsyncGenerator[str, None]:
            def sse(msg_type: str, **kwargs: object) -> str:
                return f"data: {_json.dumps({'type': msg_type, **kwargs})}\n\n"

            people: list[dict] = list(cached_people or [])
            companies: list[dict] = list(cached_companies or [])

            if need_people or need_companies:
                yield sse("status", message="Searching your CRM…")
                async with httpx.AsyncClient(headers=notion_headers(token), timeout=60) as client:
                    if need_people:
                        people_db_id = db_ids.get("notion_people_data_source_id")
                        if people_db_id:
                            try:
                                for row in await _fetch_all_pages(client, people_db_id):
                                    props = row.get("properties", {})
                                    people.append({
                                        "id": row["id"],
                                        "name": extract_title_prop(props),
                                        "position": extract_text_prop(props, "Position"),
                                        "company": extract_text_prop(props, "Company"),
                                    })
                            except Exception as exc:
                                logger.warning("people fetch failed: {}", exc)

                    if need_companies:
                        co_db_id = db_ids.get("notion_companies_data_source_id")
                        if co_db_id:
                            try:
                                for row in await _fetch_all_pages(client, co_db_id):
                                    props = row.get("properties", {})
                                    sector = ""
                                    if props.get("Sector", {}).get("select"):
                                        sector = props["Sector"]["select"]["name"]
                                    companies.append({
                                        "id": row["id"],
                                        "name": extract_title_prop(props),
                                        "sector": sector,
                                    })
                            except Exception as exc:
                                logger.warning("companies fetch failed: {}", exc)

                parts = []
                if people:
                    parts.append(f"{len(people)} contacts")
                if companies:
                    parts.append(f"{len(companies)} companies")
                yield sse("status", message=f"Found {', '.join(parts) or 'nothing'}, analysing…")

            history = [{"role": m.role, "content": m.content} for m in req.history]
            try:
                result = await chat_crm(
                    settings, req.query, history,
                    people=people,
                    companies=companies if companies else None,
                    workspace_memory=workspace_memory,
                )
            except ValueError as exc:
                yield sse("error", message=str(exc))
                return
            except httpx.HTTPStatusError as exc:
                logger.warning("chat_crm LLM error: {}", exc.response.text[:300])
                yield sse("error", message=f"LLM API error: {exc.response.text[:200]}")
                return
            except Exception as exc:
                logger.warning("chat_crm failed: {}", exc)
                yield sse("error", message="LLM returned an unreadable response. Try again.")
                return

            # "create" intent is handled client-side via the deal wizard (which fetches
            # Deals DB schema and prompts the user before calling /api/cockpit/create-deal).
            yield sse("result", data=result)

            # Persist conversation server-side
            if sid:
                try:
                    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    session = existing_session or {
                        "id": sid,
                        "title": req.query[:60] + ("…" if len(req.query) > 60 else ""),
                        "created_at": now,
                        "messages": [],
                        "history": [],
                    }
                    if need_people and people:
                        session["people_cache"] = people
                    if need_companies and companies:
                        session["companies_cache"] = companies
                    session["updated_at"] = now
                    session["messages"].append({"role": "user", "content": req.query, "ts": now})
                    assistant_msg = result.get("message", "")
                    session["messages"].append({"role": "assistant", "content": assistant_msg, "data": result, "ts": now})
                    session["history"] = [
                        {"role": m["role"], "content": m["content"]}
                        for m in session["messages"]
                    ]
                    save_conversation(wid, session)
                except Exception as exc:
                    logger.warning("conversation save failed: {}", exc)

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Conversations ────────────────────────────────────────────────────────

    @app.get("/api/cockpit/conversations")
    async def cockpit_list_conversations(request: Request) -> dict:
        _require_token(request)
        wid = _workspace_id(request)
        return {"conversations": list_conversations(wid)}

    @app.get("/api/cockpit/conversations/{session_id}")
    async def cockpit_get_conversation(session_id: str, request: Request) -> dict:
        _require_token(request)
        if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', session_id):
            raise HTTPException(status_code=400, detail="Invalid session_id")
        wid = _workspace_id(request)
        session = load_conversation(wid, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"session": session}

    @app.delete("/api/cockpit/conversations/{session_id}")
    async def cockpit_delete_conversation(session_id: str, request: Request) -> dict:
        _require_token(request)
        if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', session_id):
            raise HTTPException(status_code=400, detail="Invalid session_id")
        wid = _workspace_id(request)
        if not delete_conversation(wid, session_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"ok": True}

    # ── Workspace memory ─────────────────────────────────────────────────────

    @app.get("/api/cockpit/memory")
    async def cockpit_get_memory(request: Request) -> dict:
        _require_token(request)
        wid = _workspace_id(request)
        return {"text": load_memory(wid)}

    @app.put("/api/cockpit/memory")
    async def cockpit_save_memory(req: UpdateMemoryRequest, request: Request) -> dict:
        _require_token(request)
        wid = _workspace_id(request)
        save_memory(wid, req.text.strip())
        return {"ok": True}

    @app.get("/api/cockpit/deals-properties")
    async def cockpit_deals_properties(request: Request) -> dict:
        """Return wizard-relevant properties of the Deals database (select/multi_select with options)."""
        token = _require_token(request)
        wid = _workspace_id(request)
        deals_db_id = resolve_db_ids(settings, wid).get("notion_deals_database_id")
        if not deals_db_id:
            raise HTTPException(status_code=400, detail="Deals database not configured")
        async with httpx.AsyncClient(headers=notion_headers(token), timeout=15) as client:
            r = await client.get(f"{NOTION_API}/databases/{deals_db_id}")
            r.raise_for_status()
        props = r.json().get("properties", {})
        wizard_fields = []
        skip = {"Name", "Client", "Contacts"}  # handled implicitly
        for name, cfg in props.items():
            if name in skip:
                continue
            ptype = cfg.get("type")
            if ptype == "select":
                options = [o["name"] for o in cfg["select"].get("options", [])]
                wizard_fields.append({"key": name, "type": "select", "options": options})
            elif ptype == "multi_select":
                options = [o["name"] for o in cfg["multi_select"].get("options", [])]
                wizard_fields.append({"key": name, "type": "multi_select", "options": options})
            elif ptype == "rich_text":
                wizard_fields.append({"key": name, "type": "text"})
            elif ptype == "number":
                wizard_fields.append({"key": name, "type": "number"})
        return {"fields": wizard_fields}

    @app.post("/api/cockpit/create-deal")
    async def cockpit_create_deal(req: CreateDealRequest, request: Request) -> dict:
        """Create a single Deal entry with wizard-collected properties."""
        token = _require_token(request)
        wid = _workspace_id(request)
        db_ids = resolve_db_ids(settings, wid)
        deals_db_id = db_ids.get("notion_deals_database_id")
        if not deals_db_id:
            raise HTTPException(status_code=400, detail="Deals database not configured")

        hdrs = notion_headers(token)
        contact_id: str | None = req.notion_id

        async with httpx.AsyncClient(headers=hdrs, timeout=20) as client:
            if not contact_id and req.new_person:
                people_db_id = db_ids.get("notion_people_data_source_id")
                if not people_db_id:
                    raise HTTPException(status_code=400, detail="People database not configured")
                person_props: dict = {
                    "Nom": {"title": [{"text": {"content": req.new_person.name}}]},
                }
                if req.new_person.position:
                    person_props["Position"] = {"rich_text": [{"text": {"content": req.new_person.position}}]}
                p_r = await client.post(f"{NOTION_API}/pages", json={
                    "parent": {"database_id": people_db_id},
                    "properties": person_props,
                })
                p_r.raise_for_status()
                contact_id = p_r.json()["id"]

            deal_props: dict = {
                "Name": {"title": [{"text": {"content": req.deal_name}}]},
                "Stage": {"select": {"name": "Prospect"}},
            }
            if contact_id:
                deal_props["Contacts"] = {"relation": [{"id": contact_id}]}
            # Merge extra fields from wizard answers
            for key, val in (req.extra_fields or {}).items():
                if isinstance(val, list):
                    deal_props[key] = {"multi_select": [{"name": v} for v in val]}
                elif isinstance(val, (int, float)):
                    deal_props[key] = {"number": val}
                elif val:
                    # select or text
                    if key in {"Stage", "Type"}:
                        deal_props[key] = {"select": {"name": val}}
                    else:
                        deal_props[key] = {"rich_text": [{"text": {"content": str(val)}}]}

            logger.info("create-deal: posting to DB {} props={}", deals_db_id, list(deal_props.keys()))
            d_r = await client.post(f"{NOTION_API}/pages", json={
                "parent": {"database_id": deals_db_id},
                "properties": deal_props,
            })
            if not d_r.is_success:
                logger.error("create-deal Notion error {}: {}", d_r.status_code, d_r.text[:400])
                raise HTTPException(status_code=400, detail=f"Notion API error: {d_r.text[:200]}")
            page_id = d_r.json()["id"]
            logger.info("create-deal: created page_id={}", page_id)

        return {"page_id": page_id, "url": notion_page_url(page_id)}

    @app.post("/api/cockpit/create-lead")
    async def cockpit_create_lead(req: CreateLeadRequest, request: Request) -> dict:
        token = _require_token(request)
        wid = _workspace_id(request)
        people_db_id = resolve_db_ids(settings, wid).get("notion_people_data_source_id")
        if not people_db_id:
            raise HTTPException(status_code=400, detail="People database not configured")
        props: dict = {"Nom": {"title": [{"text": {"content": req.name}}]}}
        if req.position:
            props["Position"] = {"rich_text": [{"text": {"content": req.position}}]}
        async with httpx.AsyncClient(headers=notion_headers(token), timeout=20) as client:
            r = await client.post(
                f"{NOTION_API}/pages",
                json={"parent": {"database_id": people_db_id}, "properties": props},
            )
            r.raise_for_status()
            page_id = r.json()["id"]
        return {"page_id": page_id, "url": notion_page_url(page_id)}

    # ── Workflows ─────────────────────────────────────────────────────────────

    @app.get("/api/cockpit/workflows")
    async def cockpit_get_workflows(request: Request) -> dict:
        _require_token(request)
        return {"workflows": load_workflows(_workspace_id(request))}

    @app.post("/api/cockpit/workflows")
    async def cockpit_save_workflow(req: SaveWorkflowRequest, request: Request) -> dict:
        _require_token(request)
        wid = _workspace_id(request)
        wfs = load_workflows(wid)
        # Upsert by id
        wfs = [w for w in wfs if w.get("id") != req.workflow.id]
        wfs.append(req.workflow.model_dump())
        save_workflows(wid, wfs)
        return {"ok": True, "workflow_id": req.workflow.id}

    @app.delete("/api/cockpit/workflows/{workflow_id}")
    async def cockpit_delete_workflow(workflow_id: str, request: Request) -> dict:
        _require_token(request)
        wid = _workspace_id(request)
        wfs = [w for w in load_workflows(wid) if w.get("id") != workflow_id]
        save_workflows(wid, wfs)
        return {"ok": True}

    @app.post("/api/cockpit/run-workflow")
    async def cockpit_run_workflow(req: RunWorkflowRequest, request: Request) -> StreamingResponse:
        """Run a saved workflow: execute nodes in topological order (respecting edges)."""
        token = _require_token(request)
        wid = _workspace_id(request)
        wfs = load_workflows(wid)
        wf = next((w for w in wfs if w.get("id") == req.workflow_id), None)
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow '{req.workflow_id}' not found")

        all_scripts = load_scripts()
        scripts_by_id = {s["id"]: s for s in all_scripts}

        # Topological sort of workflow nodes respecting edges
        nodes = [n["id"] for n in wf.get("nodes", [])]
        edges = wf.get("edges", [])
        deps: dict[str, set[str]] = {n: set() for n in nodes}
        for e in edges:
            if e["target"] in deps:
                deps[e["target"]].add(e["source"])

        ordered: list[str] = []
        visited: set[str] = set()

        def _topo(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            for dep in deps.get(node_id, set()):
                _topo(dep)
            ordered.append(node_id)

        for n in nodes:
            _topo(n)

        env = os.environ.copy()
        env["NOTION_TOKEN"] = token
        for k, v in resolve_db_ids(settings, wid).items():
            if v:
                env[k.upper()] = v

        repo_root = pathlib.Path(__file__).parent.parent

        async def _generate() -> AsyncGenerator[str, None]:
            def sse(msg_type: str, **kwargs: object) -> str:
                return f"data: {_json.dumps({'type': msg_type, **kwargs})}\n\n"

            for script_id in ordered:
                script = scripts_by_id.get(script_id)
                if not script:
                    yield sse("log", message=f"⚠ Script '{script_id}' not found, skipping", script_id=script_id)
                    continue
                script_path = repo_root / script["path"]
                if not script_path.exists():
                    yield sse("log", message=f"⚠ File not found: {script['path']}", script_id=script_id)
                    continue

                cmd = [sys.executable, str(script_path)] + list(script.get("args") or [])
                display = f"$ python {script['path']}" + (
                    " " + " ".join(script.get("args") or []) if script.get("args") else ""
                )
                yield sse("step_start", script_id=script_id, label=script["label"])
                yield sse("log", message=display, script_id=script_id)
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                        env=env,
                        cwd=str(repo_root),
                    )
                    _running_procs[script_id] = proc
                    assert proc.stdout is not None
                    while line := await proc.stdout.readline():
                        yield sse("log", message=line.decode().rstrip(), script_id=script_id)
                    await proc.wait()
                    if proc.returncode == 0:
                        yield sse("step_done", script_id=script_id, message="✓ Done")
                    else:
                        yield sse("step_error", script_id=script_id, message=f"Exited with code {proc.returncode}")
                        break  # stop workflow on first failure
                except Exception as exc:
                    logger.error("workflow step {} failed: {}", script_id, exc)
                    yield sse("step_error", script_id=script_id, message=str(exc))
                    break
                finally:
                    _running_procs.pop(script_id, None)

            yield sse("done", message="Workflow complete")

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Static files + pages ──────────────────────────────────────────────────

    _static = pathlib.Path(__file__).parent / "static"
    if _static.exists():
        app.mount("/static", StaticFiles(directory=str(_static)), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:
            return HTMLResponse((_static / "index.html").read_text())

        @app.get("/cockpit", response_class=HTMLResponse, response_model=None)
        async def cockpit_page(request: Request) -> HTMLResponse | RedirectResponse:
            if not request.session.get("notion_token"):
                return RedirectResponse("/auth/notion?next=/cockpit")
            return HTMLResponse((_static / "cockpit.html").read_text())

    return app


def app_factory() -> FastAPI:
    """Factory for uvicorn --factory mode."""
    from notion_pilot.shared.config import load_settings
    return create_app(load_settings())
