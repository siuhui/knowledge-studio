"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Toast } from "@/components/ui/Toast";

interface ToastItem {
  id: string;
  type: "success" | "error";
  message: string;
}

interface ToastContextValue {
  toasts: ToastItem[];
  addToast: (type: "success" | "error", message: string) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_DURATION = 5000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (type: "success" | "error", message: string) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, type, message }]);
      setTimeout(() => removeToast(id), TOAST_DURATION);
    },
    [removeToast],
  );

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" aria-live="polite">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            id={toast.id}
            type={toast.type}
            message={toast.message}
            onDismiss={removeToast}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
