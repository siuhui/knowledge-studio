# TF-IDF Weighting

TF-IDF, which expands to term frequency times inverse document frequency, is a numerical statistic that reflects how important a word is to a document within a collection. It predates BM25 and the entire probabilistic retrieval tradition, tracing back to work by Karen Spärck Jones in 1972 on the specificity of terms. For decades it served as the default weighting scheme for the vector-space model of information retrieval, and it remains a workhorse in text mining, document classification, and keyword extraction well beyond search.

## The Two Factors

The name says everything: the weight of a term is the product of two independent quantities. The first, term frequency, measures how often a word occurs inside a single document. The second, inverse document frequency, measures how rare that word is across the entire corpus. Multiplying them yields a weight that is high when a term appears frequently in one document but seldom elsewhere, which is exactly the profile of a word that characterizes that document.

```
tfidf(t, d, D) = tf(t, d) * idf(t, D)
```

A word such as "network" might appear often in one technical article, giving it a high term frequency there, yet if it also appears in nearly every other article the inverse document frequency pulls its weight back down. Conversely a word appearing in only a handful of documents earns a large inverse document frequency and therefore stands out as a discriminative signal whenever it occurs.

## Computing Term Frequency

There are several conventions for the term frequency component. The raw count is the simplest, but it lets long documents dominate, so most implementations apply a sublinear transform. A very common choice is logarithmic scaling:

```
tf(t, d) = 1 + log(count(t, d))    if count(t, d) > 0, else 0
```

This dampening ensures that a word occurring twenty times is not treated as twenty times more important than a word occurring once. Other variants include boolean frequency, which records only presence or absence, and augmented frequency, which divides by the maximum raw count in the document to normalize for length. The key idea across all of them is that additional occurrences of a term yield diminishing returns, a theme TF-IDF shares in spirit with the saturation found in later models.

## Inverse Document Frequency

The inverse document frequency factor is where the scheme earns its power to separate signal from noise. It is defined as the logarithm of the ratio between the total number of documents and the number of documents containing the term:

```
idf(t, D) = log( N / df(t) )
```

Here `N` is the size of the collection and `df(t)`, the document frequency, counts how many documents contain the term at least once. Because the ratio is inside a logarithm, the weight grows slowly: a term ten times rarer does not become ten times more important, only additively so. A term that occurs in every single document has a document frequency equal to `N`, giving `log(1) = 0`, so it contributes nothing at all — which is exactly how stop words like "and" or "the" are neutralized without an explicit stop list. To avoid division by zero for unseen terms and to keep weights strictly positive, practitioners often add smoothing, writing the denominator as `1 + df(t)` and sometimes adding one to the numerator as well.

## The Vector-Space Model

TF-IDF is most often paired with the vector-space model, in which every document and every query is represented as a vector over the vocabulary. Each dimension corresponds to a term, and its value is the TF-IDF weight of that term in the document. Retrieval then reduces to a geometry problem: rank documents by how close their vectors lie to the query vector. The standard closeness measure is the cosine similarity, which computes the cosine of the angle between two vectors and thereby ignores their magnitudes.

```python
import numpy as np

def cosine_similarity(query_vec, doc_vec):
    dot = np.dot(query_vec, doc_vec)
    norm = np.linalg.norm(query_vec) * np.linalg.norm(doc_vec)
    return dot / norm if norm else 0.0
```

Because cosine similarity divides out the vector lengths, a short query and a long document can still match strongly if they point in the same direction in term space. This normalization is one reason the vector-space model tolerates documents of very different sizes reasonably well, though it lacks the principled length correction that BM25 later introduced.

## Strengths, Limits, and Modern Role

The great virtue of TF-IDF is simplicity. It requires no training data, it is trivial to compute over an inverted index, and its scores are interpretable term by term. In scikit-learn the `TfidfVectorizer` turns a corpus into a sparse matrix in a single call, which is why the technique is ubiquitous in classical machine-learning pipelines for tasks like spam filtering and topic clustering.

Its limitations are equally well understood. TF-IDF treats every term as an isolated symbol, so it has no notion that "car" and "automobile" mean the same thing; it cannot capture synonymy or word order, and it fails on paraphrases where no surface words overlap. These gaps are precisely what dense embedding models were built to close. Even so, TF-IDF and its probabilistic descendant BM25 remain the interpretable, zero-training foundation on top of which many hybrid retrieval systems still layer their neural components, and understanding it is essential to understanding everything that came after.
