# Multi-Head Attention

Multi-head attention runs several attention computations in parallel and combines their results, rather than performing one attention function across the entire representation. Instead of computing attention once over the full model dimension, it splits the model dimension into several lower-dimensional attention heads, applies scaled dot-product attention independently within each, and then recombines the outputs. This design gives the model the ability to jointly attend to information from different representation subspaces at different positions, which a single attention function cannot do.

## Motivation

With one attention distribution, a position must blend every kind of relationship it cares about, syntactic, positional, coreferential, into a single set of weights. Averaging these competing signals loses information. Multiple heads sidestep this by letting each head form its own attention distribution over its own subspace. One head might track the immediately preceding token, another might link a pronoun to its antecedent, and a third might attend to a distant but topically related word, all in the same layer and all at once.

## Projection, Attention, Concatenation

The mechanism has three stages. First, the input is linearly projected into per-head queries, keys, and values using separate learned weight matrices, so each head sees a different lower-dimensional view of the input. Second, scaled dot-product attention is computed independently inside each head. Third, the per-head outputs are concatenated back into a single vector and passed through a final output projection.

```python
def multi_head_attention(X, W_q, W_k, W_v, W_o, h):
    n, d_model = X.shape
    d_k = d_model // h
    outputs = []
    for i in range(h):                       # h heads in parallel
        Qi = X @ W_q[i]                      # (n, d_k)
        Ki = X @ W_k[i]                      # (n, d_k)
        Vi = X @ W_v[i]                      # (n, d_k)
        Ai = scaled_dot_product(Qi, Ki, Vi)  # (n, d_k)
        outputs.append(Ai)
    concat = np.concatenate(outputs, axis=-1)  # (n, d_model)
    return concat @ W_o                        # final output projection
```

## Subspaces and Dimensions

If the model dimension is d and there are h heads, each head typically works in a subspace of dimension d divided by h. The large query, key, and value projections can be seen as h smaller projections stacked together, each carving out its own subspace of the representation. Every head therefore attends to information from a different representation subspace, and the concatenation step reassembles these subspaces into a full-width vector before the output projection mixes them.

## Computational Cost

A useful property is that the total computational cost stays roughly constant as the number of heads changes. Because each head operates in a subspace of reduced dimension, splitting into more heads partitions the existing compute and parameter budget into parallel channels rather than multiplying it. Doubling the head count while halving the per-head dimension leaves the total number of parameters and floating-point operations essentially unchanged, so multi-head attention buys representational diversity at almost no extra cost.

## What Different Heads Learn

Empirically, heads specialize, and some of their behavior is interpretable. Certain heads attend consistently to the previous or next token, some focus on separators and delimiters, and others capture longer-range dependencies such as subject-verb agreement. At the same time, studies of trained models find substantial redundancy: many heads can be pruned after training with little or no loss in quality, suggesting that only a subset of heads carries most of the load.

## Concatenation and Output Projection

The final output projection is more than bookkeeping. After each head produces its subspace output, concatenation stacks them into one vector that is partitioned by head. The output projection matrix then recombines these partitions, allowing the layer to produce values that depend jointly on several heads at once. Without this mixing step, the heads would remain isolated channels and could not contribute to a shared representation. The projection is what turns a set of independent attention results into a single coherent output.

## Choosing the Number of Heads

Selecting the head count is a trade-off. Too few heads limits the diversity of relationships the layer can represent, pushing it back toward the single-distribution bottleneck. Too many heads shrinks each subspace so much that individual heads lack the dimensionality to represent anything useful, and the per-head attention becomes noisy. Common configurations pick a head count that keeps the per-head dimension in a moderate range, balancing expressive diversity against the capacity of each individual head.

## Efficient Implementations

In practice the per-head loop shown above is never written out explicitly. Real implementations fuse the h projection matrices into single large weight matrices, compute all queries, keys, and values in one matrix multiply, and then reshape the result into a head axis. The batched tensor of shape batch by heads by length by head-dimension lets a single batched matrix multiply score every head at once, which maps efficiently onto GPU hardware. After attention, the head axis is folded back and the output projection is applied. The mathematics is identical to the loop; only the memory layout and the number of kernel launches change.

## Variants That Share Keys and Values

Later architectures reduce the memory footprint of attention by letting several query heads share a single set of keys and values. Multi-query attention takes this to the extreme, using many query heads but only one key head and one value head, which shrinks the key-value cache that dominates memory during autoregressive generation. Grouped-query attention is the middle ground, partitioning the query heads into a few groups that each share one key-value pair. These variants keep the parallel-head structure for queries while trading a small amount of quality for large savings in the cache, and they have become standard in large language models built for fast inference.
