"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  api,
  apiPaginated,
  presignSourceUpload,
  completeSourceUpload,
  uploadToPresignedUrl,
  getContentType,
  listSourceDocuments,
  listKnowledgeBaseDocuments,
  getDocumentChunks,
  sendMessageStream,
  listSessions,
  getSession,
  renameSession,
  deleteSession,
} from "@/lib/api";
import { parseSSEStream } from "@/lib/sse";
import { useToast } from "@/hooks/useToast";
import { usePanelResize } from "@/hooks/usePanelResize";
import { LeftSidebar } from "@/components/knowledge-bases/LeftSidebar";
import { DetailPanel } from "@/components/knowledge-bases/DetailPanel";
import { AddSourceModal } from "@/components/knowledge-bases/AddSourceModal";
import { SessionBar } from "@/components/knowledge-bases/SessionBar";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { flattenDocs } from "@/lib/types";
import type {
  Citation,
  Document,
  DocumentDetail,
  FlatDocument,
  KnowledgeBase,
  PanelState,
  SessionItem,
  Source,
  SourceNode,
  StreamEvent,
} from "@/lib/types";
import type { DetailSourceDetail } from "@/components/knowledge-bases/DetailPanel";

// ── Message types ──
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  createdAt: string;
}

// ── Shared chat area (used in both normal and maximized layouts) ──

interface ChatAreaProps {
  panelMode: "normal" | "maximized";
  isDragging: boolean;
  hasMessages: boolean;
  messages: ChatMessage[];
  chatStatus: "idle" | "thinking" | "streaming" | "error";
  hasDocs: boolean;
  input: string;
  checkedDocIds: Set<string>;
  scrollRef: React.RefObject<HTMLDivElement | null>;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  onInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSend: () => void;
  onStop: () => void;
  width?: number;
  sessionBar?: React.ReactNode;
}

function ChatArea({
  panelMode,
  isDragging,
  hasMessages,
  messages,
  chatStatus,
  hasDocs,
  input,
  checkedDocIds,
  scrollRef,
  inputRef,
  onInputChange,
  onKeyDown,
  onSend,
  onStop,
  width,
  sessionBar,
}: ChatAreaProps) {
  const isMaximized = panelMode === "maximized";
  const isBusy = chatStatus === "thinking" || chatStatus === "streaming";

  return (
    <div
      className={`flex flex-col h-full bg-white ${
        isMaximized ? "shrink-0 border-l border-gray-200" : "flex-1 min-w-[360px]"
      } ${!isDragging ? "transition-all duration-300 ease-in-out" : ""}`}
      style={isMaximized && width ? { width } : undefined}
    >
      {sessionBar}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {hasMessages ? (
          <div className={isMaximized ? "py-4 px-3" : "mx-auto py-6 px-4"}>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {chatStatus === "thinking" && (
              <div className={`flex items-center gap-3 ${isMaximized ? "px-2 py-3" : "px-6 py-4"}`}>
                <div
                  className={`rounded-full bg-[#1A1A1A] flex items-center justify-center shrink-0 ${
                    isMaximized ? "w-6 h-6" : "w-7 h-7"
                  }`}
                >
                  <span
                    className={`font-semibold text-white ${isMaximized ? "text-[10px]" : "text-[11px]"}`}
                  >
                    AI
                  </span>
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

      {/* Input area */}
      <div className={isMaximized ? "px-2 pb-3 pt-1" : "px-6 pb-6 pt-2"}>
        <div className={isMaximized ? "" : "mx-auto"}>
          <div
            className={`bg-white border transition-all duration-200 ${
              isMaximized ? "rounded-lg" : "rounded-xl shadow-md"
            } ${input.length > 0 ? "border-gray-300" : "border-gray-200/80"}`}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={onInputChange}
              onKeyDown={onKeyDown}
              placeholder={
                !hasDocs
                  ? isMaximized
                    ? "Select documents…"
                    : "Select documents from the sidebar to begin…"
                  : isMaximized
                    ? "Ask a question…"
                    : "Ask a question about your documents…"
              }
              rows={1}
              className={`w-full resize-none rounded-xl px-4 py-3 text-sm text-[#2F3437]
                placeholder:text-gray-300 outline-none
                focus:border-gray-400 focus:ring-0
                transition-colors duration-200
                bg-transparent`}
            />
            <div
              className={`flex items-center justify-between ${isMaximized ? "px-2 pb-2" : "px-3 pb-3"}`}
            >
              <span
                className={isMaximized ? "text-[9px] text-gray-300" : "text-[10px] text-gray-300"}
              >
                {!hasDocs
                  ? isMaximized
                    ? "No docs"
                    : "No documents selected"
                  : `${checkedDocIds.size} document${checkedDocIds.size === 1 ? "" : "s"} in context`}
              </span>
              {chatStatus === "streaming" ? (
                <button
                  type="button"
                  onClick={onStop}
                  className={`flex items-center justify-center bg-[#1A1A1A] text-white hover:bg-[#2F3437]
                    transition-all duration-200 ${
                      isMaximized ? "w-6 h-6 rounded-md shrink-0" : "w-8 h-8 rounded-lg shrink-0"
                    }`}
                  aria-label="Stop generating"
                >
                  <svg
                    width={isMaximized ? 9 : 11}
                    height={isMaximized ? 9 : 11}
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    aria-hidden="true"
                  >
                    <rect x="4" y="4" width="16" height="16" rx="2" />
                  </svg>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onSend}
                  disabled={input.trim().length === 0 || isBusy}
                  className={`flex items-center justify-center bg-[#1A1A1A] text-white hover:bg-[#2F3437]
                    transition-all duration-200
                    disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed ${
                      isMaximized ? "w-6 h-6 rounded-md shrink-0" : "w-8 h-8 rounded-lg shrink-0"
                    }`}
                  aria-label="Send message"
                >
                  <svg
                    width={isMaximized ? 11 : 14}
                    height={isMaximized ? 11 : 14}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              )}
            </div>
          </div>
          {!isMaximized && (
            <p className="text-[10px] text-gray-300 text-center mt-2">
              Press Enter to send, Shift+Enter for new line
            </p>
          )}
        </div>
      </div>
    </div>
  );
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
          <span className="text-xs font-medium text-[#2F3437]">{isUser ? "You" : "AI"}</span>
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
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-gray-300"
            aria-hidden="true"
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
  const router = useRouter();
  const searchParams = useSearchParams();
  const { addToast } = useToast();
  const kbId = params.id;

  // KB metadata
  const [kbName, setKbName] = useState("");

  // Sources (real API)
  const [sources, setSources] = useState<Source[]>([]);
  const [sourcesFirstLoad, setSourcesFirstLoad] = useState(true);
  const [sourcesError, setSourcesError] = useState("");

  // Documents (loaded per-source, keyed by source_id)
  const [documentsBySource, setDocumentsBySource] = useState<Record<string, Document[]>>({});

  // Orphaned documents (source deleted, source_id = null)
  const [orphanedDocuments, setOrphanedDocuments] = useState<Document[]>([]);

  // Upload
  const [uploading, setUploading] = useState(false);
  const [uploadStage, setUploadStage] = useState("");

  // Delete source
  const [deleteSourceId, setDeleteSourceId] = useState<string | null>(null);
  const [deletingSource, setDeletingSource] = useState(false);

  // Delete document
  const [deleteDocumentId, setDeleteDocumentId] = useState<string | null>(null);
  const [documentTitleToDelete, setDocumentTitleToDelete] = useState("");
  const [deletingDocument, setDeletingDocument] = useState(false);

  // Re-extract
  const [extractingSourceId, setExtractingSourceId] = useState<string | null>(null);

  // Documents & selection
  const [checkedDocIds, setCheckedDocIds] = useState<Set<string>>(new Set());

  // Modals
  const [addSourceOpen, setAddSourceOpen] = useState(false);

  // Studio
  const [panelState, setPanelState] = useState<PanelState>({ type: "empty" });

  // Document cache + loading
  const documentCacheRef = useRef<Map<string, DocumentDetail>>(new Map());
  const [documentCache, setDocumentCache] = useState<Map<string, DocumentDetail>>(new Map());
  const [loadingDocument, setLoadingDocument] = useState(false);
  const [documentError, setDocumentError] = useState("");

  // Chat
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [chatStatus, setChatStatus] = useState<"idle" | "thinking" | "streaming" | "error">("idle");
  const abortControllerRef = useRef<AbortController | null>(null);
  const streamingMsgIdRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Sessions
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(true);

  // ── Layout: panel resizing & modes ──
  type PanelMode = "normal" | "maximized";
  const [panelMode, setPanelMode] = useState<PanelMode>("normal");
  const {
    width: rightPanelWidth,
    isDragging: isDraggingRight,
    dragHandleProps,
  } = usePanelResize(400);
  // Second resize hook for the chat sidebar width in maximized mode
  const {
    width: chatSidebarWidth,
    isDragging: isDraggingChat,
    dragHandleProps: chatDragHandleProps,
  } = usePanelResize(340);
  const isDragging = isDraggingRight || isDraggingChat;

  // ── Derived: SourceNode[] ──
  const sourceNodes = useMemo<SourceNode[]>(() => {
    return sources.map((s) => {
      const config = s.config as Record<string, unknown> | null;
      const name = (config?.original_name as string) ?? `Source ${s.id.slice(0, 8)}`;
      const docs = documentsBySource[s.id] ?? [];
      return {
        id: s.id,
        name,
        type: (s.type as "upload") ?? "upload",
        status: s.status,
        documents: docs.map((d) => ({
          id: d.id,
          sourceId: s.id,
          title: d.title,
          version: "v1",
          description: `${d.source_format} document`,
          status: d.status,
          chunkStatus: d.chunk_status,
          embedStatus: d.embed_status,
        })),
      };
    });
  }, [sources, documentsBySource]);

  const documents = useMemo<FlatDocument[]>(() => {
    const fromSources = flattenDocs(sourceNodes);
    const orphans: FlatDocument[] = orphanedDocuments.map((d) => ({
      id: d.id,
      sourceId: undefined,
      sourceName: undefined,
      sourceType: undefined,
      title: d.title,
      version: "v1",
      description: `${d.source_format} document`,
      status: d.status,
      chunkStatus: d.chunk_status,
      embedStatus: d.embed_status,
    }));
    return [...fromSources, ...orphans];
  }, [sourceNodes, orphanedDocuments]);

  // ── Restore document selection from session.reference_document_ids ──
  // Called after loading a session's detail.
  // reference_document_ids: null → select all; [] → none; [...] → just those.
  const restoreDocSelection = useCallback(
    (detail: { reference_document_ids: string[] | null }) => {
      if (detail.reference_document_ids === null) {
        // NULL = all documents selected (default)
        setCheckedDocIds(new Set(documents.map((d) => d.id)));
      } else if (detail.reference_document_ids.length === 0) {
        setCheckedDocIds(new Set());
      } else {
        setCheckedDocIds(new Set(detail.reference_document_ids));
      }
    },
    [documents],
  );

  // ── Derived: active source for Studio detail view ──
  const activeSource = useMemo<DetailSourceDetail | null>(() => {
    if (panelState.type !== "source") return null;
    const src = sources.find((s) => s.id === panelState.sourceId);
    if (!src) return null;
    const config = src.config as Record<string, unknown> | null;
    const name = (config?.original_name as string) ?? `Source ${src.id.slice(0, 8)}`;
    const docs = documentsBySource[src.id] ?? [];
    return {
      id: src.id,
      name,
      type: src.type as "upload" | "link",
      status: src.status,
      createdAt: src.created_at,
      documents: docs.map((d) => ({
        id: d.id,
        title: d.title,
        version: "v1",
        description: `${d.source_format} document`,
        status: d.status,
        chunkStatus: d.chunk_status,
        embedStatus: d.embed_status,
        createdAt: d.created_at,
      })),
    };
  }, [panelState, sources, documentsBySource]);

  // ── Derived: active document from cache ──
  const activeDocument = useMemo<DocumentDetail | null>(() => {
    if (panelState.type !== "document") return null;
    return documentCache.get(panelState.documentId) ?? null;
  }, [panelState, documentCache]);

  // ── Load KB name ──
  useEffect(() => {
    api<KnowledgeBase>(`/api/v1/knowledge-bases/${kbId}`)
      .then((r) => setKbName(r.data.name))
      .catch(() => {});
  }, [kbId]);

  // ── Load sources + documents from API ──
  const loadSources = useCallback(async () => {
    setSourcesError("");
    try {
      const result = await apiPaginated<Source>(
        `/api/v1/knowledge-bases/${kbId}/sources?page=1&page_size=50`,
      );
      setSources(result.data);

      // Load documents for all sources in parallel
      const bySource: Record<string, Document[]> = {};
      if (result.data.length > 0) {
        const docResults = await Promise.all(
          result.data.map(async (s) => {
            try {
              const docs = await listSourceDocuments(s.id);
              return { sourceId: s.id, docs };
            } catch {
              return { sourceId: s.id, docs: [] as Document[] };
            }
          }),
        );
        for (const { sourceId, docs } of docResults) {
          bySource[sourceId] = docs;
        }
        setDocumentsBySource(bySource);
      }

      // Fetch KB-level documents to catch orphans (source deleted)
      try {
        const kbDocs = await listKnowledgeBaseDocuments(kbId);
        const allSourceDocIds = new Set(
          Object.values(bySource)
            .flat()
            .map((d) => d.id),
        );
        const orphaned = kbDocs.filter((d) => d.source_id === null && !allSourceDocIds.has(d.id));
        setOrphanedDocuments(orphaned);
      } catch {
        setOrphanedDocuments([]);
      }
    } catch (err) {
      setSourcesError(err instanceof Error ? err.message : "Failed to load sources");
    } finally {
      setSourcesFirstLoad(false);
    }
  }, [kbId]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  // ── Smart polling: refresh while any docs are in a transitional state ──
  // Terminal statuses: "ready" | "failed". Non-terminal: "pending" | "processing".
  // Also polls when an active source has zero documents (pipeline hasn't created them yet).
  useEffect(() => {
    if (sourcesFirstLoad) return;

    const hasTransitionalDoc = Object.values(documentsBySource).some((docs) =>
      docs.some((d) => d.status === "pending" || d.status === "processing"),
    );

    const hasEmptyActiveSource = sources.some(
      (s) => s.status === "active" && (documentsBySource[s.id] ?? []).length === 0,
    );

    if (!hasTransitionalDoc && !hasEmptyActiveSource) return;

    const interval = setInterval(() => {
      loadSources();
    }, 2000);

    return () => clearInterval(interval);
  }, [sourcesFirstLoad, documentsBySource, sources, loadSources]);

  // ── Default to select-all when no session is active ──
  const initialSelectDone = useRef(false);

  useEffect(() => {
    if (initialSelectDone.current) return;
    if (sourcesFirstLoad || activeSessionId !== null || documents.length === 0) return;
    initialSelectDone.current = true;
    setCheckedDocIds(new Set(documents.map((d) => d.id)));
  }, [sourcesFirstLoad, documents, activeSessionId]);

  // ── Auto-scroll chat ──
  const isNearBottomRef = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const handleScroll = () => {
      isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    };
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  // biome-ignore lint/correctness/useExhaustiveDependencies: messages changes trigger scroll on tokens
  useEffect(() => {
    if (scrollRef.current && isNearBottomRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // ── Sessions: load on mount ──
  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const result = await listSessions(kbId);
      setSessions(result.data);
      return result.data;
    } catch {
      return [] as SessionItem[];
    } finally {
      setSessionsLoading(false);
    }
  }, [kbId]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: loadSessions/searchParams stable; mount-only init
  useEffect(() => {
    loadSessions().then((sessionsList) => {
      // Restore from URL query param
      const urlSessionId = searchParams.get("session");
      if (urlSessionId && sessionsList.some((s) => s.id === urlSessionId)) {
        handleSelectSessionById(urlSessionId);
      } else if (sessionsList.length > 0) {
        handleSelectSession(sessionsList[0]);
      }
    });
  }, []);

  // ── Select session by ID (from URL) ──
  const handleSelectSessionById = useCallback(
    async (sessionId: string) => {
      try {
        const detail = await getSession(kbId, sessionId);
        const msgs: ChatMessage[] = detail.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          citations: m.citations ?? undefined,
          createdAt: m.created_at,
        }));
        setMessages(msgs);
        setActiveSessionId(sessionId);
        restoreDocSelection(detail);
      } catch {
        // Session may have been deleted; clear selection
        setActiveSessionId(null);
        setMessages([]);
      }
    },
    [kbId, restoreDocSelection],
  );

  // ── Select session ──
  const handleSelectSession = useCallback(
    async (session: SessionItem) => {
      router.replace(`/knowledge-bases/${kbId}?session=${session.id}`, {
        scroll: false,
      });
      try {
        const detail = await getSession(kbId, session.id);
        const msgs: ChatMessage[] = detail.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          citations: m.citations ?? undefined,
          createdAt: m.created_at,
        }));
        setMessages(msgs);
        setActiveSessionId(session.id);
        restoreDocSelection(detail);
      } catch {
        addToast("error", "Failed to load session");
      }
    },
    [kbId, addToast, router, restoreDocSelection],
  );

  // ── New Chat (clear state, no API call) ──
  const handleNewChat = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    initialSelectDone.current = false;
    setCheckedDocIds(new Set(documents.map((d) => d.id)));
    router.replace(`/knowledge-bases/${kbId}`, { scroll: false });
  }, [kbId, router, documents]);

  // ── Rename session ──
  const handleRenameSession = useCallback(
    async (sessionId: string, title: string) => {
      try {
        const updated = await renameSession(kbId, sessionId, title);
        setSessions((prev) =>
          prev.map((s) => (s.id === sessionId ? { ...s, title: updated.title } : s)),
        );
      } catch {
        addToast("error", "Failed to rename session");
      }
    },
    [kbId, addToast],
  );

  // ── Delete session ──
  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      try {
        await deleteSession(kbId, sessionId);
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (activeSessionId === sessionId) {
          setActiveSessionId(null);
          setMessages([]);
          router.replace(`/knowledge-bases/${kbId}`, { scroll: false });
        }
        addToast("success", "Chat deleted");
      } catch {
        addToast("error", "Failed to delete session");
      }
    },
    [kbId, activeSessionId, addToast, router],
  );

  // Persist document scope to session
  const persistDocumentScope = useCallback(
    (ids: Set<string>) => {
      if (!activeSessionId) return;
      const arr = Array.from(ids);
      // NULL if all selected, else the array
      const totalDocs = documents.length;
      const reference_document_ids = ids.size === totalDocs && totalDocs > 0 ? null : arr;
      api(`/api/v1/knowledge-bases/${kbId}/sessions/${activeSessionId}`, {
        method: "PATCH",
        body: JSON.stringify({ reference_document_ids }),
      }).catch(() => {});
    },
    [activeSessionId, kbId, documents],
  );

  // ── Handlers ──

  const handleToggleDocument = useCallback(
    (docId: string) => {
      setCheckedDocIds((prev) => {
        const next = new Set(prev);
        if (next.has(docId)) next.delete(docId);
        else next.add(docId);
        persistDocumentScope(next);
        return next;
      });
    },
    [persistDocumentScope],
  );

  const handleToggleAll = useCallback(
    (selectAll: boolean) => {
      setCheckedDocIds(() => {
        const next = selectAll ? new Set(documents.map((d) => d.id)) : new Set<string>();
        persistDocumentScope(next);
        return next;
      });
    },
    [documents, persistDocumentScope],
  );

  // Upload flow: create source → presign → browser-to-MinIO → complete → reload
  const handleAddSourceFromModal = useCallback(
    async (file: File) => {
      setAddSourceOpen(false);
      setUploading(true);

      try {
        // Step 1: Create source (pending)
        setUploadStage("Creating source...");
        const created = await api<Source>(`/api/v1/knowledge-bases/${kbId}/sources`, {
          method: "POST",
          body: JSON.stringify({ type: "upload", config: null }),
        });

        // Show pending source in list immediately
        await loadSources();

        // Step 2: Get presigned URL
        setUploadStage("Preparing upload...");
        const contentType = getContentType(file.name);
        const presignResult = await presignSourceUpload(created.data.id, file.name, contentType);

        // Step 3: Upload directly to MinIO (bypasses backend)
        setUploadStage("Uploading file...");
        await uploadToPresignedUrl(presignResult.upload_url, presignResult.upload_fields, file);

        // Step 4: Notify backend to validate and trigger indexing.
        // /complete synchronously transitions source pending → active in the DB.
        setUploadStage("Processing...");
        await completeSourceUpload(created.data.id, {
          bucket: presignResult.bucket,
          object_key: presignResult.object_key,
        });
        addToast("success", `"${file.name}" uploaded. Indexing...`);
        await loadSources();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        addToast("error", msg);
        await loadSources();
      } finally {
        setUploading(false);
        setUploadStage("");
      }
    },
    [kbId, addToast, loadSources],
  );

  const handleTraceSource = useCallback((sourceId: string) => {
    setPanelState({ type: "source", sourceId });
  }, []);

  const handleBack = useCallback(() => {
    setPanelState({ type: "empty" });
    // Reset panel mode to normal when navigating away from document/source views
    setPanelMode("normal");
  }, []);

  // Select document — show content in right panel
  const handleSelectDocument = useCallback(async (docId: string) => {
    setPanelState({ type: "document", documentId: docId });
    setDocumentError("");

    // Cache hit — render immediately
    if (documentCacheRef.current.has(docId)) {
      // Force re-render so activeDocument picks up from cache
      setDocumentCache(new Map(documentCacheRef.current));
      return;
    }

    setLoadingDocument(true);
    try {
      const detail = await getDocumentChunks(docId);
      documentCacheRef.current.set(docId, detail);
      setDocumentCache(new Map(documentCacheRef.current));
    } catch (err) {
      setDocumentError(err instanceof Error ? err.message : "Failed to load document");
      documentCacheRef.current.delete(docId);
    } finally {
      setLoadingDocument(false);
    }
  }, []);

  // Retry loading a document that failed
  const handleRetryDocument = useCallback(() => {
    if (panelState.type !== "document") return;
    const docId = panelState.documentId;
    documentCacheRef.current.delete(docId);
    setDocumentCache(new Map(documentCacheRef.current));
    handleSelectDocument(docId);
  }, [panelState, handleSelectDocument]);

  // ── Panel mode handlers (maximize / restore) ──

  const handleMaximizePanel = useCallback(() => {
    setPanelMode("maximized");
  }, []);

  const handleRestorePanel = useCallback(() => {
    setPanelMode("normal");
  }, []);

  // ── Auto-reset panel mode when navigating away from a document ──
  // Prevents layout deadlock: if user is in maximized mode and clicks "Back", reset to normal
  // clicks "Back" or switches to source view, reset to normal layout.
  useEffect(() => {
    if (panelState.type !== "document" && panelMode !== "normal") {
      setPanelMode("normal");
    }
  }, [panelState.type, panelMode]);

  // Re-extract flow
  const handleReExtract = useCallback(
    async (sourceId: string) => {
      setExtractingSourceId(sourceId);
      try {
        await api(`/api/v1/sources/${sourceId}/extract`, { method: "POST" });
        addToast("success", "Re-extraction started");
        await loadSources();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Re-extraction failed";
        addToast("error", msg);
      } finally {
        setExtractingSourceId(null);
      }
    },
    [addToast, loadSources],
  );

  // Delete: open confirm modal
  const handleDeleteSource = useCallback((sourceId: string) => {
    setDeleteSourceId(sourceId);
  }, []);

  // Delete: execute
  const confirmDeleteSource = useCallback(async () => {
    if (!deleteSourceId) return;
    setDeletingSource(true);
    try {
      await api(`/api/v1/sources/${deleteSourceId}`, { method: "DELETE" });
      addToast("success", "Source deleted. Documents preserved in knowledge base.");
      setDeleteSourceId(null);
      setPanelState({ type: "empty" });
      // Reload — source disappears, its documents reappear as orphaned
      await loadSources();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      addToast("error", msg);
    } finally {
      setDeletingSource(false);
    }
  }, [deleteSourceId, addToast, loadSources]);

  // Delete document: open confirm modal (called from sidebar trash icon or header dropdown)
  const handleDeleteDocument = useCallback((docId: string, docTitle: string) => {
    setDeleteDocumentId(docId);
    setDocumentTitleToDelete(docTitle);
  }, []);

  // Delete document: execute
  const confirmDeleteDocument = useCallback(async () => {
    if (!deleteDocumentId) return;
    setDeletingDocument(true);
    try {
      await api(`/api/v1/documents/${deleteDocumentId}`, { method: "DELETE" });
      addToast("success", `"${documentTitleToDelete}" deleted`);
      setDeleteDocumentId(null);
      setDocumentTitleToDelete("");
      // Clear panel, cache, and reload
      setPanelState({ type: "empty" });
      documentCacheRef.current.delete(deleteDocumentId);
      setDocumentCache(new Map(documentCacheRef.current));
      await loadSources();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      addToast("error", msg);
    } finally {
      setDeletingDocument(false);
    }
  }, [deleteDocumentId, documentTitleToDelete, addToast, loadSources]);

  const handleSend = useCallback(async () => {
    const query = input.trim();
    if (!query || chatStatus === "thinking" || chatStatus === "streaming") return;

    const userMsgId = crypto.randomUUID();
    const userMsg: ChatMessage = {
      id: userMsgId,
      role: "user",
      content: query,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setChatStatus("thinking");
    isNearBottomRef.current = true;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const docScope = checkedDocIds.size === documents.length ? null : Array.from(checkedDocIds);
      const { stream } = activeSessionId
        ? await sendMessageStream(kbId, query, activeSessionId, null, controller.signal)
        : await sendMessageStream(kbId, query, null, docScope, controller.signal);

      if (!stream) throw new Error("No response body");

      let accumulated = "";
      let sessionEventFired = false;

      setChatStatus("streaming");

      await parseSSEStream(
        stream,
        (event: StreamEvent) => {
          switch (event.type) {
            case "session": {
              if (!activeSessionId) {
                setActiveSessionId(event.session_id);
                router.replace(
                  `/knowledge-bases/${kbId}?session=${event.session_id}`,
                  { scroll: false },
                );
                loadSessions();
              }
              // Create placeholder AI message
              const tempId = crypto.randomUUID();
              streamingMsgIdRef.current = tempId;
              setMessages((prev) => [
                ...prev,
                {
                  id: tempId,
                  role: "assistant",
                  content: "",
                  createdAt: new Date().toISOString(),
                },
              ]);
              sessionEventFired = true;
              break;
            }
            case "token":
              accumulated += event.text;
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (
                  last?.role === "assistant" &&
                  (last.id === streamingMsgIdRef.current || !sessionEventFired)
                ) {
                  const updated = [...prev];
                  updated[updated.length - 1] = { ...last, content: accumulated };
                  return updated;
                }
                return prev;
              });
              break;
            case "citation":
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last?.role === "assistant") {
                  const updated = [...prev];
                  updated[updated.length - 1] = { ...last, citations: event.citations };
                  return updated;
                }
                return prev;
              });
              break;
            case "done":
              if (!event.persisted) {
                addToast("error", "Conversation couldn't be saved");
              }
              setChatStatus("idle");
              break;
            case "error":
              addToast("error", event.message);
              setChatStatus("error");
              break;
          }
        },
        controller.signal,
      );
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User cancelled — keep partial content
        setChatStatus("idle");
        return;
      }
      const msg = err instanceof Error ? err.message : "Failed to get answer";
      addToast("error", msg);
      setChatStatus("error");
    } finally {
      abortControllerRef.current = null;
      streamingMsgIdRef.current = null;
    }
  }, [
    input,
    chatStatus,
    kbId,
    activeSessionId,
    addToast,
    router,
    loadSessions,
    checkedDocIds,
    documents,
  ]);

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

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
      {/* ══ Upload progress overlay ══ */}
      {uploading && (
        <div className="fixed top-12 left-1/2 -translate-x-1/2 z-40">
          <div className="bg-[#1A1A1A] text-white text-xs px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="animate-spin shrink-0"
              aria-hidden="true"
            >
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            <span>{uploadStage}</span>
          </div>
        </div>
      )}

      {/* ══ Left: Tabbed sidebar (Documents / Sources) ══ */}
      <LeftSidebar
        knowledgeBaseName={kbName}
        documents={documents}
        sources={sources}
        checkedDocIds={checkedDocIds}
        activeSourceId={panelState.type === "source" ? panelState.sourceId : null}
        sourcesFirstLoad={sourcesFirstLoad}
        sourcesError={sourcesError}
        onToggleDocument={handleToggleDocument}
        onToggleAll={handleToggleAll}
        onAddSource={() => setAddSourceOpen(true)}
        onSelectSource={(sourceId) => setPanelState({ type: "source", sourceId })}
        onSelectDocument={handleSelectDocument}
        onTraceSource={handleTraceSource}
      />

      {/* ══ Center & Right: layout varies by panelMode ══ */}

      {/* ── Normal: [Chat flex-1] [Handle] [DetailPanel fixed] ── */}
      {panelMode === "normal" && (
        <>
          <ChatArea
            panelMode="normal"
            isDragging={isDragging}
            hasMessages={hasMessages}
            messages={messages}
            chatStatus={chatStatus}
            hasDocs={hasDocs}
            input={input}
            checkedDocIds={checkedDocIds}
            scrollRef={scrollRef}
            inputRef={inputRef}
            onInputChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onSend={handleSend}
            onStop={handleStop}
            sessionBar={
              <SessionBar
                sessions={sessions}
                activeSessionId={activeSessionId}
                loading={sessionsLoading}
                onSelectSession={handleSelectSession}
                onNewChat={handleNewChat}
                onRenameSession={handleRenameSession}
                onDeleteSession={handleDeleteSession}
              />
            }
          />

          <div
            {...dragHandleProps}
            className={`w-1.5 shrink-0 h-full cursor-col-resize flex items-center justify-center
              hover:bg-gray-200/60 active:bg-gray-300/60 transition-colors duration-150
              ${isDraggingRight ? "bg-gray-200/60" : ""}`}
          >
            <div className="w-[3px] h-8 rounded-full bg-gray-300/70" />
          </div>

          <div
            className="h-full bg-[#F7F7F5] flex flex-col border-l border-gray-200/60 overflow-hidden shrink-0"
            style={{ width: rightPanelWidth }}
          >
            <DetailPanel
              panelState={panelState}
              activeSource={activeSource}
              activeDocument={activeDocument}
              loadingDocument={loadingDocument}
              documentError={documentError}
              extracting={extractingSourceId !== null}
              panelMode={panelMode}
              onBack={handleBack}
              onReExtract={handleReExtract}
              onDeleteSource={handleDeleteSource}
              onSelectDocument={handleSelectDocument}
              onRetryDocument={handleRetryDocument}
              onMaximize={handleMaximizePanel}
              onRestore={handleRestorePanel}
              onDeleteDocument={handleDeleteDocument}
            />
          </div>
        </>
      )}

      {/* ── Maximized: [DetailPanel flex-1] [Handle] [Chat fixed right] ── */}
      {panelMode === "maximized" && (
        <>
          <div className="h-full bg-[#F7F7F5] flex flex-col overflow-hidden flex-1 w-0">
            <DetailPanel
              panelState={panelState}
              activeSource={activeSource}
              activeDocument={activeDocument}
              loadingDocument={loadingDocument}
              documentError={documentError}
              extracting={extractingSourceId !== null}
              panelMode={panelMode}
              onBack={handleBack}
              onReExtract={handleReExtract}
              onDeleteSource={handleDeleteSource}
              onSelectDocument={handleSelectDocument}
              onRetryDocument={handleRetryDocument}
              onMaximize={handleMaximizePanel}
              onRestore={handleRestorePanel}
              onDeleteDocument={handleDeleteDocument}
            />
          </div>

          <div
            {...chatDragHandleProps}
            className={`w-1.5 shrink-0 h-full cursor-col-resize flex items-center justify-center
              hover:bg-gray-200/60 active:bg-gray-300/60 transition-colors duration-150
              ${isDraggingChat ? "bg-gray-200/60" : ""}`}
          >
            <div className="w-[3px] h-8 rounded-full bg-gray-300/70" />
          </div>

          <ChatArea
            panelMode="maximized"
            isDragging={isDragging}
            hasMessages={hasMessages}
            messages={messages}
            chatStatus={chatStatus}
            hasDocs={hasDocs}
            input={input}
            checkedDocIds={checkedDocIds}
            scrollRef={scrollRef}
            inputRef={inputRef}
            onInputChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onSend={handleSend}
            onStop={handleStop}
            width={chatSidebarWidth}
            sessionBar={
              <SessionBar
                sessions={sessions}
                activeSessionId={activeSessionId}
                loading={sessionsLoading}
                onSelectSession={handleSelectSession}
                onNewChat={handleNewChat}
                onRenameSession={handleRenameSession}
                onDeleteSession={handleDeleteSession}
              />
            }
          />
        </>
      )}

      {/* ══ Modals ══ */}
      <AddSourceModal
        open={addSourceOpen}
        onClose={() => setAddSourceOpen(false)}
        onAddSource={handleAddSourceFromModal}
      />

      <ConfirmModal
        open={deleteSourceId !== null}
        title="Delete Source"
        message="This will permanently delete the original source and uploaded files. Extracted documents will remain in the knowledge base and continue to be searchable."
        confirmLabel="Delete"
        danger
        loading={deletingSource}
        onConfirm={confirmDeleteSource}
        onCancel={() => setDeleteSourceId(null)}
      />

      <ConfirmModal
        open={deleteDocumentId !== null}
        title="Delete Document?"
        message={`Are you sure you want to delete '${documentTitleToDelete}'? This will remove its chunks from the AI context and cannot be undone.`}
        confirmLabel="Confirm Delete"
        danger
        loading={deletingDocument}
        onConfirm={confirmDeleteDocument}
        onCancel={() => {
          setDeleteDocumentId(null);
          setDocumentTitleToDelete("");
        }}
      />
    </div>
  );
}
