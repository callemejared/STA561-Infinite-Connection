"""Form-based group generator for sound and letter pattern categories."""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from random import Random

from generators.generator_resources import clone_group, dedupe_groups, load_form_bank, load_word_pool, normalize_word_key


def group_words_available(group: dict[str, object], used_words: set[str] | None) -> bool:
    """Return True when a candidate group avoids words already used."""
    if not used_words:
        return True

    return not used_words.intersection(normalize_word_key(word) for word in group["words"])


@lru_cache(maxsize=1)
def build_prefix_groups() -> tuple[dict[str, object], ...]:
    """Create dynamic shared-prefix groups from the official word pool."""
    buckets: dict[str, list[str]] = defaultdict(list)

    for word in load_word_pool():
        key = normalize_word_key(word)

        if len(key) < 5 or not key.isalpha():
            continue

        buckets[key[:3]].append(str(word).upper())

    groups: list[dict[str, object]] = []

    for prefix, words in sorted(buckets.items()):
        unique_words = sorted(set(words))

        if len(unique_words) < 4 or len(unique_words) > 7:
            continue

        groups.append(
            {
                "label": f"Starts with {prefix}",
                "type": "form",
                "words": unique_words[:4],
            }
        )

    return tuple(dedupe_groups(groups))


@lru_cache(maxsize=1)
def build_suffix_groups() -> tuple[dict[str, object], ...]:
    """Create dynamic shared-suffix groups from the official word pool."""
    buckets: dict[str, list[str]] = defaultdict(list)

    for word in load_word_pool():
        key = normalize_word_key(word)

        if len(key) < 5 or not key.isalpha():
            continue

        buckets[key[-3:]].append(str(word).upper())

    groups: list[dict[str, object]] = []

    for suffix, words in sorted(buckets.items()):
        unique_words = sorted(set(words))

        if len(unique_words) < 4 or len(unique_words) > 7:
            continue

        groups.append(
            {
                "label": f"Ends with {suffix}",
                "type": "form",
                "words": unique_words[:4],
            }
        )

    return tuple(dedupe_groups(groups))


def list_form_groups() -> list[dict[str, object]]:
    """Return all form groups, including dynamic prefix/suffix patterns."""
    groups: list[dict[str, object]] = [clone_group(group) for group in load_form_bank()]
    groups.extend(clone_group(group) for group in build_prefix_groups())
    groups.extend(clone_group(group) for group in build_suffix_groups())
    return dedupe_groups(groups)


def select_form_candidates(subtype: str | None = None) -> list[dict[str, object]]:
    """Filter form groups by a specific subtype when requested."""
    all_groups = list_form_groups()

    if subtype == "prefix":
        return [group for group in all_groups if str(group["label"]).startswith("Starts with ")]
    if subtype == "suffix":
        return [group for group in all_groups if str(group["label"]).startswith("Ends with ")]
    if subtype == "fill_blank":
        return [group for group in all_groups if "___" in str(group["label"])]
    if subtype == "rhyme":
        return [group for group in all_groups if str(group["label"]).startswith("Rhymes with ")]
    if subtype == "homophone":
        return [group for group in all_groups if "SOUND" in str(group["label"]).upper()]

    return all_groups


def sample_form_group(
    rng: Random,
    used_words: set[str] | None = None,
    subtype: str | None = None,
) -> dict[str, object]:
    """Sample one form-based group without reusing words inside a puzzle."""
    candidates = [group for group in select_form_candidates(subtype) if group_words_available(group, used_words)]

    if not candidates:
        raise ValueError("Could not find an available form group for the requested subtype.")

    return clone_group(rng.choice(candidates))
