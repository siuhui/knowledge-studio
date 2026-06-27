"use client";

import { useState, useRef } from "react";
import { ModalShell } from "@/components/ui/ModalShell";

interface AddSourceModalProps {
  open: boolean;
  onClose: () => void;
  onAddSource: (type: "upload" | "link", payload: File | string) => void;
}

type Tab = "upload" | "link";

export function AddSourceModal({ open, onClose, onAddSource }: AddSourceModalProps) {
  const [tab, setTab] = useState<Tab>("upload");
  const fileRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onAddSource("upload", file);
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onAddSource("upload", file);
  };

  const handleAddLink = () => {
    const trimmed = url.trim();
    if (trimmed) onAddSource("link", trimmed);
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
            onClick={() => setTab("upload")}
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
            onClick={() => setTab("link")}
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
            /* ── Upload zone ── */
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
              <p className="text-[10px] text-gray-300 mt-1">
                PDF, Markdown, TXT supported
              </p>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.md,.txt,.markdown,.text"
                onChange={handleFile}
                className="hidden"
              />
            </div>
          ) : (
            /* ── Link input ── */
            <div>
              <label
                htmlFor="source-url"
                className="text-[11px] font-medium text-gray-500 mb-1.5 block"
              >
                URL
              </label>
              <input
                id="source-url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/article"
                className="w-full rounded-lg border border-gray-200/60 px-3 py-2 text-sm
                  text-[#2F3437] placeholder:text-gray-300 outline-none
                  focus:border-gray-400 focus:ring-0 transition-colors duration-200"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAddLink();
                }}
              />
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
          {tab === "link" && (
            <button
              type="button"
              onClick={handleAddLink}
              disabled={!url.trim()}
              className="rounded-lg px-4 py-2 text-xs font-medium bg-[#1A1A1A] text-white
                hover:bg-[#2F3437] transition-all duration-200
                disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Add Link
            </button>
          )}
        </div>
      </div>
    </ModalShell>
  );
}
