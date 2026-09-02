import itertools
import math
from decimal import Decimal

import pytest

from rcc_refcert.examples import (
    gamma5_explicit_word_average_error,
    gamma5_reference_balance_error,
    natural_c_gt_one_interval,
)
from rcc_refcert.prefix import elias_gamma_nonnegative
from rcc_refcert.rank_encoding import (
    decode_word,
    encode_word,
    occupancy_factor,
    partial_program_kraft_mass,
    payload_length,
)


def test_elias_headers_are_prefix_free_for_initial_lengths() -> None:
    headers = [elias_gamma_nonnegative(length) for length in range(64)]
    for i, left in enumerate(headers):
        for j, right in enumerate(headers):
            if i != j:
                assert not right.startswith(left)


def test_non_dyadic_whole_word_codes_are_unique() -> None:
    for length in range(5):
        codes = {
            encode_word(word, 5) for word in itertools.product(range(5), repeat=length)
        }
        assert len(codes) == 5**length
        expected_payload = 0 if length == 0 else math.ceil(length * math.log2(5))
        assert all(len(code) >= expected_payload for code in codes)
        assert 0.5 < occupancy_factor(5, length) <= 1.0


def test_whole_word_decoder_roundtrips_and_domain_is_prefix_free() -> None:
    for gamma in (2, 3, 5, 10):
        codes = []
        for length in range(5):
            for word in itertools.product(range(gamma), repeat=length):
                code = encode_word(word, gamma)
                assert decode_word(code, gamma) == word
                codes.append(code)
        for index, left in enumerate(codes):
            for other_index, right in enumerate(codes):
                if index != other_index:
                    assert not right.startswith(left)


def test_decoder_rejects_unused_rank_and_nonexact_input() -> None:
    # L=1, Gamma=3 has a two-bit rank payload; binary rank 3 is unused.
    with pytest.raises(ValueError, match="unused rank"):
        decode_word("01011", 3)
    valid = encode_word((1, 2), 3)
    with pytest.raises(ValueError, match="too short|expected exactly"):
        decode_word(valid[:-1], 3)
    with pytest.raises(ValueError, match="expected exactly"):
        decode_word(valid + "0", 3)


def test_payload_length_is_exact_without_floating_logarithms() -> None:
    for gamma, length in ((3, 127), (5, 83), (17, 41)):
        assert payload_length(gamma, length) == (gamma**length - 1).bit_length()
    with pytest.raises(ValueError, match="integer"):
        payload_length(5, True)


def test_gamma5_reference_balance_and_word_averages() -> None:
    assert gamma5_reference_balance_error() < 1e-12
    for length in range(1, 6):
        assert gamma5_explicit_word_average_error(length) < 1e-12
    assert partial_program_kraft_mass(5, 20) <= 1.0


def test_natural_c_gt_one_value() -> None:
    lower, upper = natural_c_gt_one_interval(100)
    rounded = Decimal("1.398804068566733")
    quantum = Decimal("1e-15")
    assert lower.quantize(quantum) == rounded
    assert upper.quantize(quantum) == rounded
    assert Decimal(0) < upper - lower < Decimal("1e-29")
