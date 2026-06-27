"use client";

// ── Types ──

export interface FlatDocument {
  id: string;
  sourceId: string;
  sourceName: string;
  sourceType: "upload" | "link";
  title: string;
  version: string;
  description: string;
}

export interface SourceNode {
  id: string;
  name: string;
  type: "upload" | "link";
  documents: {
    id: string;
    sourceId: string;
    title: string;
    version: string;
    description: string;
  }[];
}

/** Flatten SourceNode[] → FlatDocument[] for display */
export function flattenDocs(sources: SourceNode[]): FlatDocument[] {
  return sources.flatMap((s) =>
    s.documents.map((d) => ({
      id: d.id,
      sourceId: s.id,
      sourceName: s.name,
      sourceType: s.type,
      title: d.title,
      version: d.version,
      description: d.description,
    })),
  );
}

interface DocumentPanelProps {
  knowledgeBaseName: string;
  documents: FlatDocument[];
  checkedDocIds: Set<string>;
  onToggleDocument: (docId: string) => void;
  onAddSource: () => void;
  /** Called when user clicks the source trace on a document */
  onTraceSource?: (sourceId: string) => void;
}

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
        checked
          ? "bg-[#1A1A1A] border-[#1A1A1A]"
          : "border-gray-300 bg-white hover:border-gray-400"
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

export function DocumentPanel({
  knowledgeBaseName,
  documents,
  checkedDocIds,
  onToggleDocument,
  onAddSource,
  onTraceSource,
}: DocumentPanelProps) {
  const checkedCount = checkedDocIds.size;

  return (
    <aside className="w-[22%] min-w-[260px] max-w-[320px] shrink-0 h-full bg-[#F7F7F5] flex flex-col border-r border-gray-200/60">
      {/* ── Header ── */}
      <div className="px-4 py-4 border-b border-gray-200/40">
        <h2 className="text-sm font-semibold text-[#1A1A1A] truncate">
          {knowledgeBaseName}
        </h2>
        <p className="text-[11px] text-gray-400 mt-0.5">
          {documents.length} document{documents.length === 1 ? "" : "s"}
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

      {/* ── Flat document list ── */}
      <div className="flex-1 overflow-y-auto px-3 pb-4">
        {documents.length === 0 ? (
          <div className="text-center py-10">
            <p className="text-xs text-gray-300">No documents yet</p>
            <p className="text-[11px] text-gray-200 mt-0.5">
              Add a source to extract documents
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {documents.map((doc) => {
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
                    <Checkbox
                      checked={isChecked}
                      onChange={() => onToggleDocument(doc.id)}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <DocIcon />
                        <span className="text-xs font-medium text-[#2F3437] truncate">
                          {doc.title}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5 ml-[22px]">
                        <span className="text-[10px] font-medium text-gray-400">
                          {doc.version}
                        </span>
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
                    {doc.sourceType === "upload" ? (
                      <FileIcon />
                    ) : (
                      <LinkIcon />
                    )}
                    <span className="truncate max-w-[180px]">
                      from {doc.sourceName}
                    </span>
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
