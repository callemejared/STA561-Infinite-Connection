"""Semantic group generator for the data-driven v2 pipeline."""

from __future__ import annotations

from random import Random

from generators.generator_resources import clone_group, load_semantic_bank, normalize_word_key


def list_semantic_groups() -> list[dict[str, object]]:
    """Return semantic groups from the official dataset plus fallbacks."""
    return [clone_group(group) for group in load_semantic_bank()]


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


def try_wordnet_group(category: str, used_words: set[str] | None = None) -> dict[str, object] | None:
    """Try building a semantic group from WordNet when NLTK is available."""
    try:
        from nltk.corpus import wordnet as wn
    except Exception:
        return None

    try:
        synsets = wn.synsets(category.replace(" ", "_"))
    except LookupError:
        return None

    candidate_words: list[str] = []
    seen_words: set[str] = set()
    blocked_words = used_words or set()

    for synset in synsets[:4]:
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
                return {
                    "label": category.title(),
                    "type": "semantic",
                    "words": candidate_words,
                }

    return None


def sample_semantic_group(
    rng: Random,
    category: str | None = None,
    used_words: set[str] | None = None,
) -> dict[str, object]:
    """Sample one semantic group without reusing words already in the puzzle."""
    candidates = [
        group
        for group in list_semantic_groups()
        if category_matches(group, category) and words_available(group, used_words)
    ]

    if candidates:
        return clone_group(rng.choice(candidates))

    if category:
        wordnet_group = try_wordnet_group(category, used_words=used_words)

        if wordnet_group is not None:
            return wordnet_group

    raise ValueError("Could not find an available semantic group for the requested category.")
