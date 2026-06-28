"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { logger } from "@/lib/logger";
import type { KnowledgeBase } from "@/lib/types";

/**
 * Thin layout: auth guard + load KB metadata.
 * The page renders the full immersive workspace.
 */
export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadKb = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api<KnowledgeBase>(`/api/v1/knowledge-bases/${id}`);
      setKb(result.data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Knowledge base not found";
      setError(msg);
      logger.error("Failed to load knowledge base", err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    loadKb();
  }, [loadKb, router]);

  if (loading) {
    return (
      <div className="h-[calc(100vh-3rem)] flex items-center justify-center bg-white">
        <div className="w-8 h-8 border-2 border-gray-200 border-t-[#1A1A1A] rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !kb) {
    return (
      <div className="h-[calc(100vh-3rem)] flex items-center justify-center bg-white">
        <div className="text-center">
          <p className="text-sm text-gray-400 mb-3">{error || "Not found"}</p>
          <button
            type="button"
            onClick={() => router.push("/knowledge-bases")}
            className="text-xs rounded-lg border border-gray-200/60 px-3 py-1.5
              text-gray-500 hover:text-[#2F3437] hover:bg-gray-100/70 transition-all"
          >
            ← Back to list
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
