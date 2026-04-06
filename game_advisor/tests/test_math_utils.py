import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import math
import math_utils


def test_hypergeometric_pmf_known_value():
    # 17 lands in 60-card deck, 7-card opening hand — P(exactly 3 lands) ≈ 0.2173
    result = math_utils.hypergeometric_pmf(k=3, N=60, K=17, n=7)
    assert abs(result - 0.2173) < 0.001


def test_hypergeometric_pmf_zero_successes():
    result = math_utils.hypergeometric_pmf(k=0, N=60, K=17, n=7)
    assert 0.0 < result < 1.0


def test_hypergeometric_pmf_impossible_k_greater_than_K():
    result = math_utils.hypergeometric_pmf(k=18, N=60, K=17, n=7)
    assert result == 0.0


def test_hypergeometric_pmf_impossible_k_greater_than_n():
    result = math_utils.hypergeometric_pmf(k=8, N=60, K=17, n=7)
    assert result == 0.0


def test_hypergeometric_pmf_probabilities_sum_to_one():
    N, K, n = 60, 17, 7
    total = sum(math_utils.hypergeometric_pmf(k, N, K, n) for k in range(n + 1))
    assert abs(total - 1.0) < 1e-9


def test_hypergeometric_cdf_at_least_three_lands():
    # 17 lands in 60-card deck, 7-card hand — P(>=3 lands) ≈ 0.309
    result = math_utils.hypergeometric_cdf_at_least(k=3, N=60, K=17, n=7)
    assert abs(result - 0.309) < 0.005


def test_hypergeometric_cdf_at_least_zero_always_one():
    result = math_utils.hypergeometric_cdf_at_least(k=0, N=60, K=17, n=7)
    assert abs(result - 1.0) < 1e-9


def test_prob_draw_at_least_one_guaranteed():
    # More copies than draws isn't ≥1.0 possible with hyper geometric if library > copies
    # but if copies >= draws the probability is very high
    result = math_utils.prob_draw_at_least_one(library_size=5, copies_remaining=5, draws=5)
    assert abs(result - 1.0) < 1e-9


def test_prob_draw_at_least_one_zero_copies():
    result = math_utils.prob_draw_at_least_one(library_size=30, copies_remaining=0, draws=5)
    assert result == 0.0


def test_prob_draw_at_least_one_empty_library():
    result = math_utils.prob_draw_at_least_one(library_size=0, copies_remaining=4, draws=3)
    assert result == 0.0


def test_prob_draw_at_least_one_single_copy():
    # 1 copy in 30-card library, drawing 3: P = 1 - (29/30)(28/29)(27/28) = 1 - 27/30 = 0.1
    result = math_utils.prob_draw_at_least_one(library_size=30, copies_remaining=1, draws=3)
    assert abs(result - 0.1) < 0.001
