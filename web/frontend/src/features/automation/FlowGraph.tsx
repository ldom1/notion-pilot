import React, { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { Script } from '../../api/client';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface FlowGraphProps {
  scripts: Script[];
  onRunScript: (id: string) => void;
  onStopScript: (id: string) => void;
  statuses: Record<string, string>;
}

interface ScriptNodeData extends Record<string, unknown> {
  scriptId: string;
  label: string;
  description: string;
  category: string;
  onRun: (id: string) => void;
  onStop: (id: string) => void;
  status: string;
}

// ─── Custom Node ─────────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ScriptNode = ({ data }: { data: any }) => {
  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
  const { scriptId, label, description, category, onRun, onStop, status } = data as ScriptNodeData;

  const isRunning = status === 'running';
  const isDone = status === 'done';
  const isError = status === 'error';

  const statusClass = isRunning
    ? 'rf-script-node--running'
    : isDone
    ? 'rf-script-node--done'
    : isError
    ? 'rf-script-node--error'
    : '';

  return (
    <div className={`rf-script-node ${statusClass}`}>
      <Handle type="target" position={Position.Top} />

      <div className="rf-script-node__header">
        <span className="rf-script-node__category">{category}</span>
        {isRunning && <span className="rf-script-node__spinner" />}
        {isDone && <span className="rf-script-node__badge rf-script-node__badge--done">done</span>}
        {isError && <span className="rf-script-node__badge rf-script-node__badge--error">error</span>}
      </div>

      <div className="rf-script-node__label">{label}</div>
      <div className="rf-script-node__desc">{description}</div>

      <div className="rf-script-node__actions">
        <button
          className="rf-script-node__btn rf-script-node__btn--run"
          onClick={() => onRun(scriptId)}
          disabled={isRunning}
          title="Run script"
        >
          ▶ Run
        </button>
        <button
          className="rf-script-node__btn rf-script-node__btn--stop"
          onClick={() => onStop(scriptId)}
          disabled={!isRunning}
          title="Stop script"
        >
          ■ Stop
        </button>
      </div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const nodeTypes: NodeTypes = { scriptNode: ScriptNode };

// ─── Layout helper ────────────────────────────────────────────────────────────

function buildInitialNodes(
  scripts: Script[],
  onRun: (id: string) => void,
  onStop: (id: string) => void,
  statuses: Record<string, string>,
): Node<ScriptNodeData>[] {
  const COLS = 3;
  const COL_W = 280;
  const ROW_H = 200;

  return scripts.map((script, i) => ({
    id: script.id,
    type: 'scriptNode',
    position: {
      x: (i % COLS) * COL_W + 40,
      y: Math.floor(i / COLS) * ROW_H + 40,
    },
    data: {
      scriptId: script.id,
      label: script.label,
      description: script.description ?? '',
      category: script.category ?? '',
      onRun,
      onStop,
      status: statuses[script.id] ?? 'idle',
    },
  }));
}

// ─── FlowGraph ────────────────────────────────────────────────────────────────

const FlowGraph: React.FC<FlowGraphProps> = ({
  scripts,
  onRunScript,
  onStopScript,
  statuses,
}) => {
  const initialNodes = useMemo(
    () => buildInitialNodes(scripts, onRunScript, onStopScript, statuses),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scripts],
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [nodes, setNodes, onNodesChange] = useNodesState<any>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Sync live status + callbacks into node data without re-layouting
  React.useEffect(() => {
    setNodes((prev) =>
      prev.map((node) => ({
        ...node,
        data: {
          ...node.data,
          status: statuses[node.data.scriptId] ?? 'idle',
          onRun: onRunScript,
          onStop: onStopScript,
        },
      })),
    );
  }, [statuses, onRunScript, onStopScript, setNodes]);

  const onConnect = useCallback(
    (connection: Connection) =>
      setEdges((eds) => addEdge({ ...connection, type: 'smoothstep' }, eds)),
    [setEdges],
  );

  return (
    <div className="flow-graph-container">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        deleteKeyCode="Delete"
      >
        <Background gap={16} size={1} />
        <Controls />
      </ReactFlow>
    </div>
  );
};

export default FlowGraph;
