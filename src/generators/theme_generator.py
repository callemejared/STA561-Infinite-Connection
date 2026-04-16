"""Theme group generator backed by official statistics plus curated lists."""

from __future__ import annotations

from random import Random

from generators.generator_resources import clone_group, load_theme_bank, normalize_word_key


def list_theme_groups() -> list[dict[str, object]]:
    """Return theme groups from the official dataset plus curated fallbacks."""
    return [clone_group(group) for group in load_theme_bank()]


def category_matches(group: dict[str, object], category: str | None) -> bool:
    """Return True when a group label matches a requested theme hint."""
    if not category:
        return True

    label = str(group["label"]).upper()
    requested = str(category).upper()
    return requested in label or label in requested


def words_available(group: dict[str, object], used_words: set[str] | None) -> bool:
    """Return True when the group can be used without reusing puzzle words."""
    if not used_words:
        return True

    return not used_words.intersection(normalize_word_key(word) for word in group["words"])


def sample_theme_group(
    rng: Random,
    category: str | None = None,
    used_words: set[str] | None = None,
) -> dict[str, object]:
    """Sample one theme group while respecting already-used words."""
    candidates = [
        group
        for group in list_theme_groups()
        if category_matches(group, category) and words_available(group, used_words)
    ]

    if not candidates:
        raise ValueError("Could not find an available theme group for the requested category.")

    return clone_group(rng.choice(candidates))
