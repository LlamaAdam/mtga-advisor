"""
Probability math for the MTGA game advisor.

All functions use only the stdlib math.comb (Python ≥ 3.8).
"""
from __future__ import annotations
from math import comb


def hypergeometric_pmf(k: int, N: int, K: int, n: int) -> float:
    """Probability of exactly k successes when drawing n cards from a deck of N
    containing K successes (hypergeometric distribution).

    Args:
        k: desired number of successes drawn
        N: total population (deck size)
        K: successes in population (e.g. number of lands)
        n: sample size (cards drawn)

    Returns:
        P(X = k)
    """
    lo = max(0, n + K - N)
    hi = min(n, K)
    if k < lo or k > hi or N < 0 or K < 0 or n < 0:
        return 0.0
    if N == 0:
        return 1.0 if k == 0 else 0.0
    try:
        return comb(K, k) * comb(N - K, n - k) / comb(N, n)
    except (ValueError, ZeroDivisionError):
        return 0.0


def hypergeometric_cdf_at_least(k: int, N: int, K: int, n: int) -> float:
    """P(X >= k): probability of drawing at least k successes.

    Args:
        k: minimum desired successes
        N: population size
        K: successes in population
        n: cards drawn

    Returns:
        P(X >= k)
    """
    hi = min(n, K)
    return sum(hypergeometric_pmf(i, N, K, n) for i in range(k, hi + 1))


def prob_draw_at_least_one(library_size: int, copies_remaining: int, draws: int) -> float:
    """P(drawing >= 1 copy of a card in the next `draws` cards from the library).

    Args:
        library_size: number of cards remaining in library
        copies_remaining: copies of the target card still in library
        draws: number of upcoming draws

    Returns:
        probability in [0.0, 1.0]
    """
    if library_size <= 0 or copies_remaining <= 0 or draws <= 0:
        return 0.0
    actual_draws = min(draws, library_size)
    return hypergeometric_cdf_at_least(1, library_size, copies_remaining, actual_draws)
