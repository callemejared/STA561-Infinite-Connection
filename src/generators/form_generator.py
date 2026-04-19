"""Form-based group generator for v4 sound and spelling categories."""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from random import Random

from generators.generator_resources import (
    FORM_PATTERN_COVERAGE_LIMIT,
    ambiguous_broad_categories,
    alpha_word_pool,
    attach_difficulty_metadata,
    clone_group,
    count_words_matching_pattern,
    detect_form_pattern_value,
    detect_form_subtype,
    form_pattern_blacklisted,
    group_rhyme_ending,
    label_rhyme_target,
    load_form_bank,
    normalize_word_key,
    pattern_coverage_ratio,
    pronunciation_list,
    rhyme_ending,
    rhyme_group_contains_target,
)


def group_words_available(group: dict[str, object], used_words: set[str] | None) -> bool:
    """Return True when a candidate group avoids words already used."""
    if not used_words:
        return True

    return not used_words.intersection(normalize_word_key(word) for word in group["words"])


@lru_cache(maxsize=1)
def build_rhyme_groups() -> tuple[dict[str, object], ...]:
    """Create pronunciation-based rhyme groups using CMU phoneme endings."""
    buckets: dict[str, list[str]] = defaultdict(list)

    for word in alpha_word_pool(min_length=3):
        ending = rhyme_ending(word)

        if not ending:
            continue

        buckets[ending].append(str(word).upper())

    groups: list[dict[str, object]] = []

    for ending, words in sorted(buckets.items()):
        unique_words = sorted(set(words))

        if len(unique_words) < 5 or len(unique_words) > 12:
            continue

        coverage = pattern_coverage_ratio("rhyme", ending)

        if coverage > FORM_PATTERN_COVERAGE_LIMIT:
            continue

        target = next((word for word in unique_words[4:] if normalize_word_key(word) not in {normalize_word_key(candidate) for candidate in unique_words[:4]}), None)

        if target is None:
            continue

        groups.append(
            {
                "label": f"Rhymes with {target}",
                "type": "form",
                "words": unique_words[:4],
                "metadata": {
                    "subtype": "rhyme",
                    "pattern_value": ending,
                    "pattern_match_count": count_words_matching_pattern("rhyme", ending),
                    "pattern_coverage": coverage,
                    "rhyme_ending": ending,
                    "rhyme_target": target,
                    "rhyme_frequency": len(unique_words),
                },
            }
        )

    return tuple(groups)


@lru_cache(maxsize=1)
def build_homophone_groups() -> tuple[dict[str, object], ...]:
    """Create pronunciation-based homophone groups from exact phone strings."""
    buckets: dict[str, list[str]] = defaultdict(list)

    for word in alpha_word_pool(min_length=2):
        phones = pronunciation_list(word)

        if not phones:
            continue

        buckets[phones[0]].append(str(word).upper())

    groups: list[dict[str, object]] = []

    for phone_string, words in sorted(buckets.items()):
        unique_words = sorted(set(words))

        if len(unique_words) < 4 or len(unique_words) > 8:
            continue

        groups.append(
            {
                "label": f"Sound like {unique_words[0]}",
                "type": "form",
                "words": unique_words[:4],
                "metadata": {
                    "subtype": "homophone",
                    "pattern_value": phone_string,
                    "pattern_match_count": count_words_matching_pattern("homophone", phone_string),
                    "pattern_coverage": pattern_coverage_ratio("homophone", phone_string),
                },
            }
        )

    return tuple(groups)


def _annotate_existing_form_group(group: dict[str, object]) -> dict[str, object]:
    """Add v4 subtype and pattern metadata to a curated or official form group."""
    annotated_group = clone_group(group)
    subtype = detect_form_subtype(annotated_group)
    pattern_value = detect_form_pattern_value(annotated_group)
    match_count = count_words_matching_pattern(subtype, pattern_value) if subtype else len(annotated_group["words"])
    coverage = pattern_coverage_ratio(subtype, pattern_value) if subtype else 0.0

    metadata = dict(annotated_group.get("metadata", {}))
    metadata.update(
        {
            "subtype": subtype,
            "pattern_value": pattern_value,
            "pattern_match_count": max(match_count, len(annotated_group["words"])),
            "pattern_coverage": coverage,
            "rhyme_ending": group_rhyme_ending(list(annotated_group["words"])) if subtype == "rhyme" else None,
            "rhyme_target": label_rhyme_target(str(annotated_group["label"])) if subtype == "rhyme" else None,
        }
    )
    annotated_group["metadata"] = metadata
    return annotated_group


def _is_valid_form_group(group: dict[str, object]) -> bool:
    """Return True when a form group passes v4 prefilters."""
    group_words = {normalize_word_key(word) for word in group["words"]}

    if len(group_words) != 4:
        return False

    broad_category_flags = ambiguous_broad_categories(group)
    if broad_category_flags:
        return False

    subtype = str(group.get("metadata", {}).get("subtype") or detect_form_subtype(group))
    pattern_value = group.get("metadata", {}).get("pattern_value") or detect_form_pattern_value(group)

    if subtype in {"prefix", "suffix"}:
        return False

    if subtype in {"prefix", "suffix", "rhyme", "homophone"}:
        if form_pattern_blacklisted(str(pattern_value) if pattern_value is not None else None):
            return False

        if pattern_coverage_ratio(subtype, str(pattern_value) if pattern_value is not None else None) > FORM_PATTERN_COVERAGE_LIMIT:
            return False

    if rhyme_group_contains_target(group):
        return False

    return True


@lru_cache(maxsize=1)
def list_form_groups() -> list[dict[str, object]]:
    """Return all v4 form groups, excluding trivial prefix/suffix surface patterns."""
    groups: list[dict[str, object]] = [_annotate_existing_form_group(group) for group in load_form_bank()]
    groups.extend(clone_group(group) for group in build_rhyme_groups())
    groups.extend(clone_group(group) for group in build_homophone_groups())

    filtered_groups = [clone_group(group) for group in groups if _is_valid_form_group(group)]
    filtered_groups = filtered_groups
    raw_scores: list[float] = []

    for group in filtered_groups:
        match_count = int(group.get("metadata", {}).get("pattern_match_count", len(group["words"])))
        raw_scores.append(1.0 / max(match_count, 1))

    enriched_groups = attach_difficulty_metadata(filtered_groups, raw_scores, component_name="pattern_rarity")

    for group, raw_score in zip(enriched_groups, raw_scores):
        metadata = dict(group.get("metadata", {}))
        rhyme_frequency = metadata.get("rhyme_frequency")
        sampling_weight = raw_score

        if rhyme_frequency:
            sampling_weight /= max(float(rhyme_frequency), 1.0)

        metadata.update(
            {
                "broad_category_flags": ambiguous_broad_categories(group),
                "sampling_weight": max(sampling_weight, 0.001),
            }
        )
        group["metadata"] = metadata

    deduped: list[dict[str, object]] = []
    seen_keys: set[tuple[str, tuple[str, ...]]] = set()

    for group in enriched_groups:
        key = (
            str(group.get("metadata", {}).get("subtype") or "form"),
            tuple(sorted(normalize_word_key(word) for word in group["words"])),
        )

        if key in seen_keys:
            continue

        seen_keys.add(key)
        deduped.append(group)

    return [clone_group(group) for group in deduped]


def select_form_candidates(subtype: str | None = None, required_tier: str | None = None) -> list[dict[str, object]]:
    """Filter form groups by a specific subtype and difficulty tier when requested."""
    all_groups = list_form_groups()

    if subtype is not None:
        all_groups = [group for group in all_groups if group.get("metadata", {}).get("subtype") == subtype]

    if required_tier is not None:
        all_groups = [group for group in all_groups if group["difficulty"]["tier"] == required_tier]

    return all_groups


def _weighted_choice(rng: Random, groups: list[dict[str, object]]) -> dict[str, object]:
    """Sample one group with deterministic weighted randomness."""
    weights = [float(group.get("metadata", {}).get("sampling_weight", group["difficulty"]["score"] + 0.05)) for group in groups]
    total = sum(weights)

    if total <= 0:
        return clone_group(rng.choice(groups))

    cutoff = rng.random() * total
    running_total = 0.0

    for group, weight in zip(groups, weights):
        running_total += weight

        if cutoff <= running_total:
            return clone_group(group)

    return clone_group(groups[-1])


def sample_form_group(
    rng: Random,
    used_words: set[str] | None = None,
    subtype: str | None = None,
    required_tier: str | None = None,
    used_rhyme_endings: set[str] | None = None,
) -> dict[str, object]:
    """Sample one form-based group without reusing words or rhyme endings."""
    candidates = [
        group
        for group in select_form_candidates(subtype=subtype, required_tier=required_tier)
        if group_words_available(group, used_words)
    ]

    if used_rhyme_endings:
        candidates = [
            group
            for group in candidates
            if not group.get("metadata", {}).get("rhyme_ending")
            or group["metadata"]["rhyme_ending"] not in used_rhyme_endings
        ]

    if not candidates:
        raise ValueError("Could not find an available form group for the requested subtype.")

    return _weighted_choice(rng, candidates)
