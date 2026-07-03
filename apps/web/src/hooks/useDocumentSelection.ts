"use client";

import { useState, useEffect, useCallback } from "react";
import type { FlatDocument } from "@/lib/types";

/**
 * Manages document checkbox selection, especially the null-vs-[] distinction
 * in session ``reference_document_ids``.
 *
 * ``reference_document_ids: null``   → all documents selected (default)
 * ``reference_document_ids: []``     → none selected
 * ``reference_document_ids: [...]``  → only those IDs selected
 *
 * The hook stores ``reference_document_ids`` internally so it can be applied
 * **reactively** when ``documents`` arrives — avoiding the race where the
 * session loads before the documents list.
 */
export function useDocumentSelection(documents: FlatDocument[]) {
  const [checkedDocIds, setCheckedDocIds] = useState<Set<string>>(new Set());
  const [sessionRefDocIds, setSessionRefDocIds] = useState<string[] | null>(null);

  // Apply sessionRefDocIds reactively whenever documents changes.
  useEffect(() => {
    if (documents.length === 0) return;

    if (sessionRefDocIds === null) {
      // null → select all
      setCheckedDocIds(new Set(documents.map((d) => d.id)));
    } else if (sessionRefDocIds.length === 0) {
      // [] → select none
      setCheckedDocIds(new Set());
    } else {
      // [...] → select only those IDs that still exist
      setCheckedDocIds(new Set(sessionRefDocIds));
    }
  }, [documents, sessionRefDocIds]);

  const restoreDocSelection = useCallback((detail: { reference_document_ids: string[] | null }) => {
    setSessionRefDocIds(detail.reference_document_ids);
  }, []);

  /** Reset to initial "select all" state (used for new chat). */
  const resetSelection = useCallback(() => {
    setSessionRefDocIds(null);
  }, []);

  return {
    checkedDocIds,
    setCheckedDocIds,
    restoreDocSelection,
    resetSelection,
  } as const;
}
