// ─────────────────────────────────────────────────────────────────────────────
// Notion Pilot Cockpit — API type layer
// All types correspond to the Python Pydantic models in web/models.py and the
// route contracts defined in web/server.py.
// ─────────────────────────────────────────────────────────────────────────────

// ─── Shared primitives ───────────────────────────────────────────────────────

/** Generic success response for mutating endpoints. */
export interface OkResponse {
  ok: boolean;
}

// ─── Status ──────────────────────────────────────────────────────────────────

export interface DatabaseMeta {
  count: number;
  label: string;
  icon: string;
  /** e.g. "crm" | "inbox" | "knowledge" */
  category: string;
}

/** GET /api/cockpit/status */
export interface StatusResponse {
  workspace_name: string;
  workspace_url: string;
  user_name: string;
  databases: Record<string, DatabaseMeta>;
}

// ─── Scripts ─────────────────────────────────────────────────────────────────

export type ScriptParamType = "number" | "text" | "boolean" | "checkbox";

export interface ScriptParam {
  id: string;
  label: string;
  type: ScriptParamType;
  /** CLI flag, e.g. "--limit" */
  flag: string;
  default?: string | number | boolean;
  min?: number;
  max?: number;
  help?: string;
}

export interface Script {
  id: string;
  label: string;
  description: string;
  /** Grouping key used to bucket scripts in the UI, e.g. "crm" | "inbox" */
  category: string;
  /** Pre-baked extra CLI arguments appended verbatim */
  args?: string[];
  params?: ScriptParam[];
}

/** GET /api/cockpit/scripts */
export interface ScriptsResponse {
  scripts: Script[];
}

/** POST /api/cockpit/run-script */
export interface RunScriptRequest {
  script_id: string;
  extra_args?: string[];
}

/** POST /api/cockpit/stop-script */
export interface StopScriptRequest {
  script_id: string;
}

// ─── Workflows ───────────────────────────────────────────────────────────────

export interface WorkflowNodePosition {
  x: number;
  y: number;
}

export interface WorkflowNode {
  id: string;
  position: WorkflowNodePosition;
  /** Script id or built-in node type bound to this node */
  script_id?: string;
  /** Display label shown on the canvas node */
  label?: string;
  /** Arbitrary React Flow node data — keep extensible */
  data?: Record<string, unknown>;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  /** Optional React Flow edge type, e.g. "smoothstep" */
  type?: string;
}

export interface WorkflowDef {
  id: string;
  name: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

/** GET /api/cockpit/workflows */
export interface WorkflowsResponse {
  workflows: WorkflowDef[];
}

/** POST /api/cockpit/save-workflow */
export interface SaveWorkflowRequest {
  workflow: WorkflowDef;
}

/** POST /api/cockpit/run-workflow */
export interface RunWorkflowRequest {
  workflow_id: string;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export type LeadType = "existing" | "new";

export interface Lead {
  type: LeadType;
  name: string;
  position?: string;
  company?: string;
  notion_id?: string;
  reason?: string;
  deal_name?: string;
}

export type ChatAction = "suggest" | "create" | "info";

export interface ChatResult {
  action: ChatAction;
  message: string;
  leads: Lead[];
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  /** Structured payload attached to assistant messages */
  data?: ChatResult;
  /** ISO-8601 timestamp */
  ts?: string;
}

/** Minimal history entry forwarded to the LLM */
export interface HistoryEntry {
  role: ChatRole;
  content: string;
}

/** POST /api/cockpit/chat */
export interface ChatRequest {
  query: string;
  history: HistoryEntry[];
  session_id?: string;
}

// ─── Conversations ────────────────────────────────────────────────────────────

export interface ConversationMeta {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  /** Raw history forwarded to the LLM */
  history: HistoryEntry[];
}

/** GET /api/cockpit/conversations */
export interface ConversationsResponse {
  conversations: ConversationMeta[];
}

/** GET /api/cockpit/conversations/{id} */
export interface ConversationResponse {
  session: ConversationSession;
}

// ─── Memory ──────────────────────────────────────────────────────────────────

/** GET /api/cockpit/memory */
export interface MemoryResponse {
  text: string;
}

/** PUT /api/cockpit/memory */
export interface PutMemoryRequest {
  text: string;
}

// ─── Deals / Leads ───────────────────────────────────────────────────────────

export type DealFieldType =
  | "text"
  | "number"
  | "select"
  | "multi_select"
  | "date"
  | "checkbox"
  | "url"
  | "email"
  | "phone_number"
  | "relation"
  | "formula"
  | "rollup"
  | "people"
  | "files";

export interface DealFieldOption {
  id: string;
  name: string;
  color?: string;
}

export interface DealField {
  id: string;
  name: string;
  type: DealFieldType;
  options?: DealFieldOption[];
  required?: boolean;
}

/** GET /api/cockpit/deals-properties */
export interface DealsPropertiesResponse {
  fields: DealField[];
}

/** POST /api/cockpit/create-deal */
export interface CreateDealRequest {
  [field: string]: unknown;
}

/** POST /api/cockpit/create-deal */
export interface CreateDealResponse {
  url: string;
}

/** POST /api/cockpit/create-lead */
export interface CreateLeadRequest {
  [field: string]: unknown;
}

/** POST /api/cockpit/create-lead */
export interface CreateLeadResponse {
  url: string;
}

// ─── Cockpit config ──────────────────────────────────────────────────────────

/** POST /api/cockpit/cockpit-config */
export interface CockpitConfigRequest {
  /** Notion database IDs keyed by logical name, e.g. { people: "abc123" } */
  databases?: Record<string, string>;
  workspace_url?: string;
  [key: string]: unknown;
}

// ─── SSE streaming ───────────────────────────────────────────────────────────

/**
 * Discriminated union of every event type emitted by the three SSE endpoints:
 *   POST /run-script, POST /run-workflow, POST /chat
 *
 * All events are newline-delimited JSON with a `type` discriminant.
 */

/** A line of stdout / stderr from a running script. */
export interface SseLogEvent {
  type: "log";
  line: string;
}

/** Emitted when a script or workflow node finishes. */
export interface SseStatusEvent {
  type: "status";
  /** "running" | "done" | "error" */
  status: "running" | "done" | "error";
  script_id?: string;
  node_id?: string;
  /** Human-readable message */
  message?: string;
}

/** Streamed token from the chat LLM. */
export interface SseTokenEvent {
  type: "token";
  content: string;
}

/** Final structured result from the chat endpoint. */
export interface SseChatResultEvent {
  type: "result";
  data: ChatResult;
  session_id: string;
}

/** Fatal error event — connection will close after this. */
export interface SseErrorEvent {
  type: "error";
  message: string;
}

/** Progress update for long-running workflow runs. */
export interface SseProgressEvent {
  type: "progress";
  /** Index of the currently executing node (0-based) */
  step: number;
  total: number;
  node_id: string;
  node_label?: string;
}

/** Union of all possible SSE events. */
export type SseEvent =
  | SseLogEvent
  | SseStatusEvent
  | SseTokenEvent
  | SseChatResultEvent
  | SseErrorEvent
  | SseProgressEvent;

/** Narrow helper — asserts that `e` is a specific SSE event subtype. */
export function isSseEvent<T extends SseEvent["type"]>(
  e: SseEvent,
  type: T
): e is Extract<SseEvent, { type: T }> {
  return e.type === type;
}
