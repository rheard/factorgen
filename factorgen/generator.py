# TODO: Compile with mypyc
#   Currently this compiles fine, but as soon as I call __next__ and it gets to the self.heap,
#   access violation, segmentation fault....
#   Idk if I'm doing something wrong or mypyc is, but I'm tired of playing with it.
#       Even not compiled this is so much faster than factoring with PARI

import heapq
import os
import pickle

from functools import lru_cache
from pathlib import Path
from typing import Callable

import sympy

RawFactors = tuple[tuple[int, int], ...]
HeapItem = tuple[int, bool, int, int, RawFactors]


def _bump_last_exponent(n_factors: RawFactors) -> RawFactors:
    """Increment the exponent of the last prime in n_factors by 1"""
    p, e = n_factors[-1]
    return *n_factors[:-1], (p, e + 1)


def _atomic_write(path: Path, data: bytes) -> None:
    """Atomic write to avoid corrupting checkpoint files"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with Path(tmp).open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    Path(tmp).replace(path)


class Factorizations:
    """
    Iterator over (i, factorization(i)) for i < max_i.

    Notes:
    - Iteration is in strictly increasing i.
    - No duplicates.
    - Save/load preserves exact continuation point.
    """
    max_i: int
    min_i: int = 0
    nextprime: Callable[[int], int]
    heap: list[HeapItem]
    yielded: int

    def __init__(self, max_i: int, min_i: int = 0, nextprime: Callable[[int], int] | None = None):
        """Setup the Factorizations state from scratch"""
        if nextprime is None:
            nextprime = lru_cache(maxsize=200_000)(sympy.nextprime)

        self.max_i: int = max_i
        self.min_i: int = min_i
        self.nextprime = nextprime

        # Heap holds both nodes and stream cursors.
        self.heap = []
        heapq.heappush(self.heap, (1, False, 1, 0, ()))  # Start with n = 1 (empty factorization). This yields i = 2.

        # Count of yielded results (handy for checkpoint cadence)
        self.yielded: int = 0

    def __iter__(self) -> 'Factorizations':
        return self

    def save(self, path: str | Path) -> None:
        """Save generator state (heap + counters + current max_i) to a pickle file."""
        p = Path(path)
        state = {
            "version": 1,
            "max_i": self.max_i,
            "min_i": self.min_i,
            "yielded": self.yielded,
            "heap": self.heap,
        }
        blob = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
        _atomic_write(p, blob)

    @classmethod
    def load(cls,
             path: str | Path,
             max_i: int | None = None,
             min_i: int | None = None,
             nextprime: Callable[[int], int] | None = None) -> 'Factorizations':
        """Load generator state from pickle. If max_i is provided, overrides the saved bound."""
        if nextprime is None:
            nextprime = lru_cache(maxsize=200_000)(sympy.nextprime)

        p = Path(path)
        with Path(p).open("rb") as f:
            state = pickle.load(f)

        obj = cls(max_i=int(max_i or state["max_i"]),
                  min_i=int(min_i or state["min_i"]),
                  nextprime=nextprime)

        obj.yielded = int(state["yielded"])
        obj.heap = state["heap"]
        return obj

    def __next__(self) -> tuple[int, dict]:
        heap = self.heap
        max_n = self.max_i

        while True:
            if not heap:
                raise StopIteration

            entry = heapq.heappop(heap)
            n, should_stream = entry[:2]

            # Stop cleanly at the bound, *without losing* the next entry.
            if n > max_n:
                heapq.heappush(heap, entry)
                raise StopIteration

            n_factors: RawFactors
            if should_stream:
                base_n = entry[2]
                p = entry[3]
                base_factors: RawFactors = entry[4]

                # Advance the stream cursor for this base and reinsert it.
                p2 = self.nextprime(p)
                heapq.heappush(heap, (base_n * p2, True, base_n, p2, base_factors))

                # The popped candidate is a real n-node we should yield/expand.
                last_prime = p
                n_factors = *base_factors, (p, 1)

            else:
                last_prime = entry[2]
                n_factors = entry[4]

            # Expand this n-node:
            # 1) Power child: multiply by last prime again (increase exponent),
            #    only if we actually have a last prime (i.e., n != 1).
            if last_prime != 1:
                n2 = n * last_prime
                nf2 = _bump_last_exponent(n_factors)
                heapq.heappush(heap, (n2, False, last_prime, 0, nf2))

            # 2) Start (or continue) the "append larger primes" stream for this n.
            #    Next distinct prime must be > last_prime (except last_prime==1).
            np = self.nextprime(last_prime)
            heapq.heappush(heap, (n * np, True, n, np, n_factors))

            if n < self.min_i:
                continue

            return n, dict(n_factors)

        raise StopIteration
