"use client";

import type { DocumentDetail, PanelState } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { DocumentContentView } from "./DocumentContentView";

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
  onBack: () => void;
  onReExtract: (sourceId: string) => void;
  onDeleteSource: (sourceId: string) => void;
  onSelectDocument: (documentId: string) => void;
  onRetryDocument: () => void;
  onMaximize: () => void;
  onRestore: () => void;
  onDeleteDocument?: (docId: string, docTitle: string) => void;
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

// ── Placeholder view (no selection) ──

function EmptyDetail() {
  return (
    <div className="flex-1 flex items-center justify-center px-3">
      <div className="text-center py-10">
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
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>
        <p className="text-xs text-gray-300">Select a source</p>
        <p className="text-[11px] text-gray-200 mt-0.5">
          Click a source in the sidebar to view details
        </p>
      </div>
    </div>
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
    <div className="flex-1 overflow-y-auto">
      {/* Back button + meta */}
      <div className="px-4 py-3 border-b border-gray-200/40">
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
          Back
        </button>

        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-200/70 text-gray-500 shrink-0">
            {source.type === "upload" ? "FILE" : "LINK"}
          </span>
          <StatusBadge status={source.status} />
        </div>
        <h3 className="text-sm font-semibold text-[#1A1A1A] truncate mt-1">{source.name}</h3>
        <p className="text-[10px] text-gray-400 mt-0.5">
          {new Date(source.createdAt).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </p>
      </div>

      {/* Document versions */}
      <div className="px-3 py-3">
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
  onBack,
  onReExtract,
  onDeleteSource,
  onSelectDocument,
  onRetryDocument,
  onMaximize,
  onRestore,
  onDeleteDocument,
}: DetailPanelProps) {
  const showDocument = panelState.type === "document";
  const showSource = panelState.type === "source";
  const showEmpty = panelState.type === "empty";
  const isMaximized = panelMode === "maximized";

  return (
    <aside className="w-full h-full bg-[#F7F7F5] flex flex-col">
      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-200/40">
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-[#1A1A1A] tracking-tight truncate">
              {showDocument && activeDocument
                ? activeDocument.title
                : showSource && activeSource
                  ? activeSource.name
                  : "Detail Panel"}
            </h3>
            <p className="text-[11px] text-gray-400 mt-0.5">
              {showDocument
                ? "Document content"
                : showSource
                  ? "Source information"
                  : "Select a source to inspect"}
            </p>
          </div>

          {/* Focus Mode toggle — document view only */}
          {showDocument && (
            <button
              type="button"
              onClick={isMaximized ? onRestore : onMaximize}
              className="shrink-0 p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-200/50 transition-colors duration-200 ml-auto"
              aria-label={isMaximized ? "Restore default layout" : "Swap to Document Focus Mode"}
              title={isMaximized ? "Restore default layout" : "Swap to Document Focus Mode"}
            >
              <SwapLayoutIcon />
            </button>
          )}

          {/* Restore button for non-document maximized views (soft-lock guard) */}
          {isMaximized && !showDocument && (
            <button
              type="button"
              onClick={onRestore}
              className="shrink-0 p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-200/50 transition-colors duration-200 ml-auto"
              aria-label="Restore default layout"
              title="Restore default layout"
            >
              <SwapLayoutIcon />
            </button>
          )}
        </div>
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
        <EmptyDetail />
      )}

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-gray-200/40">
        {showDocument ? (
          <p className="text-[10px] text-gray-400 text-center">Document content — read only</p>
        ) : showSource ? (
          <p className="text-[10px] text-gray-300 text-center">Source management — actions below</p>
        ) : (
          <p className="text-[10px] text-gray-300 text-center">Click a source in the sidebar</p>
        )}
      </div>
    </aside>
  );
}
