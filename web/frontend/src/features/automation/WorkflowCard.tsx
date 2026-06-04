import React from 'react';
import { WorkflowDef } from '../../api/types';

interface WorkflowCardProps {
  workflow: WorkflowDef;
  isRunning: boolean;
  onRun: () => void;
  onDelete: () => void;
}

const WorkflowCard: React.FC<WorkflowCardProps> = ({ workflow, isRunning, onRun, onDelete }) => {
  const stepCount = workflow.nodes.length;

  return (
    <div className="wf-card">
      <div className="wf-card__body">
        <span className="wf-card__icon" aria-hidden="true">⚡</span>
        <div className="wf-card__name">{workflow.name}</div>
        <div className="wf-card__meta">
          {stepCount} {stepCount === 1 ? 'step' : 'steps'}
        </div>
      </div>

      <div className="wf-card__actions">
        <button
          className="btn-ghost"
          onClick={onDelete}
          disabled={isRunning}
          aria-label={`Delete workflow ${workflow.name}`}
        >
          Delete
        </button>
        <button
          className="run-btn"
          onClick={onRun}
          disabled={isRunning}
          aria-label={isRunning ? `${workflow.name} is running` : `Run workflow ${workflow.name}`}
        >
          {isRunning ? '● Running…' : '▶ Run'}
        </button>
      </div>
    </div>
  );
};

export default WorkflowCard;
