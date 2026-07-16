# VACUUM and Dead Tuples in PostgreSQL

PostgreSQL never overwrites a row in place when you update or delete it. Because of its multiversion concurrency
control design, an update writes a brand-new version of the row and leaves the old version behind, and a delete
simply marks the existing version as no longer valid. These leftover versions are dead tuples, and although they
are invisible to new queries, they still occupy space in the table's pages. VACUUM is the maintenance process that
reclaims that space and keeps the database from growing without bound.

## Why dead tuples accumulate

Under MVCC every transaction sees a consistent snapshot of the database as it existed when the transaction began.
To make that possible, a row version cannot be removed the instant it is superseded, because an older transaction
might still need to read it. Each tuple therefore carries the transaction IDs that created and expired it, and a
version becomes truly dead only once no active snapshot could still see it. Until then the dead tuple must remain
on disk. A table that receives heavy updates or deletes accumulates these dead versions quickly, and left
unchecked they cause table bloat, where the on-disk size grows far beyond the volume of live data it holds.

Bloat is not merely wasted disk. Because scans read pages, a bloated table forces every sequential scan and every
index scan to wade through pages padded with dead tuples, so query performance degrades in proportion to the
bloat. Reclaiming the space is therefore a performance concern, not only a storage one.

## What VACUUM does

A plain `VACUUM` scans the table, identifies tuples that no snapshot can see anymore, and marks their space as free
for reuse by future inserts and updates into the same table. Crucially, an ordinary vacuum does not return that
space to the operating system; the file stays the same size, but the freed slots inside it are recycled. This is
usually what you want, because reusing space in place avoids the churn of shrinking and regrowing files.

```sql
VACUUM (VERBOSE, ANALYZE) orders;
```

VACUUM also performs two other essential jobs. It updates the visibility map, a compact per-page bitmap that marks
pages on which every tuple is visible to all transactions, which in turn allows index-only scans and lets later
vacuums skip pages that have not changed. And it prevents transaction ID wraparound: because transaction IDs are a
finite 32-bit counter, very old tuples must periodically be frozen, marked as unconditionally visible, so that the
counter can be reused safely. A table that is never vacuumed risks a wraparound that would force the database into
a protective shutdown.

## VACUUM versus VACUUM FULL

When a table has become severely bloated and you genuinely need to shrink the file on disk, `VACUUM FULL` rewrites
the entire table into a fresh file containing only the live tuples and returns the freed space to the operating
system. The catch is that it takes an exclusive lock on the table for the whole operation, blocking all reads and
writes, and it needs enough spare disk to hold a second copy while it works. A plain vacuum, by contrast, runs
concurrently with normal traffic and only takes a lightweight lock. The practical guidance is to rely on ordinary
vacuuming for routine maintenance and reserve the full rewrite for exceptional recovery from heavy bloat.

## Autovacuum

Rather than requiring an administrator to schedule cleanup by hand, PostgreSQL ships with an autovacuum daemon that
watches tables and launches vacuum and analyze runs automatically. It triggers a vacuum on a table once the number
of dead tuples crosses a threshold expressed as a base value plus a fraction of the table's size, governed by
`autovacuum_vacuum_threshold` and `autovacuum_vacuum_scale_factor`. The default scale factor is twenty percent, so
by default autovacuum wakes up after roughly a fifth of the rows have been updated or deleted, though on a large
and busy table that percentage is often lowered so cleanup runs more frequently and bloat is held in check.

```sql
ALTER TABLE events SET (autovacuum_vacuum_scale_factor = 0.05);
```

Autovacuum does double duty: the same background runs that remove dead tuples also refresh the planner statistics
through an accompanying analyze, so autovacuum quietly keeps both the physical layout and the optimizer's estimates
in good shape. Tuning it, rather than disabling it, is almost always the right response when bloat or stale
statistics start to hurt.
