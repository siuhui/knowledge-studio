# Reciprocal Rank Fusion

Reciprocal Rank Fusion, usually abbreviated RRF, is a simple and remarkably effective method for combining several ranked lists of documents into a single consolidated ranking. It was introduced by Cormack, Clarke, and Buettcher in a 2009 SIGIR paper, and it has since become the default fusion strategy in hybrid search systems that need to merge results from a keyword retriever and a dense vector retriever. Its enduring popularity comes from a rare combination of properties: it needs no training, no tuning of per-system weights, and no calibration of the underlying scores.

## The Score Calibration Problem

The central difficulty in blending retrievers is that their scores are not comparable. A BM25 engine might return scores in the range of 5 to 40, while a cosine-similarity vector search returns values between 0 and 1, and a neural reranker might emit unbounded logits. Naively adding these numbers lets whichever system has the larger numerical range dominate the outcome, which has nothing to do with which system is actually more accurate. Normalizing scores by min-max scaling or z-scores helps a little, but it is fragile because the distributions shift from query to query.

Reciprocal Rank Fusion sidesteps the whole problem by throwing the scores away and keeping only the rank positions. Rank is a universal currency: being first in a list means the same thing whether that list came from BM25, a vector index, or a learned model. By operating purely on ordinal position, RRF becomes agnostic to the scale and shape of any individual scoring function.

## The Fusion Formula

For each document, RRF sums a contribution from every ranked list in which the document appears. The contribution from a given list is the reciprocal of a constant plus the document's rank in that list:

```
RRF_score(d) = sum over lists L of  1 / (k + rank_L(d))
```

Here `rank_L(d)` is the one-based position of document `d` in list `L`, and `k` is a smoothing constant. Documents that appear near the top of several lists accumulate the largest totals and rise to the top of the fused ranking. A document that is absent from a particular list simply contributes nothing from that list rather than incurring a penalty.

The constant `k` was set to 60 in the original paper, and 60 has become the near-universal default. Its role is to reduce the influence of very high rankings and prevent any single first-place finish from overwhelming the combination. With a large `k`, the difference between rank 1 and rank 2 shrinks, so the method leans on agreement across many lists rather than trusting one list's top result outright. A small `k` does the opposite, sharpening the reward for being ranked first.

## A Worked Implementation

The algorithm is short enough to write in a dozen lines, which is part of its charm. The following function accepts several ranked lists of document identifiers and returns them fused:

```python
def reciprocal_rank_fusion(ranked_lists, k=60):
    scores = {}
    for ranking in ranked_lists:
        for position, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + position)
    return sorted(scores, key=scores.get, reverse=True)
```

Each list is traversed once, each document's reciprocal contribution is added into a running total, and the accumulated totals are sorted in descending order. The cost is linear in the total number of retrieved items, so fusion adds negligible latency on top of the retrieval steps it combines. Because the output is deterministic and depends only on rank positions, the same inputs always produce the same fused order.

## Why It Works So Well

The reason reciprocal weighting outperforms simple averaging of ranks is that the reciprocal curve is steep near the top and flat toward the bottom. The jump in weight from rank 1 to rank 2 is far larger than the jump from rank 50 to rank 51, so the fusion concentrates its trust where each retriever is most confident. At the same time, summing across lists rewards consensus: a document that several independent systems all place reasonably high will beat a document that one system loves and the others ignore. This consensus effect makes RRF robust to a single retriever producing a spurious top hit.

Empirically, Reciprocal Rank Fusion frequently matches or exceeds far more complex learned fusion models, and it does so without any labelled data. That combination of simplicity and strength is why it appears in Elasticsearch, OpenSearch, and most retrieval-augmented generation stacks as the built-in way to merge lexical and semantic results.

## Practical Considerations

A few subtleties matter in production. First, the lists being fused should be truncated to a comparable depth; feeding one retriever's top 1000 and another's top 10 biases the fusion toward the deeper list, since more of its documents get a chance to contribute. Second, RRF is order-preserving within a single list but says nothing about how many candidates to retrieve before fusing, so the retrieval depth becomes an implicit hyperparameter alongside `k`.

It is also worth remembering what RRF cannot do. Because it discards scores, it cannot express that one retriever is far more reliable than another unless you weight the lists explicitly, which requires extending the formula with a per-list multiplier. And because it only considers rank, it cannot rescue a relevant document that every retriever ranked poorly. RRF is a fusion layer, not a retrieval improvement; it makes good component rankings better together but cannot manufacture relevance that none of the inputs found. For that reason it is often followed by a precision-oriented reranking stage that re-scores the fused top candidates with a heavier model.
