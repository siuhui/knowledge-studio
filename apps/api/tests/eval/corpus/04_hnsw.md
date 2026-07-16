# HNSW: Hierarchical Navigable Small World Graphs

Hierarchical Navigable Small World (HNSW) is an algorithm for approximate nearest neighbor search that organizes vectors into a layered proximity graph. It was introduced by Malkov and Yashunin and has become one of the most widely deployed indexing methods, appearing as an option inside many vector databases and search libraries. HNSW is prized for its excellent recall-versus-latency tradeoff and for the fact that it needs no separate training phase: the index is built purely by inserting points one at a time.

## The multi-layer structure

The core idea builds on two older concepts. Navigable small-world graphs connect each vector to a handful of neighbors such that any node can be reached from any other in a small number of hops. HNSW adds a hierarchy of these graphs stacked in layers, an idea borrowed from skip lists. The bottom layer contains every vector, and each higher layer contains a random, exponentially thinned subset of the layer beneath it. Consequently the top HNSW layer contains only a sparse subset of all points, forming long-range shortcuts, while the dense bottom layer captures fine-grained local structure. When a new element is inserted, a random level is drawn from an exponentially decaying distribution to decide the highest layer it will join.

## How search works

A query enters at a single entry point in the topmost layer and greedily walks toward the query vector, repeatedly hopping to whichever neighbor is closer. When it can no longer improve at the current layer, it drops down one layer and continues from where it stopped. The sparse upper layers let the search cover large distances in few steps, zooming quickly into the right region of the space, and the descent refines the result as the graph grows denser. This coarse-to-fine navigation is what gives HNSW its characteristic logarithmic-like scaling of search time with dataset size.

```text
Layer 2:   entry ●───────────────● 
                  \               
Layer 1:   ●───────●────────●─────●
                    \        
Layer 0:   ●─●─●─●─●─●─●─●─●─●─●─●─●   (all vectors)
```

## Key parameters

Two build-time parameters dominate the quality and cost of an HNSW index. The parameter `M` sets the maximum number of neighbors each node keeps per layer; a larger `M` produces a richer graph with better recall but higher memory use and slower construction. The parameter `efConstruction` controls the size of the dynamic candidate list explored while inserting a new node—raising it improves graph quality at the expense of build time.

At query time, a single parameter `ef` (sometimes called `efSearch`) sets the size of the candidate list maintained during the descent through the bottom layer. A larger `ef` explores more of the graph, increasing recall while spending more time per query, and it must be at least as large as the number of neighbors `k` you want returned. Tuning HNSW in practice usually means fixing `M` and `efConstruction` at build time and then sweeping `ef` to find the recall-latency point the application needs.

```python
import hnswlib
import numpy as np

dim = 128
p = hnswlib.Index(space="cosine", dim=dim)
p.init_index(max_elements=100000, M=16, ef_construction=200)

data = np.random.random((100000, dim)).astype("float32")
p.add_items(data)

p.set_ef(64)                       # query-time breadth
labels, distances = p.knn_query(data[:5], k=10)
```

## Incremental construction

Because every point is added individually through the same greedy search-and-connect procedure used for queries, HNSW supports online insertion. New vectors can be appended to a live index without rebuilding it from scratch, which is a meaningful operational advantage over methods that must learn a partitioning from a data sample before they can be populated. This is why graph indexes can be created on an empty structure and grown as data arrives.

## Deletion and memory tradeoffs

The convenience of incremental building comes with two well-known costs. First, HNSW is a memory-resident structure: the entire graph, including all the neighbor links, must stay in RAM, so per-vector overhead is higher than compressed schemes such as product quantization. Second, deletion is awkward, because physically removing a node can disconnect paths that other nodes relied on for navigation. Most implementations therefore only mark elements as deleted (a soft delete) and reclaim the space during a full rebuild, so churn-heavy workloads periodically pay a reconstruction cost.

## Complexity and comparison

Search visits a number of nodes that grows roughly logarithmically with the dataset size, while construction cost grows near-linearly in the number of inserted points scaled by the candidate-list breadth. Compared with inverted-file methods that cluster vectors and scan a chosen number of partitions, HNSW usually achieves higher recall at the same latency and avoids the sensitivity of cluster-based indexes to how well the training sample represents the data. Its weaknesses are the higher memory footprint and the deletion problem. These tradeoffs explain why HNSW is frequently the default choice for in-memory approximate nearest neighbor search, while disk-based or quantized approaches take over when a dataset is simply too large to hold in memory as an uncompressed graph.

## Practical guidance

A reasonable starting point for many datasets is `M` around 16 and `efConstruction` in the low hundreds, then adjusting `ef` at query time to hit a target recall. Raising `M` helps most for high-dimensional or hard-to-separate data. Because the graph must fit in memory, capacity planning should account for the neighbor links, which can add substantial overhead on top of the raw vectors themselves. When those constraints are acceptable, HNSW delivers some of the best in-class query performance available for approximate nearest neighbor search.
