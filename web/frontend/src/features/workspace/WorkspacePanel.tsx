import { useCallback, useState } from "react";
import { deleteWorkspace, refreshCrmTemplate } from "../../api/client";

export interface DatabaseEntry {
  count: number | null;
  has_more?: boolean;
  label: string;
  icon: string;
  category: string;
  db_id?: string | null;
  notion_name?: string | null;
  error?: string;
}

interface NotionDb {
  id: string;
  name: string;
}

interface WorkspacePanelProps {
  databases: Record<string, DatabaseEntry>;
  onRefresh: () => void;
  isRefreshing?: boolean;
  editingDbId: string | null;
  savingDbId: string | null;
  onEditDb: (key: string) => void;
  onSaveDb: (key: string, newId: string) => void;
  onCancelEdit: () => void;
  onRedeploy: () => void;
  /** Notion page id of the deployed CRM home, or null if none is linked yet. */
  crmPageId: string | null;
}

export function WorkspacePanel({
  databases,
  onRefresh,
  isRefreshing = false,
  editingDbId,
  savingDbId,
  onEditDb,
  onSaveDb,
  onCancelEdit,
  onRedeploy,
  crmPageId,
}: WorkspacePanelProps) {
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [availableDbs, setAvailableDbs] = useState<NotionDb[]>([]);
  const [loadingDbs, setLoadingDbs] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [refreshingCrm, setRefreshingCrm] = useState(false);
  const [crmRefreshError, setCrmRefreshError] = useState<string | null>(null);
  const [crmWarnings, setCrmWarnings] = useState<string[] | null>(null);

  const fetchDbs = useCallback(async () => {
    setLoadingDbs(true);
    try {
      const r = await fetch("/api/cockpit/notion-databases", { credentials: "include" });
      if (r.ok) {
        const data = await r.json() as { databases: NotionDb[] };
        setAvailableDbs(data.databases ?? []);
      }
    } catch {
      setAvailableDbs([]);
    } finally {
      setLoadingDbs(false);
    }
  }, []);

  function handleEditClick(key: string, currentId: string | null | undefined) {
    setSelections((prev) => ({ ...prev, [key]: currentId ?? "" }));
    onEditDb(key);
    void fetchDbs();
  }

  function handleSave(key: string) {
    onSaveDb(key, selections[key] ?? "");
  }

  async function handleRefreshCrm(): Promise<void> {
    setRefreshingCrm(true);
    setCrmRefreshError(null);
    setCrmWarnings(null);
    try {
      const result = await refreshCrmTemplate();
      setCrmWarnings(result.warnings);
      onRefresh();
    } catch (err) {
      setCrmRefreshError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshingCrm(false);
    }
  }

  async function handleDelete(): Promise<void> {
    setDeleting(true);
    try {
      await deleteWorkspace();
      onRefresh();
      setConfirmDelete(false);
    } catch {
      // ignore — user can retry
    } finally {
      setDeleting(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <span className="panel-title">Workspace</span>
        <button
          className="btn-ghost btn-sm"
          onClick={onRefresh}
          disabled={isRefreshing}
        >
          {isRefreshing ? "↻ …" : "↻ Refresh"}
        </button>
      </div>

      <div className="db-grid">
        {Object.entries(databases)
          .filter(([, db]) => db.category !== "inbox")
          .map(([key, db]) => {
          const isEditing = editingDbId === key;
          const isSaving = savingDbId === key || isRefreshing;
          const countIsNull = db.count === null;
          const catClass = (db.category ?? "").toLowerCase();
          const countLabel = db.count !== null
            ? `${db.count}${db.has_more ? "+" : ""}`
            : null;

          return (
            <div className={`db-card${isSaving ? " db-card-saving" : ""}`} key={key}>
              <div className="db-card-top">
                <span className="db-icon">{db.icon}</span>
                <span className="db-cat">{catClass}</span>
                {isSaving && <span className="db-saving-spinner" />}
              </div>

              <div className="db-name">{db.label}</div>
              <div className={`db-count${isSaving ? " na" : countIsNull ? " na" : db.error ? " error" : ""}`}>
                {isSaving ? "…" : db.error ? "Error" : countLabel ?? "—"}
              </div>
              <div className="db-count-label">
                {isSaving ? "loading" : db.error ? db.error.slice(0, 40) : "records"}
              </div>

              <div className="db-footer">
                {!isEditing && (
                  <>
                    <span className="db-id-display" title={db.db_id ?? undefined}>
                      {db.notion_name ?? (db.error ? "⚠ check access" : db.db_id ? "linked" : "not configured")}
                    </span>
                    <button
                      className="db-edit-btn"
                      title="Link database"
                      onClick={() => handleEditClick(key, db.db_id)}
                    >
                      ✎
                    </button>
                  </>
                )}
              </div>

              <div className={`db-edit-form${isEditing ? " open" : ""}`}>
                {loadingDbs ? (
                  <div className="db-edit-loading">Loading databases…</div>
                ) : (
                  <select
                    className="db-edit-select"
                    value={selections[key] ?? ""}
                    onChange={(e) => setSelections((prev) => ({ ...prev, [key]: e.target.value }))}
                    autoFocus={isEditing}
                  >
                    <option value="">— Select a database —</option>
                    {availableDbs.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                )}
                <div className="db-edit-actions">
                  <button className="db-edit-save" onClick={() => handleSave(key)}>Save</button>
                  <button className="db-edit-cancel" onClick={onCancelEdit}>Cancel</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="tg-bot-card" style={{ marginTop: "0.5rem" }}>
        <div className="tg-bot-header">
          <span className="db-icon">⚙️</span>
          <span className="tg-bot-label">Workspace actions</span>
        </div>
        <div className="tg-bot-actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
          {crmPageId && (
            <button
              className="btn-ghost btn-sm"
              onClick={() => { void handleRefreshCrm(); }}
              disabled={refreshingCrm}
              title="Rewrite the CRM home template and pipeline views in place — databases and rows are kept."
            >
              {refreshingCrm ? "Refreshing CRM…" : "⟳ Refresh CRM template"}
            </button>
          )}
          <button className="btn-ghost btn-sm" onClick={onRedeploy}>
            ↺ Redeploy workspace
          </button>
          {!confirmDelete ? (
            <button
              className="btn-ghost btn-sm"
              style={{ color: "var(--bad)", borderColor: "var(--bad-wash)" }}
              onClick={() => setConfirmDelete(true)}
            >
              🗑 Delete workspace config
            </button>
          ) : (
            <span style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.78rem", color: "var(--bad)" }}>
                This clears all DB links. Are you sure?
              </span>
              <button
                className="btn-ghost btn-sm"
                style={{ color: "var(--bad)", borderColor: "var(--bad-wash)" }}
                onClick={() => void handleDelete()}
                disabled={deleting}
              >
                {deleting ? "Deleting…" : "Confirm delete"}
              </button>
              <button className="btn-ghost btn-sm" onClick={() => setConfirmDelete(false)}>
                Cancel
              </button>
            </span>
          )}
        </div>
        {crmRefreshError && (
          <p style={{ margin: "0.6rem 0 0", fontSize: "0.78rem", color: "var(--bad)" }}>
            {crmRefreshError}
          </p>
        )}
        {crmWarnings && crmWarnings.length === 0 && (
          <p style={{ margin: "0.6rem 0 0", fontSize: "0.78rem", color: "var(--muted)" }}>
            CRM home refreshed — all four pipeline views are up to date.
          </p>
        )}
        {crmWarnings && crmWarnings.length > 0 && (
          <ul className="lp-setup-warnings" style={{ margin: "0.6rem 0 0" }}>
            {crmWarnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
