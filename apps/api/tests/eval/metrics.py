"""Retrieval evaluation metrics — pure functions, zero dependencies.

Judgment is passage-level offset-overlap (决策 1), not document-level.  A
retrieved chunk *covers* a golden anchor iff they are in the **same document**
AND their character ranges **overlap**.  Document-level recall ("hit any chunk
of the relevant doc") inflates the number — it rewards retrieving an irrelevant
paragraph of the right document.  We report it too (``doc_recall_at_k``) only to
quantify that inflation against the honest metric.

Spans are ``(doc_key, start, end)`` tuples — 0-based, half-open
(``full_text[start:end]``).  ``doc_key`` is the corpus filename, resolved from
``citation.document_id`` at eval time.

All functions take spans already ordered by retrieval rank and slice to ``k``
internally.  No DB, no I/O — unit-tested in ``test_metrics.py`` and run in CI.
"""

from __future__ import annotations

Span = tuple[str, int, int]
"""(doc_key, start_offset, end_offset) — half-open character range within a doc."""


def overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Two half-open ranges overlap iff they share at least one position.

    Touching ranges (``a_end == b_start``) do NOT overlap — consistent with the
    half-open convention used by the chunker's ``start_offset/end_offset``.
    """
    return a_start < b_end and a_end > b_start


def _covers(retrieved: Span, golden: Span) -> bool:
    """A retrieved span covers a golden span iff same doc AND ranges overlap."""
    r_doc, r_start, r_end = retrieved
    g_doc, g_start, g_end = golden
    return r_doc == g_doc and overlap(r_start, r_end, g_start, g_end)


def answer_ctx_recall_at_k(retrieved_spans: list[Span], golden_spans: list[Span], k: int) -> float:
    """Answer-Context Recall@k (主指标, 诚实口径).

    Fraction of golden anchors covered by at least one of the top-k retrieved
    chunks.  A golden anchor is the character span of a discriminative phrase
    that actually answers the question — covering it means the answer text made
    it into the retrieved context.

    Returns 0.0 when a query has no golden spans (degenerate — should never
    happen after ``validate_anchors()``).
    """
    if not golden_spans:
        return 0.0
    topk = retrieved_spans[:k]
    covered = sum(1 for g in golden_spans if any(_covers(r, g) for r in topk))
    return covered / len(golden_spans)


def doc_recall_at_k(retrieved_doc_keys: list[str], relevant: set[str], k: int) -> float:
    """Doc Recall@k (次指标, 暴露文档级高估).

    Fraction of relevant documents that appear anywhere in the top-k retrieved
    chunks' documents.  Deliberately the inflated document-level view — reported
    alongside the honest metric so the gap is visible.
    """
    if not relevant:
        return 0.0
    topk = set(retrieved_doc_keys[:k])
    found = sum(1 for d in relevant if d in topk)
    return found / len(relevant)


def hit_at_k(retrieved_spans: list[Span], golden_spans: list[Span], k: int) -> float:
    """Hit@k (success rate) — 1.0 if ≥1 golden anchor is covered in top-k, else 0.0.

    Per-query binary; the aggregate mean is the fraction of questions whose
    answer made it into the retrieved context at all.
    """
    if not golden_spans:
        return 0.0
    topk = retrieved_spans[:k]
    return 1.0 if any(_covers(r, g) for g in golden_spans for r in topk) else 0.0


def mrr_at_k(retrieved_spans: list[Span], golden_spans: list[Span], k: int) -> float:
    """MRR@k — reciprocal rank of the first chunk that covers any golden anchor.

    Rewards ranking the answer-bearing chunk high.  Returns 0.0 if no top-k
    chunk covers a golden anchor.
    """
    if not golden_spans:
        return 0.0
    for rank, r in enumerate(retrieved_spans[:k], start=1):
        if any(_covers(r, g) for g in golden_spans):
            return 1.0 / rank
    return 0.0
