import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchScripts,
  fetchWorkflows,
  runScript,
  stopScript,
  Script,
  WorkflowDef,
  SSEEvent,
} from '../../api/client';
import LogPanel, { LogLine } from '../../components/LogPanel';
import ParamsModal from './ParamsModal';
import FlowGraph from './FlowGraph';

// ─── ScriptCard ───────────────────────────────────────────────────────────────

interface ScriptCardProps {
  script: Script;
  isRunning: boolean;
  onRun: (script: Script) => void;
  onStop: (scriptId: string) => void;
}

export const ScriptCard: React.FC<ScriptCardProps> = ({
  script,
  isRunning,
  onRun,
  onStop,
}) => (
  <div className="script-card">
    <div className="script-card-top">
      <span className={`script-cat-badge ${(script.category ?? '').toLowerCase()}`}>
        {script.category ?? ''}
      </span>
    </div>
    <div className="script-name">{script.label}</div>
    {script.description && (
      <div className="script-desc">{script.description}</div>
    )}
    <div className="script-footer" style={{ gap: '0.4rem' }}>
      <button
        className="run-btn stop-btn"
        style={{ background: '#dc2626', display: isRunning ? 'inline-flex' : 'none' }}
        onClick={() => onStop(script.id)}
      >
        ■ Stop
      </button>
      <button
        className={`run-btn${isRunning ? ' running' : ''}`}
        onClick={() => onRun(script)}
        disabled={isRunning}
      >
        {isRunning ? '● Running…' : '▶ Run'}
      </button>
    </div>
  </div>
);

// ─── WorkflowCard ─────────────────────────────────────────────────────────────

interface WorkflowCardProps {
  workflow: WorkflowDef;
  isRunning: boolean;
  onRun: (workflowId: string) => void;
}

export const WorkflowCard: React.FC<WorkflowCardProps> = ({
  workflow,
  isRunning,
  onRun,
}) => (
  <div className="wf-card">
    <div className="wf-card-icon">⬡</div>
    <div className="wf-card-info">
      <div className="wf-card-name">{workflow.name}</div>
      <div className="wf-card-meta">
        {workflow.nodes.length} step{workflow.nodes.length !== 1 ? 's' : ''}
      </div>
    </div>
    <div className="wf-card-actions">
      <button
        className={`run-btn btn-sm${isRunning ? ' running' : ''}`}
        style={{ fontSize: '0.72rem', padding: '0.28rem 0.65rem' }}
        disabled={isRunning}
        onClick={() => onRun(workflow.id)}
      >
        {isRunning ? '● Running…' : '▶ Run'}
      </button>
    </div>
  </div>
);

// ─── Category filter ──────────────────────────────────────────────────────────

type CategoryFilter = 'all' | 'crm' | 'inbox';

function getCategories(scripts: Script[]): CategoryFilter[] {
  const seen = new Set<string>();
  for (const s of scripts) {
    if (s.category) seen.add(s.category);
  }
  const extras = Array.from(seen).filter(
    (c): c is CategoryFilter => c === 'crm' || c === 'inbox',
  );
  return ['all', ...extras];
}

// ─── AutomationPanel ─────────────────────────────────────────────────────────

type View = 'list' | 'graph';
type ActiveTab = 'operations' | 'workflows';

const AutomationPanel: React.FC = () => {
  // ── view state ──
  const [view, setView] = useState<View>('list');
  const [activeTab, setActiveTab] = useState<ActiveTab>('operations');
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all');

  // ── data ──
  const [scripts, setScripts] = useState<Script[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDef[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  // ── script run state ──
  const [runningScriptId, setRunningScriptId] = useState<string | null>(null);
  const [logLines, setLogLines] = useState<LogLine[]>([]);
  const [logVisible, setLogVisible] = useState(false);
  const [logLabel, setLogLabel] = useState('');

  // ── params modal ──
  const [paramsScript, setParamsScript] = useState<Script | null>(null);

  // ── load scripts + workflows on mount ──
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [s, w] = await Promise.all([fetchScripts(), fetchWorkflows()]);
        if (!cancelled) {
          setScripts(s);
          setWorkflows(w);
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : String(err));
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── run a script (after params resolved) ──
  const executeScript = useCallback(
    async (scriptId: string, extraArgs: string[] = []) => {
      const script = scripts.find((s) => s.id === scriptId);
      const label = script?.label ?? scriptId;

      setRunningScriptId(scriptId);
      setLogLines([{ text: `▶ ${label}`, cls: 'cmd' }]);
      setLogLabel(label);
      setLogVisible(true);

      try {
        const stream: AsyncGenerator<SSEEvent> = runScript({
          script_id: scriptId,
          extra_args: extraArgs.length > 0 ? extraArgs : undefined,
        });

        for await (const event of stream) {
          if (event.type === 'log') {
            setLogLines((prev) => [
              ...prev,
              { text: (event.message ?? '') as string, cls: '' },
            ]);
          } else if (event.type === 'done' || event.type === 'status') {
            const msg =
              typeof event.message === 'string' && event.message
                ? event.message
                : 'Done.';
            setLogLines((prev) => [...prev, { text: `✓ ${msg}`, cls: 'done' }]);
          } else if (event.type === 'error') {
            const msg =
              typeof event.message === 'string' && event.message
                ? event.message
                : 'Unknown error';
            setLogLines((prev) => [...prev, { text: `✗ ${msg}`, cls: 'err' }]);
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setLogLines((prev) => [...prev, { text: `✗ ${msg}`, cls: 'err' }]);
      } finally {
        setRunningScriptId(null);
      }
    },
    [scripts],
  );

  // ── handle "Run" click on a ScriptCard ──
  const handleRunScript = useCallback(
    (script: Script) => {
      if (script.params && script.params.length > 0) {
        // open params modal — execution deferred to onConfirm
        setParamsScript(script);
      } else {
        void executeScript(script.id);
      }
    },
    [executeScript],
  );

  // ── confirm params from modal ──
  const handleParamsConfirm = useCallback(
    (extraArgs: string[]) => {
      if (!paramsScript) return;
      const id = paramsScript.id;
      setParamsScript(null);
      void executeScript(id, extraArgs);
    },
    [paramsScript, executeScript],
  );

  // ── stop running script ──
  const handleStop = useCallback(async (scriptId: string) => {
    try {
      await stopScript(scriptId);
    } catch {
      // best-effort
    } finally {
      setRunningScriptId(null);
    }
  }, []);

  // ── filtered scripts ──
  const visibleScripts =
    categoryFilter === 'all'
      ? scripts
      : scripts.filter((s) => s.category === categoryFilter);

  const categories = getCategories(scripts);

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <section className="panel">
      <div className="panel-header">
        <span className="panel-title">Automation</span>
        <div className="auto-view-toggle">
          <button
            className={`view-btn${view === 'list' ? ' active' : ''}`}
            onClick={() => setView('list')}
          >
            ≡ List
          </button>
          <button
            className={`view-btn${view === 'graph' ? ' active' : ''}`}
            onClick={() => setView('graph')}
          >
            ⬡ Graph
          </button>
        </div>
      </div>

      {view === 'list' && (
        <>
          <div className="auto-tabs-row">
            <div className="auto-type-tabs">
              <button
                className={`atype-btn${activeTab === 'operations' ? ' active' : ''}`}
                onClick={() => setActiveTab('operations')}
              >
                Operations
              </button>
              <button
                className={`atype-btn${activeTab === 'workflows' ? ' active' : ''}`}
                onClick={() => setActiveTab('workflows')}
              >
                Workflows
              </button>
            </div>
            {activeTab === 'operations' && categories.length > 1 && (
              <div className="filter-tabs">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    className={`ftab${categoryFilter === cat ? ' active' : ''}`}
                    onClick={() => setCategoryFilter(cat)}
                  >
                    {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </button>
                ))}
              </div>
            )}
          </div>

          {activeTab === 'operations' && (
            <>
              {loadError && (
                <p style={{ color: '#dc2626', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
                  Failed to load scripts: {loadError}
                </p>
              )}
              <div className="script-grid">
                {visibleScripts.map((script) => (
                  <ScriptCard
                    key={script.id}
                    script={script}
                    isRunning={runningScriptId === script.id}
                    onRun={handleRunScript}
                    onStop={(id) => void handleStop(id)}
                  />
                ))}
                {visibleScripts.length === 0 && !loadError && (
                  <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '1.5rem', color: '#bbb', fontSize: '0.84rem' }}>
                    No scripts available.
                  </div>
                )}
              </div>
            </>
          )}

          {activeTab === 'workflows' && (
            <>
              <div className="wf-cards-list">
                {workflows.map((wf) => (
                  <WorkflowCard
                    key={wf.id}
                    workflow={wf}
                    isRunning={false}
                    onRun={() => undefined}
                  />
                ))}
                {workflows.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '1.5rem', color: '#bbb', fontSize: '0.84rem' }}>
                    No workflows saved yet.
                  </div>
                )}
              </div>
              <button className="wf-compose-btn" style={{ marginTop: '0.75rem' }} onClick={() => setView('graph')}>
                ⬡ Compose a new workflow in graph view
              </button>
            </>
          )}
        </>
      )}

      {view === 'graph' && (
        <>
          <div className="graph-hint">
            <span>Connect nodes to define execution order — drag from a node's right handle to another's left.</span>
            <button className="btn-ghost btn-sm" onClick={() => setView('list')}>← Back to list</button>
          </div>
          <div id="rf-root">
            <FlowGraph
              scripts={scripts}
              onRunScript={(id) => void executeScript(id)}
              onStopScript={(id) => void handleStop(id)}
              statuses={Object.fromEntries(
                scripts.map((s) => [s.id, runningScriptId === s.id ? 'running' : 'idle'])
              )}
            />
          </div>
        </>
      )}

      <LogPanel
        visible={logVisible}
        scriptLabel={logLabel}
        lines={logLines}
        isRunning={runningScriptId !== null}
        onStop={() => runningScriptId && void handleStop(runningScriptId)}
        onClose={() => setLogVisible(false)}
      />

      <ParamsModal
        script={paramsScript}
        onConfirm={handleParamsConfirm}
        onClose={() => setParamsScript(null)}
      />
    </section>
  );
};

export default AutomationPanel;
