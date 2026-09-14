// Notion Pilot Cockpit — API type layer (kept surfaces after P4).
// Prefer importing from ./client for runtime helpers.

export interface OkResponse {
  ok: boolean;
}

export interface DatabaseMeta {
  count: number;
  label: string;
  icon: string;
  category: string;
}

/** GET /api/cockpit/status */
export interface StatusResponse {
  workspace_name: string;
  workspace_url: string;
  user_name: string;
  databases: Record<string, DatabaseMeta>;
}

/** POST /api/cockpit/config */
export interface CockpitConfigRequest {
  databases?: Record<string, string>;
  workspace_url?: string;
}
