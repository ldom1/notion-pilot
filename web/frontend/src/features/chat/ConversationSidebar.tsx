import React from "react";
import { ConversationMeta } from "../../api/client";

interface ConversationSidebarProps {
  conversations: ConversationMeta[];
  currentSessionId: string;
  onLoad: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  });
}

export function ConversationSidebar({
  conversations,
  currentSessionId,
  onLoad,
  onDelete,
  onNew,
}: ConversationSidebarProps): React.ReactElement {
  function handleDelete(
    e: React.MouseEvent<HTMLButtonElement>,
    id: string
  ): void {
    e.stopPropagation();
    if (window.confirm("Delete this conversation?")) {
      onDelete(id);
    }
  }

  return (
    <div className="chat-sidebar">
      <div className="chat-sidebar-label">History</div>

      <div className="conv-list">
        {conversations.length === 0 ? (
          <div className="conv-empty-hint">No history yet</div>
        ) : (
          conversations.map((conv) => (
            <button
              key={conv.id}
              className={`conv-item${conv.id === currentSessionId ? " active" : ""}`}
              onClick={() => onLoad(conv.id)}
              type="button"
            >
              <div className="conv-item-title">{conv.title}</div>
              {conv.preview && (
                <div style={{ fontSize: '0.64rem', color: '#aaa', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: '0.1rem' }}>
                  {conv.preview}
                </div>
              )}
              <div className="conv-item-meta">
                <span>{formatDate(conv.updated_at ?? conv.created_at ?? '')}</span>
                <button
                  className="conv-del"
                  onClick={(e) => handleDelete(e, conv.id)}
                  type="button"
                  aria-label="Delete"
                >
                  ✕
                </button>
              </div>
            </button>
          ))
        )}
      </div>

      <button className="conv-new-btn" onClick={onNew} type="button">
        + New
      </button>
    </div>
  );
}
