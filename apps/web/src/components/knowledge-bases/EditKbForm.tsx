"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import type { KnowledgeBase } from "@/lib/types";

interface EditKbFormProps {
  kb: KnowledgeBase;
  onUpdated: () => void;
  onCancel: () => void;
}

export function EditKbForm({ kb, onUpdated, onCancel }: EditKbFormProps) {
  const [name, setName] = useState(kb.name);
  const [description, setDescription] = useState(kb.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { addToast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError("");
    setSaving(true);
    try {
      await api(`/api/v1/knowledge-bases/${kb.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      });
      addToast("success", "Knowledge base updated");
      onUpdated();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update knowledge base";
      setError(msg);
      addToast("error", msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Input value={name} onChange={setName} placeholder="Knowledge base name" required />
      <Input value={description} onChange={setDescription} placeholder="Description (optional)" />
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50/50 p-3 text-sm text-red-600">
          {error}
        </div>
      )}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={saving || !name.trim()}>
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button type="button" variant="secondary" disabled={saving} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
