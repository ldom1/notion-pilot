import React, { useEffect, useRef } from 'react';

export interface LogLine {
  text: string;
  cls: 'cmd' | 'done' | 'err' | '';
}

interface LogPanelProps {
  visible: boolean;
  scriptLabel: string;
  lines: LogLine[];
  isRunning: boolean;
  onStop: () => void;
  onClose: () => void;
}

const LogPanel: React.FC<LogPanelProps> = ({
  visible,
  scriptLabel,
  lines,
  isRunning,
  onStop,
  onClose,
}) => {
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [lines]);

  if (!visible) {
    return null;
  }

  return (
    <div className="log-wrap">
      <div className="log-hdr">
        <span className="log-label">{scriptLabel}</span>
        {isRunning && <span className="log-spinner" aria-label="Running" />}
        {isRunning && (
          <button
            onClick={onStop}
            style={{ marginLeft: 'auto', background: '#dc2626', color: '#fff', border: 'none', fontSize: '0.72rem', fontWeight: 700, padding: '0.25rem 0.65rem', borderRadius: '4px', cursor: 'pointer' }}
          >
            ■ Stop
          </button>
        )}
        <button
          onClick={onClose}
          style={{ background: 'none', border: '1px solid #444', color: '#666', fontSize: '0.72rem', padding: '0.25rem 0.55rem', borderRadius: '4px', cursor: 'pointer', marginLeft: isRunning ? '0.35rem' : 'auto' }}
          aria-label="Close"
        >
          ✕
        </button>
      </div>
      <div className="log-body" ref={bodyRef}>
        {lines.map((line, i) => (
          <div key={i} className={`log-line${line.cls ? ` ${line.cls}` : ''}`}>
            {line.text}
          </div>
        ))}
      </div>
    </div>
  );
};

export default LogPanel;
