"use client";

import { useState, useRef } from "react";
import { ModalShell } from "@/components/ui/ModalShell";

interface AddSourceModalProps {
  open: boolean;
  onClose: () => void;
  onAddFile: (file: File) => void;
  onAddUrl: (url: string) => void;
}

type Tab = "upload" | "url";

const ALLOWED_EXTENSIONS = [".pdf", ".md", ".markdown", ".txt", ".text"];

function checkExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function isValidUrl(raw: string): boolean {
  try {
    const url = new URL(raw.trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function AddSourceModal({ open, onClose, onAddFile, onAddUrl }: AddSourceModalProps) {
  const [tab, setTab] = useState<Tab>("upload");
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");

  const handleFile = (file: File) => {
    setError("");
    if (!checkExtension(file.name)) {
      setError(`Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`);
      return;
    }
    onAddFile(file);
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

  const handleAddUrl = () => {
    setError("");
    const trimmed = url.trim();
    if (!trimmed) {
      setError("Please enter a URL");
      return;
    }
    if (!isValidUrl(trimmed)) {
      setError("Please enter a valid http:// or https:// URL");
      return;
    }
    onAddUrl(trimmed);
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
            Upload a file or add a URL to extract knowledge
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
              setTab("url");
              setError("");
            }}
            className={`flex-1 py-2.5 text-xs font-medium transition-all duration-200 border-b-2 ${
              tab === "url"
                ? "text-[#1A1A1A] border-[#1A1A1A]"
                : "text-gray-400 border-transparent hover:text-gray-500"
            }`}
          >
            Add URL
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
            /* URL input form */
            <div className="space-y-3">
              <div>
                <label
                  htmlFor="source-url"
                  className="block text-[11px] font-medium text-gray-500 mb-1"
                >
                  Enter a URL to extract
                </label>
                <input
                  id="source-url"
                  type="url"
                  placeholder="https://example.com/article"
                  value={url}
                  onChange={(e) => {
                    setUrl(e.target.value);
                    setError("");
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleAddUrl();
                  }}
                  className="w-full rounded-lg border border-gray-200/60 bg-white px-3 py-2 text-xs
                    text-[#2F3437] placeholder-gray-300 outline-none
                    focus:border-gray-400 focus:ring-1 focus:ring-gray-200
                    transition-all duration-200"
                />
                <p className="text-[10px] text-gray-300 mt-1">
                  Web pages are extracted to plain text. JavaScript-heavy pages are supported via
                  browser rendering.
                </p>
              </div>
              {error && <p className="text-[11px] text-red-500">{error}</p>}
              <button
                type="button"
                onClick={handleAddUrl}
                className="w-full rounded-lg bg-[#1A1A1A] px-3 py-2 text-xs font-medium text-white
                  hover:bg-[#2F3437] transition-all duration-200"
              >
                Add URL
              </button>
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
