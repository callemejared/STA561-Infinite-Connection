"""Semantic group generator for the v4 pipeline."""

from __future__ import annotations

from functools import lru_cache
from random import Random

from generators.generator_resources import (
    ambiguous_broad_categories,
    attach_difficulty_metadata,
    clone_group,
    label_wordnet_depth,
    load_semantic_bank,
    normalize_word_key,
    revealing_label_overlap,
)


def category_matches(group: dict[str, object], category: str | None) -> bool:
    """Return True when a group label matches the requested category hint."""
    if not category:
        return True

    label = str(group["label"]).upper()
    requested = str(category).upper()
    return requested in label or label in requested


def words_available(group: dict[str, object], used_words: set[str] | None) -> bool:
    """Return True when the group can be used without word reuse."""
    if not used_words:
        return True

    return not used_words.intersection(normalize_word_key(word) for word in group["words"])


def _is_valid_semantic_group(group: dict[str, object]) -> bool:
    """Return True when a semantic group passes v4 prefilters."""
    group_words = {normalize_word_key(word) for word in group["words"]}

    if len(group_words) != 4:
        return False

    if revealing_label_overlap(group):
        return False

    if ambiguous_broad_categories(group):
        return False

    return True


@lru_cache(maxsize=1)
def list_semantic_groups() -> list[dict[str, object]]:
    """Return filtered semantic groups with WordNet difficulty metadata."""
    filtered_groups = [clone_group(group) for group in load_semantic_bank() if _is_valid_semantic_group(group)]
    raw_scores = [float(label_wordnet_depth(str(group["label"]))) for group in filtered_groups]
    enriched_groups = attach_difficulty_metadata(filtered_groups, raw_scores, component_name="wordnet_depth")

    for group, raw_score in zip(enriched_groups, raw_scores):
        group["metadata"] = {
            "broad_category_flags": ambiguous_broad_categories(group),
            "self_revealing_words": revealing_label_overlap(group),
            "wordnet_depth": raw_score,
        }

    return [clone_group(group) for group in enriched_groups]


def try_wordnet_group(category: str, used_words: set[str] | None = None) -> dict[str, object] | None:
    """Try building a semantic group from WordNet when a requested category is missing."""
    try:
        from nltk.corpus import wordnet as wn
    except Exception:
        return None

    candidate_words: list[str] = []
    seen_words: set[str] = set()
    blocked_words = used_words or set()

    for synset in wn.synsets(category.replace(" ", "_"), pos=wn.NOUN)[:8]:
        for lemma in synset.lemma_names():
            word = lemma.replace("_", " ").upper()
            word_key = normalize_word_key(word)

            if word_key in seen_words or word_key in blocked_words:
                continue
            if len(word_key) < 3:
                continue

            seen_words.add(word_key)
            candidate_words.append(word)

            if len(candidate_words) == 4:
                provisional_group = {
                    "label": category.title(),
                    "type": "semantic",
                    "words": candidate_words,
                }

                if not _is_valid_semantic_group(provisional_group):
                    return None

                enriched_group = attach_difficulty_metadata(
                    [provisional_group],
                    [float(label_wordnet_depth(category))],
                    component_name="wordnet_depth",
                )[0]
                enriched_group["metadata"] = {
                    "broad_category_flags": ambiguous_broad_categories(enriched_group),
                    "self_revealing_words": revealing_label_overlap(enriched_group),
                    "wordnet_depth": float(label_wordnet_depth(category)),
                }
                return enriched_group

    return None


def sample_semantic_group(
    rng: Random,
    category: str | None = None,
    used_words: set[str] | None = None,
    required_tier: str | None = None,
) -> dict[str, object]:
    """Sample one semantic group without reusing words already in the puzzle."""
    candidates = [
        group
        for group in list_semantic_groups()
        if category_matches(group, category)
        and words_available(group, used_words)
        and (required_tier is None or group["difficulty"]["tier"] == required_tier)
    ]

    if candidates:
        return clone_group(rng.choice(candidates))

    if category:
        wordnet_group = try_wordnet_group(category, used_words=used_words)

        if wordnet_group is not None and (required_tier is None or wordnet_group["difficulty"]["tier"] == required_tier):
            return wordnet_group

    raise ValueError("Could not find an available semantic group for the requested category.")
