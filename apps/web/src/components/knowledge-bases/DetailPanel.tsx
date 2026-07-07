"use client";

import type { DocumentDetail, PanelState, ReportTask } from "@/lib/types";
import { DocumentContentView } from "./DocumentContentView";
import { StatusBadge } from "./StatusBadge";
import { StudioPanel } from "./StudioPanel";

// ── Types ──

export interface DetailSourceDocument {
  id: string;
  title: string;
  version: string;
  description: string;
  status: string;
  chunkStatus: string | null;
  embedStatus: string | null;
  createdAt: string;
}

export interface DetailSourceDetail {
  id: string;
  name: string;
  type: "upload" | "link";
  status: string;
  createdAt: string;
  documents: DetailSourceDocument[];
}

interface DetailPanelProps {
  panelState: PanelState;
  activeSource: DetailSourceDetail | null;
  activeDocument: DocumentDetail | null;
  loadingDocument: boolean;
  documentError: string;
  extracting: boolean;
  panelMode: "normal" | "maximized";
  recentTabs: ReportTask[];
  selectedDocCount: number;
  onBack: () => void;
  onReExtract: (sourceId: string) => void;
  onDeleteSource: (sourceId: string) => void;
  onSelectDocument: (documentId: string) => void;
  onRetryDocument: () => void;
  onMaximize: () => void;
  onRestore: () => void;
  onDeleteDocument?: (docId: string, docTitle: string) => void;
  onCreateReport: () => void;
  onViewReport: (report: ReportTask) => void;
}

// ── Focus Mode toggle icon ──

function SwapLayoutIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m16 3 4 4-4 4" />
      <path d="M20 7H4" />
      <path d="m8 21-4-4 4-4" />
      <path d="M4 17h16" />
    </svg>
  );
}

// ── Studio view (default) ──

function StudioDetailView({
  recentTabs,
  selectedDocCount,
  onCreateReport,
  onViewReport,
}: {
  recentTabs: ReportTask[];
  selectedDocCount: number;
  onCreateReport: () => void;
  onViewReport: (report: ReportTask) => void;
}) {
  return (
    <StudioPanel
      reports={recentTabs}
      selectedDocCount={selectedDocCount}
      onCreateReport={onCreateReport}
      onViewReport={onViewReport}
    />
  );
}

// ── Source detail view ──

function SourceDetailView({
  source,
  extracting,
  onBack,
  onReExtract,
  onDeleteSource,
  onSelectDocument,
}: {
  source: DetailSourceDetail;
  extracting: boolean;
  onBack: () => void;
  onReExtract: (sourceId: string) => void;
  onDeleteSource: (sourceId: string) => void;
  onSelectDocument: (documentId: string) => void;
}) {
  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      {/* Document versions */}
      <div className="px-3 pt-3 pb-3">
        <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wider px-1 mb-2">
          Document Versions
        </p>
        <div className="space-y-1">
          {source.documents.length === 0 ? (
            <p className="text-[11px] text-gray-300 px-1 py-2">
              {source.status === "pending" ? "Indexing in progress…" : "No versions extracted yet"}
            </p>
          ) : (
            source.documents.map((doc) => (
              <button
                key={doc.id}
                type="button"
                onClick={() => onSelectDocument(doc.id)}
                className="w-full text-left rounded-lg border border-gray-200/60 bg-white p-2.5
                  flex items-center gap-2.5 hover:border-gray-300 hover:shadow-[0_1px_3px_rgba(0,0,0,0.04)]
                  transition-all duration-200"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="shrink-0 text-gray-400"
                  aria-hidden="true"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="text-xs font-medium text-[#2F3437] truncate">{doc.title}</p>
                    <StatusBadge status={doc.status} />
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-[10px] font-medium text-gray-400">{doc.version}</span>
                    <span className="text-[10px] text-gray-300">· {doc.description}</span>
                  </div>
                </div>
                <span className="text-[10px] text-gray-300 shrink-0">
                  {new Date(doc.createdAt).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="px-3 pb-4 space-y-1.5">
        <button
          type="button"
          onClick={() => onReExtract(source.id)}
          disabled={extracting}
          className="w-full flex items-center justify-center gap-2 rounded-lg border border-gray-200/60
            px-3 py-2 text-xs font-medium text-[#2F3437] hover:bg-gray-50/50 hover:border-gray-300
            transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {extracting ? (
            <>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="animate-spin"
                aria-hidden="true"
              >
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
              Extracting…
            </>
          ) : (
            <>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
                <line x1="8" y1="11" x2="14" y2="11" />
                <line x1="11" y1="8" x2="11" y2="14" />
              </svg>
              Re-extract
            </>
          )}
        </button>
        <button
          type="button"
          onClick={() => onDeleteSource(source.id)}
          className="w-full flex items-center justify-center gap-2 rounded-lg border border-red-200/60
            px-3 py-2 text-xs font-medium text-red-500 hover:bg-red-50 hover:border-red-300
            transition-all duration-200"
        >
          Delete Source
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// DetailPanel
// ═══════════════════════════════════════════════════════════

export function DetailPanel({
  panelState,
  activeSource,
  activeDocument,
  loadingDocument,
  documentError,
  extracting,
  panelMode,
  recentTabs,
  selectedDocCount,
  onBack,
  onReExtract,
  onDeleteSource,
  onSelectDocument,
  onRetryDocument,
  onMaximize,
  onRestore,
  onDeleteDocument,
  onCreateReport,
  onViewReport,
}: DetailPanelProps) {
  const showDocument = panelState.type === "document";
  const showSource = panelState.type === "source";
  const showStudio = panelState.type === "studio";
  const isMaximized = panelMode === "maximized";

  return (
    <aside className="w-full h-full bg-[#F7F7F5] flex flex-col">
      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-200/40">
        {/* ── Document state ── */}
        {showDocument && (
          <>
            {/* Row 1: Back button + swap toggle */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onBack}
                className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-[#2F3437] transition-colors duration-200"
              >
                <svg
                  width="10"
                  height="10"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <line x1="19" y1="12" x2="5" y2="12" />
                  <polyline points="12 19 5 12 12 5" />
                </svg>
                Back to Studio
              </button>
              <button
                type="button"
                onClick={isMaximized ? onRestore : onMaximize}
                className="shrink-0 p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-200/50 transition-colors duration-200 ml-auto"
                aria-label={isMaximized ? "Restore default layout" : "Swap to Document Focus Mode"}
                title={isMaximized ? "Restore default layout" : "Swap to Document Focus Mode"}
              >
                <SwapLayoutIcon />
              </button>
            </div>

            {/* Row 4: Badges + actions */}
            <div className="flex items-center gap-2 mt-2.5">
              {activeDocument ? (
                <>
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-200/70 text-gray-500 shrink-0">
                    {activeDocument.source_format.toUpperCase()}
                  </span>
                  <StatusBadge status={activeDocument.status} />
                  {activeDocument.chunk_status === "done" && (
                    <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-500 shrink-0">
                      Chunked
                    </span>
                  )}
                  {activeDocument.embed_status === "done" && (
                    <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-purple-50 text-purple-500 shrink-0">
                      Embedded
                    </span>
                  )}
                  {activeDocument.embed_status === "running" && (
                    <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-400 shrink-0 animate-pulse">
                      Embedding…
                    </span>
                  )}
                  {onDeleteDocument && (
                    <button
                      type="button"
                      onClick={() => onDeleteDocument(activeDocument.id, activeDocument.title)}
                      className="ml-auto p-1.5 rounded-md text-gray-400 opacity-80 hover:text-red-500 hover:bg-red-50 transition-colors duration-200"
                      aria-label="Delete document"
                      title="Delete Document"
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M3 6h18" />
                        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                        <line x1="10" y1="11" x2="10" y2="17" />
                        <line x1="14" y1="11" x2="14" y2="17" />
                      </svg>
                    </button>
                  )}
                </>
              ) : (
                <span className="text-[10px] text-gray-300">
                  {loadingDocument ? "Loading…" : "Document"}
                </span>
              )}
            </div>

            {/* Row 2: Document title */}
            <h3 className="text-base font-bold text-[#1A1A1A] truncate mt-2">
              {activeDocument?.title ?? (loadingDocument ? "Loading document…" : "Document")}
            </h3>

            {/* Row 3: Metadata */}
            <p className="text-[11px] text-gray-400 mt-0.5">
              {activeDocument ? (
                <>
                  {activeDocument.chunk_count === 0
                    ? "No indexed sections yet"
                    : `${activeDocument.chunk_count} indexed section${activeDocument.chunk_count === 1 ? "" : "s"}`}
                  {" · "}
                  Created{" "}
                  {new Date(activeDocument.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </>
              ) : loadingDocument ? (
                "Fetching document…"
              ) : (
                "Document not found"
              )}
            </p>
          </>
        )}

        {/* ── Source state ── */}
        {showSource && activeSource && (
          <>
            <button
              type="button"
              onClick={onBack}
              className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-[#2F3437] transition-colors duration-200 mb-2"
            >
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              Back to Studio
            </button>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-200/70 text-gray-500 shrink-0">
                {activeSource.type === "upload" ? "FILE" : "LINK"}
              </span>
              <StatusBadge status={activeSource.status} />
            </div>
            <h3 className="text-sm font-semibold text-[#1A1A1A] truncate mt-1">
              {activeSource.name}
            </h3>
            <p className="text-[10px] text-gray-400 mt-0.5">
              {new Date(activeSource.createdAt).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          </>
        )}

        {/* ── Studio state ── */}
        {showStudio && (
          <>
            <h3 className="text-sm font-semibold text-[#1A1A1A] tracking-tight">Studio</h3>
            <p className="text-[11px] text-gray-400 mt-0.5">
              Generate reports and presentations from your knowledge base
            </p>
          </>
        )}
      </div>

      {/* Body */}
      {showDocument ? (
        <DocumentContentView
          document={activeDocument}
          loading={loadingDocument}
          error={documentError}
          onBack={onBack}
          onRetry={onRetryDocument}
          onDeleteDocument={onDeleteDocument}
        />
      ) : showSource && activeSource ? (
        <SourceDetailView
          source={activeSource}
          extracting={extracting}
          onBack={onBack}
          onReExtract={onReExtract}
          onDeleteSource={onDeleteSource}
          onSelectDocument={onSelectDocument}
        />
      ) : (
        <StudioDetailView
          recentTabs={recentTabs}
          selectedDocCount={selectedDocCount}
          onCreateReport={onCreateReport}
          onViewReport={onViewReport}
        />
      )}
    </aside>
  );
}
