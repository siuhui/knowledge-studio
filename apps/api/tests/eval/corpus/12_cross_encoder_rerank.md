# Cross-Encoder Reranking

A cross-encoder reranker is a neural model that takes a query and a candidate document together as a single input and outputs a scalar relevance score. It sits at the precision end of a retrieval pipeline, reordering a small set of candidates that a cheaper first-stage retriever has already selected. Because it reads the query and the document jointly, a cross-encoder can model fine-grained interactions between their words that no independent embedding can capture, which is why it consistently tops leaderboards for reranking quality.

## Bi-Encoders Versus Cross-Encoders

To understand why cross-encoders are accurate, it helps to contrast them with bi-encoders, the architecture behind dense vector search. A bi-encoder pushes the query and the document through the network separately, producing one fixed vector for each, and then measures their similarity with a dot product or cosine. Because the document vectors do not depend on the query, they can be computed once and stored in an index, which makes bi-encoder retrieval fast enough to scan millions of documents.

A cross-encoder makes the opposite trade. It concatenates the query and the document into a single sequence, typically separated by a special token, and feeds the pair through a transformer so that every query token can attend to every document token. The output is a single relevance score for that specific pairing. This joint encoding is what gives the model its accuracy, but it also means nothing can be precomputed: every query-document pair must pass through the full network at search time. Scoring one query against a thousand documents therefore requires a thousand separate forward passes.

## How Scoring Works

Concretely, the model receives an input of the form `[CLS] query [SEP] document [SEP]` and produces a representation of the whole sequence. A small classification head, usually a single linear layer over the pooled `[CLS]` representation, projects that into one number interpreted as the relevance score. The candidates are then sorted by this score in descending order to produce the reranked list.

```python
from sentence_transformers import CrossEncoder

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
pairs = [(query, doc) for doc in candidate_documents]
scores = model.predict(pairs)
reranked = [doc for _, doc in sorted(zip(scores, candidate_documents), reverse=True)]
```

Models trained for this task are commonly fine-tuned on the MS MARCO passage ranking dataset, where each training example is a query paired with a relevant passage and several non-relevant ones. The network learns to assign higher scores to the relevant pairing, often optimized with a cross-entropy loss over the candidates or a pairwise ranking objective. The resulting scores are not calibrated probabilities and are only meaningful relative to one another within the same query.

## The Retrieve-Then-Rerank Pattern

Cross-encoders are almost never used to search a corpus directly, because scoring every document against the query would be hopelessly slow. Instead they operate in a two-stage cascade. A fast first-stage retriever, such as BM25 or a bi-encoder vector search, produces a candidate pool of perhaps the top fifty to two hundred documents. The cross-encoder then re-scores only that shortlist, and its ordering replaces the first-stage order for the final result.

This division of labour lets the pipeline enjoy the recall of a cheap retriever and the precision of an expensive model without paying the expensive cost over the whole collection. The depth of the candidate pool becomes the crucial tuning knob: a deeper pool gives the reranker more chances to surface a document the first stage ranked low, but it also increases latency linearly, since each additional candidate is one more forward pass. In practice teams choose the pool size by measuring where reranking quality stops improving on a validation set.

## Latency and Deployment

The accuracy of a cross-encoder comes at a real computational price, and managing that price dominates deployment decisions. Reranking a shortlist of one hundred passages can add tens to hundreds of milliseconds depending on the model size and hardware, and unlike the first stage it typically wants a GPU to stay within a reasonable latency budget. Practitioners reduce the burden by choosing distilled models such as the MiniLM family, by batching all candidate pairs into a single inference call, and by trimming very long documents so the sequence length stays manageable.

Even with these optimizations the reranker remains the heaviest component per candidate, which is precisely why it is confined to a shortlist rather than the full index. The economics only work because the first stage has already discarded the vast majority of documents.

## Where It Fits in RAG

In a retrieval-augmented generation system the cross-encoder earns its keep by improving the precision of the context handed to the language model. After a hybrid retriever fuses lexical and semantic candidates, the reranker reorders them so that the most relevant passages occupy the top few slots, and only those top passages are placed into the prompt. Because a language model's answer quality degrades when irrelevant passages crowd the context window, tightening the top of the ranking has an outsized effect on the final answer even though it never changes which documents were retrievable in the first place. A cross-encoder cannot recover a passage that the first stage failed to retrieve, so it complements rather than replaces the recall-oriented retrieval that precedes it.
