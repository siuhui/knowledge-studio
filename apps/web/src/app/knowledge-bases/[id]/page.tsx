"use client";

import { AddSourceModal } from "@/components/knowledge-bases/AddSourceModal";
import { CreateReportModal } from "@/components/knowledge-bases/CreateReportModal";
import type { ReportConfig } from "@/components/knowledge-bases/CreateReportModal";
import { ReportViewerModal } from "@/components/knowledge-bases/ReportViewerModal";
import { DetailPanel } from "@/components/knowledge-bases/DetailPanel";
import type { DetailSourceDetail } from "@/components/knowledge-bases/DetailPanel";
import { LeftSidebar } from "@/components/knowledge-bases/LeftSidebar";
import { SessionBar } from "@/components/knowledge-bases/SessionBar";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { MarkdownContent } from "@/components/ui/MarkdownContent";
import { useDocumentSelection } from "@/hooks/useDocumentSelection";
import { usePanelResize } from "@/hooks/usePanelResize";
import { useToast } from "@/hooks/useToast";
import {
  api,
  apiPaginated,
  completeSourceUpload,
  createStudioTask,
  deleteSession,
  deleteStudioTask,
  downloadStudioReport,
  downloadStudioReportFile,
  getContentType,
  getDocumentChunks,
  getSession,
  getStudioTask,
  listKnowledgeBaseDocuments,
  listSessions,
  listSourceDocuments,
  listStudioTasks,
  presignSourceUpload,
  renameSession,
  sendMessageStream,
  uploadToPresignedUrl,
} from "@/lib/api";
import { parseSSEStream } from "@/lib/sse";
import { flattenDocs } from "@/lib/types";
import type {
  AgentProgressEvent,
  Citation,
  Document,
  DocumentDetail,
  FlatDocument,
  KnowledgeBase,
  PanelState,
  ReportTask,
  SessionItem,
  Source,
  SourceNode,
  StreamEvent,
  StudioTaskItem,
} from "@/lib/types";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
  agentSteps: AgentProgressEvent[];
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
  agentSteps,
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
      <div ref={scrollRef} className="flex-1 overflow-y-auto flex flex-col custom-scrollbar">
        {hasMessages ? (
          <div className={isMaximized ? "py-4" : "py-6"}>
            {messages.map((msg, i) => {
              const isLast = i === messages.length - 1;
              const isLastAssistant = isLast && msg.role === "assistant";
              return (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  isLastAssistant={isLastAssistant}
                  isThinking={isLastAssistant && chatStatus === "thinking"}
                  agentSteps={isLastAssistant && agentSteps.length > 0 ? agentSteps : undefined}
                  isMaximized={isMaximized}
                />
              );
            })}
          </div>
        ) : (
          <EmptyChat hasDocs={hasDocs} />
        )}
      </div>

      {/* Input area */}
      <div className={isMaximized ? "px-2 pb-3 pt-1" : "px-4 pb-4 pt-2"}>
        <div
          className={`flex items-center gap-2.5 bg-white border rounded-xl px-3.5 py-2 transition-all duration-200
            ${input.length > 0 ? "border-gray-300" : "border-gray-200/80"}`}
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={onInputChange}
            onKeyDown={onKeyDown}
            placeholder={hasDocs ? "Ask a question…" : "Select documents to begin…"}
            rows={1}
            className="flex-1 resize-none bg-transparent py-0.5 text-sm text-[#2F3437]
              placeholder:text-gray-300 outline-none"
          />
          <div className="flex items-center shrink-0">
            {chatStatus === "streaming" ? (
              <button
                type="button"
                onClick={onStop}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                  bg-[#1A1A1A] text-white hover:bg-[#2F3437] transition-colors
                  active:scale-95"
                aria-label="Stop generating"
              >
                <svg
                  width="11"
                  height="11"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <rect x="4" y="4" width="16" height="16" rx="3" />
                </svg>
              </button>
            ) : (
              <button
                type="button"
                onClick={onSend}
                disabled={input.trim().length === 0 || isBusy}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                  bg-[#1A1A1A] text-white hover:bg-[#2F3437] transition-all duration-200
                  active:scale-95
                  disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed
                  disabled:active:scale-100"
                aria-label="Send message"
              >
                <svg
                  width="13"
                  height="13"
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
      </div>
    </div>
  );
}

// ── Message bubble ──
function MessageBubble({
  message,
  isLastAssistant,
  isThinking,
  agentSteps,
  isMaximized,
}: {
  message: ChatMessage;
  isLastAssistant?: boolean;
  isThinking?: boolean;
  agentSteps?: AgentProgressEvent[];
  isMaximized?: boolean;
}) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end px-4 py-2">
        <div className="max-w-[80%] bg-[#F1F1F4] rounded-lg px-3.5 py-2">
          <p className="text-sm text-[#2F3437] leading-relaxed whitespace-pre-wrap break-words">
            {message.content}
          </p>
        </div>
      </div>
    );
  }

  const isEmpty = !message.content;
  const hasSteps = agentSteps && agentSteps.length > 0;

  return (
    <div className="px-4 py-2">
      {/* Agent steps — expandable tool-call style blocks */}
      {hasSteps && (
        <div className="mb-2 rounded-lg border border-gray-200/80 bg-gray-50/50 overflow-hidden">
          {agentSteps.map((step, i) => (
            <AgentStepRow
              // biome-ignore lint/suspicious/noArrayIndexKey: append-only ephemeral list
              key={i}
              step={step}
              compact={isMaximized ?? false}
              isLast={i === agentSteps.length - 1}
            />
          ))}
        </div>
      )}

      {/* Thinking indicator when no progress yet */}
      {isThinking && !hasSteps && isEmpty && (
        <span className="text-sm text-gray-400 italic">Thinking…</span>
      )}

      {/* Message content */}
      {message.content && (
        <MarkdownContent
          content={message.content}
          className="text-sm text-[#2F3437] leading-relaxed break-words"
        />
      )}

      {/* Citations — minimal inline footnotes */}
      {message.citations && message.citations.length > 0 && (
        <div className="mt-3 pt-2 border-t border-gray-100">
          <p className="text-[11px] text-gray-400 mb-1.5">Sources</p>
          <div className="space-y-1">
            {message.citations.map((c, i) => (
              <div key={`${c.document_id}-${c.chunk_index}`} className="text-[11px] text-gray-500">
                <span className="font-medium text-gray-400">[{i + 1}]</span>{" "}
                <span className="text-gray-500">{c.document_title}</span>
                {c.content_snippet && (
                  <span className="text-gray-400 ml-1.5 italic">
                    &ldquo;{c.content_snippet.slice(0, 120)}
                    {c.content_snippet.length > 120 ? "…" : ""}&rdquo;
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Agent step labels (frontend owns display strings) ──

const STATUS_LABELS: Record<AgentProgressEvent["status"], string> = {
  listing: "searched docs",
  searching: "searched",
  reading: "read",
  analyzing: "analyzed",
  error: "error",
};

function formatStepMessage(step: AgentProgressEvent): string {
  switch (step.status) {
    case "listing":
      return step.document_count
        ? `found ${step.document_count} document(s)`
        : "no documents found";
    case "searching":
      if (step.query === undefined) return "";
      return step.hits
        ? `"${step.query}" — ${step.hits} match(es)`
        : `"${step.query}" — no results`;
    case "reading":
      if (!step.found) return "document not found";
      return step.document_title ? `${step.document_title}` : "reading...";
    case "analyzing":
      return "preparing answer...";
    case "error":
      return "retrieval error, retrying...";
  }
}

function AgentStepRow({
  step,
  compact,
  isLast,
}: {
  step: AgentProgressEvent;
  compact: boolean;
  isLast: boolean;
}) {
  const label = STATUS_LABELS[step.status];
  const detail = formatStepMessage(step);
  const isError = step.status === "error";
  const isDone = step.status === "analyzing" && isLast;

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 text-[11px] font-mono
        ${!isLast ? "border-b border-gray-100" : ""}
        ${isError ? "text-red-500 bg-red-50/30" : isDone ? "text-gray-500" : "text-gray-400"}`}
    >
      <span
        className={`shrink-0 ${isError ? "text-red-400" : isDone ? "text-blue-400" : "text-gray-300"}`}
      >
        {isError ? "✗" : isDone ? "●" : "○"}
      </span>
      <span className="font-medium text-gray-500 shrink-0">{label}</span>
      {detail && <span className="text-gray-400 truncate">{detail}</span>}
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

  // Modals
  const [addSourceOpen, setAddSourceOpen] = useState(false);

  // Studio — default right panel
  const [panelState, setPanelState] = useState<PanelState>({ type: "studio" });

  // Document cache + loading
  const documentCacheRef = useRef<Map<string, DocumentDetail>>(new Map());
  const [documentCache, setDocumentCache] = useState<Map<string, DocumentDetail>>(new Map());
  const [loadingDocument, setLoadingDocument] = useState(false);
  const [documentError, setDocumentError] = useState("");
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Chat
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [chatStatus, setChatStatus] = useState<"idle" | "thinking" | "streaming" | "error">("idle");
  const [agentSteps, setAgentSteps] = useState<AgentProgressEvent[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const streamingMsgIdRef = useRef<string | null>(null);
  const traceIdRef = useRef<string>(""); // Langfuse trace ID for debugging
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Sessions
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(true);

  // Report tasks — list shown in the right panel's Studio view
  const [reportTasks, setReportTasks] = useState<ReportTask[]>([]);

  // Report viewer modal
  const [viewingReport, setViewingReport] = useState<ReportTask | null>(null);

  // Delete confirmation
  const [deleteConfirmReport, setDeleteConfirmReport] = useState<ReportTask | null>(null);

  // Create report modal
  const [createReportOpen, setCreateReportOpen] = useState(false);
  const [reportGenerating, setReportGenerating] = useState(false);

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

  // ── Document selection (reactive: null=all, []=none, [...]=subset) ──
  const { checkedDocIds, setCheckedDocIds, restoreDocSelection, resetSelection } =
    useDocumentSelection(documents);

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
    resetSelection();
    setPanelState({ type: "studio" }); // auto-revert to Studio
    router.replace(`/knowledge-bases/${kbId}`, { scroll: false });
  }, [kbId, router, resetSelection]);

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
          resetSelection();
          router.replace(`/knowledge-bases/${kbId}`, { scroll: false });
        }
        addToast("success", "Chat deleted");
      } catch {
        addToast("error", "Failed to delete session");
      }
    },
    [kbId, activeSessionId, addToast, router, resetSelection],
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
        if (next.has(docId)) {
          next.delete(docId);
          // Auto-revert: if the deselected doc is being viewed, go back to Studio
          if (panelState.type === "document" && panelState.documentId === docId) {
            setPanelState({ type: "studio" });
          }
        } else {
          next.add(docId);
        }
        persistDocumentScope(next);
        return next;
      });
    },
    [panelState, persistDocumentScope, setCheckedDocIds],
  );

  const handleToggleAll = useCallback(
    (selectAll: boolean) => {
      setCheckedDocIds(() => {
        const next = selectAll ? new Set(documents.map((d) => d.id)) : new Set<string>();
        // Auto-revert: deselecting all while viewing a document → back to Studio
        if (!selectAll && panelState.type === "document") {
          setPanelState({ type: "studio" });
        }
        persistDocumentScope(next);
        return next;
      });
    },
    [documents, panelState, persistDocumentScope, setCheckedDocIds],
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
    setPanelState({ type: "studio" });
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
      setPanelState({ type: "studio" });
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
      setPanelState({ type: "studio" });
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

  // Clean up poll timer on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, []);

  // ── Studio: shared poll helper ──

  const pollStudioTask = useCallback(
    (backendTaskId: string) => {
      const POLL_INTERVAL = 3000;

      const poll = async () => {
        try {
          const updated = await getStudioTask(kbId, backendTaskId);

          if (updated.status === "completed") {
            const content = await downloadStudioReport(kbId, backendTaskId);
            setReportTasks((prev) =>
              prev.map((t) =>
                t.taskId === backendTaskId ? { ...t, status: "completed", content } : t,
              ),
            );
            setReportGenerating(false);
            return;
          }

          if (updated.status === "failed") {
            setReportTasks((prev) =>
              prev.map((t) =>
                t.taskId === backendTaskId
                  ? { ...t, status: "failed", error: updated.error_message || "Unknown error" }
                  : t,
              ),
            );
            setReportGenerating(false);
            return;
          }

          pollTimerRef.current = setTimeout(poll, POLL_INTERVAL);
        } catch {
          setReportTasks((prev) =>
            prev.map((t) =>
              t.taskId === backendTaskId ? { ...t, status: "failed", error: "Polling failed" } : t,
            ),
          );
          setReportGenerating(false);
        }
      };

      poll();
    },
    [kbId],
  );

  // Load existing tasks from backend on mount
  useEffect(() => {
    if (!kbId) return;

    listStudioTasks(kbId, 1, 50)
      .then(({ data }) => {
        const mapped: ReportTask[] = data.map((t) => ({
          id: t.id,
          taskId: t.id,
          type: t.task_type === "ppt" ? "ppt" : "report",
          title: t.title,
          status:
            t.status === "completed"
              ? "completed"
              : t.status === "failed"
                ? "failed"
                : "generating",
          content: "",
          error: undefined,
        }));

        setReportTasks((prev) => {
          const existingIds = new Set(prev.map((r) => r.taskId));
          const fresh = mapped.filter((r) => !existingIds.has(r.taskId));
          return [...prev, ...fresh];
        });

        for (const task of data) {
          if (task.status === "pending" || task.status === "running") {
            pollStudioTask(task.id);
          }
        }
      })
      .catch(() => {
        // Silently ignore — UI shows empty state
      });
  }, [kbId, pollStudioTask]);

  // ── Studio: Create Report ──
  const handleCreateReport = useCallback(() => {
    if (checkedDocIds.size === 0) return;
    setCreateReportOpen(true);
  }, [checkedDocIds]);

  const handleSubmitReport = useCallback(
    (config: ReportConfig) => {
      setCreateReportOpen(false);
      setReportGenerating(true);

      const uiId = crypto.randomUUID();
      const newTask: ReportTask = {
        id: uiId,
        taskId: "",
        type: "report",
        title: config.title,
        status: "generating",
        content: "",
      };

      setReportTasks((prev) => [...prev, newTask]);

      const docIds = checkedDocIds.size === documents.length ? null : Array.from(checkedDocIds);

      createStudioTask(kbId, {
        title: config.title,
        config: {
          instruction: config.instruction,
          document_ids: docIds,
          style: config.style,
          length: config.length,
        },
      })
        .then((task) => {
          setReportTasks((prev) =>
            prev.map((t) => (t.id === uiId ? { ...t, taskId: task.id } : t)),
          );
          pollStudioTask(task.id);
        })
        .catch((err) => {
          setReportTasks((prev) =>
            prev.map((t) =>
              t.id === uiId
                ? {
                    ...t,
                    status: "failed",
                    error: err instanceof Error ? err.message : "Failed to create task",
                  }
                : t,
            ),
          );
          setReportGenerating(false);
        });
    },
    [kbId, pollStudioTask, checkedDocIds, documents],
  );

  const handleDeleteReport = useCallback((report: ReportTask) => {
    setDeleteConfirmReport(report);
  }, []);

  const handleConfirmDeleteReport = useCallback(
    (report: ReportTask) => {
      if (report.taskId) {
        deleteStudioTask(kbId, report.taskId).catch(() => {
          // Silently ignore — remove from UI regardless
        });
      }
      setReportTasks((prev) => prev.filter((t) => t.id !== report.id));
      setViewingReport(null);
      setDeleteConfirmReport(null);
    },
    [kbId],
  );

  const handleDownloadReport = useCallback(
    (report: ReportTask) => {
      if (report.taskId) {
        downloadStudioReportFile(kbId, report.taskId, `${report.title}.md`);
      }
    },
    [kbId],
  );

  // ── Report viewer ──
  const handleViewReport = useCallback(
    async (report: ReportTask) => {
      // If completed but content not loaded yet (e.g. loaded from API on mount),
      // fetch it from the backend before showing the viewer.
      if (report.status === "completed" && !report.content && report.taskId) {
        try {
          const content = await downloadStudioReport(kbId, report.taskId);
          const updated = { ...report, content };
          setReportTasks((prev) => prev.map((t) => (t.id === report.id ? updated : t)));
          setViewingReport(updated);
          return;
        } catch {
          // Still show the viewer — the error state inside handles this
        }
      }
      setViewingReport(report);
    },
    [kbId],
  );

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
    setAgentSteps([]);
    traceIdRef.current = ""; // reset for new request
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
      let firstTokenSeen = false;

      // Keep "thinking" state during agent retrieval — switch to
      // "streaming" only when the first token arrives so the
      // agent_progress step list is visible to the user.
      // ──────────────────────────────────────────────────────────

      await parseSSEStream(
        stream,
        (event: StreamEvent) => {
          switch (event.type) {
            case "agent_progress":
              setAgentSteps((prev) => [...prev, event]);
              break;
            case "session": {
              if (!activeSessionId) {
                setActiveSessionId(event.session_id);
                router.replace(`/knowledge-bases/${kbId}?session=${event.session_id}`, {
                  scroll: false,
                });
                loadSessions();
              }
              // Store trace_id for Langfuse debugging
              if (event.trace_id) {
                traceIdRef.current = event.trace_id;
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
              if (!firstTokenSeen) {
                firstTokenSeen = true;
                setChatStatus("streaming");
              }
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
              addToast(
                "error",
                event.message +
                  (traceIdRef.current ? ` (Trace ID: ${traceIdRef.current.slice(0, 8)}…)` : ""),
              );
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
      const traceSuffix = traceIdRef.current
        ? ` (Trace ID: ${traceIdRef.current.slice(0, 8)}…)`
        : "";
      addToast("error", msg + traceSuffix);
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
    <div className="h-[calc(100vh-3rem)] flex flex-col overflow-hidden">
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

      {/* ══ Main three-column area ══ */}
      <div className="flex-1 flex overflow-hidden min-h-0">
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
              agentSteps={agentSteps}
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
                recentTabs={reportTasks}
                selectedDocCount={checkedDocIds.size}
                onBack={handleBack}
                onReExtract={handleReExtract}
                onDeleteSource={handleDeleteSource}
                onSelectDocument={handleSelectDocument}
                onRetryDocument={handleRetryDocument}
                onMaximize={handleMaximizePanel}
                onRestore={handleRestorePanel}
                onDeleteDocument={handleDeleteDocument}
                onCreateReport={handleCreateReport}
                onViewReport={handleViewReport}
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
                recentTabs={reportTasks}
                selectedDocCount={checkedDocIds.size}
                onBack={handleBack}
                onReExtract={handleReExtract}
                onDeleteSource={handleDeleteSource}
                onSelectDocument={handleSelectDocument}
                onRetryDocument={handleRetryDocument}
                onMaximize={handleMaximizePanel}
                onRestore={handleRestorePanel}
                onDeleteDocument={handleDeleteDocument}
                onCreateReport={handleCreateReport}
                onViewReport={handleViewReport}
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
              agentSteps={agentSteps}
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
      </div>
      {/* end three-column area */}

      {/* ══ Report viewer modal ══ */}
      <ReportViewerModal
        open={viewingReport !== null}
        report={viewingReport}
        onClose={() => setViewingReport(null)}
        onDownload={handleDownloadReport}
        onDelete={handleDeleteReport}
      />

      <ConfirmModal
        open={deleteConfirmReport !== null}
        title="Delete Report"
        message={
          deleteConfirmReport
            ? `Delete "${deleteConfirmReport.title}"? This will permanently remove the report and its file from storage.`
            : ""
        }
        confirmLabel="Delete"
        danger
        onConfirm={() => deleteConfirmReport && handleConfirmDeleteReport(deleteConfirmReport)}
        onCancel={() => setDeleteConfirmReport(null)}
      />

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

      <CreateReportModal
        open={createReportOpen}
        loading={reportGenerating}
        onClose={() => setCreateReportOpen(false)}
        onCreate={handleSubmitReport}
      />
    </div>
  );
}
