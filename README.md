# factorgen

`factorgen` is a fast, resumable generator that enumerates integers together with their prime factorizations without factoring the integers.

Instead of calling `factorint(n)` for each `n`, `factorgen` **constructs** each next value by 
    multiplying allowed primes in a canonical order, carrying the factorization along as it goes. 
    This gives you **complete coverage**, **strictly increasing output**, 
    and **no duplicates** for the chosen factor set. 

## Features

* **Enumerate factorizations without factoring**: yields `(n, {prime: exponent, ...})`
* **Strictly increasing** `n` (deterministic order), **no repeats**
* **Configurable factor base** via a `nextprime` callback (e.g., “only primes $\equiv 1 \bmod 4$”)
* **Checkpointing**: `save()` / `load()` using pickle
* **Extendable bounds**: finish up to `N`, save, then reload and continue up to `M > N` without repeating work

## Installation

```bash
pip install factorgen
```

Dependencies:

* Python 3.9+
* `sympy` (used by default for prime stepping) 

## Quickstart

Enumerate all integers `2..limit` with their prime factorizations:

```python
from factorgen import Factorizations

limit = 20_000
gen = Factorizations(limit, min_i=2)

for n, factors in gen:
    # factors is a dict: {prime: exponent}
    # e.g. 12 -> {2: 2, 3: 1}
    ...
```

## Examples

### Using cyPARI for faster prime stepping

The `Factorizations` class accepts a `nextprime` argument for customization of the prime set.
    When given a prime (or any number) it should return the next relevant prime.
    This can also be used to provide a faster backend, for example by use of cyPARI.

```python
from functools import lru_cache
from cypari import pari
from factorgen import Factorizations

@lru_cache(maxsize=2_000_000)
def nextprime(p: int) -> int:
    return int(pari(p).nextprime())

limit = 20_000
gen = Factorizations(limit, min_i=2, nextprime=nextprime)

for n, factors in gen:
    # factors is a dict: {prime: exponent}
    # e.g. 12 -> {2: 2, 3: 1}
    ...
```


### Constraining the primes (example: only primes $\equiv 1 \bmod 4$)

As mentioned, you can restrict the prime set using the `nextprime` argument to numbers whose prime factors come 
    from a subset by returning the **next allowed prime strictly greater than `p`**.

Example: only primes $p$ where $p \bmod 4 \equiv 1$:

```python
from sympy import nextprime
from factorgen import Factorizations

def next_prime_1mod4(p: int) -> int:
    q = int(nextprime(p))
    while q % 4 != 1:
        q = int(nextprime(q))
    return q

limit = 20_000
gen = Factorizations(limit, min_i=2, nextprime=next_prime_1mod4)

for n, factors in gen:
    # Every yielded n has only primes ≡ 1 (mod 4) in its factorization
    assert all(p % 4 == 1 for p in factors)
```

### Checkpoint / Resume (and extend the limit)

Long runs can be checkpointed:

```python
from factorgen import Factorizations

gen = Factorizations(10_000_000, min_i=2)

for idx, (n, factors) in enumerate(gen, start=1):
    ...
    
gen.save("state.pkl")
```

Resume later (optionally extending the limit):

```python
from factorgen import Factorizations

gen = Factorizations.load("state.pkl", max_i=20_000_000)

for n, factors in gen:
    ...
```

> **Important:** if you were using a custom `nextprime=...`, pass the same function to `load(...)` as well, 
>   so the enumeration continues under the same constraints.

## API

### `Factorizations(max_i: int, min_i: int = 0, nextprime: callable | None = None)`

* `max_i`: inclusive upper bound on yielded integers, required.
* `min_i`: lower bound filter (values smaller than `min_i` are skipped)
* `nextprime(p)`: callback returning the next allowed prime > `p`

  * If omitted, a cached wrapper around `sympy.nextprime` is used by default

### Methods

* `save(path)`: checkpoint internal frontier state to a pickle file
* `load(path, max_i=None, nextprime=None)`: restore a checkpoint and optionally override `max_i`
* Attribute: `yielded` (count of yielded values so far) 

## Background (terminology)

Mathematically, this is constructive enumeration of integers over a factor base (often discussed in terms of *smooth-number* generation). 
    `factorgen` focuses on the practical side: **enumerating factorizations without factoring**, 
    with a resumable frontier and a customizable “allowed prime” stream.
