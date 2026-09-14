/**
 * Notion Pilot cockpit — typed API client
 *
 * All functions use credentials: 'include' so the session cookie is forwarded.
 * SSE-streaming functions return AsyncGenerator<SSEEvent>.
 */

// ── Types ─────────────────────────────────────────────────────────────────────

export type Scope = "crm" | "inbox" | "both";

export interface CockpitConfigRequest {
  databases: Record<string, string>;
  workspace_url?: string;
}

export interface DatabaseStatus {
  key: string;
  label: string;
  icon: string;
  category: string;
  db_id: string | null;
  count: number | null;
  has_more?: boolean;
  configured: boolean;
  notion_name: string | null;
  error?: string;
}

export interface CockpitStatus {
  databases: DatabaseStatus[];
  workspace_name: string;
  user_name: string;
  workspace_url: string;
  crm_page_id: string | null;
}

export type SSEEventType =
  | "log"
  | "status"
  | "done"
  | "error"
  | "warning"
  | "result"
  | "token"
  | "step_start"
  | "step_done"
  | "step_error";

export interface SSEEvent {
  type: SSEEventType;
  message?: string;
  url?: string;
  script_id?: string;
  label?: string;
  data?: Record<string, unknown>;
  [key: string]: unknown;
}

// ── Internal helpers ──────────────────────────────────────────────────────────

const BASE = "";

/** Throw with the parsed `detail` from a non-ok FastAPI response. */
async function _throwIfNotOk(res: Response): Promise<void> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (body?.detail) detail = JSON.stringify(body.detail);
    } catch {
      // ignore parse error, use default message
    }
    throw new Error(detail);
  }
}

/** POST/PUT/DELETE helper — returns parsed JSON. */
async function _json<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  await _throwIfNotOk(res);
  return res.json() as Promise<T>;
}

/** GET helper — returns parsed JSON. */
async function _get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: "include", signal });
  await _throwIfNotOk(res);
  return res.json() as Promise<T>;
}

/**
 * SSE streaming helper.
 *
 * Reads the response body line-by-line and yields parsed SSEEvent objects for
 * every `data: {...}` line.  The generator terminates when the stream closes
 * or an event with type "done" or "error" is received.
 */
async function* _sse(
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  await _throwIfNotOk(res);

  if (!res.body) throw new Error("Response body is null");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      const lines = buf.split("\n");
      // Keep the last (potentially incomplete) line in the buffer
      buf = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const jsonStr = trimmed.slice("data:".length).trim();
        if (!jsonStr) continue;
        let event: SSEEvent;
        try {
          event = JSON.parse(jsonStr) as SSEEvent;
        } catch {
          continue; // malformed line — skip
        }
        yield event;
        if (event.type === "done" || event.type === "error") return;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

/** GET /api/cockpit/status */
export async function fetchStatus(): Promise<CockpitStatus> {
  return _get<CockpitStatus>("/api/cockpit/status");
}

/** GET /api/cockpit/status/:key — refresh a single database entry */
export async function fetchSingleDbStatus(key: string): Promise<DatabaseStatus> {
  return _get<DatabaseStatus>(`/api/cockpit/status/${encodeURIComponent(key)}`);
}

/** POST /api/cockpit/config */
export async function saveCockpitConfig(
  req: CockpitConfigRequest,
): Promise<void> {
  await _json<{ ok: boolean }>("POST", "/api/cockpit/config", req);
}

/** DELETE /api/workspace — clear cockpit config (DB links) for this workspace */
export async function deleteWorkspace(): Promise<void> {
  await _json<{ ok: boolean }>("DELETE", "/api/workspace");
}

/** POST /api/crm/refresh — rewrite the CRM home template + views in place. */
export interface RefreshCrmResult {
  notion_page_url: string;
  warnings: string[];
  views: Record<string, { view_id: string; block_id: string }>;
}

export async function refreshCrmTemplate(): Promise<RefreshCrmResult> {
  return _json<RefreshCrmResult>("POST", "/api/crm/refresh");
}

/** GET /api/setup/pages — Notion pages the integration can parent a CRM under */
export interface SetupPage {
  id: string;
  name: string;
  root: boolean;
}

export function listSetupPages(signal?: AbortSignal): Promise<{ pages: SetupPage[] }> {
  return _get("/api/setup/pages", signal);
}

/** POST /api/setup/stream — SSE stream for workspace deployment */
export interface SetupRequest {
  scope: "crm" | "inbox" | "both";
  workspace_name: string;
  /** Omit to create at the top level of the workspace (OAuth tokens only). */
  parent_page_id?: string | null;
}

export function runSetup(req: SetupRequest): AsyncGenerator<SSEEvent> {
  return _sse("POST", "/api/setup/stream", req);
}

export interface SetupCapabilities {
  can_create_top_level: boolean;
  owner_type: string | null;
  workspace_name: string;
}

/** GET /api/setup/capabilities — which placements this token allows */
export async function fetchSetupCapabilities(): Promise<SetupCapabilities> {
  return _get<SetupCapabilities>("/api/setup/capabilities");
}

export interface NotionPage {
  id: string;
  name: string;
}

/** GET /api/cockpit/notion-pages — pages usable as a deploy parent */
export async function fetchNotionPages(
  q = "",
): Promise<{ pages: NotionPage[]; truncated: boolean }> {
  const path = q ? `/api/cockpit/notion-pages?q=${encodeURIComponent(q)}` : "/api/cockpit/notion-pages";
  return _get<{ pages: NotionPage[]; truncated: boolean }>(path);
}
