import React, { useEffect, useState, useCallback } from "react";

import Header from "../components/Header";
import { Spinner } from "../components/Spinner";
import { McpPanel } from "../features/mcp/McpPanel";
import { ChatPanel } from "../features/chat/ChatPanel";
import { SetupWizard } from "../features/setup/SetupWizard";
import { WorkspacePanel, DatabaseEntry } from "../features/workspace/WorkspacePanel";

import { fetchStatus, fetchSingleDbStatus, saveCockpitConfig, CockpitStatus, DatabaseStatus } from "../api/client";

// ── helpers ───────────────────────────────────────────────────────────────────

function toDbEntry(ds: DatabaseStatus): DatabaseEntry {
  return {
    count: ds.count,
    has_more: ds.has_more,
    label: ds.label,
    icon: ds.icon,
    category: ds.category,
    db_id: ds.db_id,
    notion_name: ds.notion_name,
    error: ds.error,
  };
}

function toDatabasesMap(
  statuses: DatabaseStatus[],
): Record<string, DatabaseEntry> {
  return Object.fromEntries(statuses.map((ds) => [ds.key, toDbEntry(ds)]));
}

// ── Cockpit page ──────────────────────────────────────────────────────────────

const Cockpit: React.FC = () => {
  const [status, setStatus] = useState<CockpitStatus | null>(null);
  const [loading, setLoading] = useState(true);   // initial mount only
  const [refreshing, setRefreshing] = useState(false); // user-triggered refresh
  const [error, setError] = useState<string | null>(null);

  // WorkspacePanel editing state
  const [editingDbId, setEditingDbId] = useState<string | null>(null);
  const [savingDbId, setSavingDbId] = useState<string | null>(null);
  const [showRedeploy, setShowRedeploy] = useState(false);

  const loadStatus = useCallback(async (opts?: { initial?: boolean }) => {
    const isInitial = opts?.initial ?? false;
    if (isInitial) setLoading(true); else setRefreshing(true);
    setError(null);
    try {
      const data = await fetchStatus();
      setStatus(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("401") || msg.toLowerCase().includes("unauthorized")) {
        window.location.href = `/auth/notion?next=/cockpit`;
        return;
      }
      setError(msg);
    } finally {
      if (isInitial) setLoading(false); else setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadStatus({ initial: true });
  }, [loadStatus]);

  // ── WorkspacePanel handlers ─────────────────────────────────────────────────

  function handleEditDb(key: string) {
    setEditingDbId(key);
  }

  function handleCancelEdit() {
    setEditingDbId(null);
  }

  async function handleSaveDb(key: string, newId: string) {
    if (!status) return;
    const updatedDbs: Record<string, string> = {};
    for (const ds of status.databases) {
      updatedDbs[ds.key] = ds.key === key ? newId : (ds.db_id ?? "");
    }
    await saveCockpitConfig({ databases: updatedDbs });
    setEditingDbId(null);
    setSavingDbId(key);
    try {
      const updated = await fetchSingleDbStatus(key);
      setStatus((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          databases: prev.databases.map((ds) =>
            ds.key === key ? { ...ds, ...updated } : ds
          ),
        };
      });
    } catch {
      await loadStatus();
    } finally {
      setSavingDbId(null);
    }
  }

  // ── render ──────────────────────────────────────────────────────────────────

  if (loading) {
    return <Spinner fullPage />;
  }

  if (error) {
    return (
      <>
        <Header workspaceName="" userName="" notionUrl="" />
        <div className="main">
          <p style={{ color: '#dc2626', padding: '2rem 0', fontSize: '0.88rem' }}>{error}</p>
        </div>
      </>
    );
  }

  const workspaceName = status?.workspace_name ?? "";
  const userName = status?.user_name ?? "";
  const notionUrl = status?.workspace_url ?? "";
  const databases = status ? toDatabasesMap(status.databases) : {};

  return (
    <>
      <Header
        workspaceName={workspaceName}
        userName={userName}
        notionUrl={notionUrl}
      />
      <div className="main">
        <ChatPanel />
        <WorkspacePanel
          databases={databases}
          onRefresh={() => { void loadStatus(); }}
          isRefreshing={refreshing}
          editingDbId={editingDbId}
          savingDbId={savingDbId}
          onEditDb={handleEditDb}
          onSaveDb={handleSaveDb}
          onCancelEdit={handleCancelEdit}
          onRedeploy={() => setShowRedeploy(true)}
        />
        <McpPanel />
      </div>

      {showRedeploy && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            zIndex: 1000, padding: "1rem",
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowRedeploy(false); }}
        >
          <SetupWizard
            onComplete={() => { setShowRedeploy(false); void loadStatus(); }}
            onSkip={() => setShowRedeploy(false)}
          />
        </div>
      )}
    </>
  );
};

export default Cockpit;
