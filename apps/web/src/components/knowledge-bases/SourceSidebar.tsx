"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiPaginated, uploadFile } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import type { Document, PaginatedMeta, Source } from "@/lib/types";

interface SourceSidebarProps {
  knowledgeBaseId: string;
  knowledgeBaseName: string;
}

export function SourceSidebar({
  knowledgeBaseId,
  knowledgeBaseName,
}: SourceSidebarProps) {
  const { addToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [source, setSource] = useState<Source | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [meta, setMeta] = useState<PaginatedMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  // Bootstrap: ensure a default "upload" source exists, then load its documents
  const bootstrap = useCallback(async () => {
    setLoading(true);
    try {
      // 1. List sources for this KB
      const sourcesResult = await apiPaginated<Source>(
        `/api/v1/knowledge-bases/${knowledgeBaseId}/sources?page=1&page_size=1`,
      );

      let activeSource: Source;
      if (sourcesResult.data.length === 0) {
        // 2. No source yet — create a default "upload" source
        const created = await api<Source>(
          `/api/v1/knowledge-bases/${knowledgeBaseId}/sources`,
          {
            method: "POST",
            body: JSON.stringify({ type: "upload", config: {} }),
          },
        );
        activeSource = created.data;
      } else {
        activeSource = sourcesResult.data[0];
      }
      setSource(activeSource);

      // 3. Load documents for the source
      const docsResult = await apiPaginated<Document>(
        `/api/v1/sources/${activeSource.id}/documents?page=1&page_size=50`,
      );
      setDocuments(docsResult.data);
      setMeta(docsResult.meta);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to load documents";
      addToast("error", msg);
    } finally {
      setLoading(false);
    }
  }, [knowledgeBaseId, addToast]);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !source) return;

    setUploading(true);
    try {
      await uploadFile("/api/v1/documents/upload", file, {
        source_id: source.id,
      });
      addToast("success", `"${file.name}" uploaded and indexed`);
      bootstrap(); // refresh the list
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to upload document";
      addToast("error", msg);
    } finally {
      setUploading(false);
      // Reset the input so the same file can be re-uploaded
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDeleteDocument = async (doc: Document) => {
    if (!confirm(`Delete "${doc.title}"? This cannot be undone.`)) return;
    try {
      await api(`/api/v1/documents/${doc.id}`, { method: "DELETE" });
      addToast("success", `"${doc.title}" deleted`);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to delete document";
      addToast("error", msg);
    }
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });

  const formatBadge = (fmt: string) => {
    const map: Record<string, string> = {
      pdf: "PDF",
      markdown: "MD",
      text: "TXT",
    };
    return map[fmt] ?? fmt.toUpperCase();
  };

  return (
    <aside className="w-64 shrink-0 border-r border-gray-200/60 flex flex-col h-full bg-[#FBFBFA]">
      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-200/60">
        <h2 className="text-sm font-semibold text-[#2F3437] truncate">
          {knowledgeBaseName}
        </h2>
        <p className="text-[11px] text-gray-400 mt-0.5">
          {meta ? `${meta.total} document${meta.total === 1 ? "" : "s"}` : "Sources"}
        </p>
      </div>

      {/* Upload button */}
      <div className="px-3 py-3">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.md,.txt,.markdown,.text"
          onChange={handleUpload}
          className="hidden"
          aria-label="Upload document"
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full flex items-center justify-center gap-2 rounded-lg
            border-2 border-dashed border-gray-200 px-3 py-2 text-xs font-medium
            text-gray-400 hover:border-gray-300 hover:text-gray-500
            hover:bg-gray-50/50 transition-all duration-150
            disabled:opacity-40 disabled:cursor-not-allowed"
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
            <title>Add</title>
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          {uploading ? "Uploading…" : "Add Document"}
        </button>
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto px-3 pb-4">
        {loading ? (
          <div className="space-y-2">
            {["s1", "s2", "s3", "s4"].map((key) => (
              <div
                key={key}
                className="rounded-lg bg-white border border-gray-200/60 p-3 animate-pulse"
              >
                <div className="h-3 bg-gray-100 rounded w-3/4 mb-1.5" />
                <div className="h-2.5 bg-gray-50 rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-xs text-gray-300">No documents yet</p>
            <p className="text-[11px] text-gray-200 mt-0.5">
              Upload a file to get started
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="group rounded-lg bg-white border border-gray-200/60 p-2.5
                  hover:border-gray-300 transition-colors relative"
              >
                <div className="flex items-start gap-2">
                  {/* Format icon */}
                  <span
                    className="shrink-0 mt-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded
                      bg-gray-100 text-gray-500"
                  >
                    {formatBadge(doc.source_format)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-[#2F3437] truncate font-medium">
                      {doc.title}
                    </p>
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      {formatDate(doc.created_at)}
                    </p>
                  </div>
                  {/* Delete button — visible on hover */}
                  <button
                    type="button"
                    onClick={() => handleDeleteDocument(doc)}
                    className="shrink-0 p-1 rounded opacity-0 group-hover:opacity-100
                      text-gray-400 hover:text-red-500 hover:bg-red-50
                      transition-all duration-150"
                    title="Delete document"
                    aria-label={`Delete ${doc.title}`}
                  >
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
                      <title>Delete</title>
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
