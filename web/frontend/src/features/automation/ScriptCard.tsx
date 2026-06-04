import React from 'react';
import { Script } from '../../api/types';

interface ScriptCardProps {
  script: Script;
  isRunning: boolean;
  onRun: () => void;
  onStop: () => void;
}

const ScriptCard: React.FC<ScriptCardProps> = ({ script, isRunning, onRun, onStop }) => {
  return (
    <div className="script-card">
      <div className="script-card__body">
        <span className="script-card__badge">{script.category}</span>
        <div className="script-card__name">{script.label}</div>
        <div className="script-card__description">{script.description}</div>
      </div>

      <div className="script-card__footer">
        {isRunning && (
          <button
            className="stop-btn"
            onClick={onStop}
            aria-label={`Stop ${script.label}`}
          >
            &#9632; Stop
          </button>
        )}
        <button
          className="run-btn"
          onClick={onRun}
          disabled={isRunning}
          aria-label={isRunning ? `${script.label} is running` : `Run ${script.label}`}
        >
          {isRunning ? '● Running…' : '▶ Run'}
        </button>
      </div>
    </div>
  );
};

export default ScriptCard;
