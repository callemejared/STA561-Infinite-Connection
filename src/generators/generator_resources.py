"""Shared resource loaders for the v2 puzzle generators."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from data_utils.dataset_loader import load_or_build_dataset_assets
from generators.category_bank import FORM_GROUPS, SEMANTIC_GROUPS, THEME_GROUPS

CategoryGroup = dict[str, Any]

CURATED_THEME_GROUPS: list[CategoryGroup] = [
    {"label": "Major U.S. cities", "type": "theme", "words": ["AUSTIN", "BOSTON", "CHICAGO", "SEATTLE"]},
    {"label": "Classic movie monsters", "type": "theme", "words": ["DRACULA", "FRANKENSTEIN", "MUMMY", "WEREWOLF"]},
    {"label": "Pizza toppings", "type": "theme", "words": ["BASIL", "MUSHROOM", "OLIVE", "PEPPERONI"]},
    {"label": "At a farmers market", "type": "theme", "words": ["BASKET", "HONEY", "PEACH", "TOMATO"]},
    {"label": "Awards show words", "type": "theme", "words": ["ENVELOPE", "NOMINEE", "SPEECH", "STATUETTE"]},
    {"label": "At a sushi bar", "type": "theme", "words": ["EDAMAME", "MAKI", "NORI", "WASABI"]},
]

CURATED_FORM_GROUPS: list[CategoryGroup] = [
    {"label": "Rhymes with CAKE", "type": "form", "words": ["BAKE", "CAKE", "LAKE", "RAKE"]},
    {"label": "Rhymes with BELL", "type": "form", "words": ["BELL", "DELL", "SELL", "TELL"]},
    {"label": "Sound like letters", "type": "form", "words": ["ARE", "QUEUE", "SEA", "WHY"]},
]

CURATED_ANAGRAM_GROUPS: list[CategoryGroup] = [
    {"label": "Anagrams", "type": "anagram", "words": ["ALERT", "ALTER", "ARTEL", "LATER"]},
    {"label": "Anagrams", "type": "anagram", "words": ["CARET", "CATER", "CRATE", "TRACE"]},
]


def normalize_word_key(word: Any) -> str:
    """Return a comparison-friendly version of a word."""
    cleaned = "".join(character for character in str(word).upper() if character.isalnum())
    return cleaned or str(word).strip().upper()


def clone_group(group: CategoryGroup, group_type: str | None = None) -> CategoryGroup:
    """Return a mutable copy of one group dictionary."""
    return {
        "label": str(group["label"]),
        "type": group_type if group_type is not None else str(group["type"]),
        "words": [str(word).upper() for word in group["words"]],
    }


def dedupe_groups(groups: list[CategoryGroup]) -> list[CategoryGroup]:
    """Drop exact duplicate groups while preserving order."""
    unique_groups: list[CategoryGroup] = []
    seen_keys: set[tuple[str, tuple[str, ...]]] = set()

    for group in groups:
        key = (
            str(group["type"]),
            tuple(sorted(normalize_word_key(word) for word in group["words"])),
        )

        if key in seen_keys:
            continue

        seen_keys.add(key)
        unique_groups.append(clone_group(group))

    return unique_groups


@lru_cache(maxsize=1)
def load_official_stats_safe() -> dict[str, Any]:
    """Load dataset statistics when available, otherwise return an empty fallback."""
    try:
        _, statistics = load_or_build_dataset_assets()
        return statistics
    except Exception:
        return {
            "category_banks": {"semantic": [], "theme": [], "form": []},
            "word_pool": [],
        }


@lru_cache(maxsize=1)
def load_semantic_bank() -> tuple[CategoryGroup, ...]:
    """Return semantic groups from the dataset plus v1 fallback banks."""
    stats = load_official_stats_safe()
    groups = [clone_group(group) for group in stats["category_banks"].get("semantic", [])]
    groups.extend(clone_group(group) for group in SEMANTIC_GROUPS)
    return tuple(dedupe_groups(groups))


@lru_cache(maxsize=1)
def load_theme_bank() -> tuple[CategoryGroup, ...]:
    """Return theme groups from the dataset plus curated and v1 fallback banks."""
    stats = load_official_stats_safe()
    groups = [clone_group(group) for group in stats["category_banks"].get("theme", [])]
    groups.extend(clone_group(group) for group in CURATED_THEME_GROUPS)
    groups.extend(clone_group(group) for group in THEME_GROUPS)
    return tuple(dedupe_groups(groups))


@lru_cache(maxsize=1)
def load_form_bank() -> tuple[CategoryGroup, ...]:
    """Return form groups from the dataset plus small curated fallback sets."""
    stats = load_official_stats_safe()
    groups = [clone_group(group) for group in stats["category_banks"].get("form", [])]
    groups.extend(clone_group(group) for group in CURATED_FORM_GROUPS)
    groups.extend(clone_group(group) for group in FORM_GROUPS)
    return tuple(dedupe_groups(groups))


@lru_cache(maxsize=1)
def load_anagram_bank() -> tuple[CategoryGroup, ...]:
    """Return anagram-specific groups from curated and official form banks."""
    anagram_groups: list[CategoryGroup] = [clone_group(group) for group in CURATED_ANAGRAM_GROUPS]

    for group in load_form_bank():
        sorted_letters = {"".join(sorted(normalize_word_key(word))) for word in group["words"]}

        if "ANAGRAM" in str(group["label"]).upper() or len(sorted_letters) == 1:
            anagram_groups.append(clone_group(group, group_type="anagram"))

    return tuple(dedupe_groups(anagram_groups))


@lru_cache(maxsize=1)
def load_word_pool() -> tuple[str, ...]:
    """Return a reusable word pool for form-pattern generation."""
    stats = load_official_stats_safe()
    word_pool = {str(word).upper() for word in stats.get("word_pool", [])}

    for group in load_semantic_bank() + load_theme_bank() + load_form_bank() + load_anagram_bank():
        word_pool.update(str(word).upper() for word in group["words"])

    return tuple(sorted(word_pool))
