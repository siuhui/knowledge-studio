"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { ModalShell } from "@/components/ui/ModalShell";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

interface CreateKbModalProps {
  open: boolean;
  onCreated: () => void;
  onClose: () => void;
}

export function CreateKbModal({ open, onCreated, onClose }: CreateKbModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const { addToast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError("");
    setSubmitting(true);
    try {
      await api("/api/v1/knowledge-bases", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      });
      const createdName = name.trim();
      setName("");
      setDescription("");
      setError("");
      addToast("success", `"${createdName}" created`);
      onCreated();
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create knowledge base";
      setError(msg);
      addToast("error", msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell open={open} onClose={onClose}>
      <div
        className="bg-white rounded-2xl shadow-[0_4px_24px_rgba(0,0,0,0.08)] border border-gray-200/60 p-6 w-full max-w-sm"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={() => {
          /* prevent event bubbling */
        }}
      >
        <h2 className="text-base font-semibold text-[#2F3437] mb-4">Create Knowledge Base</h2>

        <form onSubmit={handleSubmit} className="space-y-3">
          <Input value={name} onChange={setName} placeholder="Knowledge base name" required />
          <Input
            value={description}
            onChange={setDescription}
            placeholder="Description (optional)"
          />

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50/50 p-2.5 text-sm text-red-600">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="secondary" disabled={submitting} onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={submitting || !name.trim()}>
              {submitting ? "Creating…" : "Create"}
            </Button>
          </div>
        </form>
      </div>
    </ModalShell>
  );
}
