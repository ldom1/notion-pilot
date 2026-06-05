import { useCallback, useEffect, useState } from "react";

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

interface TelegramStatus {
  connected: boolean;
  bot_name: string | null;
  last_seen: string | null;
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
}: WorkspacePanelProps) {
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [availableDbs, setAvailableDbs] = useState<NotionDb[]>([]);
  const [loadingDbs, setLoadingDbs] = useState(false);
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null);
  const [telegramPinging, setTelegramPinging] = useState(false);
  const [telegramPingResult, setTelegramPingResult] = useState<string | null>(null);

  const fetchTelegramStatus = useCallback(async () => {
    try {
      const r = await fetch("/api/telegram/status", { credentials: "include" });
      if (r.ok) setTelegramStatus(await r.json() as TelegramStatus);
    } catch { /* silent */ }
  }, []);

  const pingTelegram = useCallback(async () => {
    setTelegramPinging(true);
    setTelegramPingResult(null);
    try {
      const r = await fetch("/api/telegram/ping", { method: "POST", credentials: "include" });
      const data = await r.json() as { ok: boolean; latency_ms: number };
      setTelegramPingResult(data.ok ? `OK — ${data.latency_ms}ms` : "Failed");
    } catch {
      setTelegramPingResult("Error");
    } finally {
      setTelegramPinging(false);
    }
  }, []);

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

  useEffect(() => {
    void fetchTelegramStatus();
    const id = setInterval(() => { void fetchTelegramStatus(); }, 60_000);
    return () => clearInterval(id);
  }, [fetchTelegramStatus]);

  function handleEditClick(key: string, currentId: string | null | undefined) {
    setSelections((prev) => ({ ...prev, [key]: currentId ?? "" }));
    onEditDb(key);
    void fetchDbs();
  }

  function handleSave(key: string) {
    onSaveDb(key, selections[key] ?? "");
  }

  function relativeTime(iso: string | null): string {
    if (!iso) return "never";
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}min ago`;
    return `${Math.floor(diff / 3600)}h ago`;
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
        {Object.entries(databases).map(([key, db]) => {
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

      <div className="tg-bot-card">
        <div className="tg-bot-header">
          <span className="db-icon">🤖</span>
          <span className="tg-bot-label">Telegram Bot</span>
          <span
            className="tg-bot-dot"
            style={{ color: telegramStatus?.connected ? "#22c55e" : "#ef4444" }}
            title={telegramStatus?.connected ? "Connected" : "Disconnected"}
          >●</span>
        </div>
        {telegramStatus && (
          <div className="tg-bot-meta">
            {telegramStatus.bot_name && <span>@{telegramStatus.bot_name}</span>}
            <span>last seen {relativeTime(telegramStatus.last_seen)}</span>
          </div>
        )}
        <div className="tg-bot-actions">
          <button
            className="btn-ghost btn-sm"
            onClick={() => { void pingTelegram(); }}
            disabled={telegramPinging}
          >
            {telegramPinging ? "Testing…" : "Test connection"}
          </button>
          {telegramPingResult && (
            <span className="tg-bot-ping-result">{telegramPingResult}</span>
          )}
        </div>
      </div>
    </section>
  );
}
