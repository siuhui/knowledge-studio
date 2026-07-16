"""Level 1 retrieval-quality eval — CLI driver.

Runs ``direct`` retrieval over the seeded eval corpus and reports four
side-by-side metrics, each sliced at k=1/3/5/10 from a single top_k=10
retrieval depth:

    Answer-Context Recall  — 主指标, 诚实口径 (passage-level offset overlap)
    Doc Recall             — 次指标, 暴露文档级高估 (document-level)
    Hit                    — success rate (≥1 anchor covered)
    MRR@10                 — rank quality of the first covered anchor

k=1/3 exist because k=5/10 saturate on this corpus: each doc is only ~8-10
chunks, so a top-10 retrieval almost always covers the target doc and Hit@5
pins to 1.0.  The tighter slices retain signal for ranking-quality regressions
(a correct chunk demoted from rank-2 to rank-4 shows up at @1/@3, not @5).

Only ``direct`` is evaluated (决策 3).  It is the single-pass exposure of the
shared ``hybrid_retrieve`` + RRF + chunk stack that agentic also builds on;
measuring direct measures that stack honestly.  Agentic adds a non-deterministic
orchestration layer whose payoff is *answer quality*, scored by Level 2, not
chunk ranking.

The eval reads ``RetrievalChunk.citation.start_offset/end_offset`` — direct's
``build_citations()`` fills these authoritatively from ``Chunk.start_offset/
end_offset``.  Chunk-level 1:1 granularity is preserved (NOT the doc-level
dedup of ``chat.py::_build_citations()``), which is exactly what the honest
passage-level metric needs.

Run:
    python -m tests.eval.retrieval_eval --top-k 10
    python -m tests.eval.retrieval_eval --top-k 10 --reset   # rebuild corpus first
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.services.retrieval.service import RetrievalService
from tests.eval.metrics import Span, answer_ctx_recall_at_k, doc_recall_at_k, hit_at_k, mrr_at_k
from tests.eval.seed import SeedResult, seed
from tests.eval.test_set import TEST_QUERIES, EvalQuery

logger = structlog.get_logger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# k slices computed from a single top_k=10 retrieval depth. k=1/k=3 expose
# ranking quality that k=5/k=10 saturate away (the target doc is ~8-10 chunks,
# so top-10 almost always covers it — hit@5 pins to 1.0 and stops discriminating).
K_VALUES = (1, 3, 5, 10)
MRR_K = 10


# ── Per-query evaluation ──────────────────────────────────────────────────────


@dataclass
class QueryEval:
    """One query's retrieved evidence + its scores at every k."""

    query: EvalQuery
    retrieved_spans: list[Span]  # ordered by retrieval rank
    retrieved_doc_keys: list[str]  # ordered by retrieval rank
    golden_spans: list[Span]
    scores: dict[str, float]


def _evaluate_query(
    db: Session,
    *,
    query: EvalQuery,
    kb_id: str,
    id_to_key: dict[str, str],
    golden_spans: list[Span],
    top_k: int,
) -> QueryEval:
    """Retrieve for one query (direct mode) and score it at every k."""
    response = RetrievalService.search(
        db,
        query=query.question,
        knowledge_base_id=kb_id,
        top_k=top_k,
        mode="direct",
    )

    retrieved_spans: list[Span] = []
    retrieved_doc_keys: list[str] = []
    for chunk in response.results:
        # Map the retrieved chunk's document UUID back to its corpus filename.
        # Unknown IDs (should not happen in a clean eval KB) map to a sentinel
        # that can never match a golden doc_key, so they score as misses.
        doc_key = id_to_key.get(chunk.citation.document_id, f"<unknown:{chunk.citation.document_id}>")
        retrieved_spans.append((doc_key, chunk.citation.start_offset, chunk.citation.end_offset))
        retrieved_doc_keys.append(doc_key)

    relevant = set(query.relevant_docs)
    scores: dict[str, float] = {}
    for k in K_VALUES:
        scores[f"answer_ctx_recall@{k}"] = answer_ctx_recall_at_k(retrieved_spans, golden_spans, k)
        scores[f"doc_recall@{k}"] = doc_recall_at_k(retrieved_doc_keys, relevant, k)
        scores[f"hit@{k}"] = hit_at_k(retrieved_spans, golden_spans, k)
    scores[f"mrr@{MRR_K}"] = mrr_at_k(retrieved_spans, golden_spans, MRR_K)

    return QueryEval(
        query=query,
        retrieved_spans=retrieved_spans,
        retrieved_doc_keys=retrieved_doc_keys,
        golden_spans=golden_spans,
        scores=scores,
    )


# ── Aggregation ───────────────────────────────────────────────────────────────

# Report order for the per-difficulty breakdown. Plain sorted() gives alphabetical
# (easy/hard/medium), which hides the "score decreases as difficulty rises" trend
# that is the whole point of the breakdown. Force easy → medium → hard.
_DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}

METRIC_KEYS = tuple(
    [f"answer_ctx_recall@{k}" for k in K_VALUES]
    + [f"doc_recall@{k}" for k in K_VALUES]
    + [f"hit@{k}" for k in K_VALUES]
    + [f"mrr@{MRR_K}"]
)


def _mean_scores(evals: list[QueryEval]) -> dict[str, float]:
    """Mean of every metric across a set of query evals (0.0 for empty set)."""
    if not evals:
        return {key: 0.0 for key in METRIC_KEYS}
    return {key: round(sum(e.scores[key] for e in evals) / len(evals), 4) for key in METRIC_KEYS}


def _aggregate(evals: list[QueryEval]) -> dict[str, Any]:
    """Overall mean + per-difficulty breakdown."""
    by_difficulty: dict[str, list[QueryEval]] = defaultdict(list)
    for e in evals:
        by_difficulty[e.query.difficulty].append(e)

    return {
        "aggregate": _mean_scores(evals),
        "by_difficulty": {
            difficulty: {"count": len(group), **_mean_scores(group)}
            for difficulty, group in sorted(by_difficulty.items(), key=lambda kv: _DIFFICULTY_ORDER.get(kv[0], 99))
        },
    }


# ── Output ────────────────────────────────────────────────────────────────────


def _build_report(evals: list[QueryEval], *, top_k: int, corpus_size: int) -> dict[str, Any]:
    agg = _aggregate(evals)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "top_k": top_k,
        "corpus_size": corpus_size,
        "query_count": len(evals),
        "aggregate": agg["aggregate"],
        "by_difficulty": agg["by_difficulty"],
        "per_query": [
            {
                "id": e.query.id,
                "difficulty": e.query.difficulty,
                "question": e.query.question,
                "retrieved": [{"doc_key": key, "start": start, "end": end} for key, start, end in e.retrieved_spans],
                "golden": [{"doc_key": key, "start": start, "end": end} for key, start, end in e.golden_spans],
                "scores": e.scores,
            }
            for e in evals
        ],
    }


def _write_report(report: dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _print_table(report: dict[str, Any]) -> None:
    col_w = 9
    header_cols = "".join(f"{f'@{k}':>{col_w}}" for k in K_VALUES)
    rule_w = 26 + col_w * len(K_VALUES)
    table_w = max(60, rule_w + 2)

    def _row(label: str, metric: str, stats: dict[str, float]) -> str:
        cells = "".join(f"{stats[f'{metric}@{k}']:>{col_w}.4f}" for k in K_VALUES)
        return f"  {label:<26}{cells}"

    def _block(stats: dict[str, float]) -> None:
        """Render the full metric grid for one score set (aggregate or per-difficulty)."""
        print(f"  {'metric':<26}{header_cols}")
        print("  " + "-" * rule_w)
        print(_row("Answer-Ctx Recall", "answer_ctx_recall", stats))
        print(_row("Doc Recall", "doc_recall", stats))
        print(_row("Hit", "hit", stats))
        print("  " + "-" * rule_w)
        print(f"  {'MRR@' + str(MRR_K):<26}{stats[f'mrr@{MRR_K}']:>{col_w}.4f}")

    print("\n" + "=" * table_w)
    print(f"  Retrieval Eval — direct mode  (top_k={report['top_k']})")
    print(f"  corpus={report['corpus_size']} docs   queries={report['query_count']}")
    print("=" * table_w)
    _block(report["aggregate"])
    print("=" * table_w)

    print("\n  by difficulty:")
    for difficulty, stats in report["by_difficulty"].items():
        print(f"\n  [{difficulty}]  n={stats['count']}")
        _block(stats)
    print("=" * table_w + "\n")


# ── Driver ────────────────────────────────────────────────────────────────────


def run(db: Session, *, top_k: int, reset: bool) -> dict[str, Any]:
    seed_result: SeedResult = seed(db, reset=reset)

    evals: list[QueryEval] = []
    for query in TEST_QUERIES:
        golden = seed_result.golden_spans.get(query.id, [])
        evals.append(
            _evaluate_query(
                db,
                query=query,
                kb_id=seed_result.kb_id,
                id_to_key=seed_result.id_to_key,
                golden_spans=golden,
                top_k=top_k,
            )
        )

    report = _build_report(evals, top_k=top_k, corpus_size=len(seed_result.doc_ids))
    out_path = _write_report(report)
    _print_table(report)
    print(f"  results written to {out_path}\n")
    logger.info("retrieval eval complete", queries=len(evals), out_path=str(out_path))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Level 1 retrieval eval (direct mode).")
    parser.add_argument("--top-k", type=int, default=10, help="retrieval depth (default 10; @5/@10 sliced from it)")
    parser.add_argument("--reset", action="store_true", help="rebuild the eval corpus before running")
    args = parser.parse_args()

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        run(db, top_k=args.top_k, reset=args.reset)
    finally:
        db.close()


if __name__ == "__main__":
    main()
