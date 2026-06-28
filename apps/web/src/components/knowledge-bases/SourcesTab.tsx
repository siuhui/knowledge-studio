"use client";

import type { Source } from "@/lib/types";

// ── Status badge helpers ──

interface StatusBadgeProps {
  status: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  pending: "bg-amber-100 text-amber-700",
  error: "bg-red-100 text-red-600",
};

function StatusBadge({ status }: StatusBadgeProps) {
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  const color = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-500";
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full shrink-0 ${color}`}>
      {label}
    </span>
  );
}

// ── Type icon ──

function SourceTypeIcon({ type }: { type: string }) {
  if (type === "upload") {
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
        <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
        <polyline points="13 2 13 9 20 9" />
      </svg>
    );
  }
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
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}

// ── Helpers ──

function sourceDisplayName(source: Source): string {
  const config = source.config as Record<string, unknown> | null;
  return (config?.original_name as string) ?? "";
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

// ── Component ──

interface SourcesTabProps {
  sources: Source[];
  activeSourceId: string | null;
  onSelectSource: (sourceId: string) => void;
}

export function SourcesTab({ sources, activeSourceId, onSelectSource }: SourcesTabProps) {
  if (sources.length === 0) {
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
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
              <polyline points="13 2 13 9 20 9" />
            </svg>
          </div>
          <p className="text-xs text-gray-300">No sources yet</p>
          <p className="text-[11px] text-gray-200 mt-0.5">
            Upload a file or add a link to get started
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-3 pb-4">
      <div className="space-y-1">
        {sources.map((source) => {
          const isActive = activeSourceId === source.id;
          const name = sourceDisplayName(source);

          return (
            <button
              key={source.id}
              type="button"
              onClick={() => onSelectSource(source.id)}
              className={`w-full text-left rounded-lg border transition-all duration-200 p-2.5 group ${
                isActive
                  ? "bg-white border-gray-300 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
                  : "bg-transparent border-transparent hover:bg-white/60 hover:border-gray-200/60"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <SourceTypeIcon type={source.type} />
                <div className="flex-1 min-w-0">
                  {name ? (
                    <p className="text-xs font-medium text-[#2F3437] truncate">{name}</p>
                  ) : (
                    <p className="text-xs text-gray-300 italic truncate">—</p>
                  )}
                  <p className="text-[10px] text-gray-300 mt-0.5">
                    {formatDate(source.created_at)}
                  </p>
                </div>
                <StatusBadge status={source.status} />
                {isActive && (
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
