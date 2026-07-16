# The Global Interpreter Lock in CPython

The Global Interpreter Lock, universally abbreviated as the GIL, is a mutex
inside the CPython interpreter that permits only one thread to execute Python
bytecode at a time. It is a property of CPython, the reference implementation,
rather than of the Python language itself; alternative implementations such as
Jython and IronPython have no such lock. The GIL is the single most discussed
and most misunderstood aspect of Python concurrency, and understanding exactly
what it does — and does not — protect is essential to writing correct and fast
concurrent code.

## Why the lock exists

CPython manages object lifetimes with reference counting: every object carries a
count of how many references point to it, incremented and decremented as names
are bound and dropped. If two threads adjusted the same reference count
simultaneously without coordination, the count could be corrupted, leaking
memory or freeing an object still in use. The GIL protects reference counts and
other interpreter internals from concurrent corruption, and it does so with one
coarse lock rather than thousands of fine-grained ones. This design keeps the
single-threaded interpreter fast and makes writing C extensions dramatically
simpler, because extension authors need not guard every object access with their
own locks.

## What the GIL does and does not do

A common misconception is that the GIL makes Python code automatically
thread-safe. It does not. The lock guarantees that a single bytecode operation
runs without interruption, but a statement as ordinary as `x += 1` compiles to
several bytecodes, and the interpreter can release the GIL between any two of
them. Consequently a race condition is still possible whenever multiple threads
perform read-modify-write sequences on shared data, which is why application
code still needs its own locks. The GIL protects the interpreter's internals,
not your program's invariants.

## How the lock is released and reacquired

The GIL is not held for the entire lifetime of a thread. In modern CPython the
running thread is asked to drop the lock after a time interval, by default about
five milliseconds, so that other threads get a turn; this is governed by
`sys.setswitchinterval`. Just as importantly, a thread releases the GIL whenever
it makes a blocking I/O call — reading a socket, waiting on disk, sleeping — so
other threads can run while it waits. Well-behaved C extensions do the same,
wrapping long computations in `Py_BEGIN_ALLOW_THREADS` and
`Py_END_ALLOW_THREADS` macros to let Python threads proceed while native code
runs.

```python
import sys

# Print and then shorten the interpreter's thread-switch interval.
print(sys.getswitchinterval())   # 0.005 seconds by default
sys.setswitchinterval(0.001)     # ask threads to yield more often
```

## Consequences for concurrency

The practical upshot is stark. Because only one thread executes bytecode at a
time, CPU-bound Python code cannot be sped up by adding threads; two threads
crunching numbers share one core's worth of interpreter time and add contention
on top. This is precisely why the multiprocessing module exists: separate
processes each carry their own interpreter and their own GIL, so they achieve
genuine parallelism across cores. Threads remain valuable for I/O-bound work,
where the lock is released during the wait and concurrency comes for free.

```python
# CPU-bound: threads do NOT help because of the GIL.
# Two threads summing large ranges finish no faster than one.
def count(n: int) -> int:
    total = 0
    for i in range(n):
        total += i
    return total
```

## Living without the GIL

Several escape hatches exist. Extension code written in C, Cython, or via
libraries like NumPy performs its heavy loops outside the interpreter and
releases the lock, so those computations do run in parallel. The multiprocessing
module and `ProcessPoolExecutor` route around the lock entirely by using
processes. And the language itself is changing: PEP 703 describes an
experimental free-threaded build of CPython, first shipped as an option in Python
3.13, that removes the global interpreter lock and makes reference counting
thread-safe through other mechanisms. The free-threaded build lets Python threads
run bytecode in parallel, at some cost to single-threaded performance, and is
expected to mature over several releases before becoming the default.

## Summary of the mental model

Hold three facts in mind. First, the GIL allows only one thread to run Python
bytecode at once, which caps threaded CPU throughput at a single core. Second,
the lock is released on I/O and on a timer, so threads still interleave usefully
for waiting workloads. Third, the GIL protects the interpreter, not your data,
so shared mutable state still demands explicit synchronization. Everything else
about Python concurrency — when to choose threads, processes, or asyncio —
follows from these three facts.
