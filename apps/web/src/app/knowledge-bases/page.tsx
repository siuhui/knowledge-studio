"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, apiPaginated } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { logger } from "@/lib/logger";
import { useToast } from "@/hooks/useToast";
import { KbCard } from "@/components/knowledge-bases/KbCard";
import { Pagination } from "@/components/knowledge-bases/Pagination";
import { CreateKbModal } from "@/components/knowledge-bases/CreateKbModal";
import { EditKbModal } from "@/components/knowledge-bases/EditKbModal";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import type { KnowledgeBase, PaginatedMeta } from "@/lib/types";

const PAGE_SIZE = 12;

export default function KnowledgeBasesPage() {
  const router = useRouter();
  const { addToast } = useToast();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [meta, setMeta] = useState<PaginatedMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);

  // ── Modal state ──
  const [createOpen, setCreateOpen] = useState(false);
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null);
  const [deletingKb, setDeletingKb] = useState<KnowledgeBase | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    loadKbs(1);
  }, [router]);

  const loadKbs = useCallback(async (pageNum: number) => {
    setLoading(true);
    setError("");
    try {
      const result = await apiPaginated<KnowledgeBase>(
        `/api/v1/knowledge-bases?page=${pageNum}&page_size=${PAGE_SIZE}`,
      );
      setKnowledgeBases(result.data);
      setMeta(result.meta);
      setPage(pageNum);

      if (result.data.length === 0 && pageNum > 1) {
        loadKbs(pageNum - 1);
        return;
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load knowledge bases";
      setError(msg);
      logger.error("Failed to load knowledge bases", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleCreated = () => {
    // New KB always appears on page 1
    if (page === 1) {
      loadKbs(1);
    } else {
      loadKbs(1);
      setPage(1);
    }
  };

  const handleUpdated = () => {
    loadKbs(page);
  };

  // Called when user clicks "Edit" on a card
  const handleEditClick = (kb: KnowledgeBase) => {
    setEditingKb(kb);
  };

  // Called when user clicks "Delete" on a card
  const handleDeleteClick = (kb: KnowledgeBase) => {
    setDeletingKb(kb);
  };

  // Called when user confirms delete in ConfirmModal
  const handleDeleteConfirm = async () => {
    if (!deletingKb) return;
    setDeleteLoading(true);
    try {
      await api(`/api/v1/knowledge-bases/${deletingKb.id}`, { method: "DELETE" });
      addToast("success", `"${deletingKb.name}" deleted`);
      setKnowledgeBases((prev) => prev.filter((kb) => kb.id !== deletingKb.id));
      setDeletingKb(null);
      // Refetch if we emptied a non-first page
      if (knowledgeBases.length === 1 && page > 1) {
        loadKbs(page - 1);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete";
      addToast("error", msg);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handlePageChange = (newPage: number) => {
    loadKbs(newPage);
  };

  return (
    <div className="max-w-6xl mx-auto px-6 sm:px-8 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-[#2F3437] tracking-tight">Knowledge Bases</h1>
        {meta && (
          <p className="text-sm text-gray-400 mt-1">
            {meta.total} knowledge base{meta.total === 1 ? "" : "s"}
          </p>
        )}
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50/50 p-3 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {/* "+ Create Knowledge Base" card — always first */}
        <div
          onClick={() => setCreateOpen(true)}
          className="rounded-xl border-2 border-dashed border-gray-200 p-5
            flex flex-col items-center justify-center text-center cursor-pointer
            hover:border-gray-300 hover:bg-gray-50/50 transition-all duration-150
            min-h-[172px]"
          // biome-ignore lint/a11y/useSemanticElements: card with block content
          role="button"
          tabIndex={0}
          aria-label="Create knowledge base"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") setCreateOpen(true);
          }}
        >
          <div className="w-10 h-10 rounded-full bg-gray-100/70 flex items-center justify-center mb-3">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-gray-400"
              aria-hidden="true"
            >
              <title>Create</title>
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </div>
          <h3 className="text-sm font-medium text-gray-400">Create Knowledge Base</h3>
        </div>

        {/* Skeleton loading cards */}
        {loading &&
          knowledgeBases.length === 0 &&
          ["s1", "s2", "s3", "s4", "s5", "s6", "s7"].map((key) => (
            <div
              key={key}
              className="rounded-xl border border-gray-200/60 p-5 min-h-[172px] animate-pulse"
            >
              <div className="w-10 h-10 rounded-lg bg-gray-100 mb-3" />
              <div className="h-4 bg-gray-100 rounded w-3/4 mb-2" />
              <div className="h-3 bg-gray-50 rounded w-full mb-1" />
              <div className="h-3 bg-gray-50 rounded w-2/3" />
            </div>
          ))}

        {/* Knowledge base cards */}
        {knowledgeBases.map((kb) => (
          <KbCard key={kb.id} kb={kb} onEdit={handleEditClick} onDelete={handleDeleteClick} />
        ))}
      </div>

      {/* Empty state */}
      {!loading && knowledgeBases.length === 0 && (
        <div className="text-center py-16">
          <div className="flex justify-center mb-4">
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-gray-300"
              aria-hidden="true"
            >
              <title>Empty</title>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          </div>
          <h3 className="text-sm font-medium text-gray-400 mb-1">No knowledge bases yet</h3>
          <p className="text-xs text-gray-300">
            Click &ldquo;Create Knowledge Base&rdquo; to get started.
          </p>
        </div>
      )}

      {/* Pagination */}
      {meta && meta.total_pages > 1 && (
        <Pagination meta={meta} onPageChange={handlePageChange} loading={loading} />
      )}

      {/* ── Modals ── */}
      <CreateKbModal
        open={createOpen}
        onCreated={handleCreated}
        onClose={() => setCreateOpen(false)}
      />

      {editingKb && (
        <EditKbModal
          open={editingKb !== null}
          kb={editingKb}
          onUpdated={handleUpdated}
          onClose={() => setEditingKb(null)}
        />
      )}

      {deletingKb && (
        <ConfirmModal
          open={deletingKb !== null}
          title={`Delete "${deletingKb.name}"?`}
          message="This knowledge base and all its documents will be permanently deleted. This action cannot be undone."
          confirmLabel="Delete"
          danger
          loading={deleteLoading}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeletingKb(null)}
        />
      )}
    </div>
  );
}
