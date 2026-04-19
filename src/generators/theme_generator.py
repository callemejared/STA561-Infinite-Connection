"""Theme group generator backed by v4 distractibility scoring."""

from __future__ import annotations

from functools import lru_cache
from random import Random

from generators.generator_resources import (
    ambiguous_broad_categories,
    attach_difficulty_metadata,
    clone_group,
    load_independent_theme_bank,
    load_theme_bank,
    normalize_word_key,
    revealing_label_overlap,
    theme_global_distractibility,
)


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


def _is_valid_theme_group(group: dict[str, object]) -> bool:
    """Return True when a theme group passes v4 prefilters."""
    group_words = {normalize_word_key(word) for word in group["words"]}

    if len(group_words) != 4:
        return False

    if revealing_label_overlap(group):
        return False

    if ambiguous_broad_categories(group):
        return False

    return True


@lru_cache(maxsize=1)
def list_theme_groups() -> list[dict[str, object]]:
    """Return filtered theme groups with global distractibility metadata."""
    filtered_groups = [clone_group(group) for group in load_theme_bank() if _is_valid_theme_group(group)]
    raw_scores = [float(theme_global_distractibility(str(group["label"]), list(group["words"]))) for group in filtered_groups]
    enriched_groups = attach_difficulty_metadata(filtered_groups, raw_scores, component_name="theme_distractibility")

    for group, raw_score in zip(enriched_groups, raw_scores):
        group["metadata"] = {
            "broad_category_flags": ambiguous_broad_categories(group),
            "self_revealing_words": revealing_label_overlap(group),
            "global_distractibility": raw_score,
        }

    return [clone_group(group) for group in enriched_groups]


@lru_cache(maxsize=1)
def list_independent_theme_groups_v6() -> list[dict[str, object]]:
    """Return only independently authored theme groups for the v6 final workflow."""
    filtered_groups = [clone_group(group) for group in load_independent_theme_bank() if _is_valid_theme_group(group)]
    raw_scores = [float(theme_global_distractibility(str(group["label"]), list(group["words"]))) for group in filtered_groups]
    enriched_groups = attach_difficulty_metadata(filtered_groups, raw_scores, component_name="theme_distractibility")

    for group, raw_score in zip(enriched_groups, raw_scores):
        group["metadata"] = {
            "broad_category_flags": ambiguous_broad_categories(group),
            "self_revealing_words": revealing_label_overlap(group),
            "global_distractibility": raw_score,
            "theme_source": "independent_v6",
        }

    return [clone_group(group) for group in enriched_groups]


def sample_theme_group(
    rng: Random,
    category: str | None = None,
    used_words: set[str] | None = None,
    required_tier: str | None = None,
) -> dict[str, object]:
    """Sample one theme group while respecting already-used words."""
    candidates = [
        group
        for group in list_theme_groups()
        if category_matches(group, category)
        and words_available(group, used_words)
        and (required_tier is None or group["difficulty"]["tier"] == required_tier)
    ]

    if not candidates:
        raise ValueError("Could not find an available theme group for the requested category.")

    return clone_group(rng.choice(candidates))
