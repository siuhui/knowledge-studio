"use client";

import { MarkdownContent } from "@/components/ui/MarkdownContent";
import { getDocument } from "@/lib/api";
import type { DocumentDetail } from "@/lib/types";
import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "./StatusBadge";

// ── Processing state ──

function ProcessingView({ document }: { document: DocumentDetail }) {
  return (
    <div className="flex-1 flex items-center justify-center px-4">
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
            className="text-gray-300 animate-spin"
            aria-hidden="true"
          >
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        </div>
        <p className="text-xs text-gray-400 font-medium">Processing document</p>
        <p className="text-[11px] text-gray-300 mt-1 max-w-[220px]">
          This document is still being indexed. Content will appear once processing is complete.
        </p>
      </div>
    </div>
  );
}

// ── Error state ──

function ErrorView({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex-1 flex items-center justify-center px-4">
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
            className="text-red-300"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <p className="text-xs text-red-500 font-medium">Failed to load document</p>
        <p className="text-[11px] text-red-300 mt-1 max-w-[220px]">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 text-[11px] font-medium text-[#2F3437] hover:text-[#1A1A1A] transition-colors duration-200"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

// ── Loading state ──

function LoadingView() {
  return (
    <div className="flex-1 flex items-center justify-center px-4">
      <div className="w-5 h-5 border-2 border-gray-200 border-t-[#1A1A1A] rounded-full animate-spin" />
    </div>
  );
}

// ── Content view ──

function ContentView({ document }: { document: DocumentDetail }) {
  const [showDetails, setShowDetails] = useState(false);
  const [fullText, setFullText] = useState<string | null>(null);
  const [fullTextLoading, setFullTextLoading] = useState(false);

  // Lazily fetch full_text for the reading view.  Chunk data is still used
  // for the detail/inspection view and metadata (chunk_count, etc.).
  const loadFullText = useCallback(async () => {
    if (fullText || fullTextLoading) return;
    setFullTextLoading(true);
    try {
      const detail = await getDocument(document.id, true);
      setFullText(detail.full_text ?? null);
    } catch {
      // Fall back to chunk-join only if full_text fails
    } finally {
      setFullTextLoading(false);
    }
  }, [document.id, fullText, fullTextLoading]);

  useEffect(() => {
    if (!showDetails) {
      loadFullText();
    }
  }, [showDetails, loadFullText]);

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      <div className="px-5 py-4 pb-8">
        {showDetails ? (
          /* ── Detail / inspection view: original chunks with metadata ── */
          document.chunks.map((chunk, i) => (
            <div key={chunk.id} className="mb-4">
              <div className="rounded-lg border border-gray-200/60 bg-white p-3">
                {/* ── Metadata header: single flex row, wraps naturally ── */}
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0 mb-2">
                  <span className="inline-flex items-baseline gap-1.5 min-w-0">
                    <span className="text-[10px] font-semibold text-gray-500 bg-gray-100 shrink-0 px-1.5 py-0.5 rounded tabular-nums leading-normal">
                      #{chunk.chunk_index}
                    </span>
                    {chunk.section_path.length > 0 ? (
                      <span className="text-[11px] font-medium text-[#2F3437] break-words">
                        {chunk.section_path.join(" · ")}
                      </span>
                    ) : (
                      <span className="text-[11px] text-gray-400 italic">Preamble</span>
                    )}
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-[10px] text-gray-400 shrink-0 ml-auto">
                    <span className="tabular-nums">
                      offset [{chunk.start_offset}, {chunk.end_offset})
                    </span>
                    <span className="text-gray-300">·</span>
                    <span>~{chunk.token_count} tokens</span>
                  </span>
                </div>
                {/* ── Raw chunk content ── */}
                <pre className="text-sm text-[#2F3437] leading-relaxed whitespace-pre-wrap break-words font-sans m-0">{chunk.content}</pre>
              </div>
            </div>
          ))
        ) : fullTextLoading ? (
          /* ── Loading full_text ── */
          <div className="flex justify-center py-10">
            <div className="w-5 h-5 border-2 border-gray-200 border-t-[#1A1A1A] rounded-full animate-spin" />
          </div>
        ) : (
          /* ── Reading view: canonical full_text, no chunk join ── */
          <MarkdownContent
            content={fullText ?? ""}
            className="text-sm text-[#2F3437] leading-relaxed break-words"
          />
        )}
      </div>

      {/* Truncation notice */}
      {document.truncated && (
        <div className="px-5 pb-3">
          <p className="text-[10px] text-amber-600 bg-amber-50 rounded-lg px-2.5 py-1.5 border border-amber-100">
            Showing first {document.chunks.length} of {document.chunk_count} sections. Large
            documents are truncated for performance.
          </p>
        </div>
      )}

      {/* Toggle */}
      <div className="px-5 pb-8">
        <button
          type="button"
          onClick={() => setShowDetails(!showDetails)}
          className="flex items-center gap-1.5 text-[11px] text-gray-400 hover:text-gray-500 transition-colors duration-200"
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
            className={`shrink-0 transition-transform duration-200 ${showDetails ? "rotate-90" : ""}`}
            aria-hidden="true"
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          {showDetails ? "Hide indexing details" : "Show indexing details"}
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// DocumentContentView
// ═══════════════════════════════════════════════════════════

interface DocumentContentViewProps {
  document: DocumentDetail | null;
  loading: boolean;
  error: string;
  onBack: () => void;
  onRetry: () => void;
  onDeleteDocument?: (docId: string, docTitle: string) => void;
}

export function DocumentContentView({
  document,
  loading,
  error,
  onBack,
  onRetry,
  onDeleteDocument,
}: DocumentContentViewProps) {
  // Loading
  if (loading) {
    return (
      <div className="flex-1 flex flex-col">
        {/* Minimal header */}
        <div className="px-4 py-3 border-b border-gray-200/40">
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
        </div>
        <LoadingView />
      </div>
    );
  }

  // Error
  if (error) {
    return (
      <div className="flex-1 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-200/40">
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
        </div>
        <ErrorView message={error} onRetry={onRetry} />
      </div>
    );
  }

  // No document
  if (!document) {
    return (
      <div className="flex-1 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-200/40">
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
        </div>
        <ErrorView message="Document not found" onRetry={onRetry} />
      </div>
    );
  }

  const isReady = document.status === "ready";

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      {/* Body */}
      {isReady && document.chunks.length > 0 ? (
        <ContentView document={document} />
      ) : (
        <ProcessingView document={document} />
      )}
    </div>
  );
}
