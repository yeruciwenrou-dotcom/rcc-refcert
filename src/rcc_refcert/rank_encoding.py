from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Integral

from .prefix import (
    decode_elias_gamma_nonnegative,
    elias_gamma_nonnegative,
    elias_header_length,
)
from .weights import code_weight


def _require_integer(name: str, value: int, minimum: int) -> int:
    if not isinstance(value, Integral) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{name} must be an integer at least {minimum}")
    return int(value)


def word_rank(word: Sequence[int], gamma: int) -> int:
    gamma = _require_integer("gamma", gamma, 2)
    rank = 0
    for symbol in word:
        if (
            not isinstance(symbol, Integral)
            or isinstance(symbol, bool)
            or not 0 <= symbol < gamma
        ):
            raise ValueError(f"symbol {symbol} is outside [0,{gamma})")
        rank = rank * gamma + int(symbol)
    return rank


def payload_length(gamma: int, length: int) -> int:
    gamma = _require_integer("gamma", gamma, 2)
    length = _require_integer("length", length, 0)
    if length == 0:
        return 0
    return (gamma**length - 1).bit_length()


def occupancy_factor(gamma: int, length: int) -> float:
    exponent = length * math.log2(gamma) - payload_length(gamma, length)
    return 2.0**exponent


def encode_word(word: Sequence[int], gamma: int) -> str:
    gamma = _require_integer("gamma", gamma, 2)
    length = len(word)
    header = elias_gamma_nonnegative(length)
    width = payload_length(gamma, length)
    if width == 0:
        return header
    rank = word_rank(word, gamma)
    return header + format(rank, f"0{width}b")


def decode_word(code: str, gamma: int) -> tuple[int, ...]:
    """Decode an exact whole-word rank code and reject unused binary ranks."""
    gamma = _require_integer("gamma", gamma, 2)
    length, consumed = decode_elias_gamma_nonnegative(code)
    available_payload = len(code) - consumed
    if length > available_payload:
        raise ValueError("code is too short for the decoded whole-word length")
    width = payload_length(gamma, length)
    if len(code) != consumed + width:
        raise ValueError(
            f"code has length {len(code)}, expected exactly {consumed + width} bits"
        )
    rank = 0 if width == 0 else int(code[consumed:], 2)
    domain_size = gamma**length
    if rank >= domain_size:
        raise ValueError("payload is an unused rank outside the whole-word domain")
    symbols = [0] * length
    for index in range(length - 1, -1, -1):
        rank, symbols[index] = divmod(rank, gamma)
    return tuple(symbols)


def depth_kraft_mass(gamma: int, length: int) -> float:
    q_length = code_weight(elias_header_length(length))
    return q_length * occupancy_factor(gamma, length)


def partial_program_kraft_mass(gamma: int, max_length: int) -> float:
    return sum(depth_kraft_mass(gamma, length) for length in range(max_length + 1))
