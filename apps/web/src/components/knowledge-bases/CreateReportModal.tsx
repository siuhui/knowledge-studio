"use client";

import { ModalShell } from "@/components/ui/ModalShell";
import { useState } from "react";

// ── Types ──

export interface ReportConfig {
  title: string;
  instruction: string;
  style: "professional" | "casual" | "academic";
  length: "short" | "medium" | "long";
}

interface CreateReportModalProps {
  open: boolean;
  loading: boolean;
  onClose: () => void;
  onCreate: (config: ReportConfig) => void;
}

// ── Style options ──

const STYLES: { value: ReportConfig["style"]; label: string; description: string }[] = [
  {
    value: "professional",
    label: "Professional",
    description: "Formal tone suited for business and technical audiences",
  },
  {
    value: "casual",
    label: "Casual",
    description: "Conversational and approachable, ideal for internal briefings",
  },
  {
    value: "academic",
    label: "Academic",
    description: "Rigorous and citation-heavy, with formal structure",
  },
];

const LENGTHS: { value: ReportConfig["length"]; label: string; description: string }[] = [
  { value: "short", label: "Short", description: "Concise overview, ~2–3 pages" },
  { value: "medium", label: "Medium", description: "Standard depth, ~5–8 pages" },
  { value: "long", label: "Long", description: "Comprehensive analysis, ~10+ pages" },
];

// ── Component ──

export function CreateReportModal({ open, loading, onClose, onCreate }: CreateReportModalProps) {
  const [title, setTitle] = useState("");
  const [instruction, setInstruction] = useState("");
  const [style, setStyle] = useState<ReportConfig["style"]>("professional");
  const [length, setLength] = useState<ReportConfig["length"]>("medium");

  const canSubmit = title.trim().length > 0 && instruction.trim().length > 0 && !loading;

  const handleCreate = () => {
    if (!canSubmit) return;
    onCreate({ title: title.trim(), instruction: instruction.trim(), style, length });
    // Reset form
    setTitle("");
    setInstruction("");
    setStyle("professional");
    setLength("medium");
  };

  const handleClose = () => {
    if (loading) return; // prevent closing during generation
    setTitle("");
    setInstruction("");
    setStyle("professional");
    setLength("medium");
    onClose();
  };

  return (
    <ModalShell open={open} onClose={handleClose}>
      {/* biome-ignore lint/a11y/useKeyWithClickEvents: ModalShell handles Escape, form handles Enter */}
      <div
        className="bg-white rounded-2xl shadow-xl w-[480px] max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-5 border-b border-gray-100">
          <h2 className="text-base font-semibold text-[#1A1A1A]">Generate Report</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Configure the report parameters — the AI will plan, research, and write it chapter by
            chapter.
          </p>
        </div>

        {/* Form */}
        <div className="px-6 py-5 space-y-5">
          {/* Title */}
          <div>
            <label
              htmlFor="report-title"
              className="block text-xs font-medium text-[#2F3437] mb-1.5"
            >
              Report Title <span className="text-red-400">*</span>
            </label>
            <input
              id="report-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Security Architecture Assessment"
              disabled={loading}
              className="w-full rounded-lg border border-gray-200/80 px-3 py-2 text-sm text-[#2F3437]
                placeholder:text-gray-300 outline-none focus:border-gray-400 focus:ring-1 focus:ring-gray-200
                transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>

          {/* Instruction */}
          <div>
            <label
              htmlFor="report-instruction"
              className="block text-xs font-medium text-[#2F3437] mb-1.5"
            >
              Instructions <span className="text-red-400">*</span>
            </label>
            <textarea
              id="report-instruction"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Describe what the report should cover, which documents to focus on, any specific angles or questions to address…"
              rows={4}
              disabled={loading}
              className="w-full rounded-lg border border-gray-200/80 px-3 py-2 text-sm text-[#2F3437]
                placeholder:text-gray-300 outline-none focus:border-gray-400 focus:ring-1 focus:ring-gray-200
                transition-all duration-200 resize-none disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>

          {/* Style */}
          <div>
            <p className="text-xs font-medium text-[#2F3437] mb-2">Writing Style</p>
            <div className="grid grid-cols-3 gap-2">
              {STYLES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  disabled={loading}
                  onClick={() => setStyle(s.value)}
                  className={`text-left rounded-lg border px-3 py-2.5 transition-all duration-200
                    ${
                      style === s.value
                        ? "border-[#1A1A1A] bg-[#F7F7F5] ring-1 ring-[#1A1A1A]/10"
                        : "border-gray-200/60 hover:border-gray-300"
                    }
                    disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  <p className="text-xs font-medium text-[#2F3437]">{s.label}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5 leading-snug">{s.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Length */}
          <div>
            <p className="text-xs font-medium text-[#2F3437] mb-2">Length</p>
            <div className="grid grid-cols-3 gap-2">
              {LENGTHS.map((l) => (
                <button
                  key={l.value}
                  type="button"
                  disabled={loading}
                  onClick={() => setLength(l.value)}
                  className={`text-left rounded-lg border px-3 py-2.5 transition-all duration-200
                    ${
                      length === l.value
                        ? "border-[#1A1A1A] bg-[#F7F7F5] ring-1 ring-[#1A1A1A]/10"
                        : "border-gray-200/60 hover:border-gray-300"
                    }
                    disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  <p className="text-xs font-medium text-[#2F3437]">{l.label}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5 leading-snug">{l.description}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleClose}
            disabled={loading}
            className="rounded-lg px-4 py-2 text-sm font-medium text-gray-500 hover:text-[#2F3437]
              hover:bg-gray-100/70 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleCreate}
            disabled={!canSubmit}
            className="rounded-lg px-5 py-2 text-sm font-medium bg-[#1A1A1A] text-white
              hover:bg-[#2F3437] shadow-[0_1px_3px_rgba(0,0,0,0.08)] transition-all duration-200
              active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed
              disabled:active:scale-100 flex items-center gap-2"
          >
            {loading ? (
              <>
                <svg
                  width="14"
                  height="14"
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
                Generating…
              </>
            ) : (
              "Generate"
            )}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
