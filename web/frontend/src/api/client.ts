/**
 * Notion Pilot cockpit — typed API client
 *
 * All functions use credentials: 'include' so the session cookie is forwarded.
 * SSE-streaming functions return AsyncGenerator<SSEEvent>.
 */

// ── Types (mirrored from web/models.py) ──────────────────────────────────────

export type Scope = "crm" | "inbox" | "both";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface WorkflowNode {
  id: string;
  position: { x: number; y: number };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
}

export interface WorkflowDef {
  id: string;
  name: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface NewPerson {
  name: string;
  position?: string;
  company?: string;
}

// ── Request shapes ────────────────────────────────────────────────────────────

export interface RunScriptRequest {
  script_id: string;
  extra_args?: string[];
}

export interface ChatRequest {
  query: string;
  history?: ChatMessage[];
  session_id?: string;
}

export interface UpdateMemoryRequest {
  text: string;
}

export interface CreateLeadRequest {
  name: string;
  position?: string;
  company?: string;
}

export interface CreateDealRequest {
  deal_name: string;
  notion_id?: string;
  new_person?: NewPerson;
  extra_fields?: Record<string, string | string[] | number>;
  summary?: string;
  company_name?: string;
}

export interface CockpitConfigRequest {
  databases: Record<string, string>;
  workspace_url?: string;
}

export interface SaveWorkflowRequest {
  workflow: WorkflowDef;
}

export interface RunWorkflowRequest {
  workflow_id: string;
}

// ── Response shapes ───────────────────────────────────────────────────────────

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
}

export interface ScriptParam {
  id: string;
  label: string;
  type: 'number' | 'text' | 'boolean' | 'checkbox';
  flag: string;
  default?: string | number | boolean;
  min?: number;
  max?: number;
  help?: string;
}

export interface Script {
  id: string;
  label: string;
  path: string;
  args?: string[];
  description?: string;
  category: string;
  params?: ScriptParam[];
}

export interface DealWizardField {
  key: string;
  type: "select" | "multi_select" | "text" | "number";
  options?: string[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at?: string;
  message_count?: number;
  /** First user message, truncated to 80 chars */
  preview?: string;
}

/** Alias so components can import ConversationMeta from client */
export type ConversationMeta = ConversationSummary;

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  ts: string;
  data?: Record<string, unknown>;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at?: string;
  messages: ConversationMessage[];
  history: ChatMessage[];
  people_cache?: unknown[];
  companies_cache?: unknown[];
}

// ── SSE event shapes ──────────────────────────────────────────────────────────

export type SSEEventType =
  | "log"
  | "status"
  | "done"
  | "error"
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
async function _get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: "include" });
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

/** GET /api/cockpit/scripts */
export async function fetchScripts(): Promise<Script[]> {
  const data = await _get<{ scripts: Script[] }>("/api/cockpit/scripts");
  return data.scripts;
}

/** POST /api/cockpit/run-script — SSE stream */
export function runScript(
  req: RunScriptRequest,
): AsyncGenerator<SSEEvent> {
  return _sse("POST", "/api/cockpit/run-script", req);
}

/** POST /api/cockpit/stop-script */
export async function stopScript(scriptId: string): Promise<void> {
  await _json<{ ok: boolean }>("POST", "/api/cockpit/stop-script", {
    script_id: scriptId,
  });
}

/** GET /api/cockpit/workflows */
export async function fetchWorkflows(): Promise<WorkflowDef[]> {
  const data = await _get<{ workflows: WorkflowDef[] }>(
    "/api/cockpit/workflows",
  );
  return data.workflows;
}

/** POST /api/cockpit/workflows */
export async function saveWorkflow(workflow: WorkflowDef): Promise<string> {
  const data = await _json<{ ok: boolean; workflow_id: string }>(
    "POST",
    "/api/cockpit/workflows",
    { workflow } satisfies SaveWorkflowRequest,
  );
  return data.workflow_id;
}

/** DELETE /api/cockpit/workflows/:id */
export async function deleteWorkflow(workflowId: string): Promise<void> {
  await _json<{ ok: boolean }>(
    "DELETE",
    `/api/cockpit/workflows/${encodeURIComponent(workflowId)}`,
  );
}

/** POST /api/cockpit/run-workflow — SSE stream */
export function runWorkflow(
  workflowId: string,
): AsyncGenerator<SSEEvent> {
  return _sse("POST", "/api/cockpit/run-workflow", {
    workflow_id: workflowId,
  } satisfies RunWorkflowRequest);
}

/** POST /api/cockpit/chat — SSE stream */
export function sendChat(req: ChatRequest): AsyncGenerator<SSEEvent> {
  return _sse("POST", "/api/cockpit/chat", req);
}

/** GET /api/cockpit/conversations */
export async function fetchConversations(): Promise<ConversationSummary[]> {
  const data = await _get<{ conversations: ConversationSummary[] }>(
    "/api/cockpit/conversations",
  );
  return data.conversations;
}

/** GET /api/cockpit/conversations/:id */
export async function loadConversation(
  sessionId: string,
): Promise<Conversation> {
  const data = await _get<{ session: Conversation }>(
    `/api/cockpit/conversations/${encodeURIComponent(sessionId)}`,
  );
  return data.session;
}

/** DELETE /api/cockpit/conversations/:id */
export async function deleteConversation(sessionId: string): Promise<void> {
  await _json<{ ok: boolean }>(
    "DELETE",
    `/api/cockpit/conversations/${encodeURIComponent(sessionId)}`,
  );
}

/** GET /api/cockpit/memory */
export async function fetchMemory(): Promise<string> {
  const data = await _get<{ text: string }>("/api/cockpit/memory");
  return data.text;
}

/** PUT /api/cockpit/memory */
export async function saveMemory(text: string): Promise<void> {
  await _json<{ ok: boolean }>("PUT", "/api/cockpit/memory", {
    text,
  } satisfies UpdateMemoryRequest);
}

/** GET /api/cockpit/deals-properties */
export async function fetchDealProperties(): Promise<DealWizardField[]> {
  const data = await _get<{ fields: DealWizardField[] }>(
    "/api/cockpit/deals-properties",
  );
  return data.fields;
}

/** POST /api/cockpit/create-deal */
export async function createDeal(
  req: CreateDealRequest,
): Promise<{ page_id: string; url: string }> {
  return _json<{ page_id: string; url: string }>(
    "POST",
    "/api/cockpit/create-deal",
    req,
  );
}

/** POST /api/cockpit/create-lead */
export async function createLead(
  req: CreateLeadRequest,
): Promise<{ page_id: string; url: string }> {
  return _json<{ page_id: string; url: string }>(
    "POST",
    "/api/cockpit/create-lead",
    req,
  );
}

/** POST /api/cockpit/config */
export async function saveCockpitConfig(
  req: CockpitConfigRequest,
): Promise<void> {
  await _json<{ ok: boolean }>("POST", "/api/cockpit/config", req);
}
