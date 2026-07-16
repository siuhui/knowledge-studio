# FAISS: A Library for Efficient Similarity Search

FAISS (Facebook AI Similarity Search) is a library for similarity search and clustering of dense vectors, developed by Meta AI Research. It is written in C++ with thin Python bindings, and it is engineered to handle collections ranging from a few thousand vectors up into the billions. The central design decision that shapes everything else is that FAISS is a library rather than a standalone service: it links into your own process, holds its indexes in memory, and exposes function calls. It has no network protocol, no query language, no built-in persistence layer, and no cluster manager. You get very low overhead and total control, but you are responsible for serving, sharding, and durability yourself.

## Indexes are objects you build

In FAISS everything revolves around an `Index` object. You choose an index type, optionally train it on sample data, add your vectors, and then call `search` with a batch of query vectors to retrieve the `k` nearest neighbors for each. Search returns two arrays: the distances and the integer positions of the matched vectors. FAISS assigns sequential integer ids by default, so mapping those back to your own record identifiers is something you arrange outside the library.

## Flat indexes: exact search

The simplest index is the flat index, which stores vectors uncompressed and compares a query against every one of them. `IndexFlatL2` performs an exhaustive brute-force search using squared Euclidean distance, and it returns the true nearest neighbors with perfect recall. Its cost grows linearly with the number of stored vectors, so it is ideal for small collections or as a ground-truth baseline when measuring the recall of an approximate index. `IndexFlatIP` is the inner-product variant, typically used with L2-normalized vectors so that inner product ranks the same way as cosine similarity.

```python
import faiss
import numpy as np

d = 128                       # vector dimension
index = faiss.IndexFlatL2(d)  # exact L2 search

xb = np.random.random((10000, d)).astype("float32")
index.add(xb)                 # no training needed for a flat index

xq = np.random.random((5, d)).astype("float32")
distances, ids = index.search(xq, k=5)
```

## Inverted-file indexes: IVF

To avoid scanning every vector, `IndexIVFFlat` partitions the space with a coarse quantizer into Voronoi cells. The `nlist` parameter sets how many cells exist, and at query time `nprobe` controls how many of the nearest cells are actually scanned. A small `nprobe` is fast but may miss neighbors near a cell boundary, while a larger `nprobe` raises recall at the cost of latency. Unlike a flat index, an IVF index must be trained on a representative sample first so the quantizer can learn where the cell centroids sit before any vectors are added.

```python
d = 128
nlist = 100
quantizer = faiss.IndexFlatL2(d)
index = faiss.IndexIVFFlat(quantizer, d, nlist)

index.train(xb)      # learn the coarse centroids
index.add(xb)
index.nprobe = 10    # scan 10 cells per query
distances, ids = index.search(xq, k=5)
```

## Compression: product quantization

For collections too large to keep as raw floats, FAISS offers product quantization. `IndexIVFPQ` combines the inverted-file partitioning with PQ compression, splitting each vector into sub-vectors and encoding each with a small codebook. This shrinks memory dramatically, letting billions of vectors fit in RAM, at the cost of approximating distances rather than computing them exactly. The composite index string syntax, such as `"IVF4096,PQ64"`, lets you describe these pipelines compactly to the `index_factory` helper.

## GPU acceleration

A distinctive strength of FAISS is first-class GPU support. Many index types have GPU implementations that run search an order of magnitude faster than on CPU for large batches. You move an index onto a device with `index_cpu_to_gpu`, and you can shard a single large index across several GPUs. Because GPU memory is limited, the compressed IVF and PQ families are especially useful there, since they let more vectors fit on the device at once.

## Identifiers and metadata

Since FAISS stores only vectors, it provides `IndexIDMap` to attach arbitrary 64-bit identifiers so that search returns your ids instead of sequential positions. Anything richer than an integer id, such as text, tags, or timestamps for filtering, must live in a separate store that you join against after retrieving candidates. FAISS deliberately stays out of the metadata business; it is a nearest-neighbor engine, not a database.

## Persistence

An index is serialized with `faiss.write_index` and reloaded with `faiss.read_index`. There is no incremental write-ahead log or automatic durability, so a common production pattern is to build the index offline, persist the file, and load it into read-only serving processes. Updates typically mean rebuilding or maintaining a small mutable delta index in front of a large frozen one.

```python
faiss.write_index(index, "vectors.faiss")
index = faiss.read_index("vectors.faiss")
```

## Choosing an index

Picking an index is a balance of memory, speed, and recall. Use a flat index when the collection is small or when you need exact answers and a recall baseline. Move to IVF when the collection grows into the millions and some approximation is acceptable. Reach for PQ variants when raw vectors no longer fit in memory and billion-scale efficiency matters more than exactness. Because FAISS gives you the primitives rather than a finished service, it is most attractive to teams that want to embed high-performance similarity search inside their own application and are prepared to build the serving and storage layers around it.
