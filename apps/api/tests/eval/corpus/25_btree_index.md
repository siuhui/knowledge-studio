# B-tree Indexes in PostgreSQL

The B-tree is the default and most widely used index type in PostgreSQL. When you write `CREATE INDEX` without
specifying an access method, you get a B-tree. It is a self-balancing tree that keeps its keys in sorted order, which
makes it the natural structure for equality lookups, range scans, and any query that benefits from ordered data. Almost
every primary key and unique constraint in a typical schema is backed by a B-tree behind the scenes.

## Balanced tree structure

A B-tree is organized into pages arranged as a shallow, wide, balanced tree. The root and internal pages hold separator
keys that route a search toward the correct child, while the leaf pages hold the actual index entries pointing at heap
tuples. Because the tree stays balanced as rows are inserted and deleted, every leaf sits at the same depth, so the
number of page reads to locate any key is roughly constant. In practice even a table with hundreds of millions of rows
is only three or four levels deep, so a lookup touches just a handful of pages before reaching the leaf.

PostgreSQL implements a variant known as a Lehman and Yao B-link tree, which adds a right-link pointer between sibling
leaf pages. This link lets a scan move sideways to the next page without climbing back up to the parent, and it allows
readers to proceed concurrently with page splits caused by writers.

## Ordered keys and range scans

Because leaf entries are stored in sorted key order, a B-tree index can do far more than pinpoint a single value. It can
walk a contiguous stretch of the leaf level to satisfy a range predicate, following the right-links from one leaf to the
next. This is why a B-tree is the ideal structure for range scans over ordered data such as timestamps or numeric
columns.

```sql
CREATE INDEX idx_orders_created ON orders (created_at);

-- The planner descends to the first matching leaf, then walks forward in order
SELECT * FROM orders
 WHERE created_at >= '2026-01-01' AND created_at < '2026-02-01'
 ORDER BY created_at;
```

The same ordering means a B-tree can supply rows already sorted, so an `ORDER BY` on the indexed column can be answered
without a separate sort step. It also serves both directions, satisfying ascending and descending requests from one
physical structure.

## Supported operators and multicolumn indexes

A B-tree accelerates the ordering operators `<`, `<=`, `=`, `>=`, and `>`, along with `BETWEEN` and `IN`, and it can
support pattern matches like `LIKE 'prefix%'` when the pattern is anchored at the start. A multicolumn B-tree sorts by
the leading column first, then by the next, and so on, so it is most effective when a query constrains a prefix of the
indexed columns. A predicate on the second column alone cannot use the ordered structure efficiently, because the entries
are not globally sorted by that column.

```sql
CREATE INDEX idx_events_kb_time ON events (knowledge_base_id, created_at);

-- Uses both columns: equality on the leading key, range on the trailing key
SELECT * FROM events
 WHERE knowledge_base_id = '...' AND created_at > now() - interval '1 day';
```

## Index-only scans and covering indexes

When every column a query needs is present in the index, PostgreSQL can perform an index-only scan and skip visiting the
heap entirely, provided the relevant table pages are marked all-visible in the visibility map. The `INCLUDE` clause lets
you add non-key payload columns to a B-tree so the index covers a query without making those columns part of the sort
key.

```sql
CREATE INDEX idx_users_email ON users (email) INCLUDE (display_name);
```

## Physical maintenance and bloat

B-tree pages fill as rows are inserted, and when a leaf page has no room a page split moves half its entries to a new
page. Over time, deletions and splits can leave pages sparsely populated, a condition known as index bloat that inflates
the on-disk size and slows scans. PostgreSQL reclaims entries for dead tuples during vacuum and can merge nearly empty
pages, but a heavily churned index sometimes benefits from `REINDEX`, which rebuilds it compactly. Modern versions also
deduplicate repeated key values in the leaf level, storing one copy of the key with a list of matching row pointers,
which keeps indexes on low-cardinality columns much smaller than they once were.
