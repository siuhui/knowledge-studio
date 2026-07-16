"""Retrieval-eval test set — 30 queries over the 7-cluster corpus.

Each :class:`EvalQuery` pins the answer to one or more ``answer_anchors``:
verbatim, discriminative phrases that actually answer the question.  At seed
time ``validate_anchors()`` resolves every anchor to a golden ``(doc_key,
start, end)`` span via ``full_text.find()`` and asserts it is globally unique
(appears in exactly one document, exactly once).  That gate is why anchors are
written as long, specific phrases rather than bare keywords.

Difficulty (aligned with the cluster structure, see retrieval-eval-plan §四):
    easy   — cross-cluster keyword hit; exercises the FTS path.
    medium — in-cluster semantic paraphrase; must beat near-neighbour
             distractors, exercises the vector path + fusion.
    hard   — answer spans two documents, or is phrased indirectly enough that
             lexical overlap alone will not surface it.

This module is import-safe with no DB (only a frozen dataclass + a list), so
pytest can collect it and ``test_metrics.py`` alongside it in CI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalQuery:
    """One eval question and its ground-truth annotation.

    ``relevant_docs`` is the document-level truth (corpus filenames) used by the
    inflated Doc Recall metric.  ``answer_anchors`` is the passage-level truth
    used by the honest Answer-Context Recall metric — each anchor is a verbatim
    substring of exactly one corpus document.
    """

    id: str
    question: str
    relevant_docs: tuple[str, ...]
    answer_anchors: tuple[str, ...]
    difficulty: str  # "easy" | "medium" | "hard"


TEST_QUERIES: list[EvalQuery] = [
    # ── Cluster 1: vector search (01-04) ─────────────────────────────────────
    EvalQuery(
        id="vec-1",
        question="How do you tune the recall of an IVFFlat index in pgvector at query time?",
        relevant_docs=("01_pgvector.md",),
        answer_anchors=("the `ivfflat.probes` setting, which decides how many of the nearest lists to scan",),
        difficulty="easy",
    ),
    EvalQuery(
        id="vec-2",
        question="Why does FAISS leave serving, sharding, and durability up to the application that uses it?",
        relevant_docs=("02_faiss.md",),
        answer_anchors=("it links into your own process, holds its indexes in memory, and exposes function calls",),
        difficulty="medium",
    ),
    EvalQuery(
        id="vec-3",
        question="What lets Milvus scale its query capacity separately from where the vectors are stored?",
        relevant_docs=("03_milvus.md",),
        answer_anchors=("Milvus adopts a distributed architecture that separates storage and compute",),
        difficulty="medium",
    ),
    EvalQuery(
        id="vec-4",
        question="In the HNSW graph, how are the top layers structured compared with the bottom layer?",
        relevant_docs=("04_hnsw.md",),
        answer_anchors=("the top HNSW layer contains only a sparse subset of all points",),
        difficulty="medium",
    ),
    EvalQuery(
        id="vec-5",
        question=(
            "Which nearest-neighbour index can be built on an empty table and grown incrementally, "
            "and which one must wait until the table already holds representative data?"
        ),
        relevant_docs=("01_pgvector.md", "04_hnsw.md"),
        answer_anchors=(
            "HNSW supports online insertion",
            "build an IVFFlat index only after the table already holds a representative sample",
        ),
        difficulty="hard",
    ),
    # ── Cluster 2: attention (05-08) — verified by corpus subagent ───────────
    EvalQuery(
        id="attn-1",
        question="How does FlashAttention cut down GPU memory traffic when computing attention?",
        relevant_docs=("06_flash_attention.md",),
        answer_anchors=("FlashAttention reduces the reads and writes between high-bandwidth memory and SRAM",),
        difficulty="easy",
    ),
    EvalQuery(
        id="attn-2",
        question=(
            "Why is it beneficial to run several parallel attention computations over separate slices "
            "of the embedding instead of one attention function over the whole vector?"
        ),
        relevant_docs=("08_multi_head.md",),
        answer_anchors=("attend to information from different representation subspaces at different positions",),
        difficulty="medium",
    ),
    EvalQuery(
        id="attn-3",
        question=(
            "In an encoder-decoder translation model, when the decoder attends over the source sentence, "
            "where do the vectors it matches against and reads content from originate?"
        ),
        relevant_docs=("07_cross_attention.md",),
        answer_anchors=("the keys and values come from the encoder outputs",),
        difficulty="medium",
    ),
    EvalQuery(
        id="attn-4",
        question="How does multi-head attention differ from one attention function over the full model dimension?",
        relevant_docs=("05_self_attention.md", "08_multi_head.md"),
        answer_anchors=(
            "a single scaled dot-product attention over the full model dimension",
            "splits the model dimension into several lower-dimensional attention heads",
        ),
        difficulty="hard",
    ),
    # ── Cluster 3: ranking & fusion (09-12) ──────────────────────────────────
    EvalQuery(
        id="rank-1",
        question="What controls term frequency saturation in BM25?",
        relevant_docs=("09_bm25.md",),
        answer_anchors=("term frequency saturation, and it is controlled by the parameter k1",),
        difficulty="easy",
    ),
    EvalQuery(
        id="rank-2",
        question="In TF-IDF, why does a word that appears in every document end up contributing nothing to the score?",
        relevant_docs=("10_tfidf.md",),
        answer_anchors=("A term that occurs in every single document has a document frequency equal to `N`",),
        difficulty="medium",
    ),
    EvalQuery(
        id="rank-3",
        question="How does Reciprocal Rank Fusion combine retrievers whose score ranges are not comparable?",
        relevant_docs=("11_rrf.md",),
        answer_anchors=("throwing the scores away and keeping only the rank positions",),
        difficulty="medium",
    ),
    EvalQuery(
        id="rank-4",
        question="Why can't a cross-encoder's document vectors be precomputed and cached like a bi-encoder's?",
        relevant_docs=("12_cross_encoder_rerank.md",),
        answer_anchors=("every query-document pair must pass through the full network at search time",),
        difficulty="medium",
    ),
    EvalQuery(
        id="rank-5",
        question=(
            "In a hybrid pipeline, which component merges the lexical and semantic lists using only rank position, "
            "and which component then re-scores the fused shortlist with a heavier model?"
        ),
        relevant_docs=("11_rrf.md", "12_cross_encoder_rerank.md"),
        answer_anchors=(
            "a precision-oriented reranking stage that re-scores the fused top candidates",
            "The cross-encoder then re-scores only that shortlist",
        ),
        difficulty="hard",
    ),
    # ── Cluster 4: container orchestration (13-16) ───────────────────────────
    EvalQuery(
        id="cont-1",
        question="In Docker, what does each instruction in a Dockerfile produce?",
        relevant_docs=("13_docker.md",),
        answer_anchors=("each instruction in a Dockerfile creates a new image",),
        difficulty="easy",
    ),
    EvalQuery(
        id="cont-2",
        question="How does a Kubernetes Service give clients a stable address in front of a changing set of pods?",
        relevant_docs=("14_kubernetes.md",),
        answer_anchors=("a stable virtual IP, called the ClusterIP, that stays constant",),
        difficulty="medium",
    ),
    EvalQuery(
        id="cont-3",
        question="What is the limitation of Docker Compose's depends_on when ordering service startup?",
        relevant_docs=("15_docker_compose.md",),
        answer_anchors=("waits only until the dependency's container has been started",),
        difficulty="medium",
    ),
    EvalQuery(
        id="cont-4",
        question=(
            "How do containers resolve each other by name — both across a Docker Compose application "
            "and on a user-defined Docker bridge network?"
        ),
        relevant_docs=("15_docker_compose.md", "16_container_networking.md"),
        answer_anchors=(
            "which Compose registers in an embedded DNS resolver",
            "automatic DNS resolution by container name",
        ),
        difficulty="hard",
    ),
    # ── Cluster 5: Python concurrency (17-20) ────────────────────────────────
    EvalQuery(
        id="conc-1",
        question="What role does the asyncio event loop play?",
        relevant_docs=("17_asyncio.md",),
        answer_anchors=("the scheduler that runs coroutines, dispatches callbacks, and watches",),
        difficulty="easy",
    ),
    EvalQuery(
        id="conc-2",
        question="Why is incrementing a shared counter across threads unsafe without a lock?",
        relevant_docs=("18_threading.md",),
        answer_anchors=("read, an add, and a write",),
        difficulty="medium",
    ),
    EvalQuery(
        id="conc-3",
        question="Why must every argument passed to a multiprocessing worker be picklable?",
        relevant_docs=("19_multiprocessing.md",),
        answer_anchors=("multiprocessing uses pickle to serialize objects before sending them",),
        difficulty="medium",
    ),
    EvalQuery(
        id="conc-4",
        question=(
            "Why does adding threads fail to speed up CPU-bound Python work while separate processes "
            "achieve real parallelism across cores?"
        ),
        relevant_docs=("19_multiprocessing.md", "20_gil.md"),
        answer_anchors=(
            "CPU-bound Python code cannot be sped up by adding threads",
            "private Python interpreter and a private memory space",
        ),
        difficulty="hard",
    ),
    # ── Cluster 6: authentication (21-24) ────────────────────────────────────
    EvalQuery(
        id="auth-1",
        question="What are the three parts of a JWT?",
        relevant_docs=("21_jwt.md",),
        answer_anchors=("three parts separated by dots: a header, a payload, and a signature",),
        difficulty="easy",
    ),
    EvalQuery(
        id="auth-2",
        question="Does OAuth2 establish who a user is, or does it do something else?",
        relevant_docs=("22_oauth2.md",),
        answer_anchors=("OAuth2 is about delegated authorization, not authentication",),
        difficulty="medium",
    ),
    EvalQuery(
        id="auth-3",
        question="How should a service store API keys on the server side?",
        relevant_docs=("24_api_keys.md",),
        answer_anchors=("store only a salted hash of the key",),
        difficulty="medium",
    ),
    EvalQuery(
        id="auth-4",
        question=(
            "Which authentication scheme can be revoked instantly on logout, and which one stays valid "
            "until it expires unless a server-side denylist is added?"
        ),
        relevant_docs=("21_jwt.md", "23_session_cookie.md"),
        answer_anchors=(
            "a stateless token remains valid until its exp claim passes",
            "destroy a session instantly on the server is the defining advantage",
        ),
        difficulty="hard",
    ),
    # ── Cluster 7: PostgreSQL (25-28) ────────────────────────────────────────
    EvalQuery(
        id="pg-1",
        question="Which index type does PostgreSQL create by default?",
        relevant_docs=("25_btree_index.md",),
        answer_anchors=("the default and most widely used index type in PostgreSQL",),
        difficulty="easy",
    ),
    EvalQuery(
        id="pg-2",
        question="How does a GIN index map an indexed element back to the rows that contain it?",
        relevant_docs=("26_gin_index.md",),
        answer_anchors=("a posting list or posting tree enumerating the row identifiers that contain that item",),
        difficulty="medium",
    ),
    EvalQuery(
        id="pg-3",
        question="How does the PostgreSQL planner decide between a sequential scan and an index scan?",
        relevant_docs=("27_query_planner.md",),
        answer_anchors=("PostgreSQL uses a cost-based optimizer. For each candidate plan it computes an abstract",),
        difficulty="medium",
    ),
    EvalQuery(
        id="pg-4",
        question="What does vacuuming keep current so that index-only scans can skip reading the table heap?",
        relevant_docs=("25_btree_index.md", "28_vacuum.md"),
        answer_anchors=(
            "When every column a query needs is present in the index, PostgreSQL can perform an index-only scan",
            "VACUUM also performs two other essential jobs. It updates the visibility map, a compact per-page bitmap",
        ),
        difficulty="hard",
    ),
]
