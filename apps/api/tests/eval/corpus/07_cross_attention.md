# Cross-Attention in Encoder-Decoder Models

Cross-attention is the attention mechanism that connects two different sequences. Where self-attention lets a sequence attend to itself, cross-attention lets one sequence attend to another. In the classic Transformer for sequence-to-sequence tasks such as machine translation, cross-attention is the bridge that carries information from the encoder into the decoder. It is the only place in the decoder where representations of the source sequence flow into the generation of the target sequence.

## Where Queries, Keys, and Values Come From

The scoring computation in cross-attention is identical to scaled dot-product attention: dot products between queries and keys, scaling by the square root of the key dimension, a softmax, and a weighted sum of values. What makes it cross-attention is the origin of the vectors. The queries are produced from the decoder's current hidden states, while the keys and values come from the encoder outputs. In other words, the target side asks the questions and the source side supplies both the addressing keys and the content values. This asymmetry is the whole point: each decoder position can look across the entire encoded source and pull in whatever it needs.

```python
def cross_attention(dec_hidden, enc_output, W_q, W_k, W_v):
    Q = dec_hidden @ W_q     # queries from the decoder
    K = enc_output @ W_k     # keys from the encoder
    V = enc_output @ W_v     # values from the encoder
    d_k = Q.shape[-1]
    scores = Q @ K.T / (d_k ** 0.5)   # (target_len, source_len)
    weights = softmax(scores, axis=-1)
    return weights @ V
```

Note that the resulting score matrix is rectangular, with one row per target position and one column per source position, rather than the square matrix produced by self-attention.

## The Decoder Layer

A Transformer decoder layer stacks three sub-layers. First, masked self-attention lets each target position attend to the tokens generated so far. Second, cross-attention lets those target positions attend to the encoder's representation of the source. Third, a position-wise feed-forward network transforms the result. Cross-attention sits in the middle and is the sole conduit through which encoder information reaches the decoder. If it were removed, the decoder would be a plain language model with no access to the source at all.

## Caching Encoder States

Cross-attention enables an important inference optimization. Because the encoder runs only once for a given input and its output does not change as the decoder generates tokens, the keys and values derived from the encoder can be computed a single time and cached. During autoregressive decoding, only the queries change from step to step as new target tokens are produced. Reusing the cached encoder keys and values avoids recomputing them at every decoding step and is a standard speedup in production inference systems.

## Relationship to Translation Alignment

The idea behind cross-attention traces back to attention in early neural machine translation. Before Transformers, sequence-to-sequence models compressed the entire source sentence into a single fixed vector, which became a bottleneck for long inputs. Attention let the decoder softly focus on the most relevant source words at each output step instead of relying on one compressed summary. Cross-attention in the Transformer performs the same role with learned, content-based alignment between target positions and source positions, but expressed through the query-key-value formulation and stacked across many layers and heads.

## Beyond Translation

The pattern generalizes to any setting where one stream must be conditioned on another. Text-to-image diffusion models use cross-attention so that the image being generated attends to the text prompt, with queries coming from the image features and keys and values from the encoded text. Multimodal encoders apply the same structure across modalities. In every case the shape is the same: queries come from the sequence being produced or refined, and keys and values come from the sequence being consulted.

## Self-Attention vs Cross-Attention

Because both mechanisms often appear in the same model, keeping them straight matters. Self-attention draws all three projections from a single sequence, producing a square score matrix and letting a sequence refine its own representation. Cross-attention draws its queries from one sequence and its keys and values from another, producing a rectangular score matrix that lets one sequence read from a second. The scaling and softmax steps are identical; only the sources of the vectors differ.

## Masking Differences

Masking is one of the most common places to make a mistake. The decoder's self-attention uses a causal mask to prevent a position from seeing future target tokens. Cross-attention, by contrast, usually has no causal mask at all, because the entire source is available from the start and a target position may freely attend to any source position. Only a padding mask is applied, to hide padded positions in the source. Confusing the causal mask of self-attention with the padding-only mask of cross-attention is a frequent implementation bug.

## Shape and Complexity

The rectangular score matrix has consequences for cost. With a target of length m and a source of length n, cross-attention produces an m-by-n matrix of scores, so its time and memory scale with the product m times n rather than with a single length squared. When the source is very long, this term dominates decoder cost, which is one reason encoder key-value caching matters so much in practice. Each cross-attention head projects the encoder output into its own key and value subspace, exactly as in multi-head self-attention, so a decoder layer typically runs many cross-attention heads in parallel over the same cached encoder states.

## Gradient Flow Between Encoder and Decoder

Cross-attention is also the path along which gradients travel from the decoder back into the encoder during training. Because the encoder keys and values participate directly in every target position's output, the loss computed on generated tokens propagates through the cross-attention weights and into the encoder parameters. This coupling is what lets the encoder learn source representations that are actually useful for generation, rather than representations tuned only to reconstruct the input. Removing or freezing cross-attention would sever this learning signal and leave the encoder unaware of what the decoder needs.
