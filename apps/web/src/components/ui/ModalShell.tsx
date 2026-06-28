"use client";

import { useEffect, useRef } from "react";

interface ModalShellProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

/** Shared modal overlay with Escape key and click-outside-to-dismiss. */
export function ModalShell({ open, onClose, children }: ModalShellProps) {
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) {
      previousFocus.current = document.activeElement as HTMLElement | null;
    } else if (previousFocus.current) {
      previousFocus.current.focus();
      previousFocus.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    // biome-ignore lint/a11y/useSemanticElements: overlay backdrop is a presentation-only layer
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-[1px] p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      onKeyDown={() => {
        /* click-to-dismiss handled by Esc listener above */
      }}
    >
      {children}
    </div>
  );
}
