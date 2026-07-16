# pgvector: Vector Similarity Search Inside PostgreSQL

pgvector is an open-source extension that adds vector similarity search directly to PostgreSQL. Instead of running a separate vector database alongside your relational store, pgvector lets you keep embeddings in ordinary tables next to the rest of your data. This means a single SQL query can filter on business columns and rank rows by embedding similarity at the same time, and it means your vectors inherit PostgreSQL's transactions, backups, and replication without any extra moving parts.

## The vector data type

The extension introduces a `vector` column type whose dimensionality is fixed when the column is declared. A row stores a dense array of single-precision floats, and the dimension must match whatever your embedding model produces. Because the type lives inside PostgreSQL, you insert and update vectors with normal `INSERT` and `UPDATE` statements, and you can add ordinary indexes, constraints, and foreign keys to the same table.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id          bigserial PRIMARY KEY,
    tenant_id   int NOT NULL,
    content     text,
    embedding   vector(1536)
);

INSERT INTO documents (tenant_id, content, embedding)
VALUES (1, 'hello world', '[0.12, -0.03, ...]');
```

## Distance operators

pgvector exposes similarity as distance operators that you place in the `ORDER BY` clause. The `<->` operator computes L2 (Euclidean) distance, `<#>` computes negative inner product, and `<=>` computes cosine distance. Choosing an operator that matches how your embeddings were trained is important: models tuned for cosine similarity should be queried with `<=>`, while inner-product models use `<#>`. A nearest-neighbor query is just an ordered, limited select:

```sql
SELECT id, content
FROM documents
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 10;
```

Without an index, this query performs an exact scan over every row, computing the distance for each vector. That guarantees perfect results but grows linearly with table size, so large tables need an approximate index to stay fast.

## IVFFlat indexes

The first approximate index pgvector shipped is IVFFlat, an inverted-file approach. When you build it, the extension runs k-means over a sample of your data to learn cluster centroids. Conceptually, the IVFFlat index divides the vector space into lists, where each list is a cluster of nearby vectors assigned to one centroid. At query time, pgvector compares the query only against the vectors in the closest lists rather than the whole table.

```sql
CREATE INDEX ON documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

The `lists` parameter sets how many clusters are created; a common starting heuristic is roughly the square root of the row count for large tables. Because the centroids are learned from existing data, you should build an IVFFlat index only after the table already holds a representative sample of rows. Building it on an empty or tiny table produces poor clustering.

Recall for IVFFlat is tuned at query time through the `ivfflat.probes` setting, which decides how many of the nearest lists to scan. Scanning a single list is fastest but may miss neighbors that fell into an adjacent cluster; raising the probe count trades latency for higher recall. You set it per session or per transaction:

```sql
SET ivfflat.probes = 10;
```

## HNSW indexes

pgvector also supports HNSW, a graph-based index that generally delivers higher recall and lower query latency than IVFFlat at the cost of slower build times and larger memory use. A useful practical difference is that HNSW does not depend on a learned data distribution, so it can be built on an empty table and populated incrementally as rows arrive.

```sql
CREATE INDEX ON documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Build quality is controlled by `m`, the number of connections per node, and `ef_construction`, the size of the candidate list used while inserting. At query time, the `hnsw.ef_search` parameter widens or narrows the search frontier: larger values improve recall but examine more nodes. Because HNSW keeps its graph in memory, `maintenance_work_mem` should be large enough to build the index without spilling to disk.

## Operator classes

Both index types require an operator class that matches your chosen distance operator. `vector_l2_ops` supports `<->`, `vector_ip_ops` supports `<#>`, and `vector_cosine_ops` supports `<=>`. An index built for one operator class will not accelerate queries using a different operator, so the operator class, the query operator, and the embedding model must all agree on the same distance metric.

## Combining similarity with SQL filters

The strongest argument for pgvector is that similarity search composes with everything else PostgreSQL already does. Because the query planner sees the whole statement, you can constrain results with a `WHERE` clause and still rank the survivors by distance:

```sql
SELECT id, content
FROM documents
WHERE tenant_id = 1
  AND created_at > now() - interval '30 days'
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 10;
```

This is genuine hybrid retrieval in one engine: relational predicates and vector ranking evaluated together, joined against other tables if needed, all inside a single transaction. For workloads that mix structured metadata with embeddings, this avoids the consistency headaches of syncing a dedicated vector store with your primary database.

## Operational considerations

Because pgvector runs inside PostgreSQL, it scales the way PostgreSQL scales. Read replicas can serve similarity queries, and standard tooling handles backups and point-in-time recovery. Index builds are CPU-intensive; using `CREATE INDEX CONCURRENTLY` avoids taking a heavy lock on a live table. Dimensionality has a practical ceiling, and very high-dimensional vectors consume significant storage per row, so many teams reduce embedding dimensions before ingestion. For datasets in the low millions of vectors, an HNSW index on PostgreSQL is frequently fast enough that a separate specialized database is unnecessary, which keeps the overall system simpler to operate.

## When to choose pgvector

pgvector fits best when your vectors are naturally part of a relational application and you value operational simplicity over raw scale. You already trust PostgreSQL, you want transactional guarantees over your embeddings, and your dataset is comfortably in memory. If you eventually outgrow a single node, or need billions of vectors sharded across a cluster, a purpose-built distributed system becomes more attractive, but for a large fraction of real applications the answer is to keep the vectors where the rest of the data already lives.
