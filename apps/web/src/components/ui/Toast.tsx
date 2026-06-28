"use client";

interface ToastProps {
  id: string;
  type: "success" | "error";
  message: string;
  onDismiss: (id: string) => void;
}

export function Toast({ id, type, message, onDismiss }: ToastProps) {
  const borderClass = type === "success" ? "border-gray-200" : "border-red-200";

  const dotClass = type === "success" ? "bg-emerald-500" : "bg-red-500";

  return (
    <div
      className={`bg-white border ${borderClass} text-[#2F3437] px-4 py-3 rounded-lg shadow-[0_1px_3px_rgba(0,0,0,0.04)] flex items-center gap-3 min-w-[300px] max-w-md animate-slide-in`}
      // biome-ignore lint/a11y/useSemanticElements: role="alert" is the correct ARIA pattern for toast notifications
      role="alert"
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotClass}`} />
      <span className="flex-1 text-sm">{message}</span>
      <button
        type="button"
        onClick={() => onDismiss(id)}
        className="text-gray-400 hover:text-gray-600 shrink-0 transition-colors"
        aria-label="Dismiss"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path
            d="M3 3l8 8M11 3l-8 8"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </div>
  );
}
