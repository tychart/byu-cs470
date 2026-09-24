"""Monte-Carlo coin flips, parallelized with numba's `prange`.

Same experiment as st_petersburg.py (count heads before the first tails),
but split into BLOCKS independent chunks that numba spreads across every
core.  Run with:  uv run --with numpy --with numba python st_petersburg_parallel.py
"""

import time

import numpy as np
from numba import njit, prange

# GAMES = 1_000_000_0000
GAMES = 1_000_000_000_000
BLOCKS = 512  # chunks; one per parallel task, splitty across cores


@njit(parallel=True, cache=True)
def simulate(blocks, per_block):
    totals = np.zeros(blocks, dtype=np.int64)
    maxes = np.zeros(blocks, dtype=np.int64)
    mins = np.full(blocks, np.int64(1 << 30), dtype=np.int64)

    for b in prange(blocks):  # <- the only parallel bit
        total = 0
        hi = 0
        lo = 1 << 30
        for _ in range(per_block):
            heads = 0
            while np.random.random() > 0.5:  # heads, keep flipping
                heads += 1
            total += heads
            hi = max(hi, heads)
            lo = min(lo, heads)
        totals[b] = total
        maxes[b] = hi
        mins[b] = lo

    return totals.sum(), maxes.max(), mins.min()


if __name__ == "__main__":
    per_block = GAMES // BLOCKS
    simulate(2, 10)  # warm up / compile once, outside the timer

    start = time.perf_counter()
    total, most, fewest = simulate(BLOCKS, per_block)
    elapsed = time.perf_counter() - start

    n = BLOCKS * per_block

    print(f"Total games: {GAMES:,.0f}")
    print(f"Max flips until tails: {most} = ${ (2**most):,.2f}")
    print(f"Min flips until tails: {fewest} = ${ (2**fewest):,.2f}")
    print(f"Average flips until tails: {(total / n):.4f} = ${ (2**(total / n)):,.2f}")
    print(f"({n / elapsed:,.0f} games/s in {elapsed:.2f}s)")
