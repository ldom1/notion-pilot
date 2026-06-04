import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  sendChat,
  fetchConversations,
  loadConversation,
  deleteConversation,
  createDeal,
  createLead,
  fetchDealProperties,
} from "../../api/client";
import type {
  ConversationSummary,
  ConversationMessage,
  DealWizardField,
  SSEEvent,
  ChatRequest,
} from "../../api/client";
import { ConversationSidebar } from "./ConversationSidebar";
import { MemoryEditor } from "./MemoryEditor";
import type { ConversationMeta } from "../../api/client";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Lead {
  type: "existing" | "new";
  name: string;
  position?: string;
  company?: string;
  notion_id?: string;
  reason?: string;
  deal_name?: string;
}

interface ChatResult {
  action: "suggest" | "create" | "info";
  message: string;
  leads: Lead[];
}

interface UiMessage {
  role: "user" | "assistant";
  content: string;
  data?: ChatResult;
  ts?: string;
  /** Streaming-in-progress token accumulator for assistant messages. */
  streaming?: boolean;
}

interface HistoryEntry {
  role: "user" | "assistant";
  content: string;
}

interface DealWizardState {
  lead: Lead;
  fields: DealWizardField[];
  stepIdx: number;
  values: Record<string, string | string[]>;
  confirming: boolean;
  submitting: boolean;
  submitted: boolean;
  notionUrl?: string;
  summary?: string;
  company?: string;
}

// ─── Helper: avatar initials ──────────────────────────────────────────────────

function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

// ─── Lead Card ────────────────────────────────────────────────────────────────

interface LeadCardProps {
  lead: Lead;
  onAddDeal: (lead: Lead) => void;
  onAddLead: (lead: Lead) => void;
}

function LeadCard({ lead, onAddDeal, onAddLead }: LeadCardProps): React.ReactElement {
  const [addingLead, setAddingLead] = useState(false);
  const [addedUrl, setAddedUrl] = useState<string | null>(null);

  async function handleAddLead(): Promise<void> {
    setAddingLead(true);
    try {
      const res = await createLead({
        name: lead.name,
        position: lead.position,
        company: lead.company,
      });
      setAddedUrl(res.url);
      onAddLead(lead);
    } catch (err) {
      console.error("createLead failed", err);
    } finally {
      setAddingLead(false);
    }
  }

  const subtitle = [lead.position, lead.company].filter(Boolean).join(" @ ");

  return (
    <div className="lead-card">
      <div className="lead-avatar">{initials(lead.name)}</div>
      <div className="lead-info">
        <div className="lead-name">{lead.name}</div>
        {subtitle && <div className="lead-sub">{subtitle}</div>}
        {lead.reason && <div className="lead-reason">{lead.reason}</div>}
      </div>
      <span className={`lead-badge ${lead.type}`}>
        {lead.type === "existing" ? "CRM" : "New"}
      </span>
      <div className="lead-action" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', alignItems: 'flex-end' }}>
        {lead.type === "existing" && lead.notion_id && (
          <a
            className="lead-open"
            href={`https://notion.so/${lead.notion_id.replace(/-/g, "")}`}
            target="_blank"
            rel="noreferrer"
          >
            Open ↗
          </a>
        )}
        {lead.type === "existing" && (
          <button type="button" className="lead-add" onClick={() => onAddDeal(lead)}>
            + Lead
          </button>
        )}
        {lead.type === "new" && !addedUrl && (
          <button type="button" className="lead-add" onClick={handleAddLead} disabled={addingLead}>
            {addingLead ? "Adding…" : "+ Add"}
          </button>
        )}
        {lead.type === "new" && addedUrl && (
          <a className="lead-open" href={addedUrl} target="_blank" rel="noreferrer">Open ↗</a>
        )}
      </div>
    </div>
  );
}

// ─── Deal Form Modal ──────────────────────────────────────────────────────────

interface DealWizardProps {
  wizard: DealWizardState;
  onChange: (w: DealWizardState) => void;
  onClose: () => void;
}

function DealWizard({ wizard, onChange, onClose }: DealWizardProps): React.ReactElement {
  function setValue(key: string, value: string | string[]): void {
    onChange({ ...wizard, values: { ...wizard.values, [key]: value } });
  }

  function toggleMulti(key: string, opt: string): void {
    const prev = (wizard.values[key] as string[] | undefined) ?? [];
    const next = prev.includes(opt) ? prev.filter((v) => v !== opt) : [...prev, opt];
    setValue(key, next);
  }

  async function handleSubmit(): Promise<void> {
    if (wizard.submitting || wizard.submitted) return;
    onChange({ ...wizard, submitting: true });
    try {
      const res = await createDeal({
        deal_name: wizard.lead.deal_name ?? `Lead: ${wizard.lead.name}`,
        notion_id: wizard.lead.notion_id,
        extra_fields: wizard.values as Record<string, string | string[] | number>,
        summary: wizard.summary,
        company_name: wizard.company,
      });
      onChange({ ...wizard, submitting: false, submitted: true, notionUrl: res.url });
    } catch (err) {
      console.error("createDeal failed", err);
      onChange({ ...wizard, submitting: false });
    }
  }

  return (
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-box deal-wizard-modal">

        {/* Header */}
        <div className="deal-wizard-header">
          <div>
            <div className="modal-title">New Lead</div>
            <div className="deal-wizard-sub">
              {wizard.lead.name}{wizard.lead.company ? ` · ${wizard.lead.company}` : ""}
            </div>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* Success */}
        {wizard.submitted ? (
          <div className="deal-wizard-success">
            <div className="deal-wizard-success-icon">✓</div>
            <div className="deal-wizard-success-text">Lead created in Notion</div>
            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
              {wizard.notionUrl && (
                <a
                  className="btn-primary"
                  href={wizard.notionUrl}
                  target="_blank"
                  rel="noreferrer"
                  style={{ textDecoration: 'none' }}
                >
                  Open in Notion ↗
                </a>
              )}
              <button type="button" className="modal-cancel-btn" onClick={onClose}>Close</button>
            </div>
          </div>
        ) : (
          <>
            {/* All fields at once */}
            <div className="deal-form-fields">
              {wizard.fields.map((f) => {
                const isMulti = f.type === "multi_select";
                const selectedMulti = (wizard.values[f.key] as string[] | undefined) ?? [];
                const selectedSingle = (wizard.values[f.key] as string | undefined) ?? "";
                const hasOptions = (f.options ?? []).length > 0;

                return (
                  <div key={f.key} className="deal-form-field">
                    <div className="deal-form-label">{f.key}</div>
                    {hasOptions ? (
                      <div className="deal-wizard-options">
                        {(f.options ?? []).map((opt) => (
                          <button
                            key={opt}
                            type="button"
                            className={`deal-wizard-opt${
                              isMulti
                                ? selectedMulti.includes(opt) ? " selected" : ""
                                : selectedSingle === opt ? " selected" : ""
                            }`}
                            onClick={() =>
                              isMulti ? toggleMulti(f.key, opt) : setValue(f.key, opt)
                            }
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <input
                        type={f.type === "number" ? "number" : "text"}
                        className="modal-param-input"
                        placeholder={`Enter ${f.key.toLowerCase()}…`}
                        value={selectedSingle}
                        onChange={(e) => setValue(f.key, e.target.value)}
                      />
                    )}
                  </div>
                );
              })}
            </div>

            <div className="modal-actions">
              <button type="button" className="modal-cancel-btn" onClick={onClose}>Cancel</button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleSubmit}
                disabled={wizard.submitting}
              >
                {wizard.submitting ? "Creating…" : "Create lead"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Message Bubble ───────────────────────────────────────────────────────────

interface MessageBubbleProps {
  msg: UiMessage;
  onAddDeal: (lead: Lead) => void;
  onAddLead: (lead: Lead) => void;
}

function MessageBubble({ msg, onAddDeal, onAddLead }: MessageBubbleProps): React.ReactElement {
  const hasLeads = (msg.data?.leads ?? []).length > 0;

  return (
    <div className={`chat-msg ${msg.role}`}>
      <div className="chat-bubble">
        {msg.content}
        {hasLeads && (
          <div className="leads-grid">
            {(msg.data?.leads ?? []).map((lead, i) => (
              <LeadCard
                key={`${lead.name}-${i}`}
                lead={lead}
                onAddDeal={onAddDeal}
                onAddLead={onAddLead}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Example prompts ─────────────────────────────────────────────────────────

const EXAMPLE_PROMPTS = [
  {
    label: "Generate me 3 leads",
    prompt: "Generate me 3 leads intéressants pour notre produit principal. Pour chaque lead, explique pourquoi il est pertinent.",
  },
  {
    label: "Analyse 3 contacts for this product",
    prompt: "Analyse 3 contacts de notre CRM susceptibles d'être intéressés par notre produit principal. Donne leur profil et une raison concrète.",
  },
] as const;

// ─── Chat Panel ───────────────────────────────────────────────────────────────

export function ChatPanel(): React.ReactElement {
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const [chatHistory, setChatHistory] = useState<HistoryEntry[]>([]);
  const [chatMessages, setChatMessages] = useState<UiMessage[]>([]);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [dealWizard, setDealWizard] = useState<DealWizardState | null>(null);
  const [memoryOpen, setMemoryOpen] = useState(false);

  const historyRef = useRef<HTMLDivElement>(null);

  // ── Load conversation list ───────────────────────────────────────────────

  const reloadConversations = useCallback(async (): Promise<void> => {
    try {
      const list = await fetchConversations();
      // fetchConversations returns ConversationSummary[]; cast to ConversationMeta[]
      setConversations(
        list.map((c: ConversationSummary) => ({
          id: c.id,
          title: c.title,
          created_at: c.created_at,
          updated_at: c.updated_at ?? c.created_at,
          message_count: 0,
        }))
      );
    } catch {
      // non-fatal
    }
  }, []);

  useEffect(() => {
    void reloadConversations();
  }, [reloadConversations]);

  // ── Auto-scroll (scoped to chat-history, never scrolls the page) ────────

  useEffect(() => {
    const el = historyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chatMessages, statusMsg]);

  // ── Load a past conversation ─────────────────────────────────────────────

  async function handleLoadConversation(id: string): Promise<void> {
    try {
      const conv = await loadConversation(id);
      setSessionId(id);
      // Rebuild UiMessage list from stored ConversationMessage[]
      const msgs: UiMessage[] = (conv.messages as ConversationMessage[]).map(
        (m) => ({
          role: m.role,
          content: m.content,
          ts: m.ts,
          data: m.data as ChatResult | undefined,
        })
      );
      setChatMessages(msgs);
      setChatHistory(conv.history);
      setStatusMsg(null);
      setDealWizard(null);
    } catch (err) {
      console.error("Failed to load conversation", err);
    }
  }

  // ── Delete a conversation ────────────────────────────────────────────────

  async function handleDeleteConversation(id: string): Promise<void> {
    try {
      await deleteConversation(id);
      if (id === sessionId) {
        startNewSession();
      }
      await reloadConversations();
    } catch (err) {
      console.error("Failed to delete conversation", err);
    }
  }

  // ── New session ──────────────────────────────────────────────────────────

  function startNewSession(): void {
    setSessionId(crypto.randomUUID());
    setChatHistory([]);
    setChatMessages([]);
    setStatusMsg(null);
    setDealWizard(null);
  }

  // ── Send a message ───────────────────────────────────────────────────────

  async function handleSend(overrideQuery?: string): Promise<void> {
    const query = (overrideQuery ?? inputValue).trim();
    if (!query || sending) return;

    setInputValue("");
    setSending(true);
    setStatusMsg(null);
    setDealWizard(null);

    // Append user bubble
    const userMsg: UiMessage = { role: "user", content: query, ts: new Date().toISOString() };
    setChatMessages((prev) => [...prev, userMsg]);

    let tokenBuffer = "";
    let finalResult: ChatResult | undefined;

    try {
      const req: ChatRequest = {
        query,
        history: chatHistory,
        session_id: sessionId,
      };

      const stream = sendChat(req);

      for await (const event of stream as AsyncIterable<SSEEvent>) {
        if (event.type === "status") {
          setStatusMsg(event.message ?? null);
        } else if (event.type === "log") {
          setStatusMsg(String(event.message ?? ""));
        } else if (event.type === "token") {
          tokenBuffer += String((event as SSEEvent & { content?: string }).content ?? "");
          const captured = tokenBuffer;
          setChatMessages((prev) => {
            const next = [...prev];
            const idx = next.length - 1;
            if (idx >= 0 && next[idx].role === "assistant") {
              next[idx] = { ...next[idx], content: captured };
            }
            return next;
          });
        } else if (event.type === "result") {
          const resultEvent = event as SSEEvent & { data?: Record<string, unknown>; session_id?: string };
          finalResult = resultEvent.data as unknown as ChatResult;
          // Update session id if server assigned one
          if (resultEvent.session_id) {
            setSessionId(resultEvent.session_id);
          }
        } else if (event.type === "error") {
          setStatusMsg(`Error: ${event.message ?? "unknown"}`);
        }
      }

      // Add assistant bubble with final result
      const finalContent = finalResult?.message ?? tokenBuffer;
      if (finalContent || finalResult?.leads?.length) {
        setChatMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: finalContent,
            data: finalResult,
            streaming: false,
            ts: new Date().toISOString(),
          },
        ]);
      }

      // Update LLM history
      setChatHistory((prev) => [
        ...prev,
        { role: "user", content: query },
        { role: "assistant", content: finalContent },
      ]);

      setStatusMsg(null);
      await reloadConversations();
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : "Request failed";
      setStatusMsg(`✗ ${errMsg}`);
    } finally {
      setSending(false);
    }
  }

  // ── Deal wizard trigger ──────────────────────────────────────────────────

  async function handleAddDeal(lead: Lead): Promise<void> {
    try {
      const fields = await fetchDealProperties();
      const wizardFields = fields.filter(
        (f) => ["select", "multi_select", "text", "number"].includes(f.type)
      );
      // Find the last assistant message that mentioned this lead as context
      const lastAssistant = [...chatMessages].reverse().find(
        (m) => m.role === "assistant" && m.content
      );
      const summary = lastAssistant?.content ?? undefined;
      setDealWizard({
        lead,
        fields: wizardFields,
        stepIdx: 0,
        values: {},
        confirming: false,
        submitting: false,
        submitted: false,
        summary,
        company: lead.company,
      });
    } catch (err) {
      console.error("fetchDealProperties failed", err);
    }
  }

  function handleAddLead(_lead: Lead): void {
    // Lead card handles creation; this is for parent state updates if needed
  }

  // ── Keyboard handler ─────────────────────────────────────────────────────

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>): void {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <section className="panel">
      <div className="panel-header">
        <span className="panel-title">Ask your data</span>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={() => setMemoryOpen((v) => !v)}
          >
            ✎ Context
          </button>
          <button
            type="button"
            className="chat-clear-btn"
            onClick={startNewSession}
          >
            + New
          </button>
        </div>
      </div>

      {/* Memory editor full-width below header */}
      <MemoryEditor open={memoryOpen} onClose={() => setMemoryOpen(false)} />

      <div className="chat-container">
        <ConversationSidebar
          conversations={conversations}
          currentSessionId={sessionId}
          onLoad={(id) => void handleLoadConversation(id)}
          onDelete={(id) => void handleDeleteConversation(id)}
          onNew={startNewSession}
        />

        <div className="chat-main">

          <div className="chat-history" ref={historyRef}>
            {chatMessages.length === 0 && (
              <div className="chat-empty">
                <p>Ask anything about your Notion databases — find leads, analyse contacts, get suggestions.</p>
                <div className="chat-examples">
                  {EXAMPLE_PROMPTS.map((ex) => (
                    <button
                      key={ex.label}
                      type="button"
                      className="chat-example-btn"
                      onClick={() => void handleSend(ex.prompt)}
                      disabled={sending}
                    >
                      {ex.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {chatMessages.map((msg, i) => (
              <MessageBubble
                key={i}
                msg={msg}
                onAddDeal={(lead) => void handleAddDeal(lead)}
                onAddLead={handleAddLead}
              />
            ))}
            {statusMsg && <div className="chat-status">{statusMsg}</div>}
          </div>

          {dealWizard && (
            <DealWizard
              wizard={dealWizard}
              onChange={setDealWizard}
              onClose={() => setDealWizard(null)}
            />
          )}

          <div className="chat-input-row">
            <input
              type="text"
              className="chat-input"
              placeholder="J'essaye de vendre Artelys Crystal HPC, trouve moi 3 leads…"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sending}
            />
            <button
              type="button"
              className="btn-primary"
              onClick={() => void handleSend()}
              disabled={sending || !inputValue.trim()}
            >
              {sending ? "…" : "Send"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

export default ChatPanel;
