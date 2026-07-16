# GIN Indexes in PostgreSQL

GIN stands for Generalized Inverted Index, and it is the access method PostgreSQL uses when a single row contains many
indexable values rather than one scalar key. Where a B-tree stores one entry per row, the GIN inverted index stores one
entry per element and maps that element back to every row that contains it. This structure is what makes GIN the right
choice for full-text search, array containment, and queries against `jsonb` documents.

## Inverted index structure

The core idea borrows directly from search engines. Instead of asking "what values does this row hold," a GIN index
answers "which rows hold this value." Internally it maintains an entry tree keyed by individual items, and each key
points to a posting list or posting tree enumerating the row identifiers that contain that item. When a document holds
many words, or an array holds many tags, each distinct element becomes one key whose posting list gathers every row it
appears in. A search then looks up the queried elements and intersects or unions their posting lists.

Because the same element from thousands of rows collapses to a single key with a shared posting list, GIN indexes are
remarkably compact for data with many repeated values. The tradeoff is on the write side, discussed below.

## Full-text search

The most common use of GIN is indexing `tsvector` columns for full-text search. A `tsvector` is a sorted list of
normalized lexemes, and the GIN index treats each lexeme as one key, so a query for a word jumps straight to the rows
that mention it.

```sql
CREATE INDEX idx_docs_fts ON documents
  USING gin (to_tsvector('english', body));

SELECT id, title FROM documents
 WHERE to_tsvector('english', body) @@ plainto_tsquery('english', 'balanced tree');
```

The `@@` match operator is what the index accelerates. Without the index this query would recompute the `tsvector` for
every row and scan the whole table; with it, PostgreSQL consults the posting lists for the query lexemes and touches
only the matching rows.

## Arrays and jsonb containment

GIN also indexes array columns and `jsonb` documents. For an array, each distinct element becomes a key, so the
containment operators `@>`, `<@`, and the overlap operator `&&` can be answered from the index. For `jsonb`, the
default operator class indexes both keys and values, supporting the containment operator `@>` and existence operators
such as `?`.

```sql
CREATE INDEX idx_items_tags ON items USING gin (tags);

-- Uses the inverted index to find rows whose array contains both tags
SELECT * FROM items WHERE tags @> ARRAY['postgres', 'index'];
```

There is a lighter-weight `jsonb_path_ops` operator class that indexes only hashed paths rather than every key and
value. It produces a smaller index and faster containment lookups, at the cost of supporting fewer operators, so it is
a good choice when your queries only ever use `@>`.

## The pending list and fastupdate

Inserting into a GIN index is expensive because one new row can touch many keys scattered across the entry tree. To
soften this, GIN has a `fastupdate` mechanism: new entries are first appended to an unsorted pending list, and later
merged into the main structure in bulk. The merge happens when the pending list exceeds `gin_pending_list_limit`, or
during vacuum, or when a query needs it. This batching amortizes the cost of many small writes, though it means a
search may have to scan the pending list in addition to the main index until the next merge occurs.

```sql
ALTER INDEX idx_docs_fts SET (fastupdate = on, gin_pending_list_limit = '4MB');
```

## When GIN is the wrong tool

GIN indexes are not ordered, so they cannot satisfy an `ORDER BY` or return a range of scalar values the way a B-tree
does. They are also slower to build and larger to maintain when the indexed values change frequently. For a plain
scalar column with simple equality and range predicates, a B-tree remains the better choice. GIN earns its cost only
when each row genuinely contains a collection of searchable items, where the inverted mapping from element to rows is
what the workload actually needs.
