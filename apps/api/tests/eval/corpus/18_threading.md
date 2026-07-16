# Threading: Shared-Memory Concurrency in Python

The `threading` module lets a program run multiple threads of execution within
a single process. All threads share the same address space, so they can read and
write the same objects directly without any serialization or message passing.
This shared-memory model makes communication cheap but introduces the classic
hazards of concurrent programming: race conditions, deadlocks, and data
corruption when two threads touch the same mutable state at the same time.
Threads in CPython are real operating-system threads, scheduled by the kernel,
but their execution of Python bytecode is serialized by the interpreter lock.

## Creating and joining threads

A thread is created by instantiating `threading.Thread` with a target callable,
then calling `start` to begin execution in the background. The parent can later
call `join` to wait until the thread finishes. A thread marked as a daemon does
not keep the process alive; the interpreter exits once only daemon threads
remain, abandoning their work. Non-daemon threads, by contrast, must complete or
be joined before the program can terminate cleanly.

```python
import threading

counter = 0
lock = threading.Lock()

def increment(n: int) -> None:
    global counter
    for _ in range(n):
        with lock:            # only one thread mutates counter at a time
            counter += 1

threads = [threading.Thread(target=increment, args=(100_000,)) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(counter)   # deterministically 400000 thanks to the lock
```

## Race conditions and the need for locks

Consider four threads each incrementing a shared integer one hundred thousand
times. The operation `counter += 1` looks atomic but actually compiles to a
read, an add, and a write. If the interpreter switches threads between the read
and the write, one update is lost, and the final total falls short of the
expected value. A race condition occurs when the result of a program depends on
the unpredictable interleaving of threads. Because a thread can be suspended
between two bytecodes, any read-modify-write sequence on shared data is unsafe
without protection.

## Locks and mutual exclusion

The primary tool for correctness is the mutex, exposed as `threading.Lock`. A
lock has two states, locked and unlocked, and only one thread may hold it at a
time. A thread must acquire the lock before touching the guarded data and
release it afterward; using the lock as a context manager guarantees release
even if an exception is raised. The critical section protected by a thread lock
must be kept as small as possible, because every thread that wants the lock
waits, eroding the concurrency you were trying to gain.

When the same thread needs to acquire a lock it already holds — for example in
recursive code — a plain `Lock` deadlocks, and you must use `threading.RLock`,
the reentrant lock, which counts how many times its owning thread has acquired
it. For signalling between threads, `threading.Event` offers a simple flag that
one thread sets and others wait on, while `threading.Condition` supports the
wait/notify pattern for producer–consumer coordination.

## Deadlock and lock ordering

Locks solve one problem and create another. Deadlock arises when two threads
each hold a lock the other needs and neither will release, so both block
forever. The classic remedy is to impose a global lock ordering: every thread
acquires multiple locks in the same fixed sequence, which makes a cyclic wait
impossible. Keeping the number of locks small and never calling unknown code
while holding a lock are practical defenses against subtle deadlocks.

## Communicating with queues

Rather than sharing raw state guarded by locks, many programs prefer message
passing through `queue.Queue`, a thread-safe FIFO with internal locking already
handled. Worker threads pull items off the queue, process them, and the main
thread joins the queue once all tasks are marked done. This pattern eliminates
most explicit locking from application code and is the backbone of the classic
thread-pool design.

```python
import queue
import threading

work: "queue.Queue[int]" = queue.Queue()

def worker() -> None:
    while True:
        item = work.get()
        if item is None:
            break
        # process item ...
        work.task_done()

t = threading.Thread(target=worker, daemon=True)
t.start()
for i in range(10):
    work.put(i)
work.join()
```

## When threads help and when they do not

Because CPython serializes bytecode execution, threads do not speed up pure
Python computation; two compute-bound threads run no faster than one and often
slower due to lock contention and context switching. Threading pays off for
I/O-bound work, where a thread waiting on a socket or a disk read releases the
interpreter lock and lets another thread run. Blocking C extensions that release
the lock during their work — many database drivers and compression libraries do
— also benefit. For CPU-bound parallelism you need separate processes instead,
each with its own interpreter and its own memory. The rule of thumb is simple:
threads for waiting, processes for computing.
