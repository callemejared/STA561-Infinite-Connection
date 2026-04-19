"""Shared resource helpers for the v4-v6 puzzle generators."""

from __future__ import annotations

import copy
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from data_utils.dataset_loader import load_or_build_dataset_assets
from generators.category_bank import FORM_GROUPS, SEMANTIC_GROUPS, THEME_GROUPS
from generators.similarity_tools import normalize_compact, normalize_phrase, tokenize_text, text_similarity

CategoryGroup = dict[str, Any]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORM_PATTERN_BLACKLIST_PATH = PROJECT_ROOT / "data" / "raw" / "form_pattern_blacklist.txt"
DEFAULT_FORM_PATTERN_BLACKLIST = {"THE", "AND", "FOR", "WITH"}
FORM_PATTERN_COVERAGE_LIMIT = 0.30

BROAD_CATEGORY_HINTS: dict[str, set[str]] = {
    "person": {"ACTOR", "AUTHOR", "BAND", "CELEBRITY", "NAMES", "PEOPLE", "PERSON"},
    "animal": {"ANIMAL", "ANIMALS", "BIRD", "BIRDS", "BREED", "BREEDS", "DOG", "FISH"},
    "food": {"BEVERAGE", "DESSERT", "DISH", "DISHES", "DRINK", "FOOD", "FOODS", "FRUIT"},
    "place": {"AIRPORT", "CITY", "CITIES", "COUNTRY", "COUNTRIES", "PLACE", "PLACES", "STATE", "STATES"},
    "plant": {"FLOWER", "FLOWERS", "PLANT", "PLANTS", "TREE", "TREES"},
    "body_part": {"BODY", "BODILY", "FACE", "HAND", "NOSE", "PART", "PARTS"},
}

CURATED_THEME_GROUPS: list[CategoryGroup] = [
    {"label": "Major U.S. cities", "type": "theme", "words": ["AUSTIN", "BOSTON", "CHICAGO", "SEATTLE"]},
    {"label": "Classic movie monsters", "type": "theme", "words": ["DRACULA", "FRANKENSTEIN", "MUMMY", "WEREWOLF"]},
    {"label": "Pizza toppings", "type": "theme", "words": ["BASIL", "MUSHROOM", "OLIVE", "PEPPERONI"]},
    {"label": "At a farmers market", "type": "theme", "words": ["BASKET", "HONEY", "PEACH", "TOMATO"]},
    {"label": "Awards show words", "type": "theme", "words": ["ENVELOPE", "NOMINEE", "SPEECH", "STATUETTE"]},
    {"label": "At a sushi bar", "type": "theme", "words": ["EDAMAME", "MAKI", "NORI", "WASABI"]},
]

CURATED_FORM_GROUPS: list[CategoryGroup] = [
    {"label": "Rhymes with LIME", "type": "form", "words": ["CHIME", "CRIME", "SLIME", "TIME"]},
    {"label": "Rhymes with COAST", "type": "form", "words": ["GHOST", "MOST", "POST", "ROAST"]},
    {"label": "Rhymes with MINT", "type": "form", "words": ["FLINT", "GLINT", "PRINT", "TINT"]},
]

CURATED_ANAGRAM_GROUPS: list[CategoryGroup] = [
    {"label": "Anagrams", "type": "anagram", "words": ["ALERT", "ALTER", "ARTEL", "LATER"]},
    {"label": "Anagrams", "type": "anagram", "words": ["CARET", "CATER", "CRATE", "TRACE"]},
]

BROAD_CATEGORY_ROOT_NAMES = {
    "person": "person.n.01",
    "animal": "animal.n.01",
    "food": "food.n.02",
    "place": "location.n.01",
    "plant": "plant.n.02",
    "body_part": "body_part.n.01",
}


def normalize_word_key(word: Any) -> str:
    """Return a comparison-friendly version of a word."""
    return normalize_compact(word)


def clone_group(group: CategoryGroup, group_type: str | None = None) -> CategoryGroup:
    """Return a mutable deep copy of one group dictionary."""
    cloned = copy.deepcopy(group)
    cloned["label"] = str(group["label"])
    cloned["type"] = group_type if group_type is not None else str(group["type"])
    cloned["words"] = [str(word).upper() for word in group["words"]]
    return cloned


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


def label_tokens(label: str) -> list[str]:
    """Return the compact content tokens inside a label."""
    return [normalize_word_key(token) for token in tokenize_text(label) if token]


def shared_prefix(words: list[str], prefix_length: int) -> str | None:
    """Return a shared prefix when every word matches it."""
    keys = [normalize_word_key(word) for word in words]

    if len(keys) != 4 or any(len(key) < prefix_length for key in keys):
        return None

    prefix_values = {key[:prefix_length] for key in keys}
    return next(iter(prefix_values)) if len(prefix_values) == 1 else None


def shared_suffix(words: list[str], suffix_length: int) -> str | None:
    """Return a shared suffix when every word matches it."""
    keys = [normalize_word_key(word) for word in words]

    if len(keys) != 4 or any(len(key) < suffix_length for key in keys):
        return None

    suffix_values = {key[-suffix_length:] for key in keys}
    return next(iter(suffix_values)) if len(suffix_values) == 1 else None


def is_anagram_set(words: list[str]) -> bool:
    """Return True when every word is an anagram of the others."""
    keys = [normalize_word_key(word) for word in words]

    if len(keys) != 4 or any(len(key) < 3 for key in keys):
        return False

    return len({"".join(sorted(key)) for key in keys}) == 1


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
            "word_frequency": {},
        }


@lru_cache(maxsize=1)
def load_form_pattern_blacklist() -> frozenset[str]:
    """Load blacklisted form patterns from disk."""
    if not FORM_PATTERN_BLACKLIST_PATH.exists():
        return frozenset(DEFAULT_FORM_PATTERN_BLACKLIST)

    patterns: set[str] = set(DEFAULT_FORM_PATTERN_BLACKLIST)

    for raw_line in FORM_PATTERN_BLACKLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        patterns.add(normalize_word_key(stripped))

    return frozenset(patterns)


@lru_cache(maxsize=1)
def load_semantic_bank() -> tuple[CategoryGroup, ...]:
    """Return semantic groups from the dataset plus fallback banks."""
    stats = load_official_stats_safe()
    groups = [clone_group(group) for group in stats["category_banks"].get("semantic", [])]
    groups.extend(clone_group(group) for group in SEMANTIC_GROUPS)
    return tuple(dedupe_groups(groups))


def semantic_group_signature(group: CategoryGroup) -> tuple[str, tuple[str, ...]]:
    """Return a label-plus-word signature for semantic-bank overlap checks."""
    return (
        normalize_word_key(group["label"]),
        tuple(sorted(normalize_word_key(word) for word in group["words"])),
    )


def semantic_word_signature(group: CategoryGroup) -> tuple[str, ...]:
    """Return a word-only signature for semantic-bank overlap checks."""
    return tuple(sorted(normalize_word_key(word) for word in group["words"]))


@lru_cache(maxsize=1)
def official_semantic_signatures() -> tuple[set[tuple[str, tuple[str, ...]]], set[tuple[str, ...]]]:
    """Return normalized official NYT semantic signatures for duplicate detection."""
    stats = load_official_stats_safe()
    official_groups = [clone_group(group) for group in stats.get("category_banks", {}).get("semantic", [])]
    full_signatures = {semantic_group_signature(group) for group in official_groups}
    word_signatures = {semantic_word_signature(group) for group in official_groups}
    return full_signatures, word_signatures


def assert_semantic_bank_independent(groups: list[CategoryGroup]) -> None:
    """Fail loudly when the independent semantic bank overlaps with official NYT data.

    The final v6 workflow treats semantic-bank overlap as a submission blocker rather
    than something to silently filter away.
    """
    official_full_signatures, official_word_signatures = official_semantic_signatures()
    overlap_messages: list[str] = []

    for group in groups:
        full_signature = semantic_group_signature(group)
        word_signature = semantic_word_signature(group)

        if full_signature in official_full_signatures:
            overlap_messages.append(f"exact semantic overlap: {group['label']} -> {group['words']}")
        elif word_signature in official_word_signatures:
            overlap_messages.append(f"semantic word-set overlap: {group['label']} -> {group['words']}")

    if overlap_messages:
        details = "; ".join(overlap_messages[:10])
        raise RuntimeError(
            "Independent semantic bank overlaps with the official NYT semantic bank. "
            f"v6 final refuses to continue. Details: {details}"
        )


@lru_cache(maxsize=1)
def load_independent_semantic_bank() -> tuple[CategoryGroup, ...]:
    """Return only independently authored semantic groups and verify no NYT overlap."""
    groups = [clone_group(group) for group in SEMANTIC_GROUPS]
    deduped_groups = dedupe_groups(groups)
    assert_semantic_bank_independent(deduped_groups)
    return tuple(deduped_groups)


def bank_group_signature(group: CategoryGroup) -> tuple[str, tuple[str, ...]]:
    """Return a normalized label-plus-word signature for any bank group."""
    return (
        normalize_word_key(group["label"]),
        tuple(sorted(normalize_word_key(word) for word in group["words"])),
    )


def bank_word_signature(group: CategoryGroup) -> tuple[str, ...]:
    """Return a normalized word-only signature for any bank group."""
    return tuple(sorted(normalize_word_key(word) for word in group["words"]))


@lru_cache(maxsize=None)
def official_bank_signatures(group_type: str) -> tuple[set[tuple[str, tuple[str, ...]]], set[tuple[str, ...]]]:
    """Return normalized official NYT signatures for one bank type."""
    stats = load_official_stats_safe()
    official_groups = [clone_group(group) for group in stats.get("category_banks", {}).get(str(group_type), [])]
    full_signatures = {bank_group_signature(group) for group in official_groups}
    word_signatures = {bank_word_signature(group) for group in official_groups}
    return full_signatures, word_signatures


def assert_bank_independent(groups: list[CategoryGroup], official_group_type: str, bank_name: str) -> None:
    """Fail loudly when an independently authored bank overlaps with official NYT data."""
    official_full_signatures, official_word_signatures = official_bank_signatures(official_group_type)
    overlap_messages: list[str] = []

    for group in groups:
        full_signature = bank_group_signature(group)
        word_signature = bank_word_signature(group)

        if full_signature in official_full_signatures:
            overlap_messages.append(f"exact {bank_name} overlap: {group['label']} -> {group['words']}")
        elif word_signature in official_word_signatures:
            overlap_messages.append(f"{bank_name} word-set overlap: {group['label']} -> {group['words']}")

    if overlap_messages:
        details = "; ".join(overlap_messages[:10])
        raise RuntimeError(
            f"Independent {bank_name} bank overlaps with the official NYT {official_group_type} bank. "
            f"v6 final refuses to continue. Details: {details}"
        )


def filter_groups_against_official_bank(groups: list[CategoryGroup], official_group_type: str) -> list[CategoryGroup]:
    """Drop groups that exactly overlap with the official NYT bank for one type.

    v6 uses this for dynamically generated form-like groups. Independently authored
    banks are checked more strictly with `assert_bank_independent(...)`.
    """
    official_full_signatures, official_word_signatures = official_bank_signatures(official_group_type)
    filtered_groups: list[CategoryGroup] = []

    for group in groups:
        full_signature = bank_group_signature(group)
        word_signature = bank_word_signature(group)

        if full_signature in official_full_signatures or word_signature in official_word_signatures:
            continue

        filtered_groups.append(clone_group(group))

    return filtered_groups


@lru_cache(maxsize=1)
def load_theme_bank() -> tuple[CategoryGroup, ...]:
    """Return theme groups from the dataset plus curated and fallback banks."""
    stats = load_official_stats_safe()
    groups = [clone_group(group) for group in stats["category_banks"].get("theme", [])]
    groups.extend(clone_group(group) for group in CURATED_THEME_GROUPS)
    groups.extend(clone_group(group) for group in THEME_GROUPS)
    return tuple(dedupe_groups(groups))


@lru_cache(maxsize=1)
def load_independent_theme_bank() -> tuple[CategoryGroup, ...]:
    """Return only independently authored theme groups and verify no NYT overlap."""
    groups = [clone_group(group) for group in CURATED_THEME_GROUPS]
    groups.extend(clone_group(group) for group in THEME_GROUPS)
    deduped_groups = dedupe_groups(groups)
    assert_bank_independent(deduped_groups, official_group_type="theme", bank_name="theme")
    return tuple(deduped_groups)


@lru_cache(maxsize=1)
def load_form_bank() -> tuple[CategoryGroup, ...]:
    """Return form groups from the dataset plus curated fallback sets."""
    stats = load_official_stats_safe()
    groups = [clone_group(group) for group in stats["category_banks"].get("form", [])]
    groups.extend(clone_group(group) for group in CURATED_FORM_GROUPS)
    groups.extend(clone_group(group) for group in FORM_GROUPS)
    return tuple(dedupe_groups(groups))


@lru_cache(maxsize=1)
def load_independent_form_bank() -> tuple[CategoryGroup, ...]:
    """Return only independently authored form groups and verify no NYT overlap."""
    groups = [clone_group(group) for group in CURATED_FORM_GROUPS]
    groups.extend(clone_group(group) for group in FORM_GROUPS)
    deduped_groups = dedupe_groups(groups)
    assert_bank_independent(deduped_groups, official_group_type="form", bank_name="form")
    return tuple(deduped_groups)


@lru_cache(maxsize=1)
def load_anagram_bank() -> tuple[CategoryGroup, ...]:
    """Return anagram-specific groups from curated and official form banks."""
    anagram_groups: list[CategoryGroup] = [clone_group(group) for group in CURATED_ANAGRAM_GROUPS]

    for group in load_form_bank():
        if "ANAGRAM" in str(group["label"]).upper() or is_anagram_set(list(group["words"])):
            anagram_groups.append(clone_group(group, group_type="anagram"))

    return tuple(dedupe_groups(anagram_groups))


@lru_cache(maxsize=1)
def load_independent_anagram_bank() -> tuple[CategoryGroup, ...]:
    """Return only independently authored anagram groups and verify no NYT overlap.

    Official NYT anagram-style groups live inside the broader form bank, so the
    overlap check is performed against the official `form` bank.
    """
    anagram_groups: list[CategoryGroup] = [clone_group(group) for group in CURATED_ANAGRAM_GROUPS]
    deduped_groups = dedupe_groups(anagram_groups)
    assert_bank_independent(deduped_groups, official_group_type="form", bank_name="anagram")
    return tuple(deduped_groups)


@lru_cache(maxsize=1)
def load_word_pool() -> tuple[str, ...]:
    """Return a reusable word pool for form-pattern generation."""
    stats = load_official_stats_safe()
    word_pool = {str(word).upper() for word in stats.get("word_pool", [])}

    for group in load_semantic_bank() + load_theme_bank() + load_form_bank() + load_anagram_bank():
        word_pool.update(str(word).upper() for word in group["words"])

    return tuple(sorted(word_pool))


@lru_cache(maxsize=1)
def load_word_frequency() -> dict[str, int]:
    """Return dataset word frequency counts keyed by display form."""
    stats = load_official_stats_safe()
    return {str(word).upper(): int(count) for word, count in stats.get("word_frequency", {}).items()}


def alpha_word_pool(min_length: int = 3) -> tuple[str, ...]:
    """Return alphabetic words from the pool for pattern generation."""
    return tuple(
        word
        for word in load_word_pool()
        if normalize_word_key(word).isalpha() and len(normalize_word_key(word)) >= min_length
    )


@lru_cache(maxsize=1)
def load_word_pool_keys() -> tuple[str, ...]:
    """Return compact keys for every word in the pool."""
    return tuple(normalize_word_key(word) for word in load_word_pool())


@lru_cache(maxsize=1)
def load_word_pool_size() -> int:
    """Return the current reusable word-pool size."""
    return len(load_word_pool())


@lru_cache(maxsize=None)
def wordnet_available() -> bool:
    """Return True when the WordNet corpus is ready to use."""
    try:
        from nltk.corpus import wordnet as wn
        wn.synsets("dog")
        return True
    except Exception:
        return False


@lru_cache(maxsize=None)
def pronouncing_available() -> bool:
    """Return True when the pronouncing package is installed."""
    try:
        import pronouncing  # noqa: F401
        return True
    except Exception:
        return False


@lru_cache(maxsize=None)
def pronunciation_list(word: str) -> tuple[str, ...]:
    """Return CMU pronunciations for one word."""
    if not pronouncing_available():
        return ()

    import pronouncing

    phones = pronouncing.phones_for_word(normalize_phrase(word).lower())
    return tuple(str(phone) for phone in phones)


@lru_cache(maxsize=None)
def rhyme_ending(word: str) -> str | None:
    """Return the phoneme suffix used for rhyming when available."""
    if not pronouncing_available():
        return None

    import pronouncing

    phones = pronunciation_list(word)

    if not phones:
        return None

    return str(pronouncing.rhyming_part(phones[0]))


def group_rhyme_ending(words: list[str]) -> str | None:
    """Return a shared rhyme ending when every word shares the same phoneme tail."""
    endings = {rhyme_ending(word) for word in words}
    endings.discard(None)

    if len(endings) != 1:
        return None

    return next(iter(endings))


def label_rhyme_target(label: str) -> str | None:
    """Extract the target word from labels such as 'Rhymes with LIME'."""
    normalized = normalize_phrase(label)
    match = re.search(r"RHYMES?\s+WITH\s+(.+)$", normalized)

    if not match:
        return None

    target = normalize_word_key(match.group(1))
    return target or None


def detect_form_subtype(group: CategoryGroup) -> str | None:
    """Infer a v4 form subtype from the label or word pattern."""
    label = normalize_phrase(group["label"])
    words = [str(word).upper() for word in group["words"]]

    if "ANAGRAM" in label or is_anagram_set(words):
        return "anagram"
    if "RHYME" in label or group_rhyme_ending(words):
        return "rhyme"
    if "HOMOPHONE" in label or "SOUND" in label:
        return "homophone"
    if "___" in label:
        return "fill_blank"

    prefix = shared_prefix(words, 3)
    if prefix:
        return "prefix"

    suffix = shared_suffix(words, 3)
    if suffix:
        return "suffix"

    return "pattern"


def detect_form_pattern_value(group: CategoryGroup) -> str | None:
    """Return the normalized surface or phonetic pattern for a form group."""
    subtype = detect_form_subtype(group)
    words = [str(word).upper() for word in group["words"]]

    if subtype == "prefix":
        return shared_prefix(words, 3)
    if subtype == "suffix":
        return shared_suffix(words, 3)
    if subtype == "rhyme":
        ending = group_rhyme_ending(words)
        if ending:
            return ending
        target = label_rhyme_target(str(group["label"]))
        return rhyme_ending(target) if target else None
    if subtype == "homophone":
        first_word = words[0]
        phones = pronunciation_list(first_word)
        return phones[0] if phones else normalize_word_key(first_word)
    if subtype == "anagram":
        return "".join(sorted(normalize_word_key(words[0])))

    return None


def label_mentions_broad_category(label: str, category_name: str) -> bool:
    """Return True when a label explicitly names a broad category."""
    label_token_set = set(label_tokens(label))
    hint_tokens = {normalize_word_key(token) for token in BROAD_CATEGORY_HINTS.get(category_name, set())}
    return bool(label_token_set.intersection(hint_tokens))


@lru_cache(maxsize=1)
def _broad_category_root_synsets() -> dict[str, Any]:
    """Return cached WordNet synsets for broad category roots."""
    if not wordnet_available():
        return {}

    from nltk.corpus import wordnet as wn

    roots: dict[str, Any] = {}

    for category_name, synset_name in BROAD_CATEGORY_ROOT_NAMES.items():
        try:
            roots[category_name] = wn.synset(synset_name)
        except Exception:
            continue

    return roots


@lru_cache(maxsize=4096)
def word_broad_categories(word: str) -> tuple[str, ...]:
    """Return broad WordNet categories that a word can belong to."""
    if not wordnet_available():
        return ()

    from nltk.corpus import wordnet as wn

    candidate_term = normalize_phrase(word).replace(" ", "_").lower()
    roots = _broad_category_root_synsets()
    categories: set[str] = set()

    for synset in wn.synsets(candidate_term, pos=wn.NOUN):
        hypernyms = {synset}
        hypernyms.update(synset.closure(lambda current: current.hypernyms()))

        for category_name, root_synset in roots.items():
            if root_synset in hypernyms:
                categories.add(category_name)

    return tuple(sorted(categories))


def ambiguous_broad_categories(group: CategoryGroup) -> dict[str, list[str]]:
    """Return broad categories that cover multiple words inside one group."""
    flagged: dict[str, list[str]] = {}

    for word in group["words"]:
        for category_name in word_broad_categories(str(word)):
            flagged.setdefault(category_name, []).append(str(word))

    return {
        category_name: sorted(set(words))
        for category_name, words in flagged.items()
        if len(set(words)) >= 2 and not label_mentions_broad_category(str(group["label"]), category_name)
    }


def revealing_label_overlap(group: CategoryGroup) -> list[str]:
    """Return words that directly reveal a non-form label."""
    group_type = normalize_word_key(group["type"])

    if group_type == "FORM":
        return []

    revealing_tokens = [token for token in label_tokens(str(group["label"])) if len(token) >= 4]
    overlaps: list[str] = []

    for word in group["words"]:
        normalized_word = normalize_word_key(word)

        if any(token == normalized_word or token in normalized_word for token in revealing_tokens):
            overlaps.append(str(word))

    return overlaps


def rhyme_group_contains_target(group: CategoryGroup) -> bool:
    """Return True when a rhyme group includes the word named in its own label."""
    if detect_form_subtype(group) != "rhyme":
        return False

    target = label_rhyme_target(str(group["label"]))

    if not target:
        return False

    return any(normalize_word_key(word) == target for word in group["words"])


def normalize_scores(raw_scores: list[float]) -> list[float]:
    """Scale a list of scores to [0, 1]."""
    if not raw_scores:
        return []

    minimum = min(raw_scores)
    maximum = max(raw_scores)

    if maximum <= minimum:
        return [0.5 for _ in raw_scores]

    return [(score - minimum) / (maximum - minimum) for score in raw_scores]


def difficulty_tier(score: float) -> str:
    """Map a normalized score into easy, medium, or hard."""
    if score < 0.34:
        return "easy"
    if score < 0.67:
        return "medium"
    return "hard"


@lru_cache(maxsize=2048)
def label_wordnet_depth(label: str) -> int:
    """Estimate semantic specificity from WordNet hypernym depth."""
    if not wordnet_available():
        return 0

    from nltk.corpus import wordnet as wn

    candidates: list[str] = []
    normalized_label = normalize_phrase(label)
    content_tokens = [token.lower() for token in tokenize_text(label) if len(token) > 2]

    if normalized_label:
        candidates.append(normalized_label.replace(" ", "_").lower())
    candidates.extend(content_tokens)
    candidates.extend(token[:-1] for token in content_tokens if token.endswith("s") and len(token) > 3)

    best_depth = 0

    for candidate in candidates:
        for synset in wn.synsets(candidate, pos=wn.NOUN):
            try:
                best_depth = max(best_depth, int(synset.min_depth()))
            except Exception:
                continue

    return best_depth


def theme_global_distractibility(label: str, words: list[str], threshold: float = 0.27) -> int:
    """Estimate how many outside words in the pool also point toward a theme label."""
    count = 0
    group_word_keys = {normalize_word_key(word) for word in words}

    for word in load_word_pool():
        if normalize_word_key(word) in group_word_keys:
            continue

        _, similarity = text_similarity(str(word), label)

        if similarity >= threshold:
            count += 1

    return count


def attach_difficulty_metadata(groups: list[CategoryGroup], raw_scores: list[float], component_name: str) -> list[CategoryGroup]:
    """Attach normalized difficulty metadata to already-filtered groups."""
    normalized_scores = normalize_scores(raw_scores)
    enriched_groups: list[CategoryGroup] = []

    for group, raw_score, normalized_score in zip(groups, raw_scores, normalized_scores):
        enriched_group = clone_group(group)
        enriched_group["difficulty"] = {
            "component": component_name,
            "raw_score": raw_score,
            "score": normalized_score,
            "tier": difficulty_tier(normalized_score),
        }
        enriched_groups.append(enriched_group)

    return enriched_groups


def form_pattern_blacklisted(pattern_value: str | None) -> bool:
    """Return True when a form pattern appears in the blacklist."""
    if not pattern_value:
        return False

    return normalize_word_key(pattern_value) in load_form_pattern_blacklist()


def count_words_matching_pattern(subtype: str, pattern_value: str | None) -> int:
    """Count how many pool words match a specific spelling or phonetic pattern."""
    if not pattern_value:
        return 0

    normalized_pattern = normalize_word_key(pattern_value)
    alpha_words = alpha_word_pool()

    if subtype == "prefix":
        return sum(1 for word in alpha_words if normalize_word_key(word).startswith(normalized_pattern))

    if subtype == "suffix":
        return sum(1 for word in alpha_words if normalize_word_key(word).endswith(normalized_pattern))

    if subtype == "rhyme":
        return sum(1 for word in alpha_words if rhyme_ending(word) == pattern_value)

    if subtype == "homophone":
        return sum(1 for word in alpha_words if pattern_value in pronunciation_list(word))

    return 0


def pattern_coverage_ratio(subtype: str, pattern_value: str | None) -> float:
    """Return the share of the current word pool matched by a pattern."""
    pool_size = max(load_word_pool_size(), 1)
    return count_words_matching_pattern(subtype, pattern_value) / pool_size
