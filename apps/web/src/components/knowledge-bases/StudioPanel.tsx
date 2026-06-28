"use client";

// ── Types ──

export interface StudioSourceDocument {
  id: string;
  title: string;
  version: string;
  description: string;
  createdAt: string;
}

export interface StudioSourceDetail {
  id: string;
  name: string;
  type: "upload" | "link";
  status: string;
  createdAt: string;
  documents: StudioSourceDocument[];
}

interface StudioPanelProps {
  activeSource: StudioSourceDetail | null;
  extracting: boolean;
  onBack: () => void;
  onReExtract: (sourceId: string) => void;
  onDeleteSource: (sourceId: string) => void;
}

// ── Status badge ──

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  pending: "bg-amber-100 text-amber-700",
  error: "bg-red-100 text-red-600",
};

function StatusBadge({ status }: { status: string }) {
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  const color = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-500";
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${color}`}>{label}</span>
  );
}

// ── Placeholder view (no source selected) ──

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
}: {
  source: StudioSourceDetail;
  extracting: boolean;
  onBack: () => void;
  onReExtract: (sourceId: string) => void;
  onDeleteSource: (sourceId: string) => void;
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
              <div
                key={doc.id}
                className="rounded-lg border border-gray-200/60 bg-white p-2.5 flex items-center gap-2.5"
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
                  <p className="text-xs font-medium text-[#2F3437] truncate">{doc.title}</p>
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

// ── Component ──

export function StudioPanel({
  activeSource,
  extracting,
  onBack,
  onReExtract,
  onDeleteSource,
}: StudioPanelProps) {
  const showDetail = activeSource !== null;

  return (
    <aside className="w-[22%] min-w-[260px] max-w-[320px] shrink-0 h-full bg-[#F7F7F5] flex flex-col border-l border-gray-200/60">
      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-200/40">
        <h3 className="text-sm font-semibold text-[#1A1A1A] tracking-tight">
          {showDetail ? activeSource.name : "Source Detail"}
        </h3>
        <p className="text-[11px] text-gray-400 mt-0.5">
          {showDetail ? "Source information" : "Select a source to inspect"}
        </p>
      </div>

      {/* Body */}
      {showDetail ? (
        <SourceDetailView
          source={activeSource}
          extracting={extracting}
          onBack={onBack}
          onReExtract={onReExtract}
          onDeleteSource={onDeleteSource}
        />
      ) : (
        <EmptyDetail />
      )}

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-gray-200/40">
        {showDetail ? (
          <p className="text-[10px] text-gray-300 text-center">Source management — actions below</p>
        ) : (
          <p className="text-[10px] text-gray-300 text-center">Click a source in the sidebar</p>
        )}
      </div>
    </aside>
  );
}
