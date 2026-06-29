"use client";

import { useState } from "react";
import type { FlatDocument, Source } from "@/lib/types";
import { DocumentsTab } from "./DocumentsTab";
import { SourcesTab } from "./SourcesTab";

// ── Types ──

type ActiveTab = "documents" | "sources";

interface LeftSidebarProps {
  knowledgeBaseName: string;
  documents: FlatDocument[];
  sources: Source[];
  checkedDocIds: Set<string>;
  activeSourceId: string | null;
  sourcesFirstLoad: boolean;
  sourcesError: string;
  onToggleDocument: (docId: string) => void;
  onAddSource: () => void;
  onSelectSource: (sourceId: string) => void;
  onSelectDocument: (documentId: string) => void;
  onTraceSource: (sourceId: string) => void;
}

// ── Component ──

export function LeftSidebar({
  knowledgeBaseName,
  documents,
  sources,
  checkedDocIds,
  activeSourceId,
  sourcesFirstLoad,
  sourcesError,
  onToggleDocument,
  onAddSource,
  onSelectSource,
  onSelectDocument,
  onTraceSource,
}: LeftSidebarProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>("documents");

  const checkedCount = checkedDocIds.size;

  const handleTraceSource = (sourceId: string) => {
    setActiveTab("sources");
    onTraceSource(sourceId);
  };

  return (
    <aside className="w-[22%] min-w-[260px] max-w-[320px] shrink-0 h-full bg-[#F7F7F5] flex flex-col border-r border-gray-200/60">
      {/* ── Header ── */}
      <div className="px-4 py-4 border-b border-gray-200/40">
        <h2 className="text-sm font-semibold text-[#1A1A1A] truncate">{knowledgeBaseName}</h2>
        <p className="text-[11px] text-gray-400 mt-0.5">
          {activeTab === "documents"
            ? `${documents.length} document${documents.length === 1 ? "" : "s"}`
            : `${sources.length} source${sources.length === 1 ? "" : "s"}`}
          {checkedCount > 0 && ` · ${checkedCount} active`}
        </p>
      </div>

      {/* ── + Add Source ── */}
      <div className="px-3 py-3">
        <button
          type="button"
          onClick={onAddSource}
          className="w-full flex items-center justify-center gap-2 rounded-lg
            bg-white border border-gray-200/60 px-3 py-2 text-xs font-medium
            text-[#2F3437] hover:border-gray-300 hover:bg-gray-50/50
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
            aria-hidden="true"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Source
        </button>
      </div>

      {/* ── Loading / error ── */}
      {sourcesFirstLoad && sources.length === 0 && (
        <div className="px-3 py-6 flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-gray-200 border-t-[#1A1A1A] rounded-full animate-spin" />
        </div>
      )}
      {sourcesError && (
        <div className="px-3 py-2">
          <p className="text-[11px] text-red-500 bg-red-50 rounded-lg px-2.5 py-1.5 border border-red-100">
            {sourcesError}
          </p>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="flex mx-3 border-b border-gray-200/40">
        <button
          type="button"
          onClick={() => setActiveTab("documents")}
          className={`flex-1 py-2 text-[11px] font-medium transition-all duration-200 border-b-2 ${
            activeTab === "documents"
              ? "text-[#1A1A1A] border-[#1A1A1A]"
              : "text-gray-400 border-transparent hover:text-gray-500"
          }`}
        >
          Documents
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("sources")}
          className={`flex-1 py-2 text-[11px] font-medium transition-all duration-200 border-b-2 ${
            activeTab === "sources"
              ? "text-[#1A1A1A] border-[#1A1A1A]"
              : "text-gray-400 border-transparent hover:text-gray-500"
          }`}
        >
          Sources
        </button>
      </div>

      {/* ── Tab content ── */}
      {activeTab === "documents" ? (
        <DocumentsTab
          documents={documents}
          checkedDocIds={checkedDocIds}
          onToggleDocument={onToggleDocument}
          onSelectDocument={onSelectDocument}
          onTraceSource={handleTraceSource}
        />
      ) : (
        <SourcesTab
          sources={sources}
          activeSourceId={activeSourceId}
          onSelectSource={onSelectSource}
        />
      )}

      {/* ── Footer ── */}
      {checkedCount > 0 && (
        <div className="px-4 py-2.5 border-t border-gray-200/40 bg-white/50">
          <p className="text-[10px] text-gray-500">
            <span className="font-medium">{checkedCount}</span> document
            {checkedCount === 1 ? "" : "s"} in AI context
          </p>
        </div>
      )}
    </aside>
  );
}
