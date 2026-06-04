import { useCallback, useState } from "react";

export interface DatabaseEntry {
  count: number | null;
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
  editingDbId: string | null;
  savingDbId: string | null;
  onEditDb: (key: string) => void;
  onSaveDb: (key: string, newId: string) => void;
  onCancelEdit: () => void;
}

export function WorkspacePanel({
  databases,
  onRefresh,
  editingDbId,
  savingDbId,
  onEditDb,
  onSaveDb,
  onCancelEdit,
}: WorkspacePanelProps) {
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [availableDbs, setAvailableDbs] = useState<NotionDb[]>([]);
  const [loadingDbs, setLoadingDbs] = useState(false);

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

  return (
    <section className="panel">
      <div className="panel-header">
        <span className="panel-title">Workspace</span>
        <button className="btn-ghost btn-sm" onClick={onRefresh}>↻ Refresh</button>
      </div>

      <div className="db-grid">
        {Object.entries(databases).map(([key, db]) => {
          const isEditing = editingDbId === key;
          const isSaving = savingDbId === key;
          const countIsNull = db.count === null;
          const catClass = (db.category ?? "").toLowerCase();

          return (
            <div className={`db-card${isSaving ? " db-card-saving" : ""}`} key={key}>
              <div className="db-card-top">
                <span className="db-icon">{db.icon}</span>
                <span className="db-cat">{catClass}</span>
                {isSaving && <span className="db-saving-spinner" />}
              </div>

              <div className="db-name">{db.label}</div>
              <div className={`db-count${isSaving ? " na" : countIsNull ? " na" : db.error ? " error" : ""}`}>
                {isSaving ? "…" : db.error ? "Error" : countIsNull ? "—" : db.count}
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
    </section>
  );
}
