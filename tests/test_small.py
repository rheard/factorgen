from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from sympy import (
    factorint as sympy_factorint,
    nextprime as sympy_nextprime,
)

from factorgen import Factorizations

if TYPE_CHECKING:
    from pathlib import Path

try:
    from cypari import pari

    CYPARI = True
except ImportError:
    pari = None
    CYPARI = False


@lru_cache(maxsize=200_000)
def factorint(n: int) -> dict[int, int]:
    """A wrapper for sympy's factorint unless pari is available"""
    if CYPARI:
        # PARI returns a matrix: [p1 e1; p2 e2; ...]
        f = pari(n).factor()

        # Convert to Python dict[int, int]
        return {
            int(p): int(e) for p, e in zip(f[0], f[1])
        }

    return sympy_factorint(n)


def test_small_coverage():
    """Simply validate that all numbers are returned and their factorizations are correct"""
    limit = 20000

    gen = Factorizations(limit, min_i=2)
    for i, (n, n_fact) in enumerate(gen, start=2):
        assert i == n
        assert factorint(i) == n_fact


@lru_cache(maxsize=200_000)
def _next_prime_1mod4(p: int) -> int:
    """Return the smallest prime q > p with q % 4 == 1, using sympy.nextprime"""
    q = int(nextprime(p))
    while (q & 3) != 1:  # q % 4 != 1
        q = int(nextprime(q))
    return q


def nextprime(n: int) -> int:
    """A wrapper for sympy's nextprime unless pari is available"""
    if CYPARI:
        return int(pari(n + 1).nextprime())

    return sympy_nextprime(n)


def test_limited():
    """
    Validate we can limit the primes that are used to a subset of the primes,
        and only get numbers with those factors.
    """
    limit = 20000

    gen = Factorizations(limit, min_i=2, nextprime=_next_prime_1mod4)
    i = 2

    for n, n_fact in gen:
        while i < n:
            i_fact = factorint(i)
            assert any(p % 4 in {2, 3} for p in i_fact)
            i += 1

        i_fact = factorint(i)
        assert i == n
        assert i_fact == n_fact
        assert not any(p % 4 in {2, 3} for p in i_fact)
        i += 1


def test_bounded_nextprime():
    """Validate nextprime can return None to indicate a bounded list of factors."""
    limit = 20000
    primes = (2, 3, 5)

    def bounded_nextprime(n: int) -> int | None:
        return next((p for p in primes if p > n), None)

    expected = [
        (i, factorint(i))
        for i in range(2, limit + 1)
        if all(p in primes for p in factorint(i))
    ]

    gen = Factorizations(limit, min_i=2, nextprime=bounded_nextprime)
    assert list(gen) == expected


def test_resume(tmp_path: Path):
    """Validate that we can save, stop and resume without missing any numbers"""
    p = tmp_path / "temp.pkl"
    first_limit = 10000

    gen = Factorizations(first_limit, min_i=2)
    i = 0
    for i, (n, n_fact) in enumerate(gen, start=2):
        assert i == n
        assert factorint(i) == n_fact

    assert i == first_limit
    gen.save(p)

    next_gen = Factorizations.load(p, 2 * first_limit)
    for i, (n, n_fact) in enumerate(next_gen, start=first_limit + 1):
        assert i == n
        assert factorint(i) == n_fact

    assert i == 2 * first_limit
