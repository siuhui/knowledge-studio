"use client";

import { useState, useRef } from "react";
import { ModalShell } from "@/components/ui/ModalShell";

interface AddSourceModalProps {
  open: boolean;
  onClose: () => void;
  onAddSource: (file: File) => void;
}

type Tab = "upload" | "link";

const ALLOWED_EXTENSIONS = [".pdf", ".md", ".markdown", ".txt", ".text"];

function checkExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function AddSourceModal({ open, onClose, onAddSource }: AddSourceModalProps) {
  const [tab, setTab] = useState<Tab>("upload");
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  const handleFile = (file: File) => {
    setError("");
    if (!checkExtension(file.name)) {
      setError(`Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`);
      return;
    }
    onAddSource(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handlePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <ModalShell open={open} onClose={onClose}>
      <div
        className="bg-white rounded-xl w-[420px] max-w-[95vw] shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={() => {}}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-gray-200/60">
          <h2 className="text-sm font-semibold text-[#1A1A1A]">Add Source</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">
            Upload a file or add a link to extract knowledge
          </p>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200/60">
          <button
            type="button"
            onClick={() => {
              setTab("upload");
              setError("");
            }}
            className={`flex-1 py-2.5 text-xs font-medium transition-all duration-200 border-b-2 ${
              tab === "upload"
                ? "text-[#1A1A1A] border-[#1A1A1A]"
                : "text-gray-400 border-transparent hover:text-gray-500"
            }`}
          >
            Upload File
          </button>
          <button
            type="button"
            onClick={() => {
              setTab("link");
              setError("");
            }}
            className={`flex-1 py-2.5 text-xs font-medium transition-all duration-200 border-b-2 ${
              tab === "link"
                ? "text-[#1A1A1A] border-[#1A1A1A]"
                : "text-gray-400 border-transparent hover:text-gray-500"
            }`}
          >
            Add Link
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-5">
          {tab === "upload" ? (
            <>
              {/* Upload zone */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                className={`rounded-xl border-2 border-dashed p-10 text-center transition-all duration-200 cursor-pointer ${
                  dragging
                    ? "border-[#1A1A1A] bg-gray-50/50"
                    : "border-gray-200 hover:border-gray-300 hover:bg-gray-50/30"
                }`}
                onClick={() => fileRef.current?.click()}
                // biome-ignore lint/a11y/useSemanticElements: file drop zone
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") fileRef.current?.click();
                }}
              >
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
                    className="text-gray-400"
                    aria-hidden="true"
                  >
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                </div>
                <p className="text-xs text-gray-500 font-medium">
                  Drop a file here or click to browse
                </p>
                <p className="text-[10px] text-gray-300 mt-1">PDF, Markdown, TXT supported</p>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.md,.txt,.markdown,.text"
                  onChange={handlePick}
                  className="hidden"
                />
              </div>
              {error && <p className="text-[11px] text-red-500 mt-2 text-center">{error}</p>}
            </>
          ) : (
            /* Link tab — coming soon */
            <div className="py-8 text-center">
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-gray-300 mx-auto mb-3"
                aria-hidden="true"
              >
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
              <p className="text-xs text-gray-400 font-medium">Coming Soon</p>
              <p className="text-[11px] text-gray-300 mt-1 max-w-xs mx-auto">
                Link ingestion will be available in a future release. Upload files directly for now.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-200/60 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-2 text-xs font-medium text-gray-400
              hover:text-[#2F3437] hover:bg-gray-100/70 transition-all duration-200"
          >
            Cancel
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
