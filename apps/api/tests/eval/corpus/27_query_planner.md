# The PostgreSQL Query Planner

Before PostgreSQL executes a statement, the query planner, also called the optimizer, decides how to run it. SQL is
declarative, so a query states what result is wanted without prescribing how to obtain it. The planner's job is to
enumerate candidate execution plans and choose the one it expects to be cheapest. Understanding how that choice is made
explains why a query sometimes uses an index and sometimes prefers a sequential scan.

## Cost-based optimization

PostgreSQL uses a cost-based optimizer. For each candidate plan it computes an abstract cost number, and the plan with
the lowest estimated cost wins. The cost is not measured in seconds; it is a unitless estimate assembled from tunable
planner cost constants. The baseline unit is `seq_page_cost`, the cost of reading one page sequentially, set to 1.0 by
default. A random page read costs `random_page_cost`, which defaults to 4.0 because spinning disks made scattered reads
far slower than sequential ones. Per-row work is priced by `cpu_tuple_cost`, and evaluating an index entry adds
`cpu_index_tuple_cost`. On storage where random access is cheap, such as SSDs, lowering `random_page_cost` toward 1.1
often makes the planner favor index scans it would otherwise avoid.

## Statistics and selectivity

Cost estimates depend on knowing how many rows each step will produce, and that comes from table statistics. The
`ANALYZE` command samples a table and records per-column statistics into the `pg_statistic` catalog, readable through the
`pg_stats` view. These include the fraction of null values, the number of distinct values, a list of the most common
values with their frequencies, and a histogram of value distribution. From these the planner derives selectivity, the
estimated fraction of rows a predicate will pass. Multiplying selectivity by the table's row count yields the estimated
row count, or cardinality, that flows into every cost formula upstream.

Accurate statistics are the single most important input to good plans. When statistics are stale, the planner
misjudges cardinality and can pick a badly suboptimal plan, which is why autovacuum also runs analyze to keep them
current.

```sql
ANALYZE orders;

SELECT attname, n_distinct, most_common_vals
  FROM pg_stats
 WHERE tablename = 'orders';
```

## Scan and join strategies

For retrieving rows from a single table the planner weighs a sequential scan against an index scan or bitmap heap scan.
A sequential scan reads every page but does so cheaply in order, so it wins when a query returns a large fraction of the
table. An index scan wins when the predicate is selective enough that jumping to a few rows beats reading everything.

For joining tables the planner chooses among three algorithms. A nested loop join scans the outer relation and probes
the inner one for each row, which is efficient when the outer side is small and the inner side is indexed. A hash join
builds a hash table over the smaller relation and probes it once per outer row, which suits large unsorted inputs joined
on equality. A merge join sorts both inputs on the join key and walks them in lockstep, which is attractive when the
inputs are already ordered by an index.

## Reading EXPLAIN output

The `EXPLAIN` command prints the chosen plan as a tree of nodes without running it, while `EXPLAIN ANALYZE` actually
executes the query and reports real timing and row counts alongside the estimates.

```sql
EXPLAIN ANALYZE
SELECT * FROM orders WHERE customer_id = 42;
```

Each node shows an estimated startup cost and total cost, the estimated number of rows, and the estimated average row
width. The most valuable diagnostic is the gap between estimated rows and actual rows: a large divergence signals that
statistics are misleading the planner, and it is the first thing to investigate when a query is unexpectedly slow.

## Genetic optimization for large joins

Planning is itself work, and the number of possible join orders explodes factorially as more tables are added. When a
query joins more tables than the `geqo_threshold`, PostgreSQL switches from exhaustive search to the genetic query
optimizer, which explores the space of join orders heuristically rather than examining every permutation. This trades a
guarantee of the optimal plan for planning time that stays bounded, so very large multi-way joins remain feasible to
plan.
