"use client";

import { useState, useRef, useEffect } from "react";
import type { SessionItem } from "@/lib/types";
import { ConfirmModal } from "@/components/ui/ConfirmModal";

interface SessionBarProps {
  sessions: SessionItem[];
  activeSessionId: string | null;
  loading: boolean;
  onSelectSession: (session: SessionItem) => void;
  onNewChat: () => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onDeleteSession: (sessionId: string) => void;
}

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export function SessionBar({
  sessions,
  activeSessionId,
  loading,
  onSelectSession,
  onNewChat,
  onRenameSession,
  onDeleteSession,
}: SessionBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null;

  // Close menu on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleClick);
      return () => document.removeEventListener("mousedown", handleClick);
    }
  }, [menuOpen]);

  // Focus edit input
  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  const handleSelect = (session: SessionItem) => {
    setMenuOpen(false);
    onSelectSession(session);
  };

  const handleRenameStart = (session: SessionItem) => {
    setEditTitle(session.title);
    setEditingId(session.id);
  };

  const handleRenameSubmit = (sessionId: string) => {
    const trimmed = editTitle.trim();
    if (trimmed && trimmed.length <= 255) {
      onRenameSession(sessionId, trimmed);
    }
    setEditingId(null);
  };

  const handleDeleteConfirm = () => {
    if (deleteId) {
      onDeleteSession(deleteId);
      setDeleteId(null);
    }
  };

  return (
    <>
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200/60 bg-[#FAFAFA] shrink-0">
        {/* Session dropdown */}
        <div className="relative flex-1 min-w-0" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen(!menuOpen)}
            disabled={loading}
            className="w-full flex items-center gap-2 rounded-lg border border-gray-200/60
              bg-white px-3 py-1.5 text-left text-xs
              hover:border-gray-300 transition-colors duration-150
              disabled:opacity-50"
          >
            {loading ? (
              <span className="text-gray-300 text-xs">Loading...</span>
            ) : activeSession ? (
              <>
                <span className="truncate flex-1 text-[#2F3437] font-medium">
                  {editingId === activeSession.id ? (
                    <input
                      ref={editInputRef as React.RefObject<HTMLInputElement>}
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleRenameSubmit(activeSession.id);
                        if (e.key === "Escape") setEditingId(null);
                        e.stopPropagation();
                      }}
                      onBlur={() => handleRenameSubmit(activeSession.id)}
                      onClick={(e) => e.stopPropagation()}
                      maxLength={255}
                      className="w-full outline-none bg-transparent text-xs"
                    />
                  ) : (
                    activeSession.title
                  )}
                </span>
                <span className="text-[10px] text-gray-300 shrink-0">
                  {relativeTime(activeSession.last_message_at)}
                </span>
              </>
            ) : (
              <span className="text-gray-300 text-xs">New Chat</span>
            )}
            <svg
              width="10"
              height="10"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`text-gray-300 shrink-0 transition-transform ${menuOpen ? "rotate-180" : ""}`}
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {/* Dropdown menu */}
          {menuOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-xl border border-gray-200/80 shadow-lg z-30 max-h-64 overflow-y-auto">
              {sessions.length === 0 ? (
                <div className="px-3 py-4 text-center">
                  <p className="text-[11px] text-gray-300">No chats yet</p>
                </div>
              ) : (
                sessions.map((s) => (
                  <div
                    key={s.id}
                    className={`group flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors
                      ${s.id === activeSessionId ? "bg-gray-50" : "hover:bg-gray-50/50"}`}
                  >
                    <button
                      type="button"
                      className="flex-1 text-left min-w-0"
                      onClick={() => handleSelect(s)}
                    >
                      {editingId === s.id ? (
                        <input
                          ref={editInputRef as React.RefObject<HTMLInputElement>}
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleRenameSubmit(s.id);
                            if (e.key === "Escape") setEditingId(null);
                            e.stopPropagation();
                          }}
                          onBlur={() => handleRenameSubmit(s.id)}
                          onClick={(e) => e.stopPropagation()}
                          maxLength={255}
                          className="w-full outline-none bg-transparent text-xs"
                        />
                      ) : (
                        <>
                          <span className="text-xs text-[#2F3437] truncate block">{s.title}</span>
                          <span className="text-[10px] text-gray-300">
                            {s.message_count} msgs · {relativeTime(s.last_message_at)}
                          </span>
                        </>
                      )}
                    </button>

                    {/* Action buttons */}
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRenameStart(s);
                        }}
                        className="p-1 text-gray-300 hover:text-gray-500 rounded"
                        aria-label="Rename session"
                      >
                        <svg
                          width="10"
                          height="10"
                          viewBox="0 0 24 24"
                          fill="none"
                          role="img"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <title>Rename</title>
                          <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteId(s.id);
                          setMenuOpen(false);
                        }}
                        className="p-1 text-gray-300 hover:text-red-400 rounded"
                        aria-label="Delete session"
                      >
                        <svg
                          width="10"
                          height="10"
                          viewBox="0 0 24 24"
                          fill="none"
                          role="img"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <title>Delete</title>
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* New Chat button */}
        <button
          type="button"
          onClick={onNewChat}
          className="flex items-center justify-center w-7 h-7 rounded-lg
            bg-white border border-gray-200/60 text-gray-400
            hover:border-gray-300 hover:text-[#2F3437] hover:bg-gray-50
            transition-all duration-150 shrink-0"
          aria-label="New chat"
        >
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            role="img"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <title>New chat</title>
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>

      {/* Delete confirmation */}
      <ConfirmModal
        open={deleteId !== null}
        title="Delete Chat"
        message="This will permanently delete the chat session and all its messages."
        confirmLabel="Delete"
        danger
        loading={false}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteId(null)}
      />
    </>
  );
}
