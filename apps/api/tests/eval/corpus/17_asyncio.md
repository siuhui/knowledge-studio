# Asyncio: Cooperative Concurrency in Python

Asyncio is Python's standard library for writing single-threaded concurrent
code using coroutines. It targets I/O-bound workloads such as network servers,
database clients, and web scrapers, where a program spends most of its time
waiting for external systems rather than burning CPU cycles. Instead of
dedicating an operating-system thread to each connection, asyncio multiplexes
thousands of in-flight operations onto one thread by suspending a coroutine
whenever it would block and resuming it once its data is ready.

## The event loop

At the center of every asyncio program sits the event loop. The asyncio event
loop is the scheduler that runs coroutines, dispatches callbacks, and watches
file descriptors and sockets for readiness. Only one loop runs per thread at a
time, and only one piece of Python code executes at any given moment, so there
is no need for locks to protect ordinary variables between coroutines. The loop
maintains a queue of ready callbacks and a collection of pending timers; on each
iteration it drains the ready queue, polls the operating system for I/O events
via a selector such as `epoll` or `kqueue`, and schedules the callbacks
associated with any sockets that became readable or writable.

The modern entry point is `asyncio.run`, which creates a fresh loop, runs a
top-level coroutine to completion, and then closes the loop and cancels leftover
tasks. Because the loop is cooperative, a single coroutine that performs a long
synchronous computation will stall every other coroutine until it yields
control. This is the fundamental discipline of asyncio: never block the thread.

```python
import asyncio

async def fetch(name: str, delay: float) -> str:
    await asyncio.sleep(delay)   # suspends without blocking the loop
    return f"{name} done"

async def main() -> None:
    results = await asyncio.gather(
        fetch("a", 0.3),
        fetch("b", 0.1),
    )
    print(results)

asyncio.run(main())
```

## Coroutines and await

A coroutine is defined with `async def` and, when called, returns a coroutine
object that does nothing until it is awaited or scheduled on the loop. The
`await` keyword is the mechanism that suspends the current coroutine and hands
control back to the event loop. When you await a coroutine, execution pauses
until the awaited operation completes and its value becomes available, at which
point the loop resumes the caller exactly where it left off. Only objects that
implement the awaitable protocol — coroutines, Tasks, and Futures — can appear
to the right of `await`.

The suspension is what makes concurrency possible. While one coroutine is
parked on `await asyncio.sleep` or waiting on a socket, the loop is free to run
other ready coroutines. Nothing runs truly in parallel; the illusion of
simultaneity comes from rapidly interleaving many coroutines that each spend
most of their life waiting. This is why people say to await a coroutine is to
voluntarily yield the processor to peers.

## Tasks and scheduling

Awaiting coroutines one after another runs them sequentially. To run coroutines
concurrently you wrap each in a Task, which schedules the coroutine to run on
the loop as soon as possible. `asyncio.create_task` takes a coroutine and
returns a Task object that begins executing at the next opportunity, letting the
current coroutine continue and later await the result. A Task is a subclass of
Future that drives a coroutine to completion, capturing its return value or
exception.

The helper `asyncio.gather` collects several awaitables, schedules them
together, and returns their results in the original order once all have
finished. For bounded fan-out you can group tasks with `asyncio.TaskGroup`,
introduced in Python 3.11, which cancels its siblings if any member raises and
guarantees that no task is silently abandoned. Cancellation is cooperative as
well: calling `task.cancel()` arranges for a `CancelledError` to be raised
inside the coroutine at its next suspension point, giving it a chance to clean
up in a `finally` block.

## Blocking calls and executors

Because a single blocking call freezes the whole loop, CPU-heavy work and legacy
synchronous libraries must be pushed off the event loop thread. The bridge is
`loop.run_in_executor`, which submits a function to a thread pool or process
pool and returns an awaitable. To offload blocking work you await the result of
`run_in_executor`, so the loop keeps servicing other coroutines while a worker
thread handles the slow call. The convenience wrapper `asyncio.to_thread`, added
in Python 3.9, does the same thing with a cleaner signature for the common
thread-pool case.

```python
import asyncio

def parse_big_file(path: str) -> int:
    with open(path, "rb") as f:
        return len(f.read())      # blocking, CPU + disk bound

async def main() -> None:
    size = await asyncio.to_thread(parse_big_file, "data.bin")
    print(size)
```

## Synchronization primitives

Even though coroutines never preempt one another, they still need coordination
when they share state across suspension points. Asyncio provides `Lock`,
`Event`, `Semaphore`, and `Queue` that mirror the threading API but are awaitable
rather than blocking. An `asyncio.Semaphore` is commonly used to cap the number
of concurrent outbound requests, and an `asyncio.Queue` decouples producers from
consumers within the same loop. These primitives suspend the coroutine rather
than the thread, so acquiring an asyncio lock never stalls the scheduler.

## When to reach for asyncio

Asyncio shines when a program juggles many slow connections at once — an HTTP
proxy, a chat server, a crawler fetching thousands of pages. It is a poor fit
for CPU-bound number crunching, where the work never yields and the single
thread becomes the bottleneck; that territory belongs to multiprocessing.
Mixing paradigms is common in practice: an asyncio server that occasionally
needs heavy computation delegates that computation to a process pool while the
loop stays responsive to new connections.
