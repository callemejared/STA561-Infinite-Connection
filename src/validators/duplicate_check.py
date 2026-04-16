"""Minimal helpers for comparing generated puzzles against official ones."""

from typing import Any


def canonicalize_puzzle(puzzle: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    """Normalize a puzzle into a simple comparable tuple."""
    canonical_groups = []

    for group in puzzle.get("groups", []):
        words = group.get("words", [])
        normalized_words = tuple(sorted(word.strip().upper() for word in words))
        canonical_groups.append(normalized_words)

    return tuple(sorted(canonical_groups))


def is_duplicate_of_official(
    candidate_puzzle: dict[str, Any],
    official_puzzles: list[dict[str, Any]],
) -> bool:
    """Return True when a candidate exactly matches an official puzzle."""
    candidate_key = canonicalize_puzzle(candidate_puzzle)

    for official_puzzle in official_puzzles:
        if canonicalize_puzzle(official_puzzle) == candidate_key:
            return True

    return False
