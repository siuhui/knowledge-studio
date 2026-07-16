"""Unit tests for retrieval metrics — pure functions, no DB/API. Runs in CI.

Verifies the four metrics + ``overlap()`` against hardcoded span/doc lists.
"""

from tests.eval.metrics import (
    answer_ctx_recall_at_k,
    doc_recall_at_k,
    hit_at_k,
    mrr_at_k,
    overlap,
)

# ── overlap() ────────────────────────────────────────────────────────────────


class TestOverlap:
    def test_disjoint_ranges_do_not_overlap(self) -> None:
        assert overlap(0, 10, 20, 30) is False
        assert overlap(20, 30, 0, 10) is False

    def test_touching_ranges_do_not_overlap(self) -> None:
        # half-open: [0,10) and [10,20) share no position
        assert overlap(0, 10, 10, 20) is False

    def test_partial_overlap(self) -> None:
        assert overlap(0, 10, 5, 15) is True
        assert overlap(5, 15, 0, 10) is True

    def test_contained_range_overlaps(self) -> None:
        assert overlap(0, 100, 40, 50) is True
        assert overlap(40, 50, 0, 100) is True

    def test_single_position_overlap(self) -> None:
        assert overlap(0, 11, 10, 20) is True  # position 10 shared


# ── answer_ctx_recall_at_k() ───────────────────────────────────────────────────


class TestAnswerCtxRecall:
    def test_full_recall(self) -> None:
        golden = [("doc_a", 100, 120), ("doc_b", 50, 70)]
        retrieved = [("doc_a", 90, 130), ("doc_b", 40, 80)]
        assert answer_ctx_recall_at_k(retrieved, golden, k=5) == 1.0

    def test_partial_recall(self) -> None:
        golden = [("doc_a", 100, 120), ("doc_b", 50, 70)]
        retrieved = [("doc_a", 90, 130)]  # only covers first
        assert answer_ctx_recall_at_k(retrieved, golden, k=5) == 0.5

    def test_zero_recall_wrong_doc(self) -> None:
        # overlapping offsets but different document → no cover
        golden = [("doc_a", 100, 120)]
        retrieved = [("doc_b", 100, 120)]
        assert answer_ctx_recall_at_k(retrieved, golden, k=5) == 0.0

    def test_zero_recall_no_overlap(self) -> None:
        golden = [("doc_a", 100, 120)]
        retrieved = [("doc_a", 0, 50)]
        assert answer_ctx_recall_at_k(retrieved, golden, k=5) == 0.0

    def test_k_truncates_retrieved(self) -> None:
        golden = [("doc_a", 100, 120)]
        # the covering chunk sits at rank 6 — excluded at k=5
        retrieved = [("doc_x", 0, 1)] * 5 + [("doc_a", 100, 120)]
        assert answer_ctx_recall_at_k(retrieved, golden, k=5) == 0.0
        assert answer_ctx_recall_at_k(retrieved, golden, k=10) == 1.0

    def test_empty_golden_returns_zero(self) -> None:
        assert answer_ctx_recall_at_k([("doc_a", 0, 10)], [], k=5) == 0.0

    def test_empty_retrieved_returns_zero(self) -> None:
        assert answer_ctx_recall_at_k([], [("doc_a", 0, 10)], k=5) == 0.0


# ── doc_recall_at_k() ──────────────────────────────────────────────────────────


class TestDocRecall:
    def test_full_doc_recall(self) -> None:
        assert doc_recall_at_k(["doc_a", "doc_b"], {"doc_a", "doc_b"}, k=5) == 1.0

    def test_partial_doc_recall(self) -> None:
        assert doc_recall_at_k(["doc_a", "doc_x"], {"doc_a", "doc_b"}, k=5) == 0.5

    def test_doc_recall_inflates_over_answer_ctx(self) -> None:
        # Retrieving the right doc but the wrong passage: doc_recall=1.0,
        # answer_ctx_recall=0.0 — exactly the inflation 决策 1 warns about.
        golden = [("doc_a", 500, 520)]
        retrieved_spans = [("doc_a", 0, 50)]
        retrieved_docs = ["doc_a"]
        assert doc_recall_at_k(retrieved_docs, {"doc_a"}, k=5) == 1.0
        assert answer_ctx_recall_at_k(retrieved_spans, golden, k=5) == 0.0

    def test_k_truncates_docs(self) -> None:
        retrieved = ["doc_x"] * 5 + ["doc_a"]
        assert doc_recall_at_k(retrieved, {"doc_a"}, k=5) == 0.0
        assert doc_recall_at_k(retrieved, {"doc_a"}, k=10) == 1.0

    def test_empty_relevant_returns_zero(self) -> None:
        assert doc_recall_at_k(["doc_a"], set(), k=5) == 0.0


# ── hit_at_k() ─────────────────────────────────────────────────────────────────


class TestHitAtK:
    def test_hit_when_any_anchor_covered(self) -> None:
        golden = [("doc_a", 100, 120), ("doc_b", 50, 70)]
        retrieved = [("doc_b", 40, 80)]  # covers only second
        assert hit_at_k(retrieved, golden, k=5) == 1.0

    def test_miss_when_none_covered(self) -> None:
        golden = [("doc_a", 100, 120)]
        retrieved = [("doc_a", 0, 50), ("doc_c", 0, 50)]
        assert hit_at_k(retrieved, golden, k=5) == 0.0

    def test_k_truncates(self) -> None:
        golden = [("doc_a", 100, 120)]
        retrieved = [("doc_x", 0, 1)] * 5 + [("doc_a", 100, 120)]
        assert hit_at_k(retrieved, golden, k=5) == 0.0
        assert hit_at_k(retrieved, golden, k=10) == 1.0

    def test_empty_golden_returns_zero(self) -> None:
        assert hit_at_k([("doc_a", 0, 10)], [], k=5) == 0.0


# ── mrr_at_k() ─────────────────────────────────────────────────────────────────


class TestMRRAtK:
    def test_first_rank(self) -> None:
        golden = [("doc_a", 100, 120)]
        retrieved = [("doc_a", 90, 130), ("doc_b", 0, 10)]
        assert mrr_at_k(retrieved, golden, k=10) == 1.0

    def test_third_rank(self) -> None:
        golden = [("doc_a", 100, 120)]
        retrieved = [("doc_x", 0, 1), ("doc_y", 0, 1), ("doc_a", 100, 120)]
        assert mrr_at_k(retrieved, golden, k=10) == 1.0 / 3

    def test_no_hit_returns_zero(self) -> None:
        golden = [("doc_a", 100, 120)]
        retrieved = [("doc_x", 0, 1), ("doc_y", 0, 1)]
        assert mrr_at_k(retrieved, golden, k=10) == 0.0

    def test_hit_beyond_k_returns_zero(self) -> None:
        golden = [("doc_a", 100, 120)]
        retrieved = [("doc_x", 0, 1)] * 9 + [("doc_a", 100, 120)]  # rank 10
        assert mrr_at_k(retrieved, golden, k=5) == 0.0
        assert mrr_at_k(retrieved, golden, k=10) == 1.0 / 10

    def test_takes_first_of_multiple_hits(self) -> None:
        golden = [("doc_a", 100, 120), ("doc_b", 50, 70)]
        retrieved = [("doc_c", 0, 1), ("doc_b", 40, 80), ("doc_a", 90, 130)]
        # first cover is at rank 2 (doc_b)
        assert mrr_at_k(retrieved, golden, k=10) == 1.0 / 2

    def test_empty_golden_returns_zero(self) -> None:
        assert mrr_at_k([("doc_a", 0, 10)], [], k=5) == 0.0
