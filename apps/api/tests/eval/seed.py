"""Idempotent eval-corpus seeding + anchor-validation gate.

Seeds the eval corpus into a **persistent** DB (the dev DB by default — *not* a
rollback test fixture).  Embedding has real API cost, so the corpus is created
once and reused across runs: every stage is idempotent.

Layout created (all fixed-name, so re-runs reuse them):
    User  ``eval-retrieval``
      └─ KnowledgeBase ``【EVAL】retrieval-baseline``
           └─ Document × N  (one per corpus/*.md, ``source_id=None``)

The eval corpus does not go through the real upload / URL ingestion path, so
documents are created with ``source_id=None`` — ``Document.source_id`` is
nullable and retrieval scopes purely by ``knowledge_base_id``, so no
placeholder Source is needed.

Per corpus file the pipeline is: ``DocumentService.create`` (text_hash dedup)
→ ``chunk_document`` (skips if chunks exist) → ``embed_document`` (skips if
already embedded).  All three are idempotent, so re-seeding is nearly free.

``validate_anchors()`` is the annotation gate.  Every ``answer_anchor`` must
appear **exactly once** in its target document's ``full_text`` and in **no
other** document.  A collision means the anchor is ambiguous — the gate raises
so a human fixes the annotation instead of silently scoring against a bad span.

Run directly:
    python -m tests.eval.seed            # seed / top up
    python -m tests.eval.seed --reset    # drop the eval KB and rebuild
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.document import DocumentService
from app.services.indexing.pipeline import chunk_document, embed_document
from tests.eval.metrics import Span
from tests.eval.test_set import TEST_QUERIES, EvalQuery

logger = structlog.get_logger(__name__)

# ── Fixed identifiers (stable across runs so seeding is idempotent) ──────────

EVAL_USERNAME = "eval-retrieval"
EVAL_PASSWORD = "eval-retrieval-local-only"  # noqa: S105 — fixed local eval user, never a real account
EVAL_KB_NAME = "【EVAL】retrieval-baseline"

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"


# ── Result bundle handed to the eval driver ──────────────────────────────────


@dataclass
class SeedResult:
    """Everything the eval driver needs after seeding.

    ``id_to_key`` reverses ``doc_ids`` so the driver can map a retrieved
    ``citation.document_id`` (a UUID) back to a corpus filename (``doc_key``)
    — the coordinate the golden spans are expressed in.
    """

    kb_id: str
    doc_ids: dict[str, str] = field(default_factory=dict)  # doc_key -> document_id
    id_to_key: dict[str, str] = field(default_factory=dict)  # document_id -> doc_key
    golden_spans: dict[str, list[Span]] = field(default_factory=dict)  # query_id -> golden spans


# ── Corpus loading ────────────────────────────────────────────────────────────


def read_corpus() -> dict[str, str]:
    """Read every ``corpus/*.md`` into ``{doc_key: raw_text}``.

    ``doc_key`` is the bare filename (e.g. ``01_pgvector.md``).  The raw file
    text is used verbatim as ``Document.full_text`` — no markdown parsing — so
    chunk offsets and golden-anchor offsets share one coordinate system.
    """
    if not CORPUS_DIR.is_dir():
        raise FileNotFoundError(f"corpus directory not found: {CORPUS_DIR}")

    corpus: dict[str, str] = {}
    for path in sorted(CORPUS_DIR.glob("*.md")):
        corpus[path.name] = path.read_text(encoding="utf-8")

    if not corpus:
        raise FileNotFoundError(f"no corpus files found in {CORPUS_DIR}")

    return corpus


# ── Annotation gate ───────────────────────────────────────────────────────────


def validate_anchors(corpus: dict[str, str], queries: list[EvalQuery]) -> dict[str, list[Span]]:
    """Resolve every anchor phrase to a golden ``(doc_key, start, end)`` span.

    Enforces the annotation contract and raises ``ValueError`` (listing *all*
    problems at once) if any anchor is:

    - **missing**  — not found verbatim in any corpus document;
    - **ambiguous** — found in more than one document (globally not unique);
    - **repeated** — found more than once inside its own document;
    - **mislabeled** — resolves to a document not in the query's ``relevant_docs``.

    Returns ``{query_id: [spans]}`` for the driver on success.
    """
    golden: dict[str, list[Span]] = {}
    errors: list[str] = []

    for query in queries:
        spans: list[Span] = []
        for anchor in query.answer_anchors:
            containing = [key for key, txt in corpus.items() if anchor in txt]

            if not containing:
                errors.append(f"[{query.id}] anchor not found in any document: {anchor!r}")
                continue
            if len(containing) > 1:
                errors.append(f"[{query.id}] anchor is ambiguous, appears in {containing}: {anchor!r}")
                continue

            doc_key = containing[0]
            occurrences = corpus[doc_key].count(anchor)
            if occurrences > 1:
                errors.append(f"[{query.id}] anchor appears {occurrences}× in {doc_key}: {anchor!r}")
                continue
            if doc_key not in query.relevant_docs:
                errors.append(
                    f"[{query.id}] anchor resolves to {doc_key}, not in relevant_docs "
                    f"{list(query.relevant_docs)}: {anchor!r}"
                )
                continue

            pos = corpus[doc_key].find(anchor)
            start, end = pos, pos + len(anchor)
            # Offset-legality round-trip: the resolved span must slice back to
            # the exact anchor.  Guaranteed by find()'s contract today, but
            # asserted so any future change to text handling (strip, normalize)
            # that would desync golden offsets from Document.full_text fails
            # loudly here instead of silently mis-scoring retrieval.
            if corpus[doc_key][start:end] != anchor:
                errors.append(f"[{query.id}] resolved span does not round-trip in {doc_key}: {anchor!r}")
                continue
            spans.append((doc_key, start, end))

        if not spans:
            errors.append(f"[{query.id}] no valid anchors resolved")
        golden[query.id] = spans

    if errors:
        raise ValueError("anchor validation failed:\n  " + "\n  ".join(errors))

    return golden


# ── DB setup helpers ──────────────────────────────────────────────────────────


def _get_or_create_user(db: Session) -> User:
    user = db.query(User).filter(User.username == EVAL_USERNAME).first()
    if user is None:
        user = User(username=EVAL_USERNAME, password_hash=hash_password(EVAL_PASSWORD))
        db.add(user)
        db.flush()
        logger.info("eval user created", user_id=user.id)
    return user


def _get_or_create_kb(db: Session, *, user_id: str) -> KnowledgeBase:
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id, KnowledgeBase.name == EVAL_KB_NAME).first()
    if kb is None:
        kb = KnowledgeBase(user_id=user_id, name=EVAL_KB_NAME, description="Retrieval eval baseline corpus")
        db.add(kb)
        db.flush()
        logger.info("eval knowledge_base created", knowledge_base_id=kb.id)
    return kb


def _reset_eval_kb(db: Session, *, user_id: str) -> None:
    """Drop the eval KB and everything under it (documents → chunks + index_status)."""
    kbs = db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id, KnowledgeBase.name == EVAL_KB_NAME).all()
    for kb in kbs:
        # Documents cascade to chunks + index_status via ORM ("all, delete-orphan").
        docs = db.query(Document).filter(Document.knowledge_base_id == kb.id).all()
        for doc in docs:
            db.delete(doc)
        db.flush()

        db.delete(kb)
        logger.info("eval knowledge_base reset", knowledge_base_id=kb.id)
    db.commit()


# ── Public entry point ──────────────────────────────────────────────────────


def seed(db: Session, *, reset: bool = False) -> SeedResult:
    """Idempotently seed the eval corpus and return a :class:`SeedResult`.

    Validates anchors *before* touching the DB — a bad annotation aborts the
    run before any embedding cost is incurred.
    """
    corpus = read_corpus()
    golden_spans = validate_anchors(corpus, TEST_QUERIES)  # gate — raises on bad annotation
    logger.info("anchors validated", query_count=len(TEST_QUERIES), corpus_size=len(corpus))

    user = _get_or_create_user(db)
    if reset:
        _reset_eval_kb(db, user_id=user.id)

    kb = _get_or_create_kb(db, user_id=user.id)
    db.commit()

    doc_ids: dict[str, str] = {}
    for doc_key, full_text in corpus.items():
        document_id = DocumentService.create(
            db,
            full_text=full_text,
            title=doc_key,
            source_format="markdown",
            source_id=None,
            kb_id=kb.id,
            path=f"corpus/{doc_key}",
        )
        chunk_count = chunk_document(db, document_id=document_id)
        embed_count = embed_document(db, document_id=document_id)
        db.commit()

        doc_ids[doc_key] = document_id
        logger.info("corpus document ready", doc_key=doc_key, chunks=chunk_count, newly_embedded=embed_count)

    result = SeedResult(
        kb_id=kb.id,
        doc_ids=doc_ids,
        id_to_key={v: k for k, v in doc_ids.items()},
        golden_spans=golden_spans,
    )
    logger.info("eval corpus seeded", kb_id=kb.id, documents=len(doc_ids))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the retrieval-eval corpus into the dev DB.")
    parser.add_argument("--reset", action="store_true", help="drop the eval KB and rebuild from scratch")
    args = parser.parse_args()

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        result = seed(db, reset=args.reset)
        print(f"seeded {len(result.doc_ids)} documents into KB {result.kb_id}")
        print(f"validated {len(result.golden_spans)} queries")
    finally:
        db.close()


if __name__ == "__main__":
    main()
