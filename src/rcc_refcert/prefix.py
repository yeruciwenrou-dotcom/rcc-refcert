from __future__ import annotations

from collections.abc import Iterable


def is_binary_word(word: str) -> bool:
    return isinstance(word, str) and bool(word) and set(word) <= {"0", "1"}


def prefix_conflicts(codewords: Iterable[str]) -> list[tuple[str, str]]:
    words = list(codewords)
    conflicts: list[tuple[str, str]] = []
    for i, left in enumerate(words):
        for j, right in enumerate(words):
            if i == j:
                continue
            if right.startswith(left):
                conflicts.append((left, right))
    return conflicts


def is_prefix_free(codewords: Iterable[str]) -> bool:
    words = list(codewords)
    return all(is_binary_word(word) for word in words) and not prefix_conflicts(words)


def kraft_sum(codewords: Iterable[str]) -> float:
    return sum(2.0 ** (-len(word)) for word in codewords)


def elias_gamma_nonnegative(value: int) -> str:
    """Encode value >= 0 by applying Elias-gamma to value+1."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("value must be nonnegative")
    payload = bin(value + 1)[2:]
    return "0" * (len(payload) - 1) + payload


def decode_elias_gamma_nonnegative(code: str) -> tuple[int, int]:
    """Decode one nonnegative Elias-gamma header.

    The second return value is the number of consumed bits, allowing a caller
    to parse a following payload while still enforcing an exact outer domain.
    """
    if not isinstance(code, str) or not code or set(code) - {"0", "1"}:
        raise ValueError("code must be a nonempty binary string")
    zero_count = 0
    while zero_count < len(code) and code[zero_count] == "0":
        zero_count += 1
    if zero_count == len(code):
        raise ValueError("truncated Elias-gamma header")
    consumed = 2 * zero_count + 1
    if len(code) < consumed:
        raise ValueError("truncated Elias-gamma header")
    encoded_positive = int(code[zero_count:consumed], 2)
    return encoded_positive - 1, consumed


def elias_header_length(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("value must be nonnegative")
    return 2 * (value + 1).bit_length() - 1
