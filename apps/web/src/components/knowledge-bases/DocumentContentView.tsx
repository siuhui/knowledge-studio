"use client";

import { useState } from "react";
import type { DocumentDetail } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { renderMarkdown } from "@/lib/markdown";

// ── Format badge ──

function FormatBadge({ format }: { format: string }) {
  return (
    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-200/70 text-gray-500 shrink-0">
      {format.toUpperCase()}
    </span>
  );
}

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

/**
 * Remove overlapping text between consecutive chunks.
 *
 * Backend chunks with OVERLAP=50 tokens (~200 chars): each chunk i (i>0)
 * prepends the tail of chunk i-1. This deduplicates so the reading view
 * shows one continuous, non-repeating document.
 *
 * showDetails mode skips dedup — it shows raw chunks for inspection.
 */
function deduplicateChunks(chunks: { content: string }[]): string[] {
  const result: string[] = [];
  for (let i = 0; i < chunks.length; i++) {
    if (i === 0) {
      result.push(chunks[i].content);
    } else {
      const prev = result[i - 1];
      const current = chunks[i].content;
      // Check if current chunk starts with a suffix of previous chunk (max 200 chars)
      let overlapLen = 0;
      const maxOverlap = Math.min(200, prev.length);
      for (let len = maxOverlap; len > 0; len--) {
        if (current.startsWith(prev.slice(-len))) {
          overlapLen = len;
          break;
        }
      }
      result.push(current.slice(overlapLen));
    }
  }
  return result;
}

function ContentView({ document }: { document: DocumentDetail }) {
  const [showDetails, setShowDetails] = useState(false);

  // Dedup for reading view; detail view shows raw chunks
  const deduped = deduplicateChunks(document.chunks);
  // Merge raw deduped text without extra separator — the backend overlap
  // already inserts "\n" between chunks, so each deduped[i] (i>0) starts with "\n"
  const mergedHtml = renderMarkdown(deduped.join(""));

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      {/* Reading view: continuous flowing text, no separators */}
      <div className="px-5 py-4">
        {showDetails ? (
          /* ── Detail / inspection view: original chunks with metadata ── */
          document.chunks.map((chunk, i) => (
            <div key={chunk.id} className="mb-4">
              <div className="rounded-lg border border-gray-200/60 bg-white p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] font-medium text-gray-400 bg-gray-100/80 px-1.5 py-0.5 rounded">
                    Section {i + 1}
                  </span>
                  <span className="text-[10px] text-gray-300">~{chunk.token_count} tokens</span>
                  <span className="text-[10px] text-gray-300 ml-auto">
                    Chunk #{chunk.chunk_index}
                  </span>
                </div>
                <div
                  className="text-sm text-[#2F3437] leading-relaxed break-words"
                  // biome-ignore lint/security/noDangerouslySetInnerHtml: content is sanitized by renderMarkdown
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(chunk.content) }}
                />
              </div>
            </div>
          ))
        ) : (
          /* ── Reading view: single continuous, deduplicated text ── */
          <div
            className="text-sm text-[#2F3437] leading-relaxed break-words"
            // biome-ignore lint/security/noDangerouslySetInnerHtml: content is sanitized by renderMarkdown
            dangerouslySetInnerHTML={{ __html: mergedHtml }}
          />
        )}
      </div>

      {/* Truncation notice */}
      {document.truncated && (
        <div className="px-5 pb-3">
          <p className="text-[10px] text-amber-600 bg-amber-50 rounded-lg px-2.5 py-1.5 border border-amber-100">
            Showing first {document.chunks.length} of {document.chunk_count} sections. Large documents
            are truncated for performance.
          </p>
        </div>
      )}

      {/* Toggle */}
      <div className="px-5 pb-4">
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
            Back
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
            Back
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
            Back
          </button>
        </div>
        <ErrorView message="Document not found" onRetry={onRetry} />
      </div>
    );
  }

  const isActive = document.status === "active";

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      {/* Header */}
      <div className="px-5 py-3 border-b border-gray-200/40">
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
          <FormatBadge format={document.source_format} />
          <StatusBadge status={document.status} />
          {/* Trash icon — only deletion entry point */}
          {onDeleteDocument && (
            <button
              type="button"
              onClick={() => onDeleteDocument(document.id, document.title)}
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
        </div>
        <h3 className="text-sm font-semibold text-[#1A1A1A] truncate mt-1">{document.title}</h3>
        <p className="text-[10px] text-gray-400 mt-0.5">
          {document.chunk_count === 0
            ? "No indexed sections yet"
            : `${document.chunk_count} indexed section${document.chunk_count === 1 ? "" : "s"}`}
          {" · "}
          Created{" "}
          {new Date(document.created_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </p>
      </div>

      {/* Body */}
      {isActive && document.chunks.length > 0 ? (
        <ContentView document={document} />
      ) : (
        <ProcessingView document={document} />
      )}
    </div>
  );
}
