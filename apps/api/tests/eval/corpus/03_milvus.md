# Milvus: A Distributed Vector Database

Milvus is an open-source vector database built for large-scale similarity search over embeddings. It was originally created by Zilliz and later donated to the LF AI & Data Foundation. Unlike a search library that links into your application, Milvus is a full database system with its own API, query engine, metadata management, and durability. Its defining property is that Milvus adopts a distributed architecture that separates storage and compute, which lets each concern scale independently and lets stateless workers recover quickly after failure.

## Cloud-native architecture

A Milvus cluster is composed of several layers rather than a single monolithic process. A stateless proxy layer receives client requests, validates them, and routes work to the appropriate nodes. A set of coordinators handle cluster-level responsibilities: the root coordinator manages metadata and time synchronization, the data coordinator supervises writes and segment lifecycle, the query coordinator balances search load, and the index coordinator schedules index builds. Below the coordinators sit worker nodes—query nodes, data nodes, and index nodes—that do the actual heavy lifting and can be added or removed to scale a specific bottleneck without touching the others.

## Externalized storage

Milvus deliberately does not implement its own durable storage. Instead it delegates to battle-tested infrastructure. Metadata such as collection schemas and node topology lives in etcd. Bulk data—the vectors themselves plus their built indexes—resides in an object store like S3 or MinIO. Incoming writes flow through a streaming log, using Pulsar or Kafka as a write-ahead log so that inserts are durable before they are ever indexed. Keeping the compute nodes stateless in this way is what allows them to restart or rebalance without data loss.

## Segments and the data lifecycle

Data inside a collection is physically organized into segments. Freshly inserted rows accumulate in an in-memory growing segment that is immediately searchable so new data is visible with low delay. When a growing segment reaches a size threshold, Milvus flushes a growing segment into a sealed segment, writes it to object storage, and hands it to an index node to build the approximate index. Search therefore fans out across both sealed segments, which are indexed and immutable, and growing segments, which are recent and searched by brute force, and then merges the results.

## Collections, partitions, and shards

A collection is the top-level container, analogous to a table, and holds a defined schema of a primary key, a vector field, and scalar fields. Collections can be divided into partitions, which prune the search space: if you partition by tenant or by month, a query scoped to one partition never touches the others. Orthogonally, a collection is split into shards so that writes are distributed across multiple data nodes for throughput. Partitions are a logical query-pruning tool while shards are a physical write-distribution tool.

## Index types and metrics

Milvus supports a menu of index types so you can trade memory, build time, latency, and recall against each other. Common choices include `IVF_FLAT` and `IVF_PQ` from the inverted-file family, graph-based `HNSW`, and the disk-oriented `DiskANN` for datasets that exceed RAM. Each index is created with a metric type—`L2`, `IP` for inner product, or `COSINE`—that must match how the embeddings were produced.

```python
from pymilvus import Collection

index_params = {
    "index_type": "HNSW",
    "metric_type": "COSINE",
    "params": {"M": 16, "efConstruction": 200},
}
collection.create_index(field_name="embedding", index_params=index_params)
collection.load()   # bring segments into query-node memory before searching
```

## Consistency levels

Because Milvus is distributed and writes travel through a log before becoming searchable in sealed segments, it exposes tunable consistency levels that let each request choose how fresh its view must be. Strong consistency guarantees a search sees every write that completed before it, at the price of waiting for the log to catch up. Bounded staleness allows results to lag by a bounded interval, session consistency guarantees a client reads its own writes, and eventual consistency offers the lowest latency with the weakest freshness guarantee. Applications pick a level per query based on whether latency or freshness matters more.

## Filtered search

Milvus can combine vector similarity with structured predicates over scalar fields. A boolean expression is evaluated inside the engine rather than by filtering on the client after retrieval, which keeps the candidate set correct and efficient.

```python
results = collection.search(
    data=[query_vector],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 64}},
    limit=10,
    expr='category == "book" && price < 100',
)
```

## Deployment modes

Milvus scales down as well as up. Milvus Lite embeds the engine into a Python process for prototyping and small workloads. Standalone mode packages the core services into a single container backed by a local etcd and object store, suitable for a single machine. Cluster mode runs the full separated architecture on Kubernetes, where proxies, coordinators, and each class of worker node scale horizontally and independently. Before a collection can be queried it must be loaded, which pulls the relevant segments and indexes into query-node memory; releasing a collection frees that memory for others.

## When to choose Milvus

Milvus makes sense when the scale or operational requirements outgrow an in-process library or a single relational node. If you have hundreds of millions to billions of vectors, need horizontal scaling, want built-in durability through object storage and a log, and require features like partitions, multiple consistency levels, and role-based access, a dedicated distributed vector database earns its added operational complexity. For smaller datasets that fit comfortably on one machine, that complexity is usually not worth paying for.
