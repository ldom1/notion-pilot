import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Script, ScriptParam } from '../../api/client';

interface ParamsModalProps {
  script: Script | null;
  onConfirm: (extraArgs: string[]) => void;
  onClose: () => void;
}

type ParamValues = Record<string, string | number | boolean>;

function buildExtraArgs(params: ScriptParam[], values: ParamValues): string[] {
  const args: string[] = [];
  for (const param of params) {
    const value = values[param.id];
    if (param.type === 'boolean' || param.type === 'checkbox') {
      if (value === true) {
        args.push(param.flag);
      }
    } else if (param.type === 'number') {
      const num = Number(value);
      if (value !== '' && value !== undefined && num !== 0) {
        args.push(`${param.flag}=${num}`);
      }
    } else {
      if (value !== '' && value !== undefined) {
        args.push(`${param.flag}=${value}`);
      }
    }
  }
  return args;
}

function initValues(params: ScriptParam[]): ParamValues {
  const values: ParamValues = {};
  for (const param of params) {
    if (param.default !== undefined) {
      values[param.id] = param.default;
    } else if (param.type === 'boolean' || param.type === 'checkbox') {
      values[param.id] = false;
    } else if (param.type === 'number') {
      values[param.id] = 0;
    } else {
      values[param.id] = '';
    }
  }
  return values;
}

const ParamsModal: React.FC<ParamsModalProps> = ({ script, onConfirm, onClose }) => {
  const [values, setValues] = useState<ParamValues>({});
  const firstInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (script?.params) {
      setValues(initValues(script.params));
    } else {
      setValues({});
    }
  }, [script]);

  useEffect(() => {
    if (script) {
      setTimeout(() => firstInputRef.current?.focus(), 50);
    }
  }, [script]);

  const handleConfirm = useCallback(() => {
    if (!script) return;
    const extraArgs = buildExtraArgs(script.params ?? [], values);
    onConfirm(extraArgs);
  }, [script, values, onConfirm]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleConfirm();
      } else if (e.key === 'Escape') {
        onClose();
      }
    },
    [handleConfirm, onClose]
  );

  const setValue = (id: string, val: string | number | boolean) => {
    setValues((prev) => ({ ...prev, [id]: val }));
  };

  if (!script) return null;

  const params = script.params ?? [];

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-label={`Parameters for ${script.label}`}
    >
      <div
        className="modal-box"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-title">{script.label}</div>

        {params.length === 0 ? (
          <p style={{ color: "#aaa", fontSize: "0.82rem" }}>No parameters required.</p>
        ) : (
          <div className="modal-param">
            {params.map((param, idx) => (
              <div className="modal-param" key={param.id}>
                {param.type === 'boolean' || param.type === 'checkbox' ? (
                  <>
                    <label className="modal-param-label">
                      <input
                        ref={idx === 0 ? firstInputRef : undefined}
                        type="checkbox"
                        checked={Boolean(values[param.id])}
                        onChange={(e) => setValue(param.id, e.target.checked)}
                        onKeyDown={handleKeyDown}
                      />
                      {param.label}
                    </label>
                    {param.help && <div className="modal-info">{param.help}</div>}
                  </>
                ) : param.type === 'number' ? (
                  <>
                    <label className="modal-param-label" htmlFor={`param-${param.id}`}>
                      {param.label}
                    </label>
                    <input
                      ref={idx === 0 ? firstInputRef : undefined}
                      id={`param-${param.id}`}
                      type="number"
                      className="modal-param-input"
                      value={values[param.id] as number}
                      min={param.min}
                      max={param.max}
                      onChange={(e) => setValue(param.id, e.target.valueAsNumber)}
                      onKeyDown={handleKeyDown}
                    />
                    {param.help && <div className="modal-info">{param.help}</div>}
                  </>
                ) : (
                  <>
                    <label className="modal-param-label" htmlFor={`param-${param.id}`}>
                      {param.label}
                    </label>
                    <input
                      ref={idx === 0 ? firstInputRef : undefined}
                      id={`param-${param.id}`}
                      type="text"
                      className="modal-param-input"
                      value={values[param.id] as string}
                      placeholder={param.default !== undefined ? String(param.default) : ''}
                      onChange={(e) => setValue(param.id, e.target.value)}
                      onKeyDown={handleKeyDown}
                    />
                    {param.help && <div className="modal-info">{param.help}</div>}
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="modal-actions">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleConfirm}>
            &#9654; Run
          </button>
        </div>
      </div>
    </div>
  );
};

export default ParamsModal;
