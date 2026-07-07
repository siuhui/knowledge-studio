"use client";

import { ModalShell } from "@/components/ui/ModalShell";
import { MarkdownContent } from "@/components/ui/MarkdownContent";
import type { ReportTask } from "@/lib/types";

interface ReportViewerModalProps {
  open: boolean;
  report: ReportTask | null;
  onClose: () => void;
  onDownload: (report: ReportTask) => void;
  onDelete: (report: ReportTask) => void;
}

export function ReportViewerModal({
  open,
  report,
  onClose,
  onDownload,
  onDelete,
}: ReportViewerModalProps) {
  return (
    <ModalShell open={open} onClose={onClose}>
      {/* biome-ignore lint/a11y/useKeyWithClickEvents: ModalShell handles Escape */}
      <div
        className="bg-white rounded-2xl shadow-xl w-[min(90vw,900px)] max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3 shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-[#1A1A1A] truncate">
                {report?.title ?? "Report"}
              </h2>
              {report && (
                <span
                  className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full shrink-0
                    ${report.type === "report" ? "bg-blue-50 text-blue-500" : "bg-purple-50 text-purple-500"}`}
                >
                  {report.type === "report" ? "Report" : "PPT"}
                </span>
              )}
            </div>
          </div>

          {/* Actions */}
          {report && report.status === "completed" && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onDownload(report)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-[#1A1A1A] hover:bg-gray-100 rounded-lg transition-colors"
              >
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
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Download
              </button>
              <button
                type="button"
                onClick={() => onDelete(report)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
              >
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
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
                Delete
              </button>
            </div>
          )}

          {report && report.status === "failed" && (
            <button
              type="button"
              onClick={() => onDelete(report)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
            >
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
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              Delete
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="shrink-0 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label="Close report viewer"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-8 py-6">
          {report?.status === "generating" ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-gray-200 border-t-[#1A1A1A] rounded-full animate-spin mb-4" />
              <p className="text-sm font-medium text-[#2F3437]">Generating report…</p>
              <p className="text-xs text-gray-400 mt-1">
                The AI is planning, researching, and writing each chapter.
              </p>
            </div>
          ) : report?.status === "failed" ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="flex justify-center mb-3">
                <svg
                  width="28"
                  height="28"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1"
                  className="text-red-300"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <p className="text-sm font-medium text-red-500">Generation failed</p>
              <p className="text-xs text-red-400 mt-1 text-center max-w-sm">
                {report.error || "An unexpected error occurred."}
              </p>
            </div>
          ) : report?.status === "completed" ? (
            <MarkdownContent
              content={report.content}
              className="text-sm text-[#2F3437] leading-relaxed"
            />
          ) : (
            <div className="flex flex-col items-center justify-center py-20">
              <p className="text-xs text-gray-300">No content to display.</p>
            </div>
          )}
        </div>
      </div>
    </ModalShell>
  );
}
