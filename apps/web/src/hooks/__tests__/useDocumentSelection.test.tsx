import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDocumentSelection } from "@/hooks/useDocumentSelection";
import type { FlatDocument } from "@/lib/types";

function makeDocs(ids: string[]): FlatDocument[] {
  return ids.map((id) => ({
    id,
    sourceId: `src-${id}`,
    sourceName: `Source ${id}`,
    sourceType: "upload" as const,
    title: `Document ${id}`,
    version: "v1",
    description: "test doc",
    status: "ready" as const,
    chunkStatus: "completed" as const,
    embedStatus: "completed" as const,
  }));
}

const DOCS_3 = makeDocs(["doc-1", "doc-2", "doc-3"]);

describe("useDocumentSelection", () => {
  // ── null = select all ──────────────────────────────────────────────

  it("null → selects all documents when documents are available upfront", () => {
    const { result } = renderHook(() => useDocumentSelection(DOCS_3));

    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: null });
    });

    expect(result.current.checkedDocIds).toEqual(new Set(["doc-1", "doc-2", "doc-3"]));
  });

  it("null → selects all documents when documents arrive later (race fix)", () => {
    // Start with empty document list — simulating session loading first.
    const { result, rerender } = renderHook(({ docs }) => useDocumentSelection(docs), {
      initialProps: { docs: [] as FlatDocument[] },
    });

    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: null });
    });

    // Before documents arrive, the Set is empty (no docs to select).
    expect(result.current.checkedDocIds).toEqual(new Set());

    // Documents arrive later.
    rerender({ docs: DOCS_3 });

    // Now the null should be applied against the full document list.
    expect(result.current.checkedDocIds).toEqual(new Set(["doc-1", "doc-2", "doc-3"]));
  });

  // ── [] = select none ───────────────────────────────────────────────

  it("[] → selects no documents", () => {
    const { result } = renderHook(() => useDocumentSelection(DOCS_3));

    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: [] });
    });

    expect(result.current.checkedDocIds).toEqual(new Set());
  });

  it("[] → stays empty even when documents arrive later", () => {
    const { result, rerender } = renderHook(({ docs }) => useDocumentSelection(docs), {
      initialProps: { docs: [] as FlatDocument[] },
    });

    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: [] });
    });

    rerender({ docs: DOCS_3 });

    // [] means "user explicitly selected none" — must stay empty.
    expect(result.current.checkedDocIds).toEqual(new Set());
  });

  // ── [...] = specific IDs ───────────────────────────────────────────

  it("[...] → selects only matching IDs", () => {
    const { result } = renderHook(() => useDocumentSelection(DOCS_3));

    act(() => {
      result.current.restoreDocSelection({
        reference_document_ids: ["doc-1", "doc-3"],
      });
    });

    // Order doesn't matter for Set equality.
    expect(result.current.checkedDocIds).toEqual(new Set(["doc-3", "doc-1"]));
  });

  // ── resetSelection ─────────────────────────────────────────────────

  it("resetSelection selects all documents", () => {
    const { result } = renderHook(() => useDocumentSelection(DOCS_3));

    // Start with empty selection.
    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: [] });
    });
    expect(result.current.checkedDocIds).toEqual(new Set());

    // Reset → select all.
    act(() => {
      result.current.resetSelection();
    });
    expect(result.current.checkedDocIds).toEqual(new Set(["doc-1", "doc-2", "doc-3"]));
  });

  it("resetSelection works when documents arrive later", () => {
    const { result, rerender } = renderHook(({ docs }) => useDocumentSelection(docs), {
      initialProps: { docs: [] as FlatDocument[] },
    });

    act(() => {
      result.current.resetSelection();
    });

    rerender({ docs: DOCS_3 });

    expect(result.current.checkedDocIds).toEqual(new Set(["doc-1", "doc-2", "doc-3"]));
  });

  // ── Edge: no documents at all ──────────────────────────────────────

  it("no documents: checkedDocIds stays empty regardless of value", () => {
    const { result } = renderHook(() => useDocumentSelection([]));

    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: null });
    });

    // No documents → nothing to select.
    expect(result.current.checkedDocIds).toEqual(new Set());
  });

  // ── Switching between values ───────────────────────────────────────

  it("switching null → [] → [...] works correctly in sequence", () => {
    const { result } = renderHook(() => useDocumentSelection(DOCS_3));

    // null → all
    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: null });
    });
    expect(result.current.checkedDocIds).toEqual(new Set(["doc-1", "doc-2", "doc-3"]));

    // [] → none
    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: [] });
    });
    expect(result.current.checkedDocIds).toEqual(new Set());

    // [...] → specific
    act(() => {
      result.current.restoreDocSelection({
        reference_document_ids: ["doc-2"],
      });
    });
    expect(result.current.checkedDocIds).toEqual(new Set(["doc-2"]));

    // back to null → all
    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: null });
    });
    expect(result.current.checkedDocIds).toEqual(new Set(["doc-1", "doc-2", "doc-3"]));
  });

  // ── direct setCheckedDocIds (user toggles checkboxes) ──────────────

  it("user can toggle individual checkboxes via setCheckedDocIds", () => {
    const { result } = renderHook(() => useDocumentSelection(DOCS_3));

    // Start with null (all selected).
    act(() => {
      result.current.restoreDocSelection({ reference_document_ids: null });
    });

    // User unchecks doc-2.
    act(() => {
      result.current.setCheckedDocIds((prev) => {
        const next = new Set(prev);
        next.delete("doc-2");
        return next;
      });
    });

    expect(result.current.checkedDocIds).toEqual(new Set(["doc-1", "doc-3"]));

    // User re-checks doc-2.
    act(() => {
      result.current.setCheckedDocIds((prev) => new Set(prev).add("doc-2"));
    });

    expect(result.current.checkedDocIds).toEqual(new Set(["doc-1", "doc-2", "doc-3"]));
  });
});
