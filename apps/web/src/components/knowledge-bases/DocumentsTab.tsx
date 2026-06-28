"use client";

import { useState } from "react";
import type { FlatDocument } from "@/lib/types";

// ── Icons ──

function DocIcon() {
  return (
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
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0 text-gray-400"
      aria-hidden="true"
    >
      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <polyline points="13 2 13 9 20 9" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0 text-gray-400"
      aria-hidden="true"
    >
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

// ── Checkbox ──

function Checkbox({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onChange();
      }}
      className={`shrink-0 w-4 h-4 rounded border transition-all duration-200 flex items-center justify-center ${
        checked ? "bg-[#1A1A1A] border-[#1A1A1A]" : "border-gray-300 bg-white hover:border-gray-400"
      }`}
      aria-label={checked ? "Deselect document" : "Select document"}
    >
      {checked && (
        <svg
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="white"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
    </button>
  );
}

// ── Component ──

interface DocumentsTabProps {
  documents: FlatDocument[];
  checkedDocIds: Set<string>;
  onToggleDocument: (docId: string) => void;
  /** Called when user clicks the source trace link — switches to Sources tab + selects source */
  onTraceSource?: (sourceId: string) => void;
}

export function DocumentsTab({
  documents,
  checkedDocIds,
  onToggleDocument,
  onTraceSource,
}: DocumentsTabProps) {
  const [search, setSearch] = useState("");

  const filtered = search.trim()
    ? documents.filter((d) => d.title.toLowerCase().includes(search.toLowerCase()))
    : documents;

  return (
    <>
      {/* Search */}
      {documents.length > 0 && (
        <div className="px-3 pb-2">
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-300">
              <SearchIcon />
            </span>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search documents..."
              className="w-full rounded-lg border border-gray-200/60 bg-white/70 pl-7 pr-2.5 py-1.5
                text-[11px] text-[#2F3437] placeholder:text-gray-300
                outline-none focus:border-gray-300 focus:bg-white
                transition-all duration-200"
            />
          </div>
        </div>
      )}

      {/* Document list */}
      <div className="flex-1 overflow-y-auto px-3 pb-4">
        {filtered.length === 0 ? (
          <div className="text-center py-10">
            {documents.length === 0 ? (
              <>
                <p className="text-xs text-gray-300">No documents yet</p>
                <p className="text-[11px] text-gray-200 mt-0.5">
                  Add a source to extract documents
                </p>
              </>
            ) : (
              <p className="text-xs text-gray-300">No documents match &ldquo;{search}&rdquo;</p>
            )}
          </div>
        ) : (
          <div className="space-y-1">
            {filtered.map((doc) => {
              const isChecked = checkedDocIds.has(doc.id);

              return (
                <div
                  key={doc.id}
                  className={`rounded-lg border transition-all duration-200 p-2.5 group ${
                    isChecked
                      ? "bg-white border-gray-300 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
                      : "bg-transparent border-transparent hover:bg-white/60 hover:border-gray-200/60"
                  }`}
                >
                  {/* Main row: checkbox + title */}
                  <div className="flex items-center gap-2.5">
                    <Checkbox checked={isChecked} onChange={() => onToggleDocument(doc.id)} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <DocIcon />
                        <span className="text-xs font-medium text-[#2F3437] truncate">
                          {doc.title}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5 ml-[22px]">
                        <span className="text-[10px] font-medium text-gray-400">{doc.version}</span>
                        <span className="text-[10px] text-gray-300 truncate">
                          · {doc.description}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Source trace line */}
                  <button
                    type="button"
                    onClick={() => onTraceSource?.(doc.sourceId)}
                    className="flex items-center gap-1 mt-2 ml-[26px] text-[10px] text-gray-300
                      hover:text-gray-500 transition-colors duration-200 group/trace"
                  >
                    {doc.sourceType === "upload" ? <FileIcon /> : <LinkIcon />}
                    <span className="truncate max-w-[180px]">from {doc.sourceName}</span>
                    <svg
                      width="10"
                      height="10"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="shrink-0 opacity-0 group-hover/trace:opacity-100 transition-opacity duration-200"
                      aria-hidden="true"
                    >
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
