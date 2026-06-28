"use client";

import { useRouter } from "next/navigation";
import type { KnowledgeBase } from "@/lib/types";

interface KbCardProps {
  kb: KnowledgeBase;
  onEdit: (kb: KnowledgeBase) => void;
  onDelete: (kb: KnowledgeBase) => void;
}

export function KbCard({ kb, onEdit, onDelete }: KbCardProps) {
  const router = useRouter();

  const handleClick = () => {
    router.push(`/knowledge-bases/${kb.id}`);
  };

  const createdDate = new Date(kb.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div
      onClick={handleClick}
      className="group bg-white rounded-xl border border-gray-200/60 p-5 cursor-pointer
        hover:shadow-[0_2px_8px_rgba(0,0,0,0.06)] hover:border-gray-300
        transition-all duration-150 flex flex-col min-h-[172px] relative"
      // biome-ignore lint/a11y/useSemanticElements: card with block content
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") handleClick();
      }}
    >
      {/* Action buttons — top right, visible on hover */}
      <div className="absolute top-3 right-3 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-10">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onEdit(kb);
          }}
          className="p-1.5 rounded-md text-gray-400 hover:text-[#2F3437] hover:bg-gray-100/70 transition-colors"
          title="Rename"
          aria-label="Rename knowledge base"
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
            <title>Edit</title>
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(kb);
          }}
          className="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
          title="Delete"
          aria-label="Delete knowledge base"
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
            <title>Delete</title>
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      </div>

      {/* Icon */}
      <div className="mb-3">
        <div className="w-10 h-10 rounded-lg bg-gray-100/70 flex items-center justify-center">
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
            <title>Knowledge Base</title>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
        </div>
      </div>

      {/* Name */}
      <h3 className="font-medium text-sm text-[#2F3437] mb-1 line-clamp-2 leading-snug">
        {kb.name}
      </h3>

      {/* Description */}
      {kb.description ? (
        <p className="text-xs text-gray-400 line-clamp-2 mb-3 leading-relaxed">{kb.description}</p>
      ) : (
        <p className="text-xs text-gray-300 italic mb-3">No description</p>
      )}

      {/* Spacer pushes footer down */}
      <div className="flex-1" />

      {/* Created date */}
      <p className="text-[11px] text-gray-300">{createdDate}</p>
    </div>
  );
}
