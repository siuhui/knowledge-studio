# FlashAttention: IO-Aware Exact Attention

FlashAttention is an algorithm for computing exact attention that is designed around the memory hierarchy of modern GPUs rather than around raw arithmetic. The key observation behind it is that a standard attention implementation is bottlenecked not by floating-point operations but by the repeated movement of the large intermediate score matrix between levels of GPU memory. By reorganizing the computation to respect the hardware, FlashAttention reduces the reads and writes between high-bandwidth memory and SRAM, which is what actually dominates the wall-clock time of the operation.

## The Memory Bottleneck

A naive attention kernel computes the full score matrix, writes it out to high-bandwidth memory, reads it back to apply the softmax, writes the softmax result out again, and reads it once more to multiply by the value matrix. Each of these round trips moves a tensor whose size grows with the square of the sequence length. Because high-bandwidth memory, despite its name, is far slower than the small on-chip memory close to the compute units, these transfers are the true cost. The arithmetic itself finishes quickly and then waits on data.

## Tiling and On-Chip SRAM

FlashAttention exploits the GPU memory hierarchy by keeping intermediate results in the fast on-chip SRAM and never spilling the full score matrix to slower memory. It divides the queries, keys, and values into blocks small enough to fit in SRAM, then loops over key and value blocks for each query block. Within the on-chip memory it fuses the three logical steps, score computation, softmax, and multiplication by values, into a single pass. Because the intermediate scores for a block live only in SRAM and are consumed immediately, FlashAttention never materializes the full attention matrix in high-bandwidth memory.

```python
# Schematic of the tiled forward pass (one query block)
for kv_block in split(K, V):          # stream key/value tiles through SRAM
    s = q_block @ kv_block.K.T / sqrt(d)   # partial scores, on-chip
    m_new = max(m_running, rowmax(s))      # update running max
    p = exp(s - m_new)                     # rescale exponentials
    l = exp(m_running - m_new) * l + rowsum(p)   # update running sum
    o = exp(m_running - m_new) * o + p @ kv_block.V
    m_running = m_new
o = o / l                              # final normalization
```

## Online Softmax

Because the algorithm processes keys one block at a time, it cannot see all the scores before normalizing. FlashAttention solves this with an online softmax: it maintains a running maximum and a running normalization sum while streaming through the key blocks. Whenever a new block produces a score larger than the current maximum, the partial output and the running sum are rescaled so that the final result is identical to a softmax computed over the entire row at once. This numerically stable, incremental normalization is what makes single-pass, block-wise attention possible.

## Exactness

FlashAttention is not an approximation. It is mathematically equivalent to computing the full softmax attention over the entire sequence, so it produces bit-for-bit comparable results to a standard implementation up to floating-point reordering. This distinguishes it sharply from methods that trade accuracy for speed. The gains come entirely from a better memory access pattern, not from dropping or approximating any entries of the attention computation.

## Memory Savings

The consequence of never storing the full score matrix is that peak memory stops scaling with the square of the sequence length. Instead of holding an n-by-n tensor, the algorithm keeps only the current blocks in SRAM plus a small set of running statistics, so its memory footprint is linear in the sequence length. This is what allows models to train and run inference with far longer context windows on the same hardware than a naive implementation could support.

## Backward Pass and Recomputation

Since the forward pass deliberately avoids saving the full attention matrix, the backward pass cannot simply read it back to compute gradients. FlashAttention instead recomputes the needed attention blocks on the fly during the backward pass, using the saved running statistics. This recomputation adds some extra floating-point work, but because the operation was memory-bound to begin with, trading a little more arithmetic for far less data movement is a net win.

## Relationship to Approximate Attention

Earlier efforts to tame the quadratic cost of attention took a different route. Sparse attention restricts each position to attend to a limited subset of others, and linear attention rewrites the computation with kernel feature maps to avoid forming the score matrix at all. These methods reduce asymptotic complexity but change the mathematics of attention, which can degrade model quality and often requires retraining. FlashAttention's advantage is that it preserves exact softmax attention while optimizing only the memory access pattern through tiling and kernel fusion, so it can be dropped into existing models without any change to their behavior or the need to retrain them.
