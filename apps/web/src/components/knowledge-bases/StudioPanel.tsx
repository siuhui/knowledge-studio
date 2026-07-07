"use client";

import type { ReportTask } from "@/lib/types";

// ── Action card ──

interface ActionCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  disabled?: boolean;
  disabledLabel?: string;
  onClick: () => void;
}

function ActionCard({
  icon,
  title,
  description,
  disabled = false,
  disabledLabel,
  onClick,
}: ActionCardProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`w-full text-left rounded-xl border p-4 transition-all duration-200 group
        ${
          disabled
            ? "border-gray-200/40 bg-gray-50/30 cursor-not-allowed opacity-60"
            : "border-gray-200/60 bg-white hover:border-gray-300 hover:shadow-[0_2px_8px_rgba(0,0,0,0.06)] active:scale-[0.99]"
        }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`shrink-0 w-10 h-10 rounded-lg flex items-center justify-center transition-colors duration-200
            ${
              disabled
                ? "bg-gray-100 text-gray-400"
                : "bg-[#F1F1F4] text-[#1A1A1A] group-hover:bg-[#E8E8EB]"
            }`}
        >
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-[#1A1A1A]">{title}</h4>
            {disabled && disabledLabel && (
              <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600 shrink-0">
                {disabledLabel}
              </span>
            )}
          </div>
          <p className="text-[11px] text-gray-400 mt-0.5 leading-relaxed">{description}</p>
        </div>
      </div>
    </button>
  );
}

// ── Icons ──

function ReportIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function PptIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="9" y1="21" x2="9" y2="9" />
    </svg>
  );
}

function ClockIcon() {
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
      aria-hidden="true"
      className="text-gray-300"
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

// ── Main component ──

interface StudioPanelProps {
  reports: ReportTask[];
  selectedDocCount: number;
  onCreateReport: () => void;
  onViewReport: (report: ReportTask) => void;
}

export function StudioPanel({
  reports,
  selectedDocCount,
  onCreateReport,
  onViewReport,
}: StudioPanelProps) {
  const noSelection = selectedDocCount === 0;
  return (
    <div className="flex-1 overflow-y-auto pb-8 custom-scrollbar">
      {/* Actions */}
      <div className="px-4 py-4 space-y-3">
        <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wider px-1">
          Create
        </p>

        <ActionCard
          icon={<ReportIcon />}
          title="Generate Report"
          description="Deep-dive analysis into a structured multi-chapter markdown report"
          disabled={noSelection}
          disabledLabel={noSelection ? "No documents selected" : undefined}
          onClick={onCreateReport}
        />

        <ActionCard
          icon={<PptIcon />}
          title="Generate Presentation"
          description="Coming in a future update — export findings as a slide deck"
          disabled
          disabledLabel="Soon"
          onClick={() => {}}
        />
      </div>

      {/* Recent tasks */}
      <div className="px-4 py-3">
        <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wider px-1 mb-2">
          Recent Outputs
        </p>

        {reports.length === 0 ? (
          <div className="flex items-center gap-2 px-1 py-3">
            <ClockIcon />
            <p className="text-[11px] text-gray-300">
              Generated reports and presentations will appear here
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {reports.map((report) => (
              <button
                key={report.id}
                type="button"
                onClick={() => onViewReport(report)}
                className={`w-full text-left flex items-center gap-2.5 px-2.5 py-2 rounded-lg border transition-all duration-200
                  ${
                    report.status === "completed"
                      ? "border-gray-200/40 bg-white hover:border-gray-300 hover:shadow-[0_1px_3px_rgba(0,0,0,0.04)] cursor-pointer"
                      : "border-gray-200/40 bg-white hover:border-gray-300 hover:shadow-[0_1px_3px_rgba(0,0,0,0.04)] cursor-pointer"
                  }`}
              >
                <div className="shrink-0 w-2 h-2 rounded-full">
                  {report.status === "generating" ? (
                    <span className="block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                  ) : report.status === "completed" ? (
                    <span className="block w-2 h-2 rounded-full bg-emerald-400" />
                  ) : (
                    <span className="block w-2 h-2 rounded-full bg-red-400" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-[#2F3437] truncate">{report.title}</p>
                  <p className="text-[10px] text-gray-400">
                    {report.status === "generating"
                      ? "Generating…"
                      : report.status === "completed"
                        ? "Completed — click to view"
                        : "Failed — click for details"}
                  </p>
                </div>
                <span
                  className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full shrink-0
                    ${
                      report.type === "report"
                        ? "bg-blue-50 text-blue-500"
                        : "bg-purple-50 text-purple-500"
                    }`}
                >
                  {report.type === "report" ? "Report" : "PPT"}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
