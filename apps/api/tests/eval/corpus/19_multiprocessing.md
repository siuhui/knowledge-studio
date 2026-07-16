# Multiprocessing: True Parallelism Through Separate Processes

The `multiprocessing` module sidesteps the interpreter lock by running code in
separate operating-system processes instead of threads. Each process owns a
private Python interpreter and a private memory space, so several processes can
execute Python bytecode on different CPU cores at the same instant. This is the
canonical answer to CPU-bound work in Python — image processing, numerical
simulation, data crunching — where threading offers no speedup because the
interpreter lock serializes bytecode within a single process.

## Processes versus threads

The trade-off is the mirror image of threading. Threads share memory and
communicate for free but cannot run Python code truly in parallel; processes run
in parallel but cannot share ordinary objects. Because a child process does not
share the parent's address space, any data exchanged between them must be
serialized, shipped across a pipe or socket, and reconstructed on the other
side. Creating a process is also heavier than creating a thread, and the fixed
startup cost means multiprocessing pays off only when the work per task clearly
outweighs the overhead of spawning and communication.

```python
from multiprocessing import Process

def square(n: int) -> None:
    print(n * n)

if __name__ == "__main__":
    procs = [Process(target=square, args=(i,)) for i in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
```

The `if __name__ == "__main__"` guard is not optional on Windows and macOS.
Under the spawn start method the child re-imports the main module, and without
the guard that re-import would recursively launch new processes.

## Start methods: fork, spawn, forkserver

A process is created through one of three start methods. With fork, available on
Unix, the child is a copy of the parent created by the operating system's
`fork` call, inheriting its memory cheaply through copy-on-write. With spawn, the
default on Windows and on macOS since Python 3.8, a brand-new interpreter is
launched and only the resources it needs are inherited, which is slower but
avoids the subtle bugs fork inherits from threads and locks held at fork time.
The forkserver method starts a dedicated server process that forks clean workers
on demand. You choose one explicitly with `multiprocessing.set_start_method`.

## Pickling and its limits

Serialization is where beginners stumble. Everything sent to a child process —
the target function, its arguments, and the values returned — must be picklable,
because multiprocessing uses pickle to serialize objects before sending them
between processes. That rules out lambdas, locally defined closures, open file
handles, database connections, and sockets. When you see a `PicklingError`, the
usual cause is passing one of these unpicklable objects across the process
boundary. Defining worker functions at module top level, so pickle can locate
them by qualified name, is the standard fix.

## Process pools

Managing processes by hand is tedious, so the module provides `Pool`, a fixed
set of worker processes that consume tasks from a queue. A multiprocessing pool
distributes work across a fixed set of worker processes and gathers the results
back to the parent, hiding the plumbing of dispatch and collection. The `map`
method splits an iterable into chunks and applies a function to each item in
parallel, blocking until every result is ready; `imap` streams results lazily,
and `apply_async` submits a single call and returns immediately with a handle you
poll later.

```python
from multiprocessing import Pool

def heavy(x: int) -> int:
    return sum(i * i for i in range(x))

if __name__ == "__main__":
    with Pool(processes=4) as pool:
        results = pool.map(heavy, [10_000, 20_000, 30_000, 40_000])
    print(results)
```

## Sharing state between processes

Since processes do not share memory, exchanging data needs explicit channels. A
`multiprocessing.Queue` is a process-safe FIFO that pickles items through an
internal pipe, and `Pipe` gives a bidirectional connection between exactly two
endpoints. For shared numeric or array data there are `Value` and `Array`, which
live in shared memory and are guarded by an optional lock. A `Manager` goes
further, hosting ordinary Python objects — dicts, lists — in a server process
and handing out proxies, at the cost of a round trip for every access. Python
3.8 added `shared_memory`, which exposes a raw block of memory that multiple
processes can map directly, avoiding the copy entirely for large arrays.

## The concurrent.futures bridge

For most applications the higher-level `concurrent.futures.ProcessPoolExecutor`
is preferable to raw `Pool`, because it presents the same executor interface as
its thread-based sibling. Swapping `ThreadPoolExecutor` for
`ProcessPoolExecutor` changes only one line while moving work from threads to
processes, letting you match the executor to the workload — threads for I/O,
processes for computation — without rewriting the surrounding code. The executor
returns `Future` objects whose results you gather as they complete.

## Choosing multiprocessing

Reach for multiprocessing when the work is genuinely CPU-bound and each unit of
work is large enough to amortize the serialization and startup cost. If the
tasks are tiny or the arguments are enormous, the time spent pickling and
copying can dwarf the computation and leave you slower than a plain loop. And if
the workload is dominated by waiting on the network or disk, threads or asyncio
will serve better, because those tools were built for I/O rather than raw
compute.
