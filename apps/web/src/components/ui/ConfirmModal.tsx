"use client";

import { useEffect, useRef } from "react";
import { ModalShell } from "./ModalShell";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  danger = false,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  return (
    <ModalShell open={open} onClose={onCancel}>
      <div
        className="bg-white rounded-2xl shadow-[0_4px_24px_rgba(0,0,0,0.08)] border border-gray-200/60 p-6 w-full max-w-sm"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={() => { /* prevent event bubbling */ }}
      >
        <h2 className="text-base font-semibold text-[#2F3437] mb-2">{title}</h2>
        <p className="text-sm text-gray-500 leading-relaxed mb-6">{message}</p>

        <div className="flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded-lg px-4 py-2 text-sm font-medium text-gray-500
              hover:text-[#2F3437] hover:bg-gray-100/70 transition-colors
              disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors
              disabled:opacity-40 disabled:cursor-not-allowed ${
                danger
                  ? "bg-red-600 text-white hover:bg-red-700"
                  : "bg-[#1A1A1A] text-white hover:bg-[#2F3437]"
              }`}
          >
            {loading ? "Deleting…" : confirmLabel}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
