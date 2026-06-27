"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { DocumentPanel, flattenDocs } from "@/components/knowledge-bases/DocumentPanel";
import { StudioPanel } from "@/components/knowledge-bases/StudioPanel";
import { AddSourceModal } from "@/components/knowledge-bases/AddSourceModal";
import type { Citation, KnowledgeBase, QaResponse } from "@/lib/types";
import type { SourceNode, FlatDocument } from "@/components/knowledge-bases/DocumentPanel";
import type { StudioSourceDetail } from "@/components/knowledge-bases/StudioPanel";

// ── Placeholder source data ──
const PLACEHOLDER_SOURCES: SourceNode[] = [
  {
    id: "src-1",
    name: "research_paper.pdf",
    type: "upload",
    documents: [
      { id: "doc-1a", sourceId: "src-1", title: "research_paper_v2", version: "v2.0", description: "增强 OCR 文本" },
      { id: "doc-1b", sourceId: "src-1", title: "research_paper_v1", version: "v1.0", description: "基础文本" },
    ],
  },
  {
    id: "src-2",
    name: "tech_notes.md",
    type: "upload",
    documents: [
      { id: "doc-2a", sourceId: "src-2", title: "tech_notes_parsed", version: "v1.0", description: "Markdown 解析" },
    ],
  },
  {
    id: "src-3",
    name: "docs.example.com/kb",
    type: "link",
    documents: [],
  },
];

// ── Message types ──
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  createdAt: string;
}

// ── Message bubble ──
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const initials = isUser ? "U" : "AI";

  return (
    <div className="group flex gap-3 px-6 py-4">
      <div
        className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold ${
          isUser ? "bg-gray-200 text-gray-500" : "bg-[#1A1A1A] text-white"
        }`}
      >
        {initials}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-xs font-medium text-[#2F3437]">
            {isUser ? "You" : "AI"}
          </span>
          <span className="text-[10px] text-gray-300">
            {new Date(message.createdAt).toLocaleTimeString("en-US", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
        <div className="text-sm text-[#2F3437] leading-relaxed whitespace-pre-wrap">
          {message.content}
        </div>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.citations.map((c, i) => (
              <div
                key={`${c.document_id}-${c.chunk_index}`}
                className="text-[11px] text-gray-400 bg-gray-50 rounded-lg px-2.5 py-1.5 border border-gray-100/90"
              >
                <span className="font-medium text-gray-500">[{i + 1}]</span>{" "}
                <span className="text-gray-400">{c.document_title}</span>
                {c.content_snippet && (
                  <span className="text-gray-300 block mt-0.5 line-clamp-1">
                    &ldquo;{c.content_snippet}&rdquo;
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyChat({ hasDocs }: { hasDocs: boolean }) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center">
        <div className="flex justify-center mb-3">
          <svg
            width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"
            className="text-gray-300" aria-hidden="true"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <p className="text-sm text-gray-400 font-medium">
          {hasDocs ? "Start a conversation" : "Select documents to begin"}
        </p>
        <p className="text-xs text-gray-300 mt-1 max-w-xs">
          {hasDocs
            ? "Ask a question to analyze the selected documents with AI."
            : "Check documents from the sidebar to inject them into the AI context."}
        </p>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Page
// ═══════════════════════════════════════════════════════════

export default function WorkspacePage() {
  const params = useParams<{ id: string }>();
  const { addToast } = useToast();
  const kbId = params.id;

  // KB metadata
  const [kbName, setKbName] = useState("");

  // Sources & documents
  const [sources, setSources] = useState<SourceNode[]>([]);
  const [documents, setDocuments] = useState<FlatDocument[]>([]);
  const [checkedDocIds, setCheckedDocIds] = useState<Set<string>>(new Set());

  // Modals
  const [addSourceOpen, setAddSourceOpen] = useState(false);

  // Studio
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);

  // Chat
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Derived: active source for Studio detail view ──
  const activeSource = useMemo<StudioSourceDetail | null>(() => {
    if (!activeSourceId) return null;
    const src = sources.find((s) => s.id === activeSourceId);
    if (!src) return null;
    return {
      id: src.id,
      name: src.name,
      type: src.type,
      createdAt: "2025-03-15T00:00:00Z", // placeholder — real data from API
      documents: src.documents.map((d) => ({
        ...d,
        createdAt: "2025-06-01T00:00:00Z", // placeholder
      })),
    };
  }, [activeSourceId, sources]);

  // Load KB name
  useEffect(() => {
    api<KnowledgeBase>(`/api/v1/knowledge-bases/${kbId}`)
      .then((r) => setKbName(r.data.name))
      .catch(() => {});
  }, [kbId]);

  // Load sources & flatten into documents
  useEffect(() => {
    // TODO: Replace with real API:
    // GET /api/v1/knowledge-bases/:id/sources → GET /api/v1/sources/:id/documents
    const t = setTimeout(() => {
      setSources(PLACEHOLDER_SOURCES);
      setDocuments(flattenDocs(PLACEHOLDER_SOURCES));
    }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll
  // biome-ignore lint/correctness/useExhaustiveDependencies: messages.length triggers scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // ── Handlers ──

  const handleToggleDocument = useCallback((docId: string) => {
    setCheckedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  }, []);

  const handleAddSourceFromModal = useCallback(
    (_type: "upload" | "link", payload: File | string) => {
      // TODO: POST /api/v1/knowledge-bases/:id/sources + upload file
      setAddSourceOpen(false);
      addToast("success", "Source added (placeholder — API not wired)");
    },
    [addToast],
  );

  const handleTraceSource = useCallback((sourceId: string) => {
    setActiveSourceId((prev) => (prev === sourceId ? null : sourceId));
  }, []);

  const handleBackToCapabilities = useCallback(() => {
    setActiveSourceId(null);
  }, []);

  const handleReExtract = useCallback(
    (sourceId: string) => {
      // TODO: POST /api/v1/sources/:id/extract
      addToast("success", "Re-extraction triggered (placeholder)");
    },
    [addToast],
  );

  const handleDeleteSource = useCallback(
    (sourceId: string) => {
      // TODO: DELETE /api/v1/knowledge-bases/:id/sources/:sourceId
      addToast("success", "Source deleted (placeholder)");
    },
    [addToast],
  );

  const handleSend = useCallback(async () => {
    const query = input.trim();
    if (!query || thinking) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: query,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setThinking(true);

    try {
      const result = await api<QaResponse>("/api/v1/qa/ask", {
        method: "POST",
        body: JSON.stringify({ query, knowledge_base_id: kbId, top_k: 10 }),
      });

      const aiMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: result.data.answer,
        citations: result.data.sources,
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to get answer";
      addToast("error", msg);
    } finally {
      setThinking(false);
    }
  }, [input, thinking, kbId, addToast]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const hasDocs = checkedDocIds.size > 0;
  const hasMessages = messages.length > 0;

  return (
    <div className="h-[calc(100vh-3rem)] flex overflow-hidden">
      {/* ══ Left: Document panel ══ */}
      <DocumentPanel
        knowledgeBaseName={kbName}
        documents={documents}
        checkedDocIds={checkedDocIds}
        onToggleDocument={handleToggleDocument}
        onAddSource={() => setAddSourceOpen(true)}
        onTraceSource={handleTraceSource}
      />

      {/* ══ Center: Chat canvas ══ */}
      <div className="flex-1 flex flex-col h-full bg-white min-w-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {hasMessages ? (
            <div className="max-w-[640px] mx-auto py-6">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {thinking && (
                <div className="flex items-center gap-3 px-6 py-4">
                  <div className="w-7 h-7 rounded-full bg-[#1A1A1A] flex items-center justify-center">
                    <span className="text-[11px] font-semibold text-white">AI</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-300 animate-pulse" />
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-300 animate-pulse [animation-delay:0.15s]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-300 animate-pulse [animation-delay:0.3s]" />
                  </div>
                </div>
              )}
            </div>
          ) : (
            <EmptyChat hasDocs={hasDocs} />
          )}
        </div>

        {/* Floating input */}
        <div className="px-6 pb-6 pt-2">
          <div className="max-w-[640px] mx-auto">
            <div
              className={`rounded-xl bg-white border shadow-md transition-all duration-200 ${
                input.length > 0 ? "border-gray-300" : "border-gray-200/80"
              }`}
            >
              <textarea
                ref={inputRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={
                  !hasDocs
                    ? "Select documents from the sidebar to begin…"
                    : "Ask a question about your documents…"
                }
                rows={1}
                className="w-full resize-none rounded-xl px-4 py-3 text-sm text-[#2F3437]
                  placeholder:text-gray-300 outline-none
                  focus:border-gray-400 focus:ring-0
                  transition-colors duration-200
                  bg-transparent"
              />
              <div className="flex items-center justify-between px-3 pb-3">
                <span className="text-[10px] text-gray-300">
                  {!hasDocs
                    ? "No documents selected"
                    : `${checkedDocIds.size} document${checkedDocIds.size === 1 ? "" : "s"} in context`}
                </span>
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={input.trim().length === 0 || thinking || !hasDocs}
                  className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center
                    bg-[#1A1A1A] text-white hover:bg-[#2F3437]
                    transition-all duration-200
                    disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed"
                  aria-label="Send message"
                >
                  {thinking ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                      className="animate-spin" aria-hidden="true">
                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                      strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <line x1="22" y1="2" x2="11" y2="13" />
                      <polygon points="22 2 15 22 11 13 2 9 22 2" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
            <p className="text-[10px] text-gray-300 text-center mt-2">
              Press Enter to send, Shift+Enter for new line
            </p>
          </div>
        </div>
      </div>

      {/* ══ Right: Studio panel ══ */}
      <StudioPanel
        knowledgeBaseName={kbName}
        activeDocCount={checkedDocIds.size}
        activeSource={activeSource}
        onBackToCapabilities={handleBackToCapabilities}
        onReExtract={handleReExtract}
        onDeleteSource={handleDeleteSource}
      />

      {/* ══ Modals ══ */}
      <AddSourceModal
        open={addSourceOpen}
        onClose={() => setAddSourceOpen(false)}
        onAddSource={handleAddSourceFromModal}
      />
    </div>
  );
}
