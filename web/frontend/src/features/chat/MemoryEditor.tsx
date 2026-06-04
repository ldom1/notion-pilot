import React, { useEffect, useRef, useState } from "react";
import { fetchMemory, saveMemory } from "../../api/client";

interface MemoryEditorProps {
  open: boolean;
  onClose: () => void;
}

export function MemoryEditor({ open, onClose }: MemoryEditorProps): React.ReactElement | null {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedBriefly, setSavedBriefly] = useState(false);
  const savedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!open) return;
    fetchMemory()
      .then((t) => setText(t))
      .catch(() => setText(""));
  }, [open]);

  useEffect(() => {
    return () => {
      if (savedTimerRef.current !== null) {
        clearTimeout(savedTimerRef.current);
      }
    };
  }, []);

  async function handleSave(): Promise<void> {
    if (saving) return;
    setSaving(true);
    try {
      await saveMemory(text);
      setSavedBriefly(true);
      savedTimerRef.current = setTimeout(() => {
        setSavedBriefly(false);
      }, 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={`memory-bar${open ? " open" : ""}`}>
      <div className="memory-bar-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span>Workspace context</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#bbb', fontSize: '0.78rem', padding: '0.1rem 0.3rem', lineHeight: 1 }}
        >
          ✕
        </button>
      </div>
      <p className="memory-hint">
        Tell the AI about your role, product, and target market. This is
        injected into every chat call.
      </p>
      <textarea
        className="memory-textarea"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={6}
        placeholder="e.g. I am a sales rep at Acme selling B2B SaaS to mid-market finance teams..."
      />
      <div className="memory-actions">
        <button
          type="button"
          className="memory-save-btn"
          onClick={handleSave}
          disabled={saving}
        >
          {savedBriefly ? "✓ Saved" : "Save"}
        </button>
      </div>
    </div>
  );
}

export default MemoryEditor;
