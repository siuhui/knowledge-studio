"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

interface CreateKbFormProps {
  onCreated: () => void;
}

export function CreateKbForm({ onCreated }: CreateKbFormProps) {
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
      setName("");
      setDescription("");
      addToast("success", `"${name.trim()}" created`);
      onCreated();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create knowledge base";
      setError(msg);
      addToast("error", msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mb-8 bg-white rounded-xl border border-gray-200/60 p-5 space-y-3 shadow-[0_1px_3px_rgba(0,0,0,0.02)]"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-medium text-gray-400 uppercase tracking-wider">
          Create Knowledge Base
        </h2>
        <Button
          type="submit"
          variant="primary"
          disabled={submitting || !name.trim()}
        >
          {submitting ? "Creating…" : "Create"}
        </Button>
      </div>
      <Input
        value={name}
        onChange={setName}
        placeholder="Knowledge base name"
        required
        className="text-sm"
      />
      <Input
        value={description}
        onChange={setDescription}
        placeholder="Description (optional)"
        className="text-sm"
      />
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50/50 p-3 text-sm text-red-600">
          {error}
        </div>
      )}
    </form>
  );
}
