# Scaled Dot-Product Self-Attention

Self-attention is the core computation inside a Transformer encoder or decoder layer. It lets every position in a sequence gather information from every other position in the same sequence, producing a new representation for each token that is a weighted blend of the whole input. The defining property of self-attention, as opposed to other attention variants, is that the queries, keys, and values are all derived from the same sequence. There is no separate source or target stream; a single set of token representations plays all three roles at once.

## Queries, Keys, and Values

Given an input matrix of token embeddings, self-attention first produces three projected representations. Each input row is multiplied by three learned weight matrices to produce a query vector, a key vector, and a value vector for that position. Because the three projections are computed from the same input tensor, the operation is self-referential: the sequence attends to itself.

Conceptually, the query represents "what this position is looking for," the key represents "what this position offers," and the value carries the actual content that will be passed forward once a match is found. The compatibility between a query and a key is measured by their dot product. A large dot product means the two positions are highly relevant to each other and the corresponding value should contribute strongly to the output.

```python
import numpy as np

def self_attention(X, W_q, W_k, W_v):
    Q = X @ W_q          # (n, d_k)  queries
    K = X @ W_k          # (n, d_k)  keys
    V = X @ W_v          # (n, d_v)  values
    d_k = Q.shape[-1]
    scores = Q @ K.T / np.sqrt(d_k)      # (n, n) scaled scores
    weights = softmax(scores, axis=-1)   # rows sum to 1
    return weights @ V                   # (n, d_v) output
```

## The Scaling Factor

The raw dot products between queries and keys are divided by the square root of the key dimension before the softmax is applied. This scaling matters because as the key dimension grows, the variance of the dot products grows with it, and large-magnitude scores push the softmax into regions where its gradient is vanishingly small. Dividing by the square root of the key dimension keeps the logits in a numerically stable range and preserves useful gradients during backpropagation. Without this term, deep models with wide attention layers would train poorly or not at all.

## Softmax and the Attention Weights

After scaling, a softmax is applied across each row of the score matrix. This converts the raw compatibility scores into a probability distribution: for a given query position, the attention weights over all key positions are non-negative and sum to one. Each output vector is then the weighted sum of value vectors, using these weights. In effect, every token produces a fresh representation that is a soft, content-based lookup over the entire sequence, rather than a fixed function of its neighbors.

## Masking

Two kinds of masking are common. A causal mask sets the scores for future positions to negative infinity before the softmax so that a position can only attend to itself and earlier positions; this is essential in an autoregressive decoder that must not look ahead. A padding mask suppresses attention to padded tokens in a batched sequence. Both masks operate on the score matrix, leaving the projection and scaling untouched.

## Complexity and Permutation Behavior

The central cost of self-attention is that it is quadratic in the sequence length. With n tokens, both the score matrix and the weight matrix hold n-by-n entries, so memory and compute scale with the square of the sequence length. This quadratic term is the bottleneck that motivates a large body of research into more efficient attention.

Self-attention is also permutation-equivariant: it treats its input as an unordered set, so if you permute the input tokens the output is permuted in exactly the same way. On its own, the mechanism has no notion of word order. To restore order information, positional encodings, either fixed sinusoidal patterns or learned embeddings, are added to the token embeddings before the query, key, and value projections are computed. Without them the model could not distinguish "the cat chased the dog" from "the dog chased the cat."

## Dot-Product vs Additive Attention

Earlier attention formulations used an additive scoring function, computing compatibility with a small feed-forward network. Dot-product attention became the standard because it maps cleanly onto GPU hardware and can be expressed as dense matrix multiplication, making it substantially faster and more memory-efficient at large dimensions once the scaling factor is applied. The two forms have similar representational capacity, but the dot-product variant is the practical choice for modern accelerators.

## Single-Space vs Split Representations

A basic implementation applies a single scaled dot-product attention over the full model dimension, treating the entire embedding as one undivided space. This is the simplest possible design and is perfectly functional, but it forces one attention distribution to capture every kind of relationship at once. In practice, Transformer layers instead partition the representation so that several attention computations run side by side, each free to focus on a different aspect of the input. That refinement is a separate topic, but it is worth noting that plain self-attention over the whole dimension is the conceptual starting point from which the richer designs are built.
