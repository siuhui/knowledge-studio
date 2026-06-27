"use client";

import { useState } from "react";

// ── Types ──

export interface StudioSourceDetail {
  id: string;
  name: string;
  type: "upload" | "link";
  createdAt: string;
  documents: {
    id: string;
    title: string;
    version: string;
    description: string;
    createdAt: string;
  }[];
}

interface StudioPanelProps {
  knowledgeBaseName: string;
  activeDocCount: number;
  /** When set, shows source detail instead of capabilities */
  activeSource: StudioSourceDetail | null;
  onBackToCapabilities: () => void;
  onReExtract: (sourceId: string) => void;
  onDeleteSource: (sourceId: string) => void;
}

// ── Icons ──

function CapabilityIcon({ id }: { id: string }) {
  const map: Record<string, React.ReactNode> = {
    report: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    ),
    slides: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </svg>
    ),
    summary: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    ),
    timeline: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <line x1="12" y1="2" x2="12" y2="22" />
        <polyline points="19 8 12 2 5 8" />
        <polyline points="5 16 12 22 19 16" />
      </svg>
    ),
    qa_bank: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
    custom: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </svg>
    ),
  };
  return <>{map[id]}</>;
}

const CAPABILITIES = [
  { id: "report", label: "Generate Report", description: "Synthesize a structured research report from selected documents" },
  { id: "slides", label: "Create Slides", description: "Turn key findings into a presentation deck" },
  { id: "summary", label: "Executive Summary", description: "Condense selected docs into a one-page brief" },
  { id: "timeline", label: "Timeline", description: "Extract events into a chronological timeline" },
  { id: "qa_bank", label: "Q&A Bank", description: "Generate a question bank from the material" },
  { id: "custom", label: "Custom Output", description: "Define your own output format and structure" },
];

// ── Capabilities view ──

function CapabilitiesView({ disabled }: { disabled: boolean }) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <div className="flex-1 overflow-y-auto px-3 py-3">
      {disabled && (
        <div className="text-center py-4 mb-2">
          <p className="text-[11px] text-gray-300">Select documents to unlock</p>
        </div>
      )}
      <div className="space-y-1">
        {CAPABILITIES.map((cap) => {
          const isHovered = hoveredId === cap.id;
          return (
            <button
              key={cap.id}
              type="button"
              disabled={disabled}
              onMouseEnter={() => setHoveredId(cap.id)}
              onMouseLeave={() => setHoveredId(null)}
              className={`w-full text-left rounded-lg border transition-all duration-200 p-3 group ${
                disabled
                  ? "border-transparent opacity-40 cursor-not-allowed"
                  : "border-transparent hover:bg-white hover:border-gray-200/60 hover:shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <span
                  className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors duration-200 ${
                    isHovered && !disabled ? "bg-[#1A1A1A] text-white" : "bg-gray-200/70 text-gray-500"
                  }`}
                >
                  <CapabilityIcon id={cap.id} />
                </span>
                <div className="flex-1 min-w-0">
                  <p className={`text-xs font-medium transition-colors duration-200 ${isHovered && !disabled ? "text-[#1A1A1A]" : "text-[#2F3437]"}`}>
                    {cap.label}
                  </p>
                  {isHovered && !disabled && (
                    <p className="text-[10px] text-gray-400 mt-0.5">{cap.description}</p>
                  )}
                </div>
                {!disabled && (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                    className={`shrink-0 text-gray-300 transition-all duration-200 ${isHovered ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-1"}`} aria-hidden="true">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Source detail view ──

function SourceDetailView({
  source,
  onBack,
  onReExtract,
  onDeleteSource,
}: {
  source: StudioSourceDetail;
  onBack: () => void;
  onReExtract: (sourceId: string) => void;
  onDeleteSource: (sourceId: string) => void;
}) {
  return (
    <div className="flex-1 overflow-y-auto">
      {/* Back button */}
      <div className="px-4 py-3 border-b border-gray-200/40">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-[#2F3437] transition-colors duration-200 mb-2"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Studio
        </button>

        {/* Source meta */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-200/70 text-gray-500 shrink-0">
            {source.type === "upload" ? "FILE" : "LINK"}
          </span>
          <h3 className="text-sm font-semibold text-[#1A1A1A] truncate">{source.name}</h3>
        </div>
        <p className="text-[10px] text-gray-400 mt-1">
          {new Date(source.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
        </p>
      </div>

      {/* Document versions */}
      <div className="px-3 py-3">
        <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wider px-1 mb-2">
          Document Versions
        </p>
        <div className="space-y-1">
          {source.documents.length === 0 ? (
            <p className="text-[11px] text-gray-300 px-1 py-2">No versions extracted yet</p>
          ) : (
            source.documents.map((doc) => (
              <div
                key={doc.id}
                className="rounded-lg border border-gray-200/60 bg-white p-2.5 flex items-center gap-2.5"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-gray-400" aria-hidden="true">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-[#2F3437] truncate">{doc.title}</p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-[10px] font-medium text-gray-400">{doc.version}</span>
                    <span className="text-[10px] text-gray-300">· {doc.description}</span>
                  </div>
                </div>
                <span className="text-[10px] text-gray-300 shrink-0">
                  {new Date(doc.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="px-3 pb-4 space-y-1.5">
        <button
          type="button"
          onClick={() => onReExtract(source.id)}
          className="w-full flex items-center justify-center gap-2 rounded-lg border border-gray-200/60
            px-3 py-2 text-xs font-medium text-[#2F3437] hover:bg-gray-50/50 hover:border-gray-300
            transition-all duration-200"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="8" y1="11" x2="14" y2="11" />
            <line x1="11" y1="8" x2="11" y2="14" />
          </svg>
          Re-extract
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

// ── Component ──

export function StudioPanel({
  knowledgeBaseName,
  activeDocCount,
  activeSource,
  onBackToCapabilities,
  onReExtract,
  onDeleteSource,
}: StudioPanelProps) {
  const hasDocs = activeDocCount > 0;
  const showDetail = activeSource !== null;

  return (
    <aside className="w-[22%] min-w-[260px] max-w-[320px] shrink-0 h-full bg-[#F7F7F5] flex flex-col border-l border-gray-200/60">
      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-200/40">
        <h3 className="text-sm font-semibold text-[#1A1A1A] tracking-tight">
          {showDetail ? activeSource.name : "Studio"}
        </h3>
        <p className="text-[11px] text-gray-400 mt-0.5">
          {showDetail ? "Source detail" : "Reports, slides & more"}
        </p>
      </div>

      {/* Body */}
      {showDetail ? (
        <SourceDetailView
          source={activeSource}
          onBack={onBackToCapabilities}
          onReExtract={onReExtract}
          onDeleteSource={onDeleteSource}
        />
      ) : (
        <CapabilitiesView disabled={!hasDocs} />
      )}

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-gray-200/40">
        {showDetail ? (
          <p className="text-[10px] text-gray-300 text-center">
            Source management — actions above
          </p>
        ) : hasDocs ? (
          <p className="text-[10px] text-gray-400 text-center">
            <span className="font-medium text-gray-500">{activeDocCount}</span> doc{activeDocCount === 1 ? "" : "s"} in context — Studio ready
          </p>
        ) : (
          <p className="text-[10px] text-gray-300 text-center">
            Select documents to unlock
          </p>
        )}
      </div>
    </aside>
  );
}
