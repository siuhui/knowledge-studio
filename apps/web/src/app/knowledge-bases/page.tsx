"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { logger } from "@/lib/logger";
import type { KnowledgeBase } from "@/lib/types";

export default function KnowledgeBasesPage() {
  const router = useRouter();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    loadKnowledgeBases();
  }, [router]);

  const loadKnowledgeBases = async () => {
    try {
      const { data } = await api<KnowledgeBase[]>("/api/v1/knowledge-bases");
      setKnowledgeBases(data);
    } catch (err) {
      logger.error("Failed to load knowledge bases", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      await api("/api/v1/knowledge-bases", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), description: description.trim() || null }),
      });
      setName("");
      setDescription("");
      await loadKnowledgeBases();
    } catch (err) {
      logger.error("Failed to create knowledge base", err);
    } finally {
      setCreating(false);
    }
  }, [name, description]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this knowledge base?")) return;
    try {
      await api(`/api/v1/knowledge-bases/${id}`, { method: "DELETE" });
      setKnowledgeBases((prev) => prev.filter((kb) => kb.id !== id));
    } catch (err) {
      logger.error("Failed to delete knowledge base", err);
    }
  };

  if (loading) {
    return <div className="text-center py-8 text-gray-500">Loading...</div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Knowledge Bases</h1>

      {/* Create form */}
      <form onSubmit={handleCreate} className="mb-8 bg-white rounded-lg border p-4 space-y-3">
        <div>
          <input
            type="text"
            placeholder="Knowledge base name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <input
            type="text"
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <button
          type="submit"
          disabled={creating || !name.trim()}
          className="rounded-lg bg-blue-600 px-4 py-2 text-white font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {creating ? "Creating..." : "Create"}
        </button>
      </form>

      {/* List */}
      {knowledgeBases.length === 0 ? (
        <p className="text-center text-gray-500 py-8">
          No knowledge bases yet. Create one above.
        </p>
      ) : (
        <div className="space-y-3">
          {knowledgeBases.map((kb) => (
            <div
              key={kb.id}
              className="bg-white rounded-lg border p-4 flex items-center justify-between hover:shadow-sm transition-shadow"
            >
              <div>
                <h3 className="font-medium text-gray-900">{kb.name}</h3>
                {kb.description && (
                  <p className="text-sm text-gray-500 mt-1">{kb.description}</p>
                )}
                <p className="text-xs text-gray-400 mt-1">
                  Created: {new Date(kb.created_at).toLocaleDateString()}
                </p>
              </div>
              <button
                onClick={() => handleDelete(kb.id)}
                className="text-red-500 hover:text-red-700 text-sm font-medium transition-colors"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
