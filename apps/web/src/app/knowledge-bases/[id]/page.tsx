"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
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
} from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { usePanelResize } from "@/hooks/usePanelResize";
import { LeftSidebar } from "@/components/knowledge-bases/LeftSidebar";
import { DetailPanel } from "@/components/knowledge-bases/DetailPanel";
import { AddSourceModal } from "@/components/knowledge-bases/AddSourceModal";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { flattenDocs } from "@/lib/types";
import type {
  Citation,
  Document,
  DocumentDetail,
  FlatDocument,
  KnowledgeBase,
  PanelState,
  QaResponse,
  Source,
  SourceNode,
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
  thinking: boolean;
  hasDocs: boolean;
  input: string;
  checkedDocIds: Set<string>;
  scrollRef: React.RefObject<HTMLDivElement | null>;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  onInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSend: () => void;
  width?: number;
}

function ChatArea({
  panelMode,
  isDragging,
  hasMessages,
  messages,
  thinking,
  hasDocs,
  input,
  checkedDocIds,
  scrollRef,
  inputRef,
  onInputChange,
  onKeyDown,
  onSend,
  width,
}: ChatAreaProps) {
  const isMaximized = panelMode === "maximized";

  return (
    <div
      className={`flex flex-col h-full bg-white ${
        isMaximized
          ? "shrink-0 border-l border-gray-200"
          : "flex-1 min-w-[360px]"
      } ${!isDragging ? "transition-all duration-300 ease-in-out" : ""}`}
      style={isMaximized && width ? { width } : undefined}
    >
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {hasMessages ? (
          <div className={isMaximized ? "py-4 px-3" : "mx-auto py-6 px-4"}>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {thinking && (
              <div className={`flex items-center gap-3 ${isMaximized ? "px-2 py-3" : "px-6 py-4"}`}>
                <div className={`rounded-full bg-[#1A1A1A] flex items-center justify-center shrink-0 ${
                  isMaximized ? "w-6 h-6" : "w-7 h-7"
                }`}>
                  <span className={`font-semibold text-white ${isMaximized ? "text-[10px]" : "text-[11px]"}`}>
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
                  ? isMaximized ? "Select documents…" : "Select documents from the sidebar to begin…"
                  : isMaximized ? "Ask a question…" : "Ask a question about your documents…"
              }
              rows={1}
              className={`w-full resize-none rounded-xl px-4 py-3 text-sm text-[#2F3437]
                placeholder:text-gray-300 outline-none
                focus:border-gray-400 focus:ring-0
                transition-colors duration-200
                bg-transparent`}
            />
            <div className={`flex items-center justify-between ${isMaximized ? "px-2 pb-2" : "px-3 pb-3"}`}>
              <span className={isMaximized ? "text-[9px] text-gray-300" : "text-[10px] text-gray-300"}>
                {!hasDocs
                  ? isMaximized ? "No docs" : "No documents selected"
                  : `${checkedDocIds.size} document${checkedDocIds.size === 1 ? "" : "s"} in context`}
              </span>
              <button
                type="button"
                onClick={onSend}
                disabled={input.trim().length === 0 || thinking || !hasDocs}
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
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Layout: panel resizing & modes ──
  type PanelMode = "normal" | "maximized";
  const [panelMode, setPanelMode] = useState<PanelMode>("normal");
  const { width: rightPanelWidth, isDragging: isDraggingRight, dragHandleProps } = usePanelResize(400);
  // Second resize hook for the chat sidebar width in maximized mode
  const { width: chatSidebarWidth, isDragging: isDraggingChat, dragHandleProps: chatDragHandleProps } =
    usePanelResize(340);
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
    }));
    return [...fromSources, ...orphans];
  }, [sourceNodes, orphanedDocuments]);

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
          Object.values(bySource).flat().map((d) => d.id),
        );
        const orphaned = kbDocs.filter(
          (d) => d.source_id === null && !allSourceDocIds.has(d.id),
        );
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
  // Terminal statuses: "active" | "error". Non-terminal: "processing" | "pending" | "parsed".
  // Also polls when an active source has zero documents (pipeline hasn't created them yet).
  useEffect(() => {
    if (sourcesFirstLoad) return;

    const hasTransitionalDoc = Object.values(documentsBySource).some((docs) =>
      docs.some((d) => d.status === "processing" || d.status === "pending" || d.status === "parsed"),
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
  const handleSelectDocument = useCallback(
    async (docId: string) => {
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
    },
    [],
  );

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
            thinking={thinking}
            hasDocs={hasDocs}
            input={input}
            checkedDocIds={checkedDocIds}
            scrollRef={scrollRef}
            inputRef={inputRef}
            onInputChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onSend={handleSend}
          />

          <div
            {...dragHandleProps}
            className={`w-1.5 shrink-0 h-full cursor-col-resize flex items-center justify-center
              hover:bg-gray-200/60 active:bg-gray-300/60 transition-colors duration-150
              ${isDraggingRight ? "bg-gray-200/60" : ""}`}
          >
            <div className="w-[3px] h-8 rounded-full bg-gray-300/70" />
          </div>

          <div className="h-full bg-[#F7F7F5] flex flex-col border-l border-gray-200/60 overflow-hidden shrink-0"
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
            thinking={thinking}
            hasDocs={hasDocs}
            input={input}
            checkedDocIds={checkedDocIds}
            scrollRef={scrollRef}
            inputRef={inputRef}
            onInputChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onSend={handleSend}
            width={chatSidebarWidth}
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
